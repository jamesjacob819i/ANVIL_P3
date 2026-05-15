import os
import json
import asyncio
from typing import Callable, Awaitable, Optional

import redis.asyncio as aioredis

from shared.events import SentinelEvent, TOPICS

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
STREAM_MAXLEN = 10000
CONSUMER_GROUP = "sentinel-workers"


class EventBus:
    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None

    async def connect(self):
        self.redis = await aioredis.from_url(
            f"redis://{REDIS_HOST}:{REDIS_PORT}",
            decode_responses=False,
        )
        for topic in TOPICS:
            try:
                await self.redis.xgroup_create(topic, CONSUMER_GROUP, mkstream=True)
            except aioredis.ResponseError as e:
                if "BUSYGROUP" not in str(e):
                    raise

    async def publish(self, event: SentinelEvent) -> None:
        if self.redis is None:
            await self.connect()
        stream_data = {}
        for k, v in event.model_dump().items():
            if isinstance(v, dict):
                stream_data[k.encode()] = json.dumps(v).encode()
            elif isinstance(v, bool):
                stream_data[k.encode()] = b"true" if v else b"false"
            else:
                stream_data[k.encode()] = str(v).encode()
        await self.redis.xadd(event.topic, stream_data, maxlen=STREAM_MAXLEN)

    async def subscribe(
        self,
        topic: str,
        consumer_name: str,
        callback: Callable[[SentinelEvent], Awaitable[None]],
        batch_size: int = 1,
        poll_interval: float = 1.0,
        group_name: str = None,
    ) -> None:
        if group_name is None:
            group_name = consumer_name.rsplit('_', 1)[0]
            
        if self.redis is None:
            await self.connect()
            
        try:
            await self.redis.xgroup_create(topic, group_name, mkstream=True)
        except aioredis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                pass
                
        while True:
            try:
                results = await self.redis.xreadgroup(
                    group_name,
                    consumer_name,
                    {topic: ">"},
                    count=batch_size,
                    block=2000,
                )
                if results:
                    for stream_name, messages in results:
                        for msg_id, msg_data in messages:
                            try:
                                event = SentinelEvent.from_stream_dict(msg_data)
                                await callback(event)
                                await self.redis.xack(topic, group_name, msg_id)
                            except Exception as e:
                                print(f"[{consumer_name}] Error processing msg {msg_id}: {e}")
                                await self.redis.xack(topic, group_name, msg_id)
                else:
                    await asyncio.sleep(poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[{consumer_name}] Subscription error: {e}")
                await asyncio.sleep(poll_interval)

    async def close(self):
        if self.redis:
            await self.redis.close()

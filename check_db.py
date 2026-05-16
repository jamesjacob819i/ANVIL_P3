import asyncio
import os
import sys

# Ensure shared module can be found
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from shared.db import get_session, AgentRun
from sqlalchemy import select

async def main():
    async with get_session() as session:
        result = await session.execute(select(AgentRun).order_by(AgentRun.created_at.desc()).limit(20))
        runs = result.scalars().all()
        for run in runs:
            print(f"[{run.created_at}] {run.agent_name} -> {run.status}")
            if run.status == "failed":
                print(f"  Error: {run.result_payload.get('error')}")

asyncio.run(main())

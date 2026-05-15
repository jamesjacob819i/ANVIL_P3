import uuid
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from typing import Any, Optional


class SentinelEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str
    parent_event_id: Optional[str] = None
    topic: str
    agent_name: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    def to_stream_dict(self) -> dict[bytes, bytes]:
        d = self.model_dump()
        return {k.encode(): str(v).encode() if not isinstance(v, (bytes, str)) else str(v).encode() for k, v in d.items()}

    @classmethod
    def from_stream_dict(cls, data: dict[bytes, bytes]) -> "SentinelEvent":
        decoded = {k.decode(): v.decode() for k, v in data.items()}

        payload_str = decoded.pop("payload", "{}")
        import json
        try:
            decoded["payload"] = json.loads(payload_str)
        except (json.JSONDecodeError, TypeError):
            decoded["payload"] = {}

        bool_fields = {}
        for k in list(decoded.keys()):
            if decoded[k] == "True":
                decoded[k] = True
            elif decoded[k] == "False":
                decoded[k] = False

        return cls(**decoded)


TOPICS = [
    "incidents.new",
    "triage.done",
    "diagnostics.done",
    "rca.done",
    "fix.done",
    "github.pr_merged",
    "deployment.done",
    "postmortem.done",
]

from typing import Optional, Literal
from pydantic import BaseModel

class SharedMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    platform: str
    user_id: str
    source: Literal["user", "assistant"]
    timestamp: Optional[str] = None
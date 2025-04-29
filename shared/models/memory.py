from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class MemorySearch(BaseModel):
    text: str                           = Field(..., description="Text to search in memory")
    component: Optional[str]            = Field(None, description="Filter by component")
    mode: Optional[str]                 = Field(None, description="Filter by mode")
    priority: Optional[float]           = Field(None, ge=0, le=1, description="Filter by priority (0-1 range)")
    limit: Optional[int]                = Field(None, ge=1, description="Max number of results to return")
 
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "text": "What is the weather like today?",
                    "component": "weather",
                    "mode": "query",
                    "priority": 0.8,
                    "limit": 5
                },
                {
                    "text": "Tell me about the latest news.",
                    "component": "news",
                    "mode": "summary",
                    "priority": 0.9,
                    "limit": 10
                }
            ]
        }
    }



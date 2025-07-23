from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class Entity(BaseModel):
    id: str
    name: str   # name of the entity, or original_name if name is null.
    device_id: Optional[str] = None


class Device(BaseModel):
    id: str
    name: str   # name_by_user, or name if name_by_user is null.
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    entities: list[Entity] = []
    area_id: Optional[str] = None  # ID of the area this device is in, if any. area_id is just a lower case version of the area name.

class UserRequest(BaseModel):
    full_request: str
    name: Optional[str] = None


class MediaEvent(BaseModel):
    # Device info
    device_id: str
    device_name: Optional[str] = None
    
    # App/Source info  
    app_name: Optional[str] = None
    media_content_type: Optional[str] = None  # 'music', 'tvshow', 'movie', etc.
    
    # Common media fields
    media_title: Optional[str] = None
    media_duration: Optional[int] = None  # seconds
    media_position: Optional[int] = None  # seconds
    
    # Music specific
    media_artist: Optional[str] = None
    media_album: Optional[str] = None
    media_album_artist: Optional[str] = None
    media_track: Optional[int] = None
    
    # TV/Movie specific
    media_series_title: Optional[str] = None
    media_season: Optional[str] = None
    media_episode: Optional[str] = None
    media_year: Optional[int] = None
    
    # Event info
    event_type: str  # 'play', 'pause', 'stop', 'skip', 'seek'
    timestamp: Optional[datetime] = None
    
    # Raw attributes for debugging
    raw_attributes: Optional[Dict[str, Any]] = None
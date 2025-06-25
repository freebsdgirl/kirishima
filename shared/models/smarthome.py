from pydantic import BaseModel
from typing import Optional

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

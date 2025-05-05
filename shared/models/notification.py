from pydantic import BaseModel, Field
from uuid import uuid4
from datetime import datetime


class Notification(BaseModel):
    """
    A Pydantic model representing a complete notification with its details and transmission history.
    
    Attributes:
        id (str): The unique identifier of the notification, automatically generated using UUID.
        user_id (str): The unique identifier of the user receiving the notification.
        notification (str): The content of the notification message.
        timestamp (str): The timestamp indicating when the notification was created.
        status (str): The current status of the notification (e.g., 'sent', 'pending').
    """
    id: str                             = Field(default_factory=lambda: str(uuid4()), description="The unique identifier of the notification.")
    user_id: str                        = Field(..., description="The unique identifier of the user.")
    notification: str                   = Field(..., description="The notification message to be stored.")
    timestamp: str                      = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"), description="The timestamp when the notification was created.")
    status: str                         = Field("pending", description="The status of the notification (e.g., 'unread', 'read').")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "12345",
                "user_id": "67890",
                "notification": "This is a test notification.",
                "timestamp": "2023-10-01T12:00:00Z",
                "status": "unread",
                "sent": False
            }
        }
    }


class NotificationCreateRequest(BaseModel):
    """
    A Pydantic model representing the request payload for creating a new notification.
    
    Attributes:
        user_id (str): The unique identifier of the user receiving the notification.
        notification (str): The content of the notification message to be stored.
    """
    user_id: str                       = Field(..., description="The unique identifier of the user.")
    notification: str                  = Field(..., description="The notification message to be stored.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "12345",
                "notification": "This is a test notification."
            }
        }
    }


class LastSeen(BaseModel):
    """
    A Pydantic model representing the last seen timestamp for a user.
    
    Attributes:
        user_id (str): The unique identifier of the user.
        timestamp (str): The timestamp when the user was last seen.
        platform (str): The platform from which the user was last seen.
    """
    user_id: str                        = Field(..., description="The unique identifier of the user.")
    timestamp: str                      = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"), description="The timestamp when the user was last seen.")
    platform: str                       = Field(..., description="The platform from which the user was last seen.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "12345",
                "last_seen": "2023-10-01 12:00:00"
            }
        }
    }
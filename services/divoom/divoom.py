"""
This module provides a FastAPI service for sending emoji images to a Divoom Pixoo Max device.

Functions:
    send_emoji(emoji): Sends a specified emoji image to the Divoom device if the image exists.

Classes:
    EmojiRequest: Pydantic model for validating emoji requests.

Endpoints:
    POST /send: Receives an emoji name and sends the corresponding image to the Divoom device,
    skipping the operation if the same emoji was sent previously.

Attributes:
    last_sent_emoji (str or None): Tracks the last emoji sent to avoid redundant transmissions.
"""
import os
from pixoo import PixooMax
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from time import sleep

def send_emoji(emoji):
    pixoo_baddr = "11:75:58:50:B9:8A"
    img_path = f"/home/randi/Pictures/pixelart/{emoji}.png"

    if not os.path.exists(img_path):
        return

    print(f"Sending image {emoji} to Divoom at {pixoo_baddr} from {img_path}")

    pixoo = PixooMax(pixoo_baddr)
    pixoo.connect()

    sleep(1)

    # draw image
    pixoo.draw_pic(img_path)

app = FastAPI()
last_sent_emoji = None  # Track the last sent emoji

class EmojiRequest(BaseModel):
    emoji: str

@app.post("/send")
async def send_emoji_endpoint(request: EmojiRequest):
    """
    Handles sending an emoji via the endpoint.

    If the requested emoji is the same as the last sent emoji, the request is skipped.
    Otherwise, sends the emoji and updates the last sent emoji.

    Args:
        request (EmojiRequest): The request object containing the emoji to be sent.

    Returns:
        dict: A dictionary with the status of the operation, and the emoji.

    Raises:
        HTTPException: If an error occurs during the sending process.
    """
    global last_sent_emoji
    try:
        if request.emoji == last_sent_emoji:
            return {"status": "skipped", "reason": "emoji already sent", "emoji": request.emoji}
        send_emoji(request.emoji)
        last_sent_emoji = request.emoji
        return {"status": "success", "emoji": request.emoji}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

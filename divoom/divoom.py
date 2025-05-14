import os
from pixoo import PixooMax
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from time import sleep

def send_emoji(emoji):
    pixoo_baddr = "11:75:58:50:B9:8A"
    img_path = f"/home/randi/twemoji/assets/72x72/{emoji}.png"

    if not os.path.exists(img_path):
        return

    print(f"Sending emoji {emoji} to Divoom at {pixoo_baddr} from {img_path}")

    pixoo = PixooMax(pixoo_baddr)
    pixoo.connect()

    sleep(1)

    # draw image
    pixoo.draw_pic(img_path)

app = FastAPI()

class EmojiRequest(BaseModel):
    emoji: str

@app.post("/send")
async def send_emoji_endpoint(request: EmojiRequest):
    try:
        send_emoji(request.emoji)
        return {"status": "success", "emoji": request.emoji}
    except Exception as e:
        return
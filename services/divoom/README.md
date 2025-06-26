# Divoom Microservice

This service handles communication with the Divoom Max display over Bluetooth. It is intentionally run outside Docker due to Bluetooth stack headaches.

## Features

- Exposes a single endpoint:  
  - `POST /send` — Accepts JSON payload `{"emoji": "<emoji>"}` to display the emoji on the Divoom Max
- Tracks `last_sent_emoji` to avoid redundant updates
- Uses the [pixoo-client](https://github.com/virtualabs/pixoo-client) library for device interaction

## Setup & Launch

- Not containerized — must run on the host for Bluetooth access
- Start with:
  ```
  uvicorn divoom:app --host 0.0.0.0 --port 5551
  ```

## Configuration

- `pixoo_baddr` — Hardcoded MAC address of your Divoom Max (TODO: make configurable)
- `img_path` — Hardcoded path to emoji image files  
  - Each image is a PNG named with its emoji character (e.g., `🔥.png`)
  - Directory is a local download of the Twemoji set, with filenames rewritten to match the emoji

## Notes

- Current implementation is a stopgap; hardcoded paths and addresses are on the TODO list for future cleanup.
- If you want this to work in Docker, prepare for Bluetooth pain.
# Kirishima TTS Provider for Home Assistant

This integration allows Home Assistant to use a custom TTS server (OpenAI-compatible) for text-to-speech.

## Installation
1. Copy this folder (`kirishima_tts_provider`) to your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Add the integration via configuration.yaml or the UI.

## Configuration Example (configuration.yaml)
tts:
  - platform: kirishima_tts_provider
    name: Custom TTS
    host: 10.3.115.142
    port: 4210
    endpoint: /v1/audio/speech

## Usage
Call the `tts.speak` service with your media player and message.

"""
Custom TTS Provider for Home Assistant
"""

from .tts import KirishimaTTSProvider

async def async_setup(hass, config):
    return True

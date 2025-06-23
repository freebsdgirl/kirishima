"""
Kirishima TTS Provider for Home Assistant
"""
import logging
import aiohttp
import voluptuous as vol
from homeassistant.components.tts import Provider, PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_HOST = "host"
CONF_PORT = "port"
CONF_ENDPOINT = "endpoint"

DEFAULT_NAME = "Kirishima TTS"
DEFAULT_PORT = 4210
DEFAULT_ENDPOINT = "/v1/audio/speech"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_ENDPOINT, default=DEFAULT_ENDPOINT): cv.string,
})

class KirishimaTTSProvider(Provider):
    def __init__(self, hass, name, host, port, endpoint):
        self.hass = hass
        self._name = name
        self._host = host
        self._port = port
        self._endpoint = endpoint
        self._url = f"http://{host}:{port}{endpoint}"

    @property
    def default_language(self):
        return "en-us"

    @property
    def supported_languages(self):
        return ["en-us"]

    @property
    def supported_options(self):
        return []

    @property
    def name(self):
        return self._name

    async def async_get_tts_audio(self, message, language, options=None):
        payload = {
            "input": message,
            "voice": "tony_stark_2",
            "model": "temperature=1.1,exaggeration=0.7,cfg_weight=0.5,gap=0.5"
        }
        headers = {"Content-Type": "application/json"}
        async with aiohttp.ClientSession() as session:
            async with session.post(self._url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    _LOGGER.error("TTS server error: %s", await resp.text())
                    return (None, None)
                audio = await resp.read()
                return ("wav", audio)

def get_engine(hass, config, discovery_info=None):
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    endpoint = config.get(CONF_ENDPOINT)
    return KirishimaTTSProvider(hass, name, host, port, endpoint)


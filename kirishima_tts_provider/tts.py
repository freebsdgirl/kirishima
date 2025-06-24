"""
Kirishima TTS Provider for Home Assistant
"""
import logging
import aiohttp
import voluptuous as vol
from homeassistant.components.tts import Provider, PLATFORM_SCHEMA, TextToSpeechEntity
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv
import wave
import io

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

DOMAIN = "kirishima_tts_provider"

class KirishimaTTSProvider(Provider, TextToSpeechEntity):
    def __init__(self, hass, name, host, port, endpoint, unique_id=None):
        Provider.__init__(self)
        TextToSpeechEntity.__init__(self)
        self.hass = hass
        self._attr_name = name
        self._host = host
        self._port = port
        self._endpoint = endpoint
        self._url = f"http://{host}:{port}{endpoint}"
        self._attr_default_language = "en-us"
        self._attr_supported_languages = [self._attr_default_language]
        self._attr_supported_options = []
        self._attr_unique_id = unique_id or f"{host}:{port}:{endpoint}"
        _LOGGER.info("KirishimaTTSProvider initialized with default_language=%s, supported_languages=%s", self._attr_default_language, self._attr_supported_languages)

    @classmethod
    async def async_create_from_config_entry(cls, hass, config_entry):
        data = config_entry.data
        return cls(
            hass,
            data.get(CONF_NAME, DEFAULT_NAME),
            data.get(CONF_HOST),
            data.get(CONF_PORT, DEFAULT_PORT),
            data.get(CONF_ENDPOINT, DEFAULT_ENDPOINT),
            unique_id=config_entry.entry_id,
        )

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

    @property
    def provider(self):
        return self

    @property
    def supported_languages(self):
        # Always return a valid list
        return self._attr_supported_languages or [self._attr_default_language]
    
    @property
    def default_language(self):
        # Always return a valid default language
        return self._attr_default_language

    @property
    def supported_formats(self):
        # Only advertise support for wav
        return ["wav"]

    @property
    def name(self):
        return self._attr_name

async def async_get_engine(hass, config, discovery_info=None):
    # For YAML setup
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    endpoint = config.get(CONF_ENDPOINT)
    return KirishimaTTSProvider(hass, name, host, port, endpoint)

async def async_get_engine_from_config_entry(hass, config_entry):
    # For UI setup
    return await KirishimaTTSProvider.async_create_from_config_entry(hass, config_entry)

async def async_setup_entry(hass, config_entry, async_add_entities):
    provider = await KirishimaTTSProvider.async_create_from_config_entry(hass, config_entry)
    async_add_entities([provider])

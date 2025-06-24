import voluptuous as vol
from homeassistant import config_entries

DOMAIN = "kirishima_tts_provider"

DATA_SCHEMA = vol.Schema({
    vol.Required("name", default="Kirishima TTS"): str,
    vol.Required("host"): str,
    vol.Optional("port", default=4210): int,
    vol.Optional("endpoint", default="/v1/audio/speech"): str,
})

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            return self.async_create_entry(title=user_input["name"], data=user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

class OptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        return self.async_create_entry(title="", data={})

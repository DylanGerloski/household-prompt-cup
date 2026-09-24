"""Config flow: one entry, no options. The evaluation harness creates the entry itself."""

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult


class NeedleConfigFlow(ConfigFlow, domain="hometiny_needle"):
    """Create the single entry."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Create the entry with no settings."""
        return self.async_create_entry(title="HomeTiny Needle 3", data={})

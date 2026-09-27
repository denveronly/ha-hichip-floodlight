"""Config flow for HiChip Floodlight."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries

from .const import CONF_HOST, CONF_NAME, DEFAULT_NAME, DOMAIN
from .hichip import HiChipFloodlight
from .profile import ProfileError, load_profile


class HiChipConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Ask for camera name + IP; read the device profile from the config dir."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                profile = await self.hass.async_add_executor_job(
                    load_profile, self.hass.config.config_dir
                )
            except ProfileError:
                errors["base"] = "profile_missing"
                profile = None

            if profile is not None:
                await self.async_set_unique_id(f"{DOMAIN}_{user_input[CONF_HOST]}")
                self._abort_if_unique_id_configured()
                client = HiChipFloodlight(
                    host=user_input[CONF_HOST],
                    uid=bytes.fromhex(profile["uid"]),
                    setup=[bytes.fromhex(x) for x in profile["setup"]],
                    cmd_on=bytes.fromhex(profile["cmd_on"]),
                    cmd_off=bytes.fromhex(profile["cmd_off"]),
                    cmd_auto=bytes.fromhex(profile["cmd_auto"]),
                )
                try:
                    ok = await self.hass.async_add_executor_job(client.test_connection)
                except Exception:  # noqa: BLE001
                    ok = False
                if not ok:
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(
                        title=user_input[CONF_NAME],
                        data={CONF_NAME: user_input[CONF_NAME], CONF_HOST: user_input[CONF_HOST]},
                    )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(CONF_HOST): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

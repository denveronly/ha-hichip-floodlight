"""Floodlight switch for a HiChip GF-L300 camera."""
from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_HOST, CONF_NAME, DOMAIN
from .hichip import HiChipFloodlight
from .profile import load_profile

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    profile = await hass.async_add_executor_job(load_profile, hass.config.config_dir)
    client = HiChipFloodlight(
        host=entry.data[CONF_HOST],
        uid=bytes.fromhex(profile["uid"]),
        setup=[bytes.fromhex(x) for x in profile["setup"]],
        cmd_on=bytes.fromhex(profile["cmd_on"]),
        cmd_off=bytes.fromhex(profile["cmd_off"]),
        cmd_auto=bytes.fromhex(profile["cmd_auto"]),
    )
    await hass.async_add_executor_job(client.start)
    async_add_entities([FloodlightSwitch(entry, client)])


class FloodlightSwitch(SwitchEntity):
    """On/off control for the camera's built-in floodlight (optimistic state)."""

    _attr_icon = "mdi:light-flood-down"
    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = None  # entity takes the device (camera) name

    def __init__(self, entry: ConfigEntry, client: HiChipFloodlight) -> None:
        self._client = client
        self._attr_unique_id = f"{entry.entry_id}_floodlight"
        self._attr_is_on = False
        self._attr_available = True
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data[CONF_NAME],
            manufacturer="HiChip",
            model="GF-L300 floodlight camera",
            configuration_url=None,
        )

    async def async_will_remove_from_hass(self) -> None:
        await self.hass.async_add_executor_job(self._client.stop)

    async def async_turn_on(self, **kwargs) -> None:
        await self._send("on", True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._send("off", False)

    async def _send(self, command: str, is_on: bool) -> None:
        try:
            await self.hass.async_add_executor_job(self._client.send, command)
            self._attr_available = True
            self._attr_is_on = is_on
        except Exception as err:  # noqa: BLE001
            self._attr_available = False
            _LOGGER.error("Floodlight command %s failed: %s", command, err)
        self.async_write_ha_state()

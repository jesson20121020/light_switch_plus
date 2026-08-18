"""Light platform for Light Switch+."""
import logging
from typing import Any, Optional

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    LightEntity,
    ColorMode,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SERVICE_TURN_OFF, SERVICE_TURN_ON, STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity
import homeassistant.util.color as color_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
_BRIGHTNESS_PCT = "brightness_pct"
_COLOR_TEMP = "color_temp"
_UNAVAILABLE = {"unavailable", "unknown"}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Light Switch+ from a config entry."""
    config = entry.data
    entity = LightSwitchPlus(
        hass,
        entry.entry_id,
        config.get("name", "Light Switch+"),
        config["switch_entity"],
        config.get("light_entity"),
        config.get("sync_state", True),
    )
    async_add_entities([entity])


class LightSwitchPlus(LightEntity, RestoreEntity):
    """Representation of a Light Switch+ entity."""

    def __init__(
        self,
        hass: HomeAssistant,
        unique_id: str,
        name: str,
        switch_entity: str,
        light_entity: Optional[str],
        sync_state: bool,
    ) -> None:
        """Initialize the entity."""
        self.hass = hass
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._switch_entity = switch_entity
        self._light_entity = light_entity
        self._sync_state = sync_state
        self._attr_is_on = False
        self._attr_brightness = None
        self._attr_color_temp_kelvin = None
        self._attr_rgb_color = None
        self._attr_hs_color = None
        self._attr_effect = None
        self._unsub_listener = None
        self._desired_state: dict[str, Any] = {}
        self._pending_control = False
        self._unavailable_logged = False
        self._attr_supported_features = 0
        self._attr_supported_color_modes = set()
        self._attr_min_color_temp_kelvin = None
        self._attr_max_color_temp_kelvin = None
        self._attr_effect_list = []
        self._attr_color_mode = ColorMode.ONOFF
        self._refresh_capabilities()

    def _refresh_capabilities(self, state=None):
        """Refresh supported color modes and features from the light entity."""
        if not self._light_entity:
            self._attr_supported_color_modes = {ColorMode.ONOFF}
            return
        if state is None:
            state = self.hass.states.get(self._light_entity)
        if state is None:
            return
        attrs = state.attributes or {}
        supported_modes = attrs.get("supported_color_modes")
        if supported_modes:
            self._attr_supported_color_modes = set(supported_modes)
        if not self._attr_supported_color_modes:
            self._attr_supported_color_modes = {ColorMode.ONOFF}
        if attrs.get("min_color_temp_kelvin") is not None:
            self._attr_min_color_temp_kelvin = attrs["min_color_temp_kelvin"]
        if attrs.get("max_color_temp_kelvin") is not None:
            self._attr_max_color_temp_kelvin = attrs["max_color_temp_kelvin"]
        self._attr_effect_list = attrs.get("effect_list", []) or []
        self._attr_supported_features = (
            LightEntityFeature.EFFECT if self._attr_effect_list else 0
        )
        if self._attr_color_mode not in self._attr_supported_color_modes:
            self._attr_color_mode = next(iter(self._attr_supported_color_modes))

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """Return supported color modes."""
        return self._attr_supported_color_modes

    @property
    def extra_state_attributes(self) -> dict:
        """Return entity specific state attributes."""
        return {
            "switch_entity": self._switch_entity,
            "light_entity": self._light_entity,
            "sync_state": self._sync_state,
        }

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=self._attr_name,
            manufacturer="Light Switch+",
        )

    def _apply_light_state(self, state):
        """Project brightness, color temp and mode from an available light state."""
        if state is None or state.state in _UNAVAILABLE:
            return
        attrs = state.attributes or {}
        self._attr_brightness = attrs.get(ATTR_BRIGHTNESS)
        self._attr_color_temp_kelvin = attrs.get(ATTR_COLOR_TEMP_KELVIN)
        self._attr_rgb_color = attrs.get(ATTR_RGB_COLOR)
        self._attr_hs_color = attrs.get(ATTR_HS_COLOR)
        self._attr_effect = attrs.get(ATTR_EFFECT)

        mode = attrs.get(ATTR_COLOR_MODE)
        if mode in self._attr_supported_color_modes:
            self._attr_color_mode = mode
        elif (
            self._attr_color_temp_kelvin is not None
            and ColorMode.COLOR_TEMP in self._attr_supported_color_modes
        ):
            self._attr_color_mode = ColorMode.COLOR_TEMP
        elif (
            (self._attr_hs_color is not None or self._attr_rgb_color is not None)
            and ColorMode.HS in self._attr_supported_color_modes
        ):
            self._attr_color_mode = ColorMode.HS
        elif (
            self._attr_rgb_color is not None
            and ColorMode.RGB in self._attr_supported_color_modes
        ):
            self._attr_color_mode = ColorMode.RGB
        elif (
            self._attr_brightness is not None
            and ColorMode.BRIGHTNESS in self._attr_supported_color_modes
        ):
            self._attr_color_mode = ColorMode.BRIGHTNESS
        elif ColorMode.ONOFF in self._attr_supported_color_modes:
            self._attr_color_mode = ColorMode.ONOFF
        elif self._attr_supported_color_modes:
            self._attr_color_mode = next(iter(self._attr_supported_color_modes))

        desired = {}
        if self._attr_brightness is not None:
            desired[ATTR_BRIGHTNESS] = self._attr_brightness
        if self._attr_color_temp_kelvin is not None:
            desired[ATTR_COLOR_TEMP_KELVIN] = self._attr_color_temp_kelvin
        if self._attr_effect is not None:
            desired[ATTR_EFFECT] = self._attr_effect
        if self._attr_hs_color is not None:
            desired[ATTR_HS_COLOR] = self._attr_hs_color
        elif self._attr_rgb_color is not None:
            desired[ATTR_RGB_COLOR] = self._attr_rgb_color
        self._desired_state = desired

    async def async_update(self) -> None:
        """Update the state."""
        self._refresh_capabilities()
        switch_state = self.hass.states.get(self._switch_entity)
        if switch_state:
            self._attr_is_on = switch_state.state == STATE_ON
            self._attr_available = switch_state.state not in _UNAVAILABLE
        if self._light_entity and self._attr_is_on:
            self._apply_light_state(self.hass.states.get(self._light_entity))

    async def async_added_to_hass(self) -> None:
        """Run when the entity is added to Home Assistant."""
        await super().async_added_to_hass()
        self._refresh_capabilities()

        last_state = await self.async_get_last_state()
        if last_state:
            self._attr_is_on = last_state.state == STATE_ON
            self._apply_light_state(last_state)

        entities_to_track = [self._switch_entity]
        if self._light_entity:
            entities_to_track.append(self._light_entity)
        self._unsub_listener = async_track_state_change_event(
            self.hass, entities_to_track, self._async_state_changed
        )

        self.async_schedule_update_ha_state(True)

    async def async_will_remove_from_hass(self) -> None:
        """Run when the entity is removed from Home Assistant."""
        if self._unsub_listener:
            self._unsub_listener()

    @callback
    def _async_state_changed(self, event):
        """Handle state change events."""
        data = event.data
        _LOGGER.debug("State changed for %s", data.get("entity_id"))
        entity_id = data.get("entity_id")
        new_state = data.get("new_state")
        if new_state is None:
            return
        if entity_id == self._switch_entity:
            self._handle_switch_change(new_state)
        elif entity_id == self._light_entity:
            self._handle_light_change(new_state)
        self.async_write_ha_state()

    def _handle_switch_change(self, new_state):
        """Handle switch state changes."""
        self._attr_is_on = new_state.state == STATE_ON
        self._attr_available = new_state.state not in _UNAVAILABLE
        if self._attr_is_on and self._sync_state and self._light_entity:
            self.hass.async_create_task(self._sync_light_state())

    def _handle_light_change(self, new_state):
        """Handle light state changes."""
        self._refresh_capabilities(new_state)
        if not self._attr_is_on:
            return
        if new_state.state in _UNAVAILABLE:
            return
        self._apply_light_state(new_state)
        if self._pending_control:
            self.hass.async_create_task(self._sync_light_state())

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        old_state = self._attr_is_on
        await self.hass.services.async_call(
            "switch" if self._switch_entity.startswith("switch") else "input_boolean",
            SERVICE_TURN_ON,
            {"entity_id": self._switch_entity},
            blocking=True,
        )
        self._attr_is_on = True
        if not old_state:
            self.async_write_ha_state()
        if self._light_entity and kwargs:
            await self._control_light(**kwargs)
        elif self._light_entity and self._sync_state:
            await self._sync_light_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        old_state = self._attr_is_on
        await self.hass.services.async_call(
            "switch" if self._switch_entity.startswith("switch") else "input_boolean",
            SERVICE_TURN_OFF,
            {"entity_id": self._switch_entity},
            blocking=True,
        )
        self._attr_is_on = False
        if old_state:
            self.async_write_ha_state()

    async def _control_light(self, **kwargs: Any) -> None:
        """Control the underlying light."""
        if not self._light_entity:
            return
        self._apply_control_to_desired(kwargs)
        state = self.hass.states.get(self._light_entity)
        if state is None or state.state in _UNAVAILABLE:
            self._mark_pending()
            return
        service_data = self._control_service_data(kwargs)
        if len(service_data) <= 1:
            return
        try:
            await self.hass.services.async_call(
                "light", SERVICE_TURN_ON, service_data, blocking=True
            )
            self._pending_control = False
            self._unavailable_logged = False
        except Exception:
            _LOGGER.warning(
                "Failed to control underlying light %s",
                self._light_entity,
                exc_info=True,
            )
            self._pending_control = True

    def _control_service_data(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Build service data for the underlying light from HA kwargs."""
        service_data: dict[str, Any] = {"entity_id": self._light_entity}
        supported = self._attr_supported_color_modes

        if ATTR_BRIGHTNESS in kwargs:
            service_data[ATTR_BRIGHTNESS] = kwargs[ATTR_BRIGHTNESS]
        elif _BRIGHTNESS_PCT in kwargs:
            service_data[ATTR_BRIGHTNESS] = self._brightness_from_pct(
                kwargs[_BRIGHTNESS_PCT]
            )

        color_temp_kelvin = kwargs.get(ATTR_COLOR_TEMP_KELVIN)
        if color_temp_kelvin is None and _COLOR_TEMP in kwargs:
            color_temp_kelvin = color_util.color_temperature_mired_to_kelvin(
                kwargs[_COLOR_TEMP]
            )
        if color_temp_kelvin is not None and ColorMode.COLOR_TEMP in supported:
            service_data[ATTR_COLOR_TEMP_KELVIN] = color_temp_kelvin

        if ATTR_EFFECT in kwargs and self._attr_effect_list:
            service_data[ATTR_EFFECT] = kwargs[ATTR_EFFECT]

        if ColorMode.HS in supported and ATTR_HS_COLOR in kwargs:
            service_data[ATTR_HS_COLOR] = kwargs[ATTR_HS_COLOR]
        elif ColorMode.HS in supported and ATTR_RGB_COLOR in kwargs:
            service_data[ATTR_RGB_COLOR] = kwargs[ATTR_RGB_COLOR]
        elif ColorMode.RGB in supported and ATTR_RGB_COLOR in kwargs:
            service_data[ATTR_RGB_COLOR] = kwargs[ATTR_RGB_COLOR]

        return service_data

    def _apply_control_to_desired(self, kwargs: dict[str, Any]) -> None:
        """Merge user control kwargs into the desired state."""
        if ATTR_BRIGHTNESS in kwargs:
            self._desired_state[ATTR_BRIGHTNESS] = kwargs[ATTR_BRIGHTNESS]
        elif _BRIGHTNESS_PCT in kwargs:
            self._desired_state[ATTR_BRIGHTNESS] = self._brightness_from_pct(
                kwargs[_BRIGHTNESS_PCT]
            )

        color_temp_kelvin = kwargs.get(ATTR_COLOR_TEMP_KELVIN)
        if color_temp_kelvin is None and _COLOR_TEMP in kwargs:
            color_temp_kelvin = color_util.color_temperature_mired_to_kelvin(
                kwargs[_COLOR_TEMP]
            )
        if color_temp_kelvin is not None:
            self._desired_state[ATTR_COLOR_TEMP_KELVIN] = color_temp_kelvin

        if ATTR_EFFECT in kwargs and self._attr_effect_list:
            self._desired_state[ATTR_EFFECT] = kwargs[ATTR_EFFECT]

        if ATTR_HS_COLOR in kwargs:
            self._desired_state[ATTR_HS_COLOR] = kwargs[ATTR_HS_COLOR]
            self._desired_state.pop(ATTR_RGB_COLOR, None)
        elif ATTR_RGB_COLOR in kwargs:
            self._desired_state[ATTR_RGB_COLOR] = kwargs[ATTR_RGB_COLOR]
            self._desired_state.pop(ATTR_HS_COLOR, None)

    @staticmethod
    def _brightness_from_pct(pct) -> int:
        """Convert a 0-100 percentage to HA brightness 0-255."""
        return round(255 * min(max(float(pct), 0.0), 100.0) / 100)

    def _mark_pending(self) -> None:
        """Mark pending control and warn once per unavailable phase."""
        self._pending_control = True
        if not self._unavailable_logged:
            _LOGGER.warning(
                "Underlying light %s is unavailable; control will be applied when it recovers",
                self._light_entity,
            )
            self._unavailable_logged = True

    async def _sync_light_state(self) -> None:
        """Sync the desired state to the underlying light."""
        if not self._light_entity:
            return
        state = self.hass.states.get(self._light_entity)
        if state is None or state.state in _UNAVAILABLE:
            self._mark_pending()
            return
        service_data = {"entity_id": self._light_entity}
        service_data.update(self._desired_state)
        try:
            await self.hass.services.async_call(
                "light", SERVICE_TURN_ON, service_data, blocking=True
            )
            self._pending_control = False
            self._unavailable_logged = False
        except Exception:
            _LOGGER.warning(
                "Failed to sync underlying light %s",
                self._light_entity,
                exc_info=True,
            )
            self._pending_control = True

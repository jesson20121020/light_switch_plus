"""Home Assistant module stubs for Light Switch+ tests."""
import os
import sys
import types

import pytest


def _stub_module(name, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module
    return module


def install_ha_stubs():
    """Install minimal HA stubs before importing the integration."""
    if "homeassistant" in sys.modules:
        return

    class ColorMode:
        ONOFF = "onoff"
        BRIGHTNESS = "brightness"
        COLOR_TEMP = "color_temp"
        HS = "hs"
        RGB = "rgb"

    class LightEntityFeature:
        EFFECT = 4

    class LightEntity:
        pass

    class RestoreEntity:
        pass

    class HomeAssistant:
        pass

    class ConfigEntry:
        pass

    class DeviceInfo:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class AddEntitiesCallback:
        pass

    def async_track_state_change_event(hass, entities, callback_fn):
        return lambda: None

    homeassistant = types.ModuleType("homeassistant")
    homeassistant.__path__ = []
    sys.modules["homeassistant"] = homeassistant

    components = types.ModuleType("homeassistant.components")
    components.__path__ = []
    sys.modules["homeassistant.components"] = components

    helpers = types.ModuleType("homeassistant.helpers")
    helpers.__path__ = []
    sys.modules["homeassistant.helpers"] = helpers

    util = types.ModuleType("homeassistant.util")
    util.__path__ = []
    sys.modules["homeassistant.util"] = util

    _stub_module(
        "homeassistant.components.light",
        ATTR_BRIGHTNESS="brightness",
        ATTR_COLOR_MODE="color_mode",
        ATTR_COLOR_TEMP_KELVIN="color_temp_kelvin",
        ATTR_EFFECT="effect",
        ATTR_HS_COLOR="hs_color",
        ATTR_RGB_COLOR="rgb_color",
        LightEntity=LightEntity,
        ColorMode=ColorMode,
        LightEntityFeature=LightEntityFeature,
    )

    _stub_module(
        "homeassistant.config_entries",
        ConfigEntry=ConfigEntry,
    )

    _stub_module(
        "homeassistant.const",
        SERVICE_TURN_OFF="turn_off",
        SERVICE_TURN_ON="turn_on",
        STATE_ON="on",
    )

    _stub_module(
        "homeassistant.core",
        HomeAssistant=HomeAssistant,
        callback=lambda fn: fn,
    )

    _stub_module(
        "homeassistant.helpers.entity",
        DeviceInfo=DeviceInfo,
    )

    _stub_module(
        "homeassistant.helpers.entity_platform",
        AddEntitiesCallback=AddEntitiesCallback,
    )

    _stub_module(
        "homeassistant.helpers.event",
        async_track_state_change_event=async_track_state_change_event,
    )

    _stub_module(
        "homeassistant.helpers.restore_state",
        RestoreEntity=RestoreEntity,
    )

    _stub_module(
        "homeassistant.util.color",
        color_temperature_mired_to_kelvin=lambda mireds: round(1_000_000 / mireds),
    )

    custom_components = types.ModuleType("custom_components")
    custom_components.__path__ = []
    sys.modules["custom_components"] = custom_components

    light_switch_plus = types.ModuleType("custom_components.light_switch_plus")
    light_switch_plus.__path__ = [
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ]
    sys.modules["custom_components.light_switch_plus"] = light_switch_plus

    const = types.ModuleType("custom_components.light_switch_plus.const")
    const.DOMAIN = "light_switch_plus"
    sys.modules["custom_components.light_switch_plus.const"] = const


install_ha_stubs()

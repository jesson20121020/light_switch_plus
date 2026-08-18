"""Tests for Light Switch+ light platform."""
import asyncio

import custom_components.light_switch_plus.light as light_module
from custom_components.light_switch_plus.light import ColorMode, LightEntityFeature, LightSwitchPlus


class FakeState:
    def __init__(self, state, attributes):
        self.state = state
        self.attributes = attributes


class FakeServices:
    def __init__(self):
        self.calls = []

    async def async_call(self, domain, service, service_data, blocking=True):
        self.calls.append((domain, service, service_data, blocking))


class FakeHass:
    def __init__(self, light_state=None):
        self.states = {"light.test": light_state} if light_state else {}
        self.services = FakeServices()
        self.created_tasks = []

    def async_create_task(self, coro):
        self.created_tasks.append(coro)
        return coro


def make_entity(hass):
    return LightSwitchPlus(
        hass,
        "test-id",
        "Test Light",
        "switch.test",
        "light.test",
        True,
    )


def color_temp_state():
    return FakeState(
        "on",
        {
            "supported_color_modes": [ColorMode.COLOR_TEMP],
            "min_color_temp_kelvin": 3000,
            "max_color_temp_kelvin": 6400,
            "effect_list": [],
        },
    )


def test_control_light_forwards_color_temp_kelvin():
    hass = FakeHass(color_temp_state())
    entity = make_entity(hass)

    async def scenario():
        await entity._control_light(brightness=128, color_temp_kelvin=4000)

    asyncio.run(scenario())

    _, _, data, _ = hass.services.calls[0]
    assert data["entity_id"] == "light.test"
    assert data["brightness"] == 128
    assert data["color_temp_kelvin"] == 4000


def test_control_light_converts_brightness_pct():
    hass = FakeHass(color_temp_state())
    entity = make_entity(hass)

    async def scenario():
        await entity._control_light(brightness_pct=40)

    asyncio.run(scenario())

    _, _, data, _ = hass.services.calls[0]
    assert data["brightness"] == 102


def test_control_light_converts_mireds_to_kelvin():
    hass = FakeHass(color_temp_state())
    entity = make_entity(hass)

    async def scenario():
        await entity._control_light(color_temp=250)

    asyncio.run(scenario())

    _, _, data, _ = hass.services.calls[0]
    assert data["color_temp_kelvin"] == 4000


def test_unavailable_light_sets_pending_without_service_call():
    state = FakeState("unavailable", {"supported_color_modes": [ColorMode.COLOR_TEMP]})
    hass = FakeHass(state)
    entity = make_entity(hass)

    async def scenario():
        await entity._control_light(brightness=128)

    asyncio.run(scenario())

    assert hass.services.calls == []
    assert entity._desired_state["brightness"] == 128
    assert entity._pending_control is True


def test_light_recovery_replays_desired_state():
    state = FakeState("unavailable", {"supported_color_modes": [ColorMode.COLOR_TEMP]})
    hass = FakeHass(state)
    entity = make_entity(hass)
    entity._attr_is_on = True

    async def control():
        await entity._control_light(brightness=128)

    asyncio.run(control())
    assert entity._pending_control is True

    available = FakeState(
        "on",
        {
            "color_mode": ColorMode.COLOR_TEMP,
            "brightness": 128,
            "color_temp_kelvin": 4000,
            "effect": None,
            "supported_color_modes": [ColorMode.COLOR_TEMP],
        },
    )
    hass.states["light.test"] = available
    entity._handle_light_change(available)

    assert len(hass.created_tasks) == 1
    asyncio.run(hass.created_tasks[0])
    assert entity._pending_control is False
    assert hass.services.calls[0][2]["brightness"] == 128


def test_capabilities_keep_color_temp_when_unavailable():
    state = FakeState(
        "unavailable",
        {
            "supported_color_modes": [ColorMode.COLOR_TEMP],
            "min_color_temp_kelvin": 3000,
            "max_color_temp_kelvin": 6400,
        },
    )
    hass = FakeHass(state)
    entity = make_entity(hass)

    assert entity._attr_supported_color_modes == {ColorMode.COLOR_TEMP}


def test_effect_feature_comes_from_effect_list():
    state = FakeState(
        "on",
        {
            "supported_color_modes": [ColorMode.COLOR_TEMP],
            "effect_list": ["月光"],
        },
    )
    hass = FakeHass(state)
    entity = make_entity(hass)

    assert entity._attr_supported_features == LightEntityFeature.EFFECT


def test_normal_sync_does_not_log_error(monkeypatch):
    state = FakeState(
        "on",
        {
            "color_mode": ColorMode.COLOR_TEMP,
            "brightness": 100,
            "color_temp_kelvin": 4000,
            "effect": None,
            "supported_color_modes": [ColorMode.COLOR_TEMP],
        },
    )
    hass = FakeHass(state)
    entity = make_entity(hass)
    entity._attr_is_on = True

    def fail(*args, **kwargs):
        raise AssertionError("normal sync must not log at error level")

    monkeypatch.setattr(light_module._LOGGER, "error", fail)
    entity._apply_light_state(state)

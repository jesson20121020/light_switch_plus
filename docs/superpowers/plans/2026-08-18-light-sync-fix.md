# Light Switch+ 亮度/色温同步修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 Light Switch+ 在 Home Assistant 2026.8.1 上的色温控制、能力刷新、颜色模式同步和底层灯不可用时的状态补齐。

**Architecture:** 在现有 `light.py` 内引入 `_desired_state` 作为期望控制状态，统一从底层灯同步显示属性，并在底层灯不可用时保留 pending 控制、恢复可用后自动补发。用轻量 HA stub 做单元测试，不依赖完整 Home Assistant 环境。

**Tech Stack:** Python 3.13、pytest、Home Assistant light platform API。

---

## 文件结构

- `light.py`：虚拟灯实体，包含能力刷新、状态投影、控制转发、pending 重试。
- `tests/__init__.py`：测试包标记。
- `tests/conftest.py`：Home Assistant 模块 stub。
- `tests/test_light.py`：核心行为测试。

---

### Task 1: 添加测试脚手架和失败测试

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_light.py`

- [ ] **Step 1: 创建测试脚手架**

创建 `tests/__init__.py`，内容为空。

创建 `tests/conftest.py`：

```python
"""Home Assistant module stubs for Light Switch+ tests."""
import sys
import types

import pytest


def _stub_module(name, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module
    return module


@pytest.fixture(scope="session", autouse=True)
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
    light_switch_plus.__path__ = []
    sys.modules["custom_components.light_switch_plus"] = light_switch_plus

    const = types.ModuleType("custom_components.light_switch_plus.const")
    const.DOMAIN = "light_switch_plus"
    sys.modules["custom_components.light_switch_plus.const"] = const
```

- [ ] **Step 2: 创建核心测试**

创建 `tests/test_light.py`：

```python
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
```

- [ ] **Step 3: 运行测试确认失败**

Run: `python -m pytest tests -q`

Expected: FAIL。当前 `light.py` 没有 `_desired_state`、`_pending_control`、`_control_service_data` 等方法，且色温转发仍是旧字段，多个断言会失败。

- [ ] **Step 4: 提交测试脚手架**

```bash
git add tests/__init__.py tests/conftest.py tests/test_light.py
git commit -m "test: add light sync fix tests"
```

---

### Task 2: 重写 light.py 实现完整修复

**Files:**
- Modify: `light.py`
- Test: `tests/test_light.py`

- [ ] **Step 1: 用最终实现替换 light.py**

将 `light.py` 完整替换为以下内容：

```python
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
```

- [ ] **Step 2: 运行全部测试**

Run: `python -m pytest tests -q`

Expected: PASS，8 个测试全部通过。

- [ ] **Step 3: 提交实现**

```bash
git add light.py
git commit -m "fix: sync brightness and color temp with pending recovery"
```

---

### Task 3: 最终验证

**Files:**
- Modify: `light.py`（仅在验证发现问题时）
- Test: `tests/test_light.py`

- [ ] **Step 1: 运行测试和语法检查**

Run: `python -m pytest tests -q`

Expected: PASS。

Run: `python -m py_compile light.py`

Expected: 退出码 0。

- [ ] **Step 2: 确认没有遗留 error 日志和未使用导入**

Run: `rg -n "_LOGGER\.error|color_util|LightEntityFeature" light.py`

Expected: `color_util` 和 `LightEntityFeature` 仍有使用；`_LOGGER.error` 不出现。

- [ ] **Step 3: 检查工作区并提交收尾**

Run: `git status --short`

Expected: 工作区干净；如有未提交修改，按需提交。

---

## Self-Review

- Spec 覆盖：色温 Kelvin 转发、brightness_pct 归一化、能力动态刷新、`color_mode` 投影、unavailable pending 恢复、日志降级均有对应任务。
- 无占位符：所有代码步骤都包含完整实现或测试代码。
- 类型一致：`_desired_state`、`_pending_control`、`_control_service_data`、`_apply_control_to_desired`、`_brightness_from_pct` 在测试和实现中使用一致。

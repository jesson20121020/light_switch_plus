"""Light platform for Light Switch+."""
import logging
from typing import Any, Optional

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ATTR_HS_COLOR,
    ATTR_EFFECT,
    LightEntity,
    ColorMode,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON
)
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
import homeassistant.util.color as color_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

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
        config.get("sync_state", True)
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
        sync_state: bool
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
        self._attr_color_temp = None
        self._attr_color_temp_kelvin = None
        self._attr_rgb_color = None
        self._attr_hs_color = None
        self._attr_effect = None
        self._unsub_listener = None
        self._last_light_state = {}
        self._attr_supported_features = 0
        self._attr_supported_color_modes = set()
        self._attr_min_color_temp_kelvin = None
        self._attr_max_color_temp_kelvin = None
        self._attr_effect_list = []
        
        # 设置默认颜色模式
        self._attr_color_mode = ColorMode.ONOFF
        
        # 更新支持的功能
        self._update_supported_features()
        
    def _update_supported_features(self):
        """根据灯光实体更新支持的功能"""
        if not self._light_entity:
            # 如果没有灯光实体，只支持开关模式
            self._attr_supported_color_modes = {ColorMode.ONOFF}
            return
            
        light_state = self.hass.states.get(self._light_entity)
        if not light_state:
            self._attr_supported_color_modes = {ColorMode.ONOFF}
            return
            
        attrs = light_state.attributes
        _LOGGER.error("_update_supported_features" + str(attrs))
        self._attr_supported_features = attrs.get("supported_features", 0)
        self._attr_effect_list = attrs.get("effect_list", [])
        
        # 获取支持的颜色模式
        supported_color_modes = set()
        if "supported_color_modes" in attrs:
            # 使用灯光实体报告的支持模式
            supported_color_modes = set(attrs["supported_color_modes"])
            if attrs.get("min_color_temp_kelvin") or attrs.get("max_color_temp_kelvin"):
                # 设置开尔文温度范围
                self._attr_min_color_temp_kelvin = attrs.get("min_color_temp_kelvin")
                self._attr_max_color_temp_kelvin = attrs.get("max_color_temp_kelvin")
        else:
            # 回退到基于旧属性的支持模式
            if attrs.get("min_color_temp_kelvin") or attrs.get("max_color_temp_kelvin"):
                supported_color_modes.add(ColorMode.COLOR_TEMP)
                # 设置开尔文温度范围
                self._attr_min_color_temp_kelvin = attrs.get("min_color_temp_kelvin")
                self._attr_max_color_temp_kelvin = attrs.get("max_color_temp_kelvin")
            if attrs.get("hs_color") or attrs.get("rgb_color"):
                supported_color_modes.add(ColorMode.HS)
            if attrs.get("brightness"):
                supported_color_modes.add(ColorMode.BRIGHTNESS)
        
        # 确保至少有一种模式
        if not supported_color_modes:
            supported_color_modes = {ColorMode.ONOFF}
        
        self._attr_supported_color_modes = supported_color_modes
        
        # 确保颜色模式是支持的模式之一
        if self._attr_color_mode not in self._attr_supported_color_modes:
            # 如果当前颜色模式不支持，选择支持模式中的第一个
            self._attr_color_mode = next(iter(self._attr_supported_color_modes))

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """返回支持的颜色模式"""
        return self._attr_supported_color_modes

    @property
    def extra_state_attributes(self) -> dict:
        """返回实体特定的状态属性"""
        return {
            "switch_entity": self._switch_entity,
            "light_entity": self._light_entity,
            "sync_state": self._sync_state
        }

    @property
    def device_info(self) -> DeviceInfo:
        """返回此实体的设备信息"""
        return DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=self._attr_name,
            manufacturer="Light Switch+"
        )

    def _update_light_attributes(self, state):
        _LOGGER.error("update_light_attributes" + str(state) + "  " + str(self._attr_is_on))
        """Update attributes from light entity."""
        if not state:
            return
            
        # Store last state for sync
        self._last_light_state = {
            k: state.attributes.get(k) for k in [
                ATTR_BRIGHTNESS, ATTR_COLOR_TEMP_KELVIN, 
                ATTR_RGB_COLOR, ATTR_HS_COLOR, ATTR_EFFECT
            ] if k in state.attributes
        }
        
        # Update attributes when switch is on
        if self._attr_is_on:
            if ATTR_BRIGHTNESS in state.attributes:
                self._attr_brightness = state.attributes[ATTR_BRIGHTNESS]
            if ATTR_COLOR_TEMP_KELVIN in state.attributes:
                self._attr_color_temp_kelvin = state.attributes[ATTR_COLOR_TEMP_KELVIN]
            if ATTR_COLOR_TEMP in state.attributes:
                self._attr_color_temp = state.attributes[ATTR_COLOR_TEMP]
            if ATTR_RGB_COLOR in state.attributes:
                self._attr_rgb_color = state.attributes[ATTR_RGB_COLOR]
            if ATTR_HS_COLOR in state.attributes:
                self._attr_hs_color = state.attributes[ATTR_HS_COLOR]
            if ATTR_EFFECT in state.attributes:
                self._attr_effect = state.attributes[ATTR_EFFECT]
            
            # 根据属性确定颜色模式，但只选择支持的模式
            if self._attr_color_temp_kelvin is not None and ColorMode.COLOR_TEMP in self.supported_color_modes:
                self._attr_color_mode = ColorMode.COLOR_TEMP
            elif (self._attr_hs_color is not None or self._attr_rgb_color is not None) and ColorMode.HS in self.supported_color_modes:
                self._attr_color_mode = ColorMode.HS
            elif self._attr_brightness is not None and ColorMode.BRIGHTNESS in self.supported_color_modes:
                self._attr_color_mode = ColorMode.BRIGHTNESS
            elif ColorMode.ONOFF in self.supported_color_modes:
                self._attr_color_mode = ColorMode.ONOFF
            else:
                # 如果没有匹配的模式，使用支持模式中的第一个
                if self.supported_color_modes:
                    self._attr_color_mode = next(iter(self.supported_color_modes))
        else:
            # 当灯光关闭时，保持之前的颜色模式
            # 或者使用支持模式中的第一个
            if not hasattr(self, '_attr_color_mode') or self._attr_color_mode not in self.supported_color_modes:
                if self.supported_color_modes:
                    self._attr_color_mode = next(iter(self.supported_color_modes))

    async def async_update(self) -> None:
        """Update the state."""
        # Update switch state
        switch_state = self.hass.states.get(self._switch_entity)
        if switch_state:
            self._attr_is_on = switch_state.state == STATE_ON
            self._attr_available = switch_state.state not in ["unavailable", "unknown"]
        
        # Update light attributes if available
        if self._light_entity:
            self._update_light_attributes(self.hass.states.get(self._light_entity))

    async def async_added_to_hass(self) -> None:
        """当实体添加到Home Assistant时运行"""
        await super().async_added_to_hass()
        
        # 恢复之前的状态
        last_state = await self.async_get_last_state()
        if last_state:
            self._attr_is_on = last_state.state == STATE_ON
            self._attr_brightness = last_state.attributes.get(ATTR_BRIGHTNESS)
            self._attr_color_temp_kelvin = last_state.attributes.get(ATTR_COLOR_TEMP_KELVIN)
            self._attr_color_temp = last_state.attributes.get(ATTR_COLOR_TEMP)
            self._attr_rgb_color = last_state.attributes.get(ATTR_RGB_COLOR)
            self._attr_hs_color = last_state.attributes.get(ATTR_HS_COLOR)
            self._attr_effect = last_state.attributes.get(ATTR_EFFECT)
            
            # 恢复颜色模式
            if "color_mode" in last_state.attributes:
                restored_color_mode = last_state.attributes["color_mode"]
                # 检查恢复的颜色模式是否在支持的模式中
                if restored_color_mode in self.supported_color_modes:
                    self._attr_color_mode = restored_color_mode
                else:
                    # 如果恢复的模式不支持，使用支持模式中的第一个
                    if self.supported_color_modes:
                        self._attr_color_mode = next(iter(self.supported_color_modes))
            else:
                # 回退到基于属性的颜色模式
                if self._attr_color_temp_kelvin is not None and ColorMode.COLOR_TEMP in self.supported_color_modes:
                    self._attr_color_mode = ColorMode.COLOR_TEMP
                elif (self._attr_hs_color is not None or self._attr_rgb_color is not None) and ColorMode.HS in self.supported_color_modes:
                    self._attr_color_mode = ColorMode.HS
                elif self._attr_brightness is not None and ColorMode.BRIGHTNESS in self.supported_color_modes:
                    self._attr_color_mode = ColorMode.BRIGHTNESS
                elif ColorMode.ONOFF in self.supported_color_modes:
                    self._attr_color_mode = ColorMode.ONOFF
                else:
                    if self.supported_color_modes:
                        self._attr_color_mode = next(iter(self.supported_color_modes))
        
        # 开始监听状态变化
        entities_to_track = [self._switch_entity]
        if self._light_entity:
            entities_to_track.append(self._light_entity)
        self._unsub_listener = async_track_state_change_event(
            self.hass, entities_to_track, self._async_state_changed
        )
        
        # 初始更新
        self.async_schedule_update_ha_state(True)

    async def async_will_remove_from_hass(self) -> None:
        """当实体从Home Assistant中移除时运行"""
        if self._unsub_listener:
            self._unsub_listener()

    @callback
    def _async_state_changed(self, event):
        """处理状态变化事件"""
        data = event.data
        _LOGGER.info("async_state_changed" + str(event))
        entity_id = data.get("entity_id")
        old_state = data.get("old_state")
        new_state = data.get("new_state")
        
        if new_state is None:
            return
            
        if entity_id == self._switch_entity:
            self._handle_switch_change(new_state)
        elif entity_id == self._light_entity:
            self._handle_light_change(new_state)
        
        self.async_write_ha_state()

    def _handle_switch_change(self, new_state):
        """处理开关状态变化"""
         # 保存旧状态用于比较
        old_state = self._attr_is_on
        self._attr_is_on = new_state.state == STATE_ON
        
        # 如果状态发生变化，强制触发完整更新
        if old_state != self._attr_is_on:
            self.async_write_ha_state()
        
        # 如果开关打开且启用了同步，同步灯光状态
        if self._attr_is_on and self._sync_state and self._light_entity:
            self.hass.async_create_task(self._sync_light_state())
    
    def _handle_light_change(self, new_state):
        """处理灯光状态变化"""
        if not self._attr_is_on:
            return
        _LOGGER.error("_handle_light_change" + str(new_state))
        # 更新属性
        self._attr_brightness = new_state.attributes.get(ATTR_BRIGHTNESS)
        self._attr_color_temp_kelvin = new_state.attributes.get(ATTR_COLOR_TEMP_KELVIN)
        self._attr_color_temp = new_state.attributes.get(ATTR_COLOR_TEMP)
        self._attr_rgb_color = new_state.attributes.get(ATTR_RGB_COLOR)
        self._attr_hs_color = new_state.attributes.get(ATTR_HS_COLOR)
        self._attr_effect = new_state.attributes.get(ATTR_EFFECT)
        
        # 根据属性更新颜色模式，但只选择支持的模式
        if self._attr_color_temp_kelvin is not None and ColorMode.COLOR_TEMP in self.supported_color_modes:
            self._attr_color_mode = ColorMode.COLOR_TEMP
        elif (self._attr_hs_color is not None or self._attr_rgb_color is not None) and ColorMode.HS in self.supported_color_modes:
            self._attr_color_mode = ColorMode.HS
        elif self._attr_brightness is not None and ColorMode.BRIGHTNESS in self.supported_color_modes:
            self._attr_color_mode = ColorMode.BRIGHTNESS
        elif ColorMode.ONOFF in self.supported_color_modes:
            self._attr_color_mode = ColorMode.ONOFF
        else:
            # 如果没有匹配的模式，使用支持模式中的第一个
            if self.supported_color_modes:
                self._attr_color_mode = next(iter(self.supported_color_modes))
        
        # 保存最后的状态用于同步
        self._last_light_state = {
            k: new_state.attributes.get(k) for k in [
                ATTR_BRIGHTNESS, ATTR_COLOR_TEMP_KELVIN, 
                ATTR_RGB_COLOR, ATTR_HS_COLOR, ATTR_EFFECT
            ] if k in new_state.attributes
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """打开灯光"""
        # 保存旧状态用于比较
        old_state = self._attr_is_on
        # 打开开关
        await self.hass.services.async_call(
            "switch" if self._switch_entity.startswith("switch") else "input_boolean",
            SERVICE_TURN_ON,
            {"entity_id": self._switch_entity},
            blocking=True
        )
        
        # 更新状态
        self._attr_is_on = True
        
        # 如果状态发生变化，强制触发完整更新
        if not old_state:
            self.async_write_ha_state()
        
        # 如果有灯光实体和额外参数，控制灯光
        if self._light_entity and kwargs:
            await self._control_light(**kwargs)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """关闭灯光"""
         # 保存旧状态用于比较
        old_state = self._attr_is_on
        await self.hass.services.async_call(
            "switch" if self._switch_entity.startswith("switch") else "input_boolean",
            SERVICE_TURN_OFF,
            {"entity_id": self._switch_entity},
            blocking=True
        )
        # 更新状态
        self._attr_is_on = False
        
        # 如果状态发生变化，强制触发完整更新
        if old_state:
            self.async_write_ha_state()

    async def _control_light(self, **kwargs):
        """控制辅助灯光"""
        service_data = {"entity_id": self._light_entity}
        
        # 处理颜色参数
        if "hs_color" in kwargs:
            service_data["hs_color"] = kwargs["hs_color"]
        elif "rgb_color" in kwargs:
            service_data["rgb_color"] = kwargs["rgb_color"]
        
        # 处理其他参数
        for attr in ["brightness", "color_temp", "effect"]:
            if attr in kwargs:
                service_data[attr] = kwargs[attr]
        
        # 调用灯光服务
        await self.hass.services.async_call(
            "light",
            SERVICE_TURN_ON,
            service_data,
            blocking=True
        )

    async def _sync_light_state(self):
        """当打开时同步灯光状态"""
        if not self._last_light_state or not self._light_entity:
            return
            
        service_data = {"entity_id": self._light_entity}
        service_data.update(self._last_light_state)
        
        await self.hass.services.async_call(
            "light",
            SERVICE_TURN_ON,
            service_data,
            blocking=True
        )
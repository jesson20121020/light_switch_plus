"""Light platform for Light Switch+."""
import logging
from typing import Any, Optional

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_RGB_COLOR,
    ATTR_HS_COLOR,
    ATTR_EFFECT,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR_TEMP,
    SUPPORT_COLOR,
    SUPPORT_EFFECT,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change
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
        self._attr_rgb_color = None
        self._attr_hs_color = None
        self._attr_effect = None
        self._attr_supported_features = 0
        self._unsub_listener = None
        self._last_light_state = {}
        
        # 更新支持的功能
        self._update_supported_features()
        
    def _update_supported_features(self):
        """根据灯光实体更新支持的功能"""
        if not self._light_entity:
            self._attr_supported_features = 0
            return
            
        light_state = self.hass.states.get(self._light_entity)
        if not light_state:
            return
            
        supported = 0
        attrs = light_state.attributes
        
        if attrs.get(ATTR_BRIGHTNESS) is not None:
            supported |= SUPPORT_BRIGHTNESS
        if attrs.get(ATTR_COLOR_TEMP) is not None:
            supported |= SUPPORT_COLOR_TEMP
        if attrs.get(ATTR_RGB_COLOR) is not None or attrs.get(ATTR_HS_COLOR) is not None:
            supported |= SUPPORT_COLOR
        if attrs.get("effect_list") is not None:
            supported |= SUPPORT_EFFECT
            
        self._attr_supported_features = supported

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

    async def async_added_to_hass(self) -> None:
        """当实体添加到Home Assistant时运行"""
        await super().async_added_to_hass()
        
        # 恢复之前的状态
        last_state = await self.async_get_last_state()
        if last_state:
            self._attr_is_on = last_state.state == STATE_ON
            self._attr_brightness = last_state.attributes.get(ATTR_BRIGHTNESS)
            self._attr_color_temp = last_state.attributes.get(ATTR_COLOR_TEMP)
            self._attr_rgb_color = last_state.attributes.get(ATTR_RGB_COLOR)
            self._attr_hs_color = last_state.attributes.get(ATTR_HS_COLOR)
            self._attr_effect = last_state.attributes.get(ATTR_EFFECT)
        
        # 开始监听状态变化
        self._unsub_listener = async_track_state_change(
            self.hass, 
            [self._switch_entity] + ([self._light_entity] if self._light_entity else []), 
            self._async_state_changed
        )
        
        # 初始更新
        self.async_schedule_update_ha_state(True)

    async def async_will_remove_from_hass(self) -> None:
        """当实体从Home Assistant中移除时运行"""
        if self._unsub_listener:
            self._unsub_listener()

    @callback
    def _async_state_changed(self, entity_id, old_state, new_state):
        """处理状态变化"""
        if new_state is None:
            return
            
        if entity_id == self._switch_entity:
            self._handle_switch_change(new_state)
        elif entity_id == self._light_entity:
            self._handle_light_change(new_state)
        
        self.async_write_ha_state()
    
    def _handle_switch_change(self, new_state):
        """处理开关状态变化"""
        self._attr_is_on = new_state.state == STATE_ON
        
        # 如果开关打开且启用了同步，同步灯光状态
        if self._attr_is_on and self._sync_state and self._light_entity:
            self.hass.async_create_task(self._sync_light_state())
    
    def _handle_light_change(self, new_state):
        """处理灯光状态变化"""
        if not self._attr_is_on:
            return
            
        # 更新属性
        self._attr_brightness = new_state.attributes.get(ATTR_BRIGHTNESS)
        self._attr_color_temp = new_state.attributes.get(ATTR_COLOR_TEMP)
        self._attr_rgb_color = new_state.attributes.get(ATTR_RGB_COLOR)
        self._attr_hs_color = new_state.attributes.get(ATTR_HS_COLOR)
        self._attr_effect = new_state.attributes.get(ATTR_EFFECT)
        
        # 保存最后的状态用于同步
        self._last_light_state = {
            k: new_state.attributes[k] for k in [
                ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, 
                ATTR_RGB_COLOR, ATTR_HS_COLOR, ATTR_EFFECT
            ] if k in new_state.attributes
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """打开灯光"""
        # 打开开关
        await self.hass.services.async_call(
            "switch" if self._switch_entity.startswith("switch") else "input_boolean",
            SERVICE_TURN_ON,
            {"entity_id": self._switch_entity},
            blocking=True
        )
        
        # 如果有灯光实体和额外参数，控制灯光
        if self._light_entity and kwargs:
            await self._control_light(**kwargs)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """关闭灯光"""
        await self.hass.services.async_call(
            "switch" if self._switch_entity.startswith("switch") else "input_boolean",
            SERVICE_TURN_OFF,
            {"entity_id": self._switch_entity},
            blocking=True
        )

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
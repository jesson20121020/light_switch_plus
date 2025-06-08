"""Config flow for Light Switch+ integration."""
import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.const import CONF_NAME

_LOGGER = logging.getLogger(__name__)

DOMAIN = "light_switch_plus"
DEFAULT_NAME = "Light Switch+"

class ConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Light Switch+."""
    
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        user_input = user_input or {}
        
        if user_input:
            # 验证开关实体
            switch_entity = user_input.get("switch_entity")
            if not switch_entity:
                errors["base"] = "switch_required"
            elif not self.hass.states.get(switch_entity):
                errors["base"] = "switch_not_found"
            
            # 验证灯光实体（如果提供）
            light_entity = user_input.get("light_entity")
            if light_entity and not self.hass.states.get(light_entity):
                errors["base"] = "light_not_found"
            
            if not errors:
                # 创建唯一ID
                unique_id = f"light_switch_plus_{switch_entity}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                
                return self.async_create_entry(
                    title=user_input.get("name", DEFAULT_NAME),
                    data=user_input
                )

        # 创建配置表单
        schema = vol.Schema({
            vol.Required("name", default=user_input.get("name", DEFAULT_NAME)): str,
            vol.Required("switch_entity", default=user_input.get("switch_entity", "")): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["switch", "input_boolean"], multiple=False)
            ),
            vol.Optional("light_entity", default=user_input.get("light_entity", "")): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["light"], multiple=False)
            ),
            vol.Required("sync_state", default=user_input.get("sync_state", True)): bool
        })
        
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors
        )
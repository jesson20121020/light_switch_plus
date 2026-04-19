## ADDED Requirements

### Requirement: HomeAssistant 2026.4.3 Compatibility
The Light Switch+ integration SHALL be compatible with HomeAssistant 2026.4.3 by removing dependencies on deprecated ATTR_COLOR_TEMP constant.

#### Scenario: Successful loading in HomeAssistant 2026.4.3
- **WHEN** the integration is loaded in HomeAssistant 2026.4.3
- **THEN** no ImportError should occur related to ATTR_COLOR_TEMP

#### Scenario: Color temperature handling
- **WHEN** the integration processes light entities with color temperature attributes
- **THEN** it SHALL only use ATTR_COLOR_TEMP_KELVIN for color temperature operations

## REMOVED Requirements

### Requirement: ATTR_COLOR_TEMP Support
**Reason**: ATTR_COLOR_TEMP has been removed from HomeAssistant 2026.4.3
**Migration**: Use ATTR_COLOR_TEMP_KELVIN instead for all color temperature operations
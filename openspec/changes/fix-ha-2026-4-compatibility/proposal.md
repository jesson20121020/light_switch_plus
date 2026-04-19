## Why

HomeAssistant 2026.4.3 版本中移除了 `ATTR_COLOR_TEMP` 常量，导致 Light Switch+ 集成无法正常加载。这个变更解决了集成与最新 HomeAssistant 版本的兼容性问题，确保用户能够正常使用该集成。

## What Changes

- 移除对 `ATTR_COLOR_TEMP` 的导入引用
- 移除所有对 `self._attr_color_temp` 属性的使用
- 只保留 `ATTR_COLOR_TEMP_KELVIN` 相关的色温处理逻辑
- 更新代码以适配 HomeAssistant 2026.4.3 的 API 变更

## Capabilities

### New Capabilities

- `ha-2026-4-compatibility`: 确保集成与 HomeAssistant 2026.4.3 版本的兼容性

### Modified Capabilities

## Impact

- 影响 `light.py` 文件中的导入语句和色温处理逻辑
- 移除对已废弃 API 的依赖
- 不会影响集成的核心功能，只是更新了底层实现以适配新版本
## Context

HomeAssistant 2026.4.3 版本中，开发团队移除了 `ATTR_COLOR_TEMP` 常量，这是为了统一色温处理方式，只保留开尔文色温单位 (`ATTR_COLOR_TEMP_KELVIN`)。这一变更导致现有的 Light Switch+ 集成在启动时出现导入错误，无法正常加载。

当前集成同时使用了 `ATTR_COLOR_TEMP` (mired 色温单位) 和 `ATTR_COLOR_TEMP_KELVIN` (开尔文色温单位) 来处理色温属性，需要更新为只使用开尔文色温单位。

## Goals / Non-Goals

**Goals:**
- 解决 HomeAssistant 2026.4.3 版本的兼容性问题
- 移除对已废弃 API 的依赖
- 确保集成能够正常加载和运行
- 保持集成的核心功能不变

**Non-Goals:**
- 添加新的功能特性
- 改变集成的用户界面或配置流程
- 修改除色温处理外的其他逻辑

## Decisions

1. **移除 ATTR_COLOR_TEMP 依赖** - 由于 HomeAssistant 已经移除了这个常量，必须从代码中完全移除对其的引用，这是解决加载失败的直接方案。

2. **保留 ATTR_COLOR_TEMP_KELVIN** - 继续使用开尔文色温单位，这是 HomeAssistant 推荐的标准色温表示方式。

3. **清理相关属性** - 移除 `self._attr_color_temp` 属性及相关处理逻辑，因为该属性依赖于已移除的 `ATTR_COLOR_TEMP`。

4. **保持向后兼容** - 虽然移除了对 `ATTR_COLOR_TEMP` 的处理，但确保现有配置和状态恢复功能不受影响。

## Risks / Trade-offs

- **兼容性风险** → 通过只使用 HomeAssistant 推荐的 API 来降低风险
- **功能缺失风险** → 通过保留开尔文色温单位处理确保核心色温功能正常
- **状态恢复问题** → 需要验证从旧版本升级后的状态恢复是否正常工作
## 1. 代码修复任务

- [x] 1.1 移除 light.py 中对 ATTR_COLOR_TEMP 的导入引用
- [x] 1.2 移除 light.py 中所有对 self._attr_color_temp 属性的使用
- [x] 1.3 清理与 ATTR_COLOR_TEMP 相关的处理逻辑

## 2. 测试验证任务

- [x] 2.1 验证集成在 HomeAssistant 2026.4.3 中能够正常加载
- [x] 2.2 验证色温功能在使用 ATTR_COLOR_TEMP_KELVIN 时正常工作
- [x] 2.3 验证状态恢复功能不受影响
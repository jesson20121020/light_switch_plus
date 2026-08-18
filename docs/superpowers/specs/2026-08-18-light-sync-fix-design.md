# Light Switch+ 亮度/色温同步修复设计

日期：2026-08-18

## 背景

Light Switch+ 把“开关实体”和“灯光实体”组合成一个虚拟灯：开关实体负责供电，灯光实体负责亮度、色温、效果等控制。当前实现在 Home Assistant 2026.8.1 上存在以下问题：

- 修改色温没有效果：`_control_light` 只转发旧字段 `color_temp`，HA 2026.8 使用 `color_temp_kelvin`，色温参数被丢弃。
- 底层灯实体 `unavailable` 时，控制调用静默失败，虚拟灯状态不会更新；底层灯恢复可用后也没有自动补齐。
- 支持能力只在初始化时计算一次，底层灯尚未可用时可能错误退回 `ONOFF`，之后不再刷新。
- 颜色模式通过属性存在性猜测，没有使用底层灯真实的 `color_mode`，多模式灯可能显示错误控件。
- 正常状态同步使用 `_LOGGER.error`，产生大量错误日志。
- `_last_light_state` 原样保存并回放底层灯 state 属性，可能包含冲突或过期字段。

## 目标

- 色温调整在 HA 2026.8.1 上真实生效，转发字段统一为 `color_temp_kelvin`。
- 亮度调整保持可用，并在收到 `brightness_pct` 时归一化后转发。
- 底层灯 `unavailable` 时保留最后一次正常状态，不把 UI 打回默认值；恢复可用后自动补齐 pending 控制。
- 支持能力随底层灯状态动态刷新，不再错误退回 `ONOFF`。
- 颜色模式以底层灯 `color_mode` 为准。
- 正常同步日志降级为 `debug`，真正的故障使用 `warning`。

## 非目标

- 不修改配置流程、实体命名或用户界面。
- 不修复底层灯集成自身的不可用问题。
- 不引入对完整 Home Assistant 测试环境的依赖。

## 设计

### 1. 期望状态模型

新增 `_desired_state: dict`，保存虚拟灯期望的底层控制参数，键名与 `light.turn_on` 服务参数一致：

- `brightness`：0-255
- `color_temp_kelvin`
- `effect`
- `rgb_color` / `hs_color`

更新规则：

- 底层灯处于可用状态且虚拟灯开启时，从底层灯 state 属性刷新 `_desired_state`。
- 用户通过虚拟灯发出控制参数时，用控制参数覆盖 `_desired_state` 中对应字段。
- 底层灯 `unavailable`/`unknown` 时不更新 `_desired_state`，也不更新亮度、色温等显示属性。
- 开关关闭时保留 `_desired_state`，下次开启时继续使用。

### 2. 支持能力动态刷新

把 `_update_supported_features` 改为 `_refresh_capabilities()`，在以下时机调用：

- 初始化
- 底层灯状态变化事件
- 底层灯从不可用恢复可用

刷新规则：

- 优先使用底层灯 `supported_color_modes`。
- 有 `effect_list` 时设置 `LightEntityFeature.EFFECT`，而不是复制底层灯 `supported_features`。
- 底层灯不可用但状态属性仍包含能力信息时，继续使用这些信息。
- 只有完全没有任何能力信息时才使用 `ONOFF`，并在后续状态变化时重新刷新。

### 3. 控制参数转发

`_control_light` 按以下规则构造 `light.turn_on` 服务数据：

- 转发 `brightness`、`color_temp_kelvin`、`effect`、`rgb_color`、`hs_color`。
- `brightness_pct` 先转换为 `brightness`。
- 旧版 `color_temp`（mired）先转换为 `color_temp_kelvin`。
- 只转发底层灯支持的模式对应的字段，避免传入冲突参数。

转换使用 `homeassistant.util.color` 已有的工具函数，不手写换算公式。

### 4. 可用性兜底

调用底层灯前检查 `hass.states.get(self._light_entity)`：

- 底层灯不可用时，不直接调用服务；把控制参数合并进 `_desired_state`，设置 `_pending_control = True`，记录一次 `warning`。
- 底层灯恢复可用且虚拟灯开启时，自动补发 `_desired_state`；补发成功后清除 pending。
- 服务调用异常时保留 pending，等待下一次状态变化或开关切换时重试。
- 同一个不可用阶段只记录一次 warning，避免刷屏。

### 5. 状态投影

`_attr_color_mode` 优先使用底层灯 state 属性中的 `color_mode`；属性缺失时才回退到基于现有属性的判断。

亮度、色温、效果等显示属性只在底层灯可用且虚拟灯开启时从底层灯复制。底层灯不可用时保留上次正常值。

### 6. 日志

- 状态同步、能力刷新使用 `debug`。
- 底层灯不可用、服务调用失败使用 `warning`，并带防重复机制。

## 数据流

### 用户调整亮度/色温

1. HA 调用虚拟灯 `async_turn_on`，传入 `brightness`/`color_temp_kelvin` 等参数。
2. 虚拟灯先确保开关打开。
3. 参数写入 `_desired_state`。
4. 底层灯可用时，调用底层 `light.turn_on`。
5. 底层灯不可用时，设置 pending，等待恢复可用事件。

### 底层灯状态变化

1. 收到底层灯 state changed 事件。
2. 刷新能力信息。
3. 底层灯可用时，同步亮度、色温、效果和 `color_mode`。
4. 存在 pending 且虚拟灯开启时，自动补发控制。

### 开关打开

1. 虚拟灯状态变为开启。
2. 有 `_desired_state` 时调用底层 `light.turn_on` 同步。
3. 底层灯不可用时设置 pending，等待恢复。

## 错误处理

- `hass.services.async_call` 异常统一捕获，记录 warning，不清除 pending。
- 不可用状态下不抛出异常给 HA 调用方，避免服务调用界面报错。
- 状态变化事件处理中避免重复发送同一份 pending 状态。

## 测试

使用 `pytest` 和轻量 stub，不依赖完整 Home Assistant：

- 色温调整时 `_control_light` 转发 `color_temp_kelvin`。
- `brightness_pct` 正确转换为 `brightness`。
- 底层灯不可用时参数进入 `_desired_state` 并设置 pending。
- 底层灯恢复可用后自动补发一次，并清除 pending。
- 底层灯不可用时能力信息不退回 `ONOFF`。
- 正常同步不产生 error 级别日志。

## 涉及文件

- `light.py`：主要实现修改。
- `docs/superpowers/specs/2026-08-18-light-sync-fix-design.md`：本文档。

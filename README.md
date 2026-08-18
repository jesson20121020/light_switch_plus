# Light Switch Plus

用于结合一个开关实体和一个灯光实体作为一个新的灯光实体设备。

- 开关实体只负责开关电源，并负责更新虚拟灯光实体的开关状态。
- 灯光实体负责控制色温、亮度、效果、RGB 颜色等。

## 功能

- 虚拟灯实体
- 色温、亮度、效果同步
- 底层灯不可用时自动保留期望状态，恢复可用后补齐

## HACS 安装

1. 打开 HACS，点击右上角菜单，选择“自定义仓库”。
2. 仓库地址填写 `https://github.com/jesson20121020/light_switch_plus`。
3. 分类选择 `Integration`。
4. 添加后在 HACS 中找到 Light Switch+ 并下载安装。
5. 重启 Home Assistant。
6. 在“设置 -> 设备与服务 -> 添加集成”中选择 Light Switch+，配置开关实体和灯光实体。

后续更新直接在 HACS 中点击更新即可。

## 手动安装

将 `custom_components/light_switch_plus/` 目录复制到 Home Assistant 的 `custom_components/` 目录下，然后重启 Home Assistant。

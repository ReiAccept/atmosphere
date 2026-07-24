# 大气层整合包生成工具 - Nintendo Switch Atmosphere CFW package builder

- 大气层三件套
  - [x] `Atmosphere + Fusee` [From Here](https://github.com/Atmosphere-NX/Atmosphere/releases/latest)
  - [x] `Hekate + Nyx 汉化版` [From Here](https://github.com/easyworld/hekate/releases/latest)
  - [x] `Sigpatches` [From Here](https://gbatemp.net/threads/sigpatches-for-atmosphere-hekate-fss0-fusee-package3.571543/page-275#post-10692213)
- Payload插件
  - [x] 主机系统的密钥提取工具 `Lockpick_RCM` [From Here](https://github.com/Kofysh/Lockpick_RCM)
  - [x] Hekate下的文件管理工具 `TegraExplorer` [From Here](https://github.com/zdm65477730/TegraExplorer/releases/latest)
  - [x] Hekate下删除主题和关闭插件自动启动 `CommonProblemResolver` [From Here](https://github.com/zdm65477730/CommonProblemResolver/releases/latest)
- Nro插件
  - [x] 联网检测是否屏蔽任天堂服务器 `Switch_90DNS_tester` [From Here](https://github.com/meganukebmp/Switch_90DNS_tester/releases/latest)
  - [x] 游戏安装, 存档管理和文件传输工具 `DBI` [From Here](https://github.com/gzk47/DBIPatcher/releases/latest)
  - [x] 游戏安装和文件传输工具 `Awoo Installer` [From Here](https://github.com/Huntereb/Awoo-Installer/releases/latest)
  - [x] 深海工具箱 `Hekate-toolbox` [From Here](https://github.com/WerWolv/Hekate-Toolbox/releases/latest)
  - [x] 游戏游玩时间记录工具 `NX-Activity-Log` [From Here](https://github.com/zdm65477730/NX-Activity-Log/releases/latest)
  - [x] 主题安装工具 `NXThemesInstaller` [From Here](https://github.com/exelix11/SwitchThemeInjector/releases/latest)
  - [x] 游戏存档管理工具 `JKSV` [From Here](https://github.com/J-D-K/JKSV/releases/latest)
  - [x] 多工具合一任天堂Switch更新器 `aio-switch-updater` [From Here](https://github.com/HamletDuFromage/aio-switch-updater/releases/latest)
  - [x] Mod下载器 `SimpleModDownloader` [From Here](https://github.com/PoloNX/SimpleModDownloader/releases/latest)
  - [x] 串流工具 `Moonlight` [From Here](https://github.com/XITRIX/Moonlight-Switch/releases/latest)
  - [x] 文件管理 `NX-Shell` [From Here](https://github.com/zdm65477730/NX-Shell/releases/latest)
  - [x] Homebrew 启动器 `Sphaira` [From Here](https://github.com/ITotalJustice/sphaira/releases/latest)
  - [x] 黑商店 `hb-appstore`  [From Here](https://github.com/fortheusers/hb-appstore/releases/latest)

- 补丁
  - [x] 主题破解 `theme-patches` [From Here](https://github.com/exelix11/theme-patches)
- Ultrahand
  - [x] 加载器 `nx-ovlloader` [From Here](https://github.com/zdm65477730/nx-ovlloader/releases/latest)
  - [x] 菜单 `Ultrahand-Overlay` [From Here](https://github.com/zdm65477730/Ultrahand-Overlay/releases/latest)
- Ovl插件
  - [x] 金手指工具 `EdiZon` [From Here](https://github.com/zdm65477730/EdiZon-Overlay/releases/latest)
  - [x] 系统模块 `ovl-sysmodules` [From Here](https://github.com/zdm65477730/ovl-sysmodules/releases/latest)
  - [x] 系统监视 `StatusMonitor` [From Here](https://github.com/zdm65477730/Status-Monitor-Overlay/releases/latest)
  - [x] 掌机底座模式切换 `ReverseNX-RT` [From Here](https://github.com/zdm65477730/ReverseNX-RT/releases/latest)
  - [x] 局域网联机 `ldn_mitm` [From Here](https://github.com/zdm65477730/ldn_mitm/releases/latest)
  - [x] 虚拟Amiibo `emuiibo` [From Here](https://github.com/zdm65477730/emuiibo/releases/latest)
  - [x] 时间同步 `QuickNTP` [From Here](https://github.com/zdm65477730/QuickNTP/releases/latest)
  - [x] 色彩调整 `Fizeau` [From Here](https://github.com/zdm65477730/Fizeau/releases/latest)
  - [x] 系统补丁 `sys-patch` [From Here](https://github.com/zdm65477730/sys-patch/releases/latest)
  - [x] 超频插件 `sys-clk` [From Here](https://github.com/zdm65477730/sys-clk/releases/latest)
  - [x] 调频插件 `OC Toolkit` [From Here](https://github.com/halop/OC_Toolkit_SC_EOS/releases/latest)

- 其他
  - [x] 蓝牙手柄插件 `MissionControl` [From Here](https://github.com/ndeadly/MissionControl/releases/latest)



### Usage

```bash
# 安装依赖
pip install -e .

### 运行

```bash
# 完整构建
python main.py

# 只显示计划, 不下载
python main.py --dry-run

# 只运行指定分组
python main.py --only core,configs,finalize

# 查看帮助
python main.py --help

# 控制并行下载数
python main.py --max-parallel 3
```

### 系统依赖

- `git` — 用于克隆 theme-patches 仓库
- `7z`（可选）— 如需解压 .7z 格式归档


### 分组说明

| 分组 | 说明 |
|------|------|
| `core` | 大气层三件套 (Atmosphere, Fusee, Hekate, Sigpatches) |
| `payload` | 引导时 payload 插件 |
| `homebrew` | NRO 自制应用 |
| `special` | 特殊下载 (Awoo, Sphaira, OC Toolkit 等) |
| `system` | 系统模块和 Overlay 插件 |
| `configs` | 生成配置文件 |
| `finalize` | 收尾处理 (重命名 payload, 清理) |

注意: 全量运行会清空并重建 `sdcard` 目录；使用 `--only` 时会保留已有内容, 仅补齐目录并执行指定分组。


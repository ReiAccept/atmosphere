"""应用全局配置常量。"""

from __future__ import annotations

import os
from pathlib import Path

# ---- 路径 ----
SCRIPT_DIR: Path = Path(__file__).resolve().parent.parent
TEMPLATE_DIR: Path = SCRIPT_DIR / "templates"
SDCARD_DIR: Path = SCRIPT_DIR / "sdcard"
DESCRIPTION_FILE: Path = SCRIPT_DIR / "description.txt"

# ---- 下载设置 ----
DOWNLOAD_TMP_SUFFIX: str = ".download-part"
HTTP_USER_AGENT: str = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
MAX_PARALLEL_DOWNLOADS: int = int(os.environ.get("MAX_PARALLEL_DOWNLOADS", "5"))
DOWNLOAD_MAX_RETRIES: int = 3
DOWNLOAD_RETRY_DELAY: float = 2.0
DOWNLOAD_TIMEOUT: float = 300.0
GITHUB_TOKEN: str | None = os.environ.get("GITHUB_TOKEN")

# ---- 验证所需的必需组件 ----
REQUIRED_ITEMS: tuple[str, ...] = ("Atmosphere", "Fusee", "Hekate + Nyx CHS")

# ---- 在 sdcard 内创建的目录结构 ----
SDCARD_DIRS: tuple[str, ...] = (
    "atmosphere/config",
    "atmosphere/hosts",
    "atmosphere/contents/420000000007E51Anx-ovlloader",
    "atmosphere/contents/0000000000534C56ReverseNX-RT",
    "atmosphere/contents/4200000000000010ldn_mitm",
    "atmosphere/contents/0100000000000352emuiibo",
    "atmosphere/contents/0100000000000F12Fizeau",
    "atmosphere/contents/4200000000000000sys-tune",
    "atmosphere/contents/420000000000000Bsys-patch",
    "atmosphere/contents/010000000000bd00MissionControl",
    "atmosphere/contents/00FF0000636C6BFFsys-clk",
    "atmosphere/kips",
    "bootloader/payloads",
    "config/ultrahand/lang",
    "switch/Switch_90DNS_tester",
    "switch/DBI",
    "switch/NX-Shell",
    "switch/HB-App-Store",
    "switch/HekateToolbox",
    "switch/JKSV",
    "switch/Moonlight",
    "switch/NXThemesInstaller",
    "switch/SimpleModDownloader",
    "switch/Switchfin",
    "switch/wiliwili",
    "switch/NX-Activity-Log",
    "switch/Sphaira",
    "switch/.overlays",
    "switch/.packages",
)

# ---- 最终结构验证所需的文件 ----
REQUIRED_PATHS: tuple[str, ...] = (
    "atmosphere/package3",
    "bootloader/hekate_ipl.ini",
    "exosphere.ini",
    "boot.ini",
    "atmosphere/config/override_config.ini",
    "atmosphere/config/system_settings.ini",
    "atmosphere/hosts/emummc.txt",
    "atmosphere/hosts/sysmmc.txt",
    "bootloader/payloads/fusee.bin",
    "payload.bin",
)

# ---- 清理文件（收尾阶段删除） ----
CLEANUP_FILES: tuple[str, ...] = (
    "switch/haze.nro",
    "switch/reboot_to_payload.nro",
    "switch/daybreak.nro",
)

# ---- 模板文件映射：源 -> 目标 ----
TEMPLATE_MAPPING: dict[str, list[str]] = {
    "hekate_ipl.ini": ["bootloader/hekate_ipl.ini"],
    "exosphere.ini": ["exosphere.ini"],
    "hosts.txt": ["atmosphere/hosts/emummc.txt", "atmosphere/hosts/sysmmc.txt"],
    "boot.ini": ["boot.ini"],
    "override_config.ini": ["atmosphere/config/override_config.ini"],
    "system_settings.ini": ["atmosphere/config/system_settings.ini"],
}

# ---- 下载目录定义 ----

# 每个目录条目描述要下载的内容及其放置位置。
# 类型：
#   "github_release"  — 获取匹配正则的最新 release 资源
#   "direct_url"      — 从固定 URL 下载
#   "git_clone"       — 浅克隆 git 仓库

from typing import NamedTuple


class GitHubAsset(NamedTuple):
    """单个 GitHub release 资源下载的定义。"""

    repo: str  # 例如 "Atmosphere-NX/Atmosphere"
    pattern: str  # 匹配资源名称的正则表达式
    name: str  # 显示名称
    dest_filename: str  # 下载后的文件名（先放在当前目录，再移动）
    extract: bool = False  # 下载后是否解压
    extract_subdir: str = ""  # 解压到 sdcard 内的子目录
    target_path: str = ""  # sdcard 内的最终路径（用于不需要解压的文件）


class DirectDownload(NamedTuple):
    """直链下载的定义。"""

    url: str
    name: str
    dest_filename: str
    extract: bool = False
    extract_subdir: str = ""
    target_path: str = ""  # 下载后文件的最终路径


# ---- 核心系统下载 ----
CORE_ATMOSPHERE = GitHubAsset(
    repo="Atmosphere-NX/Atmosphere",
    pattern=r"atmosphere.*\.zip",
    name="Atmosphere",
    dest_filename="atmosphere.zip",
    extract=True,
)

CORE_FUSEE = GitHubAsset(
    repo="Atmosphere-NX/Atmosphere",
    pattern=r"fusee\.bin",
    name="Fusee",
    dest_filename="fusee.bin",
    target_path="bootloader/payloads/",
)

CORE_HEKATE = GitHubAsset(
    repo="easyworld/hekate",
    pattern=r"hekate_ctcaer.*_sc\.zip",
    name="Hekate + Nyx CHS",
    dest_filename="hekate.zip",
    extract=True,
)

CORE_SIGPATCHES = DirectDownload(
    url="https://raw.githubusercontent.com/huangqian8/SwitchPlugins/main/plugins/sigpatches.zip",
    name="Sigpatches",
    dest_filename="sigpatches.zip",
    extract=True,
)

CORE_LOGO = DirectDownload(
    url="https://raw.githubusercontent.com/huangqian8/SwitchPlugins/main/theme/logo.zip",
    name="Logo",
    dest_filename="logo.zip",
    extract=True,
)

# ---- Payload 定义 ----
PAYLOADS: tuple[GitHubAsset, ...] = (
    GitHubAsset(
        repo="zdm65477730/CommonProblemResolver",
        pattern=r"CommonProblemResolver\.bin",
        name="CommonProblemResolver",
        dest_filename="CommonProblemResolver.bin",
        target_path="bootloader/payloads/",
    ),
    GitHubAsset(
        repo="Kofysh/Lockpick_RCM",
        pattern=r"Lockpick_RCM\.bin",
        name="Lockpick_RCM",
        dest_filename="Lockpick_RCM.bin",
        target_path="bootloader/payloads/",
    ),
    GitHubAsset(
        repo="zdm65477730/TegraExplorer",
        pattern=r"TegraExplorer\.bin",
        name="TegraExplorer",
        dest_filename="TegraExplorer.bin",
        target_path="bootloader/payloads/",
    ),
)

# ---- 自制应用程序定义 ----
HOMEBREW_APPS: tuple[GitHubAsset, ...] = (
    GitHubAsset(
        repo="J-D-K/JKSV",
        pattern=r"JKSV\.nro",
        name="JKSV",
        dest_filename="JKSV.nro",
        target_path="switch/JKSV/",
    ),
    GitHubAsset(
        repo="PoloNX/SimpleModDownloader",
        pattern=r"SimpleModDownloader\.nro",
        name="SimpleModDownloader",
        dest_filename="SimpleModDownloader.nro",
        target_path="switch/SimpleModDownloader/",
    ),
    GitHubAsset(
        repo="WerWolv/Hekate-Toolbox",
        pattern=r"HekateToolbox\.nro",
        name="HekateToolbox",
        dest_filename="HekateToolbox.nro",
        target_path="switch/HekateToolbox/",
    ),
    GitHubAsset(
        repo="XITRIX/Moonlight-Switch",
        pattern=r"Moonlight-Switch\.nro",
        name="Moonlight",
        dest_filename="Moonlight-Switch.nro",
        target_path="switch/Moonlight/",
    ),
    GitHubAsset(
        repo="dragonflylee/switchfin",
        pattern=r"Switchfin\.nro",
        name="Switchfin",
        dest_filename="Switchfin.nro",
        target_path="switch/Switchfin/",
    ),
    GitHubAsset(
        repo="exelix11/SwitchThemeInjector",
        pattern=r"NXThemesInstaller\.nro",
        name="NXThemesInstaller",
        dest_filename="NXThemesInstaller.nro",
        target_path="switch/NXThemesInstaller/",
    ),
    GitHubAsset(
        repo="fortheusers/hb-appstore",
        pattern=r"appstore\.nro",
        name="hb-appstore",
        dest_filename="appstore.nro",
        target_path="switch/HB-App-Store/",
    ),
    GitHubAsset(
        repo="gzk47/DBIPatcher",
        pattern=r"DBI.*\.zhcn\.nro",
        name="DBI",
        dest_filename="DBI.nro",
        target_path="switch/DBI/",
    ),
    GitHubAsset(
        repo="meganukebmp/Switch_90DNS_tester",
        pattern=r"Switch_90DNS_tester\.nro",
        name="Switch_90DNS_tester",
        dest_filename="Switch_90DNS_tester.nro",
        target_path="switch/Switch_90DNS_tester/",
    ),
    GitHubAsset(
        repo="zdm65477730/NX-Activity-Log",
        pattern=r"NX-Activity-Log\.nro",
        name="NX-Activity-Log",
        dest_filename="NX-Activity-Log.nro",
        target_path="switch/NX-Activity-Log/",
    ),
    GitHubAsset(
        repo="zdm65477730/NX-Shell",
        pattern=r"NX-Shell\.nro",
        name="NX-Shell",
        dest_filename="NX-Shell.nro",
        target_path="switch/NX-Shell/",
    ),
)

# ---- 特殊下载 ----
SPECIAL_AWOO = GitHubAsset(
    repo="Huntereb/Awoo-Installer",
    pattern=r"Awoo-Installer\.zip",
    name="Awoo Installer",
    dest_filename="Awoo-Installer.zip",
    extract=True,
)

SPECIAL_SPHAIRA = GitHubAsset(
    repo="ITotalJustice/sphaira",
    pattern=r"sphaira\.zip",
    name="Sphaira",
    dest_filename="sphaira.zip",
    extract=True,
)

SPECIAL_AIO_UPDATER = GitHubAsset(
    repo="HamletDuFromage/aio-switch-updater",
    pattern=r"aio-switch-updater\.zip",
    name="aio-switch-updater",
    dest_filename="aio-switch-updater.zip",
    extract=True,
)

SPECIAL_WILIWILI = GitHubAsset(
    repo="xfangfang/wiliwili",
    pattern=r"wiliwili-NintendoSwitch\.zip",
    name="wiliwili",
    dest_filename="wiliwili-NintendoSwitch.zip",
    extract=True,
)

SPECIAL_DAYBREAK = DirectDownload(
    url="https://raw.githubusercontent.com/huangqian8/SwitchPlugins/main/plugins/daybreak_x.zip",
    name="daybreak",
    dest_filename="daybreak_x.zip",
    extract=True,
)

# ---- OC Toolkit ----
OC_TOOLKIT_REPO = "halop/OC_Toolkit_SC_EOS"
OC_TOOLKIT_KIP_PATTERN = r"kip\.zip"
OC_TOOLKIT_TOOLKIT_PATTERN = r"OC\.Toolkit\.u\.zip"

# ---- 主题补丁 ----
THEME_PATCHES_REPO = "https://github.com/exelix11/theme-patches"

# ---- 系统模块 ----
SYSTEM_MODULES: tuple[GitHubAsset, ...] = (
    GitHubAsset(
        repo="ndeadly/MissionControl",
        pattern=r"MissionControl.*\.zip",
        name="MissionControl",
        dest_filename="MissionControl.zip",
        extract=True,
    ),
    GitHubAsset(
        repo="zdm65477730/EdiZon-Overlay",
        pattern=r"EdiZon\.zip",
        name="EdiZon",
        dest_filename="EdiZon.zip",
        extract=True,
    ),
    GitHubAsset(
        repo="zdm65477730/Fizeau",
        pattern=r"Fizeau\.zip",
        name="Fizeau",
        dest_filename="Fizeau.zip",
        extract=True,
    ),
    GitHubAsset(
        repo="zdm65477730/QuickNTP",
        pattern=r"QuickNTP\.zip",
        name="QuickNTP",
        dest_filename="QuickNTP.zip",
        extract=True,
    ),
    GitHubAsset(
        repo="zdm65477730/ReverseNX-RT",
        pattern=r"ReverseNX-RT\.zip",
        name="ReverseNX-RT",
        dest_filename="ReverseNX-RT.zip",
        extract=True,
    ),
    GitHubAsset(
        repo="zdm65477730/Status-Monitor-Overlay",
        pattern=r"StatusMonitor\.zip",
        name="StatusMonitor",
        dest_filename="StatusMonitor.zip",
        extract=True,
    ),
    GitHubAsset(
        repo="zdm65477730/Ultrahand-Overlay",
        pattern=r"Ultrahand\.zip",
        name="Ultrahand-Overlay",
        dest_filename="Ultrahand.zip",
        extract=True,
    ),
    GitHubAsset(
        repo="zdm65477730/ldn_mitm",
        pattern=r"ldn_mitm\.zip",
        name="ldn_mitm",
        dest_filename="ldn_mitm.zip",
        extract=True,
    ),
    GitHubAsset(
        repo="zdm65477730/nx-ovlloader",
        pattern=r"nx-ovlloader\.zip",
        name="nx-ovlloader",
        dest_filename="nx-ovlloader.zip",
        extract=True,
    ),
    GitHubAsset(
        repo="zdm65477730/ovl-sysmodules",
        pattern=r"ovl-sysmodules\.zip",
        name="ovl-sysmodules",
        dest_filename="ovl-sysmodules.zip",
        extract=True,
    ),
    GitHubAsset(
        repo="zdm65477730/sys-clk",
        pattern=r"sys-clk.*\.zip",
        name="sys-clk",
        dest_filename="sys-clk.zip",
        extract=True,
    ),
    GitHubAsset(
        repo="zdm65477730/sys-patch",
        pattern=r"sys-patch\.zip",
        name="sys-patch",
        dest_filename="sys-patch.zip",
        extract=True,
    ),
)

# ---- Emuiibo（需要特殊处理） ----
SYSTEM_EMUIIBO = GitHubAsset(
    repo="XorTroll/emuiibo",
    pattern=r"emuiibo\.zip",
    name="emuiibo",
    dest_filename="emuiibo.zip",
    extract=True,
)

# ---- 运行分组 ----
ALL_GROUPS: tuple[str, ...] = (
    "core",
    "payload",
    "homebrew",
    "special",
    "system",
    "configs",
    "finalize",
)

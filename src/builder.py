"""目录结构构建器和下载编排器。

此模块将 GitHub API 客户端、下载管理器、
解压器和模板渲染器串联起来, 生成最终的 sdcard 目录树。
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from src import config
import logging

from src.config import (
    GitHubAsset,
    DirectDownload,
    TEMPLATE_MAPPING,
    CLEANUP_FILES,
    REQUIRED_ITEMS,
    REQUIRED_PATHS,
    SDCARD_DIR,
    SDCARD_DIRS,
    TEMPLATE_DIR,
    DESCRIPTION_FILE,
)
from src.github_api import GitHubClient
from src.downloader import DownloadManager
from src.extractor import extract_archive
logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass
class BuildContext:
    """构建阶段间共享的可变状态。"""

    sd_root: Path = field(default_factory=lambda: Path(SDCARD_DIR))
    description_lines: list[str] = field(default_factory=list)
    item_status: set[str] = field(default_factory=set)
    failed_items: list[str] = field(default_factory=list)
    github: GitHubClient = field(default_factory=GitHubClient)
    dry_run: bool = False

    # ---- 辅助方法 ----

    def record_item(self, name: str, version: str = "unknown") -> None:
        self.description_lines.append(f"{name} ({version})")
        self.item_status.add(name)

    def record_failure(self, name: str) -> None:
        if name not in self.failed_items:
            self.failed_items.append(name)

    def has_required(self, name: str) -> bool:
        return name in self.item_status

    def write_description(self) -> None:
        DESCRIPTION_FILE.write_text("\n".join(self.description_lines) + "\n")


class BuildError(Exception):
    """构建过程中的致命错误 — 缺少必需组件等。"""


# ======================================================================
# 公共 API
# ======================================================================


async def run_core(ctx: BuildContext) -> None:
    """下载并解压核心系统文件（Atmosphere、Hekate 等）。"""
    logger.info("正在下载核心系统文件……")

    # -- Atmosphere --
    asset = ctx.github.get_latest_release_asset(
        config.CORE_ATMOSPHERE.repo, config.CORE_ATMOSPHERE.pattern
    )
    if asset:
        ok = await _download_one(
            ctx,
            asset.url,
            ctx.sd_root / config.CORE_ATMOSPHERE.dest_filename,
            config.CORE_ATMOSPHERE.name,
        )
        if ok:
            _extract_at(ctx, ctx.sd_root / config.CORE_ATMOSPHERE.dest_filename,
                        config.CORE_ATMOSPHERE.name)
            ctx.record_item(config.CORE_ATMOSPHERE.name, asset.tag)
    else:
        ctx.record_failure(config.CORE_ATMOSPHERE.name)

    # -- Fusee --
    fusee_asset = ctx.github.get_latest_release_asset(
        config.CORE_FUSEE.repo, config.CORE_FUSEE.pattern
    )
    fusee_tag = asset.tag if asset else "unknown"
    if fusee_asset:
        ok = await _download_one(
            ctx,
            fusee_asset.url,
            ctx.sd_root / config.CORE_FUSEE.dest_filename,
            config.CORE_FUSEE.name,
        )
        if ok:
            _move_file(ctx, config.CORE_FUSEE.dest_filename,
                       config.CORE_FUSEE.target_path, config.CORE_FUSEE.name)
            ctx.record_item(config.CORE_FUSEE.name, fusee_tag)
    else:
        ctx.record_failure(config.CORE_FUSEE.name)

    # -- Hekate --
    hekate_asset = ctx.github.get_latest_release_asset(
        config.CORE_HEKATE.repo, config.CORE_HEKATE.pattern
    )
    if hekate_asset:
        ok = await _download_one(
            ctx,
            hekate_asset.url,
            ctx.sd_root / config.CORE_HEKATE.dest_filename,
            config.CORE_HEKATE.name,
        )
        if ok:
            _extract_at(ctx, ctx.sd_root / config.CORE_HEKATE.dest_filename,
                        config.CORE_HEKATE.name)
            ctx.record_item(config.CORE_HEKATE.name, hekate_asset.tag)
    else:
        ctx.record_failure(config.CORE_HEKATE.name)

    # -- Sigpatches --
    await _download_direct(ctx, config.CORE_SIGPATCHES)
    ctx.record_item(config.CORE_SIGPATCHES.name, "raw-main")

    # -- Logo --
    await _download_direct(ctx, config.CORE_LOGO)
    ctx.record_item(config.CORE_LOGO.name, "raw-main")


async def run_payload(ctx: BuildContext) -> None:
    """并行下载 payload 文件。"""
    logger.info("正在下载 payload……")
    await _download_github_assets(ctx, config.PAYLOADS,
                                   target_dir_field="target_path")


async def run_homebrew(ctx: BuildContext) -> None:
    """并行下载自制 .nro 应用程序。"""
    logger.info("正在下载自制应用程序……")
    await _download_github_assets(ctx, config.HOMEBREW_APPS,
                                   target_dir_field="target_path")


async def run_special(ctx: BuildContext) -> None:
    """下载需要自定义处理的特殊软件包。"""
    logger.info("正在下载特殊软件包……")

    # Awoo Installer
    await _download_github_assets(ctx, [config.SPECIAL_AWOO],
                                   target_dir_field="",
                                   extract=True)

    # Sphaira
    await _download_github_assets(ctx, [config.SPECIAL_SPHAIRA],
                                   target_dir_field="",
                                   extract=True)

    # AIO Switch Updater
    await _download_github_assets(ctx, [config.SPECIAL_AIO_UPDATER],
                                   target_dir_field="",
                                   extract=True)

    # Wiliwili - 解压后需要自定义移动操作
    wili_asset = ctx.github.get_latest_release_asset(
        config.SPECIAL_WILIWILI.repo, config.SPECIAL_WILIWILI.pattern
    )
    if wili_asset:
        ok = await _download_one(
            ctx, wili_asset.url,
            ctx.sd_root / config.SPECIAL_WILIWILI.dest_filename,
            config.SPECIAL_WILIWILI.name,
        )
        if ok:
            _extract_at(ctx, ctx.sd_root / config.SPECIAL_WILIWILI.dest_filename,
                        config.SPECIAL_WILIWILI.name)
            wili_dir = ctx.sd_root / "wiliwili"
            target = ctx.sd_root / "switch" / "wiliwili"
            if wili_dir.is_dir():
                nro = wili_dir / "wiliwili.nro"
                if nro.is_file():
                    target.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(nro), str(target / "wiliwili.nro"))
                shutil.rmtree(wili_dir)
            ctx.record_item(config.SPECIAL_WILIWILI.name, wili_asset.tag)
    else:
        ctx.record_failure(config.SPECIAL_WILIWILI.name)

    # Daybreak
    await _download_direct(ctx, config.SPECIAL_DAYBREAK)
    ctx.record_item(config.SPECIAL_DAYBREAK.name, "raw-main")

    # 主题补丁（git clone）
    await _clone_theme_patches(ctx)

    # OC Toolkit
    await _download_oc_toolkit(ctx)


async def run_system(ctx: BuildContext) -> None:
    """下载系统模块和覆盖层。"""
    logger.info("正在下载系统模块和覆盖层……")

    await _download_github_assets(ctx, config.SYSTEM_MODULES,
                                   target_dir_field="",
                                   extract=True)

    # Emuiibo（解压后需要特殊处理）
    emu_asset = ctx.github.get_latest_release_asset(
        config.SYSTEM_EMUIIBO.repo, config.SYSTEM_EMUIIBO.pattern
    )
    if emu_asset:
        ok = await _download_one(
            ctx, emu_asset.url,
            ctx.sd_root / config.SYSTEM_EMUIIBO.dest_filename,
            config.SYSTEM_EMUIIBO.name,
        )
        if ok:
            _extract_at(ctx, ctx.sd_root / config.SYSTEM_EMUIIBO.dest_filename,
                        config.SYSTEM_EMUIIBO.name)
            sdout = ctx.sd_root / "SdOut"
            if sdout.is_dir():
                _copy_tree(sdout, ctx.sd_root)
                shutil.rmtree(sdout)
            ctx.record_item(config.SYSTEM_EMUIIBO.name, emu_asset.tag)
    else:
        ctx.record_failure(config.SYSTEM_EMUIIBO.name)


async def run_configs(ctx: BuildContext) -> None:
    """从模板生成配置文件。"""
    logger.info("正在生成配置文件……")

    for src_name, dest_rels in TEMPLATE_MAPPING.items():
        src = TEMPLATE_DIR / src_name
        for dest_rel in dest_rels:
            dest = ctx.sd_root / dest_rel
            if not src.is_file():
                logger.error(f"缺少模板: {src_name}")
                ctx.record_failure(f"template:{src_name}")
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not ctx.dry_run:
                shutil.copy2(src, dest)

    logger.info("配置文件生成完毕")


async def run_finalize(ctx: BuildContext) -> None:
    """收尾 sdcard 目录树: 重命名 payload、清理多余文件。"""
    logger.info("正在收尾设置……")

    if ctx.dry_run:
        return

    # 将 hekate_ctcaer*.bin 重命名为 payload.bin
    candidates = list(ctx.sd_root.glob("hekate_ctcaer*.bin"))
    if candidates:
        hekate_bin = candidates[0]
        hekate_bin.rename(ctx.sd_root / "payload.bin")
        logger.info(f"已将 {hekate_bin.name} 重命名为 payload.bin")
    elif (ctx.sd_root / "payload.bin").exists():
        logger.info("payload.bin 已存在。")
    else:
        logger.error("无法将 hekate_ctcaer_*.bin 重命名为 payload.bin")
        ctx.record_failure("payload.bin")

    # 删除不需要的文件
    for rel in CLEANUP_FILES:
        f = ctx.sd_root / rel
        if f.is_file():
            f.unlink()

    # 删除 boot2.flag 文件
    contents_dir = ctx.sd_root / "atmosphere" / "contents"
    if contents_dir.is_dir():
        removed = 0
        for flag in contents_dir.rglob("boot2.flag"):
            if flag.is_file():
                flag.unlink()
                removed += 1
        logger.info(f"已从 atmosphere/contents 中删除 {removed} 个 boot2.flag 文件")

    logger.info("设置收尾完毕")


# ======================================================================
# 验证
# ======================================================================


def validate_structure(ctx: BuildContext) -> None:
    """确保 sdcard 目录树中存在所有必需的文件。"""
    logger.info("正在验证 sdcard 最终结构……")
    missing = 0
    for rel in REQUIRED_PATHS:
        if not (ctx.sd_root / rel).exists():
            logger.error(f"缺少预期文件: {rel}")
            missing += 1

    if missing:
        raise BuildError("最终结构验证失败。")
    logger.info("最终结构验证通过")


def validate_required(ctx: BuildContext) -> None:
    """验证所有必需组件是否已成功下载。"""
    missing = 0
    for item in REQUIRED_ITEMS:
        if not ctx.has_required(item):
            logger.error(f"缺少必需组件: {item}")
            ctx.record_failure(item)
            missing += 1
    if missing:
        raise BuildError("缺少必需组件, 正在中止。")


# ======================================================================
# 工作区设置/清理辅助函数
# ======================================================================


def setup_workspace(ctx: BuildContext, *, clean: bool = True) -> None:
    """创建 sdcard 目录树。

    当 *clean* 为 True 时, 先删除已有的 sdcard 目录树；
    否则保留已有内容, 仅创建缺失的目录。
    """
    if clean and ctx.sd_root.exists():
        shutil.rmtree(ctx.sd_root)
    if DESCRIPTION_FILE.exists():
        DESCRIPTION_FILE.unlink()

    for rel in SDCARD_DIRS:
        (ctx.sd_root / rel).mkdir(parents=True, exist_ok=True)


def cleanup_stale_tmp(sd_root: Path | None = None) -> None:
    """清理 sdcard 目录下残留的 ``*.download-part`` 临时文件。"""
    root = sd_root or SDCARD_DIR
    if root.is_dir():
        for tmp in root.rglob(f"*{config.DOWNLOAD_TMP_SUFFIX}"):
            if tmp.is_file():
                tmp.unlink()


# ======================================================================
# 内部辅助函数
# ======================================================================


async def _download_one(
    ctx: BuildContext,
    url: str,
    dest: Path,
    description: str,
) -> bool:
    """下载单个文件（同步, 不使用并行队列）。"""
    if ctx.dry_run:
        logger.info(f"[试运行] 将下载 {description}, 来自 {url}")
        return True

    mgr = DownloadManager()
    mgr.enqueue(description, url, dest, description)
    results = await mgr.wait_all()
    job = results.get(description)
    if job and job.status == "ok":
        return True
    ctx.record_failure(description)
    return False


async def _download_direct(ctx: BuildContext, dd: DirectDownload) -> bool:
    """下载直链项目, 可选择性解压。"""
    if ctx.dry_run:
        logger.info(f"[试运行] 将下载 {dd.name}, 来自 {dd.url}")
        return True

    dest = ctx.sd_root / dd.dest_filename
    mgr = DownloadManager()
    mgr.enqueue(dd.name, dd.url, dest, dd.name)
    results = await mgr.wait_all()
    job = results.get(dd.name)
    if not job or job.status != "ok":
        ctx.record_failure(dd.name)
        return False

    if dd.extract:
        _extract_at(ctx, dest, dd.name, dd.extract_subdir)
    if dd.target_path:
        _move_file(ctx, dd.dest_filename, dd.target_path, dd.name)
    return True


async def _download_github_assets(
    ctx: BuildContext,
    assets: tuple[GitHubAsset, ...],
    *,
    target_dir_field: str = "target_path",
    extract: bool = False,
) -> None:
    """并行下载一批 GitHub release 资源。

    对每个 :class:`GitHubAsset`, 先解析最新匹配的 release, 
    然后在共享的并行队列中一起下载。
    """
    # 阶段 1: 解析 URL
    resolved: list[tuple[GitHubAsset, str, str]] = []  # (asset, url, tag)
    for ga in assets:
        asset = ctx.github.get_latest_release_asset(ga.repo, ga.pattern)
        if asset:
            resolved.append((ga, asset.url, asset.tag))
        else:
            ctx.record_failure(ga.name)

    if not resolved:
        return

    # 阶段 2: 并行下载
    mgr = DownloadManager()
    for ga, url, _tag in resolved:
        dest = ctx.sd_root / ga.dest_filename
        mgr.enqueue(ga.name, url, dest, ga.name)

    results = await mgr.wait_all()

    # 阶段 3: 下载后处理（解压、移动）
    for ga, _url, tag in resolved:
        job = results.get(ga.name)
        if not job or job.status != "ok":
            continue

        need_extract = extract or ga.extract
        if need_extract:
            archive = ctx.sd_root / ga.dest_filename
            _extract_at(ctx, archive, ga.name, ga.extract_subdir)

        if target_dir_field and getattr(ga, target_dir_field, ""):
            _move_file(ctx, ga.dest_filename, getattr(ga, target_dir_field), ga.name)

        ctx.record_item(ga.name, tag)


async def _clone_theme_patches(ctx: BuildContext) -> None:
    """浅克隆 theme-patches 仓库并提取 systemPatches。"""
    if ctx.dry_run:
        logger.info(f"[试运行] 将克隆 {config.THEME_PATCHES_REPO}")
        return

    clone_dir = ctx.sd_root / "theme-patches"
    if clone_dir.exists():
        shutil.rmtree(clone_dir)

    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", config.THEME_PATCHES_REPO,
             str(clone_dir)],
            check=True, capture_output=True, text=True,
        )
        logger.info("theme-patches 下载完毕")

        # 从 git 获取版本号
        result = subprocess.run(
            ["git", "-C", str(clone_dir), "rev-parse", "--short", "HEAD"],
            check=False, capture_output=True, text=True,
        )
        version = result.stdout.strip() if result.returncode == 0 else "unknown"

        themes_dir = ctx.sd_root / "themes"
        themes_dir.mkdir(parents=True, exist_ok=True)
        src_patches = clone_dir / "systemPatches"
        if src_patches.is_dir():
            _copy_tree(src_patches, themes_dir / "systemPatches")

        shutil.rmtree(clone_dir)
        ctx.record_item("theme-patches", version)
    except subprocess.CalledProcessError as exc:
        logger.error(f"theme-patches 下载失败: {exc}")
        ctx.record_failure("theme-patches")
        if clone_dir.exists():
            shutil.rmtree(clone_dir)


async def _download_oc_toolkit(ctx: BuildContext) -> None:
    """下载 OC Toolkit（kip + toolkit zip）。"""
    if ctx.dry_run:
        logger.info(f"[试运行] 将下载 OC Toolkit, 来自 {config.OC_TOOLKIT_REPO}")
        return

    try:
        release = ctx.github.get_release(config.OC_TOOLKIT_REPO)
        if not release:
            ctx.record_failure("OC_Toolkit_SC_EOS")
            return

        import re
        tag = str(release.get("tag_name", "unknown"))
        assets = release.get("assets", [])
        if not isinstance(assets, list):
            ctx.record_failure("OC_Toolkit_SC_EOS")
            return

        kip_url: str | None = None
        toolkit_url: str | None = None
        for a in assets:
            if not isinstance(a, dict):
                continue
            name = a.get("name", "")
            url = a.get("browser_download_url", "")
            if not isinstance(name, str) or not isinstance(url, str):
                continue
            if re.search(config.OC_TOOLKIT_KIP_PATTERN, name) and not kip_url:
                kip_url = url
            elif re.search(config.OC_TOOLKIT_TOOLKIT_PATTERN, name) and not toolkit_url:
                toolkit_url = url

        if not kip_url or not toolkit_url:
            ctx.record_failure("OC_Toolkit_SC_EOS")
            return

        mgr = DownloadManager()
        mgr.enqueue("oc-kip", kip_url, ctx.sd_root / "kip.zip", "OC Toolkit KIP")
        mgr.enqueue("oc-toolkit", toolkit_url, ctx.sd_root / "OC.Toolkit.u.zip", "OC Toolkit")
        results = await mgr.wait_all()

        if results.get("oc-kip", None) and results["oc-kip"].status == "ok":
            _extract_at(ctx, ctx.sd_root / "kip.zip", "OC Toolkit KIP",
                        str(ctx.sd_root / "atmosphere" / "kips"))
        else:
            ctx.record_failure("OC_Toolkit_SC_EOS")

        if results.get("oc-toolkit", None) and results["oc-toolkit"].status == "ok":
            _extract_at(ctx, ctx.sd_root / "OC.Toolkit.u.zip", "OC Toolkit",
                        str(ctx.sd_root / "switch" / ".packages"))

        ctx.record_item("OC_Toolkit_SC_EOS", tag)
        logger.info("OC_Toolkit_SC_EOS 下载完毕")
    except Exception:
        logger.error("OC_Toolkit_SC_EOS 下载失败")
        ctx.record_failure("OC_Toolkit_SC_EOS")


# ======================================================================
# 文件系统辅助函数
# ======================================================================


def _extract_at(
    ctx: BuildContext,
    archive: Path,
    description: str,
    subdir: str = "",
) -> None:
    """解压 *archive*, 可选择性解压到 sd_root 的 *subdir* 子目录中。"""
    if ctx.dry_run:
        return
    try:
        dest = (ctx.sd_root / subdir) if subdir else None
        extract_archive(archive, description, dest)
    except Exception as exc:
        logger.error(f"{description} 解压失败: {exc}")
        ctx.record_failure(description)


def _move_file(
    ctx: BuildContext,
    src_rel: str,
    dest_rel: str,
    description: str,
) -> None:
    """在 sd_root 内移动文件。若源文件不存在则静默跳过。"""
    if ctx.dry_run:
        return
    src = ctx.sd_root / src_rel
    dest = ctx.sd_root / dest_rel
    if not src.exists():
        return
    dest.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest / src.name))


def _copy_tree(src: Path, dest: Path) -> None:
    """递归复制 *src* 到 *dest*, 自动创建父目录。"""
    dest.mkdir(parents=True, exist_ok=True)
    # shutil.copytree 并允许目标已存在
    shutil.copytree(src, dest, dirs_exist_ok=True)

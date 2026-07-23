from __future__ import annotations

import argparse
import asyncio
import sys

from src import config
from src.builder import (
    BuildContext,
    BuildError,
    cleanup_stale_tmp,
    run_configs,
    run_core,
    run_finalize,
    run_homebrew,
    run_payload,
    run_special,
    run_system,
    setup_workspace,
    validate_required,
    validate_structure,
)
import logging

logger = logging.getLogger(__name__)

# ANSI 颜色码，用于终端输出
_YELLOW = "\033[33m"
_GREEN = "\033[32m"
_NC = "\033[0m"


class ColoredFormatter(logging.Formatter):
    """为日志级别名称添加 ANSI 颜色的日志格式化器。"""

    _COLORS = {
        logging.ERROR: "\033[31m",    # 红色
        logging.WARNING: "\033[33m",  # 黄色
    }
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self._COLORS.get(record.levelno, "")
        record.levelname = f"[{record.levelname}]"
        if color:
            record.levelname = f"{color}{record.levelname}{self._RESET}"
        return super().format(record)


def setup_logging() -> None:
    """配置根日志记录器，输出带颜色的终端日志。"""
    handler = logging.StreamHandler()
    handler.setFormatter(ColoredFormatter("%(levelname)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])


# ======================================================================
# 命令行参数解析
# ======================================================================


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="switchscript",
        description="大气层个人整合包生成工具 — Nintendo Switch Atmosphere CFW 整合包构建器",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="仅打印选定计划并退出（不进行下载或文件系统更改）。",
    )
    p.add_argument(
        "--only",
        type=str,
        metavar="GROUPS",
        help=(
            "仅运行选定的分组（逗号分隔）。"
            f"可用分组：{', '.join(config.ALL_GROUPS)}"
        ),
    )
    p.add_argument(
        "--max-parallel",
        type=int,
        default=config.MAX_PARALLEL_DOWNLOADS,
        help=f"最大并行下载数（默认：{config.MAX_PARALLEL_DOWNLOADS}）。",
    )
    return p


def resolve_enabled_groups(only_arg: str | None) -> frozenset[str]:
    """将 ``--only`` 参数解析为一组启用的分组。

    ``"all"`` 返回空集合（表示：所有分组均启用）。
    未知的分组名称将导致程序退出并报错。
    """
    if not only_arg:
        return frozenset()  # 空集合表示"全部"

    parts = [g.strip() for g in only_arg.split(",") if g.strip()]
    enabled: set[str] = set()

    for group in parts:
        if group == "all":
            return frozenset()
        if group not in config.ALL_GROUPS:
            print(f"--only 的未知分组：{group}", file=sys.stderr)
            sys.exit(1)
        enabled.add(group)

    return frozenset(enabled)


# ======================================================================
# 编排调度
# ======================================================================


async def run_build(
    ctx: BuildContext,
    enabled: frozenset[str],
) -> None:
    """按依赖顺序执行构建阶段。

    *enabled* 为 ``frozenset()``（空）时运行所有分组，
    或为特定分组名称的集合。
    """

    def _on(name: str) -> bool:
        return not enabled or name in enabled

    has_core = _on("core")
    has_payload = _on("payload")
    has_homebrew = _on("homebrew")
    has_special = _on("special")
    has_system = _on("system")
    has_configs = _on("configs")
    has_finalize = _on("finalize")

    is_full = enabled == frozenset()

    # 1. 工作区
    if is_full:
        setup_workspace(ctx, clean=True)
        cleanup_stale_tmp(ctx.sd_root)
    else:
        logger.info(
            "正在创建目录结构，保留现有 sdcard 内容……"
        )
        setup_workspace(ctx, clean=False)
        cleanup_stale_tmp(ctx.sd_root)

    # 2. 下载（顺序重要 — 核心必须先下载以进行验证）
    if has_core:
        await run_core(ctx)

    if has_payload:
        await run_payload(ctx)

    if has_homebrew:
        await run_homebrew(ctx)

    if has_special:
        await run_special(ctx)

    if has_system:
        await run_system(ctx)

    # 3. 核心下载后验证必需项
    if has_core:
        validate_required(ctx)

    # 4. 打印失败摘要
    _print_failure_summary(ctx)

    # 5. 写入描述文件
    if any([has_core, has_payload, has_homebrew, has_special, has_system]):
        ctx.write_description()

    # 6. 配置生成
    if has_configs:
        await run_configs(ctx)

    # 7. 收尾
    if has_finalize:
        await run_finalize(ctx)

    # 8. 完整运行验证
    if has_core and has_configs and has_finalize:
        validate_structure(ctx)


def _print_failure_summary(ctx: BuildContext) -> None:
    """打印所有下载失败的摘要。"""
    if not ctx.failed_items:
        logger.info("所有下载均已完成，无失败记录。")
        return

    logger.info(f"部分下载失败（{len(ctx.failed_items)} 项）：")
    for item in ctx.failed_items:
        print(f" - {item}")


# ======================================================================
# 入口点
# ======================================================================


def main(argv: list[str] | None = None) -> None:
    setup_logging()
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    enabled = resolve_enabled_groups(args.only)

    if args.max_parallel:
        config.MAX_PARALLEL_DOWNLOADS = args.max_parallel

    # --dry-run
    if args.dry_run:
        logger.info(
            "试运行模式已启用。不会进行下载或文件系统更改。"
        )
        if not enabled:
            logger.info("已选分组：全部")
        else:
            logger.info("已选分组：")
            for g in config.ALL_GROUPS:
                if g in enabled:
                    print(f" - {g}")
        return

    # 检查依赖
    _check_deps()

    # 构建
    ctx = BuildContext(dry_run=False)
    try:
        asyncio.run(run_build(ctx, enabled))
    except BuildError:
        sys.exit(1)
    finally:
        ctx.github.close()

    if ctx.failed_items:
        logger.info("设置已完成，但存在警告。请查看上述失败项。")
        print(
            f"\n{_YELLOW}你的 Switch SD 卡已准备就绪，"
            f"但部分可选项目失败。{_NC}"
        )
    else:
        logger.info("设置已成功完成！")
        print(
            f"\n{_GREEN}你的 Switch SD 卡已准备就绪！"
            f"{_NC}"
        )


def _check_deps() -> None:
    """验证所需的系统工具是否可用。"""
    import shutil

    missing: list[str] = []
    # git 用于克隆主题补丁仓库
    for tool in ("git",):
        if shutil.which(tool) is None:
            missing.append(tool)
            logger.error(f"缺少依赖：{tool}")

    if missing:
        print(
            "请先安装必需的依赖：git。",
            file=sys.stderr,
        )
        sys.exit(1)


# 支持通过 `python -m src.main` 运行
if __name__ == "__main__":
    main()

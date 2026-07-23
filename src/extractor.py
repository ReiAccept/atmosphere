"""压缩包解压工具。

支持通过 Python 内置的 ``zipfile`` 解压 .zip 压缩包, 
以及通过外部 ``7z`` 二进制文件解压 .7z 文件。
"""

from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path

import logging

logger = logging.getLogger(__name__)


class ExtractionError(Exception):
    """压缩包解压失败时抛出。"""


def extract_archive(
    archive: Path,
    description: str,
    extract_dir: Path | None = None,
) -> None:
    """原地解压 *archive*（或解压到 *extract_dir*）, 然后删除压缩包。

    当压缩包不存在、格式不受支持或解压工具失败时, 
    抛出 :class:`ExtractionError`。
    """
    if not archive.is_file():
        raise ExtractionError(
            f"{description} 解压失败: 文件未找到（{archive}）"
        )

    dest = extract_dir or archive.parent
    suffix = archive.suffix.lower()

    try:
        if suffix == ".zip":
            _extract_zip(archive, dest)
        elif suffix == ".7z":
            _extract_7z(archive, dest)
        else:
            raise ExtractionError(f"未知的压缩包格式: {archive}")
    except ExtractionError:
        raise
    except Exception as exc:
        raise ExtractionError(f"{description} 解压错误: {exc}") from exc

    # 解压成功后删除压缩包
    archive.unlink()
    logger.info(f"{description} 解压完毕")


# ------------------------------------------------------------------
# 内部函数
# ------------------------------------------------------------------


def _extract_zip(archive: Path, dest: Path) -> None:
    """将 .zip 压缩包解压到 *dest*。"""
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "r") as zf:
        zf.extractall(dest)


def _extract_7z(archive: Path, dest: Path) -> None:
    """使用 ``7z`` 命令行工具解压 .7z 压缩包。"""
    if shutil.which("7z") is None:
        raise ExtractionError(
            f"无法解压 {archive.name}: 缺少依赖 '7z'。"
            "请安装 p7zip / 7-Zip 后重试。"
        )
    dest.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["7z", "x", str(archive), f"-o{dest}", "-y"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ExtractionError(
            f"7z 解压 {archive.name} 失败: {result.stderr.strip()}"
        )

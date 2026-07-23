"""带按仓库 release 缓存的 GitHub API 客户端。

处理认证/匿名请求、速率限制感知，
并在运行期间按仓库缓存 release JSON。
"""

from __future__ import annotations

import re
from typing import NamedTuple

import httpx

from src.config import GITHUB_TOKEN, HTTP_USER_AGENT
import logging

logger = logging.getLogger(__name__)

GITHUB_API_BASE: str = "https://api.github.com"


class ReleaseAsset(NamedTuple):
    """已解析的 release 资源，包含 URL 和 tag 版本。"""

    url: str
    tag: str


class GitHubClient:
    """最小化的 GitHub API 客户端，带内存缓存用于 release 查询。"""

    def __init__(self) -> None:
        headers: dict[str, str] = {
            "Accept": "application/vnd.github+json",
            "User-Agent": HTTP_USER_AGENT,
        }
        if GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

        self._client = httpx.Client(
            headers=headers,
            timeout=30.0,
            follow_redirects=True,
        )
        # 按仓库缓存的 release JSON
        self._release_cache: dict[str, dict[str, object]] = {}

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    def get_latest_release_asset(self, repo: str, pattern: str) -> ReleaseAsset | None:
        """返回名称匹配 *pattern* 的最新 release 资源的
        browser_download_url 和 tag，未找到则返回 *None*。"""
        release = self._get_release(repo)
        if release is None:
            return None

        tag = release.get("tag_name", "unknown")
        assets = release.get("assets", [])
        if not isinstance(assets, list):
            return None

        regex = re.compile(pattern)
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            name = asset.get("name", "")
            if isinstance(name, str) and regex.search(name):
                url = asset.get("browser_download_url", "")
                if isinstance(url, str) and url:
                    return ReleaseAsset(url=url, tag=str(tag))

        logger.warning(
            f"在 {repo} 的最新 release (tag={tag}) 中"
            f"未找到匹配 pattern={pattern!r} 的资源"
        )
        return None

    def get_release(self, repo: str) -> dict[str, object] | None:
        """返回 *repo* 最新 GitHub release 的解析后 JSON。"""
        return self._get_release(repo)

    # ------------------------------------------------------------------
    # 内部辅助函数
    # ------------------------------------------------------------------

    def _get_release(self, repo: str) -> dict[str, object] | None:
        """获取 /repos/<repo>/releases/latest，优先使用缓存。"""
        if repo in self._release_cache:
            return self._release_cache[repo]

        url = f"{GITHUB_API_BASE}/repos/{repo}/releases/latest"
        try:
            resp = self._client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning(f"GitHub API 请求失败（{repo}）：{exc}")
            logger.warning(
                "如果此问题频繁出现，请设置 GITHUB_TOKEN 以避免"
                "未认证的 API 速率限制。"
            )
            return None

        data: dict[str, object] = resp.json()
        self._release_cache[repo] = data
        return data

    def close(self) -> None:
        """关闭底层的 HTTP 客户端。"""
        self._client.close()

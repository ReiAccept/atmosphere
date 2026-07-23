"""带按仓库 release 缓存的 GitHub API 客户端。

处理认证/匿名请求、速率限制感知,
并在运行期间按仓库缓存 release JSON。

在 GitHub Actions 中自动使用 secrets.GITHUB_TOKEN 进行认证,
以避免未认证 API 的速率限制（60 次/小时 vs 认证后的 5,000 次/小时）。
"""

from __future__ import annotations

import re
import time
from typing import NamedTuple

import httpx

from src.config import GITHUB_TOKEN, HTTP_USER_AGENT
import logging

logger = logging.getLogger(__name__)

GITHUB_API_BASE: str = "https://api.github.com"

# 速率限制安全阈值 — 低于此值时主动等待
_RATE_LIMIT_SAFE_THRESHOLD: int = 10


class RateLimitError(Exception):
    """GitHub API 速率限制已耗尽时抛出。"""


class ReleaseAsset(NamedTuple):
    """已解析的 release 资源, 包含 URL 和 tag 版本。"""

    url: str
    tag: str


def _parse_rate_limit(resp: httpx.Response) -> dict[str, int]:
    """从响应头中提取速率限制信息。"""
    return {
        "limit": int(resp.headers.get("X-RateLimit-Limit", "0")),
        "remaining": int(resp.headers.get("X-RateLimit-Remaining", "0")),
        "reset": int(resp.headers.get("X-RateLimit-Reset", "0")),
    }


def _log_rate_limit(resp: httpx.Response, repo: str = "") -> None:
    """记录速率限制状态, 用于调试。"""
    rl = _parse_rate_limit(resp)
    prefix = f"[{repo}] " if repo else ""
    logger.debug(
        f"{prefix}速率限制: 剩余 {rl['remaining']}/{rl['limit']}"
        f"（重置时间: {rl['reset']}）"
    )


class GitHubClient:
    """最小化的 GitHub API 客户端, 带内存缓存用于 release 查询。

    支持认证请求（通过 GITHUB_TOKEN 环境变量）,
    当速率限制耗尽时自动等待或抛出明确错误。
    """

    def __init__(self) -> None:
        headers: dict[str, str] = {
            "Accept": "application/vnd.github+json",
            "User-Agent": HTTP_USER_AGENT,
        }
        if GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
            logger.info("已配置 GitHub API 认证（使用 GITHUB_TOKEN）")
        else:
            logger.warning(
                "未设置 GITHUB_TOKEN — 将使用未认证的 API 请求"
                "（限制为 60 次/小时）。"
                "在 GitHub Actions 中运行时, 请在 workflow 中设置"
                " GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}。"
            )

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
        browser_download_url 和 tag, 未找到则返回 *None*。"""
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
        """获取 /repos/<repo>/releases/latest, 优先使用缓存。

        遇到速率限制时, 根据 X-RateLimit-Reset 自动等待,
        或在等待时间过长时抛出 RateLimitError。
        """
        if repo in self._release_cache:
            return self._release_cache[repo]

        url = f"{GITHUB_API_BASE}/repos/{repo}/releases/latest"

        for attempt in range(3):
            try:
                resp = self._client.get(url)
            except httpx.HTTPError as exc:
                logger.warning(f"GitHub API 请求失败（{repo}）: {exc}")
                return None

            _log_rate_limit(resp, repo)

            # 速率限制已耗尽 — 根据 Retry-After 或 X-RateLimit-Reset 等待
            if resp.status_code in (403, 429):
                rl = _parse_rate_limit(resp)
                remaining = rl["remaining"]

                if resp.status_code == 429 or (resp.status_code == 403 and remaining == 0):
                    retry_after = _get_retry_after(resp, rl)
                    if retry_after > 0 and retry_after <= 300:
                        logger.warning(
                            f"GitHub API 速率限制已耗尽（{repo}）,"
                            f"等待 {retry_after} 秒后重试……"
                        )
                        time.sleep(retry_after)
                        continue
                    else:
                        raise RateLimitError(
                            f"GitHub API 速率限制已耗尽（{repo}）,"
                            f"重置时间较长（{retry_after} 秒）。"
                            "请在 GitHub Actions workflow 中设置"
                            " GITHUB_TOKEN 环境变量以使用认证请求。"
                        )

                # 其他 403 错误（非速率限制）
                try:
                    body = resp.json()
                    msg = body.get("message", "") if isinstance(body, dict) else ""
                except Exception:
                    msg = ""
                logger.error(f"GitHub API 返回 403（{repo}）: {msg}")
                return None

            # 成功 — 检查剩余次数是否偏低
            rl = _parse_rate_limit(resp)
            if rl["remaining"] <= _RATE_LIMIT_SAFE_THRESHOLD and rl["remaining"] > 0:
                wait = max(rl["reset"] - int(time.time()), 0)
                if 0 < wait <= 300:
                    logger.info(
                        f"速率限制剩余次数偏低（{rl['remaining']}/{rl['limit']}）,"
                        f"等待 {wait} 秒至重置……"
                    )
                    time.sleep(wait)
                else:
                    logger.warning(
                        f"速率限制剩余次数偏低（{rl['remaining']}/{rl['limit']}）,"
                        "但重置时间过久, 继续运行……"
                    )

            try:
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning(f"GitHub API 请求失败（{repo}）: {exc}")
                return None

            data: dict[str, object] = resp.json()
            self._release_cache[repo] = data
            return data

        # 所有重试均已耗尽
        logger.error(f"GitHub API 速率限制重试已耗尽（{repo}）")
        return None

    def close(self) -> None:
        """关闭底层的 HTTP 客户端。"""
        self._client.close()


def _get_retry_after(resp: httpx.Response, rl: dict[str, int]) -> int:
    """从响应头或速率限制数据中计算等待秒数。"""
    # 优先使用 Retry-After 头
    retry_after = resp.headers.get("Retry-After")
    if retry_after is not None:
        try:
            return int(retry_after)
        except ValueError:
            pass

    # 其次根据 X-RateLimit-Reset 计算
    reset_ts = rl.get("reset", 0)
    if reset_ts > 0:
        wait = reset_ts - int(time.time()) + 1  # +1 秒安全余量
        if wait > 0:
            return wait

    return 60  # 默认等待 60 秒

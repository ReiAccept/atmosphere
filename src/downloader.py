"""带重试和进度跟踪的并行下载管理器。

使用 asyncio + httpx 并发下载多个文件，
遵守可配置的最大并行数。每个下载拥有多次重试机会，
并通过临时文件暂存，确保部分下载不会被误认为已完成。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_fixed,
)

from src.config import (
    DOWNLOAD_MAX_RETRIES,
    DOWNLOAD_RETRY_DELAY,
    DOWNLOAD_TIMEOUT,
    DOWNLOAD_TMP_SUFFIX,
    HTTP_USER_AGENT,
    MAX_PARALLEL_DOWNLOADS,
)
import logging

logger = logging.getLogger(__name__)


@dataclass
class DownloadJob:
    """单个排队下载的元数据。"""

    key: str
    url: str
    dest: Path
    description: str
    status: str = "pending"  # pending | ok | fail


@dataclass
class DownloadManager:
    """管理有界并行下载队列。

    用法::

        mgr = DownloadManager()
        mgr.enqueue("atmo", url, path, "Atmosphere")
        mgr.enqueue("hekate", url2, path2, "Hekate")
        results = await mgr.wait_all()
        # results 将 key 映射到 DownloadJob（状态为 "ok" 或 "fail"）
    """

    _sem: asyncio.Semaphore = field(default_factory=lambda: asyncio.Semaphore(MAX_PARALLEL_DOWNLOADS))
    _jobs: dict[str, DownloadJob] = field(default_factory=dict)
    _tasks: list[asyncio.Task[None]] = field(default_factory=list)
    _failed_items: list[str] = field(default_factory=list)

    def enqueue(
        self,
        key: str,
        url: str,
        dest: Path,
        description: str,
    ) -> None:
        """安排一个下载任务，在调用 *wait_all* 之前不会开始。"""
        job = DownloadJob(key=key, url=url, dest=dest, description=description)
        self._jobs[key] = job
        self._tasks.append(asyncio.create_task(self._run_one(job)))

    # --------------------------------------------------------------
    # 等待
    # --------------------------------------------------------------

    async def wait_all(self) -> dict[str, DownloadJob]:
        """等待所有排队的下载完成，返回最终状态映射。"""
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
            self._tasks.clear()
        return dict(self._jobs)

    @property
    def failed_items(self) -> list[str]:
        """返回失败下载的描述列表。"""
        return [j.description for j in self._jobs.values() if j.status == "fail"]

    # --------------------------------------------------------------
    # 内部方法
    # --------------------------------------------------------------

    async def _run_one(self, job: DownloadJob) -> None:
        async with self._sem:
            try:
                await self._download(job)
                job.status = "ok"
                logger.info(f"{job.description} 下载完毕")
            except Exception:
                job.status = "fail"
                logger.error(f"{job.description} 下载失败")

    @retry(
        stop=stop_after_attempt(DOWNLOAD_MAX_RETRIES),
        wait=wait_fixed(DOWNLOAD_RETRY_DELAY),
        retry=retry_if_exception_type((httpx.HTTPError, OSError)),
        before_sleep=lambda retry_state: logger.info(
            f"正在重试下载（第 {retry_state.attempt_number + 1}/"
            f"{DOWNLOAD_MAX_RETRIES} 次）……"
        ),
    )
    async def _download(self, job: DownloadJob) -> None:
        """通过临时文件（暂存）将 *url* 下载到 *dest*。"""
        tmp = job.dest.with_suffix(job.dest.suffix + DOWNLOAD_TMP_SUFFIX)
        tmp.parent.mkdir(parents=True, exist_ok=True)

        # 如果存在残留的临时文件则删除
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass

        async with httpx.AsyncClient(
            headers={"User-Agent": HTTP_USER_AGENT},
            timeout=DOWNLOAD_TIMEOUT,
            follow_redirects=True,
        ) as client:
            async with client.stream("GET", job.url) as resp:
                resp.raise_for_status()
                with tmp.open("wb") as fh:
                    async for chunk in resp.aiter_bytes(chunk_size=65536):
                        fh.write(chunk)
        # 原子性地重命名到目标位置
        tmp.rename(job.dest)

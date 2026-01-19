# ---- Standard library imports ----
from __future__ import annotations

import asyncio
import inspect
import random
import time
import traceback
from dataclasses import dataclass
from typing import Any, Callable, Iterable
import psutil

# ---- Package imports ----
from pysft.core import constants as const
from pysft.core.enums import E_FetchType
from pysft.core.fetch_task import fetchTask
from pysft.core.structures import outputCls
from pysft.core.models import indicatorRequest
import pysft.core.utilities as utils

# ---------------------------
# Result structures
# ---------------------------

@dataclass(slots=True)
class TaskEnvelope:
    task: fetchTask
    est_mem_bytes: int
    timeout_s: float
    retries: int
    backoff_base_s: float


@dataclass(slots=True)
class TaskSuccess:
    task: fetchTask
    result: Any
    started_at: float
    ended_at: float

    @property
    def duration_s(self) -> float:
        return self.ended_at - self.started_at


@dataclass(slots=True)
class TaskFailure:
    task: fetchTask
    fetch_type: E_FetchType
    attempt: int
    exception: BaseException
    tb: str
    started_at: float
    ended_at: float

    @property
    def duration_s(self) -> float:
        return self.ended_at - self.started_at


# ---------------------------
# Resource gates
# ---------------------------

class MemoryBudget:
    """A token-based RAM budget.

    This avoids oscillations and overfitting to live RSS measurements.
    Each task declares an *estimate* (in bytes). The scheduler guarantees
    the sum of inflight estimates does not exceed the configured budget.
    """

    def __init__(self, max_bytes: int):
        self.max_bytes = max(0, int(max_bytes))
        self._used_bytes = 0
        self._cond = asyncio.Condition()

    @property
    def used_bytes(self) -> int:
        return self._used_bytes

    @property
    def free_bytes(self) -> int:
        return max(0, self.max_bytes - self._used_bytes)

    async def acquire(self, amount_bytes: int) -> None:
        amount_bytes = max(0, int(amount_bytes))
        if amount_bytes == 0:
            return
        async with self._cond:
            while self._used_bytes + amount_bytes > self.max_bytes:
                await self._cond.wait()
            self._used_bytes += amount_bytes

    async def release(self, amount_bytes: int) -> None:
        amount_bytes = max(0, int(amount_bytes))
        if amount_bytes == 0:
            return
        async with self._cond:
            self._used_bytes = max(0, self._used_bytes - amount_bytes)
            self._cond.notify_all()


class _SemaphoreCM:
    def __init__(self, sem: asyncio.Semaphore):
        self._sem = sem

    async def __aenter__(self):
        await self._sem.acquire()

    async def __aexit__(self, exc_type, exc, tb):
        self._sem.release()
        return False


# ---------------------------
# Scheduler
# ---------------------------

class taskScheduler:
    """Task scheduler for managing and executing fetch tasks."""

    def __init__(
        self,
        taskList: list[fetchTask],
        *,
        # Per-fetch-type concurrency limits (defaults from constants)
        concurrency_by_type: dict[E_FetchType, int] | None = None,
        # Total RAM budget for inflight tasks (defaults to INSTANCE_MAX_MEMORY)
        mem_budget_bytes: int | None = None,
        # Default per-task memory estimates
        default_task_mem_bytes: dict[E_FetchType, int] | None = None,
        # Optional CPU soft-guard (system CPU percent). None disables.
        cpu_guard_percent: float | None = None,
        cpu_poll_s: float = 0.20,
        # Timeouts / retries defaults
        default_timeout_s: float = 180.0,
        default_retries: int = const.MAX_ATTEMPTS,
        backoff_base_s: float = 0.75,
        # Worker count (defaults to sum of per-type limits)
        global_max_workers: int | None = None,
        # Optional callbacks
        on_success: Callable[[TaskSuccess], None] | None = None,
        on_failure: Callable[[TaskFailure], None] | None = None,
    ):
        self._queue: asyncio.Queue[TaskEnvelope | None] = asyncio.Queue()

        if concurrency_by_type is None:
            concurrency_by_type = {
                E_FetchType.YFINANCE: int(const.YF_K_SEMAPHORES),
                E_FetchType.TASE: int(const.TASE_K_SEMAPHORES),
            }

        self.semaphores: dict[E_FetchType, asyncio.Semaphore] = {
            ft: asyncio.Semaphore(max(1, int(k))) for ft, k in concurrency_by_type.items()
        }

        if mem_budget_bytes is None:
            mem_budget_bytes = int(getattr(const, "INSTANCE_MAX_MEMORY", const.ONE_GB))

        self._mem_budget = MemoryBudget(int(mem_budget_bytes))

        if default_task_mem_bytes is None:
            # Keep within your declared max allocation if present.
            max_task = int(getattr(const, "MAX_TASK_MEMORY_ALLOCATION", 200 * const.ONE_MB))
            default_task_mem_bytes = {
                E_FetchType.YFINANCE: min(max_task, 200 * const.ONE_MB),
                E_FetchType.TASE: min(max_task, 500 * const.ONE_MB),
            }

        self._default_task_mem_bytes = default_task_mem_bytes
        self._default_timeout_s = float(default_timeout_s)
        self._default_retries = max(0, int(default_retries))
        self._backoff_base_s = float(backoff_base_s)

        if global_max_workers is None:
            global_max_workers = max(1, sum(concurrency_by_type.values()))
        self._global_max_workers = int(global_max_workers)

        self._cpu_guard_percent = float(cpu_guard_percent) if cpu_guard_percent is not None else None
        self._cpu_poll_s = float(cpu_poll_s)
        if self._cpu_guard_percent is not None and psutil is not None:
            try:
                psutil.cpu_percent(interval=None)  # prime measurement
            except Exception:
                pass

        self._on_success = on_success
        self._on_failure = on_failure

        self._results: list[TaskSuccess] = []
        self._failures: list[TaskFailure] = []
        self._list_lock = asyncio.Lock()

        self._workers: list[asyncio.Task[None]] = []
        self._started = False

        self.initialize_queue(taskList)

    # ---------------------------
    # Public API
    # ---------------------------

    @property
    def results(self) -> list[TaskSuccess]:
        return list(self._results)

    @property
    def failures(self) -> list[TaskFailure]:
        return list(self._failures)

    @property
    def mem_budget_bytes(self) -> int:
        return self._mem_budget.max_bytes

    @property
    def mem_used_bytes(self) -> int:
        return self._mem_budget.used_bytes

    def initialize_queue(self, taskList: list[fetchTask]) -> None:
        """Queue task objects for later execution.

        IMPORTANT:
        - We do NOT call asyncio.create_task() here.
        - We only enqueue TaskEnvelope objects.
        """
        for t in taskList:
            est = int(self._default_task_mem_bytes.get(t.fetch_type, 64 * const.ONE_MB))
            env = TaskEnvelope(
                task=t,
                est_mem_bytes=est,
                timeout_s=self._default_timeout_s,
                retries=self._default_retries,
                backoff_base_s=self._backoff_base_s,
            )
            self._queue.put_nowait(env)

    def submit(
        self,
        task: fetchTask,
        *,
        est_mem_bytes: int | None = None,
        timeout_s: float | None = None,
        retries: int | None = None,
        backoff_base_s: float | None = None,
    ) -> None:
        """Submit an additional task before run_async()."""
        env = TaskEnvelope(
            task=task,
            est_mem_bytes=int(est_mem_bytes) if est_mem_bytes is not None else int(self._default_task_mem_bytes.get(task.fetch_type, 64 * const.ONE_MB)),
            timeout_s=float(timeout_s) if timeout_s is not None else self._default_timeout_s,
            retries=int(retries) if retries is not None else self._default_retries,
            backoff_base_s=float(backoff_base_s) if backoff_base_s is not None else self._backoff_base_s,
        )
        self._queue.put_nowait(env)

    def submit_many(self, tasks: Iterable[fetchTask], **kwargs) -> None:
        for t in tasks:
            self.submit(t, **kwargs)

    async def run_async(self) -> tuple[list[TaskSuccess], list[TaskFailure]]:
        """Run until all queued tasks reach a conclusion."""
        if not self._started:
            self._start_workers()

        await self._queue.join()

        # Stop workers
        for _ in range(len(self._workers)):
            self._queue.put_nowait(None)
        await asyncio.gather(*self._workers, return_exceptions=False)

        return list(self._results), list(self._failures)

    def run(self) -> tuple[list[TaskSuccess], list[TaskFailure]]:
        """Convenience wrapper for non-async callers."""
        return asyncio.run(self.run_async())

    # ---------------------------
    # Internal
    # ---------------------------

    def _start_workers(self) -> None:
        self._workers = [
            asyncio.create_task(self._worker(i), name=f"pysft-task-worker-{i}")
            for i in range(self._global_max_workers)
        ]
        self._started = True

    async def _wait_for_cpu_headroom(self) -> None:
        if self._cpu_guard_percent is None:
            return
        while True:
            try:
                cpu_now = psutil.cpu_percent(interval=0.0)
            except Exception:
                return
            if cpu_now < self._cpu_guard_percent:
                return
            await asyncio.sleep(self._cpu_poll_s)

    async def _worker(self, worker_id: int) -> None:
        while True:
            env = await self._queue.get()
            if env is None:
                self._queue.task_done()
                return

            task = env.task
            ft = task.fetch_type

            sem = self.semaphores.get(ft)
            if sem is None:
                # Unknown type -> fail fast (still mark queue task done)
                started = time.monotonic()
                ended = started
                failure = TaskFailure(
                    task=task,
                    fetch_type=ft,
                    attempt=1,
                    exception=ValueError(f"Unsupported fetch type: {ft}"),
                    tb="",
                    started_at=started,
                    ended_at=ended,
                )
                async with self._list_lock:
                    self._failures.append(failure)
                if self._on_failure:
                    self._on_failure(failure)
                self._queue.task_done()
                continue

            async with _SemaphoreCM(sem):
                await self._mem_budget.acquire(env.est_mem_bytes)
                started = time.monotonic()
                try:
                    await self._wait_for_cpu_headroom()
                    result = await self._run_with_retries(env)
                    ended = time.monotonic()
                    success = TaskSuccess(task=task, result=result, started_at=started, ended_at=ended)
                    async with self._list_lock:
                        self._results.append(success)
                    if self._on_success:
                        self._on_success(success)
                except asyncio.CancelledError:
                    raise
                except BaseException as e:
                    ended = time.monotonic()
                    failure = TaskFailure(
                        task=task,
                        fetch_type=ft,
                        attempt=int(getattr(e, "_pysft_attempts", env.retries + 1)),
                        exception=e,
                        tb=traceback.format_exc(),
                        started_at=started,
                        ended_at=ended,
                    )
                    async with self._list_lock:
                        self._failures.append(failure)
                    if self._on_failure:
                        self._on_failure(failure)
                finally:
                    await self._mem_budget.release(env.est_mem_bytes)
                    self._queue.task_done()

    async def _run_with_retries(self, env: TaskEnvelope) -> Any:
        last_exc: BaseException | None = None
        for attempt in range(env.retries + 1):
            try:
                return await asyncio.wait_for(self._invoke_task(env.task), timeout=env.timeout_s)
            except asyncio.TimeoutError as e:
                last_exc = e
            except BaseException as e:
                last_exc = e

            if attempt < env.retries:
                base = env.backoff_base_s * (2 ** attempt)
                jitter = random.uniform(0.0, 0.25 * base)
                await asyncio.sleep(base + jitter)

        assert last_exc is not None
        try:
            setattr(last_exc, "_pysft_attempts", env.retries + 1)
        except Exception:
            pass
        raise last_exc

    async def _invoke_task(self, task: fetchTask) -> Any:
        """Invoke a task using the best available interface.

        Preference order:
        1) await task.run() (if implemented)
        2) await task.execute_async()
        3) run task.execute() in a background thread
        """
        run_maybe = getattr(task, "run", None)
        if callable(run_maybe):
            out = run_maybe()
            if inspect.isawaitable(out):
                return await out
            return out

        exa = getattr(task, "execute_async", None)
        if callable(exa):
            out = exa()
            if inspect.isawaitable(out):
                return await out
            return out

        exe = getattr(task, "execute", None)
        if not callable(exe):
            raise ValueError("Task has no run(), execute_async(), or execute()")

        await asyncio.to_thread(exe)
        get_results = getattr(task, "get_results", None)
        if callable(get_results):
            return get_results()
        return None

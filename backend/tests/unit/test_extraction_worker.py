from __future__ import annotations

import asyncio
import threading
import time
import uuid

from app.extraction.worker import ExtractionJobWorker


def test_worker_respects_concurrency_and_continues_after_an_independent_failure() -> None:
    class TrackingWorker(ExtractionJobWorker):
        def __init__(self) -> None:
            super().__init__(
                session_factory=lambda: None,  # type: ignore[arg-type]
                storage=None,  # type: ignore[arg-type]
                extractor=None,  # type: ignore[arg-type]
                concurrency=2,
                max_attempts=1,
                timeout_seconds=1,
                retry_backoff_seconds=0,
                poll_interval_seconds=0.005,
            )
            self.lock = threading.Lock()
            self.next_job = 0
            self.running = 0
            self.maximum = 0
            self.finished: list[int] = []

        def _fail_stale_runs(self) -> None:
            return

        def _claim_next(self) -> uuid.UUID | None:
            with self.lock:
                if self.next_job == 4:
                    return None
                self.next_job += 1
                return uuid.UUID(int=self.next_job)

        def _process_run(self, run_id: uuid.UUID) -> None:
            number = run_id.int
            with self.lock:
                self.running += 1
                self.maximum = max(self.maximum, self.running)
            time.sleep(0.02)
            with self.lock:
                self.running -= 1
                self.finished.append(number)
            if number == 2:
                raise RuntimeError("synthetic failure")

    async def run_worker(worker: TrackingWorker) -> None:
        stop = asyncio.Event()
        task = asyncio.create_task(worker.run(stop))
        await asyncio.sleep(0.15)
        stop.set()
        await task

    worker = TrackingWorker()
    asyncio.run(run_worker(worker))
    assert worker.maximum == 2
    assert sorted(worker.finished) == [1, 2, 3, 4]

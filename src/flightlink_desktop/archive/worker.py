"""Background serialized archive sync worker running independently of UI page navigation and live-update pause."""

from __future__ import annotations

import queue
import threading
from typing import Any

from PySide6.QtCore import QObject, Qt, Signal, Slot

from flightlink_desktop.api.errors import ApiError, NetworkError, SessionInvalidatedError
from flightlink_desktop.archive.sync_engine import ArchiveSyncEngine


class ArchiveSyncWorker(QObject):
    """Owns a single serialized worker thread sharing one queue for auto-sync and manual retry.

    - Starts immediately on login (`onSessionStarted`), independent of opening History page.
    - Never paused by UI "pause scroll" or "pause live updates".
    - Cancels in-flight streams cleanly on logout, server switch, or app shutdown.
    - Emits UI snapshots strictly via Qt.QueuedConnection to GUI thread.
    """

    snapshotReady = Signal(int, dict)  # epoch, snapshot_dict
    retryFinished = Signal(int, str, bool, str)  # epoch, session_id, ok, message

    def __init__(
        self,
        engine: ArchiveSyncEngine,
        *,
        poll_interval_seconds: float = 15.0,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.engine = engine
        self._poll_interval = max(1.0, float(poll_interval_seconds))
        self._queue: queue.Queue[tuple[str, dict[str, Any]]] = queue.Queue()
        self._stop_thread = threading.Event()
        self._cancel_current = threading.Event()
        self._state_lock = threading.Lock()
        self._active_epoch: int = 0
        self._active_ecs_id: str = ""
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_thread.clear()
        self._thread = threading.Thread(target=self._run_loop, name="FlightLinkArchiveWorker", daemon=True)
        self._thread.start()

    def shutdown(self, timeout_s: float = 3.0) -> None:
        self._stop_thread.set()
        self._cancel_current.set()
        self._queue.put(("shutdown", {}))
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout_s)

    @Slot(int, str, str)
    def onSessionStarted(self, epoch: int, ecs_instance_id: str, server_url: str) -> None:
        with self._state_lock:
            self._active_epoch = epoch
            self._active_ecs_id = ecs_instance_id
        self._cancel_current.clear()
        self.start()
        # Trigger immediate sync upon login (never waits for History page!)
        self._queue.put(("sync", {"epoch": epoch, "ecs_instance_id": ecs_instance_id}))

    @Slot(int, str)
    def onSessionEnded(self, new_epoch: int, reason: str) -> None:
        with self._state_lock:
            self._active_epoch = new_epoch
            self._active_ecs_id = ""
        # Cancel any in-flight file stream immediately so old server never writes to disk
        self._cancel_current.set()
        # Drain queued work for previous session
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    @Slot(str)
    def enqueueManualRetry(self, session_id: str) -> None:
        with self._state_lock:
            epoch = self._active_epoch
            ecs_id = self._active_ecs_id
        if not ecs_id or not session_id:
            return
        self._queue.put(("retry", {"epoch": epoch, "ecs_instance_id": ecs_id, "session_id": session_id}))

    def _run_loop(self) -> None:
        while not self._stop_thread.is_set():
            try:
                cmd, payload = self._queue.get(timeout=self._poll_interval)
            except queue.Empty:
                with self._state_lock:
                    epoch = self._active_epoch
                    ecs_id = self._active_ecs_id
                if not ecs_id:
                    continue
                cmd = "sync"
                payload = {"epoch": epoch, "ecs_instance_id": ecs_id}

            if cmd == "shutdown" or self._stop_thread.is_set():
                break

            req_epoch = int(payload.get("epoch", 0))
            req_ecs_id = str(payload.get("ecs_instance_id", ""))
            with self._state_lock:
                if req_epoch != self._active_epoch or req_ecs_id != self._active_ecs_id or not req_ecs_id:
                    continue

            if cmd == "sync":
                try:
                    self.engine.sync_once(
                        ecs_instance_id=req_ecs_id,
                        expected_epoch=req_epoch,
                        cancel_event=self._cancel_current,
                    )
                except (SessionInvalidatedError, NetworkError, ApiError):
                    pass
                except Exception:
                    pass
                self._emit_snapshot_if_current(req_epoch, req_ecs_id)
            elif cmd == "retry":
                sid = str(payload.get("session_id", ""))
                ok = False
                msg = ""
                try:
                    res = self.engine.retry_session(
                        ecs_instance_id=req_ecs_id,
                        session_id=sid,
                        expected_epoch=req_epoch,
                        cancel_event=self._cancel_current,
                    )
                    st = self.engine.get_session_state(req_ecs_id, sid)
                    ok = res.files_failed == 0 and st is not None and st["local_status"] in ("saved", "saved_with_source_gaps")
                    msg = "补下载完成" if ok else (str(st["last_error_message"]) if st and st.get("last_error_message") else "补下载未完成")
                except (SessionInvalidatedError, NetworkError, ApiError) as exc:
                    msg = str(exc)
                self._emit_snapshot_if_current(req_epoch, req_ecs_id)
                with self._state_lock:
                    if req_epoch == self._active_epoch:
                        self.retryFinished.emit(req_epoch, sid, ok, msg)

    def _emit_snapshot_if_current(self, epoch: int, ecs_instance_id: str) -> None:
        with self._state_lock:
            if epoch != self._active_epoch or ecs_instance_id != self._active_ecs_id:
                return
        snap = self.engine.get_instance_snapshot(ecs_instance_id)
        self.snapshotReady.emit(epoch, snap)

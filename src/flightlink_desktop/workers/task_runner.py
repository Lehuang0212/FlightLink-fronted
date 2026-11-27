"""Background task runner executing blocking I/O off the Qt GUI thread."""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal


class _WorkerSignals(QObject):
    finished = Signal(object, object)  # (result, error)


class _FunctionRunnable(QRunnable):
    def __init__(self, fn: Callable[[], Any]) -> None:
        super().__init__()
        self.setAutoDelete(True)
        self._fn = fn
        self.signals = _WorkerSignals()

    def run(self) -> None:
        try:
            result = self._fn()
        except Exception as exc:
            self.signals.finished.emit(None, exc)
        else:
            self.signals.finished.emit(result, None)


class BackgroundTaskRunner(QObject):
    """Runs background callables on QThreadPool and delivers results on GUI thread via QueuedConnection."""

    def __init__(self, parent: QObject | None = None, *, max_threads: int = 6) -> None:
        super().__init__(parent)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(max(2, max_threads))
        self._active_signals: set[_WorkerSignals] = set()

    def submit(
        self,
        fn: Callable[[], Any],
        on_done: Callable[[Any, Exception | None], None],
    ) -> None:
        runnable = _FunctionRunnable(fn)
        sig = runnable.signals
        self._active_signals.add(sig)

        def _dispatch(result: Any, err: Any) -> None:
            self._active_signals.discard(sig)
            on_done(result, err)

        sig.finished.connect(_dispatch, Qt.ConnectionType.QueuedConnection)
        self._pool.start(runnable)

    def shutdown(self, timeout_ms: int = 3000) -> None:
        self._pool.clear()
        self._pool.waitForDone(timeout_ms)

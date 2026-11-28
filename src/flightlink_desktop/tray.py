"""Native Windows system tray (notification area) controller using Win32 Shell_NotifyIconW.

Implemented directly via Win32 ctypes to stay strictly within the
QGuiApplication + Qt Quick/QML architecture constraint.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os
import sys
import threading
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Property, QObject, Qt, Signal, Slot

# Win32 constants
WM_NULL = 0x0000
WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_APP = 0x8000
WM_TRAYICON = WM_APP + 1

WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
WM_CONTEXTMENU = 0x007B

NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002

NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
NIF_INFO = 0x00000010
NIIF_INFO = 0x00000001

IMAGE_ICON = 1
LR_LOADFROMFILE = 0x00000010
LR_DEFAULTSIZE = 0x00000040
IDI_APPLICATION = 32512

MF_STRING = 0x00000000
MF_SEPARATOR = 0x00000800
TPM_RIGHTBUTTON = 0x0002
TPM_BOTTOMALIGN = 0x0020
TPM_NONOTIFY = 0x0080
TPM_RETURNCMD = 0x0100

MENU_ID_RESTORE = 1001
MENU_ID_QUIT = 1002

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wt.DWORD),
        ("Data2", wt.WORD),
        ("Data3", wt.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class _WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wt.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wt.HINSTANCE),
        ("hIcon", wt.HICON),
        ("hCursor", wt.HANDLE),
        ("hbrBackground", wt.HBRUSH),
        ("lpszMenuName", wt.LPCWSTR),
        ("lpszClassName", wt.LPCWSTR),
    ]


class _NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.DWORD),
        ("hWnd", wt.HWND),
        ("uID", wt.UINT),
        ("uFlags", wt.UINT),
        ("uCallbackMessage", wt.UINT),
        ("hIcon", wt.HICON),
        ("szTip", wt.WCHAR * 128),
        ("dwState", wt.DWORD),
        ("dwStateMask", wt.DWORD),
        ("szInfo", wt.WCHAR * 256),
        ("uVersion", wt.UINT),
        ("szInfoTitle", wt.WCHAR * 64),
        ("dwInfoFlags", wt.DWORD),
        ("guidItem", _GUID),
        ("hBalloonIcon", wt.HICON),
    ]


def _configure_win32_apis() -> tuple[ctypes.WinDLL, ctypes.WinDLL, ctypes.WinDLL]:
    user32 = ctypes.windll.user32
    shell32 = ctypes.windll.shell32
    kernel32 = ctypes.windll.kernel32

    kernel32.GetModuleHandleW.argtypes = [wt.LPCWSTR]
    kernel32.GetModuleHandleW.restype = wt.HMODULE

    user32.RegisterClassW.argtypes = [ctypes.POINTER(_WNDCLASSW)]
    user32.RegisterClassW.restype = wt.ATOM

    user32.CreateWindowExW.argtypes = [
        wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wt.HWND, wt.HMENU, wt.HINSTANCE, wt.LPVOID,
    ]
    user32.CreateWindowExW.restype = wt.HWND

    user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
    user32.DefWindowProcW.restype = LRESULT

    user32.DestroyWindow.argtypes = [wt.HWND]
    user32.DestroyWindow.restype = wt.BOOL

    user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
    user32.PostMessageW.restype = wt.BOOL

    user32.PostQuitMessage.argtypes = [ctypes.c_int]
    user32.PostQuitMessage.restype = None

    user32.GetMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT]
    user32.GetMessageW.restype = wt.BOOL

    user32.TranslateMessage.argtypes = [ctypes.POINTER(wt.MSG)]
    user32.TranslateMessage.restype = wt.BOOL

    user32.DispatchMessageW.argtypes = [ctypes.POINTER(wt.MSG)]
    user32.DispatchMessageW.restype = LRESULT

    user32.RegisterWindowMessageW.argtypes = [wt.LPCWSTR]
    user32.RegisterWindowMessageW.restype = wt.UINT

    user32.LoadImageW.argtypes = [wt.HINSTANCE, wt.LPCWSTR, wt.UINT, ctypes.c_int, ctypes.c_int, wt.UINT]
    user32.LoadImageW.restype = wt.HANDLE

    user32.LoadIconW.argtypes = [wt.HINSTANCE, wt.LPCWSTR]
    user32.LoadIconW.restype = wt.HICON

    user32.DestroyIcon.argtypes = [wt.HICON]
    user32.DestroyIcon.restype = wt.BOOL

    user32.CreatePopupMenu.argtypes = []
    user32.CreatePopupMenu.restype = wt.HMENU

    user32.AppendMenuW.argtypes = [wt.HMENU, wt.UINT, ctypes.c_size_t, wt.LPCWSTR]
    user32.AppendMenuW.restype = wt.BOOL

    user32.TrackPopupMenu.argtypes = [
        wt.HMENU, wt.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.HWND, wt.LPVOID,
    ]
    user32.TrackPopupMenu.restype = wt.BOOL

    user32.DestroyMenu.argtypes = [wt.HMENU]
    user32.DestroyMenu.restype = wt.BOOL

    user32.GetCursorPos.argtypes = [ctypes.POINTER(wt.POINT)]
    user32.GetCursorPos.restype = wt.BOOL

    user32.SetForegroundWindow.argtypes = [wt.HWND]
    user32.SetForegroundWindow.restype = wt.BOOL

    shell32.Shell_NotifyIconW.argtypes = [wt.DWORD, ctypes.POINTER(_NOTIFYICONDATAW)]
    shell32.Shell_NotifyIconW.restype = wt.BOOL

    return user32, shell32, kernel32


class _Win32TrayBackend:
    """Dedicated Win32 message-loop thread hosting a single notification-area tray icon."""

    _class_counter = 0

    def __init__(
        self,
        *,
        icon_path: Path | None,
        tooltip: str,
        on_restore: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        self._icon_path = icon_path
        self._tooltip = tooltip[:127]
        self._on_restore = on_restore
        self._on_quit = on_quit

        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._thread: threading.Thread | None = None
        self._hwnd: int = 0
        self._hicon: int = 0
        self._owns_icon: bool = False
        self._icon_added: bool = False
        self._started: bool = False
        self._taskbar_created_msg: int = 0
        self._wndproc_ref: WNDPROC | None = None

    def start(self, *, balloon_title: str = "", balloon_text: str = "") -> bool:
        with self._lock:
            if self._started:
                return self._icon_added
            self._started = True
            self._ready.clear()
            self._thread = threading.Thread(
                target=self._run_loop,
                args=(balloon_title, balloon_text),
                name="FlightLinkWin32Tray",
                daemon=True,
            )
            self._thread.start()
        self._ready.wait(timeout=3.0)
        return self._icon_added

    def show_balloon(self, title: str, text: str) -> None:
        if not self._hwnd or not self._icon_added:
            return
        try:
            _, shell32, _ = _configure_win32_apis()
            nid = self._make_nid(NIF_INFO, balloon_title=title, balloon_text=text)
            shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))
        except Exception:
            pass

    def stop(self) -> None:
        with self._lock:
            hwnd = self._hwnd
            th = self._thread
            self._started = False
        if hwnd:
            try:
                user32, _, _ = _configure_win32_apis()
                user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
            except Exception:
                pass
        if th is not None and th.is_alive() and th is not threading.current_thread():
            th.join(timeout=2.0)

    def _make_nid(
        self,
        flags: int,
        *,
        balloon_title: str = "",
        balloon_text: str = "",
    ) -> _NOTIFYICONDATAW:
        nid = _NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(_NOTIFYICONDATAW)
        nid.hWnd = self._hwnd
        nid.uID = 1
        nid.uFlags = flags
        nid.uCallbackMessage = WM_TRAYICON
        nid.hIcon = self._hicon
        nid.szTip = self._tooltip
        if balloon_text:
            nid.szInfoTitle = balloon_title[:63]
            nid.szInfo = balloon_text[:255]
            nid.dwInfoFlags = NIIF_INFO
        return nid

    def _add_icon(self, shell32: ctypes.WinDLL, *, balloon_title: str = "", balloon_text: str = "") -> bool:
        flags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        if balloon_text:
            flags |= NIF_INFO
        nid = self._make_nid(flags, balloon_title=balloon_title, balloon_text=balloon_text)
        ok = bool(shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid)))
        self._icon_added = ok
        return ok

    def _remove_icon(self, shell32: ctypes.WinDLL) -> None:
        if self._hwnd and self._icon_added:
            nid = self._make_nid(0)
            try:
                shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
            except Exception:
                pass
            self._icon_added = False

    def _show_context_menu(self, user32: ctypes.WinDLL, hwnd: int) -> None:
        hmenu = user32.CreatePopupMenu()
        if not hmenu:
            return
        try:
            user32.AppendMenuW(hmenu, MF_STRING, MENU_ID_RESTORE, "打开主界面")
            user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)
            user32.AppendMenuW(hmenu, MF_STRING, MENU_ID_QUIT, "完全退出")

            pt = wt.POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            user32.SetForegroundWindow(hwnd)
            cmd = int(
                user32.TrackPopupMenu(
                    hmenu,
                    TPM_RIGHTBUTTON | TPM_BOTTOMALIGN | TPM_RETURNCMD | TPM_NONOTIFY,
                    pt.x,
                    pt.y,
                    0,
                    hwnd,
                    None,
                )
            )
            user32.PostMessageW(hwnd, WM_NULL, 0, 0)
            if cmd == MENU_ID_RESTORE:
                self._on_restore()
            elif cmd == MENU_ID_QUIT:
                self._on_quit()
        finally:
            user32.DestroyMenu(hmenu)

    def _run_loop(self, balloon_title: str, balloon_text: str) -> None:
        user32, shell32, kernel32 = _configure_win32_apis()
        hinst = kernel32.GetModuleHandleW(None)
        self._taskbar_created_msg = int(user32.RegisterWindowMessageW("TaskbarCreated"))

        _Win32TrayBackend._class_counter += 1
        class_name = f"FlightLinkTrayWnd_{os.getpid()}_{_Win32TrayBackend._class_counter}"

        def _wndproc(hwnd: int, msg: int, wparam: int, lparam: int) -> int:
            if msg == WM_TRAYICON:
                ev = lparam & 0xFFFF
                if ev in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                    self._on_restore()
                    return 0
                if ev in (WM_RBUTTONUP, WM_CONTEXTMENU):
                    self._show_context_menu(user32, hwnd)
                    return 0
            elif self._taskbar_created_msg and msg == self._taskbar_created_msg:
                self._add_icon(shell32)
                return 0
            elif msg == WM_CLOSE:
                self._remove_icon(shell32)
                user32.DestroyWindow(hwnd)
                return 0
            elif msg == WM_DESTROY:
                self._remove_icon(shell32)
                user32.PostQuitMessage(0)
                return 0
            return int(user32.DefWindowProcW(hwnd, msg, wparam, lparam))

        self._wndproc_ref = WNDPROC(_wndproc)

        wc = _WNDCLASSW()
        wc.lpfnWndProc = self._wndproc_ref
        wc.hInstance = hinst
        wc.lpszClassName = class_name
        user32.RegisterClassW(ctypes.byref(wc))

        hwnd = int(
            user32.CreateWindowExW(
                0,
                class_name,
                "FlightLinkTray",
                0,
                0,
                0,
                0,
                0,
                None,
                None,
                hinst,
                None,
            )
        )
        self._hwnd = hwnd

        # Load custom .ico if present; fallback to system application icon
        hicon = 0
        if self._icon_path is not None and self._icon_path.is_file():
            hicon = int(
                user32.LoadImageW(
                    None,
                    str(self._icon_path),
                    IMAGE_ICON,
                    0,
                    0,
                    LR_LOADFROMFILE | LR_DEFAULTSIZE,
                )
            )
            if hicon:
                self._owns_icon = True
        if not hicon:
            hicon = int(user32.LoadIconW(None, ctypes.cast(IDI_APPLICATION, wt.LPCWSTR)))
            self._owns_icon = False
        self._hicon = hicon

        if hwnd:
            self._add_icon(shell32, balloon_title=balloon_title, balloon_text=balloon_text)
        self._ready.set()

        if not hwnd:
            return

        msg = wt.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        self._remove_icon(shell32)
        if self._owns_icon and self._hicon:
            user32.DestroyIcon(self._hicon)
        self._hwnd = 0
        self._hicon = 0
        self._owns_icon = False


def resolve_app_icon_path() -> Path | None:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        cand = Path(meipass) / "flightlink_desktop" / "assets" / "flightlink.ico"
        if cand.is_file():
            return cand
    cand = Path(__file__).resolve().parent / "assets" / "flightlink.ico"
    return cand if cand.is_file() else None


def bring_window_to_foreground(win_id: int) -> None:
    if sys.platform != "win32" or not win_id:
        return
    try:
        user32 = ctypes.windll.user32
        user32.SetForegroundWindow.argtypes = [wt.HWND]
        user32.SetForegroundWindow.restype = wt.BOOL
        user32.SetForegroundWindow(int(win_id))
    except Exception:
        pass


class TrayController(QObject):
    """GUI-thread QObject bridging QML close actions and the native Windows system tray."""

    inTrayChanged = Signal()
    restoreRequested = Signal()
    quitRequested = Signal()

    _internalRestore = Signal()
    _internalQuit = Signal()

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        icon_path: Path | None = None,
        enable_native_tray: bool | None = None,
    ) -> None:
        super().__init__(parent)
        self._icon_path = icon_path if icon_path is not None else resolve_app_icon_path()
        if enable_native_tray is None:
            qpa = os.environ.get("QT_QPA_PLATFORM", "").strip().lower()
            enable_native_tray = sys.platform == "win32" and qpa != "offscreen"
        self._enable_native_tray = bool(enable_native_tray)
        self._in_tray = False
        self._shown_balloon_once = False
        self._backend: _Win32TrayBackend | None = None

        self._internalRestore.connect(self._on_restore_gui, Qt.ConnectionType.QueuedConnection)
        self._internalQuit.connect(self._on_quit_gui, Qt.ConnectionType.QueuedConnection)

    @Property(bool, notify=inTrayChanged)
    def inTray(self) -> bool:
        return self._in_tray

    @Property(bool, constant=True)
    def traySupported(self) -> bool:
        return self._enable_native_tray

    @Slot()
    def hideToTray(self) -> None:
        """Create/show taskbar tray icon and mark window hidden to background."""
        if self._enable_native_tray:
            if self._backend is None:
                self._backend = _Win32TrayBackend(
                    icon_path=self._icon_path,
                    tooltip="FlightLink Desktop 1.0（点击恢复界面）",
                    on_restore=self._internalRestore.emit,
                    on_quit=self._internalQuit.emit,
                )
                self._backend.start(
                    balloon_title="FlightLink Desktop 已转入后台运行",
                    balloon_text="点击任务栏右下角小图标可随时恢复主界面。",
                )
                self._shown_balloon_once = True
            elif not self._shown_balloon_once:
                self._backend.show_balloon(
                    "FlightLink Desktop 已转入后台运行",
                    "点击任务栏右下角小图标可随时恢复主界面。",
                )
                self._shown_balloon_once = True

        if not self._in_tray:
            self._in_tray = True
            self.inTrayChanged.emit()

    @Slot()
    def restoreFromTray(self) -> None:
        """Restore window from background tray back to foreground."""
        if self._in_tray:
            self._in_tray = False
            self.inTrayChanged.emit()
        self.restoreRequested.emit()

    @Slot()
    def requestQuit(self) -> None:
        """Remove tray icon cleanly and trigger full application exit."""
        self.shutdown()
        self.quitRequested.emit()

    @Slot()
    def _on_restore_gui(self) -> None:
        self.restoreFromTray()

    @Slot()
    def _on_quit_gui(self) -> None:
        self.requestQuit()

    def shutdown(self) -> None:
        if self._in_tray:
            self._in_tray = False
            self.inTrayChanged.emit()
        if self._backend is not None:
            self._backend.stop()
            self._backend = None

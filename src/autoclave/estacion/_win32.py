# autoclave/estacion/_win32.py
#
# Declaraciones ctypes de Win32 de la herramienta de táctiles y del lanzador
# (la cubierta de arranque se retiró en la tanda 18, EST-08). Solo se cargan en Windows y bajo demanda (`api()`):
# importar este módulo en otra plataforma no falla. Todas las funciones llevan
# argtypes/restype explícitos para que los HANDLE/LPARAM de 64 bits no se
# trunquen a int de 32.
#
# Nunca se usa en las pruebas automáticas (prohibido abrir ventanas reales):
# las pruebas inyectan dobles en las capas de arriba.

import ctypes
import functools
import sys
from types import SimpleNamespace

if sys.platform == "win32":
    from ctypes import wintypes

    LRESULT = ctypes.c_ssize_t
    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    MONITORENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
                                         ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)

    class WNDCLASSEXW(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("style", wintypes.UINT), ("lpfnWndProc", WNDPROC),
                    ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                    ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
                    ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                    ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR),
                    ("hIconSm", wintypes.HICON)]

    class MONITORINFOEXW(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD), ("szDevice", wintypes.WCHAR * 32)]

    class DISPLAY_DEVICEW(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("DeviceName", wintypes.WCHAR * 32),
                    ("DeviceString", wintypes.WCHAR * 128), ("StateFlags", wintypes.DWORD),
                    ("DeviceID", wintypes.WCHAR * 128), ("DeviceKey", wintypes.WCHAR * 128)]

    class PAINTSTRUCT(ctypes.Structure):
        _fields_ = [("hdc", wintypes.HDC), ("fErase", wintypes.BOOL), ("rcPaint", wintypes.RECT),
                    ("fRestore", wintypes.BOOL), ("fIncUpdate", wintypes.BOOL),
                    ("rgbReserved", ctypes.c_byte * 32)]

    class RAWINPUTDEVICE(ctypes.Structure):
        _fields_ = [("usUsagePage", wintypes.USHORT), ("usUsage", wintypes.USHORT),
                    ("dwFlags", wintypes.DWORD), ("hwndTarget", wintypes.HWND)]

    class RAWINPUTHEADER(ctypes.Structure):
        _fields_ = [("dwType", wintypes.DWORD), ("dwSize", wintypes.DWORD),
                    ("hDevice", wintypes.HANDLE), ("wParam", wintypes.WPARAM)]

# Constantes
WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
SW_SHOW = 5
SW_SHOWNOACTIVATE = 4
HWND_TOPMOST = -1
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
PM_REMOVE = 0x0001
QS_ALLINPUT = 0x04FF
WAIT_OBJECT_0 = 0
WAIT_TIMEOUT = 0x102
WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_PAINT = 0x000F
WM_ERASEBKGND = 0x0014
WM_SETCURSOR = 0x0020
WM_MOUSEACTIVATE = 0x0021
WM_QUIT = 0x0012
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
WM_INPUT = 0x00FF
WM_APP = 0x8000
MA_NOACTIVATEANDEAT = 4
VK_ESCAPE = 0x1B
VK_RETURN = 0x0D
DT_CENTER = 0x0001
DT_VCENTER = 0x0004
DT_WORDBREAK = 0x0010
DT_TOP = 0x0000
DT_BOTTOM = 0x0008
DT_SINGLELINE = 0x0020
ANTIALIASED_QUALITY = 4
WM_TOUCH = 0x0240
WM_POINTER_PRIMERO = 0x0241   # WM_POINTERDEVICECHANGE .. WM_POINTERHWHEEL
WM_POINTER_ULTIMO = 0x024F
WM_MOUSE_PRIMERO = 0x0200     # WM_MOUSEMOVE .. WM_MOUSEHWHEEL
WM_MOUSE_ULTIMO = 0x020E
TRANSPARENT = 1
BLACK_BRUSH = 4
EVENT_MODIFY_STATE = 0x0002
SYNCHRONIZE = 0x00100000
EDD_GET_DEVICE_INTERFACE_NAME = 0x00000001
DISPLAY_DEVICE_ACTIVE = 0x00000001
RIDEV_INPUTSINK = 0x00000100
RIDEV_REMOVE = 0x00000001
RID_INPUT = 0x10000003
RID_HEADER = 0x10000005
RIDI_DEVICENAME = 0x20000007
RIM_TYPEHID = 2
HID_USAGE_PAGE_DIGITIZER = 0x0D
HID_USAGE_DIGITIZER_TOUCH_SCREEN = 0x04
FW_BOLD = 700
FW_NORMAL = 400


def _firmar(funcion, argtypes, restype):
    funcion.argtypes = argtypes
    funcion.restype = restype
    return funcion


@functools.cache
def api():
    """Funciones de user32/gdi32/kernel32/shell32 con su firma. Solo Windows;
    en otra plataforma lanza OSError (los llamadores lo atrapan)."""
    if sys.platform != "win32":
        raise OSError("Win32 solo existe en Windows")
    w = wintypes
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    a = SimpleNamespace()
    a.GetModuleHandleW = _firmar(kernel32.GetModuleHandleW, (w.LPCWSTR,), w.HMODULE)
    a.GetCurrentThreadId = _firmar(kernel32.GetCurrentThreadId, (), w.DWORD)
    a.CreateEventW = _firmar(kernel32.CreateEventW, (w.LPVOID, w.BOOL, w.BOOL, w.LPCWSTR), w.HANDLE)
    a.OpenEventW = _firmar(kernel32.OpenEventW, (w.DWORD, w.BOOL, w.LPCWSTR), w.HANDLE)
    a.SetEvent = _firmar(kernel32.SetEvent, (w.HANDLE,), w.BOOL)
    a.ResetEvent = _firmar(kernel32.ResetEvent, (w.HANDLE,), w.BOOL)
    a.CloseHandle = _firmar(kernel32.CloseHandle, (w.HANDLE,), w.BOOL)
    a.WaitForSingleObject = _firmar(kernel32.WaitForSingleObject, (w.HANDLE, w.DWORD), w.DWORD)
    a.MsgWaitForMultipleObjects = _firmar(user32.MsgWaitForMultipleObjects,
                                          (w.DWORD, ctypes.POINTER(w.HANDLE), w.BOOL, w.DWORD, w.DWORD),
                                          w.DWORD)
    a.RegisterClassExW = _firmar(user32.RegisterClassExW, (ctypes.POINTER(WNDCLASSEXW),), w.ATOM)
    a.UnregisterClassW = _firmar(user32.UnregisterClassW, (w.LPCWSTR, w.HINSTANCE), w.BOOL)
    a.CreateWindowExW = _firmar(user32.CreateWindowExW,
                                (w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD, ctypes.c_int, ctypes.c_int,
                                 ctypes.c_int, ctypes.c_int, w.HWND, w.HMENU, w.HINSTANCE, w.LPVOID),
                                w.HWND)
    a.DestroyWindow = _firmar(user32.DestroyWindow, (w.HWND,), w.BOOL)
    a.IsWindow = _firmar(user32.IsWindow, (w.HWND,), w.BOOL)
    a.DefWindowProcW = _firmar(user32.DefWindowProcW, (w.HWND, w.UINT, w.WPARAM, w.LPARAM), LRESULT)
    a.ShowWindow = _firmar(user32.ShowWindow, (w.HWND, ctypes.c_int), w.BOOL)
    a.UpdateWindow = _firmar(user32.UpdateWindow, (w.HWND,), w.BOOL)
    a.InvalidateRect = _firmar(user32.InvalidateRect, (w.HWND, ctypes.POINTER(w.RECT), w.BOOL), w.BOOL)
    a.SetWindowPos = _firmar(user32.SetWindowPos,
                             (w.HWND, w.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.UINT),
                             w.BOOL)
    a.SetForegroundWindow = _firmar(user32.SetForegroundWindow, (w.HWND,), w.BOOL)
    a.PeekMessageW = _firmar(user32.PeekMessageW, (ctypes.POINTER(w.MSG), w.HWND, w.UINT, w.UINT, w.UINT),
                             w.BOOL)
    a.TranslateMessage = _firmar(user32.TranslateMessage, (ctypes.POINTER(w.MSG),), w.BOOL)
    a.DispatchMessageW = _firmar(user32.DispatchMessageW, (ctypes.POINTER(w.MSG),), LRESULT)
    a.PostThreadMessageW = _firmar(user32.PostThreadMessageW, (w.DWORD, w.UINT, w.WPARAM, w.LPARAM), w.BOOL)
    a.BeginPaint = _firmar(user32.BeginPaint, (w.HWND, ctypes.POINTER(PAINTSTRUCT)), w.HDC)
    a.EndPaint = _firmar(user32.EndPaint, (w.HWND, ctypes.POINTER(PAINTSTRUCT)), w.BOOL)
    a.GetClientRect = _firmar(user32.GetClientRect, (w.HWND, ctypes.POINTER(w.RECT)), w.BOOL)
    a.FillRect = _firmar(user32.FillRect, (w.HDC, ctypes.POINTER(w.RECT), w.HBRUSH), ctypes.c_int)
    a.DrawTextW = _firmar(user32.DrawTextW, (w.HDC, w.LPCWSTR, ctypes.c_int, ctypes.POINTER(w.RECT), w.UINT),
                          ctypes.c_int)
    a.SetCursor = _firmar(user32.SetCursor, (w.HANDLE,), w.HANDLE)
    a.EnumDisplayMonitors = _firmar(user32.EnumDisplayMonitors,
                                    (w.HDC, ctypes.POINTER(w.RECT), MONITORENUMPROC, w.LPARAM), w.BOOL)
    a.GetMonitorInfoW = _firmar(user32.GetMonitorInfoW, (w.HMONITOR, ctypes.POINTER(MONITORINFOEXW)), w.BOOL)
    a.EnumDisplayDevicesW = _firmar(user32.EnumDisplayDevicesW,
                                    (w.LPCWSTR, w.DWORD, ctypes.POINTER(DISPLAY_DEVICEW), w.DWORD), w.BOOL)
    a.RegisterRawInputDevices = _firmar(user32.RegisterRawInputDevices,
                                        (ctypes.POINTER(RAWINPUTDEVICE), w.UINT, w.UINT), w.BOOL)
    a.GetRawInputData = _firmar(user32.GetRawInputData,
                                (w.HANDLE, w.UINT, w.LPVOID, ctypes.POINTER(w.UINT), w.UINT), w.UINT)
    a.GetRawInputDeviceInfoW = _firmar(user32.GetRawInputDeviceInfoW,
                                       (w.HANDLE, w.UINT, w.LPVOID, ctypes.POINTER(w.UINT)), w.UINT)
    a.GetStockObject = _firmar(gdi32.GetStockObject, (ctypes.c_int,), w.HGDIOBJ)
    a.SetTextColor = _firmar(gdi32.SetTextColor, (w.HDC, w.COLORREF), w.COLORREF)
    a.SetBkMode = _firmar(gdi32.SetBkMode, (w.HDC, ctypes.c_int), ctypes.c_int)
    a.CreateFontW = _firmar(gdi32.CreateFontW,
                            (ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                             w.DWORD, w.DWORD, w.DWORD, w.DWORD, w.DWORD, w.DWORD, w.DWORD, w.DWORD,
                             w.LPCWSTR), w.HFONT)
    a.SelectObject = _firmar(gdi32.SelectObject, (w.HDC, w.HGDIOBJ), w.HGDIOBJ)
    a.DeleteObject = _firmar(gdi32.DeleteObject, (w.HGDIOBJ,), w.BOOL)
    a.IsUserAnAdmin = _firmar(shell32.IsUserAnAdmin, (), w.BOOL)
    return a


def monitores(a=None) -> list:
    """Monitores activos en el orden de EnumDisplayMonitors: lista de
    SimpleNamespace(rect=(x, y, ancho, alto), dispositivo='\\\\.\\DISPLAY1')."""
    a = a or api()
    salida = []

    def _cb(hmon, _hdc, _rect, _lp):
        info = MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if a.GetMonitorInfoW(hmon, ctypes.byref(info)):
            r = info.rcMonitor
            salida.append(SimpleNamespace(rect=(r.left, r.top, r.right - r.left, r.bottom - r.top),
                                          dispositivo=info.szDevice))
        return True

    cb = MONITORENUMPROC(_cb)   # referencia viva durante la llamada
    a.EnumDisplayMonitors(None, None, cb, 0)
    return salida


def interfaces_monitor(dispositivo: str, a=None) -> list[str]:
    """Rutas de interfaz (\\\\?\\DISPLAY#...#{e6f07b5f-...}) de los monitores
    conectados al adaptador `dispositivo` (\\\\.\\DISPLAY1), con
    EnumDisplayDevicesW(..., EDD_GET_DEVICE_INTERFACE_NAME)."""
    a = a or api()
    activos, todos = [], []
    i = 0
    while True:
        dd = DISPLAY_DEVICEW()
        dd.cb = ctypes.sizeof(DISPLAY_DEVICEW)
        if not a.EnumDisplayDevicesW(dispositivo, i, ctypes.byref(dd), EDD_GET_DEVICE_INTERFACE_NAME):
            break
        if dd.DeviceID:
            todos.append(dd.DeviceID)
            if dd.StateFlags & DISPLAY_DEVICE_ACTIVE:
                activos.append(dd.DeviceID)
        i += 1
    return activos or todos

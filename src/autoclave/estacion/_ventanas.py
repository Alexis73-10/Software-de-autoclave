# autoclave/estacion/_ventanas.py
#
# Ventanas Win32 negras, sin borde y siempre encima, con dos líneas de texto
# blanco centradas: las usa la herramienta de táctiles (EST-06, una a la
# vez). La cubierta de arranque (EST-07, una por monitor), que también las
# usaba, se retiró en la tanda 18 (EST-08).
#
# Reglas de hilo de Win32: las ventanas pertenecen al hilo que las crea, y
# solo ese hilo puede destruirlas y procesar sus mensajes. Por eso crear(),
# esperar() y destruir() se llaman siempre desde el mismo hilo; despertar() es
# lo único que se puede llamar desde otro hilo (publica un mensaje al hilo).
#
# Solo Windows. No se usa en las pruebas automáticas (se inyectan dobles).

import ctypes
import logging

from autoclave.estacion import _win32 as w

logger = logging.getLogger(__name__)

WM_DESPERTAR = w.WM_APP + 1
_COLOR_TEXTO = 0x00FFFFFF   # COLORREF blanco (0x00BBGGRR)


class VentanasTexto:
    """Ventanas negras con un título (logotipo de texto) y un texto debajo.

    `activable=False` (cubierta): WS_EX_NOACTIVATE y WM_MOUSEACTIVATE →
    MA_NOACTIVATEANDEAT: los toques y clics se los queda la ventana y no se
    reenvían a nada, sin robarle el foco a las pantallas QML que van
    apareciendo. `activable=True` (táctiles): la ventana toma el foco para
    recibir Esc/Enter.

    `al_mensaje(hwnd, msg, wparam, lparam)` permite atender mensajes propios
    (WM_INPUT, teclas); si devuelve un int, ese es el resultado del mensaje."""

    CLASE = "EspecifikaAutoclaveVentanaTexto"

    def __init__(self, titulo: str, texto: str, *, activable: bool, al_mensaje=None, api=None):
        self.a = api or w.api()
        self.titulo = titulo
        self.texto = texto
        self.activable = activable
        self.al_mensaje = al_mensaje
        self.hwnds: list = []
        self.hilo_id = None
        # nombre de clase propio de cada instancia: una cubierta que se cierra
        # mientras se abre otra no choca con ERROR_CLASS_ALREADY_EXISTS
        self.clase = f"{self.CLASE}{id(self):x}"
        self._wndproc = None
        self._hinst = None
        self._clase = False
        self._fuente_titulo = None
        self._fuente_texto = None

    # ── creación ────────────────────────────────────────────────────────────
    def crear(self, rects) -> None:
        """Una ventana por rectángulo (x, y, ancho, alto). Lanza OSError si
        no pudo crear ninguna; las que sí creó quedan para destruir()."""
        a = self.a
        self.hilo_id = a.GetCurrentThreadId()
        self._hinst = a.GetModuleHandleW(None)
        self._wndproc = w.WNDPROC(self._proc)   # referencia viva mientras existan las ventanas
        wc = w.WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(w.WNDCLASSEXW)
        wc.lpfnWndProc = self._wndproc
        wc.hInstance = self._hinst
        wc.hbrBackground = a.GetStockObject(w.BLACK_BRUSH)
        wc.lpszClassName = self.clase
        if not a.RegisterClassExW(ctypes.byref(wc)):
            raise OSError(f"RegisterClassExW falló (error {ctypes.get_last_error()})")
        self._clase = True
        self._fuente_titulo = a.CreateFontW(-72, 0, 0, 0, w.FW_BOLD, 0, 0, 0, 0, 0, 0,
                                            w.ANTIALIASED_QUALITY, 0, "Segoe UI")
        self._fuente_texto = a.CreateFontW(-40, 0, 0, 0, w.FW_NORMAL, 0, 0, 0, 0, 0, 0,
                                           w.ANTIALIASED_QUALITY, 0, "Segoe UI")
        estilo_ex = w.WS_EX_TOPMOST | w.WS_EX_TOOLWINDOW
        if not self.activable:
            estilo_ex |= w.WS_EX_NOACTIVATE
        for x, y, ancho, alto in rects:
            hwnd = a.CreateWindowExW(estilo_ex, self.clase, "Autoclave", w.WS_POPUP,
                                     x, y, ancho, alto, None, None, self._hinst, None)
            if not hwnd:
                logger.warning("CreateWindowExW falló en (%s, %s, %s, %s) (error %s)",
                               x, y, ancho, alto, ctypes.get_last_error())
                continue
            self.hwnds.append(hwnd)
            a.ShowWindow(hwnd, w.SW_SHOW if self.activable else w.SW_SHOWNOACTIVATE)
            a.SetWindowPos(hwnd, w.HWND_TOPMOST, x, y, ancho, alto, w.SWP_NOACTIVATE | w.SWP_SHOWWINDOW)
            a.UpdateWindow(hwnd)
            if self.activable:
                a.SetForegroundWindow(hwnd)
        if not self.hwnds:
            raise OSError("no se pudo crear ninguna ventana")

    def cambiar_texto(self, titulo: str, texto: str) -> None:
        self.titulo, self.texto = titulo, texto
        for hwnd in self.hwnds:
            self.a.InvalidateRect(hwnd, None, True)

    def reafirmar(self) -> None:
        """Vuelve a ponerlas encima de todo (la barra de tareas también es
        TOPMOST y puede subir sobre ellas si Explorer la reacomoda)."""
        for hwnd in self.hwnds:
            self.a.SetWindowPos(hwnd, w.HWND_TOPMOST, 0, 0, 0, 0,
                                w.SWP_NOACTIVATE | 0x0001 | 0x0002)   # SWP_NOSIZE | SWP_NOMOVE

    # ── bucle de mensajes ───────────────────────────────────────────────────
    def esperar(self, ms: int, handles=()) -> bool:
        """Espera hasta `ms` milisegundos a un mensaje o a que se señale alguno
        de `handles`, y procesa los mensajes pendientes. False si llegó
        WM_QUIT o WM_DESPERTAR (pedido de cierre desde otro hilo)."""
        a = self.a
        n = len(handles)
        arreglo = (w.wintypes.HANDLE * n)(*handles) if n else None
        a.MsgWaitForMultipleObjects(n, arreglo, False, max(0, int(ms)), w.QS_ALLINPUT)
        msg = w.wintypes.MSG()
        while a.PeekMessageW(ctypes.byref(msg), None, 0, 0, w.PM_REMOVE):
            if msg.message in (w.WM_QUIT, WM_DESPERTAR) and not msg.hWnd:
                return False
            a.TranslateMessage(ctypes.byref(msg))
            a.DispatchMessageW(ctypes.byref(msg))
        return True

    def despertar(self) -> None:
        """Desde cualquier hilo: hace que esperar() devuelva False."""
        if self.hilo_id:
            self.a.PostThreadMessageW(self.hilo_id, WM_DESPERTAR, 0, 0)

    # ── cierre ──────────────────────────────────────────────────────────────
    def destruir(self) -> None:
        """Destruye todo lo creado, aunque crear() haya fallado a medias.
        Cada paso por separado: un fallo no deja las demás ventanas vivas."""
        a = self.a
        for hwnd in self.hwnds:
            try:
                a.DestroyWindow(hwnd)
            except Exception:
                logger.exception("DestroyWindow falló")
        self.hwnds = []
        for fuente in (self._fuente_titulo, self._fuente_texto):
            if fuente:
                try:
                    a.DeleteObject(fuente)
                except Exception:
                    pass
        self._fuente_titulo = self._fuente_texto = None
        if self._clase:
            try:
                a.UnregisterClassW(self.clase, self._hinst)
            except Exception:
                pass
            self._clase = False

    # ── procedimiento de ventana ────────────────────────────────────────────
    def _proc(self, hwnd, msg, wparam, lparam):
        a = self.a
        try:
            if self.al_mensaje is not None:
                r = self.al_mensaje(hwnd, msg, wparam, lparam)
                if r is not None:
                    return r
            if msg == w.WM_PAINT:
                self._pintar(hwnd)
                return 0
            if msg == w.WM_CLOSE:
                return 0   # Alt+F4 no la cierra: solo destruir()
            if msg == w.WM_SETCURSOR:
                a.SetCursor(None)   # sin flecha del ratón sobre la cubierta
                return 1
            if not self.activable:
                if msg == w.WM_MOUSEACTIVATE:
                    return w.MA_NOACTIVATEANDEAT
                if (w.WM_MOUSE_PRIMERO <= msg <= w.WM_MOUSE_ULTIMO or msg == w.WM_TOUCH
                        or w.WM_POINTER_PRIMERO <= msg <= w.WM_POINTER_ULTIMO):
                    return 0   # se queda con el toque/clic; no se reenvía a nada
        except Exception:
            logger.exception("Error en el procedimiento de ventana (mensaje 0x%04X)", msg)
        return a.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _pintar(self, hwnd) -> None:
        a = self.a
        ps = w.PAINTSTRUCT()
        hdc = a.BeginPaint(hwnd, ctypes.byref(ps))
        try:
            rc = w.wintypes.RECT()
            a.GetClientRect(hwnd, ctypes.byref(rc))
            a.FillRect(hdc, ctypes.byref(rc), a.GetStockObject(w.BLACK_BRUSH))
            a.SetBkMode(hdc, w.TRANSPARENT)
            a.SetTextColor(hdc, _COLOR_TEXTO)
            centro = (rc.top + rc.bottom) // 2
            arriba = w.wintypes.RECT(rc.left, rc.top, rc.right, centro - 10)
            abajo = w.wintypes.RECT(rc.left, centro + 10, rc.right, rc.bottom)
            previa = a.SelectObject(hdc, self._fuente_titulo) if self._fuente_titulo else None
            a.DrawTextW(hdc, self.titulo, -1, ctypes.byref(arriba),
                        w.DT_CENTER | w.DT_BOTTOM | w.DT_SINGLELINE)
            if self._fuente_texto:
                a.SelectObject(hdc, self._fuente_texto)
            a.DrawTextW(hdc, self.texto, -1, ctypes.byref(abajo),
                        w.DT_CENTER | w.DT_TOP | w.DT_WORDBREAK)
            if previa:
                a.SelectObject(hdc, previa)
        finally:
            a.EndPaint(hwnd, ctypes.byref(ps))

# autoclave/estacion/cubierta_arranque.py
#
# EST-07 (tanda 17, DECISIÓN SIN CONFIRMAR): cubierta de arranque.
#
# Al iniciar sesión, el escritorio de Windows quedaba expuesto unos 30 s
# hasta que aparecían las pantallas QML. El lanzador (exe_unico, rol
# lanzador) abre esta cubierta LO PRIMERO, antes de importar PySide o lanzar
# el backend:
#   - una ventana Win32 nativa por monitor (EnumDisplayMonitors), WS_POPUP sin
#     borde, WS_EX_TOPMOST (siempre encima, también de la barra de tareas),
#     WS_EX_TOOLWINDOW (no sale en la barra) y WS_EX_NOACTIVATE, del tamaño
#     completo del monitor; fondo negro con "e-specifika" e
#     "Iniciando… / Starting…" (texto bilingüe fijo: corre antes de cargar
#     los catálogos i18n);
#   - se queda con los toques y clics (MA_NOACTIVATEANDEAT y mensajes de
#     ratón/toque/puntero devueltos como atendidos; sin WS_EX_TRANSPARENT);
#   - corre en su propio hilo (daemon) con su bucle de mensajes: no bloquea el
#     arranque;
#   - se cierra cuando las pantallas QML señalan su primer cuadro (eventos con
#     nombre, ver primer_cuadro.py): con todas las puertas esperadas, o
#     GRACIA_S después de la primera (para que una pantalla 2 que no arranca
#     no deje tapada la 1); y en todo caso a los TOPE_S = 180 s de abrirla,
#     medidos con time.monotonic() en el propio hilo de la cubierta (no
#     depende de que el hilo principal esté libre). Un temporizador de
#     respaldo (threading.Timer) pide además el cierre a los TOPE_S + 10 s;
#   - cualquier error se registra en el log y el arranque sigue: abrir() nunca
#     lanza, y el hilo destruye en un `finally` todas las ventanas que creó
#     (aunque la creación haya fallado a medias), así que no quedan ventanas
#     huérfanas. Si el proceso termina, Windows destruye las ventanas.
#
# Activación: solo en Windows; por defecto solo en el build congelado. La
# variable de entorno AUTOCLAVE_CUBIERTA=0 la desactiva siempre y =1 la activa
# también en desarrollo.

import logging
import os
import sys
import threading
import time

from autoclave.estacion import primer_cuadro

logger = logging.getLogger(__name__)

TOPE_S = 180.0
GRACIA_S = 15.0
RESPALDO_EXTRA_S = 10.0
VARIABLE_ENTORNO = "AUTOCLAVE_CUBIERTA"
TITULO = "e-specifika"
TEXTO = "Iniciando… / Starting…"
_PAUSA_MAX_MS = 250
_REAFIRMAR_S = 1.0


def activa(entorno=None, congelado=None, plataforma=None) -> bool:
    entorno = os.environ if entorno is None else entorno
    plataforma = sys.platform if plataforma is None else plataforma
    congelado = bool(getattr(sys, "frozen", False)) if congelado is None else congelado
    if plataforma != "win32":
        return False
    valor = str(entorno.get(VARIABLE_ENTORNO, "")).strip()
    if valor == "0":
        return False
    if valor == "1":
        return True
    return congelado


def motivo_cierre(ahora: float, inicio: float, primera, pendientes, *, tope_s: float = TOPE_S,
                  gracia_s: float = GRACIA_S, solicitado: bool = False):
    """Decide si la cubierta debe cerrarse. Función pura (reloj inyectado).
    Devuelve el motivo ('solicitado', 'pantallas', 'tope', 'gracia') o None."""
    if solicitado:
        return "solicitado"
    if not pendientes:
        return "pantallas"
    if ahora - inicio >= tope_s:
        return "tope"
    if primera is not None and ahora - primera >= gracia_s:
        return "gracia"
    return None


class _NucleoWin32:
    """Ventanas y eventos reales. Todo se llama desde el hilo de la cubierta,
    salvo despertar()."""

    def __init__(self):
        from autoclave.estacion import _win32
        from autoclave.estacion._ventanas import VentanasTexto
        self._w = _win32
        self.a = _win32.api()
        self.ventanas = VentanasTexto(TITULO, TEXTO, activable=False, api=self.a)
        self.eventos: dict[int, int] = {}

    def crear(self, puertas) -> None:
        for puerta in puertas:
            h = self.a.CreateEventW(None, True, False, primer_cuadro.nombre_evento(puerta))
            if h:
                self.a.ResetEvent(h)   # por si sobrevivía uno ya señalado de otro arranque
                self.eventos[puerta] = h
            else:
                logger.warning("Cubierta: no se pudo crear el evento de la puerta %s; se cerrará por tope",
                               puerta)
        rects = [m.rect for m in self._w.monitores(self.a)]
        if not rects:
            raise OSError("EnumDisplayMonitors no devolvió monitores")
        self.ventanas.crear(rects)

    def senaladas(self) -> set:
        return {p for p, h in self.eventos.items()
                if self.a.WaitForSingleObject(h, 0) == self._w.WAIT_OBJECT_0}

    def esperar(self, ms: int, pendientes=None) -> bool:
        """V17-s2-02: solo los eventos de las puertas PENDIENTES. Los eventos
        son de reinicio manual: uno ya señalado haría volver al instante a
        MsgWaitForMultipleObjects y el bucle giraría sin pausa."""
        puertas = self.eventos.keys() if pendientes is None else pendientes
        handles = [self.eventos[p] for p in sorted(puertas) if p in self.eventos]
        return self.ventanas.esperar(ms, handles)

    def reafirmar(self) -> None:
        self.ventanas.reafirmar()

    def despertar(self) -> None:
        self.ventanas.despertar()

    def destruir(self) -> None:
        try:
            self.ventanas.destruir()
        finally:
            for h in self.eventos.values():
                try:
                    self.a.CloseHandle(h)
                except Exception:
                    pass
            self.eventos = {}


class Cubierta:
    """Cubierta abierta (o que intentó abrirse). `error` tiene el motivo si no
    se pudo abrir; `cerrada` se activa cuando el hilo terminó y ya no queda
    ninguna ventana; `motivo` dice por qué se cerró."""

    def __init__(self, puertas, *, tope_s=TOPE_S, gracia_s=GRACIA_S, reloj=time.monotonic,
                 fabrica=None, log=None):
        self.puertas = tuple(puertas)
        self.tope_s = float(tope_s)
        self.gracia_s = float(gracia_s)
        self._reloj = reloj
        self._fabrica = fabrica or _NucleoWin32
        self._log = log or logger
        self._pedido = threading.Event()
        self.cerrada = threading.Event()
        self.error = None
        self.motivo = None
        self._nucleo = None
        self._hilo = None
        self._respaldo = None
        self.inicio = reloj()

    # ── desde cualquier hilo ────────────────────────────────────────────────
    def cerrar(self) -> None:
        """Pide el cierre. Nunca lanza."""
        self._pedido.set()
        nucleo = self._nucleo
        if nucleo is not None:
            try:
                nucleo.despertar()
            except Exception:
                self._log.exception("Cubierta: no se pudo despertar su hilo")

    def esperar_cierre(self, timeout=None) -> bool:
        return self.cerrada.wait(timeout)

    # ── hilo propio ─────────────────────────────────────────────────────────
    def iniciar(self) -> None:
        self._hilo = threading.Thread(target=self.correr, name="cubierta-arranque", daemon=True)
        self._hilo.start()
        self._respaldo = threading.Timer(self.tope_s + RESPALDO_EXTRA_S, self.cerrar)
        self._respaldo.daemon = True
        self._respaldo.start()

    def correr(self) -> None:
        """Cuerpo del hilo: crea, espera señal o tope y destruye siempre."""
        nucleo = None
        try:
            nucleo = self._fabrica()
            self._nucleo = nucleo
            nucleo.crear(self.puertas)
            self._log.info("Cubierta de arranque abierta (puertas %s, tope %.0f s)",
                           ",".join(str(p) for p in self.puertas), self.tope_s)
            pendientes = set(self.puertas)
            primera = None
            ultimo_reafirmar = self._reloj()
            while True:
                ahora = self._reloj()
                hechas = nucleo.senaladas() & pendientes
                if hechas:
                    pendientes -= hechas
                    if primera is None:
                        primera = ahora
                    self._log.info("Cubierta: primer cuadro de la puerta %s a los %.1f s",
                                   ",".join(str(p) for p in sorted(hechas)), ahora - self.inicio)
                motivo = motivo_cierre(ahora, self.inicio, primera, pendientes, tope_s=self.tope_s,
                                       gracia_s=self.gracia_s, solicitado=self._pedido.is_set())
                if motivo:
                    self.motivo = motivo
                    break
                if ahora - ultimo_reafirmar >= _REAFIRMAR_S:
                    nucleo.reafirmar()
                    ultimo_reafirmar = ahora
                limite = self.inicio + self.tope_s
                if primera is not None:
                    limite = min(limite, primera + self.gracia_s)
                pausa_ms = int(max(0.0, min(_PAUSA_MAX_MS / 1000.0, limite - ahora)) * 1000)
                if not nucleo.esperar(pausa_ms, frozenset(pendientes)):
                    self.motivo = "solicitado"
                    break
        except Exception as e:
            self.error = f"{type(e).__name__}: {e}"
            self.motivo = "error"
            self._log.exception("Cubierta de arranque: falló; el arranque sigue sin ella")
        finally:
            if nucleo is not None:
                try:
                    nucleo.destruir()
                except Exception:
                    self._log.exception("Cubierta de arranque: error al destruir sus ventanas")
            if self._respaldo is not None:
                self._respaldo.cancel()
            self.cerrada.set()
            self._log.info("Cubierta de arranque cerrada (%s) a los %.1f s", self.motivo,
                           self._reloj() - self.inicio)


def abrir(puertas=(1, 2), *, tope_s=TOPE_S, gracia_s=GRACIA_S, reloj=time.monotonic, fabrica=None,
          log=None):
    """Abre la cubierta en su propio hilo y devuelve la Cubierta. Nunca lanza:
    ante un error devuelve una Cubierta ya cerrada con `error`."""
    cubierta = None
    try:
        cubierta = Cubierta(puertas, tope_s=tope_s, gracia_s=gracia_s, reloj=reloj, fabrica=fabrica,
                            log=log)
        cubierta.iniciar()
        return cubierta
    except Exception as e:
        (log or logger).exception("Cubierta de arranque: no se pudo iniciar")
        if cubierta is None:
            cubierta = Cubierta.__new__(Cubierta)
            cubierta.cerrada = threading.Event()
            cubierta._pedido = threading.Event()
            cubierta._nucleo = None
            cubierta._log = log or logger
            cubierta.motivo = None
        cubierta.error = f"{type(e).__name__}: {e}"
        cubierta.motivo = "error"
        cubierta.cerrar()
        cubierta.cerrada.set()
        return cubierta

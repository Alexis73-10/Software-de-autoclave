# ui_qml/controllers/mantenimiento_controller.py
#
# OPCIONES › Mantenimiento (M1, tanda 3; diseño PROVISIONAL): próximo
# vencimiento, último mantenimiento, ciclos restantes y "Registrar
# mantenimiento realizado". Lee GET /maintenance y escribe POST
# /maintenance/records con el token de la ventana (técnico/ingeniero). No
# calcula nada: el backend decide vencimientos y valida (y nunca bloquea un
# ciclo: esta pantalla solo informa). Desde la tanda 4 (B3) también edita los
# intervalos (días y ciclos; 0 = no aplica) con PUT /maintenance/config.
#
# Sin HTTP síncrono en la GUI (AJUSTES 2026-11-02, paso 2 fase 4):
#   - Intervalos: cambio optimista con reversión (CambioOptimista; clave
#     "intervalos", valor (días, ciclos)); el desenlace llega por `cambioResuelto`.
#   - Registrar mantenimiento: asíncrono; lo mostrado no cambia hasta el 200 y la
#     clave "registro" queda en `pendientes` («guardando…») mientras tanto.
#   - Lectura: GET asíncrono con `cargando`.
# Los slots devuelven False si falla la validación local; con el resultado en el
# acto (sesión de prueba con solo `enviar`), el `ok` real; en vuelo, True.

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtQml import qmlRegisterType

from autoclave.core.runtime.mantenimiento import TIPOS
from autoclave.ui_qml import sesion_backend
from autoclave.ui_qml.cambio_optimista import (
    ENVIANDO, SIN_CONFIRMAR, SIN_LECTURA, CambioOptimista)
from autoclave.ui_qml.domain import resumen_sistema as dominio

# TIPOS: definición única en core/runtime/mantenimiento.py (MNT-03; lógica pura,
# sin E/S: no arrastra el servicio del backend ni la máquina de estados).
# límites de core/runtime/mantenimiento.py (el backend los vuelve a validar)
DIAS_MAX = 3650
CICLOS_MAX = 1_000_000

_MENSAJES = {
    "reloj_invalido": "opciones.mant_err_reloj",
    "reloj_adelantado": "opciones.mant_err_reloj_adelantado",
    "validacion": "opciones.mant_err_validacion",
    "calibracion_en_curso": "opciones.mant_err_calibracion_en_curso",
    "rol_sin_permiso": "opciones.err_rol",
    "sesion_invalida": "opciones.err_identidad",
    "estado_no_permitido": "opciones.err_bloqueada",
    sesion_backend.BACKEND_NO_RESPONDE: "opciones.err_sin_respuesta",
}


MENSAJE_SIN_CONFIRMAR = "opciones.cambio_sin_confirmar"
_CLAVE_INTERVALOS = "intervalos"


def mensaje_de(causa: str) -> str:
    return _MENSAJES.get(causa, "opciones.err_generico")


def _cancelar_al_destruir(sesion, ident):
    return lambda *_: sesion_backend.cancelar_envios(sesion, ident)


class MantenimientoController(QObject):
    datosChanged = Signal()
    mensajeChanged = Signal()
    pendientesChanged = Signal()
    cargandoChanged = Signal()
    # clave del cambio, aceptado, clave i18n del mensaje ("" si aceptado)
    cambioResuelto = Signal(str, bool, str)

    def __init__(self, parent=None, sesion=None):
        super().__init__(parent)
        self._sesion = sesion
        self._datos = dominio.mantenimiento_presentable(None)
        self._estado = ""
        self._mensaje = ""
        self._revertido = False         # el mensaje es el motivo de una reversión
        self._intervalos = (-1, -1)     # (días, ciclos); -1 = se desconocen
        self._en_vuelo: dict[str, str] = {}   # acciones B pendientes
        self._gen_carga = 0
        self._cargando = False
        self._resuelto = None           # desenlace síncrono del último slot
        self._opt = CambioOptimista(self._lanzar_intervalos, self._al_cambiar,
                                    self._al_revertir, self._releer,
                                    al_confirmar=self._al_confirmar,
                                    al_pendientes=self.pendientesChanged.emit)
        # sin referencia a self: el destructor de C++ ya está en marcha
        self.destroyed.connect(_cancelar_al_destruir(sesion, id(self)))

    def _s(self):
        return self._sesion or sesion_backend.ventana()

    def _enviar(self, metodo, ruta, cuerpo, al_terminar, al_tardio=None) -> None:
        sesion_backend.enviar_async(self._s(), metodo, ruta, cuerpo, al_terminar,
                                    dueno=self, al_tardio=al_tardio)

    def _fijar_mensaje(self, clave: str, revertido: bool = False) -> None:
        if clave != self._mensaje or revertido != self._revertido:
            self._mensaje = clave
            self._revertido = revertido
            self.mensajeChanged.emit()

    # ── estado de los envíos ─────────────────────────────────────────────
    @Property("QVariantMap", notify=pendientesChanged)
    def pendientes(self) -> dict:
        """clave -> "enviando" | "verificando"."""
        return {**self._opt.pendientes(), **self._en_vuelo}

    @Property(bool, notify=cargandoChanged)
    def cargando(self) -> bool:
        return self._cargando

    def _fijar_cargando(self, v: bool) -> None:
        if v != self._cargando:
            self._cargando = v
            self.cargandoChanged.emit()

    # ── carga ────────────────────────────────────────────────────────────
    @Slot()
    def cargar(self) -> None:
        self._gen_carga += 1
        gen, marca = self._gen_carga, self._opt.marca()
        self._fijar_cargando(True)
        self._enviar("GET", "/maintenance", None, lambda r: self._al_cargar(r, gen, marca))

    def _al_cargar(self, r, gen, marca) -> None:
        if gen != self._gen_carga:
            return                         # una carga posterior manda
        self._fijar_cargando(False)
        if r.ok and isinstance(r.datos, dict):
            self._datos = dominio.mantenimiento_presentable(r.datos)
            self._estado = str(r.datos.get("estado") or "")
            leidos = self._leer_intervalos(r.datos)
            if self._opt.confirmar_lectura(_CLAVE_INTERVALOS, leidos, marca):
                self._intervalos = leidos
            else:
                # cambio pendiente o lectura lanzada antes del último cambio:
                # se conserva lo que se muestra
                self._intervalos = self._opt.mostrar(_CLAVE_INTERVALOS, self._intervalos)
        else:
            self._datos = dominio.mantenimiento_presentable(None)
            self._estado = ""
            self._intervalos = (-1, -1)
            self._fijar_mensaje(mensaje_de(r.causa))
        self.datosChanged.emit()

    @staticmethod
    def _leer_intervalos(datos: dict) -> tuple[int, int]:
        cfg = datos.get("configuracion")
        cfg = cfg if isinstance(cfg, dict) else {}

        def entero(v):
            return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else -1
        return entero(cfg.get("intervalo_dias")), entero(cfg.get("intervalo_ciclos"))

    # ── registrar mantenimiento: asíncrono ───────────────────────────────
    @Slot(str, result=bool)
    def registrar(self, tipo: str) -> bool:
        """"Registrar mantenimiento realizado". False si el tipo no es válido;
        con el resultado en el acto, el `ok` real; en vuelo, True."""
        if tipo not in TIPOS:
            return False
        clave = "registro"
        if clave in self._en_vuelo:
            return False                   # el anterior sigue pendiente
        self._en_vuelo[clave] = ENVIANDO
        self.pendientesChanged.emit()
        self._resuelto = None

        def terminar(r):
            self._en_vuelo.pop(clave, None)
            self.pendientesChanged.emit()
            self._resuelto = r.ok
            # sin respuesta el resultado es incierto: se relee antes de informar
            self.cargar()
            self._fijar_mensaje("" if r.ok else mensaje_de(r.causa))
            self.cambioResuelto.emit(clave, r.ok, self._mensaje)

        self._enviar("POST", "/maintenance/records", {"tipo": tipo, "observaciones": ""}, terminar)
        resuelto, self._resuelto = self._resuelto, None
        return True if resuelto is None else resuelto

    # ── intervalos: optimista con reversión ──────────────────────────────
    def _lanzar_intervalos(self, clave, valor, al_terminar) -> None:
        dias, ciclos = valor
        # la respuesta tardía (tras backend_no_responde) no pasa por el cambio
        # optimista: se relee, y la marca protege lo aún pendiente
        self._enviar("PUT", "/maintenance/config",
                     {"intervalo_dias": dias, "intervalo_ciclos": ciclos}, al_terminar,
                     al_tardio=lambda _r: self.cargar())

    def _releer(self, clave, al_leer) -> None:
        def leido(r):
            if r.ok and isinstance(r.datos, dict):
                al_leer(self._leer_intervalos(r.datos))
            else:
                al_leer(SIN_LECTURA)
        self._enviar("GET", "/maintenance", None, leido)

    def _al_cambiar(self, clave, valor) -> None:
        if self._intervalos != valor:
            self._intervalos = valor
            self.datosChanged.emit()

    def _al_confirmar(self, clave) -> None:
        self._resuelto = True
        self._fijar_mensaje("")
        self.cargar()                      # vencimientos y ciclos restantes dependen de los intervalos
        self.cambioResuelto.emit(clave, True, "")

    def _al_revertir(self, clave, causa) -> None:
        self._resuelto = False
        if causa == SIN_CONFIRMAR:
            self._fijar_mensaje(MENSAJE_SIN_CONFIRMAR)
            self.cargar()                  # mostrar el estado real
        else:
            self._fijar_mensaje(mensaje_de(causa), revertido=True)
        self.cambioResuelto.emit(clave, False, self._mensaje)

    @Slot(int, int, result=bool)
    def guardarIntervalos(self, dias: int, ciclos: int) -> bool:
        """Guarda los intervalos (0 = no aplica). False si no pasa la validación
        local; con el resultado en el acto, el `ok` real; en vuelo, True."""
        if not (0 <= dias <= DIAS_MAX and 0 <= ciclos <= CICLOS_MAX):
            self._fijar_mensaje(mensaje_de("validacion"))
            return False
        self._resuelto = None
        self._opt.aplicar(_CLAVE_INTERVALOS, (dias, ciclos), self._intervalos)
        resuelto, self._resuelto = self._resuelto, None
        return True if resuelto is None else resuelto

    @Property(int, notify=datosChanged)
    def intervaloDias(self) -> int:
        return self._intervalos[0]

    @Property(int, notify=datosChanged)
    def intervaloCiclos(self) -> int:
        return self._intervalos[1]

    @Property(int, constant=True)
    def diasMax(self) -> int:
        return DIAS_MAX

    @Property(int, constant=True)
    def ciclosMax(self) -> int:
        return CICLOS_MAX

    @Property(str, notify=datosChanged)
    def proximo(self) -> str:
        return self._datos["proximo"]

    @Property(bool, notify=datosChanged)
    def vencido(self) -> bool:
        return self._datos["vencido"]

    @Property(str, notify=datosChanged)
    def ultimo(self) -> str:
        return self._datos["ultimo"]

    @Property(str, notify=datosChanged)
    def ciclosRestantes(self) -> str:
        return self._datos["ciclos_restantes"]

    @Property(str, notify=datosChanged)
    def estado(self) -> str:
        return self._estado

    @Property(list, constant=True)
    def tipos(self) -> list:
        return list(TIPOS)

    @Property(str, notify=mensajeChanged)
    def mensaje(self) -> str:
        return self._mensaje

    @Property(bool, notify=mensajeChanged)
    def mensajeRevertido(self) -> bool:
        """El mensaje es el motivo de un cambio que no se aplicó: la pantalla
        lo muestra dentro de opciones.cambio_revertido."""
        return self._revertido

    @Slot()
    def limpiarMensaje(self) -> None:
        self._fijar_mensaje("")


qmlRegisterType(MantenimientoController, "Autoclave.Controllers", 1, 0,
                "MantenimientoController")

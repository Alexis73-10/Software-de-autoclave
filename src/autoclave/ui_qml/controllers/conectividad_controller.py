# ui_qml/controllers/conectividad_controller.py
#
# OPCIONES › Conectividad (O2g, tanda 6; mockup 11 de docs/mockups/tanda6/
# APROBADO.md). Red en solo lectura (GET /network/status) y correo de ciclos
# (GET/PUT /email/config, POST /email/test). Los permisos los decide el
# backend (403); aquí solo se reflejan con permisos_opciones.motivo_destinatarios
# para deshabilitar los controles del técnico con el motivo (decisión 1.9).
# La contraseña del relay nunca llega a esta capa: el backend solo informa si
# está configurada.
#
# Sin HTTP síncrono en la GUI (AJUSTES 2026-11-02, paso 2 fase 4):
#   - Interruptor y destinatarios (PUT /email/config): cambio optimista con
#     reversión (CambioOptimista; clave "email", valor {envio_activo,
#     destinatarios}); si el backend lo rechaza vuelve a lo confirmado.
#   - Correo de prueba: asíncrono; la clave "prueba" queda en `pendientes`
#     hasta el 200.
#   - Red y correo: GET asíncronos con `cargando`.
# Los slots devuelven False si falla la validación local; con el resultado en
# el acto (sesión de prueba con solo `enviar`), el `ok` real; en vuelo, True.

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtQml import qmlRegisterType

from autoclave.ui_qml import sesion_backend
from autoclave.ui_qml.cambio_optimista import (
    ENVIANDO, SIN_CONFIRMAR, SIN_LECTURA, CambioOptimista)
from autoclave.ui_qml.domain import permisos_opciones as permisos

_MENSAJES = {
    "correo_invalido": "conectividad.err_correo_invalido",
    "duplicado": "conectividad.err_duplicado",
    "demasiados": "conectividad.err_demasiados",
    "nombre_largo": "conectividad.err_nombre_largo",
    "sin_destinatarios": "conectividad.err_sin_destinatarios",
    "correo_no_configurado": "conectividad.err_no_configurado",
    "envio_fallido": "conectividad.err_envio",
    "envio_desactivado": "conectividad.err_desactivado",
    "ARCHIVO_NO_ESCRIBIBLE": "conectividad.err_archivo",
    "rol_sin_permiso": "opciones.err_rol",
    "sesion_invalida": "opciones.err_identidad",
    "estado_no_permitido": "opciones.err_bloqueada",
    sesion_backend.BACKEND_NO_RESPONDE: "opciones.err_sin_respuesta",
}
MENSAJE_SIN_CONFIRMAR = "opciones.cambio_sin_confirmar"
_CLAVE_EMAIL = "email"


def mensaje_de(causa: str) -> str:
    return _MENSAJES.get(causa, "opciones.err_generico")


def _cancelar_al_destruir(sesion, ident):
    return lambda *_: sesion_backend.cancelar_envios(sesion, ident)


def _valor_email(datos: dict) -> dict:
    """Lo que se edita y se compara: interruptor y lista de destinatarios."""
    lista = datos.get("destinatarios")
    return {"envio_activo": datos.get("envio_activo") is True,
            "destinatarios": [dict(d) for d in lista if isinstance(d, dict)]
            if isinstance(lista, list) else []}


class ConectividadController(QObject):
    datosChanged = Signal()
    mensajeChanged = Signal()
    rolChanged = Signal()
    pendientesChanged = Signal()
    cargandoChanged = Signal()
    # clave del cambio, aceptado, clave i18n del mensaje ("" si aceptado)
    cambioResuelto = Signal(str, bool, str)

    def __init__(self, parent=None, sesion=None):
        super().__init__(parent)
        self._sesion = sesion
        self._red: dict = {}
        self._correo: dict = {}
        self._mensaje = ""
        self._revertido = False            # el mensaje es el motivo de una reversión
        self._rol = ""
        self._estado = ""
        self._en_vuelo: dict[str, str] = {}   # acciones B pendientes
        self._gen_carga = 0
        self._cargas: set = set()
        self._resuelto = None              # desenlace síncrono del último slot
        self._ultimo_ok = None             # respuesta del último PUT aceptado
        self._opt = CambioOptimista(self._lanzar_email, self._al_cambiar, self._al_revertir,
                                    self._releer, al_confirmar=self._al_confirmar,
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

    # ── rol y estado (para el motivo de solo lectura) ─────────────────
    def _get_rol(self):
        return self._rol

    def _set_rol(self, v):
        if v != self._rol:
            self._rol = v or ""
            self.rolChanged.emit()

    rol = Property(str, _get_rol, _set_rol, notify=rolChanged)

    def _get_estado(self):
        return self._estado

    def _set_estado(self, v):
        if v != self._estado:
            self._estado = v or ""
            self.rolChanged.emit()

    estadoMaquina = Property(str, _get_estado, _set_estado, notify=rolChanged)

    @Property(str, notify=rolChanged)
    def motivoEdicion(self) -> str:
        return permisos.motivo_destinatarios(self._rol, self._estado)

    @Property(bool, notify=rolChanged)
    def puedeEditar(self) -> bool:
        return self.motivoEdicion == ""

    # ── estado de los envíos ──────────────────────────────────────────
    @Property("QVariantMap", notify=pendientesChanged)
    def pendientes(self) -> dict:
        """clave -> "enviando" | "verificando"."""
        return {**self._opt.pendientes(), **self._en_vuelo}

    @Property(bool, notify=cargandoChanged)
    def cargando(self) -> bool:
        return bool(self._cargas)

    def _fijar_cargas(self, cargas: set) -> None:
        antes = bool(self._cargas)
        self._cargas = cargas
        if antes != bool(cargas):
            self.cargandoChanged.emit()

    # ── carga ─────────────────────────────────────────────────────────
    @Slot()
    def cargar(self) -> None:
        self._gen_carga += 1
        gen, marca = self._gen_carga, self._opt.marca()
        self._fijar_cargas({"red", "correo"})
        self._enviar("GET", "/network/status", None, lambda r: self._al_cargar_red(r, gen))
        self._enviar("GET", "/email/config", None,
                     lambda r: self._al_cargar_correo(r, gen, marca))

    def _al_cargar_red(self, r, gen) -> None:
        if gen != self._gen_carga:
            return                         # una carga posterior manda
        self._fijar_cargas(self._cargas - {"red"})
        self._red = r.datos if r.ok and isinstance(r.datos, dict) else {}
        self.datosChanged.emit()

    def _al_cargar_correo(self, r, gen, marca) -> None:
        if gen != self._gen_carga:
            return
        self._fijar_cargas(self._cargas - {"correo"})
        if r.ok and isinstance(r.datos, dict):
            nuevo = dict(r.datos)
            leido = _valor_email(nuevo)
            if not self._opt.confirmar_lectura(_CLAVE_EMAIL, leido, marca):
                # cambio pendiente o lectura lanzada antes del último cambio:
                # se conserva lo que se muestra
                nuevo.update(self._opt.mostrar(_CLAVE_EMAIL, _valor_email(self._correo)))
            self._correo = nuevo
        else:
            self._correo = {}
            self._fijar_mensaje(mensaje_de(r.causa))
        self.datosChanged.emit()

    # ── interruptor y destinatarios: optimista con reversión ──────────
    def _lanzar_email(self, clave, valor, al_terminar) -> None:
        def terminar(r):
            if r.ok and isinstance(r.datos, dict):
                self._ultimo_ok = r.datos
            al_terminar(r)
        # la respuesta tardía (tras backend_no_responde) no pasa por el cambio
        # optimista: se relee, y la marca protege lo aún pendiente
        self._enviar("PUT", "/email/config",
                     {"envio_activo": valor["envio_activo"],
                      "destinatarios": valor["destinatarios"]},
                     terminar, al_tardio=lambda _r: self.cargar())

    def _releer(self, clave, al_leer) -> None:
        def leido(r):
            if r.ok and isinstance(r.datos, dict):
                al_leer(_valor_email(r.datos))
            else:
                al_leer(SIN_LECTURA)
        self._enviar("GET", "/email/config", None, leido)

    def _al_cambiar(self, clave, valor) -> None:
        if _valor_email(self._correo) != valor:
            self._correo = {**self._correo, **valor}
            self.datosChanged.emit()

    def _al_confirmar(self, clave) -> None:
        ok, self._ultimo_ok = self._ultimo_ok, None
        if ok is not None and self._opt.pendiente(clave) is None:
            self._correo = {**self._correo, **ok}      # lo normalizado por el backend
            self.datosChanged.emit()
        self._resuelto = True
        self._fijar_mensaje("")
        self.cambioResuelto.emit(clave, True, "")

    def _al_revertir(self, clave, causa) -> None:
        self._ultimo_ok = None
        self._resuelto = False
        if causa == SIN_CONFIRMAR:
            self._fijar_mensaje(MENSAJE_SIN_CONFIRMAR)
            self.cargar()                  # mostrar el estado real
        else:
            self._fijar_mensaje(mensaje_de(causa), revertido=True)
        self.cambioResuelto.emit(clave, False, self._mensaje)

    def _guardar(self, activo: bool, destinatarios: list) -> bool:
        nuevo = {"envio_activo": bool(activo), "destinatarios": list(destinatarios)}
        self._resuelto = None
        self._opt.aplicar(_CLAVE_EMAIL, nuevo, _valor_email(self._correo))
        resuelto, self._resuelto = self._resuelto, None
        return True if resuelto is None else resuelto

    @Slot(bool, result=bool)
    def fijarEnvio(self, activo: bool) -> bool:
        return self._guardar(bool(activo), self.destinatarios)

    @Slot(str, str, result=bool)
    def agregar(self, nombre: str, correo: str) -> bool:
        correo = (correo or "").strip()
        lista = self.destinatarios + [{"nombre": (nombre or "").strip() or correo, "correo": correo}]
        return self._guardar(self.envioActivo, lista)

    @Slot(int, result=bool)
    def quitar(self, indice: int) -> bool:
        lista = self.destinatarios
        if not 0 <= indice < len(lista):
            return False
        del lista[indice]
        return self._guardar(self.envioActivo, lista)

    # ── correo de prueba: asíncrono ───────────────────────────────────
    @Slot(result=bool)
    def enviarPrueba(self) -> bool:
        clave = "prueba"
        if clave in self._en_vuelo:
            return False                   # el anterior sigue pendiente
        self._en_vuelo[clave] = ENVIANDO
        self.pendientesChanged.emit()
        self._resuelto = None

        def terminar(r):
            self._en_vuelo.pop(clave, None)
            self.pendientesChanged.emit()
            self._resuelto = r.ok
            self._fijar_mensaje("conectividad.prueba_enviada" if r.ok else mensaje_de(r.causa))
            self.cambioResuelto.emit(clave, r.ok, self._mensaje)

        self._enviar("POST", "/email/test", None, terminar)
        resuelto, self._resuelto = self._resuelto, None
        return True if resuelto is None else resuelto

    # ── propiedades ───────────────────────────────────────────────────
    @Property(bool, notify=datosChanged)
    def envioActivo(self) -> bool:
        return self._correo.get("envio_activo") is True

    @Property("QVariantList", notify=datosChanged)
    def destinatarios(self) -> list:
        lista = self._correo.get("destinatarios")
        return [dict(d) for d in lista if isinstance(d, dict)] if isinstance(lista, list) else []

    @Property(str, notify=datosChanged)
    def remitente(self) -> str:
        return str(self._correo.get("remitente") or "")

    @Property(str, notify=datosChanged)
    def servidor(self) -> str:
        s = str(self._correo.get("servidor") or "")
        p = self._correo.get("puerto")
        return f"{s}:{p}" if s and isinstance(p, int) else s

    @Property(bool, notify=datosChanged)
    def contrasenaConfigurada(self) -> bool:
        return self._correo.get("contrasena_configurada") is True

    @Property(int, notify=datosChanged)
    def maxDestinatarios(self) -> int:
        v = self._correo.get("max_destinatarios")
        return v if isinstance(v, int) else 10

    @Property("QVariantList", notify=datosChanged)
    def adaptadores(self) -> list:
        lista = self._red.get("adaptadores")
        return [dict(a) for a in lista if isinstance(a, dict)] if isinstance(lista, list) else []

    @Property(str, notify=datosChanged)
    def wifiSsid(self) -> str:
        return str((self._red.get("wifi") or {}).get("ssid") or "")

    @Property(int, notify=datosChanged)
    def wifiSenal(self) -> int:
        v = (self._red.get("wifi") or {}).get("senal")
        return v if isinstance(v, int) else -1

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


qmlRegisterType(ConectividadController, "Autoclave.Controllers", 1, 0, "ConectividadController")

# ui_qml/controllers/manejo_ciclos_controller.py
#
# OPCIONES › Opciones avanzadas › Manejo de ciclos (C9, tanda 9, D9-10). Antes
# estos botones vivían en Parámetros del ciclo (O1, tanda 5). Usa los
# endpoints existentes:
#   - GET /programas (lista);
#   - POST /programas/{n}/duplicar {nombre[, crear]} — "Crear" = duplicar un
#     programa existente con un nombre nuevo (Q2); `crear` solo cambia el
#     evento de la bitácora (programa_creado);
#   - PUT /programas/{n}/habilitado {habilitado};
#   - DELETE /programas/{n} (solo personalizados; el backend rechaza los de
#     fábrica y el programa seleccionado).
# El backend es la autoridad (rol, fuera de ciclo, nombre válido y único). Un
# resultado sin respuesta es incierto: la lista se relee siempre.
#
# Sin HTTP síncrono en la GUI para habilitar / deshabilitar y para leer
# (AJUSTES 2026-11-02, paso 2 fase 4):
#   - Habilitar / deshabilitar: cambio optimista con reversión (CambioOptimista;
#     clave "habilitado:<n>"); el optimismo es solo local de esta pantalla.
#   - Lista: GET asíncrono con `cargando`.
#   - Crear, duplicar y borrar siguen síncronos (operaciones raras y con
#     confirmación; el resultado manda la lista que se relee).
# Los slots devuelven el `ok` real si el resultado llegó en el acto (sesión de
# prueba con solo `enviar`); en vuelo, True («aceptado»).

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtQml import qmlRegisterType

from autoclave.ui_qml import sesion_backend
from autoclave.ui_qml.cambio_optimista import SIN_CONFIRMAR, SIN_LECTURA, CambioOptimista

# Código del backend -> clave del catálogo
_MENSAJES = {
    "estado_no_permitido": "manejo_ciclos.err_estado",
    "rol_sin_permiso": "manejo_ciclos.err_rol",
    "sesion_invalida": "manejo_ciclos.err_identidad",
    "VALOR_INVALIDO": "manejo_ciclos.err_nombre_invalido",
    "nombre_repetido": "manejo_ciclos.err_nombre_repetido",
    "programa_activo": "manejo_ciclos.err_programa_activo",
    "programa_de_fabrica": "manejo_ciclos.err_de_fabrica",
    "PROGRAMA_NO_EDITABLE": "manejo_ciclos.err_no_duplicable",
    "programa_no_encontrado": "manejo_ciclos.err_no_encontrado",
    "programa_existente": "manejo_ciclos.err_generico",
    "BASE_OCUPADA": "manejo_ciclos.err_base_ocupada",
    sesion_backend.BACKEND_NO_RESPONDE: "manejo_ciclos.err_sin_respuesta",
}


MENSAJE_SIN_CONFIRMAR = "opciones.cambio_sin_confirmar"


def mensaje_de(causa: str) -> str:
    return _MENSAJES.get(causa, "manejo_ciclos.err_generico")


def _cancelar_al_destruir(sesion, ident):
    return lambda *_: sesion_backend.cancelar_envios(sesion, ident)


def _filas(datos) -> list | None:
    """Programas operables (cycles/user) de la respuesta de GET /programas;
    None si no es una respuesta válida."""
    if not isinstance(datos, dict):
        return None
    filas = []
    for p in datos.get("programas") or []:
        # solo los programas operables (cycles/user); los de cycles/factory
        # son la referencia de fábrica y no se manejan aquí
        if p.get("origen") != "user":
            continue
        danado = bool(p.get("danado"))
        personalizado = p.get("personalizado") is True
        filas.append({**p, "personalizado": personalizado,
                      "habilitado": p.get("habilitado", True) is not False,
                      "duplicable": not danado,
                      "borrable": personalizado})
    return filas


class ManejoCiclosController(QObject):
    programasChanged = Signal()
    mensajeChanged = Signal()
    pendientesChanged = Signal()
    cargandoChanged = Signal()
    # clave del cambio, aceptado, clave i18n del mensaje ("" si aceptado)
    cambioResuelto = Signal(str, bool, str)

    def __init__(self, parent=None, sesion=None):
        super().__init__(parent)
        self._sesion = sesion
        self._programas: list = []
        self._mensaje = ""
        self._detalle: dict = {}
        self._exito = False
        self._revertido = False            # el mensaje es el motivo de una reversión
        self._gen_carga = 0
        self._cargando = False
        self._resuelto = None              # desenlace síncrono del último slot
        self._opt = CambioOptimista(self._lanzar_habilitado, self._al_cambiar,
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

    def _fijar_mensaje(self, clave: str, detalle: dict | None = None, exito: bool = False,
                       revertido: bool = False) -> None:
        self._mensaje, self._detalle, self._exito = clave, dict(detalle or {}), exito
        self._revertido = revertido
        self.mensajeChanged.emit()

    # ── estado de los envíos ─────────────────────────────────────────
    @Property("QVariantMap", notify=pendientesChanged)
    def pendientes(self) -> dict:
        """clave ("habilitado:<n>") -> "enviando" | "verificando"."""
        return self._opt.pendientes()

    @Property(bool, notify=cargandoChanged)
    def cargando(self) -> bool:
        return self._cargando

    def _fijar_cargando(self, v: bool) -> None:
        if v != self._cargando:
            self._cargando = v
            self.cargandoChanged.emit()

    # ── lista ────────────────────────────────────────────────────────

    @Slot()
    def cargar(self) -> None:
        self._gen_carga += 1
        gen, marca = self._gen_carga, self._opt.marca()
        self._fijar_cargando(True)
        self._enviar("GET", "/programas", None, lambda r: self._al_cargar(r, gen, marca))

    def _al_cargar(self, r, gen, marca) -> None:
        if gen != self._gen_carga:
            return                         # una carga posterior manda
        self._fijar_cargando(False)
        filas = _filas(r.datos) if r.ok else None
        if filas is None:
            self._programas = []
            self.programasChanged.emit()
            self._fijar_mensaje(mensaje_de(r.causa))
            return
        for fila in filas:
            clave = self._clave(fila.get("numero"))
            if not self._opt.confirmar_lectura(clave, fila["habilitado"], marca):
                # cambio pendiente o lectura lanzada antes del último cambio:
                # se conserva lo que se muestra
                previa = next((v for v in self._programas if v.get("numero") == fila.get("numero")), None)
                fila["habilitado"] = self._opt.mostrar(
                    clave, fila["habilitado"] if previa is None else previa["habilitado"])
        self._programas = filas
        self.programasChanged.emit()

    @Property("QVariantList", notify=programasChanged)
    def programas(self) -> list:
        return self._programas

    @Property("QVariantList", notify=programasChanged)
    def bases(self) -> list:
        """Programas que sirven de base para Crear."""
        return [p for p in self._programas if p["duplicable"]]

    def _nombre(self, numero: int) -> str:
        return next((p.get("nombre", "") for p in self._programas if p.get("numero") == numero), "")

    # ── operaciones ──────────────────────────────────────────────────

    def _tras(self, r, clave_ok: str, detalle: dict) -> bool:
        self.cargar()         # sin respuesta el resultado es incierto: se relee siempre
        if r.ok:
            self._fijar_mensaje(clave_ok, detalle, exito=True)
            return True
        self._fijar_mensaje(mensaje_de(r.causa))
        return False

    def _duplicar(self, numero: int, nombre: str, crear: bool) -> bool:
        nombre = " ".join(str(nombre or "").split())
        if not nombre:
            self._fijar_mensaje("manejo_ciclos.err_nombre_invalido")
            return False
        cuerpo = {"nombre": nombre, "crear": True} if crear else {"nombre": nombre}
        r = self._s().enviar("POST", f"/programas/{int(numero)}/duplicar", cuerpo)
        datos = r.datos if r.ok and isinstance(r.datos, dict) else {}
        return self._tras(r, "manejo_ciclos.ok_creado",
                          {"nombre": datos.get("nombre", nombre), "numero": datos.get("numero")})

    @Slot(int, str, result=bool)
    def crear(self, numero_base: int, nombre: str) -> bool:
        return self._duplicar(numero_base, nombre, True)

    @Slot(int, str, result=bool)
    def duplicar(self, numero: int, nombre: str) -> bool:
        return self._duplicar(numero, nombre, False)

    # ── habilitar / deshabilitar: optimista con reversión ────────────

    @staticmethod
    def _clave(numero) -> str:
        return f"habilitado:{numero}"

    @staticmethod
    def _numero(clave: str) -> int:
        return int(clave.split(":", 1)[1])

    def _lanzar_habilitado(self, clave, valor, al_terminar) -> None:
        # la respuesta tardía (tras backend_no_responde) no pasa por el cambio
        # optimista: se relee la lista, y la marca protege lo aún pendiente
        self._enviar("PUT", f"/programas/{self._numero(clave)}/habilitado",
                     {"habilitado": bool(valor)}, al_terminar,
                     al_tardio=lambda _r: self.cargar())

    def _releer(self, clave, al_leer) -> None:
        def leido(r):
            filas = _filas(r.datos) if r.ok else None
            fila = None if filas is None else next(
                (f for f in filas if f.get("numero") == self._numero(clave)), None)
            al_leer(SIN_LECTURA if fila is None else fila["habilitado"])
        self._enviar("GET", "/programas", None, leido)

    def _al_cambiar(self, clave, valor) -> None:
        numero = self._numero(clave)
        for p in self._programas:
            if p.get("numero") == numero and p["habilitado"] != bool(valor):
                p["habilitado"] = bool(valor)
                self.programasChanged.emit()
                return

    def _al_confirmar(self, clave) -> None:
        self._resuelto = True
        habilitado = bool(self._opt.confirmado(clave, True))
        nombre = self._nombre(self._numero(clave))
        self.cargar()                      # se relee siempre; el éxito se anuncia después
        self._fijar_mensaje("manejo_ciclos.ok_habilitado" if habilitado
                            else "manejo_ciclos.ok_deshabilitado", {"nombre": nombre}, exito=True)
        self.cambioResuelto.emit(clave, True, "")

    def _al_revertir(self, clave, causa) -> None:
        self._resuelto = False
        if causa == SIN_CONFIRMAR:
            self._fijar_mensaje(MENSAJE_SIN_CONFIRMAR)
            self.cargar()                  # mostrar el estado real
        else:
            self._fijar_mensaje(mensaje_de(causa), revertido=True)
        self.cambioResuelto.emit(clave, False, self._mensaje)

    @Slot(int, bool, result=bool)
    def fijarHabilitado(self, numero: int, habilitado: bool) -> bool:
        clave = self._clave(int(numero))
        fila = next((p for p in self._programas if p.get("numero") == int(numero)), None)
        self._resuelto = None
        if fila is None:
            self._opt.aplicar(clave, bool(habilitado))
        else:
            self._opt.aplicar(clave, bool(habilitado), fila["habilitado"])
        resuelto, self._resuelto = self._resuelto, None
        return True if resuelto is None else resuelto

    @Slot(int, result=bool)
    def borrar(self, numero: int) -> bool:
        nombre = self._nombre(numero)
        r = self._s().enviar("DELETE", f"/programas/{int(numero)}")
        return self._tras(r, "manejo_ciclos.ok_borrado", {"nombre": nombre})

    # ── mensajes ─────────────────────────────────────────────────────

    @Property(str, notify=mensajeChanged)
    def mensaje(self) -> str:
        return self._mensaje

    @Property("QVariantMap", notify=mensajeChanged)
    def detalleMensaje(self) -> dict:
        return self._detalle

    @Property(bool, notify=mensajeChanged)
    def mensajeRevertido(self) -> bool:
        """El mensaje es el motivo de un cambio que no se aplicó: la pantalla
        lo muestra dentro de opciones.cambio_revertido."""
        return self._revertido

    @Property(bool, notify=mensajeChanged)
    def exito(self) -> bool:
        return self._exito

    @Slot()
    def limpiarMensaje(self) -> None:
        self._fijar_mensaje("")


qmlRegisterType(ManejoCiclosController, "Autoclave.Controllers", 1, 0, "ManejoCiclosController")

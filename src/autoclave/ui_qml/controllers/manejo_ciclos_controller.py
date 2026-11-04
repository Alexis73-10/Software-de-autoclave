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
#   - Crear, duplicar y borrar (FASE 6, P1): `OperacionCritica` sin optimismo,
#     una a la vez (clave "programa"), plazo 10 s, bloquean la navegación. Solo
#     un 200 o una relectura de GET /programas que lo demuestre (aparece el
#     programa nuevo / ya no está el borrado) es éxito; sin respuesta y sin
#     esa prueba queda «sin confirmar»; no hay reintento automático. El slot
#     devuelve True = «enviado»; el resultado llega por `operacionResuelta`.
# Habilitar / deshabilitar devuelve el `ok` real si el resultado llegó en el
# acto (sesión de prueba con solo `enviar`); en vuelo, True («aceptado»).

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtQml import qmlRegisterType

from autoclave.ui_qml import operacion_critica as oc
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
CLAVE_PROGRAMA = "programa"          # crear, duplicar y borrar: una a la vez
PLAZO_PROGRAMA_S = 10.0
MENSAJE_PROGRAMA_SIN_CONFIRMAR = "manejo_ciclos.err_sin_respuesta"


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
    operacionEnCursoChanged = Signal()
    # clave, estado final (confirmada|rechazada|sin_confirmar), clave i18n del mensaje
    operacionResuelta = Signal(str, str, str)

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
        self._op = oc.OperacionCritica(self, self._s)
        self._op.operacionEnCursoChanged.connect(self.operacionEnCursoChanged)
        self._op.operacionResuelta.connect(self._al_resolver)
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

    @Property(bool, notify=operacionEnCursoChanged)
    def operacionEnCurso(self) -> bool:
        """Hay un crear / duplicar / borrar en vuelo (la pantalla bloquea los botones)."""
        return self._op.operacionEnCurso

    @Slot(str, result=str)
    def estadoDe(self, clave: str) -> str:
        """inactiva | enviando | verificando."""
        return self._op.estado(clave)

    def _releer_programas(self, al_leido) -> None:
        """Relectura de la operación crítica: aplica la lista si es válida (una
        lectura fallida no vacía la que se muestra) y entrega las filas."""
        def leido(r) -> None:
            filas = _filas(r.datos) if r.ok else None
            if filas is not None:
                self._gen_carga += 1       # manda sobre cargas lanzadas antes
                self._fijar_cargando(False)
                self._programas = filas
                self.programasChanged.emit()
            al_leido(SIN_LECTURA if filas is None else filas)
        self._enviar("GET", "/programas", None, leido)

    def _iniciar_programa(self, metodo, ruta, cuerpo, ok_clave, detalle, conciliar,
                          nombre_ok=None, borra=None) -> bool:
        if self._op.en_curso(CLAVE_PROGRAMA):
            return False                   # una a la vez
        # MAYOR-1 (corrección tras revisión): el contexto va con SU operación
        # (contexto_resuelta), no en el controlador: un 200 tardío de un
        # duplicar no reescribe lo que anuncia la vigente
        ctx = {"clave": ok_clave, "detalle": dict(detalle), "borra": borra}

        def al_ok(r) -> None:
            datos = r.datos if isinstance(r.datos, dict) else {}
            if nombre_ok is not None:
                ctx["detalle"] = {"nombre": datos.get("nombre", nombre_ok),
                                  "numero": datos.get("numero")}
            self.cargar()

        return self._op.iniciar(
            CLAVE_PROGRAMA, metodo, ruta, cuerpo, plazo_s=PLAZO_PROGRAMA_S, al_ok=al_ok,
            al_rechazo=lambda r: mensaje_de(r.causa), releer=self._releer_programas,
            conciliar=conciliar, bloquea_navegacion=True,
            msg_sin_confirmar=MENSAJE_PROGRAMA_SIN_CONFIRMAR, contexto=ctx)

    @Slot(int, result=bool)
    def borrando(self, numero: int) -> bool:
        return self._borrando(int(numero))

    def _borrando(self, numero) -> bool:
        """MENOR-6: hay un borrado del programa `numero` en vuelo."""
        ctx = self._op.contexto_de(CLAVE_PROGRAMA)
        return isinstance(ctx, dict) and ctx.get("borra") == numero

    def _al_resolver(self, clave: str, estado: str, mensaje: str) -> None:
        ctx = self._op.contexto_resuelta if isinstance(self._op.contexto_resuelta, dict) else {}
        if estado == oc.CONFIRMADA:
            self._fijar_mensaje(ctx.get("clave", ""), ctx.get("detalle"), exito=True)
        else:
            self._fijar_mensaje(mensaje)
            self.cargar()         # sin éxito demostrado: se muestra el estado real
        self.operacionResuelta.emit(clave, estado, mensaje)

    def _duplicar(self, numero: int, nombre: str, crear: bool) -> bool:
        """True = enviada; False sin enviar (nombre vacío, o ya hay una en curso)."""
        nombre = " ".join(str(nombre or "").split())
        if not nombre:
            self._fijar_mensaje("manejo_ciclos.err_nombre_invalido")
            return False
        cuerpo = {"nombre": nombre, "crear": True} if crear else {"nombre": nombre}
        # MENOR-5: la prueba «aparece uno nuevo» solo vale contra una lista
        # previa cargada; sin ella (cargando o vacía) no se concilia
        lista_valida = not self._cargando and bool(self._programas)
        previos = {p.get("numero") for p in self._programas}

        def conciliar(filas):
            # el programa nuevo aparece en la lista releída
            aparece = any(f.get("nombre") == nombre and f.get("numero") not in previos
                          for f in filas)
            return oc.CONFIRMADA if aparece else oc.SIN_CONFIRMAR

        return self._iniciar_programa("POST", f"/programas/{int(numero)}/duplicar", cuerpo,
                                      "manejo_ciclos.ok_creado", {"nombre": nombre},
                                      conciliar if lista_valida else None, nombre_ok=nombre)

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
        if self._borrando(int(numero)):
            return False                   # MENOR-6: no con el borrado de ese programa en vuelo
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
        """True = enviada; False sin enviar (ya hay una operación en curso, o
        un habilitar / deshabilitar de ese programa en vuelo: MENOR-6)."""
        nombre = self._nombre(numero)
        n = int(numero)
        if self._clave(n) in self._opt.pendientes():
            return False

        def conciliar(filas):
            # el programa borrado ya no está en la lista releída
            return oc.SIN_CONFIRMAR if any(f.get("numero") == n for f in filas) else oc.CONFIRMADA

        return self._iniciar_programa("DELETE", f"/programas/{n}", None,
                                      "manejo_ciclos.ok_borrado", {"nombre": nombre}, conciliar,
                                      borra=n)

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

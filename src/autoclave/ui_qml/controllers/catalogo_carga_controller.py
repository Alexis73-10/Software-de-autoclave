# ui_qml/controllers/catalogo_carga_controller.py
#
# OPCIONES › Catálogo de carga (RCB-08.1/08.2/08.3, registro de la carga con
# lector, 19-nov; docs/mis_plans/planeacion_registro_carga.md §9; mockup
# docs/diseno/mockups/registro_carga/rcb_3_catalogo.png). Ingeniero y admin.
#
# - Lista: GET /carga/catalogo (todos, activos y de baja) con un filtro local
#   por código o nombre, sin distinguir mayúsculas.
# - Alta: POST /carga/catalogo {codigo, nombre}; el código se lee con el lector
#   (el diálogo de alta captura la lectura) o se escribe con el teclado. Se
#   valida antes de enviar con las reglas compartidas
#   (core/runtime/registro_carga.validar_codigo / validar_nombre).
# - Editar nombre y Dar de baja / Reactivar: PATCH /carga/catalogo/{id}.
# - Importar CSV (RCB-08.3): GET /carga/catalogo/usb (CSV en la raíz de cada
#   USB), POST /carga/catalogo/importar sin aplicar (vista previa con la
#   huella) y, con «Aplicar», la misma ruta con aplicar=true y la huella de la
#   vista previa (todo o nada; 409 csv_cambio si el archivo cambió).
#
# La bitácora la escribe el backend. Ningún HTTP síncrono en la GUI: todo pasa
# por sesion_backend.enviar_async. Los mensajes son claves i18n
# (`mensaje`, con `mensajeArgs` para los textos con valores y `mensajeMotivo`
# para el motivo de un CSV no válido). Nada aquí toca el control del ciclo.

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtQml import qmlRegisterType

from autoclave.core.runtime import registro_carga as rc
from autoclave.ui_qml import sesion_backend

RUTA = "/carga/catalogo"
RUTA_USB = "/carga/catalogo/usb"
RUTA_IMPORTAR = "/carga/catalogo/importar"

_MENSAJES = {
    "codigo_existe": "registro_carga.err_codigo_existe",
    "validacion": "registro_carga.err_validacion",
    "sin_cambios": "registro_carga.err_generico",
    "no_existe": "registro_carga.err_generico",
    "rol_sin_permiso": "registro_carga.err_rol",
    "usb_no_detectada": "registro_carga.err_usb",
    "archivo_no_encontrado": "registro_carga.err_usb",
    "archivo_invalido": "registro_carga.err_usb",
    "csv_invalido": "registro_carga.err_csv",
    "csv_cambio": "registro_carga.err_csv_cambio",
    "bd_no_disponible": "registro_carga.err_generico",
    "sesion_invalida": "opciones.err_identidad",
    sesion_backend.BACKEND_NO_RESPONDE: "opciones.err_sin_respuesta",
}
MENSAJE_GENERICO = "registro_carga.err_generico"
# Mensajes de éxito (la banda se pinta en verde)
EXITOS = frozenset({"registro_carga.guardado", "registro_carga.importado"})

_MOTIVOS = frozenset({"vacio", "largo", "caracter", "tipo", "duplicado", "columnas",
                      "codificacion", "sin_encabezado", "muchas_filas", "muy_grande",
                      "ilegible"})


def mensaje_de(causa: str) -> str:
    return _MENSAJES.get(causa, MENSAJE_GENERICO)


def clave_motivo(motivo) -> str:
    """Clave i18n de un motivo de rechazo (línea del CSV o archivo)."""
    return f"registro_carga.motivo_{motivo}" if motivo in _MOTIVOS else "registro_carga.motivo_tipo"


def filtrar(elementos: list[dict], texto: str) -> list[dict]:
    """Filtro local por código o nombre, sin distinguir mayúsculas."""
    t = (texto or "").strip().casefold()
    if not t:
        return list(elementos)
    return [e for e in elementos
            if t in str(e.get("codigo", "")).casefold() or t in str(e.get("nombre", "")).casefold()]


def _tamano(b) -> str:
    if not isinstance(b, (int, float)) or b < 0:
        return ""
    if b < 1024:
        return f"{int(b)} B"
    if b < 1024 * 1024:
        return f"{b / 1024:.1f} KB"
    return f"{b / (1024 * 1024):.1f} MB"


def _cancelar_al_destruir(sesion, ident):
    return lambda *_: sesion_backend.cancelar_envios(sesion, ident)


class CatalogoCargaController(QObject):
    datosChanged = Signal()
    filtroChanged = Signal()
    mensajeChanged = Signal()
    cargandoChanged = Signal()
    enviandoChanged = Signal()
    usbChanged = Signal()
    vistaChanged = Signal()
    # alta resuelta: aceptada, clave i18n del mensaje ("" si aceptada)
    altaResuelta = Signal(bool, str)
    # edición (nombre o activo) resuelta: id, aceptada, mensaje
    edicionResuelta = Signal(int, bool, str)
    # importación aplicada (True) o rechazada (False), mensaje
    importacionResuelta = Signal(bool, str)

    def __init__(self, parent=None, sesion=None):
        super().__init__(parent)
        self._sesion = sesion
        self._todos: list[dict] = []
        self._filtro = ""
        self._mensaje = ""
        self._args: dict = {}
        self._motivo = ""
        self._cargando = False
        self._enviando = False
        self._gen = 0
        self._usb_gen = 0
        self._cargando_usb = False
        self._unidades: list[dict] = []
        self._vista: dict = {}
        self._origen_vista: tuple = ()        # (unidad, archivo, huella)
        self.destroyed.connect(_cancelar_al_destruir(sesion, id(self)))

    # ── utilidades ─────────────────────────────────────────────────────
    def _s(self):
        return self._sesion or sesion_backend.ventana()

    def _enviar(self, metodo, ruta, cuerpo, al_terminar) -> None:
        sesion_backend.enviar_async(self._s(), metodo, ruta, cuerpo, al_terminar, dueno=self)

    def _fijar_mensaje(self, clave: str, args: dict | None = None, motivo: str = "") -> None:
        args = dict(args or {})
        if (clave, args, motivo) != (self._mensaje, self._args, self._motivo):
            self._mensaje, self._args, self._motivo = clave, args, motivo
            self.mensajeChanged.emit()

    def _fijar_cargando(self, v: bool) -> None:
        if v != self._cargando:
            self._cargando = v
            self.cargandoChanged.emit()

    def _fijar_enviando(self, v: bool) -> None:
        if v != self._enviando:
            self._enviando = v
            self.enviandoChanged.emit()

    def _rechazo(self, r) -> str:
        """Fija el mensaje de un rechazo y devuelve su clave."""
        clave = mensaje_de(r.causa)
        datos = r.datos if isinstance(r.datos, dict) else {}
        motivo = clave_motivo(datos.get("motivo")) if r.causa == "csv_invalido" else ""
        self._fijar_mensaje(clave, motivo=motivo)
        return clave

    # ── lista ──────────────────────────────────────────────────────────
    @Slot()
    def cargar(self) -> None:
        self._gen += 1
        gen = self._gen
        self._fijar_cargando(True)
        self._enviar("GET", RUTA, None, lambda r: self._al_cargar(r, gen))

    def _al_cargar(self, r, gen: int) -> None:
        if gen != self._gen:
            return                          # una lectura posterior manda
        self._fijar_cargando(False)
        lista = r.datos.get("elementos") if r.ok and isinstance(r.datos, dict) else None
        if isinstance(lista, list):
            self._todos = [self._normalizar(e) for e in lista if isinstance(e, dict)]
            self.datosChanged.emit()
        else:
            self._rechazo(r)                # se conserva la última lista válida

    @staticmethod
    def _normalizar(e: dict) -> dict:
        activo = bool(e.get("activo"))
        return {"id": int(e.get("id") or 0), "codigo": str(e.get("codigo") or ""),
                "nombre": str(e.get("nombre") or ""), "activo": activo,
                "claveEstado": "registro_carga.estado_activo" if activo
                               else "registro_carga.estado_baja"}

    def _get_filtro(self) -> str:
        return self._filtro

    def _set_filtro(self, v) -> None:
        v = v or ""
        if v != self._filtro:
            self._filtro = v
            self.filtroChanged.emit()
            self.datosChanged.emit()

    filtro = Property(str, _get_filtro, _set_filtro, notify=filtroChanged)

    @Property("QVariantList", notify=datosChanged)
    def elementos(self) -> list:
        return filtrar(self._todos, self._filtro)

    @Property(int, notify=datosChanged)
    def total(self) -> int:
        return len(self._todos)

    @Property(int, notify=datosChanged)
    def activos(self) -> int:
        return sum(1 for e in self._todos if e["activo"])

    @Property(int, notify=datosChanged)
    def deBaja(self) -> int:
        return sum(1 for e in self._todos if not e["activo"])

    @Property(str, notify=datosChanged)
    def claveVacio(self) -> str:
        """"" si hay filas que mostrar; si no, el texto de la lista vacía."""
        if self.elementos:
            return ""
        return "registro_carga.catalogo_sin_coincidencias" if self._todos \
            else "registro_carga.catalogo_vacio"

    @Slot(int, result="QVariantMap")
    def elemento(self, id_: int) -> dict:
        return next((dict(e) for e in self._todos if e["id"] == id_), {})

    # ── validación local (reglas compartidas con el backend) ──────────
    @Slot(str, result=str)
    def validarCodigo(self, texto: str) -> str:
        """"" si el código es válido; si no, la clave i18n del aviso."""
        _, motivo = rc.validar_codigo(texto)
        return "" if motivo is None else "registro_carga.lectura_invalida"

    @Slot(str, result=str)
    def normalizarCodigo(self, texto: str) -> str:
        codigo, _ = rc.validar_codigo(texto)
        return codigo or ""

    @Slot(str, result=str)
    def validarNombre(self, texto: str) -> str:
        _, motivo = rc.validar_nombre(texto)
        return "" if motivo is None else "registro_carga.err_validacion"

    @Property(int, constant=True)
    def largoCodigo(self) -> int:
        return rc.LONGITUD_MAX_CODIGO

    @Property(int, constant=True)
    def largoNombre(self) -> int:
        return rc.LONGITUD_MAX_NOMBRE

    # ── alta ───────────────────────────────────────────────────────────
    @Slot(str, str, result=bool)
    def alta(self, codigo: str, nombre: str) -> bool:
        """False si no se envía (validación local o ya hay un envío en vuelo).
        El desenlace llega por `altaResuelta`."""
        if self._enviando:
            return False
        cod, motivo = rc.validar_codigo(codigo)
        nom, motivo_n = rc.validar_nombre(nombre) if motivo is None else (None, motivo)
        if motivo or motivo_n:
            self._fijar_mensaje("registro_carga.err_validacion")
            self.altaResuelta.emit(False, "registro_carga.err_validacion")
            return False
        self._fijar_enviando(True)
        self._enviar("POST", RUTA, {"codigo": cod, "nombre": nom}, self._al_alta)
        return True

    def _al_alta(self, r) -> None:
        self._fijar_enviando(False)
        if r.ok:
            self._fijar_mensaje("registro_carga.guardado")
            self.altaResuelta.emit(True, "")
            self.cargar()
        else:
            self.altaResuelta.emit(False, self._rechazo(r))

    # ── editar nombre, baja / reactivar ──────────────────────────────
    @Slot(int, str, result=bool)
    def editarNombre(self, id_: int, nombre: str) -> bool:
        nom, motivo = rc.validar_nombre(nombre)
        if motivo or self._enviando or not self.elemento(id_):
            if motivo:
                self._fijar_mensaje("registro_carga.err_validacion")
            return False
        return self._modificar(id_, {"nombre": nom})

    @Slot(int, bool, result=bool)
    def fijarActivo(self, id_: int, activo: bool) -> bool:
        if self._enviando or not self.elemento(id_):
            return False
        return self._modificar(id_, {"activo": bool(activo)})

    def _modificar(self, id_: int, cuerpo: dict) -> bool:
        self._fijar_enviando(True)
        self._enviar("PATCH", f"{RUTA}/{int(id_)}", cuerpo, lambda r: self._al_modificar(r, id_))
        return True

    def _al_modificar(self, r, id_: int) -> None:
        self._fijar_enviando(False)
        if r.ok:
            self._fijar_mensaje("registro_carga.guardado")
            self.edicionResuelta.emit(id_, True, "")
        else:
            self.edicionResuelta.emit(id_, False, self._rechazo(r))
        self.cargar()                      # también tras un rechazo (p. ej. no_existe)

    # ── importar CSV ───────────────────────────────────────────────────
    @Property(bool, notify=usbChanged)
    def cargandoUsb(self) -> bool:
        return self._cargando_usb

    @Slot()
    def cargarUsb(self) -> None:
        self._usb_gen += 1
        gen = self._usb_gen
        self._cargando_usb = True
        self.usbChanged.emit()
        self._enviar("GET", RUTA_USB, None, lambda r: self._al_cargar_usb(r, gen))

    def _al_cargar_usb(self, r, gen: int) -> None:
        if gen != self._usb_gen:
            return
        self._cargando_usb = False
        u = r.datos.get("unidades") if r.ok and isinstance(r.datos, dict) else None
        if isinstance(u, list):
            self._unidades = [x for x in u if isinstance(x, dict)]
        else:
            self._unidades = []
            self._rechazo(r)
        self.usbChanged.emit()

    @Property("QVariantList", notify=usbChanged)
    def archivosUsb(self) -> list:
        """[{unidad, archivo, tamano}] de todas las USB detectadas."""
        salida = []
        for u in self._unidades:
            ruta = str(u.get("ruta") or "")
            archivos = u.get("archivos") if isinstance(u.get("archivos"), list) else []
            for a in archivos:
                if isinstance(a, dict) and a.get("archivo"):
                    salida.append({"unidad": ruta, "archivo": str(a["archivo"]),
                                   "tamano": _tamano(a.get("bytes"))})
        return salida

    @Slot(str, str, result=bool)
    def verVistaPrevia(self, unidad: str, archivo: str) -> bool:
        """Pide la vista previa (aplicar=false). False si ya hay un envío."""
        if self._enviando or not unidad or not archivo:
            return False
        self._limpiar_vista()
        self._fijar_enviando(True)
        self._enviar("POST", RUTA_IMPORTAR, {"unidad": unidad, "archivo": archivo, "aplicar": False},
                     lambda r: self._al_vista(r, unidad, archivo))
        return True

    def _al_vista(self, r, unidad: str, archivo: str) -> None:
        self._fijar_enviando(False)
        datos = r.datos if isinstance(r.datos, dict) else {}
        if r.ok and isinstance(datos.get("huella"), str):
            self._vista = {**datos, "archivo": archivo}
            self._origen_vista = (unidad, archivo, datos["huella"])
            self._fijar_mensaje("")
            self.vistaChanged.emit()
        else:
            self._rechazo(r)

    def _limpiar_vista(self) -> None:
        if self._vista or self._origen_vista:
            self._vista, self._origen_vista = {}, ()
            self.vistaChanged.emit()

    @Slot()
    def cancelarImportacion(self) -> None:
        self._limpiar_vista()

    @Property(bool, notify=vistaChanged)
    def hayVistaPrevia(self) -> bool:
        return bool(self._origen_vista)

    @Property("QVariantMap", notify=vistaChanged)
    def vistaPrevia(self) -> dict:
        """Conteos de la vista previa: archivo, altas, cambios, reactivados,
        sinCambio y rechazadas (números)."""
        v = self._vista

        def n(clave):
            x = v.get(clave)
            return len(x) if isinstance(x, list) else 0
        sin = v.get("sin_cambio")
        return {"archivo": str(v.get("archivo") or ""), "altas": n("altas"),
                "cambios": n("cambios"), "reactivados": n("reactivados"),
                "sinCambio": int(sin) if isinstance(sin, int) else 0,
                "rechazadas": n("rechazadas")}

    @Property("QVariantList", notify=vistaChanged)
    def lineasRechazadas(self) -> list:
        """[{linea, motivo (clave i18n), texto}] de la vista previa."""
        filas = self._vista.get("rechazadas")
        if not isinstance(filas, list):
            return []
        return [{"linea": int(f.get("linea") or 0), "motivo": clave_motivo(f.get("motivo")),
                 "texto": str(f.get("texto") or "")}
                for f in filas if isinstance(f, dict)]

    @Property(bool, notify=vistaChanged)
    def aplicable(self) -> bool:
        """Hay algo que aplicar (altas, cambios o reactivaciones)."""
        v = self.vistaPrevia
        return self.hayVistaPrevia and (v["altas"] + v["cambios"] + v["reactivados"]) > 0

    @Slot(result=bool)
    def aplicarImportacion(self) -> bool:
        """Aplica la vista previa vigente con su huella (todo o nada)."""
        if self._enviando or not self._origen_vista:
            return False
        unidad, archivo, huella = self._origen_vista
        self._fijar_enviando(True)
        self._enviar("POST", RUTA_IMPORTAR,
                     {"unidad": unidad, "archivo": archivo, "aplicar": True, "huella": huella},
                     self._al_aplicar)
        return True

    def _al_aplicar(self, r) -> None:
        self._fijar_enviando(False)
        datos = r.datos if isinstance(r.datos, dict) else {}
        if r.ok and datos.get("aplicado") is True:
            def n(clave):
                x = datos.get(clave)
                return len(x) if isinstance(x, list) else int(x) if isinstance(x, int) else 0
            self._limpiar_vista()
            self._fijar_mensaje("registro_carga.importado",
                                {"altas": n("altas"), "cambios": n("cambios"),
                                 "reactivados": n("reactivados")})
            self.importacionResuelta.emit(True, "registro_carga.importado")
            self.cargar()
        else:
            if r.ok:                       # 200 sin `aplicado`: no se da por hecho
                clave = MENSAJE_GENERICO
                self._fijar_mensaje(clave)
            else:
                clave = self._rechazo(r)
            if r.causa == "csv_cambio":
                self._limpiar_vista()      # hay que volver a abrir el archivo
            self.importacionResuelta.emit(False, clave)

    # ── estado común ───────────────────────────────────────────────────
    @Property(bool, notify=cargandoChanged)
    def cargando(self) -> bool:
        return self._cargando

    @Property(bool, notify=enviandoChanged)
    def enviando(self) -> bool:
        return self._enviando

    @Property(str, notify=mensajeChanged)
    def mensaje(self) -> str:
        return self._mensaje

    @Property("QVariantMap", notify=mensajeChanged)
    def mensajeArgs(self) -> dict:
        return dict(self._args)

    @Property(str, notify=mensajeChanged)
    def mensajeMotivo(self) -> str:
        return self._motivo

    @Property(bool, notify=mensajeChanged)
    def mensajeExito(self) -> bool:
        return self._mensaje in EXITOS

    @Slot()
    def limpiarMensaje(self) -> None:
        self._fijar_mensaje("")


qmlRegisterType(CatalogoCargaController, "Autoclave.Controllers", 1, 0, "CatalogoCargaController")

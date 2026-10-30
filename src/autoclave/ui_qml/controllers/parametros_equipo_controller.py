# ui_qml/controllers/parametros_equipo_controller.py
#
# OPCIONES › Parámetros del equipo (O2a, tanda 6; mockups 3, 4 y 5 aprobados).
# Entrada con 7 submenús; cada submenú lista sus parámetros (GET /system_params)
# y cada parámetro se ajusta con la misma ventana de Parámetros del ciclo
# (PATCH /global_params/{clave}, POST .../reset). Configuración de la máquina:
# idioma (PUT /language), unidades (PUT /units), serie y modelo (perfil, solo
# lectura). Impresora habilitada (P2, tanda 5) va en Impresión.
#
# Permisos (domain/permisos_opciones, decisión 1.9): la pantalla solo los
# refleja; el backend es la autoridad (403/409).

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtQml import qmlRegisterType

from autoclave.core.managers.config_manager import GRUPOS as _GRUPOS_PARAMETROS
from autoclave.ui_qml import sesion_backend
from autoclave.ui_qml.domain import permisos_opciones as permisos

# Todos los submenús posibles; los que se muestran los entrega el backend ya
# filtrados por el perfil (D9-3, tanda 9). "maquina" va siempre, al final.
GRUPOS = (*_GRUPOS_PARAMETROS, "maquina")

_MENSAJES = {
    "rol_sin_permiso": "opciones.err_rol",
    "sesion_invalida": "opciones.err_identidad",
    "estado_no_permitido": "opciones.equipo_err_ciclo",
    "ARCHIVO_NO_ESCRIBIBLE": "opciones.equipo_err_guardar",
    "sin_base_de_datos": "opciones.equipo_err_guardar",
    "fuera_de_rango": "opciones.equipo_err_rango",
    "tipo_invalido": "opciones.equipo_err_rango",
    "incoherente": "opciones.equipo_err_empaque",
    "solo_lectura": "opciones.equipo_err_solo_lectura",
    "no_existe": "opciones.err_generico",
    "apertura_automatica_no_disponible": "opciones.err_apertura_puertas_simples",
    "estado_no_permitido_unidades": "opciones.equipo_err_unidades_ciclo",
    # R11 (tanda 11, D11-1): reinicio del software al cambiar la impresora
    "reinicio_no_disponible": "opciones.equipo_err_reinicio_no_disponible",
    "apagado_en_curso": "opciones.equipo_err_reinicio_en_curso",
    # SAF-01 de la revisión de R11
    "estado_seguro_activo": "opciones.equipo_err_reinicio_estado_seguro",
    "confirmacion_pendiente": "opciones.equipo_err_reinicio_confirmacion",
    "modo_prueba_activo": "opciones.equipo_err_reinicio_modo_prueba",
    sesion_backend.BACKEND_NO_RESPONDE: "opciones.err_sin_respuesta",
}


def mensaje_de(causa: str) -> str:
    return _MENSAJES.get(causa, "opciones.err_generico")


def _perfil():
    try:
        from autoclave.ui_qml.bridge.info_equipo import cargar_perfil
        return cargar_perfil()
    except Exception:
        return None


class ParametrosEquipoController(QObject):
    datosChanged = Signal()
    mensajeChanged = Signal()
    grupoChanged = Signal()
    permisosChanged = Signal()
    parametrosGrupoChanged = Signal()
    reiniciandoChanged = Signal()

    def __init__(self, parent=None, sesion=None, perfil=None):
        super().__init__(parent)
        self._sesion = sesion
        self._leer_perfil = perfil
        self._impresora = None          # None = se desconoce
        self._unidades = {"temperatura": "", "presion": ""}   # U1; "" = se desconoce
        self._idioma = ""
        self._parametros = []
        self._grupos = list(GRUPOS)     # visibles (backend), con "maquina" al final
        self._grupo = ""                # "" = pantalla de entrada (7 tarjetas)
        self._mensaje = ""
        self._rol = ""
        self._estado = ""
        self._serie = ""
        self._modelo = ""
        self._reiniciando = False       # R11: el backend aceptó reiniciar el software

    def _s(self):
        return self._sesion or sesion_backend.ventana()

    def _fijar_mensaje(self, clave: str) -> None:
        if clave != self._mensaje:
            self._mensaje = clave
            self.mensajeChanged.emit()

    # ── contexto (lo fija la pantalla) ───────────────────────────────────
    def _get_rol(self):
        return self._rol

    def _set_rol(self, v):
        if v != self._rol:
            self._rol = v or ""
            self.permisosChanged.emit()

    def _get_estado(self):
        return self._estado

    def _set_estado(self, v):
        if v != self._estado:
            self._estado = v or ""
            self.permisosChanged.emit()

    rol = Property(str, _get_rol, _set_rol, notify=permisosChanged)
    estadoMaquina = Property(str, _get_estado, _set_estado, notify=permisosChanged)

    @Property(str, notify=permisosChanged)
    def motivoParametro(self) -> str:
        return permisos.motivo_parametro_equipo(self._rol, self._estado)

    @Property(str, notify=permisosChanged)
    def motivoIdioma(self) -> str:
        return permisos.motivo_idioma(self._rol)

    @Property(str, notify=permisosChanged)
    def motivoUnidades(self) -> str:
        return permisos.motivo_unidades(self._rol, self._estado)

    # ── carga ────────────────────────────────────────────────────────────
    @Slot()
    def cargar(self) -> None:
        r = self._s().enviar("GET", "/system_params")
        lista = r.datos.get("parametros") if r.ok and isinstance(r.datos, dict) else None
        if isinstance(lista, list):
            self._parametros = [p for p in lista if isinstance(p, dict)]
            grupos = r.datos.get("grupos")
            # sin la lista (backend anterior a D9-3), todos los submenús
            self._grupos = ([g for g in GRUPOS if g in grupos and g != "maquina"] + ["maquina"]
                            if isinstance(grupos, list) else list(GRUPOS))
            if self._grupo and self._grupo not in self._grupos:
                self._grupo = ""
                self.grupoChanged.emit()
        else:
            self._fijar_mensaje(mensaje_de(r.causa))
        r = self._s().enviar("GET", "/printer/config")
        valor = r.datos.get("habilitada") if r.ok and isinstance(r.datos, dict) else None
        self._impresora = valor if isinstance(valor, bool) else None
        ru = self._s().enviar("GET", "/units")
        datos = ru.datos if ru.ok and isinstance(ru.datos, dict) else {}
        self._unidades = {"temperatura": str(datos.get("temperatura") or ""),
                          "presion": str(datos.get("presion") or "")}
        ri = self._s().enviar("GET", "/language")
        self._idioma = str(ri.datos.get("idioma") or "") if ri.ok and isinstance(ri.datos, dict) else ""
        p = (self._leer_perfil or _perfil)()
        self._serie = str(getattr(p, "serial_number", "") or "") if p else ""
        self._modelo = str(getattr(p, "model_id", "") or "") if p else ""
        self.datosChanged.emit()
        self.parametrosGrupoChanged.emit()

    # ── navegación entre submenús ────────────────────────────────────────
    @Property(str, notify=grupoChanged)
    def grupo(self) -> str:
        return self._grupo

    @Property("QVariantList", notify=datosChanged)
    def grupos(self) -> list:
        """Submenús que se muestran (D9-3), con "maquina" al final."""
        return list(self._grupos)

    @Slot(str)
    def abrirGrupo(self, g: str) -> None:
        g = g if g in self._grupos else ""
        if g != self._grupo:
            self._grupo = g
            self.grupoChanged.emit()
            self.parametrosGrupoChanged.emit()

    @Slot(result=bool)
    def volver(self) -> bool:
        """True si subió de un submenú a la entrada; False si ya estaba arriba."""
        if not self._grupo:
            return False
        self.abrirGrupo("")
        return True

    @Property("QVariantList", notify=datosChanged)
    def parametros(self) -> list:
        return list(self._parametros)

    @Property("QVariantList", notify=parametrosGrupoChanged)
    def parametrosGrupo(self) -> list:
        """D9-4 (tanda 9): parámetros del submenú abierto como propiedad
        notificable; la lista de la pantalla se reevalúa al guardar (cargar()
        la avisa) y al cambiar de submenú. Antes era `delGrupo(grupo)`, una
        llamada que QML no volvía a evaluar con datosChanged."""
        if not self._grupo or self._grupo == "maquina":
            return []
        return self.delGrupo(self._grupo)

    @Slot(str, result="QVariantList")
    def delGrupo(self, g: str) -> list:
        return [p for p in self._parametros if p.get("grupo") == g]

    @Slot(str, result="QVariant")
    def parametro(self, clave: str):
        for p in self._parametros:
            if p.get("clave") == clave:
                return p
        return None

    # ── cambios ──────────────────────────────────────────────────────────
    def _resultado(self, r) -> bool:
        self.cargar()                  # sin respuesta el resultado es incierto: se relee
        if r.ok:
            self._fijar_mensaje("")
            return True
        self._fijar_mensaje(mensaje_de(r.causa))
        return False

    @Slot(str, "QVariant", result=bool)
    def guardar(self, clave: str, valor) -> bool:
        if isinstance(valor, float) and valor.is_integer():
            p = self.parametro(clave) or {}
            if p.get("tipo") == "int":
                valor = int(valor)
        return self._resultado(self._s().enviar("PATCH", f"/global_params/{clave}", {"valor": valor}))

    @Slot(str, result=bool)
    def restablecer(self, clave: str) -> bool:
        return self._resultado(self._s().enviar("POST", f"/global_params/{clave}/reset"))

    @Slot(bool, result=bool)
    def fijarImpresora(self, habilitada: bool) -> bool:
        return self._resultado(self._s().enviar("PUT", "/printer/config",
                                                {"habilitada": bool(habilitada)}))

    @Slot(bool, result=bool)
    def fijarImpresoraYReiniciar(self, habilitada: bool) -> bool:
        """R11 (D11-1): la pantalla ya confirmó "Se reiniciará el software". El
        backend guarda la bandera con auditoría y reinicia; mientras tanto la
        pantalla muestra el aviso de reinicio (sin releer: el backend se está
        cerrando). Rechazado: motivo y se relee, como cualquier cambio."""
        r = self._s().enviar("PUT", "/printer/config",
                             {"habilitada": bool(habilitada), "reiniciar": True})
        if r.ok and isinstance(r.datos, dict) and r.datos.get("reiniciando") is True:
            self._impresora = bool(habilitada)
            self._fijar_mensaje("")
            self._reiniciando = True
            self.datosChanged.emit()
            self.reiniciandoChanged.emit()
            return True
        return self._resultado(r)

    @Property(bool, notify=reiniciandoChanged)
    def reiniciando(self) -> bool:
        return self._reiniciando

    # ── Configuración de la máquina ──────────────────────────────────────
    @Property(str, notify=datosChanged)
    def idioma(self) -> str:
        return self._idioma

    @Slot(str, result=bool)
    def fijarIdioma(self, idioma: str) -> bool:
        r = self._s().enviar("PUT", "/language", {"idioma": idioma})
        if r.ok:
            try:                       # esta ventana cambia ya
                from autoclave import i18n
                i18n.fijar_idioma(idioma)
            except Exception:
                pass
        return self._resultado(r)

    @Property(str, notify=datosChanged)
    def unidadTemperatura(self) -> str:
        return self._unidades["temperatura"]

    @Property(str, notify=datosChanged)
    def unidadPresion(self) -> str:
        return self._unidades["presion"]

    @Slot(str, str, result=bool)
    def fijarUnidades(self, temperatura: str, presion: str) -> bool:
        r = self._s().enviar("PUT", "/units", {"temperatura": temperatura, "presion": presion})
        try:                           # que las pantallas cambien ya, sin esperar el sondeo
            from autoclave.ui_qml.bridge import unidades_qml
            unidades_qml.instancia.refrescar()
        except Exception:
            pass
        ok = self._resultado(r)
        if not ok and r.causa == "estado_no_permitido":
            self._fijar_mensaje("opciones.equipo_err_unidades_ciclo")
        return ok

    @Property(str, notify=datosChanged)
    def numeroSerie(self) -> str:
        return self._serie

    @Property(str, notify=datosChanged)
    def modelo(self) -> str:
        return self._modelo

    @Property(bool, notify=datosChanged)
    def impresoraConocida(self) -> bool:
        return self._impresora is not None

    @Property(bool, notify=datosChanged)
    def impresoraHabilitada(self) -> bool:
        return bool(self._impresora)

    @Property(str, notify=mensajeChanged)
    def mensaje(self) -> str:
        return self._mensaje

    @Slot()
    def limpiarMensaje(self) -> None:
        self._fijar_mensaje("")


qmlRegisterType(ParametrosEquipoController, "Autoclave.Controllers", 1, 0,
                "ParametrosEquipoController")

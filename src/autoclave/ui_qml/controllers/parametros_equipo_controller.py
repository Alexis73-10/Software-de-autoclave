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
#
# Sin HTTP síncrono en la GUI (AJUSTES 2026-11-02, paso 2 fase 2; modelo:
# usuarios_controller):
#   - Idioma, unidades, tema (modo oscuro) e impresora (fijarImpresora): cambio
#     optimista con reversión (CambioOptimista; claves "idioma", "unidades",
#     "tema", "impresora"), SOLO en el selector de esta pantalla. El efecto
#     global (i18n.fijar_idioma, unidades_qml.refrescar, apariencia_qml.fijar)
#     se aplica únicamente tras el 200: al revertir no parpadean °C/°F ni
#     kPa/psi ni el tema, y los sondeos globales no chocan.
#   - Parámetros del equipo (PATCH /global_params/{clave}, POST .../reset):
#     definen el control del proceso. Asíncronos SIN optimismo: lo mostrado es
#     el valor vigente hasta el 200 (se relee) y la clave "param:<clave>"
#     queda en `pendientes` («Guardando…», edición bloqueada) mientras tanto.
#     Tras el 200 pasa a "verificando" y solo se resuelve con la relectura de
#     /system_params (un parámetro del proceso no se da por resuelto antes);
#     si esa relectura falla, la clave queda en `sinConfirmar` (la fila no
#     muestra el valor viejo como vigente) hasta la próxima lectura válida.
#     Sin respuesta (el cambio pudo aplicarse) sigue el mismo camino: la
#     relectura con el valor enviado es éxito; con otro, rechazo con
#     opciones.err_sin_respuesta; si falla, `sinConfirmar`. Si un callback de
#     guardado lanza, la clave se resuelve con fallo (no queda pendiente).
#   - Carga: GET asíncronos con `cargando`. Tras un cambio se relee solo lo
#     afectado (/system_params, o la ruta de idioma/unidades/impresora); una
#     lectura fallida conserva el valor mostrado.
#   - fijarImpresoraYReiniciar (FASE 6, P1): `OperacionCritica` sin optimismo
#     (reinicia el software), plazo 10 s, bloquea la navegación. `reiniciando`
#     solo con el 200 que lo dice; sin respuesta queda «sin confirmar»
#     (opciones.equipo_reinicio_sin_confirmar) y no se relee: el backend se
#     está cerrando y lo que decide es la conectividad. Devuelve True =
#     «enviado»; el resultado llega por `operacionResuelta`.
# Los slots devuelven False si falla la validación local; si el resultado
# llegó en el acto (sesión de prueba con solo `enviar`), el `ok` real; si
# quedó en vuelo, True («aceptado»). El desenlace llega por `cambioResuelto`.

import logging

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtQml import qmlRegisterType

from autoclave.core.managers.config_manager import GRUPOS as _GRUPOS_PARAMETROS
from autoclave.installation.identidad import identidad_de_perfil
from autoclave.ui_qml import operacion_critica as oc
from autoclave.ui_qml import sesion_backend
from autoclave.ui_qml.cambio_optimista import (
    ENVIANDO, SIN_CONFIRMAR, SIN_LECTURA, VERIFICANDO, CambioOptimista)
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
    # A7 (tanda 27): sin detalle reconocible, el texto general de cada familia;
    # con `detalle.regla`, el propio (mensaje_rechazo / _MENSAJES_REGLA)
    "incoherente_empaque": "opciones.equipo_err_empaque",
    "incoherente_limites": "opciones.equipo_err_limites",
    "solo_lectura": "opciones.equipo_err_solo_lectura",
    "no_existe": "opciones.err_generico",
    "calibracion_en_curso": "opciones.equipo_err_calibracion_en_curso",
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
MENSAJE_SIN_CONFIRMAR = "opciones.cambio_sin_confirmar"
MENSAJE_ERROR_INTERNO = "opciones.err_generico"   # un callback de guardado falló

logger = logging.getLogger(__name__)
_SIN_VALOR = object()                   # valor esperado desconocido

# Cambios optimistas: clave -> (ruta de PUT y de relectura)
IDIOMA, UNIDADES, IMPRESORA, TEMA = "idioma", "unidades", "impresora", "tema"
_RUTAS_OPTIMISTAS = {IDIOMA: "/language", UNIDADES: "/units", IMPRESORA: "/printer/config",
                     TEMA: "/theme"}
TEMAS = ("claro", "oscuro")
CLAVE_REINICIO = "impresora_reinicio"          # operación crítica (no optimista)
PLAZO_REINICIO_S = 10.0
MENSAJE_REINICIO_SIN_CONFIRMAR = "opciones.equipo_reinicio_sin_confirmar"
PREFIJO_PARAMETRO = "param:"            # clave de un cambio de /global_params en vuelo


def mensaje_de(causa: str) -> str:
    return _MENSAJES.get(causa, "opciones.err_generico")


# A7 (tanda 27): (código, regla del detalle) -> (clave i18n, marcadores).
# Cada marcador: (de dónde sale el valor en kPa, es_diferencia). "p:<clave>"
# = detalle.propuestos[clave] (o detalle[clave] en empaque); "d:<campo>" =
# detalle[campo] (márgenes). La pantalla los muestra en la unidad vigente
# (diferencia = Unidades.dpres, absoluto = Unidades.pres).
_MENSAJES_REGLA = {
    ("incoherente_empaque", "sin_referencia"): ("opciones.equipo_err_empaque_sin_referencia", {}),
    ("incoherente_empaque", "empaque_sobre_atm"): ("opciones.equipo_err_empaque_sobre_atm", {
        "presion_empaque": ("p:presion_empaque", False),
        "presion_atmosferica": ("p:presion_atmosferica", False),
        "margen_empaque": ("d:margen_empaque_sobre_atm", True)}),
    ("incoherente_empaque", "empaque_chequeo_ciclo"): ("opciones.equipo_err_empaque_chequeo_ciclo", {
        "presion_empaque": ("p:presion_empaque", False),
        "presion_atmosferica": ("p:presion_atmosferica", False)}),
    ("incoherente_empaque", "vacio_bajo_atm"): ("opciones.equipo_err_vacio_bajo_atm", {
        "vacio_empaque": ("p:vacio_empaque", False),
        "presion_atmosferica": ("p:presion_atmosferica", False),
        "margen_vacio": ("d:margen_vacio_bajo_atm", True)}),
    ("incoherente_empaque", "vacio_bajo_empaque"): ("opciones.equipo_err_vacio_bajo_empaque", {
        "vacio_empaque": ("p:vacio_empaque", False),
        "presion_empaque": ("p:presion_empaque", False)}),
    ("incoherente_limites", "sin_referencia"): ("opciones.equipo_err_limites_sin_referencia", {}),
    ("incoherente_limites", "suministro_bajo_alivio"): ("opciones.equipo_err_suministro_bajo_alivio", {
        "suministro": ("p:presion_suministro_vapor", False),
        "alivio_camara": ("p:presion_alivio_camara", False),
        "alivio_chaqueta": ("p:presion_alivio_chaqueta", False)}),
    ("incoherente_limites", "alivio_bajo_fondo"): ("opciones.equipo_err_alivio_bajo_fondo", {
        "alivio_camara": ("p:presion_alivio_camara", False),
        "alivio_chaqueta": ("p:presion_alivio_chaqueta", False),
        "fondo": ("p:presion_fondo_escala", False)}),
    ("incoherente_limites", "corte_bajo_alivio_chaqueta"): ("opciones.equipo_err_corte_bajo_alivio", {
        "corte": ("p:presion_max_chaqueta_control", False),
        "alivio_chaqueta": ("p:presion_alivio_chaqueta", False),
        "margen_corte": ("d:margen_corte_bajo_alivio", True)}),
}


def _numero(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def mensaje_rechazo(causa: str, datos=None) -> tuple[str, dict]:
    """(clave i18n, valores) del rechazo de un parámetro del equipo.
    `valores`: {marcador: {"v": kPa, "dif": bool}}; {} si el texto no lleva
    valores. Un detalle ausente, de otra regla o sin todos los valores da el
    texto general de la familia (nunca el de otra familia)."""
    detalle = datos.get("detalle") if isinstance(datos, dict) else None
    regla = detalle.get("regla") if isinstance(detalle, dict) else None
    entrada = _MENSAJES_REGLA.get((causa, regla))
    if entrada is None:
        return mensaje_de(causa), {}
    clave, marcadores = entrada
    propuestos = detalle.get("propuestos") if isinstance(detalle.get("propuestos"), dict) else {}
    valores = {}
    for nombre, (origen, dif) in marcadores.items():
        tipo, campo = origen.split(":", 1)
        v = _numero(propuestos.get(campo, detalle.get(campo)) if tipo == "p" else detalle.get(campo))
        if v is None:
            return mensaje_de(causa), {}
        valores[nombre] = {"v": v, "dif": dif}
    return clave, valores


def _cancelar_al_destruir(sesion, ident):
    return lambda *_: sesion_backend.cancelar_envios(sesion, ident)


def _resguardado(al_terminar, al_fallar, ruta):
    """Envuelve el callback de un guardado: si lanza, registra la excepción y
    llama a `al_fallar()` para sacar la clave de los pendientes y resolverla."""
    def envuelto(r):
        try:
            al_terminar(r)
        except Exception:
            logger.exception("Fallo en el callback de guardado (%s)", ruta)
            al_fallar()
    return envuelto


def _valor_en(r, clave):
    """Valor de `clave` en una lectura válida de /system_params, o _SIN_VALOR."""
    datos = r.datos if r.ok and isinstance(r.datos, dict) else {}
    for p in datos.get("parametros") or []:
        if isinstance(p, dict) and p.get("clave") == clave:
            return p.get("valor", _SIN_VALOR)
    return _SIN_VALOR


def _leer_idioma(r):
    v = r.datos.get("idioma") if r.ok and isinstance(r.datos, dict) else None
    return str(v) if v else None


def _leer_unidades(r):
    datos = r.datos if r.ok and isinstance(r.datos, dict) else {}
    t, p = datos.get("temperatura"), datos.get("presion")
    return (str(t), str(p)) if t and p else None


def _leer_impresora(r):
    v = r.datos.get("habilitada") if r.ok and isinstance(r.datos, dict) else None
    return v if isinstance(v, bool) else None


def _leer_tema_resp(r):
    v = r.datos.get("tema") if r.ok and isinstance(r.datos, dict) else None
    return v if v in TEMAS else None


_LECTORES = {IDIOMA: _leer_idioma, UNIDADES: _leer_unidades, IMPRESORA: _leer_impresora,
             TEMA: _leer_tema_resp}


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
    pendientesChanged = Signal()
    cargandoChanged = Signal()
    # clave del cambio, aceptado, clave i18n del mensaje ("" si aceptado)
    cambioResuelto = Signal(str, bool, str)
    operacionEnCursoChanged = Signal()
    # clave, estado final (confirmada|rechazada|sin_confirmar), clave i18n del mensaje
    operacionResuelta = Signal(str, str, str)

    def __init__(self, parent=None, sesion=None, perfil=None):
        super().__init__(parent)
        self._sesion = sesion
        self._leer_perfil = perfil
        self._impresora = None          # None = se desconoce
        self._unidades = {"temperatura": "", "presion": ""}   # U1; "" = se desconoce
        self._idioma = ""
        self._tema = ""                 # modo oscuro; "" = se desconoce
        self._parametros = []
        self._grupos = list(GRUPOS)     # visibles (backend), con "maquina" al final
        self._grupo = ""                # "" = pantalla de entrada (7 tarjetas)
        self._mensaje = ""
        self._valores = {}              # A7: valores del mensaje (mensaje_rechazo)
        self._rol = ""
        self._estado = ""
        self._serie = ""
        self._modelo = ""
        self._serial_especifika = ""
        self._reiniciando = False       # R11: el backend aceptó reiniciar el software
        self._revertido = False         # el mensaje es el motivo de una reversión
        self._en_vuelo: dict[str, str] = {}   # cambios de parámetros pendientes
        self._sin_confirmar: set = set()      # aceptados (200) sin relectura válida
        self._gen_carga = 0
        self._gen_param = 0             # lecturas de /system_params lanzadas
        self._gen_param_aplicada = 0    # la más reciente ya aplicada
        self._gen_opt = {IDIOMA: 0, UNIDADES: 0, IMPRESORA: 0, TEMA: 0}
        self._cargas: set = set()
        self._resuelto = None           # desenlace síncrono del último slot
        self._op = oc.OperacionCritica(self, self._s)
        self._op.operacionEnCursoChanged.connect(self.operacionEnCursoChanged)
        self._op.operacionResuelta.connect(self._al_resolver_operacion)
        self._opt = CambioOptimista(self._lanzar_optimista, self._al_cambiar, self._al_revertir,
                                    self._releer, al_confirmar=self._al_confirmar,
                                    al_pendientes=self.pendientesChanged.emit)
        # sin referencia a self: el destructor de C++ ya está en marcha
        self.destroyed.connect(_cancelar_al_destruir(sesion, id(self)))

    def _s(self):
        return self._sesion or sesion_backend.ventana()

    def _enviar(self, metodo, ruta, cuerpo, al_terminar, al_tardio=None, al_fallar=None) -> None:
        """`al_fallar()`: se llama si `al_terminar` lanza una excepción (la
        sesión solo la registraría y el guardado quedaría pendiente para siempre)."""
        if al_fallar is not None:
            al_terminar = _resguardado(al_terminar, al_fallar, ruta)
        sesion_backend.enviar_async(self._s(), metodo, ruta, cuerpo, al_terminar,
                                    dueno=self, al_tardio=al_tardio)

    def _fijar_mensaje(self, clave: str, revertido: bool = False, valores=None) -> None:
        valores = dict(valores or {})
        if clave != self._mensaje or revertido != self._revertido or valores != self._valores:
            self._mensaje = clave
            self._revertido = revertido
            self._valores = valores
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

    # ── estado de los envíos ─────────────────────────────────────────────
    @Property("QVariantMap", notify=pendientesChanged)
    def pendientes(self) -> dict:
        """clave -> "enviando" | "verificando" ("idioma", "unidades",
        "impresora", "param:<clave>")."""
        return {**self._opt.pendientes(), **self._en_vuelo}

    @Property(bool, notify=pendientesChanged)
    def parametroPendiente(self) -> bool:
        """Algún cambio de /global_params espera respuesta (la pantalla no
        sale con Atrás mientras tanto)."""
        return bool(self._en_vuelo)

    @Property("QVariantList", notify=pendientesChanged)
    def sinConfirmar(self) -> list:
        """Claves de parámetros aceptadas por el backend cuya relectura falló:
        la fila se marca «sin confirmar» en vez de mostrar el valor anterior."""
        return sorted(self._sin_confirmar)

    @Property(bool, notify=cargandoChanged)
    def cargando(self) -> bool:
        return bool(self._cargas)

    def _fijar_cargas(self, cargas: set) -> None:
        antes = bool(self._cargas)
        self._cargas = cargas
        if antes != bool(cargas):
            self.cargandoChanged.emit()

    # ── carga ────────────────────────────────────────────────────────────
    @Slot()
    def cargar(self) -> None:
        self._gen_carga += 1
        gen, marca = self._gen_carga, self._opt.marca()
        self._fijar_cargas({"parametros", IMPRESORA, UNIDADES, IDIOMA})
        self._leer_identidad()
        self._leer_parametros(lambda ok, r: self._al_cargar_parametros(ok, r, gen))
        for clave in (IMPRESORA, UNIDADES, IDIOMA):
            self._leer_optimista(clave, marca)
        self._leer_optimista(TEMA, marca)

    def _leer_parametros(self, al_leer=None, al_fallar=None) -> None:
        """GET /system_params; aplica la lista si es la lectura más reciente
        de las que ya respondieron (una lanzada antes no pisa a una posterior).
        `al_leer(ok, r)` recibe si la lectura fue válida; `al_fallar()`, si
        el callback lanzó (ver `_enviar`)."""
        self._gen_param += 1
        gen = self._gen_param

        def leido(r):
            datos = r.datos if r.ok and isinstance(r.datos, dict) else {}
            ok = isinstance(datos.get("parametros"), list)
            if ok and gen > self._gen_param_aplicada:
                self._gen_param_aplicada = gen
                self._aplicar_parametros(datos)
            if al_leer is not None:
                al_leer(ok, r)
        self._enviar("GET", "/system_params", None, leido, al_fallar=al_fallar)

    def _aplicar_parametros(self, datos) -> None:
        self._parametros = [p for p in datos["parametros"] if isinstance(p, dict)]
        grupos = datos.get("grupos")
        # sin la lista (backend anterior a D9-3), todos los submenús
        self._grupos = ([g for g in GRUPOS if g in grupos and g != "maquina"] + ["maquina"]
                        if isinstance(grupos, list) else list(GRUPOS))
        if self._grupo and self._grupo not in self._grupos:
            self._grupo = ""
            self.grupoChanged.emit()
        if self._sin_confirmar:            # una lectura válida dice lo vigente
            self._sin_confirmar.clear()
            self.pendientesChanged.emit()
        self.datosChanged.emit()
        self.parametrosGrupoChanged.emit()

    def _al_cargar_parametros(self, ok, r, gen) -> None:
        if gen != self._gen_carga:
            return                         # una carga posterior manda
        self._fijar_cargas(self._cargas - {"parametros"})
        if not ok:
            self._fijar_mensaje(mensaje_de(r.causa))

    def _leer_optimista(self, clave, marca=None) -> None:
        """GET de idioma, unidades o impresora; solo la última lectura de esa
        clave cuenta."""
        self._gen_opt[clave] += 1
        gen = self._gen_opt[clave]
        marca = self._opt.marca() if marca is None else marca
        self._enviar("GET", _RUTAS_OPTIMISTAS[clave], None,
                     lambda r: self._al_cargar_optimista(r, gen, marca, clave))

    def _al_cargar_optimista(self, r, gen, marca, clave) -> None:
        if gen != self._gen_opt[clave]:
            return                         # una lectura posterior de esa clave manda
        self._fijar_cargas(self._cargas - {clave})
        leido, actual = _LECTORES[clave](r), self._valor_mostrado(clave)
        if leido is None:
            # sin dato: se conserva lo mostrado (no se inventa ni se borra)
            valor = actual
        elif self._opt.confirmar_lectura(clave, leido, marca):
            valor = leido
        else:
            # cambio pendiente o lectura lanzada antes del último cambio
            valor = self._opt.mostrar(clave, actual)
        self._fijar_mostrado(clave, valor)
        self.datosChanged.emit()

    def _valor_mostrado(self, clave):
        if clave == IDIOMA:
            return self._idioma or None
        if clave == TEMA:
            return self._tema or None      # "" = se desconoce
        if clave == UNIDADES:
            t, p = self._unidades["temperatura"], self._unidades["presion"]
            return (t, p) if t and p else None
        return self._impresora

    def _fijar_mostrado(self, clave, valor) -> None:
        if clave == IDIOMA:
            self._idioma = str(valor or "")
        elif clave == TEMA:
            self._tema = valor if valor in TEMAS else ""
        elif clave == UNIDADES:
            t, p = valor if valor else ("", "")
            self._unidades = {"temperatura": str(t), "presion": str(p)}
        else:
            self._impresora = valor if isinstance(valor, bool) else None

    def _leer_identidad(self) -> None:
        p = (self._leer_perfil or _perfil)()
        self._serie = str(getattr(p, "serial_number", "") or "") if p else ""
        self._modelo = str(getattr(p, "model_id", "") or "") if p else ""
        self._serial_especifika = ""
        # Automatización: serie y modelo originales; la serie interna aparte
        ident = identidad_de_perfil(p) if p else None
        if ident is not None and ident["serial_especifika"] is not None:
            self._serie, self._modelo = str(ident["serie"]), str(ident["modelo"])
            self._serial_especifika = str(ident["serial_especifika"])
        self.datosChanged.emit()

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
    # ── parámetros del equipo: asíncronos, sin optimismo ─────────────────
    def _cambio_parametro(self, clave: str, metodo: str, ruta: str, cuerpo,
                          esperado=_SIN_VALOR) -> bool:
        """Lo mostrado sigue siendo el valor vigente hasta que el backend
        acepta y se relee; mientras tanto "param:<clave>" queda pendiente.
        `esperado`: valor que debe leerse si el cambio se aplicó (concilia un
        envío sin respuesta)."""
        pendiente = PREFIJO_PARAMETRO + clave
        if not clave or pendiente in self._en_vuelo:
            return False                   # ese parámetro sigue guardándose
        self._en_vuelo[pendiente] = ENVIANDO
        self.pendientesChanged.emit()
        self._resuelto = None
        estado = {"resuelto": False}       # cambioResuelto una sola vez por guardado

        def resolver(ok, mensaje, valores=None):
            if estado["resuelto"]:
                return
            estado["resuelto"] = True
            self._en_vuelo.pop(pendiente, None)
            self._resuelto = ok
            # los valores quedan antes de cambioResuelto: la ventana los lee
            self._fijar_mensaje(mensaje, valores=valores)
            self.pendientesChanged.emit()
            self.cambioResuelto.emit(pendiente, ok, mensaje)

        def fallar():
            # un callback lanzó: la clave no puede quedar pendiente sin plazo
            if not estado["resuelto"]:
                resolver(False, MENSAJE_ERROR_INTERNO)

        def releido(ok, _r):
            if ok:
                self._sin_confirmar.discard(clave)
                resolver(True, "")
            else:
                # aceptado pero sin relectura: el valor anterior ya no es el vigente
                self._sin_confirmar.add(clave)
                resolver(False, MENSAJE_SIN_CONFIRMAR)

        def conciliado(ok, r, causa):
            # sin respuesta: el PATCH pudo aplicarse; lo dice la relectura (M3)
            if not ok:
                self._sin_confirmar.add(clave)
                resolver(False, MENSAJE_SIN_CONFIRMAR)
                return
            leido = _valor_en(r, clave)
            if esperado is not _SIN_VALOR and leido is not _SIN_VALOR and leido == esperado:
                self._sin_confirmar.discard(clave)
                resolver(True, "")
            else:
                resolver(False, mensaje_de(causa))

        def terminar(r):
            if r.ok or r.causa == sesion_backend.BACKEND_NO_RESPONDE:
                # un parámetro del proceso no se da por resuelto antes de releerlo
                self._en_vuelo[pendiente] = VERIFICANDO
                self.pendientesChanged.emit()
                if r.ok:
                    self._leer_parametros(releido, al_fallar=fallar)
                else:
                    self._leer_parametros(lambda ok, rs: conciliado(ok, rs, r.causa),
                                          al_fallar=fallar)
                return
            self._leer_parametros()        # el valor vigente lo dice el backend
            clave_msg, valores = mensaje_rechazo(r.causa, r.datos)
            resolver(False, clave_msg, valores)

        # una respuesta tardía (tras backend_no_responde) solo relee
        self._enviar(metodo, ruta, cuerpo, terminar, al_tardio=lambda _r: self._leer_parametros(),
                     al_fallar=fallar)
        resuelto, self._resuelto = self._resuelto, None
        return True if resuelto is None else resuelto

    @Slot(str, "QVariant", result=bool)
    def guardar(self, clave: str, valor) -> bool:
        if isinstance(valor, float) and valor.is_integer():
            p = self.parametro(clave) or {}
            if p.get("tipo") == "int":
                valor = int(valor)
        return self._cambio_parametro(clave, "PATCH", f"/global_params/{clave}", {"valor": valor},
                                      esperado=valor)

    @Slot(str, result=bool)
    def restablecer(self, clave: str) -> bool:
        p = self.parametro(clave) or {}
        return self._cambio_parametro(clave, "POST", f"/global_params/{clave}/reset", None,
                                      esperado=p.get("defecto", _SIN_VALOR))

    # ── idioma, unidades, impresora: optimistas con reversión ────────────
    def _lanzar_optimista(self, clave, valor, al_terminar) -> None:
        if clave == IDIOMA:
            cuerpo = {"idioma": valor}
        elif clave == TEMA:
            cuerpo = {"tema": valor}
        elif clave == UNIDADES:
            cuerpo = {"temperatura": valor[0], "presion": valor[1]}
        else:
            cuerpo = {"habilitada": bool(valor)}
        # la respuesta tardía no pasa por el cambio optimista: se relee y la
        # marca protege lo aún pendiente; el efecto global lo trae el sondeo
        self._enviar("PUT", _RUTAS_OPTIMISTAS[clave], cuerpo, al_terminar,
                     al_tardio=lambda _r: self._leer_optimista(clave))

    def _releer(self, clave, al_leer) -> None:
        def leido(r):
            v = _LECTORES[clave](r)
            al_leer(SIN_LECTURA if v is None else v)
        self._enviar("GET", _RUTAS_OPTIMISTAS[clave], None, leido)

    def _al_cambiar(self, clave, valor) -> None:
        if self._valor_mostrado(clave) != valor:
            self._fijar_mostrado(clave, valor)
            self.datosChanged.emit()

    def _al_confirmar(self, clave) -> None:
        self._resuelto = True
        self._fijar_mensaje("")
        self._aplicar_global(clave, self._opt.confirmado(clave))
        self.cambioResuelto.emit(clave, True, "")

    @staticmethod
    def _aplicar_global(clave, valor) -> None:
        """Efecto en toda la interfaz, solo con el cambio ya aceptado."""
        try:
            if clave == IDIOMA and valor:
                from autoclave import i18n
                i18n.fijar_idioma(valor)                 # esta ventana cambia ya
            elif clave == TEMA and valor in TEMAS:
                from autoclave.ui_qml.bridge import apariencia_qml
                apariencia_qml.instancia.fijar(valor)    # sin esperar el sondeo
            elif clave == UNIDADES:
                from autoclave.ui_qml.bridge import unidades_qml
                unidades_qml.instancia.refrescar()       # sin esperar el sondeo
        except Exception:
            pass

    def _al_revertir(self, clave, causa) -> None:
        self._resuelto = False
        self._leer_optimista(clave)        # se relee el estado real (solo esa clave)
        if causa == SIN_CONFIRMAR:
            self._fijar_mensaje(MENSAJE_SIN_CONFIRMAR)
        else:
            mensaje = mensaje_de(causa)
            if clave == UNIDADES and causa == "estado_no_permitido":
                mensaje = "opciones.equipo_err_unidades_ciclo"
            self._fijar_mensaje(mensaje, revertido=True)
        self.cambioResuelto.emit(clave, False, self._mensaje)

    def _aplicar_optimista(self, clave: str, nuevo) -> bool:
        self._resuelto = None
        actual = self._valor_mostrado(clave)
        if actual is None:
            self._opt.aplicar(clave, nuevo)
        else:
            self._opt.aplicar(clave, nuevo, actual)
        resuelto, self._resuelto = self._resuelto, None
        return True if resuelto is None else resuelto

    @Slot(bool, result=bool)
    def fijarImpresora(self, habilitada: bool) -> bool:
        if self._op.en_curso(CLAVE_REINICIO):
            return False                   # MENOR-6: no con el cambio con reinicio en vuelo
        return self._aplicar_optimista(IMPRESORA, bool(habilitada))

    @Property(bool, notify=operacionEnCursoChanged)
    def operacionEnCurso(self) -> bool:
        """Hay un cambio de impresora con reinicio en vuelo («Procesando…»)."""
        return self._op.operacionEnCurso

    @Slot(str, result=str)
    def estadoDe(self, clave: str) -> str:
        """inactiva | enviando | verificando."""
        return self._op.estado(clave)

    @Slot(bool, result=bool)
    def fijarImpresoraYReiniciar(self, habilitada: bool) -> bool:
        """R11 (D11-1): la pantalla ya confirmó "Se reiniciará el software". El
        backend guarda la bandera con auditoría y reinicia; `reiniciando` y el
        aviso de reinicio solo con el 200 que lo dice (sin releer: el backend se
        está cerrando). Rechazado: motivo y se relee. Sin respuesta: «sin
        confirmar», sin relectura ni reintento. True = enviada; False sin enviar
        (ya hay una en curso)."""
        habilitada = bool(habilitada)
        if IMPRESORA in self._opt.pendientes():
            return False                   # MENOR-6: no con el cambio optimista en vuelo

        def al_ok(r) -> None:
            datos = r.datos if isinstance(r.datos, dict) else {}
            self._fijar_mensaje("")
            if datos.get("reiniciando") is True:
                self._impresora = habilitada
                self._reiniciando = True
                self.datosChanged.emit()
                self.reiniciandoChanged.emit()
            else:
                self.cargar()

        return self._op.iniciar(
            CLAVE_REINICIO, "PUT", "/printer/config",
            {"habilitada": habilitada, "reiniciar": True}, plazo_s=PLAZO_REINICIO_S,
            al_ok=al_ok, al_rechazo=lambda r: mensaje_de(r.causa), bloquea_navegacion=True,
            msg_sin_confirmar=MENSAJE_REINICIO_SIN_CONFIRMAR)

    def _al_resolver_operacion(self, clave: str, estado: str, mensaje: str) -> None:
        if estado == oc.RECHAZADA:
            self._fijar_mensaje(mensaje)
            self.cargar()                  # el estado real lo dice el backend
        elif estado == oc.SIN_CONFIRMAR:
            self._fijar_mensaje(mensaje)   # sin relectura: el backend se cierra
        self.operacionResuelta.emit(clave, estado, mensaje)

    @Property(bool, notify=reiniciandoChanged)
    def reiniciando(self) -> bool:
        return self._reiniciando

    # ── Configuración de la máquina ──────────────────────────────────────
    @Property(str, notify=datosChanged)
    def idioma(self) -> str:
        return self._idioma

    @Slot(str, result=bool)
    def fijarIdioma(self, idioma: str) -> bool:
        if not idioma:
            return False
        return self._aplicar_optimista(IDIOMA, str(idioma))

    # Modo oscuro (OSC-02): mismos roles que el idioma (motivoIdioma), sin bitácora
    @Property(str, notify=datosChanged)
    def tema(self) -> str:
        return self._tema

    @Slot(str, result=bool)
    def fijarTema(self, tema: str) -> bool:
        """Optimista con reversión (decisión del usuario, FASE 6): el selector
        cambia ya; el tema global (`apariencia_qml`) solo tras el 200."""
        if tema not in TEMAS:
            return False
        return self._aplicar_optimista(TEMA, tema)

    @Property(str, notify=datosChanged)
    def unidadTemperatura(self) -> str:
        return self._unidades["temperatura"]

    @Property(str, notify=datosChanged)
    def unidadPresion(self) -> str:
        return self._unidades["presion"]

    @Slot(str, str, result=bool)
    def fijarUnidades(self, temperatura: str, presion: str) -> bool:
        if not temperatura or not presion:
            return False
        return self._aplicar_optimista(UNIDADES, (str(temperatura), str(presion)))

    @Property(str, notify=datosChanged)
    def numeroSerie(self) -> str:
        return self._serie

    @Property(str, notify=datosChanged)
    def modelo(self) -> str:
        return self._modelo

    @Property(str, notify=datosChanged)
    def serialEspecifika(self) -> str:
        """Serie interna (SNAANNNN) de un equipo de automatización; "" en fabricación."""
        return self._serial_especifika

    @Property(bool, notify=datosChanged)
    def impresoraConocida(self) -> bool:
        return self._impresora is not None

    @Property(bool, notify=datosChanged)
    def impresoraHabilitada(self) -> bool:
        return bool(self._impresora)

    @Property(str, notify=mensajeChanged)
    def mensaje(self) -> str:
        return self._mensaje

    @Property("QVariantMap", notify=mensajeChanged)
    def valoresMensaje(self) -> dict:
        """A7 (tanda 27): {marcador: {"v": kPa, "dif": bool}} del mensaje
        vigente; la pantalla los da en la unidad vigente."""
        return dict(self._valores)

    @Property(bool, notify=mensajeChanged)
    def mensajeRevertido(self) -> bool:
        """El mensaje es el motivo de un cambio que no se aplicó: la pantalla
        lo muestra dentro de opciones.cambio_revertido."""
        return self._revertido

    @Slot()
    def limpiarMensaje(self) -> None:
        self._fijar_mensaje("")


qmlRegisterType(ParametrosEquipoController, "Autoclave.Controllers", 1, 0,
                "ParametrosEquipoController")

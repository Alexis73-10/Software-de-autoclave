# ui_qml/controllers/parametros_ciclo_controller.py
#
# OPCIONES › Parámetros del ciclo, Fases 2 a 4 (planeacion_opciones_parametros_ciclo.md
# rev. 3.1 §4.2, §5.1 a §5.5; tanda 2026-10-14 T12):
#   - programas y secciones (GET /programas), parámetros de una sección con
#     valor por defecto, rango efectivo y última modificación
#     (GET /programas/{n}/seccion/{s});
#   - edición de un parámetro (PATCH /cycle/parameter) con
#     valor_anterior_esperado (RB-06) y el token de la ventana;
#   - roles de los sensores de temperatura (GET /cycle/sensors,
#     PUT /cycle/sensor-roles, todo o nada con asignacion_anterior_esperada).
#
# No calcula reglas de seguridad: el backend valida siempre (§4.2). Un
# resultado sin respuesta es INCIERTO: se recarga el valor antes de informar
# (§5.4, D-15).
#
# Sin HTTP síncrono en la GUI (AJUSTES 2026-11-02, paso 2 fase 3; modelo:
# usuarios_controller.py):
#   - Parámetro (PATCH /cycle/parameter, SAF-05): asíncrono SIN optimismo. Lo
#     mostrado sigue siendo el valor vigente del backend; la clave
#     "param:<n>:<sección>:<clave>" queda en `pendientes` (píldora «Guardando…»
#     con el valor tecleado en `valoresPendientes`, edición bloqueada) hasta
#     el 200 y la relectura. La conciliación (arrastres, aviso del modo de
#     descompresión, valor_anterior_esperado, relectura tras sin respuesta)
#     es la de antes, con cada relectura asíncrona y una sola vez.
#   - Entradas mostradas (PUT /cycle/display-inputs, solo visualización):
#     cambio optimista con reversión (CambioOptimista, clave "entradas:<n>").
#   - Lecturas (programas, sección, entradas, sensores): GET asíncronos con
#     `cargando`; una respuesta anterior a la última no pisa la vista.
#   - Roles de sensores (PUT /cycle/sensor-roles; FASE 6, P1): operación
#     crítica asíncrona SIN optimismo (OperacionCritica, clave
#     "sensores:<n>", plazo 10 s, bloquea la navegación). La asignación
#     mostrada es la vigente del backend hasta el 200 o hasta una relectura
#     de GET /cycle/sensors que coincida con lo pedido; sin respuesta y sin
#     coincidencia queda «sin confirmar» (ya no hay atajo que la dé por buena).
#     El desenlace llega por `operacionResuelta(clave, estado, mensaje)`.
# Los slots devuelven False si falla la validación local (o la clave sigue
# pendiente); si el resultado llegó en el acto (sesión de prueba con solo
# `enviar`), el `ok` real; si quedó en vuelo, True («aceptado»). El desenlace
# llega por `cambioResuelto(clave, ok, mensaje)`. Excepción: guardarSensores
# devuelve siempre True = enviado (o False = rechazo local).

import logging

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtQml import qmlRegisterType

from autoclave.ui_qml import sesion_backend
from autoclave.ui_qml.cambio_optimista import (
    ENVIANDO, SIN_CONFIRMAR, SIN_LECTURA, VERIFICANDO, CambioOptimista)
from autoclave.ui_qml import operacion_critica as oc

# Código del backend -> clave de es.json (opciones §5.4)
_MENSAJES = {
    "estado_no_permitido": "opciones.err_bloqueada",
    "VALOR_CAMBIO": "opciones.err_valor_cambio",
    "rol_sin_permiso": "opciones.err_rol",
    "sesion_invalida": "opciones.err_identidad",
    "VALOR_INVALIDO": "opciones.err_valor_invalido",
    "PROGRAMA_NO_EDITABLE": "opciones.err_no_editable",
    "programa_de_fabrica": "opciones.err_no_editable",
    "BASE_OCUPADA": "opciones.err_base_ocupada",
    "f0_no_disponible": "opciones.err_f0",
    "apertura_automatica_no_disponible": "opciones.err_apertura_puertas_simples",
    "ASIGNACION_INVALIDA": "opciones.err_asignacion",
    "SENSOR_NO_DISPONIBLE": "opciones.err_sensor",
    # O11 (tanda 11, D11-7.1): entrada de un sensor No en uso en el programa
    "SENSOR_NO_EN_USO": "opciones.err_sensor_no_en_uso",
    "asignacion_desfasada": "opciones.err_valor_cambio",
    # D8-5.7 (tanda 8): carga líquida
    "MODO_NO_PERMITIDO_LIQUIDO": "opciones.err_modo_liquido",
    "MODO_NO_PERMITIDO_SOLIDO": "opciones.err_modo_solido",    # T29-05
    "COHERENCIA_LIQUIDO": "opciones.err_coherencia_liquido",
    # J12 (tanda 12): límites físicos de presión (alivio de cámara/chaqueta)
    "LIMITE_PRESION_CAMARA": "opciones.err_limite_presion_camara",
    "LIMITE_CONSIGNA_CHAQUETA": "opciones.err_limite_consigna_chaqueta",
    "LIMITE_PRESION_CHAQUETA": "opciones.err_limite_presion_chaqueta",
    # Tanda 16: P1 (D-14.1) y PRG-01 (D-PRG-1)
    "COHERENCIA_RECUPERACION": "opciones.err_coherencia_recuperacion",
    "COHERENCIA_DESCOMPRESION": "opciones.err_coherencia_descompresion",   # LIQ-03 (tanda 32)
    "LIMITE_CONTRAPRESION_ENFRIAMIENTO": "opciones.err_limite_contrapresion_enfriamiento",  # M-A
    "COHERENCIA_BRECHA_PRESION": "opciones.err_coherencia_brecha_presion",   # PAM-06
    "ROL_SONDA_NO_ACTIVA": "opciones.err_rol_sonda_no_activa",
    # O1 (tanda 5): gestión de programas
    "programa_activo": "opciones.err_programa_activo",
    "programa_deshabilitado": "opciones.err_programa_deshabilitado",
    "programa_existente": "opciones.err_generico",
    sesion_backend.BACKEND_NO_RESPONDE: "opciones.err_sin_respuesta",
}


# Tanda 12: claves de advertencia que devuelve PATCH /cycle/parameter
_ADVERTENCIAS = {
    "aviso_techo_sobre_suministro": "opciones.aviso_techo_sobre_suministro",
    "aviso_chaqueta_abierta": "opciones.aviso_chaqueta_abierta",
    # A14-M1 (tanda 28): banda PWM de esterilización cerca del techo
    "aviso_banda_pwm_techo": "opciones.aviso_banda_pwm_techo",
}


MENSAJE_SIN_CONFIRMAR = "opciones.cambio_sin_confirmar"
MENSAJE_ERROR_INTERNO = "opciones.err_generico"   # un callback de guardado falló
PLAZO_SENSORES_S = 10.0          # FASE 6: PUT /cycle/sensor-roles


def clave_sensores(numero) -> str:
    """Clave de la operación crítica de roles de sensores del programa."""
    return f"sensores:{int(numero)}"


def conciliar_sensores(leido, pedida: dict):
    """Relectura tras «sin respuesta» del PUT de roles: CONFIRMADA solo si la
    asignación vigente es la pedida. Si no coincide NO es un rechazo (MAYOR-3,
    corrección tras revisión): el PUT puede seguir en el backend; queda
    SIN_CONFIRMAR y un 200 tardío aún se procesa."""
    if not isinstance(leido, dict):
        return oc.SIN_CONFIRMAR
    if dict(leido) == dict(pedida):
        return oc.CONFIRMADA
    return (oc.SIN_CONFIRMAR, mensaje_de(sesion_backend.BACKEND_NO_RESPONDE))

logger = logging.getLogger(__name__)


def _resguardado(al_terminar, al_fallar, ruta):
    """Envuelve el callback de un guardado: si lanza, registra la excepción y
    llama a `al_fallar()` para sacar la clave de los pendientes y resolverla
    (la sesión solo la registraría y la clave quedaría pendiente sin plazo)."""
    def envuelto(r):
        try:
            al_terminar(r)
        except Exception:
            logger.exception("Fallo en el callback de guardado (%s)", ruta)
            al_fallar()
    return envuelto


def mensaje_de(causa: str) -> str:
    return _MENSAJES.get(causa, "opciones.err_generico")


def clave_parametro(numero, seccion: str, clave: str) -> str:
    """Clave de `pendientes` de un parámetro (la pantalla la arma igual)."""
    return f"param:{int(numero)}:{seccion}:{clave}"


def _cancelar_al_destruir(sesion, ident):
    return lambda *_: sesion_backend.cancelar_envios(sesion, ident)


# ── selector por fila de las entradas mostradas (O11, tanda 11, D11-7.2) ──
# Tres filas: la 1 obligatoria, la 2 y la 3 admiten "Ninguna" (""). Una
# entrada elegida en una fila no se ofrece en las otras.
FILAS_ENTRADAS = 3


def filas_de(entradas) -> list[str]:
    """Las entradas guardadas repartidas en las 3 filas ("" = Ninguna)."""
    lista = [str(e) for e in (entradas or []) if e][:FILAS_ENTRADAS]
    return lista + [""] * (FILAS_ENTRADAS - len(lista))


def opciones_fila(disponibles, filas, fila: int) -> list[str]:
    """Entradas que ofrece el desplegable de la fila `fila` (0 a 2): las
    disponibles menos las elegidas en las otras filas ("Ninguna" lo agrega
    la pantalla en las filas 2 y 3)."""
    otras = {str(e) for i, e in enumerate(filas or []) if i != fila and e}
    return [e for e in (disponibles or []) if e not in otras]


def numero_inicial(programas) -> int:
    """T29-06: número del programa en que abre Parámetros del ciclo: el
    marcado `seleccionado` (el activo en Preciclo) o, si no hay, el primero."""
    elegido = next((p for p in programas or [] if p.get("seleccionado") is True), None)
    return (elegido or programas[0])["numero"]


def etiqueta_programa(numero, nombre) -> str:
    """T29-06: «03 · Nombre» para las vistas del flujo ("" sin programa)."""
    if not isinstance(numero, int) or isinstance(numero, bool) or numero <= 0:
        return ""
    return f"{numero:02d} · {nombre}" if nombre else f"{numero:02d}"


def entradas_de_filas(filas) -> tuple[list[str], str]:
    """(entradas a guardar en orden, clave de error o "")."""
    filas = [str(e or "") for e in (filas or [])][:FILAS_ENTRADAS]
    if not filas or not filas[0]:
        return [], "opciones.err_entrada_1_obligatoria"
    lista = [e for e in filas if e]
    if len(set(lista)) != len(lista):
        return [], "opciones.err_entradas_repetidas"
    return lista, ""


class ParametrosCicloController(QObject):
    programasChanged = Signal()
    programaChanged = Signal()
    parametrosChanged = Signal()
    sensoresChanged = Signal()
    entradasChanged = Signal()
    mensajeChanged = Signal()
    avisoChanged = Signal()
    pendientesChanged = Signal()
    cargandoChanged = Signal()
    # clave del cambio, aceptado, clave i18n del mensaje ("" si aceptado)
    cambioResuelto = Signal(str, bool, str)
    # FASE 6: operación crítica (roles de sensores): clave, estado, mensaje
    operacionResuelta = Signal(str, str, str)
    operacionEnCursoChanged = Signal()

    def __init__(self, parent=None, sesion=None):
        super().__init__(parent)
        self._sesion = sesion
        self._programas: list = []
        self._numero = 0
        self._abrir_en_seleccionado = True     # T29-06: solo la primera carga
        self._seccion = ""
        self._parametros: list = []
        self._editable_seccion = False
        self._sensores: list = []
        self._asignacion: dict = {}
        self._sensores_editable = False
        self._entradas: list = []
        self._entradas_habilitadas: list = []
        self._entradas_disponibles: list = []
        # Tanda 17 (SON-01): entradas de sondas instaladas con rol No en uso
        # (`no_en_uso` de GET /cycle/display-inputs): se rotulan "(monitoreo)"
        self._entradas_no_en_uso: list = []
        self._entradas_editable = False
        self._mensaje = ""
        self._detalle: dict = {}
        # D8-5.7: aviso informativo de un cambio automático (clave + datos)
        self._aviso = ""
        self._detalle_aviso: dict = {}
        self._revertido = False            # el mensaje es el motivo de una reversión
        # parámetros en vuelo: clave -> {"estado": ..., "valor": valor tecleado}
        self._en_vuelo: dict[str, dict] = {}
        self._lecturas = 0                 # GET en vuelo (`cargando`)
        self._gen = {"programas": 0, "seccion": 0, "entradas": 0, "sensores": 0}
        self._gen_seccion_vista = 0        # última lectura de sección aplicada a la vista
        self._resuelto = None              # desenlace síncrono del último slot
        self._opt = CambioOptimista(self._lanzar_entradas, self._al_cambiar_entradas,
                                    self._al_revertir_entradas, self._releer_entradas,
                                    al_confirmar=self._al_confirmar_entradas,
                                    al_pendientes=self.pendientesChanged.emit)
        self._op = oc.OperacionCritica(self, self._s)
        self._op.operacionEnCursoChanged.connect(self.operacionEnCursoChanged)
        self._op.operacionResuelta.connect(self._al_resolver_operacion)
        # sin referencia a self: el destructor de C++ ya está en marcha
        self.destroyed.connect(_cancelar_al_destruir(sesion, id(self)))

    def _s(self):
        return self._sesion or sesion_backend.ventana()

    def _enviar(self, metodo, ruta, cuerpo, al_terminar, al_tardio=None, al_fallar=None) -> None:
        """`al_fallar()`: se llama si `al_terminar` lanza (ver `_resguardado`)."""
        if al_fallar is not None:
            al_terminar = _resguardado(al_terminar, al_fallar, ruta)
        sesion_backend.enviar_async(self._s(), metodo, ruta, cuerpo, al_terminar,
                                    dueno=self, al_tardio=al_tardio)

    def _leer(self, ruta: str, al_terminar, al_fallar=None) -> None:
        """GET asíncrono que cuenta para `cargando`."""
        self._fijar_lecturas(self._lecturas + 1)

        def terminar(r):
            self._fijar_lecturas(self._lecturas - 1)
            al_terminar(r)
        self._enviar("GET", ruta, None, terminar, al_fallar=al_fallar)

    def _fijar_lecturas(self, n: int) -> None:
        antes = self._lecturas > 0
        self._lecturas = max(0, n)
        if antes != (self._lecturas > 0):
            self.cargandoChanged.emit()

    def _nueva_gen(self, tipo: str) -> int:
        self._gen[tipo] += 1
        return self._gen[tipo]

    def _fijar_mensaje(self, clave: str, detalle: dict | None = None,
                       revertido: bool = False) -> None:
        self._mensaje = clave
        self._detalle = dict(detalle or {})
        self._revertido = revertido
        self.mensajeChanged.emit()

    # ── estado de los envíos ─────────────────────────────────────────

    @Property("QVariantMap", notify=pendientesChanged)
    def pendientes(self) -> dict:
        """clave -> "enviando" | "verificando" (parámetros y entradas)."""
        return {**self._opt.pendientes(),
                **{k: v["estado"] for k, v in self._en_vuelo.items()}}

    @Property("QVariantMap", notify=pendientesChanged)
    def valoresPendientes(self) -> dict:
        """clave de parámetro -> valor tecleado que se está guardando (no vigente)."""
        return {k: v["valor"] for k, v in self._en_vuelo.items()}

    @Property(bool, notify=pendientesChanged)
    def parametroPendiente(self) -> bool:
        """M1 (SAF-05): algún PATCH de parámetro sin desenlace; la pantalla no
        se deja abandonar mientras tanto (se perdería el aviso de arrastres)."""
        return any(k.startswith("param:") for k in self._en_vuelo)

    @Property(bool, notify=cargandoChanged)
    def cargando(self) -> bool:
        return self._lecturas > 0

    # ── programas ────────────────────────────────────────────────────

    @Slot()
    def cargar(self) -> None:
        gen = self._nueva_gen("programas")
        self._leer("/programas", lambda r: self._al_cargar(r, gen))

    def _al_cargar(self, r, gen) -> None:
        if gen != self._gen["programas"]:
            return                          # una carga posterior manda
        if not r.ok or not isinstance(r.datos, dict):
            self._fijar_mensaje(mensaje_de(r.causa))
            return
        self._programas = list(r.datos.get("programas") or [])
        self.programasChanged.emit()
        if self._abrir_en_seleccionado and self._programas:
            # T29-06: la primera carga abre en el programa seleccionado en
            # Preciclo (`seleccionado` de GET /programas); si no hay, el primero.
            # Las cargas posteriores (tras guardar) no cambian de programa.
            self._abrir_en_seleccionado = False
            self.elegirPrograma(numero_inicial(self._programas))
        elif self._programas and not any(p["numero"] == self._numero for p in self._programas):
            self.elegirPrograma(self._programas[0]["numero"])
        else:
            self.programaChanged.emit()

    @Property("QVariantList", notify=programasChanged)
    def programas(self) -> list:
        return self._programas

    @Slot(int)
    def elegirPrograma(self, numero: int) -> None:
        if numero != self._numero:
            self._numero = numero
            self._parametros, self._seccion = [], ""
            self.parametrosChanged.emit()
        self.programaChanged.emit()

    def _programa(self) -> dict:
        return next((p for p in self._programas if p["numero"] == self._numero), {})

    @Property(int, notify=programaChanged)
    def numero(self) -> int:
        return self._numero

    @Property(str, notify=programaChanged)
    def nombrePrograma(self) -> str:
        return self._programa().get("nombre", "")

    @Property(str, notify=programaChanged)
    def etiquetaPrograma(self) -> str:
        """T29-06: «03 · Nombre» del programa abierto (todas las vistas)."""
        return etiqueta_programa(self._numero, self._programa().get("nombre", ""))

    @Property("QVariantList", notify=programaChanged)
    def secciones(self) -> list:
        return list(self._programa().get("secciones") or [])

    @Property(bool, notify=programaChanged)
    def programaEditable(self) -> bool:
        return bool(self._programa().get("editable"))

    # ── estado del programa (O1, tanda 5) ────────────────────────────
    # C9 (tanda 9, D9-10): habilitar, duplicar y borrar se movieron a Opciones
    # avanzadas › Manejo de ciclos (manejo_ciclos_controller.py); aquí solo se
    # informa el estado.

    @Property(bool, notify=programaChanged)
    def programaHabilitado(self) -> bool:
        return self._programa().get("habilitado", True) is not False

    @Property(bool, notify=programaChanged)
    def programaPersonalizado(self) -> bool:
        return self._programa().get("personalizado") is True

    # ── entradas mostradas (O1) ──────────────────────────────────────

    @Slot()
    def cargarEntradas(self) -> None:
        numero, gen, marca = self._numero, self._nueva_gen("entradas"), self._opt.marca()
        self._leer(f"/cycle/display-inputs?programa={numero}",
                   lambda r: self._al_cargar_entradas(r, numero, gen, marca))

    def _al_cargar_entradas(self, r, numero, gen, marca) -> None:
        if gen != self._gen["entradas"] or numero != self._numero:
            return                          # otra carga u otro programa manda
        if r.ok and isinstance(r.datos, dict):
            clave = f"entradas:{numero}"
            leidas = list(r.datos.get("entradas") or [])
            if not self._opt.confirmar_lectura(clave, leidas, marca):
                # cambio pendiente o lectura lanzada antes del último cambio:
                # se conserva lo que se muestra
                leidas = list(self._opt.mostrar(clave, list(self._entradas)))
            self._entradas = leidas
            self._entradas_habilitadas = list(r.datos.get("habilitadas") or [])
            # O11 (D11-7.1): el selector no ofrece un sensor No en uso; un
            # backend sin "disponibles" (anterior a O11): las habilitadas
            disp = r.datos.get("disponibles")
            self._entradas_disponibles = list(disp if isinstance(disp, list)
                                              else self._entradas_habilitadas)
            self._entradas_editable = bool(r.datos.get("editable"))
            no = r.datos.get("no_en_uso")
            self._entradas_no_en_uso = [str(e) for e in no if isinstance(e, str)] if isinstance(no, list) else []
        else:
            # B1: con un cambio pendiente se conserva lo que se muestra (al
            # confirmarse, CambioOptimista no vuelve a llamar a `al_cambiar`)
            clave = f"entradas:{numero}"
            self._entradas = (list(self._opt.mostrar(clave, list(self._entradas)))
                              if self._opt.pendiente(clave) else [])
            self._entradas_habilitadas, self._entradas_editable = [], False
            self._entradas_disponibles = []
            self._entradas_no_en_uso = []
            self._fijar_mensaje(mensaje_de(r.causa))
        self.entradasChanged.emit()

    @Property("QVariantList", notify=entradasChanged)
    def entradas(self) -> list:
        return self._entradas

    @Property("QVariantList", notify=entradasChanged)
    def entradasHabilitadas(self) -> list:
        return self._entradas_habilitadas

    @Property(bool, notify=entradasChanged)
    def entradasEditable(self) -> bool:
        return self._entradas_editable

    @Property("QVariantList", notify=entradasChanged)
    def entradasDisponibles(self) -> list:
        """O11: las que ofrece el selector (sin los sensores No en uso)."""
        return self._entradas_disponibles

    @Property("QVariantList", notify=entradasChanged)
    def entradasNoEnUso(self) -> list:
        """Tanda 17 (SON-01): entradas de sondas No en uso (rótulo "(monitoreo)")."""
        return self._entradas_no_en_uso

    @Property("QVariantList", notify=entradasChanged)
    def filasEntradas(self) -> list:
        """O11: la selección guardada en las 3 filas ("" = Ninguna)."""
        return filas_de(self._entradas)

    @Slot(int, "QVariantList", result="QVariantList")
    def opcionesFila(self, fila: int, filas) -> list:
        return opciones_fila(self._entradas_disponibles, list(filas or []), int(fila))

    @Slot("QVariantList", result=bool)
    def guardarFilas(self, filas) -> bool:
        """O11 (D11-7.2): Entrada 1 obligatoria, sin repetir; guarda con el
        mismo PUT (1 a 3, auditoría en el backend)."""
        lista, error = entradas_de_filas(list(filas or []))
        if error:
            self._fijar_mensaje(error)
            return False
        return self.guardarEntradas(lista)

    @Slot("QVariantList", result=bool)
    def guardarEntradas(self, entradas) -> bool:
        lista = [str(e) for e in entradas]
        if not 1 <= len(lista) <= 3:
            self._fijar_mensaje("opciones.err_entradas_cantidad")
            return False
        # C (paso 2): optimista con reversión; solo cambia lo que se muestra
        self._resuelto = None
        self._opt.aplicar(f"entradas:{self._numero}", lista, list(self._entradas))
        resuelto, self._resuelto = self._resuelto, None
        return True if resuelto is None else resuelto

    def _lanzar_entradas(self, clave, valor, al_terminar) -> None:
        numero = int(clave.split(":", 1)[1])
        # la respuesta tardía (tras backend_no_responde) no pasa por el cambio
        # optimista: se relee, y la marca protege lo aún pendiente
        self._enviar("PUT", "/cycle/display-inputs",
                     {"programa": numero, "entradas": list(valor)}, al_terminar,
                     al_tardio=lambda _r: self._recargar_entradas_de(numero))

    def _recargar_entradas_de(self, numero) -> None:
        if numero == self._numero:
            self.cargarEntradas()

    def _releer_entradas(self, clave, al_leer) -> None:
        numero = int(clave.split(":", 1)[1])

        def leido(r):
            if r.ok and isinstance(r.datos, dict) and isinstance(r.datos.get("entradas"), list):
                al_leer(list(r.datos["entradas"]))
            else:
                al_leer(SIN_LECTURA)
        self._enviar("GET", f"/cycle/display-inputs?programa={numero}", None, leido)

    def _al_cambiar_entradas(self, clave, valor) -> None:
        if int(clave.split(":", 1)[1]) == self._numero and self._entradas != list(valor):
            self._entradas = list(valor)
            self.entradasChanged.emit()

    def _al_confirmar_entradas(self, clave) -> None:
        self._resuelto = True
        self._fijar_mensaje("")
        self.cambioResuelto.emit(clave, True, "")
        # B1: una lectura fallida dejó la lista vacía: se relee lo vigente
        if not self._entradas:
            self._recargar_entradas_de(int(clave.split(":", 1)[1]))

    def _al_revertir_entradas(self, clave, causa) -> None:
        self._resuelto = False
        if causa == SIN_CONFIRMAR:
            self._fijar_mensaje(MENSAJE_SIN_CONFIRMAR)
            self._recargar_entradas_de(int(clave.split(":", 1)[1]))   # el estado real
        else:
            self._fijar_mensaje(mensaje_de(causa), revertido=True)
        self.cambioResuelto.emit(clave, False, self._mensaje)

    # ── parámetros de una sección ────────────────────────────────────

    @Slot(str)
    def abrirSeccion(self, seccion: str) -> None:
        if seccion != self._seccion:
            # mientras llega la lectura no se muestran los de otra sección
            self._seccion = seccion
            self._parametros, self._editable_seccion = [], False
            self.parametrosChanged.emit()
        self._leer_seccion(self._numero, seccion)

    def _leer_seccion(self, numero, seccion: str, al_leer=None, al_fallar=None) -> None:
        """GET de una sección. Se aplica a la vista solo si sigue abierta y si
        no llegó antes una lectura posterior; `al_leer(r)` recibe siempre el
        resultado (conciliación de un guardado); `al_fallar()`, si el callback
        lanzó (también `_aplicar_seccion`, que corre antes de `al_leer`)."""
        gen = self._nueva_gen("seccion")

        def leido(r):
            if (numero == self._numero and seccion == self._seccion
                    and gen > self._gen_seccion_vista):
                self._gen_seccion_vista = gen
                self._aplicar_seccion(r)
            if al_leer is not None:
                al_leer(r)
        self._leer(f"/programas/{numero}/seccion/{seccion}", leido, al_fallar=al_fallar)

    def _aplicar_seccion(self, r) -> None:
        if r.ok and isinstance(r.datos, dict):
            self._parametros = list(r.datos.get("parametros") or [])
            self._editable_seccion = bool(r.datos.get("editable"))
        else:
            self._parametros, self._editable_seccion = [], False
            self._fijar_mensaje(mensaje_de(r.causa))
        self.parametrosChanged.emit()

    @Property(str, notify=parametrosChanged)
    def seccion(self) -> str:
        return self._seccion

    @Property("QVariantList", notify=parametrosChanged)
    def parametros(self) -> list:
        return self._parametros

    @Property(bool, notify=parametrosChanged)
    def seccionEditable(self) -> bool:
        return self._editable_seccion

    @Slot(str, "QVariant", result=bool)
    def guardar(self, clave: str, valor) -> bool:
        """PATCH del parámetro `clave` de la sección abierta. Asíncrono y sin
        optimismo (SAF-05): lo mostrado sigue siendo el valor vigente hasta el
        200 y la relectura. False si no se envió (parámetro desconocido o un
        guardado de esa clave aún pendiente); con resultado inmediato, si se
        guardó; en vuelo, True (aceptado). Desenlace: `cambioResuelto`."""
        p = next((x for x in self._parametros if x["clave"] == clave), None)
        cycle_id = self._programa().get("cycle_id")
        if p is None or not cycle_id:
            return False
        if p.get("tipo") == "int" and isinstance(valor, float) and valor.is_integer():
            valor = int(valor)
        numero, seccion = self._numero, self._seccion
        k = clave_parametro(numero, seccion, clave)
        if k in self._en_vuelo:
            return False                    # la edición de esa clave sigue bloqueada
        cuerpo = {"cycle_id": cycle_id, "fase": seccion, "path": p["path"],
                  "value": valor, "valor_anterior_esperado": p["valor"]}
        self._fijar_aviso("")
        self._en_vuelo[k] = {"estado": ENVIANDO, "valor": valor}
        self.pendientesChanged.emit()
        self._resuelto = None

        fallar = self._guarda(k)

        def enviar_patch(modo_antes):
            self._enviar("PATCH", "/cycle/parameter", cuerpo,
                         lambda r: self._al_guardar(k, numero, seccion, clave, valor, modo_antes, r),
                         al_tardio=lambda rt: self._al_guardar_tardio(numero, seccion, valor, rt),
                         al_fallar=fallar)

        # SAF-05 (revisión D8-5.7): el modo antes del cambio de tipo de carga,
        # para avisar del cambio automático aunque la respuesta no llegue; se
        # lee antes de enviar el PATCH (en orden, no en paralelo)
        if self._es_tipo_carga(p):
            self._leer_modo(numero, enviar_patch, al_fallar=fallar)
        else:
            enviar_patch(None)
        resuelto, self._resuelto = self._resuelto, None
        return True if resuelto is None else resuelto

    def _al_guardar(self, k, numero, seccion, clave, valor, modo_antes, r) -> None:
        datos = r.datos if isinstance(r.datos, dict) else {}
        if r.ok:
            self._fijar_mensaje("")
            self._avisar_arrastres(datos.get("arrastres"), valor)
            self._avisar_advertencias(datos.get("advertencias"))
            # relectura única: la sección (valor vigente, «*», última
            # modificación) y los programas ("No se ejecuta" puede cambiar)
            self._leer_seccion(numero, seccion, lambda _r: self._resolver(k, True),
                               al_fallar=self._guarda(k))
            self.cargar()
            return
        if r.causa == sesion_backend.BACKEND_NO_RESPONDE:
            # Sin respuesta: resultado incierto; se relee y se informa lo real (§5.4)
            self._en_vuelo[k]["estado"] = VERIFICANDO
            self.pendientesChanged.emit()
            self._leer_seccion(numero, seccion,
                               lambda rs: self._conciliar(k, numero, clave, valor, modo_antes, r, rs),
                               al_fallar=self._guarda(k))
            return
        # rechazo: se relee una vez (p. ej. VALOR_CAMBIO trae otro vigente)
        self._leer_seccion(numero, seccion, lambda _r: self._rechazado(k, r),
                           al_fallar=self._guarda(k))

    def _conciliar(self, k, numero, clave, valor, modo_antes, r, rs) -> None:
        params = rs.datos.get("parametros") if rs.ok and isinstance(rs.datos, dict) else None
        ahora = next((x for x in params or [] if isinstance(x, dict) and x.get("clave") == clave), None)
        if ahora is None or ahora.get("valor") != valor:
            self._rechazado(k, r)           # no se aplicó (o no se pudo releer)
            return
        self._fijar_mensaje("")
        if modo_antes is None:
            self._resolver(k, True)
            return

        def con_modo(modo_despues):
            if modo_despues is not None and modo_despues != modo_antes:
                self._avisar_arrastres([{"fase": "descompresion", "clave": "modo",
                                         "anterior": modo_antes, "nuevo": modo_despues}], valor)
            self._resolver(k, True)
        self._leer_modo(numero, con_modo, al_fallar=self._guarda(k))

    def _rechazado(self, k, r) -> None:
        datos = r.datos if isinstance(r.datos, dict) else {}
        # tanda 12: los límites físicos traen el máximo admisible en `valor`
        detalle = datos.get("valor_actual") if "valor_actual" in datos else datos.get("valor")
        # DEU-01 (tanda 16): alivios y suministro vigentes del equipo
        limites = {x: datos.get(x) for x in ("alivio_camara", "alivio_chaqueta", "suministro")
                   if datos.get(x) is not None}
        self._fijar_mensaje(mensaje_de(r.causa), {"valor": detalle, **limites})
        self._resolver(k, False)

    def _guarda(self, k):
        """Salvaguarda del guardado en vuelo de `k`: si un callback lanza, la
        clave sale de los pendientes y se resuelve con fallo (una sola vez;
        no toca un guardado posterior de la misma clave)."""
        entrada = self._en_vuelo.get(k)

        def fallar():
            if entrada is not None and self._en_vuelo.get(k) is entrada:
                self._fijar_mensaje(MENSAJE_ERROR_INTERNO)
                self._resolver(k, False)
        return fallar

    def _resolver(self, k, ok: bool) -> None:
        if self._en_vuelo.pop(k, None) is None:
            return                          # ya resuelto (p. ej. por la salvaguarda)
        self.pendientesChanged.emit()
        self._resuelto = ok
        self.cambioResuelto.emit(k, ok, "" if ok else self._mensaje)

    def _al_guardar_tardio(self, numero, seccion, valor, rt) -> None:
        """Respuesta que llegó tras vencer el plazo (ya se informó «sin
        respuesta» o se está verificando): se muestra lo real releyendo."""
        if rt.ok:
            datos = rt.datos if isinstance(rt.datos, dict) else {}
            self._fijar_mensaje("")
            self._avisar_arrastres(datos.get("arrastres"), valor)
            self._avisar_advertencias(datos.get("advertencias"))
        self._leer_seccion(numero, seccion)
        self.cargar()

    # ── sensores (pantalla 4) ────────────────────────────────────────

    @Slot()
    def cargarSensores(self) -> None:
        numero, gen = self._numero, self._nueva_gen("sensores")

        def leido(r):
            if gen == self._gen["sensores"] and numero == self._numero:
                self._aplicar_sensores(r)
        self._leer(f"/cycle/sensors?programa={numero}", leido)

    def _releer_sensores(self, numero: int, al_leido) -> None:
        """Relectura de la operación crítica de roles: GET /cycle/sensors ->
        al_leido(asignación vigente) o al_leido(SIN_LECTURA). Descarta las
        lecturas anteriores; un fallo no borra la vista."""
        gen = self._nueva_gen("sensores")

        def leido(r):
            if r.ok and isinstance(r.datos, dict):
                if gen == self._gen["sensores"] and numero == self._numero:
                    self._aplicar_sensores(r)
                al_leido(dict(r.datos.get("asignacion") or {}))
            else:
                al_leido(SIN_LECTURA)
        self._leer(f"/cycle/sensors?programa={numero}", leido)

    def _aplicar_sensores(self, r) -> None:
        if r.ok and isinstance(r.datos, dict):
            self._sensores = list(r.datos.get("sensores") or [])
            self._asignacion = dict(r.datos.get("asignacion") or {})
            self._sensores_editable = bool(r.datos.get("editable"))
        else:
            self._sensores, self._asignacion, self._sensores_editable = [], {}, False
            self._fijar_mensaje(mensaje_de(r.causa))
        self.sensoresChanged.emit()

    @Property("QVariantList", notify=sensoresChanged)
    def sensores(self) -> list:
        return self._sensores

    @Property("QVariantMap", notify=sensoresChanged)
    def asignacion(self) -> dict:
        return self._asignacion

    @Property(bool, notify=sensoresChanged)
    def sensoresEditable(self) -> bool:
        return self._sensores_editable

    @Property(bool, notify=operacionEnCursoChanged)
    def operacionEnCurso(self) -> bool:
        return self._op.en_curso()

    @Slot(str, result=str)
    def estadoDe(self, clave: str) -> str:
        """inactiva | enviando | verificando de la operación crítica `clave`."""
        return self._op.estado(clave)

    @Slot(result=str)
    def claveSensores(self) -> str:
        return clave_sensores(self._numero)

    @Slot("QVariantMap", result=bool)
    def guardarSensores(self, asignacion) -> bool:
        """FASE 6: True = enviado (desenlace por `operacionResuelta`); False =
        ya hay un guardado de roles en curso (sin segundo envío)."""
        numero, pedida = self._numero, dict(asignacion)
        cuerpo = {"programa": numero, "asignacion": pedida,
                  "asignacion_anterior_esperada": dict(self._asignacion)}
        if self._op.en_curso(clave_sensores(numero)):
            return False
        self._nueva_gen("sensores")         # una lectura anterior ya no pisa la vista
        self._fijar_mensaje("")
        return self._op.iniciar(
            clave_sensores(numero), "PUT", "/cycle/sensor-roles", cuerpo,
            plazo_s=PLAZO_SENSORES_S, al_rechazo=lambda r: mensaje_de(r.causa),
            releer=lambda al_leido: self._releer_sensores(numero, al_leido),
            conciliar=lambda leido: conciliar_sensores(leido, pedida),
            bloquea_navegacion=True)

    def _al_resolver_operacion(self, clave: str, estado: str, mensaje: str) -> None:
        if clave.startswith("sensores:"):
            numero = int(clave.split(":", 1)[1])
            if estado == oc.CONFIRMADA:
                self._fijar_mensaje(mensaje)    # "" o operacion.confirmada_tarde
                self.cargar()
            else:
                self._fijar_mensaje(mensaje or MENSAJE_SIN_CONFIRMAR)
            # lo vigente del backend (sin borrar la vista si no hay lectura)
            self._releer_sensores(numero, lambda _leido: None)
        self.operacionResuelta.emit(clave, estado, mensaje)

    # ── mensajes ─────────────────────────────────────────────────────

    @Property(str, notify=mensajeChanged)
    def mensaje(self) -> str:
        return self._mensaje

    @Property("QVariantMap", notify=mensajeChanged)
    def detalleMensaje(self) -> dict:
        return self._detalle

    @Property(bool, notify=mensajeChanged)
    def mensajeRevertido(self) -> bool:
        """El mensaje es el motivo de un cambio optimista (entradas mostradas)
        que no se aplicó: la pantalla lo muestra dentro de opciones.cambio_revertido."""
        return self._revertido

    @Slot()
    def limpiarMensaje(self) -> None:
        self._fijar_mensaje("")

    # ── aviso de cambios automáticos (D8-5.7) ────────────────────────

    def _fijar_aviso(self, clave: str, detalle: dict | None = None) -> None:
        if clave != self._aviso or dict(detalle or {}) != self._detalle_aviso:
            self._aviso = clave
            self._detalle_aviso = dict(detalle or {})
            self.avisoChanged.emit()

    def _es_tipo_carga(self, p: dict) -> bool:
        return self._seccion == "globals" and list(p.get("path") or []) == ["tipo_carga"]

    @staticmethod
    def _modo_de(r):
        """Modo de descompresión (int) de una lectura de la sección, o None."""
        if not r.ok or not isinstance(r.datos, dict):
            return None
        for x in r.datos.get("parametros") or []:
            if isinstance(x, dict) and x.get("clave") == "modo":
                v = x.get("valor")
                return v if isinstance(v, int) and not isinstance(v, bool) else None
        return None

    def _leer_modo(self, numero, al_leer, al_fallar=None) -> None:
        """Modo de descompresión vigente del programa `numero` -> al_leer(int | None)."""
        self._enviar("GET", f"/programas/{numero}/seccion/descompresion", None,
                     lambda r: al_leer(self._modo_de(r)), al_fallar=al_fallar)

    def _avisar_arrastres(self, arrastres, valor) -> None:
        """El backend cambió solo el modo de descompresión al cambiar el tipo
        de carga: la pantalla lo avisa con un texto del catálogo."""
        if not isinstance(arrastres, list):
            return
        for a in arrastres:
            if (isinstance(a, dict) and a.get("fase") == "descompresion"
                    and a.get("clave") == "modo" and isinstance(a.get("nuevo"), int)):
                clave = ("opciones.aviso_modo_liquido" if valor == "liquido"
                         else "opciones.aviso_modo_solido")
                self._fijar_aviso(clave, {"modo": a["nuevo"], "anterior": a.get("anterior")})
                return

    def _avisar_advertencias(self, advertencias) -> None:
        """Tanda 12 (C-04.3, C-05.5, C-05.9): guardado con una advertencia no
        bloqueante (techo o chaqueta sobre el suministro): texto del catálogo."""
        if not isinstance(advertencias, list):
            return
        for a in advertencias:
            clave = a.get("clave") if isinstance(a, dict) else None
            if isinstance(clave, str) and clave in _ADVERTENCIAS:
                self._fijar_aviso(_ADVERTENCIAS[clave])
                return

    @Property(str, notify=avisoChanged)
    def aviso(self) -> str:
        return self._aviso

    @Property("QVariantMap", notify=avisoChanged)
    def detalleAviso(self) -> dict:
        return self._detalle_aviso

    @Slot()
    def limpiarAviso(self) -> None:
        self._fijar_aviso("")


qmlRegisterType(ParametrosCicloController, "Autoclave.Controllers", 1, 0,
                "ParametrosCicloController")

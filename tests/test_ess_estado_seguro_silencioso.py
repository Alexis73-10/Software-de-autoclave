"""ESS (28-oct, planeacion_estado_seguro_silencioso.md): estado seguro
silencioso por sensor sin lectura.

ESS-02: /status publica estado_seguro.silencioso_por_sensor y
camara_segura_motivo_es_sensor (falla cerrada); bloqueado_motivo ya no lleva
el texto de presión sin lectura. ESS-03: sin CIC-10 si el único motivo es un
sensor (presión o Principal); se conserva para el sellado con líquidos y el
tiempo límite con carga caliente. ESS-04: la sección de seguridad oculta las
filas del estado seguro y NO ABRIR; la campana cuenta solo la alarma del
sensor. ESS-05: «— No abrir la puerta» en el nombre de las alarmas del
inventario. La lógica de seguridad (protocolo, válvulas, puertas, inicio,
no_abrir) no cambia.
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from autoclave.core.runtime import camara_segura
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.alarms.catalogo import CIC_10, SEN_03, SEN_06
from autoclave.state_machine.alarms.instancia import EstadoInstancia
from tests.helpers.backend_doble import cargar_servidor, modulo_backend
from tests.test_s9_estado_seguro_arranque import (_CFG, _Config, _arrancar, _loop, _programa,
                                                  _tick_es)

_SELLADO = ("Sensor Principal sin lectura con carga líquida: cámara sellada hasta que las "
            "sondas confirmen la temperatura o venza la espera")


def _cic10(alarmas):
    return [i for i in alarmas.activas()
            if i.codigo == CIC_10 and i.estado is EstadoInstancia.ACTIVA]


def _sen03(alarmas, sensor="temp_camara"):
    from autoclave.state_machine.alarms.catalogo import nombre_legible
    legible = nombre_legible(sensor)
    alarmas.activar(SEN_03, origen=legible, sensor=legible, valor="—")


def _ctx_status(loop, alarmas, vigentes=True):
    ctx = MagicMock()
    cargar_servidor(ctx)
    ctx.control_loop.estado_seguro = loop.estado_seguro
    ctx.control_loop.presion_vigente = vigentes
    ctx.alarm_manager = alarmas
    ctx.config_manager = _Config(_CFG)
    ctx.programas_para_seguridad.return_value = [_programa()]
    ctx.profile = None
    ctx.temp_max_tras_ciclo.return_value = None
    return modulo_backend("rutas.sistema")


def _status(loop, alarmas, vigentes=True):
    """(_camara_segura_status, _estado_seguro_status) con el lazo real."""
    ctx = MagicMock()
    cargar_servidor(ctx)
    ctx.control_loop.estado_seguro = loop.estado_seguro
    ctx.control_loop.presion_vigente = vigentes
    ctx.alarm_manager = alarmas
    ctx.config_manager = _Config(_CFG)
    ctx.programas_para_seguridad.return_value = [_programa()]
    ctx.profile = None
    ctx.temp_max_tras_ciclo.return_value = None
    sistema = modulo_backend("rutas.sistema")
    camara = sistema._camara_segura_status(loop.estado)
    es = sistema._estado_seguro_status(loop.estado,
                                       camara["camara_segura_motivo_es_sensor"] is True)
    return camara, es


# ══ ESS-02: motivos de cámara no segura ═══════════════════════════════════

@pytest.mark.req("ESS-02")
@pytest.mark.parametrize("pres,temp", [
    (None, None), (None, 30.0), (None, 120.0), (250.0, None), (101.3, None),
    (250.0, 120.0), (101.3, 120.0), (50.0, 30.0), (101.3, 30.0), (101.3, 0.0)])
def test_motivos_coincide_con_evaluar(pres, temp):
    estado = EstadoAutoclave()
    estado.sensores_pres["pres_camara"] = pres
    estado.sensores_temp["temp_camara"] = temp
    segura, motivo = camara_segura.evaluar(estado, _CFG, [None])
    lista = camara_segura.motivos(estado, _CFG, [None])
    assert segura is (lista == [])
    if not segura:
        assert lista[0].codigo == motivo.codigo


@pytest.mark.req("ESS-02")
def test_solo_por_sensor_falla_cerrada():
    m = camara_segura.Motivo
    assert camara_segura.solo_por_sensor([m("sin_presion_camara", "x")])
    assert camara_segura.solo_por_sensor([m("sin_presion_camara", "x"), m("sin_temp_camara", "y")])
    assert not camara_segura.solo_por_sensor([])
    assert not camara_segura.solo_por_sensor(["sin código"])
    assert not camara_segura.solo_por_sensor([m("sin_temp_camara", "y"), m("sobrepresion", "z")])
    assert not camara_segura.solo_por_sensor([m("sin_datos_vigentes", "x")])
    assert not camara_segura.solo_por_sensor(None)


# ══ Casos de §5 ═══════════════════════════════════════════════════════════

@pytest.mark.req("ESS-02")
def test_arranque_sin_presion_silencioso_y_sin_cic10():
    alarmas = AlarmManager()
    loop = _loop(alarmas)
    _arrancar(loop, pres=None, temp=30.0)
    _tick_es(loop, 4)
    alarmas.activar(SEN_06, origen="pres_camara")
    camara, es = _status(loop, alarmas)
    assert not _cic10(alarmas)
    # la seguridad no cambia: NO ABRIR y protocolo activo
    assert camara["no_abrir"] is True and loop.estado_seguro.activo
    assert camara["camara_segura_motivo_es_sensor"] is True
    assert es["silencioso_por_sensor"] is True
    # bloqueado_motivo sin el texto de presión (coherente con CIC-10)
    assert es["bloqueado_motivo"] is None
    assert es["detenido_sin_presion"] is True


@pytest.mark.req("ESS-02")
def test_sin_la_alarma_del_sensor_no_hay_silencio():
    """Falla cerrada: si la alarma del sensor no está a la vista, se muestra todo."""
    alarmas = AlarmManager()
    loop = _loop(alarmas)
    _arrancar(loop, pres=None, temp=30.0)
    _tick_es(loop, 4)
    camara, es = _status(loop, alarmas)
    assert camara["camara_segura_motivo_es_sensor"] is False
    assert es["silencioso_por_sensor"] is False


@pytest.mark.req("ESS-03")
def test_principal_perdido_sin_cic10_y_silencioso():
    alarmas = AlarmManager()
    loop = _loop(alarmas)
    _sen03(alarmas)
    _arrancar(loop, pres=101.3, temp=None)
    _tick_es(loop, 4)
    camara, es = _status(loop, alarmas)
    assert not _cic10(alarmas)
    assert loop.estado_seguro.activo and camara["no_abrir"] is True
    assert es["silencioso_por_sensor"] is True
    # la vía de recuperación sigue: el motivo del Principal se publica
    assert "Principal" in (es["bloqueado_motivo"] or "")


@pytest.mark.req("ESS-02")
def test_motivo_mixto_presurizada_y_sensor_se_muestra_todo():
    alarmas = AlarmManager()
    loop = _loop(alarmas)
    _arrancar(loop, pres=250.0, temp=None)
    _tick_es(loop, 4)
    _sen03(alarmas)
    camara, es = _status(loop, alarmas)
    assert camara["camara_segura_motivo_es_sensor"] is False
    assert es["silencioso_por_sensor"] is False


@pytest.mark.req("ESS-02")
def test_paro_con_sensor_perdido_se_ve_el_paro():
    alarmas = AlarmManager()
    loop = _loop(alarmas)
    _arrancar(loop, pres=None, temp=30.0)
    _tick_es(loop, 4)
    alarmas.activar(SEN_06, origen="pres_camara")
    loop.estado.set_flag("PARO_EMERGENCIA", True)
    loop.estado.set_flag("PARO_REAL", True)
    loop.estado_seguro.update(datos_vigentes=True)
    _, es = _status(loop, alarmas)
    assert es["silencioso_por_sensor"] is False
    # paro liberado: confirmación pendiente, tampoco silencioso
    loop.estado.set_flag("PARO_EMERGENCIA", False)
    loop.estado.set_flag("PARO_REAL", False)
    loop.estado_seguro.update(datos_vigentes=True)
    _, es = _status(loop, alarmas)
    assert es["requiere_confirmacion"] is True and es["silencioso_por_sensor"] is False


@pytest.mark.req("ESS-02")
def test_datos_no_vigentes_no_silencia():
    alarmas = AlarmManager()
    loop = _loop(alarmas)
    _arrancar(loop, pres=None, temp=30.0)
    _tick_es(loop, 4)
    alarmas.activar(SEN_06, origen="pres_camara")
    camara, es = _status(loop, alarmas, vigentes=False)
    assert camara["camara_segura_motivo_es_sensor"] is False
    assert es["silencioso_por_sensor"] is False


@pytest.mark.req("ESS-03")
def test_presion_perdida_y_camara_sellada_cic10_visible():
    from autoclave.state_machine.estado_seguro import ProtocoloEstadoSeguro
    alarmas = AlarmManager()
    es = ProtocoloEstadoSeguro(EstadoAutoclave(), _CFG, alarm_manager=alarmas)
    es._protocolo = SimpleNamespace(presion_perdida=True,
                                    bloqueado_motivo="Sensor de presión de cámara sin lectura",
                                    bloqueado_motivo_sin_presion=_SELLADO,
                                    bloqueado_motivo_no_sensor=_SELLADO)
    es._actualizar_alarma_bloqueo()
    [cic10] = _cic10(alarmas)
    assert "sellada" in cic10.descripcion
    assert es.bloqueo_no_sensor is True     # → silencioso_por_sensor False


@pytest.mark.req("ESS-03")
def test_protocolo_real_motivo_no_sensor():
    from autoclave.state_machine.cycle_phases.protocolo_fallo import ProtocoloFallo
    estado = EstadoAutoclave()
    estado.sensores_pres["pres_camara"] = 250.0
    estado.sensores_temp["temp_camara"] = 120.0
    set_do = MagicMock()
    set_do.reset_all_outputs.return_value = True
    prot = ProtocoloFallo(estado, set_do, _programa(modo=2), _CFG)
    prot.ejecutar(solo_lenta=True)
    estado.sensores_temp["temp_camara"] = None
    prot._presion_perdida = True
    assert prot.bloqueado_motivo.startswith("Sensor de presión de cámara")
    assert prot.bloqueado_motivo_sin_presion.startswith("Sensor Principal sin lectura")
    assert prot.bloqueado_motivo_no_sensor is None
    prot._sellado = True
    assert prot.bloqueado_motivo_no_sensor == _SELLADO
    prot._sellado = False
    prot._solo_lenta = False
    prot._aviso_no_escala = True
    assert prot.bloqueado_motivo_no_sensor.startswith("Tiempo límite")


@pytest.mark.req("ESS-02")
def test_estado_seguro_sin_consulta_falla_cerrada():
    from autoclave.state_machine.estado_seguro import ProtocoloEstadoSeguro
    es = ProtocoloEstadoSeguro(EstadoAutoclave(), _CFG)
    es._protocolo = SimpleNamespace(bloqueado_motivo=None)
    assert es.bloqueo_no_sensor is True
    es._protocolo = MagicMock()
    assert es.bloqueo_no_sensor is True


@pytest.mark.req("ESS-02")
def test_puente_sin_el_campo_muestra_todo():
    from autoclave.ui_qml.bridge.ui_bridge import UiBridge
    s = UiBridge._seguridad_de({"no_abrir": True, "estado_seguro": {"activo": True}})
    assert s["es_silencioso"] is False and s["no_abrir_por_sensor"] is False
    s = UiBridge._seguridad_de({})
    assert s["es_silencioso"] is False and s["no_abrir_por_sensor"] is False
    s = UiBridge._seguridad_de({"motivo_es_sensor": "true",
                                "estado_seguro": {"silencioso_por_sensor": 1}})
    assert s["es_silencioso"] is False and s["no_abrir_por_sensor"] is False
    s = UiBridge._seguridad_de({"motivo_es_sensor": True,
                                "estado_seguro": {"silencioso_por_sensor": True}})
    assert s["es_silencioso"] is True and s["no_abrir_por_sensor"] is True


# ══ ESS-05: textos ════════════════════════════════════════════════════════

@pytest.mark.req("ESS-05")
@pytest.mark.parametrize("codigo", ["SEN-02", "SEN-03", "SEN-04", "SEN-05", "SEN-06", "SEN-08",
                                    "CIC-19"])
def test_nombre_dice_no_abrir_la_puerta(codigo):
    from autoclave import i18n
    from autoclave.state_machine.alarms.catalogo import CATALOGO
    assert CATALOGO[codigo].titulo.endswith(" — No abrir la puerta")
    raiz = __import__("pathlib").Path(i18n.__file__).parent
    es = json.loads((raiz / "es.json").read_text(encoding="utf-8"))
    en = json.loads((raiz / "en.json").read_text(encoding="utf-8"))

    def titulo(d):
        pila = [d]
        while pila:
            x = pila.pop()
            if isinstance(x, dict):
                if codigo in x and isinstance(x[codigo], dict) and "titulo" in x[codigo]:
                    return x[codigo]["titulo"]
                pila.extend(x.values())
    assert titulo(es).endswith(" — No abrir la puerta")
    assert titulo(en).endswith(" — Do not open the door")


@pytest.mark.req("ESS-05")
def test_sen07_y_comunicacion_sin_el_sufijo():
    from autoclave.state_machine.alarms.catalogo import CATALOGO
    assert "No abrir" not in CATALOGO["SEN-07"].titulo
    assert "No abrir" not in CATALOGO["CIC-10"].titulo


# ══ ESS-04: sección de seguridad y campana (QML) ══════════════════════════

_QML = """
import QtQuick
import "Componentes"
Item {
    width: 600; height: 1600
    QtObject {
        id: puenteFalso
        property bool noAbrir: true
        property string noAbrirMotivo: "Sin lectura válida de presión de cámara"
        property bool noAbrirPorSensor: true
        property bool paroActivo: false
        property bool estadoSeguroActivo: true
        property bool estadoSeguroRequiereConfirmacion: false
        property bool estadoSeguroSilencioso: true
        property string estadoSeguroCausa: "arranque"
        property string estadoSeguroBloqueadoMotivo: ""
        property string estadoSeguroBloqueadoClave: ""
        property bool estadoSeguroBloqueoPorSonda: false
        property bool modoPrueba: false
        property bool connected: true
        property string estadoModuloEs: "ok"
    }
    QtObject {
        id: comandosFalsos
        property bool ocupado: false
        property string mensaje: ""
        property int asignaciones: 0
        function confirmarEstadoSeguro() {}
        function asignarSondaPrincipal() { asignaciones += 1 }
    }
    property alias puente: puenteFalso
    property alias comandos: comandosFalsos
    ListModel { id: alarmasFalsas }
    function agregar(codigo) {
        alarmasFalsas.append({id: codigo, codigo: codigo, description: "x", level: "FALLA",
                              priority: "media", titulo: codigo + " — No abrir la puerta"})
    }
    PanelNotificaciones {
        id: pn
        objectName: "panelPrueba"
        alarmas: alarmasFalsas
        puente: puenteFalso
        comandosSistema: comandosFalsos
    }
    SeccionEstadoSeguro {
        objectName: "seccion"
        puente: puenteFalso
        comandos: comandosFalsos
    }
    VentanaDetalleAlarma {
        id: detalle
        objectName: "detalle"
        bloqueoPorSonda: puenteFalso.estadoSeguroBloqueoPorSonda
        onAsignarSondaPulsado: comandosFalsos.asignarSondaPrincipal()
    }
}
"""

_SCRIPT = r"""
panel = raiz.findChild(QObject, "panelPrueba")
seccion = raiz.findChild(QObject, "seccion")
def vis(nombre):
    return bool(seccion.findChild(QObject, nombre).property("visible"))
FILAS = ["filaEstadoSeguroEnCurso", "avisoCausaEstadoSeguro", "botonConfirmarEstadoSeguro",
         "notaNoAbrirEnCurso", "avisoEstadoSeguroDetenido", "filaNoAbrir"]
QMetaObject.invokeMethod(raiz, "agregar", Q_ARG("QVariant", "SEN-06"))
app.processEvents()
# foto de referencia: solo SEN-06, campana en 1
r["silencio_filas_ocultas"] = not any(vis(f) for f in FILAS)
r["silencio_campana_1"] = panel.property("conteoTotal") == 1
r["silencio_seccion_0"] = seccion.property("conteoTotal") == 0
# sin el dato del puente (falla cerrada): se muestra el estado seguro
puente.setProperty("estadoSeguroSilencioso", False)
r["sin_silencio_en_curso"] = vis("filaEstadoSeguroEnCurso") and vis("botonConfirmarEstadoSeguro")
r["sin_silencio_campana_2"] = panel.property("conteoTotal") == 2
puente.setProperty("estadoSeguroSilencioso", True)
# paro: se ve aunque el backend diga silencioso
puente.setProperty("paroActivo", True)
r["paro_visible"] = vis("filaParo") and seccion.property("conteoTotal") == 1
puente.setProperty("paroActivo", False)
# confirmación pendiente: se ve
puente.setProperty("estadoSeguroRequiereConfirmacion", True)
r["confirmar_visible"] = vis("filaEstadoSeguroPendiente") and vis("botonConfirmarEstadoSeguro")
puente.setProperty("estadoSeguroRequiereConfirmacion", False)
# módulo E/S sin datos: se ve
puente.setProperty("estadoModuloEs", "sin_tramas_validas")
r["sin_datos_visible"] = vis("filaModuloEsSinDatos") and vis("filaEstadoSeguroEnCurso")
puente.setProperty("estadoModuloEs", "ok")
# sin conexión: se ve
puente.setProperty("connected", False)
r["sin_conexion_visible"] = vis("filaSeguridadDesconocida")
puente.setProperty("connected", True)
# fuera del estado seguro: NO ABRIR oculto solo si el motivo es un sensor
puente.setProperty("estadoSeguroActivo", False)
r["no_abrir_oculto_por_sensor"] = not vis("filaNoAbrir")
puente.setProperty("noAbrirPorSensor", False)
r["no_abrir_visible_otro_motivo"] = vis("filaNoAbrir")
# botón de asignar sonda en el detalle de SEN-02/SEN-03 (ESS-04)
detalle = raiz.findChild(QObject, "detalle")
boton = detalle.findChild(QObject, "botonAsignarSondaDetalle")
detalle.setProperty("datos", {"id": "SEN-03", "codigo": "SEN-03"})
r["asignar_oculto_sin_bloqueo"] = not detalle.property("asignarSonda")
puente.setProperty("estadoSeguroBloqueoPorSonda", True)
r["asignar_visible_sen03"] = detalle.property("asignarSonda") is True and boton is not None
detalle.setProperty("datos", {"id": "SEN-06", "codigo": "SEN-06"})
r["asignar_oculto_sen06"] = not detalle.property("asignarSonda")
r["avisos"] = avisos
print(json.dumps(r))
"""


@pytest.mark.req("ESS-04")
def test_seccion_silenciosa_y_campana_en_1():
    pytest.importorskip("PySide6")
    from tests.test_t7_avisos_qml import _CABECERA, _correr
    s = _correr(_CABECERA + _SCRIPT, _QML)
    assert s.pop("avisos") == []
    assert all(s.values()), {k: v for k, v in s.items() if not v}


# ══ Revisión de seguridad ESS (SAF-04 a SAF-08) ══════════════════════════

@pytest.mark.req("ESS-02")
def test_saf04_otra_sonda_caliente_no_silencia():
    alarmas = AlarmManager()
    loop = _loop(alarmas)
    _sen03(alarmas)
    _arrancar(loop, pres=101.3, temp=None)
    loop.estado.sensores_temp["temp_ref"] = 120.0
    _tick_es(loop, 4)
    camara, es = _status(loop, alarmas)
    assert camara["camara_segura_motivo_es_sensor"] is False
    assert es["silencioso_por_sensor"] is False
    # el drenaje caliente no cuenta
    loop.estado.sensores_temp["temp_ref"] = 30.0
    loop.estado.sensores_temp["temp_drenaje"] = 120.0
    camara, es = _status(loop, alarmas)
    assert camara["camara_segura_motivo_es_sensor"] is True


@pytest.mark.req("ESS-02")
def test_saf05_presion_perdida_con_la_camara_presurizada_no_silencia():
    alarmas = AlarmManager()
    loop = _loop(alarmas)
    _arrancar(loop, pres=250.0, temp=30.0)
    _tick_es(loop, 4)
    alarmas.activar(SEN_06, origen="pres_camara")
    sistema = _ctx_status(loop, alarmas)
    assert sistema._camara_segura_status(loop.estado)["camara_segura_motivo_es_sensor"] is False
    loop.estado.sensores_pres["pres_camara"] = None     # se pierde a 250 kPa
    _tick_es(loop, 4)
    camara = sistema._camara_segura_status(loop.estado)
    assert camara["camara_segura_motivo_es_sensor"] is False
    es = sistema._estado_seguro_status(loop.estado, False)
    assert es["silencioso_por_sensor"] is False
    # perdida en la banda atm: sí
    loop.estado.sensores_pres["pres_camara"] = 101.3
    sistema._camara_segura_status(loop.estado)
    loop.estado.sensores_pres["pres_camara"] = None
    assert sistema._camara_segura_status(loop.estado)["camara_segura_motivo_es_sensor"] is True


@pytest.mark.req("ESS-02")
def test_saf05_enfriando_en_modo_4_no_silencia():
    from autoclave.state_machine.estado_seguro import ProtocoloEstadoSeguro
    prot = MagicMock()
    prot.bloqueado_motivo_no_sensor = None
    prot._modo_efectivo.return_value = 4
    prot._sub_etapa = "enfriamiento"
    es = ProtocoloEstadoSeguro(EstadoAutoclave(), _CFG)
    es._protocolo = prot
    assert es.bloqueo_no_sensor is True
    prot._sub_etapa = None
    assert es.bloqueo_no_sensor is False


@pytest.mark.req("ESS-02")
def test_saf06_alarma_de_otra_sonda_no_silencia():
    alarmas = AlarmManager()
    loop = _loop(alarmas)
    _sen03(alarmas, "temp_ref")         # SEN-03 de una Referencia, no del Principal
    _arrancar(loop, pres=101.3, temp=None)
    _tick_es(loop, 4)
    camara, _ = _status(loop, alarmas)
    assert camara["camara_segura_motivo_es_sensor"] is False
    # CIC-10 se conserva: no hay alarma del Principal a la vista (SAF-07)
    [cic10] = _cic10(alarmas)
    assert "Principal" in cic10.descripcion


@pytest.mark.req("ESS-03")
def test_saf07_sin_alarma_del_principal_cic10_se_conserva():
    alarmas = AlarmManager()
    loop = _loop(alarmas)
    _arrancar(loop, pres=101.3, temp=None)
    _tick_es(loop, 4)
    [cic10] = _cic10(alarmas)
    assert "Principal" in cic10.descripcion


@pytest.mark.req("ESS-02")
def test_saf08_inactivo_falla_cerrada():
    from autoclave.state_machine.estado_seguro import ProtocoloEstadoSeguro
    es = ProtocoloEstadoSeguro(EstadoAutoclave(), _CFG)
    assert es.bloqueo_no_sensor is True

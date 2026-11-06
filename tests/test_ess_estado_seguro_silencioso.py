"""ESS (28-oct, planeacion_estado_seguro_silencioso.md): estado seguro
silencioso por sensor sin lectura.

Hotfix ES (6-nov): el protocolo de estado seguro se retiró; quedan las
pruebas de camara_segura_motivo_es_sensor (NO ABRIR oculto solo por un
sensor sin lectura, con su alarma a la vista) y de los nombres de alarma.

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
from tests.test_s9_estado_seguro_arranque import (_CFG, _Config, _arrancar, _loop, _programa,  # noqa: F401
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
def test_arranque_sin_presion_motivo_de_sensor_y_sin_cic10():
    # Hotfix ES (6-nov): sin protocolo; NO ABRIR sigue y su motivo es el sensor
    alarmas = AlarmManager()
    loop = _loop(alarmas)
    _arrancar(loop, pres=None, temp=30.0)
    _tick_es(loop, 4)
    alarmas.activar(SEN_06, origen="pres_camara")
    camara, es = _status(loop, alarmas)
    assert not _cic10(alarmas)
    assert camara["no_abrir"] is True and not loop.estado_seguro.activo
    assert camara["camara_segura_motivo_es_sensor"] is True
    assert es["activo"] is False and es["silencioso_por_sensor"] is False


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
def test_principal_perdido_sin_cic10_y_motivo_de_sensor():
    alarmas = AlarmManager()
    loop = _loop(alarmas)
    _sen03(alarmas)
    _arrancar(loop, pres=101.3, temp=None)
    _tick_es(loop, 4)
    camara, es = _status(loop, alarmas)
    assert not _cic10(alarmas)
    assert not loop.estado_seguro.activo and camara["no_abrir"] is True
    assert camara["camara_segura_motivo_es_sensor"] is True


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
    loop.estado_seguro.update()
    _, es = _status(loop, alarmas)
    assert es["silencioso_por_sensor"] is False
    # paro liberado: confirmación pendiente, tampoco silencioso
    loop.estado.set_flag("PARO_EMERGENCIA", False)
    loop.estado.set_flag("PARO_REAL", False)
    loop.estado_seguro.update()
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
    obj = seccion.findChild(QObject, nombre)
    return obj is not None and bool(obj.property("visible"))
QMetaObject.invokeMethod(raiz, "agregar", Q_ARG("QVariant", "SEN-06"))
app.processEvents()
# hotfix ES (6-nov): ya no hay filas de "estado seguro en curso"
r["sin_filas_del_protocolo"] = all(
    seccion.findChild(QObject, f) is None
    for f in ("filaEstadoSeguroEnCurso", "avisoCausaEstadoSeguro", "notaNoAbrirEnCurso",
              "avisoEstadoSeguroDetenido"))
r["solo_la_alarma_del_sensor"] = panel.property("conteoTotal") == 1
# paro: se ve
puente.setProperty("paroActivo", True)
r["paro_visible"] = vis("filaParo") and seccion.property("conteoTotal") == 1
puente.setProperty("paroActivo", False)
# confirmación pendiente: se ve
puente.setProperty("estadoSeguroRequiereConfirmacion", True)
r["confirmar_visible"] = vis("filaEstadoSeguroPendiente") and vis("botonConfirmarEstadoSeguro")
puente.setProperty("estadoSeguroRequiereConfirmacion", False)
# módulo E/S sin datos: se ve
puente.setProperty("estadoModuloEs", "sin_tramas_validas")
r["sin_datos_visible"] = vis("filaModuloEsSinDatos")
puente.setProperty("estadoModuloEs", "ok")
# sin conexión: se ve
puente.setProperty("connected", False)
r["sin_conexion_visible"] = vis("filaSeguridadDesconocida")
puente.setProperty("connected", True)
# NO ABRIR oculto solo si el motivo es un sensor
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
def test_seccion_sin_protocolo_y_campana_en_1():
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
def test_saf06_alarma_de_otra_sonda_no_silencia():
    alarmas = AlarmManager()
    loop = _loop(alarmas)
    _sen03(alarmas, "temp_ref")         # SEN-03 de una Referencia, no del Principal
    _arrancar(loop, pres=101.3, temp=None)
    _tick_es(loop, 4)
    camara, _ = _status(loop, alarmas)
    assert camara["camara_segura_motivo_es_sensor"] is False
    # hotfix ES: sin protocolo no hay CIC-10; NO ABRIR se muestra (no es sensor)
    assert not _cic10(alarmas) and camara["no_abrir"] is True


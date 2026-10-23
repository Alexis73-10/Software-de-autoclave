"""T3 (tanda 2026-10-14 §1.1): catálogo de sensores de temperatura del ciclo
y roles por programa (principal / referencia / no_en_uso)."""

from types import SimpleNamespace

import pytest

from autoclave.core.runtime import sensores_ciclo as sc
from autoclave.installation.equipment import EquipmentClass


def _prog(asignacion=None):
    return SimpleNamespace(sensores=asignacion)


# ── Catálogo ────────────────────────────────────────────────────────────────

def test_catalogo_tres_sensores_y_nombres_de_ubicacion():
    assert sc.SENSORES == ("temp_camara", "temp_2_camara", "temp_ref")
    assert sc.NOMBRES == {"temp_camara": "Cámara 1", "temp_2_camara": "Cámara 2",
                          "temp_ref": "Referencia"}


def test_asignacion_de_fabrica():
    assert sc.asignacion_por_omision() == {
        "temp_camara": "principal", "temp_2_camara": "no_en_uso", "temp_ref": "no_en_uso"}


# ── Migración perezosa ──────────────────────────────────────────────────────

@pytest.mark.parametrize("crudo", [None, {"1": "temp_camara", "2": "temp_ref"}, "x", []])
def test_formato_antiguo_o_ausente_se_interpreta_por_omision(crudo):
    asignacion, antiguo = sc.interpretar_asignacion(crudo)
    assert asignacion == sc.asignacion_por_omision()
    assert antiguo is True


def test_formato_nuevo_completa_ausentes_como_no_en_uso():
    asignacion, antiguo = sc.interpretar_asignacion({"temp_ref": "principal"})
    assert antiguo is False
    assert asignacion == {"temp_camara": "no_en_uso", "temp_2_camara": "no_en_uso",
                          "temp_ref": "principal"}


# ── Invariantes ─────────────────────────────────────────────────────────────

def test_asignacion_valida():
    assert sc.errores_asignacion({"temp_camara": "principal", "temp_2_camara": "referencia",
                                  "temp_ref": "referencia"}) == []


@pytest.mark.parametrize("asignacion", [
    {"temp_camara": "no_en_uso", "temp_2_camara": "no_en_uso", "temp_ref": "no_en_uso"},
    {"temp_camara": "principal", "temp_2_camara": "principal", "temp_ref": "no_en_uso"},
    {"temp_camara": "principal", "temp_2_camara": "referencia", "temp_ref": "otro"},
    {"temp_camara": "principal", "temp_chaqueta": "referencia"},
    "no es dict",
])
def test_asignacion_invalida(asignacion):
    assert sc.errores_asignacion(asignacion) != []


def test_tres_referencias_imposible_con_tres_sensores_pero_se_valida_el_maximo():
    assert sc.MAX_REFERENCIAS == 2


# ── Resolución en tiempo de ejecución ───────────────────────────────────────

def test_principal_del_programa():
    p = _prog({"temp_camara": "no_en_uso", "temp_2_camara": "principal", "temp_ref": "referencia"})
    assert sc.sensor_principal(p) == "temp_2_camara"
    assert sc.sensores_referencia(p) == ["temp_ref"]
    assert sc.sensores_en_uso(p) == ["temp_2_camara", "temp_ref"]


def test_sin_programa_principal_es_temp_camara():
    assert sc.sensor_principal(None) == "temp_camara"
    assert sc.sensores_en_uso(None) == ["temp_camara"]


def test_programa_sin_asignacion_usa_la_de_fabrica():
    assert sc.sensor_principal(_prog(None)) == "temp_camara"
    assert sc.sensores_referencia(_prog(None)) == []


def test_programa_con_asignacion_invalida_principal_temp_camara_y_no_ejecutable():
    p = _prog({"temp_camara": "no_en_uso", "temp_2_camara": "no_en_uso", "temp_ref": "no_en_uso"})
    assert sc.sensor_principal(p) == "temp_camara"
    assert sc.errores_asignacion(p.sensores) != []


def test_temp_principal_lee_el_sensor_principal():
    p = _prog({"temp_camara": "no_en_uso", "temp_2_camara": "no_en_uso", "temp_ref": "principal"})
    estado = SimpleNamespace(sensores_temp={"temp_camara": 130.0, "temp_ref": 120.5})
    assert sc.temp_principal(estado, p) == 120.5


# ── Declaración por la instalación ──────────────────────────────────────────

def _perfil(clase, probes=None):
    return SimpleNamespace(equipment_class=clase, temperature_probes=probes)


def test_piso_no_declara_camara_2():
    perfil = _perfil(EquipmentClass.PISO)
    assert sc.sensores_declarados(perfil) == ["temp_camara", "temp_ref"]


def test_lab_declara_las_tres():
    perfil = _perfil(EquipmentClass.PISO_LAB)
    assert sc.sensores_declarados(perfil) == ["temp_camara", "temp_2_camara", "temp_ref"]


def test_sonda_declarada_sin_instalar_no_se_declara():
    perfil = _perfil(EquipmentClass.PISO_LAB, {"temp_ref": False})
    assert sc.sensores_declarados(perfil) == ["temp_camara", "temp_2_camara"]


def test_sin_perfil_se_declaran_las_tres():
    assert sc.sensores_declarados(None) == list(sc.SENSORES)


@pytest.mark.parametrize("lectura,esperado", [
    (25.0, "disponible"), (None, "sin_senal"), (float("nan"), "sin_senal")])
def test_estado_sensor(lectura, esperado):
    estado = SimpleNamespace(sensores_temp={"temp_ref": lectura})
    assert sc.estado_sensor(_perfil(EquipmentClass.PISO), estado, "temp_ref") == esperado


def test_estado_sensor_no_instalado():
    estado = SimpleNamespace(sensores_temp={"temp_2_camara": 25.0})
    assert sc.estado_sensor(_perfil(EquipmentClass.PISO), estado, "temp_2_camara") == "no_instalado"


# ── F0 solo en laboratorio ──────────────────────────────────────────────────

@pytest.mark.parametrize("clase,esperado", [
    (EquipmentClass.PISO, False), (EquipmentClass.MESA_B, False),
    (EquipmentClass.PISO_LAB, True), (EquipmentClass.MESA_B_LAB, True)])
def test_f0_disponible_por_clase(clase, esperado):
    assert sc.f0_disponible(_perfil(clase)) is esperado


# ── Verificación al iniciar (RS-06) ─────────────────────────────────────────

def test_inicio_ok():
    estado = SimpleNamespace(sensores_temp={"temp_camara": 25.0, "temp_ref": 24.0})
    p = _prog({"temp_camara": "principal", "temp_2_camara": "no_en_uso", "temp_ref": "referencia"})
    assert sc.verificar_inicio(p, _perfil(EquipmentClass.PISO), estado) is None


def test_inicio_bloqueado_por_asignacion_invalida():
    estado = SimpleNamespace(sensores_temp={"temp_camara": 25.0})
    p = _prog({"temp_camara": "no_en_uso", "temp_2_camara": "no_en_uso", "temp_ref": "no_en_uso"})
    codigo, _ = sc.verificar_inicio(p, _perfil(EquipmentClass.PISO), estado)
    assert codigo == "ASIGNACION_SENSORES_INVALIDA"


def test_inicio_bloqueado_por_sensor_en_uso_sin_lectura():
    estado = SimpleNamespace(sensores_temp={"temp_camara": 25.0, "temp_ref": None})
    p = _prog({"temp_camara": "principal", "temp_2_camara": "no_en_uso", "temp_ref": "referencia"})
    codigo, detalle = sc.verificar_inicio(p, _perfil(EquipmentClass.PISO), estado)
    assert codigo == "SENSOR_NO_DISPONIBLE" and "temp_ref" in detalle


def test_inicio_bloqueado_por_sensor_en_uso_no_instalado():
    estado = SimpleNamespace(sensores_temp={"temp_camara": 25.0, "temp_2_camara": 25.0})
    p = _prog({"temp_camara": "principal", "temp_2_camara": "referencia", "temp_ref": "no_en_uso"})
    codigo, _ = sc.verificar_inicio(p, _perfil(EquipmentClass.PISO), estado)
    assert codigo == "SENSOR_NO_DISPONIBLE"


def test_inicio_ignora_sensores_no_en_uso_sin_lectura():
    estado = SimpleNamespace(sensores_temp={"temp_camara": 25.0, "temp_ref": None,
                                            "temp_2_camara": None})
    assert sc.verificar_inicio(_prog(None), _perfil(EquipmentClass.PISO_LAB), estado) is None


def test_json_canonico_ordena_claves():
    a = {"temp_ref": "no_en_uso", "temp_camara": "principal", "temp_2_camara": "no_en_uso"}
    assert sc.canonica(a) == ('{"temp_2_camara": "no_en_uso", "temp_camara": "principal", '
                              '"temp_ref": "no_en_uso"}')


# ── PREPARACION / PREPARADO: alerta no bloqueante (tanda §1.1) ──────────────

from tests.test_adenda_estados import _make, _ESTADOS          # noqa: E402
from tests.alarmas_helpers import codigos_activados, codigos_resueltos  # noqa: E402


@pytest.mark.parametrize("clase", _ESTADOS)
@pytest.mark.parametrize("sensor", ["temp_camara", "temp_2_camara", "temp_ref"])
@pytest.mark.parametrize("valor", [None, float("nan"), 0])
def test_sensor_del_ciclo_sin_lectura_alerta_sin_bloquear(clase, sensor, valor):
    obj, am, set_do = _make(clase, None, **{sensor: valor})
    # S11 (D11-3): SEN-03 solo vigila los sensores en uso; el programa usa los tres
    obj.cycle.sensores = {"temp_camara": "principal", "temp_2_camara": "referencia",
                          "temp_ref": "referencia"}
    assert obj.verificar_sensores() is True          # no bloquea el paso a listo
    assert "SEN-03" in codigos_activados(am)
    assert "SEN-01" not in codigos_activados(am)


@pytest.mark.parametrize("clase", _ESTADOS)
def test_sensor_del_ciclo_no_declarado_no_se_vigila(clase):
    perfil = SimpleNamespace(equipment_class=EquipmentClass.PISO, temperature_probes=None,
                             supply_inputs=None, door_count=2, door_type=None)
    obj, am, _ = _make(clase, perfil, temp_2_camara=None)
    obj.verificar_sensores()
    assert "SEN-03" not in codigos_activados(am)


@pytest.mark.parametrize("clase", _ESTADOS)
def test_sensor_del_ciclo_con_lectura_resuelve_la_alerta(clase):
    obj, am, _ = _make(clase, None)
    obj.verificar_sensores()
    assert "SEN-03" in codigos_resueltos(am)


@pytest.mark.parametrize("clase", _ESTADOS)
def test_sensor_del_ciclo_caido_no_apaga_el_vapor_de_chaqueta(clase):
    obj, _, set_do = _make(clase, None, pres_chaqueta=200.0, temp_ref=None)
    obj.run()
    set_do.vapor_chaqueta_on.assert_called()


# ── CicloState: vigilancia de los sensores en uso ───────────────────────────

from unittest.mock import MagicMock                             # noqa: E402
from autoclave.state_machine.alarms.alarm_manager import AlarmManager  # noqa: E402
from autoclave.state_machine.states.ciclo import CicloState     # noqa: E402


def _ciclo(asignacion, sensores_temp):
    estado = MagicMock()
    estado.sensores_temp = sensores_temp
    estado.sensores_pres = {"pres_camara": 200.0, "pres_chaqueta": 300.0,
                            "pres_empaque_1": 300.0, "pres_empaque_2": 300.0}
    estado.sensores_di = {"puerta_1_cerrada": 1, "puerta_2_cerrada": 1, "vapor_suministro": 1}
    estado.get_flag.side_effect = lambda f: False
    estado.motivo_fallo = ""
    cycle = MagicMock()
    cycle.get_param.return_value = None
    copia = MagicMock()
    copia.get_param.return_value = None
    copia.sensores = asignacion
    cycle.copia.return_value = copia
    config = MagicMock(); config.get.return_value = None
    am = AlarmManager()
    ciclo = CicloState(estado, MagicMock(), cycle, config, am)
    ciclo.reset()
    ciclo._protocolo = MagicMock()
    return ciclo, estado, am


_ASIG_REF = {"temp_camara": "principal", "temp_2_camara": "no_en_uso", "temp_ref": "referencia"}
_ASIG_P2 = {"temp_camara": "no_en_uso", "temp_2_camara": "principal", "temp_ref": "no_en_uso"}


def test_temp_camara_no_en_uso_sin_lectura_no_falla():
    ciclo, estado, am = _ciclo(_ASIG_P2, {"temp_camara": None, "temp_2_camara": 100.0})
    fase = ciclo._fases[0]
    fase.update = MagicMock(return_value=None)
    ciclo.run()
    assert estado.fase_ciclo != "SENSOR_AUSENTE"
    fase.update.assert_called_once()


def test_principal_sin_lectura_falla_antes_de_la_fase():
    ciclo, estado, am = _ciclo(_ASIG_P2, {"temp_camara": 100.0, "temp_2_camara": None})
    fase = ciclo._fases[0]
    fase.update = MagicMock()
    ciclo.run()
    assert estado.fase_ciclo == "SENSOR_AUSENTE"
    fase.update.assert_not_called()                # la vigilancia precede a la fase
    assert [i.codigo for i in am.activas()] == ["SEN-02"]


def test_referencia_sin_lectura_tambien_falla():
    # DECISIÓN SIN CONFIRMAR de la tanda: Referencia caída = mismo FALLO
    ciclo, estado, _ = _ciclo(_ASIG_REF, {"temp_camara": 100.0, "temp_ref": None})
    ciclo._fases[0].update = MagicMock()
    ciclo.run()
    assert estado.fase_ciclo == "SENSOR_AUSENTE"


# ── Fases: control con el Principal y referencias ───────────────────────────

from autoclave.state_machine.cycle_phases.base_fase import BaseFase  # noqa: E402


def test_base_fase_lee_el_principal_y_las_referencias():
    estado = SimpleNamespace(sensores_temp={"temp_camara": 130.0, "temp_2_camara": 121.0,
                                            "temp_ref": 119.0})
    fase = BaseFase(estado, None, _prog({"temp_camara": "referencia",
                                          "temp_2_camara": "principal",
                                          "temp_ref": "referencia"}), None, None, None)
    assert fase._temp_principal() == 121.0
    assert fase._temps_referencia() == {"temp_camara": 130.0, "temp_ref": 119.0}


# ── CALENTAMIENTO: entrada a esterilización con Referencias (§1.1 a) ────────

from autoclave.core.runtime.steam import p_saturacion_kpa                # noqa: E402
from autoclave.state_machine.cycle_phases.base_fase import FaseResult     # noqa: E402
from tests import test_calentamiento_fase as tcal                        # noqa: E402
from tests import test_esterilizacion_fase as test_                      # noqa: E402


def _calentamiento_con_referencia(t_ref):
    fase, estado, _ = tcal._make_fase(t_obj=134.0, presion_add=11.0, tiempo_estable=5)
    fase.cycle.sensores = _ASIG_REF
    fase.update()
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_temp["temp_ref"] = t_ref
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(134.0) + 11.0
    fase.update()
    return fase, estado


def test_referencia_fria_impide_la_ventana_de_estabilidad():
    fase, _ = _calentamiento_con_referencia(130.0)
    assert fase._timer_sostenido_desde is None


def test_referencia_en_consigna_permite_completar():
    fase, _ = _calentamiento_con_referencia(134.2)
    assert fase._timer_sostenido_desde is not None
    fase._timer_sostenido_desde -= 6
    assert fase.update() == FaseResult.COMPLETADO


def test_principal_temp_2_camara_controla_el_calentamiento():
    fase, estado, _ = tcal._make_fase(t_obj=134.0, presion_add=11.0, tiempo_estable=5)
    fase.cycle.sensores = _ASIG_P2
    fase.update()
    estado.sensores_temp["temp_camara"] = 20.0          # no en uso: no cuenta
    estado.sensores_temp["temp_2_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(134.0) + 11.0
    fase.update()
    assert fase._en_sostenimiento is True


# ── ESTERILIZACION: uniformidad térmica de las Referencias (§1.1 b) ─────────

def _esterilizacion_con_referencia(t_ref):
    fase, estado, _ = test_._make_fase(t_est=121.0)
    fase.cycle.sensores = _ASIG_REF
    estado.sensores_temp["temp_ref"] = t_ref
    return fase, estado


def test_referencia_fuera_de_rango_alerta_una_vez_y_no_falla():
    fase, estado = _esterilizacion_con_referencia(115.0)
    resultados = [fase.update() for _ in range(5)]
    assert FaseResult.FALLO not in resultados
    llamadas = [c for c in fase.alarm_manager.activar.call_args_list if c.args[0] == "CIC-09"]
    assert len(llamadas) == 1
    assert llamadas[0].kwargs["sensor"] == "Referencia"


def test_referencia_fuera_de_rango_necesita_debounce():
    fase, _ = _esterilizacion_con_referencia(115.0)
    fase.update()
    fase.update()
    assert not [c for c in fase.alarm_manager.activar.call_args_list if c.args[0] == "CIC-09"]


def test_referencia_en_rango_no_alerta():
    fase, _ = _esterilizacion_con_referencia(121.5)
    for _ in range(5):
        fase.update()
    assert not [c for c in fase.alarm_manager.activar.call_args_list if c.args[0] == "CIC-09"]


def test_f0_desactivado_en_equipo_no_lab():
    fase, estado, _ = test_._make_fase(t_est=121.0, tiempo_min=0.001, f0_activo=True,
                                       f0_objetivo=50.0)
    fase.cap = SimpleNamespace(has_liquid_sensor=False)
    fase.update()
    fase._timer_fin = 0                     # tiempo cumplido
    assert fase.update() == FaseResult.COMPLETADO     # sin exigir F0


# ── SAF-01 de la revisión de T3: temperatura de seguridad tras un ciclo ─────

_ASIG_REF_PRINCIPAL = {"temp_camara": "no_en_uso", "temp_2_camara": "no_en_uso",
                       "temp_ref": "principal"}


def test_temp_seguridad_toma_el_maximo_de_los_principales():
    estado = SimpleNamespace(sensores_temp={"temp_camara": 120.0, "temp_ref": 40.0})
    programas = [_prog(_ASIG_REF_PRINCIPAL), _prog(None)]   # seleccionado frío + último ciclo
    assert sc.temp_seguridad(estado, programas) == 120.0


def test_temp_seguridad_none_si_falta_una_lectura():
    estado = SimpleNamespace(sensores_temp={"temp_camara": None, "temp_ref": 40.0})
    assert sc.temp_seguridad(estado, [_prog(_ASIG_REF_PRINCIPAL), _prog(None)]) is None


def test_temp_seguridad_principal_no_declarado_no_es_seguro():
    perfil = SimpleNamespace(equipment_class=EquipmentClass.PISO, temperature_probes=None)
    p = _prog({"temp_camara": "no_en_uso", "temp_2_camara": "principal", "temp_ref": "no_en_uso"})
    estado = SimpleNamespace(sensores_temp={"temp_2_camara": 30.0})
    assert sc.temp_seguridad(estado, p, perfil) is None


def _loop_seguridad():
    from unittest.mock import patch
    from autoclave.services.domain.loop.control_loop import ControlLoop
    from autoclave.core.runtime.status import EstadoAutoclave
    estado = EstadoAutoclave()
    cm = MagicMock()
    seleccionado = _prog(_ASIG_REF_PRINCIPAL)
    cm.get_selected_cycle.return_value = seleccionado
    config = MagicMock()
    config.get.side_effect = lambda k, d=None: {"presion_admosferica": 101.3,
                                                "rango_presion_atm": 10.0,
                                                "temp_max_apertura": 80.0}.get(k, d)
    with patch("autoclave.services.domain.loop.control_loop.StateMachine"):
        loop = ControlLoop(units=MagicMock(), door_service=MagicMock(), doors=[],
                           estado=estado, link=MagicMock(), set_do=MagicMock(),
                           alarm_manager=MagicMock(), cycle_manager=cm, config_manager=config)
    loop.cycle = seleccionado
    return loop, estado


def test_tras_un_ciclo_cuenta_el_principal_del_ultimo_ciclo_hasta_que_sea_seguro():
    from autoclave.state_machine.machine.enum_global import GlobalState
    loop, estado = _loop_seguridad()
    ultimo = _prog(None)                               # Principal = temp_camara
    estado.set_machine_state(GlobalState.CICLO)
    loop.state_machine.ciclo.programa_en_curso = ultimo
    loop._seguir_programa_ultimo_ciclo()
    estado.set_machine_state(GlobalState.FALLA)
    estado.sensores_pres["pres_camara"] = 101.3
    estado.sensores_temp.update({"temp_camara": 120.0, "temp_ref": 40.0})
    loop._seguir_programa_ultimo_ciclo()
    assert loop.programas_para_seguridad() == [loop.cycle, ultimo]   # sigue caliente
    estado.sensores_temp["temp_camara"] = 60.0
    loop._seguir_programa_ultimo_ciclo()
    loop._seguir_programa_ultimo_ciclo()
    assert ultimo in loop.programas_para_seguridad()                # debounce: 2 ticks
    loop._seguir_programa_ultimo_ciclo()
    assert loop.programas_para_seguridad() == [loop.cycle]           # 3 ticks: segura


def test_set_active_cycle_conserva_el_ultimo_ciclo():
    from autoclave.state_machine.machine.enum_global import GlobalState
    from unittest.mock import patch
    loop, estado = _loop_seguridad()
    ultimo = _prog(None)
    loop._programa_ultimo_ciclo = ultimo
    estado.set_machine_state(GlobalState.PREPARADO)
    estado.set_flag("PARO_EMERGENCIA", False)          # S2: con paro se rechaza
    with patch("autoclave.services.domain.loop.control_loop.StateMachine"):
        assert loop.set_active_cycle(_prog(_ASIG_REF_PRINCIPAL))[0] is True
    assert ultimo in loop.programas_para_seguridad()


def test_ticket_lleva_el_aviso_de_uniformidad():
    from autoclave.services.domain.logging.ticket_formatter import format_footer
    texto = format_footer("COMPLETADO", "2026-10-14T10:00:00",
                          avisos=["Uniformidad termica fuera de rango: Referencia 115.0 C"])
    assert "Aviso: Uniformidad termica fuera de rango: Referencia 115.0 C" in texto


def test_cic09_anota_aviso_del_ciclo():
    fase, estado = _esterilizacion_con_referencia(115.0)
    estado.avisos_ciclo = []
    for _ in range(4):
        fase.update()
    # X9 (tanda 9, D9-13.4): el aviso va con clave + parámetros; el ticket lo arma
    from autoclave.services.domain.logging import ticket_formatter as tf
    assert estado.avisos_ciclo and estado.avisos_ciclo[0]["clave"] == "ticket_ciclo.aviso_uniformidad"
    assert "Referencia" in tf.aviso_ticket(estado.avisos_ciclo[0], tf.Presentacion("es", "C", "kPa"))

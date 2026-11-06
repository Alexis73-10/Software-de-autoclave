"""Hotfix ES (6-nov-2026, decisión de Cristian): retiro del protocolo
automático de estado seguro. Arranque con la cámara no segura (normal e
interrumpido) sin protocolo; COMPLETADO, FALLO y CANCELADO sin protocolo;
FALLA nivela la presión de cámara como PREPARACION; paro real → confirmar →
PREPARACION; NO ABRIR con su motivo, valor y límite."""

from unittest.mock import MagicMock, patch

import pytest

from tests.helpers.arranque_doble import evento_liberado
from autoclave.core.managers.cycle_manager import Cycle
from autoclave.core.runtime import camara_segura, motivos
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.state_machine.estado_seguro import ConfirmacionParo
from autoclave.state_machine.machine.enum_global import GlobalState
from autoclave.state_machine.state_machine import StateMachine

_VALORES = {"presion_admosferica": 101.3, "rango_presion_atm": 10.0, "temp_max_apertura": 80.0,
            "temp_segura_drenaje": 60.0, "rango_temp_drenaje": 5.0}


class _Config(dict):
    def get(self, k, d=None):
        return super().get(k, d)


def _programa(tipo="liquido", modo=1):
    return Cycle("p", "Prog", {"globals": {"tipo_carga": {"value": tipo},
                                           "presion_chaqueta": {"value": 200.0},
                                           "rango_presion_chaqueta": {"value": 20.0}},
                               "descompresion": {"modo": {"value": modo}}}, number=1)


# ── Arranque con la cámara no segura ───────────────────────────────────────

def _loop():
    from autoclave.services.domain.loop.control_loop import ControlLoop
    cm = MagicMock()
    cm.get_selected_cycle.return_value = None
    config = MagicMock()
    config.get.side_effect = lambda k, d=None: _VALORES.get(k, d)
    with patch("autoclave.services.domain.loop.control_loop.StateMachine"):
        loop = ControlLoop(arranque_liberado=evento_liberado(), units=MagicMock(),
                           door_service=MagicMock(), doors=[], estado=EstadoAutoclave(),
                           link=MagicMock(), set_do=MagicMock(), alarm_manager=MagicMock(),
                           cycle_manager=cm, config_manager=config)
    loop.cycle = None
    loop.link.edad_ultima_ai.return_value = 0.1
    loop.al_evento_seguridad = MagicMock()
    return loop


@pytest.mark.parametrize("programa", [_programa("liquido", 4), _programa("solido", 1)],
                         ids=["interrumpido_liquido", "ultimo_ciclo_solido"])
def test_arranque_con_camara_no_segura_no_inicia_protocolo(programa):
    loop = _loop()
    loop.estado.set_machine_state(GlobalState.PREPARACION)
    loop.estado.sensores_pres["pres_camara"] = 250.0
    loop.estado.sensores_temp["temp_camara"] = 115.0
    loop.recuperar_ciclo_interrumpido(programa)
    loop._procesar_recuperacion()
    # sin protocolo: nada activo, ninguna válvula ordenada desde aquí
    assert loop.estado_seguro.activo is False
    assert loop.estado_seguro.requiere_confirmacion is False
    assert loop.set_do.method_calls == []
    assert loop._recuperacion_pendiente is None
    # el Principal del ciclo sigue contando para NO ABRIR hasta la cámara segura
    assert programa in loop.programas_para_seguridad()
    segura, motivo = camara_segura.evaluar(loop.estado, loop.config_manager,
                                           loop.programas_para_seguridad())
    assert segura is False and motivo.codigo == "sobrepresion"
    # queda en la bitácora con el motivo
    evento, detalle = loop.al_evento_seguridad.call_args.args
    assert evento == "arranque_camara_no_segura" and "Sobrepresión" in detalle["motivo"]


def test_arranque_con_camara_segura_olvida_el_programa_tras_3_ticks():
    loop = _loop()
    loop.estado.set_machine_state(GlobalState.PREPARACION)
    loop.estado.sensores_pres["pres_camara"] = 101.3
    loop.estado.sensores_temp["temp_camara"] = 40.0
    prog = _programa()
    loop.recuperar_ciclo_interrumpido(prog)
    loop._procesar_recuperacion()
    assert loop._recuperacion_pendiente is None
    loop.al_evento_seguridad.assert_not_called()
    for _ in range(3):
        loop._seguir_programa_ultimo_ciclo(vigentes=True)
    assert prog not in loop.programas_para_seguridad()


def test_no_abrir_se_levanta_cuando_la_camara_se_nivela_tras_el_arranque():
    # Diagnóstico §1: sin protocolo no queda ninguna dependencia circular
    loop = _loop()
    loop.estado.set_machine_state(GlobalState.PREPARACION)
    loop.estado.sensores_pres["pres_camara"] = 250.0
    loop.estado.sensores_temp["temp_camara"] = 115.0
    prog = _programa()
    loop.recuperar_ciclo_interrumpido(prog)
    loop._procesar_recuperacion()
    loop.estado.sensores_pres["pres_camara"] = 101.3
    loop.estado.sensores_temp["temp_camara"] = 60.0
    for _ in range(3):
        loop._seguir_programa_ultimo_ciclo(vigentes=True)
    segura, _ = camara_segura.evaluar(loop.estado, loop.config_manager,
                                      loop.programas_para_seguridad(),
                                      temp_max_ciclo=loop.temp_max_tras_ciclo())
    assert segura is True


# ── Fin de ciclo sin protocolo ─────────────────────────────────────────────

def _sm_ciclo(resultado, pres=250.0, temp=115.0):
    estado = EstadoAutoclave()
    estado.sensores_pres["pres_camara"] = pres
    estado.sensores_temp["temp_camara"] = temp
    cycle = MagicMock()
    cycle.copia.return_value = cycle
    cycle.sensores = None
    sm = StateMachine(io=MagicMock(), estado=estado, set_do=MagicMock(), cycle=cycle,
                      config=_Config(_VALORES))
    estado.set_machine_state(GlobalState.CICLO)
    sm.prev_state = GlobalState.CICLO
    sm.ciclo.run = MagicMock(return_value=resultado)
    sm.ciclo._protocolo = MagicMock()
    return sm, estado


@pytest.mark.parametrize("resultado, siguiente, cierra", [
    ("COMPLETADO", GlobalState.PREPARADO, False),
    ("FALLO", GlobalState.FALLA, True),
    ("CANCELADO", GlobalState.PREPARADO, True),
])
def test_fin_de_ciclo_con_camara_no_segura_sin_protocolo(resultado, siguiente, cierra):
    sm, estado = _sm_ciclo(resultado)
    sm.update()
    assert estado.get_machine_state() == siguiente
    sm.ciclo._protocolo.ejecutar.assert_not_called()
    assert sm.estado_seguro.activo is False
    # al salir de CICLO tras FALLO/CANCELADO se cierran las válvulas del
    # protocolo de fallo; el estado siguiente maneja la cámara
    assert sm.ciclo._protocolo.finalizar.called is cierra


def test_error_al_cerrar_el_protocolo_no_impide_la_transicion():
    sm, estado = _sm_ciclo("FALLO")
    sm.ciclo._protocolo.finalizar.side_effect = RuntimeError("x")
    sm.update()
    assert estado.get_machine_state() == GlobalState.FALLA


# ── FALLA nivela la presión de cámara como PREPARACION ─────────────────────

def _sm_falla(pres, tipo="liquido"):
    estado = EstadoAutoclave()
    estado.sensores_pres["pres_camara"] = pres
    programa = _programa(tipo)
    set_do = MagicMock()
    sm = StateMachine(io=MagicMock(), estado=estado, set_do=set_do, cycle=programa,
                      config=_Config(_VALORES), programas_seguridad=lambda: [programa])
    estado.set_machine_state(GlobalState.FALLA)
    return sm, estado, set_do


def test_falla_ventea_la_sobrepresion_por_la_lenta_con_carga_liquida():
    sm, estado, set_do = _sm_falla(250.0, "liquido")
    sm.update()
    set_do.descompresion_lenta_on.assert_called()
    set_do.descompresion_rapida_on.assert_not_called()
    set_do.aire_admosferico_camara_on.assert_not_called()
    assert estado.get_machine_state() == GlobalState.FALLA


def test_falla_ventea_la_sobrepresion_por_la_rapida_con_carga_solida():
    sm, estado, set_do = _sm_falla(250.0, "solido")
    sm.update()
    set_do.descompresion_rapida_on.assert_called()
    set_do.descompresion_lenta_on.assert_not_called()


def test_falla_abre_el_aire_atmosferico_con_vacio():
    sm, estado, set_do = _sm_falla(40.0)
    sm.update()
    set_do.aire_admosferico_camara_on.assert_called()
    set_do.descompresion_rapida_on.assert_not_called()
    set_do.descompresion_lenta_on.assert_not_called()


def test_falla_nivelada_cierra_venteo_y_lenta_y_sin_dato_no_ordena():
    sm, estado, set_do = _sm_falla(250.0, "liquido")
    sm.update()
    estado.sensores_pres["pres_camara"] = 101.3
    set_do.reset_mock()
    sm.update()
    set_do.descompresion_lenta_off.assert_called()
    set_do.descompresion_rapida_off.assert_called()
    estado.sensores_pres["pres_camara"] = None
    set_do.reset_mock()
    sm.update()
    set_do.descompresion_rapida_on.assert_not_called()
    set_do.descompresion_lenta_on.assert_not_called()
    set_do.aire_admosferico_camara_on.assert_not_called()


def test_falla_con_paro_no_ventea():
    sm, estado, set_do = _sm_falla(250.0, "liquido")
    estado.set_flag("PARO_EMERGENCIA", True)
    estado.set_flag("PARO_REAL", True)
    sm.update()
    set_do.descompresion_lenta_on.assert_not_called()
    set_do.apagar_por_paro.assert_called()


def test_falla_sale_a_preparacion_con_el_reconocimiento_aunque_la_camara_no_sea_segura():
    sm, estado, set_do = _sm_falla(250.0)
    estado.set_flag("RESET_FALLA", True)
    sm.update()
    assert estado.get_machine_state() == GlobalState.PREPARACION


# ── Paro real → confirmar → PREPARACION ────────────────────────────────────

def _sm_estado(estado_maquina):
    estado = EstadoAutoclave()
    estado.sensores_pres["pres_camara"] = 101.3
    programa = _programa("solido")
    set_do = MagicMock()
    eventos = []
    sm = StateMachine(io=MagicMock(), estado=estado, set_do=set_do, cycle=programa,
                      config=_Config(_VALORES), programas_seguridad=lambda: [programa],
                      al_evento_seguridad=lambda e, d: eventos.append(e))
    estado.set_machine_state(estado_maquina)
    return sm, estado, set_do, eventos


def _pulsar_y_soltar(sm, estado):
    estado.set_flag("PARO_EMERGENCIA", True)
    estado.set_flag("PARO_REAL", True)
    sm.update()
    estado.set_flag("PARO_EMERGENCIA", False)
    estado.set_flag("PARO_REAL", False)


def test_paro_real_en_preparado_espera_confirmacion_y_pasa_a_preparacion():
    sm, estado, set_do, eventos = _sm_estado(GlobalState.PREPARADO)
    _pulsar_y_soltar(sm, estado)
    set_do.reset_mock()
    sm.update()
    sm.update()
    # soltado sin confirmar: salidas en 0, sin avanzar ni ventear
    assert sm.estado_seguro.requiere_confirmacion is True
    assert estado.get_machine_state() == GlobalState.PREPARADO
    set_do.apagar_por_paro.assert_called()
    set_do.descompresion_rapida_on.assert_not_called()
    set_do.vapor_chaqueta_on.assert_not_called()
    assert estado.get_flag("LISTO_PARA_CICLO") is False
    # confirmar no corre ningún protocolo: el equipo pasa a PREPARACION
    assert sm.confirmar_paro() is True
    assert estado.get_machine_state() == GlobalState.PREPARACION
    assert sm.estado_seguro.activo is False
    assert eventos == ["paro_activado", "paro_liberado", "estado_seguro_confirmado"]
    set_do.reset_mock()
    sm.update()
    set_do.apagar_por_paro.assert_not_called()      # PREPARACION corre normal


def test_confirmar_con_el_paro_activo_o_sin_paro_no_aplica():
    sm, estado, set_do, _ = _sm_estado(GlobalState.PREPARADO)
    assert sm.confirmar_paro() is False
    estado.set_flag("PARO_EMERGENCIA", True)
    estado.set_flag("PARO_REAL", True)
    sm.update()
    assert sm.confirmar_paro() is False
    assert estado.get_machine_state() == GlobalState.PREPARADO


def test_paro_sin_datos_no_exige_confirmacion():
    # U4: PARO_EMERGENCIA sin PARO_REAL es el módulo E/S sin datos
    sm, estado, set_do, _ = _sm_estado(GlobalState.PREPARACION)
    estado.set_flag("PARO_EMERGENCIA", True)
    sm.update()
    estado.set_flag("PARO_EMERGENCIA", False)
    sm.update()
    assert sm.estado_seguro.requiere_confirmacion is False


def test_paro_real_en_falla_el_reconocimiento_confirma_y_lleva_a_preparacion():
    sm, estado, set_do, _ = _sm_estado(GlobalState.FALLA)
    estado.sensores_pres["pres_camara"] = 250.0
    _pulsar_y_soltar(sm, estado)
    set_do.reset_mock()
    sm.update()
    set_do.descompresion_rapida_on.assert_not_called()   # sin ventear hasta confirmar
    # /fault/reset: RESET_FALLA y luego la confirmación
    estado.set_flag("RESET_FALLA", True)
    assert sm.confirmar_paro() is True
    assert estado.get_machine_state() == GlobalState.FALLA
    sm.update()
    assert estado.get_machine_state() == GlobalState.PREPARACION


def test_paro_real_en_falla_confirmado_sin_reconocer_vuelve_a_ventear():
    sm, estado, set_do, _ = _sm_estado(GlobalState.FALLA)
    estado.sensores_pres["pres_camara"] = 250.0
    _pulsar_y_soltar(sm, estado)
    sm.update()
    assert sm.confirmar_paro() is True
    set_do.reset_mock()
    sm.update()
    assert estado.get_machine_state() == GlobalState.FALLA
    set_do.descompresion_rapida_on.assert_called()       # carga sólida


def test_confirmacion_paro_solo_publica_la_forma_compatible():
    c = ConfirmacionParo(EstadoAutoclave())
    assert c.activo is False and c.programa is None and c.causa is None
    c.requiere_confirmacion = True
    assert c.causa == "paro_liberado"


# ── NO ABRIR con motivo, valor y límite ────────────────────────────────────

def _estado_camara(pres, temp):
    estado = EstadoAutoclave()
    estado.sensores_pres["pres_camara"] = pres
    estado.sensores_temp["temp_camara"] = temp
    return estado


def test_motivo_temperatura_con_valor_y_limite_del_ciclo():
    segura, motivo = camara_segura.evaluar(_estado_camara(101.3, 92.0), _Config(_VALORES), None,
                                           temp_max_ciclo=70.0)
    assert segura is False
    assert str(motivo) == "Temperatura 92 °C, máximo 70 °C"
    # en la interfaz, con el formato de las unidades vigentes
    assert motivos.texto(motivo, "es") == "Temperatura 92.0 °C, máximo 70.0 °C"
    assert "92" in motivos.texto(motivo, "en") and "70" in motivos.texto(motivo, "en")


def test_motivo_sobrepresion_y_vacio_con_valor_y_limite():
    _, sobre = camara_segura.evaluar(_estado_camara(150.0, 40.0), _Config(_VALORES), None)
    assert str(sobre) == "Sobrepresión en cámara: 150 kPa, máximo 111 kPa"
    assert motivos.texto(sobre, "es") == "Sobrepresión en cámara: 150.0 kPa, máximo 111.3 kPa"
    _, vacio = camara_segura.evaluar(_estado_camara(40.0, 40.0), _Config(_VALORES), None)
    assert str(vacio) == "Cámara en vacío: 40 kPa, mínimo 91 kPa"
    lista = camara_segura.motivos(_estado_camara(150.0, 95.0), _Config(_VALORES), None)
    assert [str(m) for m in lista] == ["Sobrepresión en cámara: 150 kPa, máximo 111 kPa",
                                      "Temperatura 95 °C, máximo 80 °C"]


def test_ningun_texto_dice_solo_que_el_ciclo_termino_en_estado_no_seguro():
    from autoclave import i18n
    for idioma in i18n.IDIOMAS:
        for causa in ("arranque", "fallo", "cancelado", "completado"):
            assert not i18n.existe(f"sistema.estado_seguro_causa_{causa}", idioma)

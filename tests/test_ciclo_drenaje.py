from unittest.mock import MagicMock
from autoclave.state_machine.states.ciclo import CicloState


def _make_ciclo(temp_drenaje=25.0, temp_segura=40.0):
    estado = MagicMock()
    estado.sensores_temp = {"temp_drenaje": temp_drenaje}
    estado.sensores_pres = {}
    estado.get_flag.return_value = False
    set_do = MagicMock()
    cycle = MagicMock()
    cycle.get_param.return_value = None
    config = MagicMock()
    config.get.return_value = temp_segura
    alarm_manager = MagicMock()
    ciclo = CicloState(estado, set_do, cycle, config, alarm_manager)
    return ciclo, set_do, alarm_manager, estado


def test_temp_alta_no_activa_agua_antes_de_3_lecturas():
    ciclo, set_do, alarm_manager, _ = _make_ciclo(temp_drenaje=45.0, temp_segura=40.0)
    ciclo._mantener_drenaje()
    ciclo._mantener_drenaje()
    set_do.agua_intercambiador_on.assert_not_called()
    alarm_manager.report.assert_not_called()


def test_temp_alta_activa_agua_al_llegar_a_3_lecturas():
    ciclo, set_do, alarm_manager, _ = _make_ciclo(temp_drenaje=45.0, temp_segura=40.0)
    ciclo._mantener_drenaje()
    ciclo._mantener_drenaje()
    ciclo._mantener_drenaje()
    set_do.agua_intercambiador_on.assert_called_once()
    alarma = alarm_manager.report.call_args.args[0]
    assert alarma.id == "TEMP_DRENAJE_ALTA"
    assert alarma.blocks_operation is False


def test_temp_segura_apaga_agua_al_llegar_a_3_lecturas():
    ciclo, set_do, alarm_manager, estado = _make_ciclo(temp_drenaje=45.0, temp_segura=40.0)
    ciclo._mantener_drenaje()
    ciclo._mantener_drenaje()
    ciclo._mantener_drenaje()
    set_do.agua_intercambiador_on.assert_called_once()

    estado.sensores_temp["temp_drenaje"] = 30.0
    ciclo._mantener_drenaje()
    ciclo._mantener_drenaje()
    set_do.agua_intercambiador_off.assert_not_called()
    ciclo._mantener_drenaje()
    set_do.agua_intercambiador_off.assert_called_once()
    alarm_manager.clear.assert_any_call("TEMP_DRENAJE_ALTA")


def test_oscilacion_resetea_contador_sin_falso_positivo():
    ciclo, set_do, alarm_manager, estado = _make_ciclo(temp_drenaje=45.0, temp_segura=40.0)
    ciclo._mantener_drenaje()  # alta (1)
    ciclo._mantener_drenaje()  # alta (2)
    estado.sensores_temp["temp_drenaje"] = 30.0
    ciclo._mantener_drenaje()  # baja (1) -- resetea contador de alta
    estado.sensores_temp["temp_drenaje"] = 45.0
    ciclo._mantener_drenaje()  # alta (1)
    ciclo._mantener_drenaje()  # alta (2)
    set_do.agua_intercambiador_on.assert_not_called()
    set_do.agua_intercambiador_off.assert_not_called()


def test_temp_drenaje_ausente_no_hace_nada():
    ciclo, set_do, alarm_manager, estado = _make_ciclo(temp_segura=40.0)
    estado.sensores_temp = {}
    ciclo._mantener_drenaje()
    set_do.agua_intercambiador_on.assert_not_called()
    set_do.agua_intercambiador_off.assert_not_called()
    alarm_manager.report.assert_not_called()
    alarm_manager.clear.assert_not_called()


def test_sensor_ausente_no_reinicia_contador_en_progreso():
    ciclo, set_do, alarm_manager, estado = _make_ciclo(temp_drenaje=45.0, temp_segura=40.0)
    ciclo._mantener_drenaje()  # alta (1)
    ciclo._mantener_drenaje()  # alta (2)
    estado.sensores_temp = {}
    ciclo._mantener_drenaje()  # sensor ausente, no toca contadores
    estado.sensores_temp = {"temp_drenaje": 45.0}
    ciclo._mantener_drenaje()  # alta (3) -- debe disparar, no reiniciarse a 1
    set_do.agua_intercambiador_on.assert_called_once()


def test_se_llama_en_run_sin_importar_la_fase_activa():
    ciclo, set_do, alarm_manager, estado = _make_ciclo(temp_drenaje=45.0, temp_segura=40.0)
    # temp_camara es sensor crítico (CicloState._SENSORES_TEMP_CRITICOS) y
    # debe estar presente o run() aborta el ciclo en el paso 4, antes de
    # llegar al paso 5 (_mantener_drenaje).
    estado.sensores_temp["temp_camara"] = 100.0
    estado.sensores_pres = {"pres_camara": 101.3, "pres_chaqueta": 300.0,
                             "pres_empaque_1": 300.0, "pres_empaque_2": 300.0}
    estado.sensores_di = {"puerta_1_cerrada": 1, "puerta_2_cerrada": 1,
                           "vapor_suministro": 1}
    # cap.has_vacuum=False para que PrevacioFase.update() (paso 7, corre
    # DESPUÉS de _mantener_drenaje) se salte sin tocar más sensores/salidas.
    ciclo.cap = MagicMock()
    ciclo.cap.has_vacuum = False
    for fase in ciclo._fases:
        fase.cap = ciclo.cap
    # PrevacioFase está en índice 2 del pipeline (PRECALENTAMIENTO, PURGA, PRE_VACIO, ...)
    ciclo.reset()
    ciclo._fase_idx = 2
    ciclo.run()
    ciclo.run()
    ciclo.run()
    set_do.agua_intercambiador_on.assert_called()

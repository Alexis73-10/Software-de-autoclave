from unittest.mock import MagicMock
from autoclave.state_machine.states.ciclo import CicloState, CicloResultado


def _make_ciclo(door_service=None, apertura_automatica=False,
                 tiempo_espera=60, temp_max=80.0, timeout_min=30,
                 temp_camara=25.0):
    estado = MagicMock()
    estado.sensores_temp = {"temp_camara": temp_camara}
    estado.sensores_pres = {"pres_camara": 101.3}
    estado.get_flag.return_value = False

    set_do = MagicMock()
    cycle = MagicMock()

    def _get_param(seccion, nombre, default=None):
        valores = {
            ("finalizacion", "apertura_automatica"): apertura_automatica,
            ("finalizacion", "tiempo_espera_apertura"): tiempo_espera,
            ("finalizacion", "temp_max_apertura"): temp_max,
            ("finalizacion", "timeout_temperatura"): timeout_min,
        }
        return valores.get((seccion, nombre), default)

    cycle.get_param.side_effect = _get_param
    config = MagicMock()
    config.get.return_value = None
    alarm_manager = MagicMock()

    ciclo = CicloState(estado, set_do, cycle, config, alarm_manager,
                        cap=None, door_service=door_service)
    ciclo.reset()
    ciclo._resultado_pendiente = CicloResultado.COMPLETADO
    return ciclo, estado, set_do, alarm_manager


def test_door_service_none_por_defecto():
    ciclo, *_ = _make_ciclo()
    assert ciclo.door_service is None


def test_door_service_se_guarda_si_se_pasa():
    door_service = MagicMock()
    ciclo, *_ = _make_ciclo(door_service=door_service)
    assert ciclo.door_service is door_service


def test_door_service_none_no_rompe_run(monkeypatch):
    ciclo, *_ = _make_ciclo(door_service=None, apertura_automatica=True)
    resultado = ciclo.run()
    assert resultado == CicloResultado.ESPERANDO_CONFIRMACION


def test_apertura_automatica_false_no_hace_nada():
    door_service = MagicMock()
    door_service.doors = {"Puerta 1": MagicMock(), "Puerta 2": MagicMock()}
    ciclo, estado, set_do, alarm_manager = _make_ciclo(
        door_service=door_service, apertura_automatica=False)

    ciclo._mantener_apertura_automatica()
    ciclo._mantener_apertura_automatica()

    door_service.request_open.assert_not_called()
    estado.set_flag.assert_not_called()


def test_espera_fija_antes_de_intentar_abrir(monkeypatch):
    import autoclave.state_machine.states.ciclo as ciclo_module
    door_service = MagicMock()
    door_service.doors = {"Puerta 1": MagicMock(), "Puerta 2": MagicMock()}
    door_service.request_open.return_value = (True, "")
    ciclo, estado, set_do, alarm_manager = _make_ciclo(
        door_service=door_service, apertura_automatica=True,
        tiempo_espera=60, temp_max=80.0, temp_camara=25.0)

    t0 = 1_000_000.0
    monkeypatch.setattr(ciclo_module.time, "time", lambda: t0)
    ciclo._mantener_apertura_automatica()
    door_service.request_open.assert_not_called()

    monkeypatch.setattr(ciclo_module.time, "time", lambda: t0 + 59)
    ciclo._mantener_apertura_automatica()
    door_service.request_open.assert_not_called()

    monkeypatch.setattr(ciclo_module.time, "time", lambda: t0 + 60)
    ciclo._mantener_apertura_automatica()
    door_service.request_open.assert_called_once_with("Puerta 2")


def test_abre_puerta_2_si_existe(monkeypatch):
    import autoclave.state_machine.states.ciclo as ciclo_module
    door_service = MagicMock()
    door_service.doors = {"Puerta 1": MagicMock(), "Puerta 2": MagicMock()}
    door_service.request_open.return_value = (True, "")
    ciclo, estado, set_do, alarm_manager = _make_ciclo(
        door_service=door_service, apertura_automatica=True,
        tiempo_espera=0, temp_max=80.0, temp_camara=25.0)

    monkeypatch.setattr(ciclo_module.time, "time", lambda: 2_000_000.0)
    ciclo._mantener_apertura_automatica()

    door_service.request_open.assert_called_once_with("Puerta 2")


def test_abre_puerta_1_si_es_equipo_de_una_puerta(monkeypatch):
    import autoclave.state_machine.states.ciclo as ciclo_module
    door_service = MagicMock()
    door_service.doors = {"Puerta 1": MagicMock()}
    door_service.request_open.return_value = (True, "")
    ciclo, estado, set_do, alarm_manager = _make_ciclo(
        door_service=door_service, apertura_automatica=True,
        tiempo_espera=0, temp_max=80.0, temp_camara=25.0)

    monkeypatch.setattr(ciclo_module.time, "time", lambda: 2_000_000.0)
    ciclo._mantener_apertura_automatica()

    door_service.request_open.assert_called_once_with("Puerta 1")


def test_espera_temperatura_antes_de_abrir(monkeypatch):
    import autoclave.state_machine.states.ciclo as ciclo_module
    door_service = MagicMock()
    door_service.doors = {"Puerta 1": MagicMock(), "Puerta 2": MagicMock()}
    door_service.request_open.return_value = (True, "")
    ciclo, estado, set_do, alarm_manager = _make_ciclo(
        door_service=door_service, apertura_automatica=True,
        tiempo_espera=0, temp_max=80.0, temp_camara=95.0)

    monkeypatch.setattr(ciclo_module.time, "time", lambda: 3_000_000.0)
    ciclo._mantener_apertura_automatica()
    door_service.request_open.assert_not_called()

    estado.sensores_temp["temp_camara"] = 75.0
    ciclo._mantener_apertura_automatica()
    door_service.request_open.assert_called_once_with("Puerta 2")


def test_confirma_solo_al_abrir_con_exito(monkeypatch):
    import autoclave.state_machine.states.ciclo as ciclo_module
    door_service = MagicMock()
    door_service.doors = {"Puerta 2": MagicMock()}
    door_service.request_open.return_value = (True, "")
    door_service.get_status.return_value = "CERRADO"
    ciclo, estado, set_do, alarm_manager = _make_ciclo(
        door_service=door_service, apertura_automatica=True,
        tiempo_espera=0, temp_max=80.0, temp_camara=25.0)

    monkeypatch.setattr(ciclo_module.time, "time", lambda: 4_000_000.0)
    ciclo._mantener_apertura_automatica()
    estado.set_flag.assert_not_called()

    door_service.get_status.return_value = "ABRIENDO"
    monkeypatch.setattr(ciclo_module.time, "time", lambda: 4_000_010.0)
    ciclo._mantener_apertura_automatica()
    estado.set_flag.assert_called_once_with("CICLO_CONFIRMADO", True)


def test_no_confirma_si_abrir_falla(monkeypatch):
    import autoclave.state_machine.states.ciclo as ciclo_module
    door_service = MagicMock()
    door_service.doors = {"Puerta 2": MagicMock()}
    door_service.get_status.return_value = "CERRADO"
    door_service.request_open.return_value = (False, "Puerta 1 no esta cerrada")
    ciclo, estado, set_do, alarm_manager = _make_ciclo(
        door_service=door_service, apertura_automatica=True,
        tiempo_espera=0, temp_max=80.0, temp_camara=25.0)

    monkeypatch.setattr(ciclo_module.time, "time", lambda: 5_000_000.0)
    ciclo._mantener_apertura_automatica()
    estado.set_flag.assert_not_called()
    door_service.request_open.assert_called_once_with("Puerta 2")

    # reintenta en un tick posterior (pasado el intervalo de reintento de 5s)
    door_service.request_open.return_value = (True, "")
    monkeypatch.setattr(ciclo_module.time, "time", lambda: 5_000_010.0)
    ciclo._mantener_apertura_automatica()
    assert door_service.request_open.call_count == 2
    estado.set_flag.assert_not_called()  # dispatch exitoso, pero aun no se observa ABRIENDO

    # el siguiente tick observa que la puerta empezo a abrir -> confirma
    door_service.get_status.return_value = "ABRIENDO"
    monkeypatch.setattr(ciclo_module.time, "time", lambda: 5_000_020.0)
    ciclo._mantener_apertura_automatica()
    estado.set_flag.assert_called_once_with("CICLO_CONFIRMADO", True)


def test_alarma_timeout_temperatura_una_sola_vez(monkeypatch):
    import autoclave.state_machine.states.ciclo as ciclo_module
    door_service = MagicMock()
    door_service.doors = {"Puerta 2": MagicMock()}
    ciclo, estado, set_do, alarm_manager = _make_ciclo(
        door_service=door_service, apertura_automatica=True,
        tiempo_espera=60, temp_max=80.0, timeout_min=30, temp_camara=95.0)

    t0 = 6_000_000.0
    monkeypatch.setattr(ciclo_module.time, "time", lambda: t0)
    ciclo._mantener_apertura_automatica()  # fija _apertura_auto_t_inicio = t0

    # tiempo_espera (60s) + timeout_temperatura (30min = 1800s) + margen
    monkeypatch.setattr(ciclo_module.time, "time", lambda: t0 + 60 + 1801)
    ciclo._mantener_apertura_automatica()
    alarm_manager.report.assert_called_once()
    alarma = alarm_manager.report.call_args.args[0]
    assert alarma.id == "TIMEOUT_APERTURA_AUTOMATICA"
    assert alarma.blocks_operation is False

    # sigue en temperatura alta: no debe repetir la alarma
    monkeypatch.setattr(ciclo_module.time, "time", lambda: t0 + 60 + 2000)
    ciclo._mantener_apertura_automatica()
    alarm_manager.report.assert_called_once()


def test_sigue_esperando_tras_alarma_timeout_hasta_que_baja_temp(monkeypatch):
    import autoclave.state_machine.states.ciclo as ciclo_module
    door_service = MagicMock()
    door_service.doors = {"Puerta 2": MagicMock()}
    door_service.get_status.return_value = "CERRADO"
    door_service.request_open.return_value = (True, "")
    ciclo, estado, set_do, alarm_manager = _make_ciclo(
        door_service=door_service, apertura_automatica=True,
        tiempo_espera=60, temp_max=80.0, timeout_min=30, temp_camara=95.0)

    t0 = 7_000_000.0
    monkeypatch.setattr(ciclo_module.time, "time", lambda: t0)
    ciclo._mantener_apertura_automatica()

    monkeypatch.setattr(ciclo_module.time, "time", lambda: t0 + 60 + 1801)
    ciclo._mantener_apertura_automatica()
    alarm_manager.report.assert_called_once()

    estado.sensores_temp["temp_camara"] = 75.0
    monkeypatch.setattr(ciclo_module.time, "time", lambda: t0 + 60 + 1802)
    ciclo._mantener_apertura_automatica()
    door_service.request_open.assert_called_once_with("Puerta 2")
    estado.set_flag.assert_not_called()

    door_service.get_status.return_value = "ABRIENDO"
    monkeypatch.setattr(ciclo_module.time, "time", lambda: t0 + 60 + 1810)
    ciclo._mantener_apertura_automatica()
    estado.set_flag.assert_called_once_with("CICLO_CONFIRMADO", True)
    alarm_manager.clear.assert_called_once_with("TIMEOUT_APERTURA_AUTOMATICA")


def test_sensor_ausente_no_avanza_ni_rompe(monkeypatch):
    import autoclave.state_machine.states.ciclo as ciclo_module
    door_service = MagicMock()
    door_service.doors = {"Puerta 2": MagicMock()}
    ciclo, estado, set_do, alarm_manager = _make_ciclo(
        door_service=door_service, apertura_automatica=True,
        tiempo_espera=0, temp_max=80.0)
    estado.sensores_temp = {}

    monkeypatch.setattr(ciclo_module.time, "time", lambda: 8_000_000.0)
    ciclo._mantener_apertura_automatica()

    door_service.request_open.assert_not_called()
    estado.set_flag.assert_not_called()


def test_run_llama_apertura_automatica_en_completado(monkeypatch):
    import autoclave.state_machine.states.ciclo as ciclo_module
    door_service = MagicMock()
    door_service.doors = {"Puerta 2": MagicMock()}
    door_service.request_open.return_value = (True, "")
    ciclo, estado, set_do, alarm_manager = _make_ciclo(
        door_service=door_service, apertura_automatica=True,
        tiempo_espera=0, temp_max=80.0, temp_camara=25.0)

    monkeypatch.setattr(ciclo_module.time, "time", lambda: 9_000_000.0)
    resultado = ciclo.run()

    assert resultado == CicloResultado.ESPERANDO_CONFIRMACION
    door_service.request_open.assert_called_once_with("Puerta 2")


def test_run_no_llama_apertura_automatica_en_fallo():
    door_service = MagicMock()
    door_service.doors = {"Puerta 2": MagicMock()}
    ciclo, estado, set_do, alarm_manager = _make_ciclo(
        door_service=door_service, apertura_automatica=True,
        tiempo_espera=0, temp_max=80.0, temp_camara=25.0)
    ciclo._resultado_pendiente = CicloResultado.FALLO
    ciclo._protocolo = MagicMock()

    ciclo.run()

    door_service.request_open.assert_not_called()


def test_run_no_llama_apertura_automatica_en_cancelado():
    door_service = MagicMock()
    door_service.doors = {"Puerta 2": MagicMock()}
    ciclo, estado, set_do, alarm_manager = _make_ciclo(
        door_service=door_service, apertura_automatica=True,
        tiempo_espera=0, temp_max=80.0, temp_camara=25.0)
    ciclo._resultado_pendiente = CicloResultado.CANCELADO
    ciclo._protocolo = MagicMock()

    ciclo.run()

    door_service.request_open.assert_not_called()


def test_reset_reinicia_temporizador_de_apertura_automatica(monkeypatch):
    import autoclave.state_machine.states.ciclo as ciclo_module
    door_service = MagicMock()
    door_service.doors = {"Puerta 2": MagicMock()}
    ciclo, estado, set_do, alarm_manager = _make_ciclo(
        door_service=door_service, apertura_automatica=True,
        tiempo_espera=60, temp_max=80.0, temp_camara=95.0)

    monkeypatch.setattr(ciclo_module.time, "time", lambda: 10_000_000.0)
    ciclo._mantener_apertura_automatica()
    assert ciclo._apertura_auto_t_inicio is not None

    ciclo.reset()

    assert ciclo._apertura_auto_t_inicio is None
    assert ciclo._apertura_auto_alarmado is False
    assert ciclo._apertura_auto_ultimo_intento is None
    assert ciclo._apertura_auto_denegada_desde is None
    assert ciclo._apertura_auto_alarmado_denegacion is False


def test_pres_camara_ausente_no_abre_aunque_temp_este_bien(monkeypatch):
    import autoclave.state_machine.states.ciclo as ciclo_module
    door_service = MagicMock()
    door_service.doors = {"Puerta 2": MagicMock()}
    ciclo, estado, set_do, alarm_manager = _make_ciclo(
        door_service=door_service, apertura_automatica=True,
        tiempo_espera=0, temp_max=80.0, temp_camara=25.0)
    estado.sensores_pres = {}

    monkeypatch.setattr(ciclo_module.time, "time", lambda: 11_000_000.0)
    ciclo._mantener_apertura_automatica()

    door_service.request_open.assert_not_called()
    estado.set_flag.assert_not_called()


def test_pres_camara_fuera_de_rango_atmosferico_no_abre(monkeypatch):
    import autoclave.state_machine.states.ciclo as ciclo_module
    door_service = MagicMock()
    door_service.doors = {"Puerta 2": MagicMock()}
    ciclo, estado, set_do, alarm_manager = _make_ciclo(
        door_service=door_service, apertura_automatica=True,
        tiempo_espera=0, temp_max=80.0, temp_camara=25.0)
    estado.sensores_pres["pres_camara"] = 50.0  # fuera de 101.3 +/- 20 (defaults del mock)

    monkeypatch.setattr(ciclo_module.time, "time", lambda: 11_000_100.0)
    ciclo._mantener_apertura_automatica()

    door_service.request_open.assert_not_called()
    estado.set_flag.assert_not_called()


def test_alarma_apertura_denegada_tras_denegacion_sostenida(monkeypatch):
    import autoclave.state_machine.states.ciclo as ciclo_module
    door_service = MagicMock()
    door_service.doors = {"Puerta 2": MagicMock()}
    door_service.get_status.return_value = "CERRADO"
    door_service.request_open.return_value = (False, "Puerta 1 no esta cerrada")
    ciclo, estado, set_do, alarm_manager = _make_ciclo(
        door_service=door_service, apertura_automatica=True,
        tiempo_espera=0, temp_max=80.0, temp_camara=25.0)

    t0 = 12_000_000.0
    monkeypatch.setattr(ciclo_module.time, "time", lambda: t0)
    ciclo._mantener_apertura_automatica()
    alarm_manager.report.assert_not_called()

    monkeypatch.setattr(ciclo_module.time, "time", lambda: t0 + 61)
    ciclo._mantener_apertura_automatica()
    alarm_manager.report.assert_called_once()
    alarma = alarm_manager.report.call_args.args[0]
    assert alarma.id == "APERTURA_AUTOMATICA_DENEGADA"
    assert "Puerta 1 no esta cerrada" in alarma.description

    # no debe repetir la alarma en un intento posterior aun denegado
    monkeypatch.setattr(ciclo_module.time, "time", lambda: t0 + 70)
    ciclo._mantener_apertura_automatica()
    alarm_manager.report.assert_called_once()

    # se limpia cuando finalmente abre
    door_service.request_open.return_value = (True, "")
    monkeypatch.setattr(ciclo_module.time, "time", lambda: t0 + 80)
    ciclo._mantener_apertura_automatica()
    door_service.get_status.return_value = "ABRIENDO"
    monkeypatch.setattr(ciclo_module.time, "time", lambda: t0 + 90)
    ciclo._mantener_apertura_automatica()
    alarm_manager.clear.assert_any_call("APERTURA_AUTOMATICA_DENEGADA")


def test_reintento_respeta_intervalo(monkeypatch):
    import autoclave.state_machine.states.ciclo as ciclo_module
    door_service = MagicMock()
    door_service.doors = {"Puerta 2": MagicMock()}
    door_service.get_status.return_value = "CERRADO"
    door_service.request_open.return_value = (False, "motivo")
    ciclo, estado, set_do, alarm_manager = _make_ciclo(
        door_service=door_service, apertura_automatica=True,
        tiempo_espera=0, temp_max=80.0, temp_camara=25.0)

    t0 = 13_000_000.0
    monkeypatch.setattr(ciclo_module.time, "time", lambda: t0)
    ciclo._mantener_apertura_automatica()
    door_service.request_open.assert_called_once()

    # 1 segundo despues (menos que el intervalo de 5s) -> no reintenta todavia
    monkeypatch.setattr(ciclo_module.time, "time", lambda: t0 + 1)
    ciclo._mantener_apertura_automatica()
    door_service.request_open.assert_called_once()

    # pasado el intervalo -> reintenta
    monkeypatch.setattr(ciclo_module.time, "time", lambda: t0 + 5)
    ciclo._mantener_apertura_automatica()
    assert door_service.request_open.call_count == 2


def test_temp_max_apertura_no_supera_el_global(monkeypatch):
    import autoclave.state_machine.states.ciclo as ciclo_module
    door_service = MagicMock()
    door_service.doors = {"Puerta 2": MagicMock()}
    ciclo, estado, set_do, alarm_manager = _make_ciclo(
        door_service=door_service, apertura_automatica=True,
        tiempo_espera=0, temp_max=130.0, temp_camara=125.0)
    ciclo.config.get.side_effect = lambda nombre: 120.0 if nombre == "temp_max_apertura" else None

    monkeypatch.setattr(ciclo_module.time, "time", lambda: 14_000_000.0)
    ciclo._mantener_apertura_automatica()

    # temp_camara=125 > min(130 del ciclo, 120 global)=120 -> sigue esperando
    door_service.request_open.assert_not_called()

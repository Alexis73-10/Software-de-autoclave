import time as time_module
from unittest.mock import MagicMock
from autoclave.state_machine.cycle_phases.protocolo_fallo import ProtocoloFallo
import autoclave.state_machine.cycle_phases.protocolo_fallo as protocolo_fallo_module


def _make_protocolo(modo, pres_camara=300.0, presion_cambio=150):
    estado = MagicMock()
    estado.sensores_pres = {"pres_camara": pres_camara}
    estado.sensores_temp = {"temp_camara": 25.0}
    config = MagicMock()
    config.get.return_value = None
    set_do = MagicMock()
    cycle = MagicMock()

    def get_param(*args, default=None):
        if args == ("descompresion", "modo"):
            return modo
        if args == ("descompresion", "modo_3", "presion_cambio"):
            return presion_cambio
        if len(args) == 3 and args[0] == "descompresion" and args[2] == "timeout":
            return 30
        return default

    cycle.get_param.side_effect = get_param
    return ProtocoloFallo(estado, set_do, cycle, config), set_do, cycle


def test_normal_vacio_sin_cambios():
    protocolo, set_do, cycle = _make_protocolo(modo=1, pres_camara=101.3)

    protocolo.ejecutar()

    set_do.aire_admosferico_camara_on.assert_called_once()
    set_do.descompresion_rapida_on.assert_not_called()
    set_do.descompresion_lenta_on.assert_not_called()
    cycle.get_param.assert_not_called()


def test_modo_0_se_fuerza_a_lenta():
    protocolo, set_do, _ = _make_protocolo(modo=0)

    protocolo.ejecutar()

    set_do.descompresion_lenta_on.assert_called_once()
    set_do.descompresion_rapida_on.assert_not_called()


def test_modo_0_usa_timeout_de_modo_2():
    protocolo, set_do, cycle = _make_protocolo(modo=0)

    protocolo.ejecutar()

    cycle.get_param.assert_any_call("descompresion", "modo_2", "timeout", default=60)


def test_modo_1_activa_rapida():
    protocolo, set_do, _ = _make_protocolo(modo=1)

    protocolo.ejecutar()

    set_do.descompresion_rapida_on.assert_called_once()
    set_do.descompresion_lenta_on.assert_not_called()


def test_modo_2_activa_lenta():
    protocolo, set_do, _ = _make_protocolo(modo=2)

    protocolo.ejecutar()

    set_do.descompresion_lenta_on.assert_called_once()
    set_do.descompresion_rapida_on.assert_not_called()


def test_modo_3_lenta_hasta_presion_cambio():
    protocolo, set_do, _ = _make_protocolo(modo=3, pres_camara=300.0, presion_cambio=150)

    protocolo.ejecutar()

    set_do.descompresion_lenta_on.assert_called_once()
    set_do.descompresion_rapida_on.assert_not_called()
    assert protocolo._sub_etapa == "lenta"


def test_modo_3_transicion_a_rapida():
    protocolo, set_do, _ = _make_protocolo(modo=3, pres_camara=140.0, presion_cambio=150)

    protocolo.ejecutar()

    set_do.descompresion_lenta_on.assert_called_once()
    set_do.descompresion_lenta_off.assert_called_once()
    assert protocolo._sub_etapa == "rapida"


def test_modo_4_va_directo_a_final_sin_enfriamiento():
    protocolo, set_do, _ = _make_protocolo(modo=4)

    protocolo.ejecutar()

    set_do.descompresion_chaqueta_on.assert_called_once()
    set_do.descompresion_rapida_on.assert_called_once()
    set_do.agua_chaqueta_on.assert_not_called()
    set_do.aire_comprimido_camara_on.assert_not_called()


def test_modo_5_va_directo_a_final_sin_enfriamiento():
    protocolo, set_do, _ = _make_protocolo(modo=5)

    protocolo.ejecutar()

    set_do.descompresion_chaqueta_on.assert_called_once()
    set_do.descompresion_rapida_on.assert_called_once()
    set_do.agua_chaqueta_on.assert_not_called()
    set_do.aire_comprimido_camara_on.assert_not_called()


def test_modo_3_continua_transicion_en_update():
    # DescompresionFase (y esta réplica) apagan "lenta" y cambian de
    # sub-etapa en el tick en que se cruza presion_cambio, pero recién
    # activan "rapida" en el tick siguiente.
    protocolo, set_do, _ = _make_protocolo(modo=3, pres_camara=300.0, presion_cambio=150)
    protocolo.ejecutar()
    set_do.reset_mock()

    protocolo.estado.sensores_pres["pres_camara"] = 140.0
    protocolo.update()

    set_do.descompresion_lenta_off.assert_called_once()
    assert protocolo._sub_etapa == "rapida"

    set_do.reset_mock()
    protocolo.update()

    set_do.descompresion_rapida_on.assert_called_once()
    set_do.descompresion_lenta_on.assert_not_called()


def test_transicion_a_presion_normal_apaga_valvulas_y_activa_atm():
    protocolo, set_do, _ = _make_protocolo(modo=1, pres_camara=300.0)
    protocolo.ejecutar()
    set_do.reset_mock()

    protocolo.estado.sensores_pres["pres_camara"] = 101.3
    protocolo.update()

    set_do.descompresion_rapida_off.assert_called_once()
    set_do.descompresion_lenta_off.assert_called_once()
    set_do.descompresion_chaqueta_off.assert_called_once()
    set_do.aire_admosferico_camara_on.assert_called_once()


def test_normal_vacio_al_disparo_update_sin_cambios():
    protocolo, set_do, _ = _make_protocolo(modo=1, pres_camara=101.3)
    protocolo.ejecutar()
    set_do.reset_mock()

    protocolo.update()

    set_do.descompresion_lenta_on.assert_not_called()
    set_do.descompresion_rapida_on.assert_not_called()
    set_do.aire_admosferico_camara_on.assert_called_once()


def test_buzzer_sin_cambios_tras_descompresion_por_modo():
    protocolo, set_do, _ = _make_protocolo(modo=1, pres_camara=300.0)
    protocolo.ejecutar()

    protocolo.estado.sensores_pres["pres_camara"] = 101.3
    protocolo.estado.sensores_temp["temp_camara"] = 25.0
    protocolo.update()

    set_do.buzer_fallo.assert_called_once()

    set_do.reset_mock()
    protocolo.update()
    set_do.buzer_fallo.assert_not_called()


def test_timeout_agotado_escala_a_rapida(monkeypatch):
    protocolo, set_do, _ = _make_protocolo(modo=2, pres_camara=300.0)

    t0 = 1_000_000.0
    monkeypatch.setattr(protocolo_fallo_module.time, "time", lambda: t0)
    protocolo.ejecutar()
    set_do.reset_mock()

    monkeypatch.setattr(protocolo_fallo_module.time, "time", lambda: t0 + 31 * 60)
    protocolo.update()

    assert protocolo._escalado is True
    set_do.descompresion_chaqueta_on.assert_called_once()
    set_do.descompresion_rapida_on.assert_called_once()


def test_timeout_no_agotado_no_escala():
    protocolo, set_do, _ = _make_protocolo(modo=2, pres_camara=300.0)
    protocolo.ejecutar()
    set_do.reset_mock()

    protocolo.update()

    assert protocolo._escalado is False
    set_do.descompresion_chaqueta_on.assert_not_called()

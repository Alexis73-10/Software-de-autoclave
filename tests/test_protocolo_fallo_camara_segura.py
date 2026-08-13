from unittest.mock import MagicMock

from autoclave.state_machine.cycle_phases.protocolo_fallo import ProtocoloFallo


def _make_protocolo(pres=101.3, temp=30.0, pres_atm=101.3, rango=3.0, temp_max=40.0):
    estado = MagicMock()
    estado.camara_segura_confirmada = False
    estado.sensores_pres = {"pres_camara": pres}
    estado.sensores_temp = {"temp_camara": temp}

    set_do = MagicMock()
    cycle = MagicMock()
    cycle.get_param.side_effect = lambda seccion, nombre, default=None: {
        ("protocolo_fallo", "temp_max_apertura"): temp_max,
    }.get((seccion, nombre), default)

    # config.get() se usa en protocolo_fallo.py como `self.config.get(clave) or
    # default_hardcodeado` (un solo argumento, sin default explícito). Un
    # MagicMock() sin configurar devuelve otro MagicMock (valor verdadero,
    # no None), lo que rompe las comparaciones numéricas en update()
    # (`pres > atm + rango` -> TypeError). Se configura side_effect para que
    # devuelva los valores reales de este escenario de prueba.
    config = MagicMock()
    config.get.side_effect = lambda clave, default=None: {
        "presion_admosferica": pres_atm,
        "rango_presion_atm": rango,
        "temp_max_apertura": temp_max,
    }.get(clave, default)

    return ProtocoloFallo(estado=estado, set_do=set_do, cycle=cycle, config=config), estado


def test_estado_inicia_sin_confirmar():
    _, estado = _make_protocolo()
    assert estado.camara_segura_confirmada is False


def test_reset_vuelve_a_dejar_el_flag_en_false():
    protocolo, estado = _make_protocolo()
    estado.camara_segura_confirmada = True
    protocolo.reset()
    assert estado.camara_segura_confirmada is False


def test_publica_camara_segura_confirmada_al_emitir_buzzer():
    protocolo, estado = _make_protocolo(pres=101.3, temp=30.0)
    protocolo.ejecutar()
    protocolo.update()  # ProtocoloFallo.update(self) no toma argumentos
    assert estado.camara_segura_confirmada is True

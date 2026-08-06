from autoclave.state_machine.states.control_banda import evaluar_banda, ConfirmadorApagado


def test_evaluar_banda_activar_si_bajo_activa_bajo_objetivo():
    r = evaluar_banda(actual=95, objetivo=100, rango=10, activar_si_bajo=True)
    assert r.debe_activar is True


def test_evaluar_banda_activar_si_bajo_no_activa_en_objetivo():
    r = evaluar_banda(actual=100, objetivo=100, rango=10, activar_si_bajo=True)
    assert r.debe_activar is False


def test_evaluar_banda_activar_si_bajo_no_activa_sobre_objetivo():
    r = evaluar_banda(actual=105, objetivo=100, rango=10, activar_si_bajo=True)
    assert r.debe_activar is False


def test_evaluar_banda_activar_si_bajo_fuera_por_debajo_estricto():
    r = evaluar_banda(actual=89, objetivo=100, rango=10, activar_si_bajo=True)
    assert r.fuera_por_debajo is True
    assert r.dentro_de_banda is False


def test_evaluar_banda_activar_si_bajo_borde_inferior_no_es_fuera():
    r = evaluar_banda(actual=90, objetivo=100, rango=10, activar_si_bajo=True)
    assert r.fuera_por_debajo is False
    assert r.dentro_de_banda is True


def test_evaluar_banda_activar_si_bajo_fuera_por_encima_estricto():
    r = evaluar_banda(actual=111, objetivo=100, rango=10, activar_si_bajo=True)
    assert r.fuera_por_encima is True
    assert r.dentro_de_banda is False


def test_evaluar_banda_activar_si_bajo_borde_superior_no_es_fuera():
    r = evaluar_banda(actual=110, objetivo=100, rango=10, activar_si_bajo=True)
    assert r.fuera_por_encima is False
    assert r.dentro_de_banda is True


def test_evaluar_banda_activar_si_alto_activa_sobre_objetivo():
    r = evaluar_banda(actual=75, objetivo=70, rango=5, activar_si_bajo=False)
    assert r.debe_activar is True


def test_evaluar_banda_activar_si_alto_no_activa_en_objetivo():
    r = evaluar_banda(actual=70, objetivo=70, rango=5, activar_si_bajo=False)
    assert r.debe_activar is False


def test_evaluar_banda_activar_si_alto_no_activa_bajo_objetivo():
    r = evaluar_banda(actual=65, objetivo=70, rango=5, activar_si_bajo=False)
    assert r.debe_activar is False


def test_evaluar_banda_activar_si_alto_fuera_por_encima_estricto():
    r = evaluar_banda(actual=76, objetivo=70, rango=5, activar_si_bajo=False)
    assert r.fuera_por_encima is True
    assert r.dentro_de_banda is False


def test_evaluar_banda_activar_si_alto_fuera_por_debajo_estricto():
    r = evaluar_banda(actual=64, objetivo=70, rango=5, activar_si_bajo=False)
    assert r.fuera_por_debajo is True
    assert r.dentro_de_banda is False


def test_confirmador_no_confirma_en_tick_1_ni_2():
    c = ConfirmadorApagado()
    assert c.confirmar(True) is False
    assert c.confirmar(True) is False


def test_confirmador_confirma_en_tick_3():
    c = ConfirmadorApagado()
    c.confirmar(True)
    c.confirmar(True)
    assert c.confirmar(True) is True


def test_confirmador_se_resetea_si_condicion_cambia():
    c = ConfirmadorApagado()
    c.confirmar(True)
    c.confirmar(False)
    c.confirmar(True)
    assert c.confirmar(True) is False  # solo 2 consecutivos desde el reset


def test_confirmador_reset_explicito():
    c = ConfirmadorApagado()
    c.confirmar(True)
    c.confirmar(True)
    c.reset()
    assert c.confirmar(True) is False
    assert c.confirmar(True) is False


def test_confirmador_respeta_ticks_requeridos_custom():
    c = ConfirmadorApagado(ticks_requeridos=1)
    assert c.confirmar(True) is True

# Tanda 20, F1: el doble en memoria de EnlaceES que reemplaza a los dobles del
# enlace serial cumple la interfaz y se comporta como ModbusLink en lo que
# observan el ControlLoop y el backend.

import pytest

from autoclave.protocols.enlace import MIEMBROS_ENLACE, EnlaceES
from tests.helpers.enlace_doble import MAC_DOBLE, EnlaceDoble


@pytest.mark.req("T20-03")
def test_doble_cumple_la_interfaz(enlace_doble):
    assert isinstance(enlace_doble, EnlaceES)
    for miembro in MIEMBROS_ENLACE:
        assert hasattr(enlace_doble, miembro), miembro


@pytest.mark.req("T20-03")
def test_get_state_tiene_las_claves_del_enlace(enlace_doble):
    st = enlace_doble.get_state()
    assert set(st) == {"ai", "ai_seq", "di", "do", "port_open", "data_alive", "last_update"}
    assert len(st["ai"]) == 16 and len(st["di"]) == 56 and len(st["do"]) == 32


@pytest.mark.req("T20-03")
def test_publicar_actualiza_secuencias_edades_y_llama_on_update(enlace_doble):
    recibidos = []
    enlace_doble.on_update = recibidos.append
    assert enlace_doble.edad_ultima_ai() is None and enlace_doble.secuencia_ultima_di() is None
    enlace_doble.publicar(ai=[250] * 6, di=[1, 0, 1], now=100.0)
    assert enlace_doble.secuencia_ultima_ai() == 1
    assert enlace_doble.estado_ultima_ai() == (100.0, 1)
    assert enlace_doble.edad_ultima_di(now=101.5) == pytest.approx(1.5)
    assert recibidos[-1]["ai"][:6] == [250] * 6 and recibidos[-1]["ai"][6] is None
    assert recibidos[-1]["di"][:3] == [1, 0, 1]


@pytest.mark.req("T20-03")
def test_salidas_rechazadas_sin_conexion_y_fuera_de_rango():
    e = EnlaceDoble(conectado=False)
    assert e.set_output(1, True) is False
    assert e.all_off() is False
    e.reconectar()
    assert e.set_output(0, True) is False and e.set_output(33, True) is False
    assert e.set_output(25, True) is True and e.get_state()["do"][24] == 1
    assert e.all_off() is True and not any(e.get_state()["do"])


@pytest.mark.req("T20-03")
def test_bobina_atascada_impide_all_off(enlace_doble):
    enlace_doble.atascar(3, True)
    assert enlace_doble.all_off() is False


@pytest.mark.req("T20-03")
def test_start_emite_conectada_y_llama_al_conectar_con_la_mac(enlace_doble):
    vistas = []
    enlace_doble.al_conectar = vistas.append
    enlace_doble.start()
    eventos = enlace_doble.tomar_eventos()
    assert [(ev.origen, ev.alarm_id) for ev in eventos] == [("conectada", None)]
    assert vistas[0]["id"] == MAC_DOBLE and vistas[0]["protocolo"] == "modbus-tcp"
    assert enlace_doble.tomar_eventos() == []


@pytest.mark.req("T20-03")
def test_desconectar_baja_port_open_y_data_alive(enlace_doble):
    recibidos = []
    enlace_doble.on_update = recibidos.append
    enlace_doble.desconectar()
    assert not enlace_doble.is_connected()
    assert recibidos[-1]["port_open"] is False and recibidos[-1]["data_alive"] is False

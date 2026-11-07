"""Tanda 32 (LIQ-01/LIQ-02/LIQ-03): integración de EnfriamientoContrapresion
en el protocolo de fallo (solo_aviso=True: nunca un segundo FALLO)."""

import time
from unittest.mock import MagicMock

import pytest

from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.alarms.catalogo import CIC_22, CIC_23, CIC_24, CIC_25
from autoclave.state_machine.cycle_phases.protocolo_fallo import ProtocoloFallo

ATM = 101.3


class Reloj:
    def __init__(self):
        self.t = 9000.0

    def __call__(self):
        return self.t


@pytest.fixture
def reloj(monkeypatch):
    r = Reloj()
    monkeypatch.setattr(time, "monotonic", r)
    return r


def _protocolo(modo=4, pres=250.0, pchq=300.0, temp=100.0, lenta_rapida=False,
               alarmas=None):
    estado = MagicMock()
    estado.sensores_pres = {"pres_camara": pres, "pres_chaqueta": pchq}
    estado.sensores_temp = {"temp_camara": temp}
    estado.sensores_di = {}
    estado.avisos_ciclo = []
    estado.get_flag.return_value = False
    config = MagicMock()
    config.get.side_effect = lambda k, d=None: {"presion_admosferica": ATM,
                                                "rango_presion_atm": 10.0,
                                                "temp_max_apertura": 80.0}.get(k, d)
    tabla = {("descompresion", "modo"): modo, ("globals", "tipo_carga"): "liquido"}
    for m in (4, 5):
        tabla.update({
            ("descompresion", f"modo_{m}", "temperatura_enfriamiento"): 80.0,
            ("descompresion", f"modo_{m}", "presion_camara_enfriamiento"): 200,
            ("descompresion", f"modo_{m}", "timeout"): 60,
            ("descompresion", f"modo_{m}", "presion_despresurizacion_chaqueta"): 20,
            ("descompresion", f"modo_{m}", "timeout_despresurizacion_chaqueta"): 3,
            ("descompresion", f"modo_{m}", "timeout_presurizacion_enfriamiento"): 3,
        })
    tabla[("descompresion", "modo_5", "descompresion_lenta_rapida")] = lenta_rapida
    tabla[("descompresion", "modo_5", "presion_cambio")] = 150
    cycle = MagicMock()
    cycle.sensores = None
    cycle.get_param.side_effect = lambda *k, default=None: tabla.get(k, default)
    set_do = MagicMock()
    set_do.reset_all_outputs.return_value = True
    prot = ProtocoloFallo(estado, set_do, cycle, config)
    prot.alarm_manager = alarmas
    return prot, estado, set_do


def _llamadas(set_do):
    return [c[0] for c in set_do.method_calls]


def _activas(am):
    return {i.codigo for i in am.activas()}


def test_orden_y_agua_solo_con_a_y_b(reloj):
    prot, estado, set_do = _protocolo(pres=150.0, pchq=300.0)
    prot.ejecutar()
    llamadas = _llamadas(set_do)
    assert "aire_comprimido_camara_on" in llamadas
    assert "descompresion_chaqueta_on" in llamadas
    assert "agua_chaqueta_on" not in llamadas
    assert "descompresion_rapida_on" not in llamadas
    estado.sensores_pres.update({"pres_camara": 200.0, "pres_chaqueta": ATM})
    set_do.reset_mock()
    reloj.t += 1
    prot.update()
    assert "agua_chaqueta_on" in _llamadas(set_do)


def test_modo_5_lenta_en_el_enfriamiento(reloj):
    prot, estado, set_do = _protocolo(modo=5)
    prot.ejecutar()
    assert "descompresion_lenta_on" in _llamadas(set_do)


def test_aviso_no_bloqueante_y_nunca_segundo_fallo_de_contrapresion(reloj):
    am = AlarmManager()
    prot, estado, set_do = _protocolo(pres=200.0, pchq=ATM, alarmas=am)
    prot.ejecutar()                           # armada: (a) y (b)
    estado.sensores_pres["pres_camara"] = 120.0      # < Psat(100) + 30
    for _ in range(15):
        reloj.t += 10
        prot.update()
    assert CIC_25 in _activas(am)
    assert not ({CIC_22, CIC_23, CIC_24} & _activas(am))
    assert prot._enfr is not None and prot._enfr.fallo is None
    assert prot._sub_etapa == "enfriamiento"
    assert any(a["clave"] == "ticket_ciclo.aviso_contrapresion" for a in estado.avisos_ciclo)
    estado.sensores_pres["pres_camara"] = 200.0
    reloj.t += 1
    prot.update()
    assert CIC_25 not in _activas(am)


@pytest.mark.parametrize("pres, pchq, clave", [
    (200.0, 300.0, "ticket_ciclo.aviso_enfriamiento_detenido_chaqueta"),
    (150.0, ATM, "ticket_ciclo.aviso_enfriamiento_detenido_presurizacion"),
])
@pytest.mark.parametrize("modo", [4, 5])
def test_tope_en_el_protocolo_sin_segundo_fallo_mantiene_contrapresion(reloj, pres, pchq,
                                                                      clave, modo):
    """Revisión de la tanda 32 (hallazgo 1): tras el tope la contrapresión se
    mantiene (aire según la presión, chaqueta abierta), sin agua de chaqueta
    ni lenta mientras la carga esté caliente, sin escalar y sin segundo
    fallo."""
    am = AlarmManager()
    prot, estado, set_do = _protocolo(modo=modo, pres=pres, pchq=pchq, alarmas=am)
    prot.ejecutar()
    reloj.t += 3 * 60 + 1
    set_do.reset_mock()
    prot.update()
    llamadas = _llamadas(set_do)
    assert "agua_chaqueta_on" not in llamadas and "agua_chaqueta_off" in llamadas
    assert "descompresion_lenta_on" not in llamadas and "descompresion_lenta_off" in llamadas
    assert "descompresion_rapida_on" not in llamadas
    assert "descompresion_chaqueta_on" in llamadas
    # el aire sigue la presión (objetivo de reposición 200 kPa con T = 100 °C)
    if pres < 200.0:
        assert "aire_comprimido_camara_on" in llamadas
    else:
        assert "aire_comprimido_camara_off" in llamadas
    estado.sensores_pres["pres_camara"] = 190.0
    set_do.reset_mock()
    reloj.t += 3                                     # reafirmación del aire (3 s)
    prot.update()
    assert "aire_comprimido_camara_on" in _llamadas(set_do)
    assert not ({CIC_22, CIC_23, CIC_24} & _activas(am))
    assert [a["clave"] for a in estado.avisos_ciclo] == [clave]
    assert prot._sub_etapa == "enfriamiento" and not prot.sellado
    # sigue con contrapresión y sin ventear; el ticket no se repite
    estado.sensores_pres.update({"pres_camara": 200.0, "pres_chaqueta": ATM})
    set_do.reset_mock()
    for _ in range(3):
        reloj.t += 70
        prot.update()
    llamadas = _llamadas(set_do)
    for salida in ("descompresion_rapida_on", "descompresion_lenta_on", "agua_chaqueta_on"):
        assert salida not in llamadas
    assert len(estado.avisos_ciclo) == 1
    assert not ({CIC_22, CIC_23, CIC_24} & _activas(am))


def test_tope_carga_caliente_bajo_temperatura_de_enfriamiento_no_ventea(reloj):
    """Tras el tope, una carga bajo temperatura_enfriamiento pero sobre
    temp_max_apertura no se despresuriza; bajo temp_max_apertura sale por el
    camino de siempre (chaqueta + rápida en modo 4)."""
    prot, estado, set_do = _protocolo(pres=200.0, pchq=300.0)
    prot._temp_max_sellado = lambda: 70.0
    prot.ejecutar()
    reloj.t += 3 * 60 + 1
    prot.update()
    assert prot._enfr_tope is not None
    estado.sensores_temp["temp_camara"] = 75.0          # < 80 (enfriamiento), > 70
    set_do.reset_mock()
    for _ in range(5):
        reloj.t += 1
        prot.update()
    assert prot._sub_etapa == "enfriamiento"
    llamadas = _llamadas(set_do)
    assert "descompresion_rapida_on" not in llamadas and "descompresion_lenta_on" not in llamadas
    estado.sensores_temp["temp_camara"] = 69.0
    set_do.reset_mock()
    reloj.t += 1
    prot.update()
    assert prot._sub_etapa == "descompresion"
    assert "descompresion_rapida_on" in _llamadas(set_do)


def test_tope_sin_lectura_del_principal_sella(reloj):
    """Tras el tope, el Principal sin lectura lleva al sellado D8-2.10 (sin
    ventear) por el camino de siempre."""
    am = AlarmManager()
    prot, estado, set_do = _protocolo(pres=200.0, pchq=300.0, alarmas=am)
    prot.ejecutar()
    reloj.t += 3 * 60 + 1
    prot.update()
    estado.sensores_temp["temp_camara"] = None
    set_do.reset_mock()
    for _ in range(3):
        reloj.t += 1
        prot.update()
    assert prot.sellado
    llamadas = _llamadas(set_do)
    assert "descompresion_lenta_on" not in llamadas and "descompresion_rapida_on" not in llamadas
    assert "aire_comprimido_camara_on" not in llamadas


def test_tope_presurizacion_sin_contrapresion_que_mantener_sella(reloj):
    """Tope (a) con la cámara ya en la banda atmosférica: sellado D8-2.10 en
    vez de ventear; tras el sellado, solo la lenta (nunca la rápida)."""
    am = AlarmManager()
    prot, estado, set_do = _protocolo(pres=150.0, pchq=ATM, alarmas=am)
    prot.ejecutar()
    estado.sensores_pres["pres_camara"] = ATM + 5        # el aire no llega
    reloj.t += 3 * 60 + 1
    set_do.reset_mock()
    prot.update()
    assert prot.sellado and prot.solo_lenta
    llamadas = _llamadas(set_do)
    for salida in ("descompresion_lenta_on", "descompresion_rapida_on",
                   "aire_comprimido_camara_on", "agua_chaqueta_on"):
        assert salida not in llamadas
    assert [a["clave"] for a in estado.avisos_ciclo] == [
        "ticket_ciclo.aviso_enfriamiento_detenido_presurizacion"]
    assert not ({CIC_22, CIC_23, CIC_24, CIC_25} & _activas(am))


def test_cerrar_todo_sellado_resuelve_cic_25(reloj):
    """Revisión de la tanda 32 (B4): CIC-25 no queda activa con la cámara
    sellada (debounce del Principal)."""
    am = AlarmManager()
    prot, estado, set_do = _protocolo(pres=200.0, pchq=ATM, alarmas=am)
    prot.ejecutar()
    estado.sensores_pres["pres_camara"] = 120.0
    for _ in range(3):
        reloj.t += 6
        prot.update()
    assert CIC_25 in _activas(am)
    estado.sensores_temp["temp_camara"] = None
    reloj.t += 1
    prot.update()                                     # debounce: _cerrar_todo_sellado
    assert not prot.sellado
    assert CIC_25 not in _activas(am)
    assert prot._enfr is None


def test_sin_atmosferica_configurada_no_abre_el_agua(reloj):
    """Revisión de la tanda 32: sin presión atmosférica de referencia
    configurada la condición (b) no se cumple."""
    prot, estado, set_do = _protocolo(pres=200.0, pchq=ATM)
    prot.config.get.side_effect = lambda k, d=None: {"temp_max_apertura": 80.0}.get(k, d)
    prot.ejecutar()
    set_do.reset_mock()
    for _ in range(3):
        reloj.t += 1
        prot.update()
    assert "agua_chaqueta_on" not in _llamadas(set_do)
    assert prot._enfr is not None and not prot._enfr.cond_b


def test_ejecutar_resuelve_el_aviso_que_dejo_la_fase(reloj):
    am = AlarmManager()
    am.activar(CIC_25, margen="30", segundos=10)
    prot, estado, set_do = _protocolo(pres=ATM, alarmas=am)
    prot.ejecutar()
    assert CIC_25 not in _activas(am)


def test_finalizar_resuelve_el_aviso(reloj):
    am = AlarmManager()
    prot, estado, set_do = _protocolo(pres=200.0, pchq=ATM, alarmas=am)
    prot.ejecutar()
    estado.sensores_pres["pres_camara"] = 120.0
    for _ in range(3):
        reloj.t += 6
        prot.update()
    assert CIC_25 in _activas(am)
    prot.finalizar()
    assert CIC_25 not in _activas(am)


def _enfriar(prot, estado, reloj):
    estado.sensores_temp["temp_camara"] = 79.0
    for _ in range(3):
        reloj.t += 1
        prot.update()


def test_modo_4_al_enfriar_chaqueta_y_rapida_como_hoy(reloj):
    prot, estado, set_do = _protocolo(modo=4, pres=200.0, pchq=ATM, lenta_rapida=True)
    prot.ejecutar()
    set_do.reset_mock()
    _enfriar(prot, estado, reloj)
    assert prot._sub_etapa == "descompresion"
    assert "descompresion_rapida_on" in _llamadas(set_do)


def test_liq03_inactiva_modo_5_igual_que_hoy(reloj):
    prot, estado, set_do = _protocolo(modo=5, pres=200.0, pchq=ATM)
    prot.ejecutar()
    set_do.reset_mock()
    _enfriar(prot, estado, reloj)
    llamadas = _llamadas(set_do)
    assert "descompresion_lenta_off" in llamadas and "descompresion_rapida_on" in llamadas


def test_liq03_activa_en_el_protocolo(reloj):
    prot, estado, set_do = _protocolo(modo=5, pres=200.0, pchq=ATM, lenta_rapida=True)
    prot.ejecutar()
    set_do.reset_mock()
    _enfriar(prot, estado, reloj)
    assert prot._sub_etapa == "descompresion_lenta"
    assert "descompresion_rapida_on" not in _llamadas(set_do)
    estado.sensores_pres["pres_camara"] = 170.0
    set_do.reset_mock()
    reloj.t += 1
    prot.update()
    llamadas = _llamadas(set_do)
    assert "descompresion_lenta_on" in llamadas and "descompresion_chaqueta_on" in llamadas
    assert "descompresion_rapida_on" not in llamadas
    # sin lectura de presión no cambia a la rápida
    estado.sensores_pres["pres_camara"] = None
    set_do.reset_mock()
    reloj.t += 1
    prot.update()
    assert "descompresion_rapida_on" not in _llamadas(set_do)
    estado.sensores_pres["pres_camara"] = 150.0
    set_do.reset_mock()
    reloj.t += 1
    prot.update()
    llamadas = _llamadas(set_do)
    assert llamadas.index("descompresion_lenta_off") < llamadas.index("descompresion_rapida_on")
    assert prot._sub_etapa == "descompresion"

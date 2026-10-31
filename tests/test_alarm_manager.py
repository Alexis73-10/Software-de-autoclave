import threading
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from autoclave.state_machine.alarms.alarm_manager import AlarmManager, DETALLE_NO_DISPONIBLE
from autoclave.state_machine.alarms.catalogo import (
    CATALOGO, COM_01, DefinicionAlarma, Despeje, Nivel, PRE_06, PUE_01, SIS_01,
)
from autoclave.state_machine.alarms.instancia import EstadoInstancia, EventoAlarma, clave_de


class _Reloj:
    def __init__(self):
        self.t = datetime(2026, 10, 7, 8, 0, 0)

    def __call__(self):
        self.t += timedelta(seconds=1)
        return self.t


_INFO = DefinicionAlarma("SIS-99", Nivel.INFORMATIVO, "Evento de prueba",
                         "Pasó {algo}.", "", False, Despeje.AUTOMATICO)


def _gestor(con_informativo=False):
    catalogo = dict(CATALOGO)
    if con_informativo:
        catalogo[_INFO.codigo] = _INFO
    eventos = []
    am = AlarmManager(catalogo=catalogo, reloj=_Reloj())
    am.suscribir(lambda ev, inst: eventos.append((ev, inst.clave)))
    return am, eventos


def test_activar_crea_instancia_con_titulo_y_descripcion():
    am, eventos = _gestor()
    inst = am.activar(PRE_06, temp=72.4, maximo=65.0)
    assert inst.clave == "PRE-06" and inst.titulo == "Temperatura de drenaje alta"
    assert "72.4 °C" in inst.descripcion and inst.estado is EstadoInstancia.ACTIVA
    assert eventos == [(EventoAlarma.APARECIDA, "PRE-06")]


def test_activar_de_nuevo_actualiza_valores_sin_evento_ni_nueva_hora():
    am, eventos = _gestor()
    primera = am.activar(PRE_06, temp=70.0, maximo=65.0)
    hora = primera.aparecida
    segunda = am.activar(PRE_06, temp=75.0, maximo=65.0)
    assert segunda is primera and "75.0" in segunda.descripcion
    assert segunda.aparecida == hora and len(eventos) == 1


def test_origen_distingue_instancias():
    am, _ = _gestor()
    am.activar(PUE_01, origen="Puerta 1", puerta="Puerta 1")
    am.activar(PUE_01, origen="Puerta 2", puerta="Puerta 2")
    assert {i.clave for i in am.activas()} == {"PUE-01|Puerta 1", "PUE-01|Puerta 2"}
    assert clave_de("PUE-01", None) == "PUE-01"


def test_codigo_desconocido_lanza():
    am, _ = _gestor()
    with pytest.raises(KeyError):
        am.activar("XXX-01")


@pytest.mark.parametrize("valores", [{}, {"temp": None, "maximo": 65.0}])
def test_plantilla_incompleta_o_none_no_lanza(valores, caplog):
    am, _ = _gestor()
    inst = am.activar(PRE_06, **valores)
    assert inst.descripcion == DETALLE_NO_DISPONIBLE
    assert "PRE-06" in caplog.text


def test_resolver_aviso_sale_de_la_lista():
    am, eventos = _gestor()
    am.activar(PRE_06, temp=70.0, maximo=65.0)
    am.resolver(PRE_06)
    assert am.activas() == []
    assert eventos[-1] == (EventoAlarma.RESUELTA, "PRE-06")


def test_resolver_inexistente_no_hace_nada():
    am, eventos = _gestor()
    am.resolver(PRE_06)
    assert eventos == []


def test_alarma_sin_reconocer_queda_resuelta_sin_reconocer():
    am, _ = _gestor()
    am.activar(COM_01)
    am.resolver(COM_01)
    [inst] = am.activas()
    assert inst.estado is EstadoInstancia.RESUELTA_SIN_RECONOCER and inst.resuelta is not None


def test_reconocer_resuelta_la_saca():
    am, eventos = _gestor()
    am.activar(COM_01)
    am.resolver(COM_01)
    assert am.reconocer("COM-01", "cristian") is True
    assert am.activas() == []
    assert eventos[-1] == (EventoAlarma.RECONOCIDA, "COM-01")


def test_reconocer_activa_la_marca_y_al_resolver_sale():
    am, _ = _gestor()
    inst = am.activar(COM_01)
    am.reconocer("COM-01", "cristian")
    assert inst.reconocida_por == "cristian" and inst.reconocida_en is not None
    assert am.activas() == [inst]
    am.resolver(COM_01)
    assert am.activas() == []


def test_reconocer_inexistente_o_aviso_devuelve_false():
    am, _ = _gestor()
    assert am.reconocer("COM-01", "x") is False
    am.activar(PRE_06, temp=70.0, maximo=65.0)
    assert am.reconocer("PRE-06", "x") is False


def test_reactivar_resuelta_sin_reconocer():
    am, eventos = _gestor()
    inst = am.activar(COM_01)
    hora = inst.aparecida
    am.resolver(COM_01)
    otra = am.activar(COM_01)
    # Instancia nueva (spec §5.2, corrección 2026-10-07): la vieja queda en
    # su fila del historial, resuelta y sin reconocer.
    assert otra is not inst
    assert otra.estado is EstadoInstancia.ACTIVA and otra.resuelta is None
    assert otra.aparecida > hora and otra.reconocida_por is None
    assert inst.estado is EstadoInstancia.RESUELTA_SIN_RECONOCER
    assert am.activas() == [otra] and am.obtener("COM-01") is otra
    assert eventos[-1] == (EventoAlarma.APARECIDA, "COM-01")
    assert [e for e, _ in eventos].count(EventoAlarma.APARECIDA) == 2


def test_resolver_todas_por_reinicio_conserva_no_reconocidas():
    am, _ = _gestor()
    am.activar(PRE_06, temp=70.0, maximo=65.0)
    am.activar(COM_01)
    am.activar(SIS_01, estado="Falla")
    am.reconocer("SIS-01", "cristian")
    am.resolver_todas_por_reinicio()
    [inst] = am.activas()
    assert inst.clave == "COM-01" and inst.estado is EstadoInstancia.RESUELTA_SIN_RECONOCER


def test_activas_ordenadas_por_nivel_y_hora():
    am, _ = _gestor()
    am.activar(PRE_06, temp=70.0, maximo=65.0)
    am.activar(COM_01)
    am.activar(SIS_01, estado="Ciclo")
    assert [i.codigo for i in am.activas()] == ["SIS-01", "COM-01", "PRE-06"]


def test_informativo_no_entra_a_activas_y_va_a_eventos():
    am, eventos = _gestor(con_informativo=True)
    inst = am.activar("SIS-99", algo="algo")
    assert am.activas() == []
    assert am.eventos_recientes() == [inst] and inst.resuelta == inst.aparecida
    assert eventos == [(EventoAlarma.APARECIDA, "SIS-99")]


def test_eventos_recientes_limita_a_20():
    am, _ = _gestor(con_informativo=True)
    for i in range(25):
        am.activar("SIS-99", algo=str(i))
    recientes = am.eventos_recientes()
    assert len(recientes) == 20 and recientes[-1].descripcion == "Pasó 24."


def test_oyente_que_falla_no_rompe_activar(caplog):
    am, _ = _gestor()
    am.suscribir(lambda ev, inst: 1 / 0)
    am.activar(COM_01)
    assert len(am.activas()) == 1


def test_oyente_se_llama_fuera_del_candado():
    am, _ = _gestor()
    dentro = []
    am.suscribir(lambda ev, inst: dentro.append(am._lock.locked()))
    am.activar(COM_01)
    assert dentro == [False]


def test_has_consultas_con_instancias_nuevas():
    am, _ = _gestor()
    assert not am.has_active_alarms()
    am.activar(SIS_01, estado="Ciclo")
    assert am.has_emergency() and am.has_blocking_alarm() and am.has_active_alarms()


def test_concurrencia_reconocer_y_resolver():
    am, _ = _gestor()
    for _ in range(200):
        am.activar(COM_01)
        t1 = threading.Thread(target=am.resolver, args=(COM_01,))
        t2 = threading.Thread(target=am.reconocer, args=("COM-01", "x"))
        t1.start(); t2.start(); t1.join(); t2.join()
        restantes = am.activas()
        # Resuelta y reconocida, en cualquier orden: no puede quedar en la lista.
        assert restantes == [], restantes

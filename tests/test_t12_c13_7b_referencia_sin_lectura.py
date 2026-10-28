# tests/test_t12_c13_7b_referencia_sin_lectura.py
#
# Tanda 12, C-13.7b (opción B confirmada 24-oct): Referencia sin lectura en
# ciclo -> el ciclo continúa, SEN-11 no bloqueante con el sensor, sin apertura
# automática. Principal sin lectura -> FALLO SEN-02 igual que hoy; presión
# sin lectura igual que hoy.
# Tanda 21 (FC-08): la marca NO CONFORME se reemplaza por una observación
# del ciclo (sensor, hora, fase) que queda aunque la Referencia vuelva a leer.

from unittest.mock import MagicMock

from autoclave.services.domain.logging import ticket_formatter as tf
from autoclave.state_machine.alarms.catalogo import CATALOGO, Nivel
from autoclave.state_machine.states.ciclo import CicloResultado
from tests.test_t3_sensores_ciclo import _ciclo

_ASIG_REF = {"temp_camara": "principal", "temp_2_camara": "no_en_uso", "temp_ref": "referencia"}
_NO_CONFORME = "ticket_ciclo.no_conforme_referencia"     # ciclos guardados antes de FC-08
_OBSERVACION = "ticket_ciclo.observacion_referencia"


def _ciclo_con_ref(temp_ref):
    ciclo, estado, am = _ciclo(_ASIG_REF, {"temp_camara": 100.0, "temp_ref": temp_ref})
    estado.avisos_ciclo = []
    fase = ciclo._fases[0]
    fase.update = MagicMock(return_value=None)
    return ciclo, estado, am, fase


def test_referencia_sin_lectura_el_ciclo_continua():
    ciclo, estado, am, fase = _ciclo_con_ref(None)
    ciclo.run()
    assert estado.fase_ciclo != "SENSOR_AUSENTE"
    fase.update.assert_called_once()
    assert ciclo._resultado_pendiente is None
    ciclo._protocolo.ejecutar.assert_not_called()


def test_referencia_en_cero_tambien_es_sin_lectura():
    ciclo, estado, am, fase = _ciclo_con_ref(0)
    ciclo.run()
    fase.update.assert_called_once()
    assert ciclo.referencia_sin_lectura is True


def test_alarma_no_bloqueante_con_el_sensor():
    ciclo, estado, am, _ = _ciclo_con_ref(None)
    ciclo.run()
    activas = [i for i in am.activas() if i.codigo == "SEN-11"]
    assert len(activas) == 1
    assert activas[0].valores["sensor"] == "Referencia"
    d = CATALOGO["SEN-11"]
    assert d.nivel is Nivel.AVISO and d.bloquea_inicio is False
    assert "SEN-02" not in [i.codigo for i in am.activas()]


def test_observacion_queda_aunque_vuelva_a_leer_y_una_sola_vez():
    ciclo, estado, am, _ = _ciclo_con_ref(None)
    for _ in range(3):
        ciclo.run()
    estado.sensores_temp["temp_ref"] = 121.0
    ciclo.run()
    estado.sensores_temp["temp_ref"] = None
    ciclo.run()
    assert ciclo.referencia_sin_lectura is True
    marcas = [a for a in estado.avisos_ciclo if a.get("clave") == _OBSERVACION]
    assert len(marcas) == 1
    assert marcas[0]["sensor"] == "Referencia" and marcas[0]["fase"] == ciclo._fases[0].name
    assert len(marcas[0]["hora"]) == 5 and marcas[0]["hora"][2] == ":"
    assert not [a for a in estado.avisos_ciclo if a.get("clave") == _NO_CONFORME]


def test_texto_del_ticket_es_y_en_de_ciclos_guardados_no_conformes():
    # lectura histórica intacta: un ciclo guardado NO CONFORME se imprime igual
    aviso = {"clave": _NO_CONFORME, "sensor": "Referencia"}
    assert tf.aviso_ticket(aviso, tf.Presentacion(idioma="es")) == \
        "NO CONFORME: punto de referencia sin verificar (Referencia)"
    assert tf.aviso_ticket(aviso, tf.Presentacion(idioma="en")) == \
        "NONCONFORMING: reference point not verified (Referencia)"
    pie = tf.format_footer("COMPLETADO", "2026-10-24T18:00:00", avisos=[aviso],
                           p=tf.Presentacion(idioma="es"))
    assert "NO CONFORME: punto de referencia sin verificar" in pie


def test_reset_del_ciclo_limpia_la_marca():
    ciclo, estado, _, _ = _ciclo_con_ref(None)
    ciclo.run()
    assert ciclo.referencia_sin_lectura
    ciclo.reset()
    assert ciclo.referencia_sin_lectura is False


def test_principal_sin_lectura_sigue_fallando_sen02():
    ciclo, estado, am = _ciclo(_ASIG_REF, {"temp_camara": None, "temp_ref": 121.0})
    fase = ciclo._fases[0]
    fase.update = MagicMock()
    ciclo.run()
    assert estado.fase_ciclo == "SENSOR_AUSENTE"
    fase.update.assert_not_called()
    assert [i.codigo for i in am.activas()] == ["SEN-02"]
    ciclo._protocolo.ejecutar.assert_called_once_with(solo_lenta=True)


def test_principal_y_referencia_sin_lectura_falla_sen02_con_ambos():
    ciclo, estado, am = _ciclo(_ASIG_REF, {"temp_camara": None, "temp_ref": None})
    ciclo._fases[0].update = MagicMock()
    ciclo.run()
    assert estado.fase_ciclo == "SENSOR_AUSENTE"
    inst = [i for i in am.activas() if i.codigo == "SEN-02"][0]
    assert "Referencia" in inst.valores["sensores"]


def test_presion_sin_lectura_sigue_fallando():
    ciclo, estado, am = _ciclo(_ASIG_REF, {"temp_camara": 100.0, "temp_ref": None})
    estado.sensores_pres["pres_camara"] = None
    ciclo._fases[0].update = MagicMock()
    ciclo.run()
    assert estado.fase_ciclo == "SENSOR_AUSENTE"
    assert [i.codigo for i in am.activas()] == ["SEN-04"]


# ── Apertura automática ──────────────────────────────────────────────────────

def _apertura(sin_lectura):
    ciclo, estado, am = _ciclo(_ASIG_REF, {"temp_camara": 50.0, "temp_ref": 50.0})
    estado.avisos_ciclo = ([{"clave": _OBSERVACION, "sensor": "Referencia", "hora": "10:00",
                             "fase": "ESTERILIZACION"}]
                           if sin_lectura else [])
    estado.sensores_pres["pres_camara"] = 101.3
    params = {"apertura_automatica": True, "tiempo_espera_apertura": 0,
              "temp_max_apertura": 80.0, "timeout_temperatura": 30}
    ciclo.cycle.get_param.side_effect = lambda *k, default=None: params.get(k[-1], default)
    ciclo.config.get.side_effect = lambda k, *a: {"presion_admosferica": 101.3,
                                                   "rango_presion_atm": 20.0}.get(k)
    puertas = MagicMock()
    puertas.doors = {"Puerta 1": object()}
    puertas.tiene_actuador.return_value = True
    puertas.get_status.return_value = "ABIERTO"
    ciclo.door_service = puertas
    flags = {}
    estado.set_flag.side_effect = lambda f, v: flags.__setitem__(f, v)
    ciclo._resultado_pendiente = CicloResultado.COMPLETADO
    ciclo._mantener_apertura_automatica()
    return flags, puertas


def test_ciclo_sin_observacion_usa_la_apertura_automatica():
    flags, _ = _apertura(sin_lectura=False)
    assert flags.get("CICLO_CONFIRMADO") is True


def test_ciclo_con_referencia_sin_lectura_no_usa_la_apertura_automatica():
    flags, puertas = _apertura(sin_lectura=True)
    assert "CICLO_CONFIRMADO" not in flags
    puertas.request_open.assert_not_called()

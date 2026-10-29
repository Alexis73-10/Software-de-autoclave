# tests/test_t23_ain_grupos.py
#
# Tanda 23 (AIN-01, AIN-02, AIN-R1): los puertos analógicos se numeran por
# grupo, RTD 01-06 (temperatura) y AI 01-16 (presión). El mismo número en dos
# grupos son puertos distintos: sin conflicto ni cruce de lecturas, en el
# backend, en /io/assignment y en el controlador de Reasignación.

import json
import sys

import pytest

from autoclave.core.runtime import asignacion_io as aio
from autoclave.core.runtime import io_names
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.hal.measures import converters
from autoclave.hal.measures.units import Units
from autoclave.utils.resources import resource_path
from tests.test_r8_reasignacion_api import _aplicar, api  # noqa: F401  (fixture)

CALIBRACION = resource_path("autoclave/config/calibration_modbus.yaml")


@pytest.fixture(autouse=True)
def _limpio():
    aio.restablecer_memoria_fabrica_codigo()
    converters.reiniciar_presiones()
    yield
    aio.restablecer_memoria_fabrica_codigo()
    converters.reiniciar_presiones()


# ── etiquetas ──────────────────────────────────────────────────────────────

@pytest.mark.req("AIN-01")
def test_etiquetas_por_grupo():
    assert aio.etiqueta("AI", 1, "temp_camara") == "RTD 01"
    assert aio.etiqueta("AI", 1, "pres_camara") == "AI 01"
    assert aio.etiqueta("AI", 16, "pres_camara") == "AI 16"
    assert aio.etiqueta("DO", 4) == "DO 04" and aio.etiqueta("DI", 11) == "DI 11"
    assert aio.etiqueta_grupo("AI_TEMP", 6) == "RTD 06"
    ids = {s["name"]: s["id"] for s in io_names.sensores("temperature")}
    ids.update({s["name"]: s["id"] for s in io_names.sensores("pressure")})
    assert ids["temp_camara"] == "RTD 01" and ids["pres_camara"] == "AI 01"
    raw = {s["name"]: s["raw_index"] for s in io_names.sensores("pressure")}
    assert raw["pres_camara"] == 8


# ── RTD 01 y AI 01 a la vez ─────────────────────────────────────────────────

@pytest.mark.req("AIN-R1")
def test_rtd_01_y_ai_01_sin_conflicto_ni_cruce_de_lecturas():
    f = aio.fabrica_codigo()
    assert f["AI"]["temp_camara"] == 1 and f["AI"]["pres_camara"] == 1
    assert aio.validar(f) == []
    # el mismo número en el otro grupo tampoco choca
    asignacion = aio.combinar(f, {"temp_camara": 6, "pres_camara": 6})
    assert aio.validar(asignacion) == []
    # en el mismo grupo sí
    e = aio.validar(aio.combinar(f, {"pres_chaqueta": 1}))
    assert [x["codigo"] for x in e] == ["conflicto"] and e[0]["grupo"] == "AI_PRES"
    assert "AI 01" in aio.texto_error(e[0])
    e = aio.validar(aio.combinar(f, {"temp_2_camara": 1}))
    assert [x["codigo"] for x in e] == ["conflicto"] and e[0]["grupo"] == "AI_TEMP"
    assert "RTD 01" in aio.texto_error(e[0])

    # sin cruce: temperatura de ai[0], presión de ai[8] (Units + EstadoAutoclave)
    aio.aplicar_en_memoria(f)
    # filtros de módulo limpios: otra prueba del mismo proceso pudo dejarlos cargados
    for filtro in converters._ma_temp:
        filtro.buffer.clear()
    for filtro in converters._oe_temp:
        filtro.reset()
    converters.reiniciar_presiones()
    u = Units(CALIBRACION)
    ai = [None] * 24
    ai[0] = 1234            # RTD 01: 123,4 °C
    ai[8] = 12000           # AI 01: 12 mA -> 200 kPa
    for seq in range(1, converters.DEBOUNCE_LECTURAS_PRESION + 3):
        u.update_from_serial({"ai": ai, "ai_seq": seq, "port_open": True, "data_alive": True})
    datos = u.get_all()
    e = EstadoAutoclave()
    e.update({"temperature": datos["temperature"], "pressure": datos["pressure"]})
    assert e.sensores_temp["temp_camara"] == pytest.approx(123.4)
    assert e.sensores_pres["pres_camara"] == pytest.approx(200.0)
    assert aio.responde("temp_camara", f, {"connected": True, **datos})
    assert aio.responde("pres_camara", f, {"connected": True, **datos})
    assert not aio.responde("pres_chaqueta", f, {"connected": True, **datos})


@pytest.mark.req("AIN-R1")
def test_io_assignment_publica_ocupados_por_grupo(api):  # noqa: F811
    cliente, _srv, _ctx, cab, _p = api
    r = cliente.get("/io/assignment", headers=cab())
    assert r.status_code == 200
    d = r.json()
    assert set(d["ocupados"]) == {"DI", "DO", "AI_TEMP", "AI_PRES"}
    assert d["ocupados"]["AI_TEMP"]["1"] == "temp_camara"
    assert d["ocupados"]["AI_PRES"]["1"] == "pres_camara"
    filas = {f["funcion"]: f for f in d["filas"]}
    assert filas["temp_camara"]["id_actual"] == "RTD 01" and filas["temp_camara"]["grupo"] == "AI_TEMP"
    assert filas["pres_camara"]["id_actual"] == "AI 01" and filas["pres_camara"]["grupo"] == "AI_PRES"
    assert filas["pres_camara"]["id_guardado"] == "AI 01"
    # mover las dos al número 6 de su grupo: válido (sin conflicto)
    r = _aplicar(cliente, cab(), {"temp_camara": 6, "pres_camara": 6})
    assert r.status_code == 200, r.text


@pytest.mark.req("AIN-02")
@pytest.mark.parametrize("cambios,etiqueta", [
    ({"temp_camara": 7}, "RTD 07"),
    ({"pres_camara": 17}, "AI 17"),
    ({"pres_camara": 0}, "AI 00"),
])
def test_puertos_inexistentes(api, cambios, etiqueta):  # noqa: F811
    errores = aio.validar(aio.combinar(aio.fabrica_codigo(), cambios))
    assert [e["codigo"] for e in errores] == ["puerto_inexistente"]
    assert etiqueta in aio.texto_error(errores[0])
    cliente, _srv, ctx, cab, _p = api
    r = _aplicar(cliente, cab(), cambios)
    assert r.status_code == 422 and r.json()["codigo"] == "puerto_inexistente"
    assert not ctx.archivo_asignacion.existe()


# ── controlador de Reasignación ─────────────────────────────────────────────

def _datos_controlador() -> dict:
    f = aio.fabrica_codigo()
    filas = []
    for tipo in aio.TIPOS:
        for funcion, puerto in f[tipo].items():
            filas.append({"funcion": aio.clave(tipo, funcion), "tipo": tipo, "i18n": f"io.x.{funcion}",
                          "puerto_actual": puerto, "id_actual": aio.etiqueta(tipo, puerto, funcion),
                          "puerto_guardado": puerto, "puerto_fabrica": puerto,
                          "id_fabrica": aio.etiqueta(tipo, puerto, funcion),
                          "critica": False, "reforzada": False,
                          "temperatura": tipo == "AI" and aio.es_temperatura(funcion),
                          "grupo": aio.grupo(tipo, funcion)})
    return {"filas": filas,
            "puertos": {g: list(r) for g, r in aio.puertos().items()},
            "ocupados": {g: {str(p): aio.clave(t, fn) for t in aio.TIPOS for fn, p in f[t].items()
                             if aio.grupo(t, fn) == g} for g in aio.GRUPOS},
            "cambios_guardados": {}, "reinicio_pendiente": False, "error_archivo": "",
            "bloqueo": "", "verificacion": {"estado": "sin_cambios", "funciones": {}},
            "editable": True, "motivo": "", "reinicio_disponible": True}


def _controlador():
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    from autoclave.ui_qml.controllers.reasignacion_controller import ReasignacionController
    from autoclave.ui_qml.sesion_backend import Resultado

    class _Sesion:
        def enviar(self, metodo, ruta, cuerpo=None):
            return Resultado("ok", json.loads(json.dumps(_datos_controlador())), 200)
    c = ReasignacionController(sesion=_Sesion())
    c.cargar()
    return c


@pytest.mark.req("AIN-R1")
def test_controlador_por_grupo():
    c = _controlador()
    assert c.conflictos == []
    pres = {x["puerto"]: x for x in c.puertosPara("pres_camara")}
    assert sorted(pres) == list(range(1, 17))
    assert pres[1]["etiqueta"] == "AI 01" and pres[1]["actual"] is True
    assert pres[1]["ocupadoPor"] == ""                       # RTD 01 no ocupa AI 01
    assert pres[2]["ocupadoPor"] == "io.x.pres_chaqueta"
    temp = {x["puerto"]: x for x in c.puertosPara("temp_camara")}
    assert sorted(temp) == list(range(1, 7))
    assert temp[1]["etiqueta"] == "RTD 01" and temp[1]["ocupadoPor"] == ""
    assert temp[4]["ocupadoPor"] == ""                       # AI 04 (pres_empaque_2) no ocupa RTD 04
    assert temp[5]["ocupadoPor"] == "io.x.temp_drenaje"
    # mover a un número que solo está ocupado en el otro grupo: sin conflicto
    c.elegirPuerto("temp_camara", 4)
    c.elegirPuerto("pres_camara", 6)
    assert c.conflictos == []
    assert c.pendientes == {"temp_camara": "RTD 04", "pres_camara": "AI 06"}
    # en el mismo grupo, sí
    c.elegirPuerto("pres_chaqueta", 6)
    [conflicto] = c.conflictos
    assert {conflicto["funcion"], conflicto["otra"]} == {"pres_camara", "pres_chaqueta"}
    assert conflicto["etiqueta"] == "AI 06" and conflicto["grupo"] == "AI_PRES"

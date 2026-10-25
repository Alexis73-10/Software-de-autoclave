"""S1 (tanda 2, decisión 1 de Cristian, 19-oct): el equipo de pruebas, con
generador interno, NO lleva DO1 (vapor_generador) ni DO2 (vapor_caldera): el
generador tiene sus propios controles y el software no los enciende ni los lee.
Con `vapor_source = generator` ninguna de las dos salidas se enciende nunca
(lazo, fases ni modo prueba). Caldera externa y mixto conservan su asignación
de E1b (queda abierta, sin cambios)."""

import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from autoclave.devices.io.set_io import SetOutput
from autoclave.installation.profile import salidas_vapor_permitidas
from tests.helpers.backend_doble import modulo_backend

_SRC = Path(__file__).resolve().parents[1] / "src" / "autoclave"


def _setdo(fuente):
    io = MagicMock()
    return SetOutput(io, MagicMock(), profile=SimpleNamespace(vapor_source=fuente)), io


def test_generador_interno_sin_salidas_de_fuente_de_vapor():
    assert salidas_vapor_permitidas(SimpleNamespace(vapor_source="generator")) == set()


def test_generador_nunca_enciende_do1_ni_do2():
    setdo, io = _setdo("generator")
    setdo.vapor_generador_on()
    setdo.vapor_caldera_on()
    setdo.set_output(1, True)
    setdo.set_output(2, True)
    assert all(c.args[1] is False for c in io.set_output.call_args_list)
    assert setdo.salida_bloqueada(1) is True and setdo.salida_bloqueada(2) is True


@pytest.mark.parametrize("fuente, permitidas", [
    ("boiler", {"vapor_caldera"}),
    ("mixed", {"vapor_generador", "vapor_caldera"}),
    (None, {"vapor_generador", "vapor_caldera"}),
])
def test_caldera_y_mixto_sin_cambios(fuente, permitidas):
    assert salidas_vapor_permitidas(SimpleNamespace(vapor_source=fuente)) == permitidas


def test_ningun_codigo_de_control_enciende_ni_lee_do1_do2():
    """Fuera de set_io.py (los métodos) y del mapa de E/S, nadie llama a
    vapor_generador_on/vapor_caldera_on ni lee su estado."""
    patron = re.compile(r"vapor_(generador|caldera)_on"
                        r"|salidas_do(\[\s*|\.get\(\s*)[\"']vapor_(generador|caldera)"
                        r"|set_output\(\s*[12]\s*,\s*True")
    hallados = []
    for py in _SRC.rglob("*.py"):   # set_output(1|2, True) literal o vía serial
        if "__pycache__" in py.parts or py.name == "set_io.py":
            continue
        for n, linea in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            if patron.search(linea):
                hallados.append(f"{py.relative_to(_SRC)}:{n}")
    assert hallados == []


def test_modo_prueba_rechaza_encender_do1_con_generador():
    from autoclave.devices.puertas.enum_doors import DoorState
    from autoclave.state_machine.machine.enum_global import GlobalState
    from fastapi.testclient import TestClient
    from tests.helpers.backend_doble import cabecera, cargar_servidor
    from tests.test_io_endpoints import _DI_ABIERTA, _DI_CERRADA, _puerta

    ctx = MagicMock()
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    ctx.estado.get_flag.return_value = False
    ctx.estado.sensores_pres = {"pres_camara": 101.0}
    ctx.estado.sensores_di = {_DI_CERRADA: 1, _DI_ABIERTA: 0}
    ctx.estado.get_door_state.return_value = DoorState.CERRADO
    ctx.config_manager.get.side_effect = {"presion_admosferica": 101.3,
                                          "rango_presion_atm": 5.0}.get
    ctx.doors = [_puerta()]
    ctx.control_loop.test_mode_active = True
    io = MagicMock()
    ctx.setdo = SetOutput(io, ctx.estado, profile=SimpleNamespace(vapor_source="generator"))
    srv, _ = cargar_servidor(ctx)
    cab = cabecera(srv, "tecnico", "tec1")
    modulo_backend("rutas.io")._token_modo_prueba = cab["Authorization"].split()[1]
    client = TestClient(srv.app, headers=cab)
    for nombre in ("vapor_generador", "vapor_caldera"):
        r = client.patch(f"/io/test/output/{nombre}", json={"value": True})
        assert r.status_code == 409 and r.json()["codigo"] == "fuente_vapor_no_instalada"
    io.set_output.assert_not_called()


def test_asistente_describe_el_generador_sin_do1_do2():
    import json
    for lang in ("es", "en"):
        textos = json.loads((_SRC / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))
        assert "DO1" in textos["instalacion"]["vapor_generator_desc"]

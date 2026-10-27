# tests/test_e11_retiro_aire_chaqueta.py
#
# E11 (tanda 11, D11-2): retiro de la salida aire_comprimido_chaqueta. El canal
# que ocupaba (índice 12 de map_do, DO 13) queda libre; las demás salidas
# conservan su número. Un YAML o una asignación de E/S antigua que aún la trae
# se acepta y se ignora con una advertencia en el log.

import json
import logging
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autoclave.core.runtime import asignacion_io as aio
from autoclave.core.runtime import io_names
from autoclave.core.runtime.status import EstadoAutoclave as E
from autoclave.utils.resources import resource_path

RETIRADA = "aire_comprimido_chaqueta"

# Numeración física de fábrica (0-indexada, posición en la trama DO) que NO
# debe cambiar: la de antes de E11 sin la salida retirada.
_MAP_DO_ESPERADO = {
    "vapor_generador": 0, "vapor_caldera": 1, "vapor_chaqueta": 2, "vapor_camara": 3,
    "descompresion_rapida": 4, "descompresion_lenta": 5, "descompresion_chaqueta": 6,
    "vacio_camara": 7, "desbloqueo_puerta_1": 8, "desbloqueo_puerta_2": 9,
    "bloqueo_puerta_1": 10, "bloqueo_puerta_2": 11,
    "aire_comprimido_camara": 13, "aire_admosferico_camara": 14, "agua_chaqueta": 15,
    "agua_intercambiador": 16, "agua_bomba": 17, "bomba_vacio": 18,
    "abrir_puerta_1": 19, "abrir_puerta_2": 20, "cerrar_puerta_1": 21,
    # tanda 19 (decisión 4 de Cristian, MOD-05): buzzer en DO 25 (posición 24)
    "cerrar_puerta_2": 22, "buzer_alarma": 24,
}


@pytest.fixture(autouse=True)
def _mapas_de_fabrica():
    aio.restablecer_memoria_fabrica_codigo()
    yield
    aio.restablecer_memoria_fabrica_codigo()


def _config_antigua(tmp_path):
    """Copia de la configuración con el YAML de instancia de antes de E11
    (io_enabled e io_ports con la salida retirada en DO 13)."""
    origen = Path(resource_path("autoclave/config"))
    destino = tmp_path / "config"
    (destino / "instances").mkdir(parents=True)
    shutil.copy(origen / "active_instances.yaml", destino / "active_instances.yaml")
    texto = (origen / "instances" / "ACV-2026-001.yaml").read_text(encoding="utf-8")
    texto = texto.replace("    - bloqueo_puerta_2\n    - aire_comprimido_camara\n",
                          "    - bloqueo_puerta_2\n    - aire_comprimido_chaqueta\n"
                          "    - aire_comprimido_camara\n")
    texto = texto.replace("    bloqueo_puerta_2: 12\n",
                          "    bloqueo_puerta_2: 12\n    aire_comprimido_chaqueta: 13\n")
    assert texto.count(RETIRADA) == 2
    (destino / "instances" / "ACV-2026-001.yaml").write_text(texto, encoding="utf-8")
    return destino


# ── La función ya no existe ─────────────────────────────────────────────────

def test_las_demas_salidas_conservan_su_numero():
    assert dict(E.map_do) == _MAP_DO_ESPERADO
    assert 12 not in E.map_do.values()               # DO 13 libre


def test_no_esta_en_el_catalogo_de_asignacion():
    assert RETIRADA not in aio.funciones()
    assert RETIRADA not in aio.fabrica_codigo()["DO"]
    assert RETIRADA not in aio.fabrica()["DO"]       # YAML del repo
    assert 13 not in aio.fabrica()["DO"].values()


def test_no_esta_en_los_canales_de_entradas_salidas():
    io = io_names.leer_io_enabled()
    assert RETIRADA not in io["DO"]
    assert RETIRADA not in [c["name"] for c in io_names.canales_digitales("DO")]


def test_io_channels_no_la_lista():
    from fastapi.testclient import TestClient
    from autoclave.state_machine.machine.enum_global import GlobalState
    from tests.helpers.backend_doble import cabecera, cargar_servidor
    ctx = MagicMock()
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    ctx.setdo.salida_bloqueada.return_value = False
    srv, _ = cargar_servidor(ctx)
    datos = TestClient(srv.app).get("/io/channels", headers=cabecera(srv, "tecnico")).json()
    nombres = [c["name"] for c in datos["DO"]]
    assert RETIRADA not in nombres and "aire_comprimido_camara" in nombres
    assert "DO 13" not in [c["id"] for c in datos["DO"]]
    assert {c["name"]: c["id"] for c in datos["DO"]}["aire_comprimido_camara"] == "DO 14"


def test_set_io_sin_metodos_de_la_salida_retirada():
    from autoclave.devices.io.set_io import SetOutput
    assert not hasattr(SetOutput, f"{RETIRADA}_on")
    assert not hasattr(SetOutput, f"{RETIRADA}_off")
    assert hasattr(SetOutput, "aire_comprimido_camara_on")


def test_aire_comprimido_camara_sigue_en_su_canal():
    from autoclave.devices.io.set_io import SetOutput
    io = MagicMock()
    s = SetOutput(io, estado=MagicMock())
    s.aire_comprimido_camara_on()
    s.aire_comprimido_camara_off()
    assert [(c.args[0], c.args[1]) for c in io.set_output.call_args_list] == [(14, True), (14, False)]


def test_apagado_individual_sigue_cubriendo_el_canal_libre():
    """Si el ALL_OFF no se confirma, el apagado canal por canal sigue enviando
    DO 13 en 0 (canal libre: siempre apagado)."""
    from autoclave.devices.io.set_io import SetOutput
    io = MagicMock()
    io.all_off.return_value = False
    SetOutput(io, estado=MagicMock()).reset_all_outputs()
    assert (13, False) in [(c.args[0], c.args[1]) for c in io.set_output.call_args_list]


def test_salidas_energia_sin_la_retirada():
    from autoclave.backend.context import BackendContext
    assert RETIRADA not in BackendContext._SALIDAS_ENERGIA
    assert "aire_comprimido_camara" in BackendContext._SALIDAS_ENERGIA


def test_i18n_sin_la_salida_retirada():
    base = Path(resource_path("autoclave/i18n"))
    for idioma in ("es", "en"):
        texto = (base / f"{idioma}.json").read_text(encoding="utf-8")
        assert RETIRADA not in texto, idioma


def test_yaml_de_modelo_sin_la_salida_retirada():
    texto = (Path(resource_path("autoclave/config")) / "models" / "solids_liquids.yaml") \
        .read_text(encoding="utf-8")
    assert RETIRADA not in texto


# ── YAML y asignación antiguos: se aceptan y se ignoran con advertencia ─────

def test_yaml_antiguo_io_ports_se_ignora_con_advertencia(tmp_path, caplog):
    cfg = _config_antigua(tmp_path)
    with caplog.at_level(logging.WARNING):
        f = aio.fabrica(cfg)
    assert f == aio.fabrica_codigo()
    assert any(RETIRADA in r.getMessage() for r in caplog.records
               if r.levelno == logging.WARNING)


def test_yaml_antiguo_io_enabled_se_omite_con_advertencia(tmp_path, caplog):
    cfg = _config_antigua(tmp_path)
    with caplog.at_level(logging.WARNING):
        canales = io_names.canales_digitales("DO", config_dir=cfg)
    assert RETIRADA not in [c["name"] for c in canales]
    assert len(canales) == len(_MAP_DO_ESPERADO)
    assert any(RETIRADA in r.getMessage() for r in caplog.records
               if r.levelno == logging.WARNING)


def test_asignacion_guardada_antigua_se_ignora_con_advertencia(tmp_path, caplog):
    ruta = tmp_path / "data" / "asignacion_io.json"
    ruta.parent.mkdir(parents=True)
    ruta.write_text(json.dumps({"formato": aio.FORMATO,
                                "cambios": {RETIRADA: 25, "vapor_camara": 26},
                                "verificacion_pendiente": [RETIRADA]}), encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        asignacion, _ = aio.vigente(aio.fabrica_codigo(), aio.ArchivoAsignacion(ruta))
    assert RETIRADA not in asignacion["DO"]
    assert asignacion["DO"]["vapor_camara"] == 26          # lo demás sí se aplica
    assert any(RETIRADA in r.getMessage() for r in caplog.records
               if r.levelno == logging.WARNING)


def test_arranque_con_yaml_y_asignacion_antiguos_no_bloquea(tmp_path, caplog):
    """cargar_asignacion_io con un YAML de instancia y un asignacion_io.json
    de antes de E11: arranca (sin ErrorArranque ni CONFIGURACION_INVALIDA) y
    deja la advertencia en el log."""
    from autoclave.backend.context import BackendContext
    cfg = _config_antigua(tmp_path)
    ruta = tmp_path / "data" / "asignacion_io.json"
    ruta.parent.mkdir(parents=True)
    ruta.write_text(json.dumps({"formato": aio.FORMATO, "cambios": {RETIRADA: 25},
                                "verificacion_pendiente": []}), encoding="utf-8")
    ctx = BackendContext.__new__(BackendContext)
    ctx.alarm_manager = MagicMock()
    ctx.alarm_manager.condiciones_bloqueo = []
    with caplog.at_level(logging.WARNING):
        ctx.cargar_asignacion_io(archivo=aio.ArchivoAsignacion(ruta), config_dir=cfg)
    assert ctx.motivo_asignacion == ""
    ctx.alarm_manager.activar.assert_not_called()
    assert dict(E.map_do) == _MAP_DO_ESPERADO
    assert any(RETIRADA in r.getMessage() for r in caplog.records
               if r.levelno == logging.WARNING)


def test_respaldo_antiguo_se_acepta_sin_la_retirada(caplog):
    from tests.helpers.backend_doble import cargar_servidor
    cargar_servidor(MagicMock())
    from autoclave.backend import server_reasignacion as sr
    datos = json.dumps({"formato": aio.FORMATO, "cambios": {RETIRADA: 25, "vapor_camara": 26}})
    with caplog.at_level(logging.WARNING):
        cambios = sr.validar_respaldo(datos.encode("utf-8"))
    assert cambios == {"vapor_camara": 26}
    assert any(RETIRADA in r.getMessage() for r in caplog.records
               if r.levelno == logging.WARNING)


def test_la_api_de_reasignacion_no_acepta_la_retirada():
    """Por la API (cambio nuevo) no se ofrece: combinar la rechaza."""
    with pytest.raises(aio.ErrorAsignacion):
        aio.combinar(aio.fabrica_codigo(), {RETIRADA: 25})

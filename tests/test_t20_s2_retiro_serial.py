# tests/test_t20_s2_retiro_serial.py
#
# Tanda 20 (T20-03): retiro del enlace serial (ESP32). Comprueba que no quedan
# los módulos, archivos, la dependencia pyserial ni el firmware, que el único
# enlace es Modbus (build_enlace, asignación de E/S, /status, calibración) y
# que lo que se decidió conservar sigue ahí (alarmas solo-serial en el
# catálogo, segunda barrera de MOD-12, tolerancia de DI vencida).

import ast
import importlib.util
import re
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

RAIZ = Path(__file__).resolve().parents[1]
SRC = RAIZ / "src" / "autoclave"
pytestmark = pytest.mark.req("T20-03")


# ── retirado ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("modulo", [
    "autoclave.protocols.serial_link",
    "autoclave.protocols.serial_link_config",
    "autoclave.protocols.crc16",
    "autoclave.protocols.device_reset",
    "autoclave.config.enlace_io",
])
def test_modulos_retirados_no_existen(modulo):
    assert importlib.util.find_spec(modulo) is None


@pytest.mark.parametrize("ruta", [
    "src/autoclave/protocols/serial_link.py",
    "src/autoclave/protocols/serial_link_config.py",
    "src/autoclave/protocols/crc16.py",
    "src/autoclave/protocols/device_reset.py",
    "src/autoclave/config/serial_link.json",
    "src/autoclave/config/enlace_io.py",
    "src/autoclave/config/enlace_io.json",
    "src/autoclave/config/calibration.yaml",
    "src/autoclave/config/plantillas/calibration_neutra.yaml",
    "tools/log_calibracion_sensores.py",
    "tests/helpers/serial_doble.py",
    "Hardware/Comunicacion_esclava_ESP32_V2",
    "Hardware/Comunicacion_esclava_ESP32_V3",
])
def test_archivos_retirados_no_existen(ruta):
    assert not (RAIZ / ruta).exists()


def test_pyserial_no_figura_en_las_dependencias():
    texto = (RAIZ / "pyproject.toml").read_text(encoding="utf-8")
    deps = texto[texto.index("dependencies = ["):]
    deps = deps[:deps.index("]")]
    assert "pyserial" not in deps.lower()
    lock = (RAIZ / "requirements.lock.txt").read_text(encoding="utf-8")
    assert not [l for l in lock.splitlines() if re.match(r"(?i)^pyserial\s*==", l)]


def _importa_pyserial(ruta: Path) -> bool:
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import) and any(
                a.name == "serial" or a.name.startswith("serial.") for a in nodo.names):
            return True
        if isinstance(nodo, ast.ImportFrom) and nodo.level == 0 and nodo.module and (
                nodo.module == "serial" or nodo.module.startswith("serial.")):
            return True
    return False


def test_ningun_archivo_de_src_importa_pyserial():
    malos = [str(p.relative_to(RAIZ)) for p in SRC.rglob("*.py") if _importa_pyserial(p)]
    assert malos == []


def test_ningun_archivo_de_src_importa_los_modulos_retirados():
    patron = re.compile(r"(serial_link|enlace_io|crc16|device_reset)\b")
    malos = []
    for p in SRC.rglob("*.py"):
        for nodo in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            nombres = []
            if isinstance(nodo, ast.Import):
                nombres = [a.name for a in nodo.names]
            elif isinstance(nodo, ast.ImportFrom) and nodo.module:
                nombres = [nodo.module] + [f"{nodo.module}.{a.name}" for a in nodo.names]
            if any(patron.search(n) for n in nombres if n.startswith("autoclave")):
                malos.append(str(p.relative_to(RAIZ)))
    assert malos == []


def test_el_spec_ya_no_empaqueta_la_calibracion_serial():
    spec = (RAIZ / "packaging" / "Autoclave.spec").read_text(encoding="utf-8")
    assert "calibration_neutra" not in spec
    assert "autoclave/config/calibration.yaml" not in spec


def test_el_backend_importa_sin_los_modulos_retirados():
    codigo = ("import sys; sys.path.insert(0, 'src');"
              "import autoclave.backend.server, autoclave.devices.factory.factory;"
              "print([m for m in sys.modules if m.startswith(('autoclave.protocols.serial_link',"
              " 'autoclave.config.enlace_io', 'autoclave.protocols.crc16',"
              " 'autoclave.protocols.device_reset'))])")
    r = subprocess.run([sys.executable, "-I", "-c", codigo], cwd=RAIZ,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-800:]
    assert r.stdout.strip().splitlines()[-1] == "[]"


# ── enlace único Modbus ────────────────────────────────────────────────────

def test_build_enlace_construye_modbus_link_sin_red():
    from autoclave.devices.factory import factory
    units = MagicMock()
    with patch("autoclave.protocols.modbus_link.ModbusLink") as cls:
        enlace = factory.build_enlace(units, al_conectar="cb")
    assert enlace is cls.return_value
    assert enlace.al_conectar == "cb"
    enlace.start.assert_called_once_with()
    assert not hasattr(factory, "build_serial")


def test_asignacion_io_enlace_y_puertos_modbus():
    from autoclave.core.runtime import asignacion_io as aio
    assert aio.enlace() == "modbus"
    assert aio.puertos() == {"DI": range(1, 17), "DO": range(1, 33),
                             "AI_TEMP": range(1, 7), "AI_PRES": range(9, 17)}
    for alias in ("PUERTOS_DI", "PUERTOS_DO", "PUERTOS_AI_TEMP", "PUERTOS_AI_PRES",
                  "_PUERTOS_SERIAL"):
        assert not hasattr(aio, alias)
    assert 17 not in aio.puertos_validos("DI")


def test_puertos_devuelve_una_copia():
    from autoclave.core.runtime import asignacion_io as aio
    p = aio.puertos()
    p["DI"] = range(1, 49)
    assert aio.puertos()["DI"] == range(1, 17)


def test_calibration_path_es_la_de_modbus():
    from autoclave.utils import paths
    assert paths.calibration_path().name == "calibration_modbus.yaml"
    assert not hasattr(paths, "CALIBRACION_SERIAL")
    assert not hasattr(paths, "nombre_calibracion")


def test_status_publica_enlace_modbus():
    from fastapi.testclient import TestClient
    from tests.helpers.backend_doble import cargar_servidor
    ctx = MagicMock()
    ctx.estado.estado_puertas = {}
    ctx.estado.sensores_temp = {}
    ctx.estado.sensores_pres = {}
    ctx.estado.sensores_di = {}
    ctx.estado.salidas_do = {}
    ctx.estado.flags = {}
    ctx.estado.Alarmas_activas = []
    ctx.serial.get_diagnostico.return_value = {"lineas_invalidas_total": 0}
    ctx.serial.tarjeta.return_value = {"version": None, "protocolo": None, "id": None}
    srv, _ = cargar_servidor(ctx)
    assert TestClient(srv.app).get("/status").json()["enlace_io"] == "modbus"


# ── conversión sin la escala del ADC serial ───────────────────────────────

def test_sin_calibracion_de_fabrica_no_hay_lectura():
    """Antes, en serial, raw/4095*escala; ahora sin calibración no hay valor."""
    from autoclave.hal.measures import converters
    assert not hasattr(converters, "ADC_MAXIMO")
    converters.reiniciar_presiones()
    for i in range(8):
        converters._ma_temp[i].buffer.clear()
        converters._oe_temp[i].reset()
    assert converters.convert_temperatures([1210] + [None] * 15, {})[0] is None
    assert converters.convert_pressures([None] * 8 + [12000] + [None] * 7, {})[0] is None
    converters.reiniciar_presiones()


def test_umbral_alto_de_lazo_siempre_activo():
    """El tope del ADC de 12 bits (umbral alto inactivo si >= 4095) se retiró."""
    from types import SimpleNamespace
    from autoclave.hal.measures import converters
    calib = SimpleNamespace(adc_min=5, adc_max=4050)
    bajo, alto = converters.umbrales_falla_presion(calib)
    assert alto == pytest.approx(4050 + 0.0625 * 4045)


# ── lo que se conserva ─────────────────────────────────────────────────────

def test_alarmas_solo_serial_siguen_en_el_catalogo_para_el_historial():
    from autoclave.protocols import enlace
    from autoclave.state_machine.alarms.catalogo import CATALOGO, CODIGOS_TARJETA
    assert set(enlace.ALARMAS_SOLO_SERIAL) == {
        "TARJETA_SIN_ACK", "TARJETA_ALL_OFF_SIN_CONFIRMAR", "TARJETA_REINICIO"}
    for codigo in enlace.ALARMAS_SOLO_SERIAL:
        assert codigo in CATALOGO and codigo in CODIGOS_TARJETA
    assert set(enlace.ALARMAS_HANDSHAKE) | set(enlace.ALARMAS_OPERACION) <= set(CODIGOS_TARJETA)


def test_segunda_barrera_de_mod_12_se_conserva():
    from autoclave.services.domain.loop import control_loop
    assert control_loop._ALARMAS_PIDEN_HANDSHAKE == {
        "TARJETA_EXPANSOR_FUERA_DE_LINEA", "DISCREPANCIA_SALIDAS",
        "TARJETA_MODULOS_ORDEN", "TARJETA_CONFIG_SEGURIDAD"}


def test_tolerancia_di_vencida_sin_cambio_hasta_decision():
    """Se justificaba con el watchdog del firmware V3 (retirado); el valor no
    cambia hasta que Cristian lo revise con Modbus (anomalía de la tanda 20)."""
    from autoclave.state_machine.states import ciclo
    assert ciclo._TOLERANCIA_DI_VENCIDA_SEG == 4.0


def test_textos_de_accion_dicen_cable_de_red():
    from autoclave.state_machine.alarms.catalogo import CATALOGO
    for codigo in ("COM-01", "COM-02", "CIC-11", "TARJETA_SIN_TRAMA_VALIDA"):
        accion = CATALOGO[codigo].accion
        assert "cable de red" in accion and "USB" not in accion, codigo


def test_verificador_falla_si_la_compilacion_trae_la_calibracion_serial(tmp_path):
    destino = tmp_path / "Autoclave" / "_internal" / "autoclave" / "config"
    destino.mkdir(parents=True)
    (destino / "calibration_modbus.yaml").write_bytes(
        (SRC / "config" / "calibration_modbus.yaml").read_bytes())
    verificador = RAIZ / "tools" / "verificar_calibracion_neutra.py"
    r = subprocess.run([sys.executable, str(verificador), str(tmp_path / "Autoclave")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    (destino / "calibration.yaml").write_text("calibration: {}\n", encoding="utf-8")
    r = subprocess.run([sys.executable, str(verificador), str(tmp_path / "Autoclave")],
                       capture_output=True, text=True)
    assert r.returncode == 1 and "FALLA" in r.stdout

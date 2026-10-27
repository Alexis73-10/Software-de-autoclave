"""D8-3.18 (tanda 8, K8): la entrega lleva una calibración NEUTRA, no los valores
del banco. `tools/verificar_calibracion_neutra.py` falla si la compilación no la
trae.

Tanda 20 (T20-03): la calibración serial (`config/calibration.yaml`) y su
plantilla neutra (`config/plantillas/calibration_neutra.yaml`) se retiraron con
el enlace serial; se borraron las pruebas de esa plantilla, de su empaquetado y
del verificador con ella. La calibración Modbus neutra la cubren
test_t19_s2_calibracion.py, test_t19_r2_verificador.py y
test_t20_s2_retiro_serial.py."""
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
VERIFICADOR = RAIZ / "tools" / "verificar_calibracion_neutra.py"


def _verificar(dist):
    return subprocess.run([sys.executable, str(VERIFICADOR), str(dist)],
                          capture_output=True, text=True)


def test_verificador_rechaza_si_falta(tmp_path):
    (tmp_path / "Autoclave").mkdir()
    r = _verificar(tmp_path / "Autoclave")
    assert r.returncode != 0

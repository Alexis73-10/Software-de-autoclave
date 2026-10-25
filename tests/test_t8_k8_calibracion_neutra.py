"""D8-3.18 (tanda 8, K8): la entrega lleva una calibración NEUTRA, no los valores
del banco. El .spec empaqueta `config/plantillas/calibration_neutra.yaml` como
`autoclave/config/calibration.yaml`, y `tools/verificar_calibracion_neutra.py`
falla si el archivo empaquetado no es igual a la plantilla."""
import subprocess
import sys
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[1]
CONFIG = RAIZ / "src" / "autoclave" / "config"
PLANTILLA = CONFIG / "plantillas" / "calibration_neutra.yaml"
VERIFICADOR = RAIZ / "tools" / "verificar_calibracion_neutra.py"


def _cargar(ruta):
    return yaml.safe_load(ruta.read_text(encoding="utf-8"))


def test_plantilla_usuario_neutra():
    """Calibración de usuario: ganancia 1.0 y offset 0.0 en todos los sensores
    (lo mismo que "Restaurar por defecto")."""
    user = _cargar(PLANTILLA)["calibration"]["user"]
    for tipo in ("temperature", "pressure"):
        assert len(user[tipo]) == 8
        for s in user[tipo]:
            assert s == {"gain": 1.0, "offset": 0.0}


def test_plantilla_fabrica_igual_a_la_del_repositorio():
    """La calibración de fábrica (escala ADC de cada canal, de la que dependen la
    conversión y la detección NAMUR de D8-1) no cambia: es la del repositorio."""
    neutra = _cargar(PLANTILLA)
    repo = _cargar(CONFIG / "calibration.yaml")
    assert neutra["calibration"]["factory"] == repo["calibration"]["factory"]
    for clave in repo:
        if clave != "calibration":
            assert neutra[clave] == repo[clave]


def test_plantilla_valida_con_el_esquema():
    from autoclave.config import load_config
    cfg = load_config(str(PLANTILLA))
    assert all(s.gain == 1.0 and s.offset == 0.0 for s in cfg.calibration.user.pressure)


def test_spec_empaqueta_la_plantilla():
    spec = (RAIZ / "packaging" / "Autoclave.spec").read_text(encoding="utf-8")
    assert "plantillas/calibration_neutra.yaml" in spec


def _verificar(dist):
    return subprocess.run([sys.executable, str(VERIFICADOR), str(dist)],
                          capture_output=True, text=True)


def _dist_falso(tmp_path, contenido):
    destino = tmp_path / "Autoclave" / "_internal" / "autoclave" / "config"
    destino.mkdir(parents=True)
    (destino / "calibration.yaml").write_bytes(contenido)
    return tmp_path / "Autoclave"


def test_verificador_acepta_la_plantilla(tmp_path):
    r = _verificar(_dist_falso(tmp_path, PLANTILLA.read_bytes()))
    assert r.returncode == 0, r.stdout + r.stderr


def test_verificador_rechaza_la_calibracion_de_banco(tmp_path):
    r = _verificar(_dist_falso(tmp_path, (CONFIG / "calibration.yaml").read_bytes()))
    assert r.returncode != 0


def test_verificador_rechaza_si_falta(tmp_path):
    (tmp_path / "Autoclave").mkdir()
    r = _verificar(tmp_path / "Autoclave")
    assert r.returncode != 0

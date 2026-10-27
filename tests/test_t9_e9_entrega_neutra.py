"""D9-7 (tanda 9, E9): la entrega no lleva datos precargados del banco.

- `config/correo.json` empaquetado = plantilla neutra (sin remitente ni
  destinatarios);
- de `cycles/` solo va `cycles/factory/` (ni `user/` ni `defecto/`);
- `tools/verificar_entrega_neutra.py <dist>` falla (salida 1) si algo de eso no
  se cumple, y también si la calibración no es la neutra (D8-3.18)."""
import json
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CONFIG = RAIZ / "src" / "autoclave" / "config"
CICLOS = RAIZ / "src" / "autoclave" / "cycles"
CORREO_NEUTRO = CONFIG / "plantillas" / "correo_neutro.json"
CALIB_NEUTRA = CONFIG / "plantillas" / "calibration_neutra.yaml"
VERIFICADOR = RAIZ / "tools" / "verificar_entrega_neutra.py"
SPECS = ("Autoclave.spec", "AutoclaveBackend.spec", "AutoclaveSettings.spec")


# ── plantilla de correo ──────────────────────────────────────────────────────

def test_plantilla_correo_sin_remitente_ni_destinatarios():
    datos = json.loads(CORREO_NEUTRO.read_text(encoding="utf-8"))
    assert datos["remitente"] == ""
    assert datos["destinos"] == []
    assert "@" not in CORREO_NEUTRO.read_text(encoding="utf-8")   # ninguna dirección


def test_plantilla_correo_se_lee_como_sin_configurar(tmp_path):
    from autoclave.ui_qml.exportacion import config_correo
    cfg = config_correo.cargar(CORREO_NEUTRO, contrasena=lambda r: "x",
                               ruta_equipo=tmp_path / "no_existe.json")
    assert cfg.remitente == "" and cfg.destinos == []
    assert not cfg.configurado


# ── .spec ────────────────────────────────────────────────────────────────────

def test_specs_solo_empaquetan_cycles_factory():
    for nombre in SPECS:
        spec = (RAIZ / "packaging" / nombre).read_text(encoding="utf-8")
        assert "('src/autoclave/cycles/factory', 'autoclave/cycles/factory')" in spec, nombre
        assert "('src/autoclave/cycles', 'autoclave/cycles')" not in spec, nombre


def test_specs_empaquetan_el_correo_neutro_y_vigilan_ciclos():
    for nombre in SPECS:
        spec = (RAIZ / "packaging" / nombre).read_text(encoding="utf-8")
        assert "plantillas/correo_neutro.json" in spec, nombre
        # el propio build falla si se cuela algo de cycles/ que no sea factory
        assert "autoclave/cycles/factory/" in spec and "SystemExit" in spec, nombre


# ── verificador ──────────────────────────────────────────────────────────────

def _verificar(dist):
    return subprocess.run([sys.executable, str(VERIFICADOR), str(dist)],
                          capture_output=True, text=True)


def _dist(tmp_path, correo=None, calib=None, extra_ciclos=(), sin_fabrica=False):
    raiz = tmp_path / "Autoclave"
    interno = raiz / "_internal" / "autoclave"
    (interno / "config").mkdir(parents=True)
    if correo is not False:
        (interno / "config" / "correo.json").write_bytes(
            correo if correo is not None else CORREO_NEUTRO.read_bytes())
    (interno / "config" / "calibration.yaml").write_bytes(
        calib if calib is not None else CALIB_NEUTRA.read_bytes())
    # Revisión R de la tanda 19 (V19-s2-01): el compilado real lleva también
    # la calibración del enlace Modbus y el verificador falla si falta.
    (interno / "config" / "calibration_modbus.yaml").write_bytes(
        (CONFIG / "calibration_modbus.yaml").read_bytes())
    fab = interno / "cycles" / "factory"
    fab.mkdir(parents=True)
    if not sin_fabrica:
        for f in (CICLOS / "factory").glob("*.json"):
            (fab / f.name).write_bytes(f.read_bytes())
    for rel in extra_ciclos:
        destino = interno / "cycles" / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text("{}", encoding="utf-8")
    return raiz


def test_verificador_acepta_entrega_neutra(tmp_path):
    r = _verificar(_dist(tmp_path))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "OK" in r.stdout


def test_verificador_rechaza_correo_del_banco(tmp_path):
    r = _verificar(_dist(tmp_path, correo=(CONFIG / "correo.json").read_bytes()))
    assert r.returncode == 1 and "correo" in r.stdout


def test_verificador_rechaza_correo_con_destinatario_aunque_no_tenga_remitente(tmp_path):
    datos = json.loads(CORREO_NEUTRO.read_text(encoding="utf-8"))
    datos["destinos"] = [{"nombre": "X", "correo": "x@ejemplo.com"}]
    r = _verificar(_dist(tmp_path, correo=json.dumps(datos).encode("utf-8")))
    assert r.returncode == 1


def test_verificador_rechaza_si_falta_el_correo(tmp_path):
    assert _verificar(_dist(tmp_path, correo=False)).returncode == 1


def test_verificador_rechaza_cycles_user(tmp_path):
    r = _verificar(_dist(tmp_path, extra_ciclos=("user/bowe_dick.json",)))
    assert r.returncode == 1 and "user" in r.stdout


def test_verificador_rechaza_cycles_defecto(tmp_path):
    assert _verificar(_dist(tmp_path, extra_ciclos=("defecto/1.json",))).returncode == 1


def test_verificador_rechaza_archivo_suelto_en_cycles(tmp_path):
    assert _verificar(_dist(tmp_path, extra_ciclos=("suelto.json",))).returncode == 1


def test_verificador_rechaza_sin_programas_de_fabrica(tmp_path):
    assert _verificar(_dist(tmp_path, sin_fabrica=True)).returncode == 1


def test_verificador_rechaza_calibracion_de_banco(tmp_path):
    r = _verificar(_dist(tmp_path, calib=(CONFIG / "calibration.yaml").read_bytes()))
    assert r.returncode == 1


def test_verificador_sin_argumentos_sale_con_2():
    r = subprocess.run([sys.executable, str(VERIFICADOR)], capture_output=True, text=True)
    assert r.returncode == 2

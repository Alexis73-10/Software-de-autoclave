"""Instalación por automatización: K_t (transporte) en secretos.py, empaquetado y guardas contra el K_t de prueba."""
import json
import sys
from pathlib import Path

import pytest

from autoclave.installation import secretos
from tests.helpers.codigo_doble import K_T_PRUEBA

RAIZ = Path(__file__).resolve().parents[1]
SPECS = ("Autoclave.spec", "AutoclaveBackend.spec", "AutoclaveSettings.spec")
K_T_REAL = bytes(range(1, 33))


def _archivo(ruta: Path, k_t: bytes = K_T_REAL, version=2, **extra) -> Path:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps({"version": version, "transporte": k_t.hex(), "huella_maestro": "0a1b2c3d", **extra}),
                    encoding="utf-8")
    return ruta


@pytest.fixture
def sin_archivo(monkeypatch, tmp_path):
    monkeypatch.setenv(secretos.VARIABLE_ENTORNO_TRANSPORTE, str(tmp_path / "nada" / "activacion_v2.json"))
    return tmp_path


# ── lectura ───────────────────────────────────────────────────────────────────────────────────────────

def test_el_k_t_de_prueba_coincide_con_la_especificacion():
    assert K_T_PRUEBA.hex() == secretos.K_T_DE_PRUEBA_HEX
    assert secretos.es_transporte_de_prueba(K_T_PRUEBA) and not secretos.es_transporte_de_prueba(K_T_REAL)


def test_leer_transporte_devuelve_32_bytes(tmp_path):
    assert secretos.leer_transporte(_archivo(tmp_path / "t.json")) == K_T_REAL


@pytest.mark.parametrize("mutar", [
    lambda d: d.update(version=1),
    lambda d: d.update(transporte="ab" * 31),
    lambda d: d.update(transporte="zz" * 32),
    lambda d: d.update(transporte=123),
    lambda d: d.pop("transporte"),
])
def test_leer_transporte_rechaza_formatos_invalidos(tmp_path, mutar):
    datos = {"version": 2, "transporte": K_T_REAL.hex()}
    mutar(datos)
    ruta = tmp_path / "t.json"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    with pytest.raises(secretos.SecretosInvalidos) as e:
        secretos.leer_transporte(ruta)
    assert K_T_REAL.hex() not in str(e.value)


def test_leer_transporte_sin_archivo_o_no_json(tmp_path):
    with pytest.raises(secretos.SecretosInvalidos):
        secretos.leer_transporte(tmp_path / "no.json")
    malo = tmp_path / "malo.json"
    malo.write_text("{no es json", encoding="utf-8")
    with pytest.raises(secretos.SecretosInvalidos):
        secretos.leer_transporte(malo)


def test_ruta_por_defecto_y_variable_de_entorno(monkeypatch, tmp_path):
    monkeypatch.delenv(secretos.VARIABLE_ENTORNO_TRANSPORTE, raising=False)
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    assert secretos.ruta_archivo_transporte() == tmp_path / "Documents" / "especifika_secretos" / "activacion_v2.json"
    monkeypatch.setenv(secretos.VARIABLE_ENTORNO_TRANSPORTE, str(tmp_path / "otra.json"))
    assert secretos.ruta_archivo_transporte() == tmp_path / "otra.json"


def test_el_v1_no_cambia():
    assert secretos.RECURSO_EMPAQUETADO == "config/activacion_secretos.json"
    assert secretos.RECURSO_TRANSPORTE == "config/activacion_transporte.json"
    assert secretos.CLAVES == ("instalacion", "fabrica") and secretos.VERSION == 1


# ── guardas contra el K_t de prueba y el archivo ausente (compilación) ────────────────────────────────

def test_entrada_de_compilacion_con_k_t_real(monkeypatch, tmp_path, capsys):
    ruta = _archivo(tmp_path / "t.json")
    monkeypatch.setenv(secretos.VARIABLE_ENTORNO_TRANSPORTE, str(ruta))
    assert secretos.entrada_compilacion_transporte() == ("config/activacion_transporte.json", str(ruta), "DATA")
    salida = capsys.readouterr().out
    assert secretos.huella(K_T_REAL) in salida and K_T_REAL.hex() not in salida


def test_entrada_de_compilacion_se_niega_con_el_k_t_de_prueba(monkeypatch, tmp_path):
    monkeypatch.setenv(secretos.VARIABLE_ENTORNO_TRANSPORTE, str(_archivo(tmp_path / "t.json", K_T_PRUEBA)))
    with pytest.raises(SystemExit) as e:
        secretos.entrada_compilacion_transporte()
    assert "prueba" in str(e.value)


def test_entrada_de_compilacion_se_niega_sin_archivo(sin_archivo):
    with pytest.raises(SystemExit) as e:
        secretos.entrada_compilacion_transporte()
    assert "transporte" in str(e.value)


# ── los 3 .spec empaquetan el K_t ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("nombre", SPECS)
def test_los_specs_empaquetan_el_transporte_junto_a_los_secretos_v1(nombre):
    spec = (RAIZ / "packaging" / nombre).read_text(encoding="utf-8")
    assert "a.datas.append(entrada_compilacion_transporte())" in spec
    assert "from autoclave.installation.secretos import" in spec and "entrada_compilacion_transporte" in spec
    # ordenado antes de PYZ para que viaje en a.datas
    assert spec.index("entrada_compilacion_transporte())") < spec.index("pyz = PYZ(a.pure)")
    if nombre != "AutoclaveSettings.spec":
        assert "a.datas.append(entrada_compilacion())" in spec           # el v1 sigue igual


# ── tools/verificar_entrega_neutra.py ─────────────────────────────────────────────────────────────────

@pytest.fixture
def verificador():
    sys.path.insert(0, str(RAIZ / "tools"))
    try:
        import verificar_entrega_neutra as m
        yield m
    finally:
        sys.path.remove(str(RAIZ / "tools"))


def _dist(tmp_path, k_t=K_T_REAL):
    dist = tmp_path / "Autoclave"
    if k_t is not None:
        _archivo(dist / "_internal" / "config" / "activacion_transporte.json", k_t)
    else:
        (dist / "_internal" / "config").mkdir(parents=True)
    return dist


def test_verificador_acepta_un_transporte_real(verificador, tmp_path):
    assert verificador.fallas_transporte(_dist(tmp_path)) == []


def test_verificador_falla_si_falta_el_transporte(verificador, tmp_path):
    fallas = verificador.fallas_transporte(_dist(tmp_path, None))
    assert len(fallas) == 1 and "transporte" in fallas[0]


def test_verificador_falla_si_es_el_k_t_de_prueba(verificador, tmp_path):
    fallas = verificador.fallas_transporte(_dist(tmp_path, K_T_PRUEBA))
    assert len(fallas) == 1 and "prueba" in fallas[0]


def test_verificador_falla_si_esta_corrupto(verificador, tmp_path):
    dist = _dist(tmp_path)
    (dist / "_internal" / "config" / "activacion_transporte.json").write_text("{", encoding="utf-8")
    assert len(verificador.fallas_transporte(dist)) == 1


def test_main_del_verificador_incluye_la_guarda_del_transporte():
    fuente = (RAIZ / "tools" / "verificar_entrega_neutra.py").read_text(encoding="utf-8")
    assert "fallas_transporte(dist)" in fuente

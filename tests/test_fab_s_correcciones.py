# tests/test_fab_s_correcciones.py
#
# Correcciones de la revisión de seguridad del modo fábrica
# (docs/informes/modo_fabrica/S_revision_seguridad.md): SAF-02 (texto en
# pantalla del fallo bloqueante ARR_CIERRE_FABRICA), SAF-04 (v1 no es primera
# instalación; evidencia de ENTREGADO fuera de la base), SAF-07 (paquete de
# liberación rechazado por contenido y nombre) y SAF-08 (polinomio plausible).

import io
import json
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import pytest
import yaml

from autoclave.core.runtime import fabrica_equipo as fe
from autoclave.core.runtime import paquete_liberacion as pl
from autoclave.core.runtime import respaldo as rp
from autoclave.installation.activacion_v2 import ResultadoCodigo
from autoclave.services.domain.logging.db_manager import DbManager
from tests.helpers import codigo_doble
from tests.test_o2h_respaldo import EQUIPO, api  # noqa: F401  (fixture)

RAIZ = Path(__file__).resolve().parents[1]
SRC = RAIZ / "src" / "autoclave"


# ── SAF-02: texto en pantalla ────────────────────────────────────────────
@pytest.mark.req("SAF-02")
def test_saf02_textos_es_en():
    for idioma, frase in (("es", "Cierre de fabricación incompleto"),
                          ("en", "Factory closing incomplete")):
        t = json.loads((SRC / "i18n" / f"{idioma}.json").read_text(encoding="utf-8"))
        assert t["arranque"]["cierre_fabrica_incompleto"].startswith(frase)
        assert "Especifika" in t["arranque"]["cierre_fabrica_incompleto"]
        assert t["aviso_detalle"]["arranque"]["accion_cierre_fabrica"]
    es = json.loads((SRC / "i18n" / "es.json").read_text(encoding="utf-8"))
    assert es["arranque"]["cierre_fabrica_incompleto"] == (
        "Cierre de fabricación incompleto: reinicie el equipo; si persiste, contacte a Especifika")


@pytest.mark.req("SAF-02")
def test_saf02_codigo_fallo_de_la_instantanea():
    pytest.importorskip("PySide6")
    from autoclave.ui_qml.bridge.progreso_arranque import codigo_fallo
    inst = {"falloBloqueante": True, "etapas": [
        {"clave": "verificando_instalacion", "estado": "fallo", "codigo": "ARR_CIERRE_FABRICA"}]}
    assert codigo_fallo(inst) == "ARR_CIERRE_FABRICA"
    assert codigo_fallo({**inst, "falloBloqueante": False}) == ""
    assert codigo_fallo(None) == "" and codigo_fallo({"falloBloqueante": True}) == ""


@pytest.mark.req("SAF-02")
def test_saf02_detalle_aviso_del_arranque():
    from autoclave.ui_qml.domain import detalle_aviso as da
    fila = da.armar("arranque", {"arranque": {"codigo": "ARR_CIERRE_FABRICA"}})
    assert "Cierre de fabricación incompleto" in json.dumps(fila, ensure_ascii=False)
    otra = da.armar("arranque", {"arranque": {"codigo": "ARR_PERFIL"}})
    assert "Cierre de fabricación" not in json.dumps(otra, ensure_ascii=False)


@pytest.mark.req("SAF-02")
def test_saf02_main_qml_usa_el_codigo():
    texto = (SRC / "ui_qml" / "qml" / "Main.qml").read_text(encoding="utf-8")
    assert '"ARR_CIERRE_FABRICA"' in texto and "arranque.cierre_fabrica_incompleto" in texto
    assert "codigoFallo" in texto


# ── SAF-04 ───────────────────────────────────────────────────────────────
@pytest.fixture
def pi(monkeypatch, tmp_path):
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    from autoclave.installation import storage
    from autoclave.ui_qml.bridge import puente_instalacion as modulo
    monkeypatch.setattr(storage, "INSTALLATION_FILE", tmp_path / "installation_profile.json")
    return modulo


def _perfil():
    from unittest.mock import MagicMock
    return MagicMock(serial_number="SN260001", model_id="M", tipo_instalacion="fabricacion",
                     serial_original=None, modelo_original=None)


@pytest.mark.req("SAF-04")
def test_saf04_v1_no_es_primera_instalacion(pi):
    assert pi.es_primera_instalacion(ResultadoCodigo(ok=True, formato="v1")) is False
    assert pi.es_primera_instalacion(ResultadoCodigo(ok=True, formato="v2", tipo="INS")) is True


@pytest.mark.req("SAF-04")
@pytest.mark.parametrize("nombre", [fe.NOMBRE_PARAMETROS, fe.NOMBRE_CALIBRACION])
def test_saf04_evidencia_de_entregado_no_entra_en_fabrica(pi, tmp_path, nombre):
    datos = tmp_path / "data"
    datos.mkdir()
    (datos / nombre).write_text("{}", encoding="utf-8")
    ruta = datos / "autoclave.db"            # base vacía (perdida en campo)
    estado = pi.registrar_equipo_instalado(_perfil(), abrir_bd=lambda: DbManager(ruta),
                                           zona=lambda: "Z", primera_instalacion=True)
    assert estado == "ENTREGADO"
    db = DbManager(ruta)
    try:
        assert db.estado_fabrica() == "ENTREGADO"
        assert [f["evento"] for f in db.get_auditoria(limite=10)] == ["equipo_instalado"]
    finally:
        db.close()


@pytest.mark.req("SAF-04")
def test_saf04_sin_evidencia_entra_en_fabrica(pi, tmp_path):
    datos = tmp_path / "data"
    datos.mkdir()
    (datos / (fe.NOMBRE_PARAMETROS + ".fab_nuevo")).write_text("{}", encoding="utf-8")
    ruta = datos / "autoclave.db"
    assert pi.registrar_equipo_instalado(_perfil(), abrir_bd=lambda: DbManager(ruta),
                                         zona=lambda: "Z", primera_instalacion=True) == "FABRICA"


@pytest.mark.req("SAF-04")
def test_saf04_error_al_buscar_evidencia_es_entregado(pi, monkeypatch):
    def falla(*_a, **_k):
        raise OSError("x")
    monkeypatch.setattr(Path, "exists", falla)
    assert pi.hay_evidencia_entregado("C:/no") is True


@pytest.mark.req("SAF-04")
def test_saf04_asistente_completo_con_evidencia(pi, tmp_path):
    from tests.test_fab_e1_asistente import _datos
    (tmp_path / fe.NOMBRE_CALIBRACION).write_text("formato: 1\n", encoding="utf-8")
    ruta = tmp_path / "autoclave.db"
    p = pi.PuenteInstalacion(verificar_codigo=codigo_doble.acepta(tipo="INS"),
                             abrir_bd=lambda: DbManager(ruta), es_semilla=lambda _c: False)
    assert p.validarCodigo("ab-123", "X", "fabricacion", "", "") == ""
    assert p.instalar(_datos()) == {"ok": True, "error": ""}
    db = DbManager(ruta)
    try:
        assert db.estado_fabrica() == "ENTREGADO"
    finally:
        db.close()


# ── SAF-07 ───────────────────────────────────────────────────────────────
def _respaldo_con(usb, extra: dict, nombre="respaldo_ACV-2026-001_20261122_100000.zip"):
    """Respaldo válido de EQUIPO (manifiesto «respaldo» bien sellado) con
    archivos extra fuera del manifiesto."""
    datos = rp.crear(EQUIPO, {"parametros_programas": True},
                     {"parametros.json": b'{"timeout_puerta": 90}'}, "tec", "1.2.0")
    with zipfile.ZipFile(io.BytesIO(datos)) as z:
        archivos = {n: z.read(n) for n in z.namelist()}
    archivos.update(extra)
    carpeta = usb / rp.CARPETA
    carpeta.mkdir(exist_ok=True)
    ruta = carpeta / nombre
    with zipfile.ZipFile(ruta, "w") as z:
        for n, d in archivos.items():
            z.writestr(n, d)
    return ruta


@pytest.mark.req("SAF-07")
@pytest.mark.parametrize("extra", [{"informe_liberacion.pdf": b"%PDF"},
                                   {"bitacora.csv": b"x"},
                                   {"ciclos/ciclo_000001_1.pdf": b"%PDF"}])
def test_saf07_contenido_de_liberacion_se_rechaza(tmp_path, extra):
    ruta = _respaldo_con(tmp_path, extra)
    with pytest.raises(rp.ErrorRespaldo) as e:
        rp.leer(ruta)
    assert e.value.codigo == "paquete_no_restaurable"
    assert rp.resumen(ruta, EQUIPO, "1.2.0")["motivo"] == "paquete_no_restaurable"


@pytest.mark.req("SAF-07")
def test_saf07_nombre_de_liberacion_se_rechaza(tmp_path):
    ruta = _respaldo_con(tmp_path, {}, nombre="liberacion_SN260001_20261122-1000.zip")
    with pytest.raises(rp.ErrorRespaldo) as e:
        rp.leer(ruta)
    assert e.value.codigo == "paquete_no_restaurable"
    with pytest.raises(rp.ErrorRespaldo) as e:
        rp.ruta_respaldo_segura(str(tmp_path), "liberacion_SN260001_20261122-1000.zip")
    assert e.value.codigo == "paquete_no_restaurable"


@pytest.mark.req("SAF-07")
def test_saf07_respaldo_normal_sigue_valido(tmp_path):
    ruta = _respaldo_con(tmp_path, {})
    m, _ = rp.leer(ruta)
    assert rp.validar_para_equipo(m, EQUIPO, "1.2.0") == ""


@pytest.mark.req("SAF-07")
def test_saf07_liberacion_con_tipo_editado_422(api, tmp_path):
    # el paquete de liberación con el manifiesto cambiado a «respaldo» y el
    # hash recalculado sigue sin restaurarse (por contenido)
    client, srv, ctx, cab, usb, programas, calib = api
    otra = tmp_path / "otra_usb"
    otra.mkdir()
    fuentes = pl.FuentesPaquete(copiar_base=pl.copiar_base_desde(ctx.db), equipo=dict(EQUIPO),
                                version_sw="1.2.0", parametros={"timeout_puerta": 90},
                                mapas_sensores={})
    r = pl.generar_paquete_liberacion(fuentes, otra, "ing", datetime(2026, 11, 22, 10, 0))
    with zipfile.ZipFile(r.ruta) as z:
        archivos = {n: z.read(n) for n in z.namelist()}
    m = json.loads(archivos["manifiesto.json"])
    m["tipo"] = "respaldo"
    m["hash"] = rp.hash_manifiesto(m)
    archivos["manifiesto.json"] = json.dumps(m).encode("utf-8")
    carpeta = usb / rp.CARPETA
    carpeta.mkdir(exist_ok=True)
    nombre = "respaldo_ACV-2026-001_20261122_100000.zip"
    with zipfile.ZipFile(carpeta / nombre, "w") as z:
        for n, d in archivos.items():
            z.writestr(n, d)
    h = cab(srv, "ingeniero")
    resp = client.post("/backup/restore", json={"unidad": str(usb), "archivo": nombre,
                                               "confirmar": True}, headers=h)
    assert resp.status_code == 422 and resp.json()["codigo"] == "paquete_no_restaurable"
    assert ctx.config_manager.get("timeout_puerta") == 60


# ── SAF-08 ───────────────────────────────────────────────────────────────
@pytest.fixture
def datos(tmp_path, monkeypatch):
    d = tmp_path / "data"
    d.mkdir()
    monkeypatch.setattr(fe, "carpeta_datos", lambda: d)
    return d


def _guardar(datos, entrada) -> None:
    (datos / fe.NOMBRE_CALIBRACION).write_text(
        yaml.safe_dump({"formato": 1, "pressure": {"pres_camara": entrada}}), encoding="utf-8")


@pytest.mark.req("SAF-08")
@pytest.mark.parametrize("poly", [
    [0.0, 1.01],                 # constante 1,01 kPa
    [1.6, 0.0],                  # 1,6·x: se aparta 210 kPa a 350
    [-1.0, 400.0],               # decreciente
    [0.01, -3.0, 0.0],           # no creciente en el rango
])
def test_saf08_poly_no_plausible_rige_el_neutro(datos, poly):
    _guardar(datos, {"canal": 0, "gain": 1.0, "offset": 0.0, "poly": poly})
    assert fe.entrada_calibracion_equipo("pressure", "pres_camara", 0) is None


@pytest.mark.req("SAF-08")
@pytest.mark.parametrize("poly", [[1.01, 0.0], [0.0, 1.01, 0.0001], [1e-5, 1.0, 0.5]])
def test_saf08_poly_plausible_se_conserva(datos, poly):
    _guardar(datos, {"canal": 0, "gain": 1.0, "offset": 0.0, "poly": poly})
    assert fe.entrada_calibracion_equipo("pressure", "pres_camara", 0)["poly"] == poly


@pytest.mark.req("SAF-08")
def test_saf08_evaluar_polinomio():
    from autoclave.core.managers.catalogo_parametros import evaluar_desviacion_polinomio as ev
    assert ev("pressure", [1.0, 0.0])[0] is None
    assert ev("pressure", [1.0, 100.0])[0] == "aviso"
    assert ev("pressure", [1.0, 130.0])[0] == "rechazo"
    assert ev("temperature", [1.0, 0.0], "temp_camara")[0] is None
    assert ev("otro", [1.0, 0.0])[0] == "rechazo"
    assert ev("pressure", [float("nan"), 0.0])[0] == "rechazo"

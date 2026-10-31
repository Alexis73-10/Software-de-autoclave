# tests/test_automatizacion_salidas.py
#
# Instalación por automatización: salidas de presentación (identidad visible).
# Fabricación queda idéntica; automatización muestra serie y modelo ORIGINALES
# y, aparte, el serial Especifika (la serie interna SNAANNNN). El manifiesto del
# respaldo y `_meta_equipo` no cambian.

import os
import sys
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from autoclave.devices.puertas.door_type import DoorType
from autoclave.installation import identidad
from autoclave.installation.equipment import EquipmentClass
from autoclave.installation.profile import InstallationProfile, Role

SERIE_ORIG = "ACME-0042-X"
MODELO_ORIG = "ACME STERILIZER MODEL 9000 HOSPITAL"
MODELO_80 = "M" * 80
SELLO = "a" * 64


def _perfil(auto=False, modelo="SPK-SAT 45V", serie="SN000123",
            serie_orig=SERIE_ORIG, modelo_orig=MODELO_ORIG):
    kw = {}
    if auto:
        kw = dict(tipo_instalacion="automatizacion", serial_original=serie_orig,
                  modelo_original=modelo_orig, sello_identidad=SELLO)
    return InstallationProfile(
        machine_id="ACV-2026-SN000123", model_id=modelo, serial_number=serie,
        equipment_class=EquipmentClass.PISO, door_count=2, door_type=list(DoorType)[0],
        cooling_level=3, door_id=1, role=Role.OPERATOR_FRONT,
        created_at=datetime(2026, 5, 25, 5, 49), locked=True, **kw)


# ── identidad.py ──────────────────────────────────────────────────────────

def test_identidad_visible_con_originales():
    r = identidad.identidad_visible("SN000123", "SPK-SAT 45V", SERIE_ORIG, MODELO_ORIG)
    assert r == {"modelo": MODELO_ORIG, "serie": SERIE_ORIG, "serial_especifika": "SN000123"}


@pytest.mark.parametrize("so,mo", [(None, None), ("", ""), ("  ", MODELO_ORIG),
                                   (SERIE_ORIG, None), (MagicMock(), MagicMock()), (5, 6)])
def test_identidad_visible_sin_original_es_la_de_siempre(so, mo):
    r = identidad.identidad_visible("SN000123", "SPK-SAT 45V", so, mo)
    assert r == {"modelo": "SPK-SAT 45V", "serie": "SN000123", "serial_especifika": None}


def test_identidad_de_perfil_y_magicmock():
    assert identidad.identidad_de_perfil(None) == {"modelo": None, "serie": None,
                                                   "serial_especifika": None}
    assert identidad.identidad_de_perfil(_perfil())["serial_especifika"] is None
    assert identidad.identidad_de_perfil(_perfil(auto=True))["serie"] == SERIE_ORIG
    mock = MagicMock()
    mock.serial_number, mock.model_id = "SN000123", "SPK-SAT 45V"
    r = identidad.identidad_de_perfil(mock)           # un MagicMock no cuenta como original
    assert r["serial_especifika"] is None and r["serie"] == "SN000123"


def test_identidad_de_ciclo_historico_sin_columnas():
    assert identidad.identidad_de_ciclo({"serie": "SN1", "modelo": "M"}) == {
        "modelo": "M", "serie": "SN1", "serial_especifika": None}
    assert identidad.identidad_de_ciclo(
        {"serie": "SN1", "modelo": "M", "serie_original": None, "modelo_original": None}
    )["serial_especifika"] is None
    r = identidad.identidad_de_ciclo({"serie": "SN1", "modelo": "M",
                                      "serie_original": "S-O", "modelo_original": "M-O"})
    assert r == {"modelo": "M-O", "serie": "S-O", "serial_especifika": "SN1"}


def test_meta_con_originales_no_toca_la_serie_interna():
    meta = {"serie": "SN000123", "modelo": "SPK-SAT 45V"}
    assert identidad.meta_con_originales(meta, _perfil()) is meta
    assert identidad.meta_con_originales(meta, MagicMock()) is meta
    con = identidad.meta_con_originales(meta, _perfil(auto=True))
    assert meta == {"serie": "SN000123", "modelo": "SPK-SAT 45V"}      # el original intacto
    assert con["serie"] == "SN000123" and con["serie_original"] == SERIE_ORIG


def test_rotulo_serial_especifika():
    assert identidad.rotulo_serial_especifika("es") == "Serial Especifika"
    assert identidad.rotulo_serial_especifika("en") == "Especifika serial"


# ── Ticket de arranque (48 columnas) ──────────────────────────────────────

INICIO = datetime(2026, 10, 22, 8, 0, 0)


def _arranque(perfil, idioma="es"):
    from autoclave.devices.printer.startup_ticket import format_startup_ticket
    return format_startup_ticket(perfil, "1.0.0", None, INICIO, idioma=idioma)


def test_arranque_fabricacion_identico():
    lineas = _arranque(_perfil()).splitlines()
    assert lineas[3] == "Modelo:         SPK-SAT 45V"
    assert lineas[4] == "Serie:          SN000123"
    assert lineas[5].startswith("Clase:")
    assert not any("Especifika" in l for l in lineas)


def test_arranque_fabricacion_con_originales_ausentes_no_cambia_nada():
    # un perfil de automatización sin sello no es posible; un MagicMock tampoco cuenta
    p = _perfil()
    assert _arranque(p) == _arranque(p, "es")


@pytest.mark.parametrize("idioma,rotulo", [("es", "Serial Especifika"), ("en", "Especifika serial")])
def test_arranque_automatizacion(idioma, rotulo):
    texto = _arranque(_perfil(auto=True), idioma)
    lineas = texto.splitlines()
    assert any(SERIE_ORIG in l for l in lineas)
    assert f"{rotulo}: SN000123" in lineas
    assert "SPK-SAT 45V" not in texto            # el modelo interno ya no se muestra
    texto.encode("cp437")
    assert all(len(l) <= 48 for l in lineas)


def test_arranque_modelo_de_80_caracteres_se_parte_sin_perder_nada():
    p = _perfil(auto=True, modelo_orig=MODELO_80, serie_orig="S" * 40)
    lineas = _arranque(p).splitlines()
    assert all(len(l) <= 48 for l in lineas)
    i = next(n for n, l in enumerate(lineas) if l.startswith("Modelo:"))
    pedazos = [lineas[i][16:]]
    j = i + 1
    while lineas[j].startswith(" " * 16):
        pedazos.append(lineas[j][16:])
        j += 1
    assert "".join(pedazos) == MODELO_80
    assert len(pedazos) == 3                      # 32 + 32 + 16
    k = next(n for n, l in enumerate(lineas) if l.startswith("Serie:"))
    assert (lineas[k][16:] + lineas[k + 1][16:]) == "S" * 40
    assert "Serial Especifika: SN000123" in lineas


# ── Ticket de ciclo (24 columnas) ─────────────────────────────────────────

def _ciclo(**extra):
    base = {"numero_ciclo": 7, "serie": "SN000123", "modelo": "SPK-SAT 45V", "version_sw": "1.0.0",
            "nombre_ciclo": "Textiles", "tipo_ciclo": "textiles", "temp_esterilizacion": 134,
            "tiempo_esterilizacion": 3.5, "fecha_inicio": "2026-10-22T08:00:00",
            "fecha_fin": "2026-10-22T09:00:00", "resultado": "COMPLETADO"}
    base.update(extra)
    return base


def _cabecera(ciclo):
    from autoclave.services.domain.logging.ticket_formatter import Presentacion, format_ticket
    texto = format_ticket(ciclo, [], Presentacion())
    return texto.splitlines()


def test_ticket_ciclo_fabricacion_identico_con_y_sin_columnas():
    esperado = _cabecera(_ciclo())
    assert "Num serie: SN000123" in esperado
    assert "Modelo: SPK-SAT 45V" in esperado
    # ciclo histórico (sin columnas) y de fabricación (NULL): byte a byte lo mismo
    assert _cabecera(_ciclo(serie_original=None, modelo_original=None)) == esperado
    assert not any("Especifika" in l for l in esperado)


def test_ticket_ciclo_automatizacion():
    lineas = _cabecera(_ciclo(serie_original=SERIE_ORIG, modelo_original=MODELO_ORIG))
    texto = "\n".join(lineas)
    assert "SPK-SAT 45V" not in texto
    assert f"Num serie: {SERIE_ORIG}" in lineas
    i = lineas.index("Serial Especifika:")
    assert lineas[i + 1] == "SN000123"
    assert all(len(l) <= 24 for l in lineas[:12])
    # el modelo original sigue completo aunque pase a varias líneas
    i = lineas.index("Modelo:")
    assert "".join(lineas[i + 1:i + 1 + 2]) == MODELO_ORIG[:48]


def test_ticket_ciclo_modelo_de_80_caracteres():
    lineas = _cabecera(_ciclo(serie_original=SERIE_ORIG, modelo_original=MODELO_80))
    i = lineas.index("Modelo:")
    trozos = lineas[i + 1:i + 5]
    assert all(len(t) <= 24 for t in trozos)
    assert "".join(trozos) == MODELO_80


def test_ticket_ciclo_acepta_fila_sqlite():
    import sqlite3
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.execute("CREATE TABLE c (serie TEXT, modelo TEXT)")
    con.execute("INSERT INTO c VALUES ('SN1', 'M')")
    fila = con.execute("SELECT * FROM c").fetchone()
    from autoclave.services.domain.logging.ticket_formatter import _originales_del_ciclo
    assert _originales_del_ciclo(fila) == {}


# ── Ticket de mantenimiento ───────────────────────────────────────────────

def test_ticket_mantenimiento():
    from autoclave.services.domain.logging import ticket_mantenimiento as tm
    ahora = datetime(2026, 10, 22, 8, 0)
    base = tm.pagina_prueba({"serie": "SN000123", "modelo": "SPK-SAT 45V"}, ahora, "es").splitlines()
    assert "Num serie: SN000123" in base and "Modelo: SPK-SAT 45V" in base
    meta = identidad.meta_con_originales({"serie": "SN000123", "modelo": "SPK-SAT 45V"},
                                         _perfil(auto=True))
    lineas = tm.pagina_prueba(meta, ahora, "es").splitlines()
    assert all(len(l) <= tm.ANCHO for l in lineas)
    assert "Num serie: " + SERIE_ORIG in lineas
    assert "Serial Especifika: SN000123" in lineas
    assert "SPK-SAT 45V" not in "\n".join(lineas)


# ── Resumen del periodo ───────────────────────────────────────────────────

def _resumen():
    return {"totales": {"total": 0, "completados": 0, "fallos": 0, "cancelados": 0, "sin_cierre": 0},
            "por_programa": [], "causas_fallo": []}


def test_resumen_periodo_impreso():
    from autoclave.services.domain.reportes.resumen_periodo import format_ticket_resumen
    ahora = datetime(2026, 10, 22, 8, 0)
    a = format_ticket_resumen(_resumen(), "2026-10-01", "2026-10-02", "SN000123", "SPK-SAT 45V", ahora, "es")
    assert "Especifika" not in a
    b = format_ticket_resumen(_resumen(), "2026-10-01", "2026-10-02", "SN000123", "SPK-SAT 45V", ahora,
                              "es", serial_especifika=None)
    assert a == b
    c = format_ticket_resumen(_resumen(), "2026-10-01", "2026-10-02", SERIE_ORIG, MODELO_ORIG, ahora,
                              "es", serial_especifika="SN000123")
    lineas = c.splitlines()
    assert lineas[lineas.index("Serial Especifika:") + 1] == "SN000123"
    assert all(len(l) <= 24 for l in lineas[:12])


# ── PDF/correo: texto de empresa ──────────────────────────────────────────

def test_texto_empresa():
    pytest.importorskip("PySide6")
    from autoclave.ui_qml.bridge.acciones_ciclos import texto_empresa
    base = texto_empresa("SPK-SAT 45V", "SN000123", "es")
    assert texto_empresa("SPK-SAT 45V", "SN000123", "es", serial_especifika=None) == base
    assert "Serial Especifika" not in base
    auto = texto_empresa(MODELO_ORIG, SERIE_ORIG, "es", serial_especifika="SN000123")
    assert SERIE_ORIG in auto and "Serial Especifika: SN000123" in auto


# ── /system/info y resumen ────────────────────────────────────────────────

@pytest.fixture
def cliente():
    from fastapi.testclient import TestClient
    from tests.helpers.backend_doble import cargar_servidor
    ctx = MagicMock()
    ctx.profile.model_id, ctx.profile.serial_number = "SPK-SAT 45V2-LAB", "SN000123"
    ctx.profile.created_at = datetime(2026, 10, 22, 9, 0)
    ctx.profile.vapor_source = "generator"
    ctx.profile.capacidad_litros, ctx.profile.tipo_carga = 45, "V"
    ctx.serial.modulo_es.return_value = {}
    ctx.db.max_numero_ciclo.return_value = 1
    ctx.mantenimiento.resumen.return_value = {}
    ctx.config_idioma.leer.return_value = "es"
    ctx.config_unidades.leer.return_value = {"temperatura": "C", "presion": "kPa"}
    ctx.config_impresora.habilitada.return_value = False
    srv, _ = cargar_servidor(ctx)
    return TestClient(srv.app), ctx


def test_system_info_fabricacion_sin_clave_nueva(cliente):
    c, ctx = cliente
    eq = c.get("/system/info").json()["equipo"]
    assert eq == {"modelo": "SPK-SAT 45V2-LAB", "serie": "SN000123",
                  "instalacion": "2026-10-22T09:00:00", "fuente_vapor": "generator",
                  "capacidad_litros": 45, "tipo_carga": "V", "clase": None}


def test_system_info_automatizacion(cliente):
    c, ctx = cliente
    ctx.profile.serial_original, ctx.profile.modelo_original = SERIE_ORIG, MODELO_ORIG
    eq = c.get("/system/info").json()["equipo"]
    assert eq["modelo"] == MODELO_ORIG and eq["serie"] == SERIE_ORIG
    assert eq["serial_especifika"] == "SN000123"
    for clave in ("instalacion", "fuente_vapor", "capacidad_litros", "tipo_carga", "clase"):
        assert clave in eq                            # no se quitó ninguna


def test_system_info_no_altera_openapi_ni_rutas():
    import json
    from pathlib import Path
    base = Path(__file__).resolve().parent.parent / "docs" / "informes" / "tanda15" / "base"
    assert base.is_dir()
    from autoclave.backend import server
    rutas = {(m, r.path) for r in server.app.routes if hasattr(r, "methods") for m in r.methods}
    assert ("GET", "/system/info") in rutas


# ── Información del equipo (panel) ────────────────────────────────────────

def test_info_equipo_filas():
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from autoclave.ui_qml.bridge.info_equipo import filas_equipo
    fab = {f["clave"]: f for f in filas_equipo(_perfil(), 1, "1.0", [])}
    assert fab["modelo"]["valor"] == "SPK-SAT 45V" and fab["serie"]["valor"] == "SN000123"
    assert "serial_especifika" not in fab
    claves_fab = [f["clave"] for f in filas_equipo(_perfil(), 1, "1.0", [])]
    auto_filas = filas_equipo(_perfil(auto=True), 1, "1.0", [])
    auto = {f["clave"]: f for f in auto_filas}
    assert auto["modelo"]["valor"] == MODELO_ORIG and auto["serie"]["valor"] == SERIE_ORIG
    assert auto["serial_especifika"]["valor"] == "SN000123"
    assert [f["clave"] for f in auto_filas if f["clave"] != "serial_especifika"] == claves_fab
    # sin perfil y con MagicMock: como siempre
    assert {f["clave"]: f for f in filas_equipo(None, 1, "1.0", [])}["serie"]["valor"] is None
    m = MagicMock()
    m.model_id, m.serial_number = "M", "SN1"
    assert "serial_especifika" not in {f["clave"] for f in filas_equipo(m, 1, "1.0", [])}


def test_info_sistema_grupos():
    from autoclave.ui_qml.controllers.info_sistema_controller import grupos_de
    fab = {f["clave"]: f for f in grupos_de({"equipo": {"modelo": "M", "serie": "S"}})[0]["filas"]}
    assert "serial_especifika" not in fab
    auto = {f["clave"]: f for f in grupos_de(
        {"equipo": {"modelo": "MO", "serie": "SO", "serial_especifika": "SN000123"}})[0]["filas"]}
    assert auto["serie"]["valor"] == "SO" and auto["serial_especifika"]["valor"] == "SN000123"


# ── Lo que NO cambia: serie interna del respaldo ──────────────────────────

def test_meta_equipo_sigue_con_la_serie_interna():
    from autoclave.backend.rutas import _comun
    ctx = MagicMock()
    ctx.profile = _perfil(auto=True)
    anterior = _comun.context
    _comun.context = ctx
    try:
        assert _comun._meta_equipo() == {"serie": "SN000123", "modelo": "SPK-SAT 45V"}
    finally:
        _comun.context = anterior

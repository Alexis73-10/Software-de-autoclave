# tests/test_e2_nombres_familia.py
#
# E2 (tanda 8): D8-0 y D8-3.23.
# - D8-0: las familias se muestran "Hospitalario"/"Hospital" (piso) y
#   "Laboratorio"/"Laboratory" (piso_lab), SOLO por catálogo i18n. Los valores
#   internos del perfil, la validación y el nombre del modelo no cambian.
# - El ticket de arranque ya no imprime el valor crudo ("Clase: piso_lab").
# - D8-3.23: en los tickets va solo el nombre del modelo; la capacidad y el
#   tipo de carga van en la cabecera del PDF y en Información del sistema.

import os
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autoclave import i18n
from autoclave.installation.equipment import EquipmentClass

NOMBRES = {
    "es": {"piso": "Hospitalario", "piso_lab": "Laboratorio"},
    "en": {"piso": "Hospital", "piso_lab": "Laboratory"},
}


# ── Catálogo ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("idioma", ["es", "en"])
@pytest.mark.parametrize("grupo", ["instalacion", "equipo"])
@pytest.mark.parametrize("clase", ["piso", "piso_lab"])
def test_catalogo_nombres_de_familia(idioma, grupo, clase):
    assert i18n.catalogo(idioma)[grupo][f"clase_{clase}"] == NOMBRES[idioma][clase]


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_ningun_texto_de_clase_dice_piso(idioma):
    cat = i18n.catalogo(idioma)
    textos = [cat["instalacion"]["clase_piso"], cat["instalacion"]["clase_piso_lab"],
              cat["equipo"]["clase_piso"], cat["equipo"]["clase_piso_lab"],
              cat["instalacion"]["error_clase_fuera_alcance"]]
    for t in textos:
        assert "piso" not in t.lower() and "floor" not in t.lower(), t


def test_valores_internos_sin_cambio():
    from autoclave.installation.modelo import CLASES_INSTALABLES, calcular_modelo
    assert EquipmentClass.PISO.value == "piso" and EquipmentClass.PISO_LAB.value == "piso_lab"
    assert CLASES_INSTALABLES == ("piso", "piso_lab")
    assert calcular_modelo("piso_lab", 45, "V", 2) == "SPK-SAT 45V2-LAB"
    assert calcular_modelo("piso", 2000, "H", 1) == "SPK-SAT 2000H"


# ── Ticket de arranque ────────────────────────────────────────────────────

def _perfil(clase, modelo):
    p = MagicMock()
    p.model_id = modelo
    p.serial_number = "SN-0001"
    p.equipment_class = clase
    p.capacidad_litros = 45
    p.tipo_carga = "V"
    return p


@pytest.mark.parametrize("idioma", ["es", "en"])
@pytest.mark.parametrize("clase,modelo", [(EquipmentClass.PISO, "SPK-SAT 45V"),
                                          (EquipmentClass.PISO_LAB, "SPK-SAT 45V2-LAB")])
def test_ticket_arranque_clase_traducida(idioma, clase, modelo):
    from autoclave.devices.printer.startup_ticket import format_startup_ticket
    texto = format_startup_ticket(_perfil(clase, modelo), "1.0.0", None,
                                  datetime(2026, 10, 22, 8, 0, 0), idioma=idioma)
    linea = next(l for l in texto.splitlines() if l.startswith(("Clase:", "Class:")))
    assert linea.split()[-1] == NOMBRES[idioma][clase.value]
    assert "piso" not in texto
    assert modelo in texto                       # el nombre del modelo no cambia
    texto.encode("cp437")                        # impresora térmica


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_ticket_arranque_solo_nombre_del_modelo(idioma):
    """D8-3.23: ni capacidad ni tipo de carga en el ticket."""
    from autoclave.devices.printer.startup_ticket import format_startup_ticket
    texto = format_startup_ticket(_perfil(EquipmentClass.PISO, "SPK-SAT 45V"), "1.0.0", None,
                                  datetime(2026, 10, 22, 8, 0, 0), idioma=idioma)
    assert " L" not in texto.replace("SPK-SAT 45V", "")
    for palabra in ("Capacidad", "Capacity", "carga", "load", "Vertical"):
        assert palabra not in texto


def test_ticket_arranque_clase_sin_traduccion_imprime_el_valor():
    """Un valor sin texto en el catálogo se imprime tal cual (nunca vacío)."""
    from autoclave.devices.printer.startup_ticket import _nombre_clase
    clase = MagicMock()
    clase.value = "desconocida"
    assert _nombre_clase(clase, "es") == "desconocida"


def test_ticket_de_ciclo_solo_nombre_del_modelo():
    from autoclave.services.domain.logging.ticket_formatter import format_header
    meta = {"modelo": "SPK-SAT 45V2-LAB", "serie": "SN-0001", "numero_ciclo": 1,
            "nombre_ciclo": "Instrumental 134", "fecha_inicio": "2026-10-22T08:00:00"}
    texto = format_header(meta)
    assert "SPK-SAT 45V2-LAB" in texto
    for palabra in ("Capacidad", "Laboratorio", "Hospitalario", "Vertical"):
        assert palabra not in texto


# ── Información del sistema ───────────────────────────────────────────────

def test_info_sistema_backend_entrega_la_clase():
    from fastapi.testclient import TestClient
    from tests.backend_doble import cargar_servidor
    ctx = MagicMock()
    ctx.profile.model_id = "SPK-SAT 45V2-LAB"
    ctx.profile.equipment_class = EquipmentClass.PISO_LAB
    ctx.profile.capacidad_litros, ctx.profile.tipo_carga = 45, "V"
    srv, _ = cargar_servidor(ctx)
    eq = TestClient(srv.app).get("/system/info").json()["equipo"]
    assert eq["clase"] == "piso_lab"
    assert eq["capacidad_litros"] == 45 and eq["tipo_carga"] == "V"


def test_info_sistema_fila_clase_por_catalogo():
    from autoclave.ui_qml.controllers.info_sistema_controller import grupos_de
    g = grupos_de({"equipo": {"modelo": "SPK-SAT 45V", "clase": "piso",
                              "capacidad_litros": 45, "tipo_carga": "V"}})
    filas = {f["clave"]: f for f in g[0]["filas"]}
    assert [f["clave"] for f in g[0]["filas"]][:4] == ["modelo", "capacidad", "tipo_carga", "clase"]
    assert filas["clase"]["valorClave"] == "equipo.clase_piso"
    assert filas["capacidad"]["valor"] == "45 L"
    assert filas["tipo_carga"]["valorClave"] == "info_sistema.carga_V"
    # valor desconocido o ausente: "—" (sin clave de catálogo inventada)
    for dato in ({"clase": "otra"}, {}):
        f = {x["clave"]: x for x in grupos_de({"equipo": dato})[0]["filas"]}["clase"]
        assert f["valorClave"] == "" and f["valor"] == ""


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_info_sistema_rotulo_clase(idioma):
    assert i18n.existe("info_sistema.rotulo_clase", idioma)


# ── Cabecera del PDF ──────────────────────────────────────────────────────

@pytest.mark.parametrize("modelo,esperado", [
    ("SPK-SAT 45V", {"clase": "piso", "capacidad_litros": 45, "tipo_carga": "V", "door_count": 1}),
    ("SPK-SAT 2000H2-LAB", {"clase": "piso_lab", "capacidad_litros": 2000, "tipo_carga": "H",
                            "door_count": 2}),
    ("SPK-SAT 120V-LAB", {"clase": "piso_lab", "capacidad_litros": 120, "tipo_carga": "V",
                          "door_count": 1}),
])
def test_desglosar_modelo(modelo, esperado):
    from autoclave.installation.modelo import calcular_modelo, desglosar_modelo
    d = desglosar_modelo(modelo)
    assert d == esperado
    assert calcular_modelo(d["clase"], d["capacidad_litros"], d["tipo_carga"], d["door_count"]) == modelo


@pytest.mark.parametrize("modelo", ["", None, "ACV-150", "SPK-SAT 19V", "SPK-SAT 45X",
                                    "SPK-SAT 45V3", "SPK-SAT 45V-LABX", "MESA_B", 45])
def test_desglosar_modelo_invalido(modelo):
    from autoclave.installation.modelo import desglosar_modelo
    assert desglosar_modelo(modelo) is None


@pytest.mark.parametrize("idioma,partes", [
    ("es", ["SPK-SAT 45V2-LAB", "Serie SN-0001", "Laboratorio", "45 L", "Carga vertical"]),
    ("en", ["SPK-SAT 45V2-LAB", "Serial SN-0001", "Laboratory", "45 L", "Vertical load"]),
])
def test_cabecera_pdf_con_familia_capacidad_y_carga(idioma, partes):
    from autoclave.ui_qml.bridge.acciones_ciclos import texto_empresa
    texto = texto_empresa("SPK-SAT 45V2-LAB", "SN-0001", idioma)
    for p in partes:
        assert p in texto, (p, texto)


def test_cabecera_pdf_modelo_antiguo_sin_desglose():
    from autoclave.ui_qml.bridge.acciones_ciclos import texto_empresa
    assert texto_empresa("ACV-150", "SN-1", "es") == i18n.t("exportacion.empresa", "es",
                                                             modelo="ACV-150", serie="SN-1")


_SCRIPT_ANCHO = r"""
import json, sys, os
from PySide6.QtGui import QGuiApplication
from autoclave.ui_qml.app import _cargar_fuentes
from autoclave.ui_qml.exportacion.pdf_ciclo import Documento
from autoclave.ui_qml.bridge.acciones_ciclos import texto_empresa
app = QGuiApplication([])
_cargar_fuentes()
r = {}
with Documento(sys.argv[1]) as doc:
    fm = doc.l.fuente(8)
    for idioma in ("es", "en"):
        r[idioma] = [fm.horizontalAdvance(texto_empresa("SPK-SAT 2000H2-LAB", "SPK-2026-000123", idioma)),
                     doc.l.ancho]
print("RESULTADO=" + json.dumps(r))
"""


def test_cabecera_pdf_cabe_en_el_ancho_de_la_pagina(tmp_path):
    """El caso más largo (2000 L, dos puertas, laboratorio) no se sale de la hoja."""
    pytest.importorskip("PySide6")
    import json
    import subprocess
    import sys
    raiz = Path(__file__).resolve().parents[1]
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONPATH": str(raiz / "src")}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT_ANCHO, str(tmp_path / "x.pdf")],
                       capture_output=True, text=True, encoding="utf-8", env=env, timeout=120)
    linea = next((l for l in p.stdout.splitlines() if l.startswith("RESULTADO=")), None)
    assert linea, p.stdout[-2000:] + p.stderr[-2000:]
    medidas = json.loads(linea[len("RESULTADO="):])
    assert sorted(medidas) == ["en", "es"]
    for idioma, (ancho_texto, ancho_hoja) in medidas.items():
        assert 0 < ancho_texto <= ancho_hoja, (idioma, ancho_texto, ancho_hoja)


# ── Pantallas QML (offscreen) ─────────────────────────────────────────────
# Con E2_CAPTURAS=1 guardan las capturas en docs/informes/tanda8/capturas/e2/.

CARPETA_CAPTURAS = Path(__file__).resolve().parents[1] / "docs" / "informes" / "tanda8" / "capturas" / "e2"
CAPTURAR = bool(os.environ.get("E2_CAPTURAS"))


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_asistente_muestra_hospitalario_y_laboratorio(idioma):
    pytest.importorskip("PySide6")
    from tests.m1_asistente_banco import recorrer
    obs = recorrer(idioma, capturas=CAPTURAR, carpeta=CARPETA_CAPTURAS)
    assert obs["avisos"] == []
    assert obs["clases"] == ["piso", "piso_lab"]                       # valores internos
    assert obs["titulosClase"] == [NOMBRES[idioma]["piso"], NOMBRES[idioma]["piso_lab"]]
    assert obs["resumenEquipo"] == NOMBRES[idioma]["piso_lab"]
    assert obs["instalado"][0]["equipment_class"] == "piso_lab"
    assert obs["instalado"][0]["model_id"] == "SPK-SAT 2000H2-LAB"


INFO_E2 = {
    "equipo": {"modelo": "SPK-SAT 2000H2-LAB", "serie": "SN-0001", "instalacion": "2026-10-22T09:00:00",
               "fuente_vapor": "generator", "capacidad_litros": 2000, "tipo_carga": "H",
               "clase": "piso_lab"},
    "software": {"version": "1.0.0", "firmware": "1.0.0", "id_tarjeta": "ESP32-A1B2C3"},
    "uso": {"ciclos": 128, "mantenimiento": None},
    "configuracion": {"idioma": "es", "unidades": {"temperatura": "C", "presion": "kPa"},
                      "impresora": "lista", "red": "conectada"},
}


@pytest.mark.parametrize("idioma,esperados", [
    ("es", ["Tipo de equipo", "Laboratorio", "Capacidad nominal", "2000 L", "Horizontal (H)",
            "SPK-SAT 2000H2-LAB"]),
    ("en", ["Equipment type", "Laboratory", "2000 L", "Horizontal (H)", "SPK-SAT 2000H2-LAB"]),
])
def test_info_sistema_pantalla_muestra_la_familia(idioma, esperados):
    pytest.importorskip("PySide6")
    from tests.opciones_qml_doble import correr
    r = correr("info_sistema", "admin", {"/system/info": INFO_E2}, idioma=idioma,
               capturar=CAPTURAR, carpeta=CARPETA_CAPTURAS,
               pasos=[{"captura": f"E2_{idioma}_info_sistema.png"}])
    assert r["avisos"] == []
    t = r["pasos"][0]["textos"]
    for texto in esperados:
        assert texto in t, (texto, t)
    assert "piso_lab" not in t and "Piso" not in " ".join(t)

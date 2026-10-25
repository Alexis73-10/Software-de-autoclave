"""M1 (tanda 7): el nombre del modelo en los documentos y pantallas que ya
leen model_id (planeacion_asistente_modelo.md §5 y §6): ticket cp437 de 24
columnas sin cortes con el nombre más largo (18 caracteres), resumen por
periodo, ticket de arranque, ticket de mantenimiento, PDF e Información del
sistema (capacidad y tipo de carga)."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from autoclave.services.domain.logging import ticket_formatter as tf

LARGO = "SPK-SAT 2000H2-LAB"


def _meta(modelo):
    return {"fecha_inicio": "2026-10-22T08:00:00", "numero_ciclo": 7, "serie": "SN-0001",
            "modelo": modelo, "version_sw": "1.0", "nombre_ciclo": "Instrumental",
            "tipo_ciclo": "Solido", "temp_esterilizacion": "134", "tiempo_esterilizacion": "3.5"}


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_ticket_de_ciclo_nombre_mas_largo_sin_cortes(idioma):
    p = tf.Presentacion(idioma=idioma, temperatura="C", presion="kPa") \
        if hasattr(tf, "Presentacion") else None
    cab = tf.format_header(_meta(LARGO), p)
    lineas = cab.split("\n")
    assert LARGO in lineas                               # entero, en su propia línea
    assert all(len(l) <= tf.ANCHO_TICKET for l in lineas), [l for l in lineas if len(l) > 24]
    i = lineas.index(LARGO)
    assert lineas[i - 1] in ("Modelo:", "Model:")
    cab.encode("cp437")


def test_ticket_de_ciclo_modelo_corto_en_una_linea():
    lineas = tf.format_header(_meta("SPK-SAT 45V")).split("\n")
    assert "Modelo: SPK-SAT 45V" in lineas or "Model: SPK-SAT 45V" in lineas


def test_lineas_rotulo():
    assert tf.lineas_rotulo("Modelo", "SPK-SAT 45V") == ["Modelo: SPK-SAT 45V"]
    assert tf.lineas_rotulo("Modelo", LARGO) == ["Modelo:", LARGO]
    assert tf.lineas_rotulo("Modelo", "") == ["Modelo: "]
    largo_viejo = "X" * 30                               # perfil anterior con texto libre
    assert tf.lineas_rotulo("Modelo", largo_viejo) == ["Modelo:", "X" * 24, "X" * 6]


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_ticket_resumen_periodo_sin_cortar_el_nombre(idioma):
    from autoclave.services.domain.reportes import resumen_periodo as rp
    resumen = {"totales": {"total": 0, "completados": 0, "fallos": 0, "cancelados": 0,
                           "sin_cierre": 0}, "por_programa": [], "causas_fallo": []}
    texto = rp.format_ticket_resumen(resumen, "2026-10-01", "2026-10-22", serie="SN-0001",
                                     modelo=LARGO, ahora=datetime(2026, 10, 22), idioma=idioma)
    lineas = texto.split("\n")
    assert LARGO in lineas
    assert all(len(l) <= 24 for l in lineas)


def test_ticket_de_arranque_48_columnas():
    from autoclave.devices.printer.startup_ticket import format_startup_ticket
    perfil = MagicMock(model_id=LARGO, serial_number="SN-0001")
    perfil.equipment_class.value = "piso_lab"
    texto = format_startup_ticket(perfil, "1.0", None, datetime(2026, 10, 22, 8), idioma="es")
    linea = next(l for l in texto.split("\n") if LARGO in l)
    assert len(linea) <= 48 and linea.endswith(LARGO)


def test_ticket_de_mantenimiento_32_columnas():
    from autoclave.services.domain.logging import ticket_mantenimiento as tm
    texto = tm.pagina_prueba({"serie": "SN-0001", "modelo": LARGO}, datetime(2026, 10, 22), "es")
    linea = next(l for l in texto.split("\n") if LARGO in l)
    assert len(linea) <= tm.ANCHO


def test_pdf_y_correo_llevan_el_nombre_en_la_cabecera():
    """El PDF (que también se adjunta al correo) pone el modelo en la línea de empresa."""
    from autoclave import i18n
    texto = i18n.t("exportacion.empresa", "es", modelo=LARGO, serie="SN-0001")
    assert LARGO in texto


# ── Información del sistema (O2d) ────────────────────────────────────────

def test_info_sistema_filas_de_capacidad_y_carga():
    from autoclave.ui_qml.controllers.info_sistema_controller import CLAVES_FILA, grupos_de
    d = {"equipo": {"modelo": "SPK-SAT 45V2-LAB", "capacidad_litros": 45, "tipo_carga": "V"}}
    filas = {f["clave"]: f for f in grupos_de(d)[0]["filas"]}
    assert list(filas)[:3] == ["modelo", "capacidad", "tipo_carga"]
    assert filas["modelo"]["valor"] == "SPK-SAT 45V2-LAB"
    assert filas["capacidad"]["valor"] == "45 L"
    assert filas["tipo_carga"]["valorClave"] == "info_sistema.carga_V"
    assert "capacidad" in CLAVES_FILA and "tipo_carga" in CLAVES_FILA


def test_info_sistema_perfil_anterior_muestra_guion():
    """Sin capacidad ni carga (perfil anterior a M1): valor vacío, la pantalla pone "—"."""
    from autoclave.ui_qml.controllers.info_sistema_controller import grupos_de
    filas = {f["clave"]: f for f in grupos_de({"equipo": {"modelo": "AC-500"}})[0]["filas"]}
    assert filas["capacidad"]["valor"] == "" and filas["capacidad"]["valorClave"] == ""
    assert filas["tipo_carga"]["valor"] == "" and filas["tipo_carga"]["valorClave"] == ""
    filas = {f["clave"]: f for f in grupos_de({"equipo": {"tipo_carga": "Z"}})[0]["filas"]}
    assert filas["tipo_carga"]["valorClave"] == ""


@pytest.fixture
def cliente():
    from fastapi.testclient import TestClient
    from tests.helpers.backend_doble import cargar_servidor
    ctx = MagicMock()
    ctx.profile.model_id, ctx.profile.serial_number = "SPK-SAT 45V2-LAB", "SN-0001"
    ctx.profile.created_at = datetime(2026, 10, 22, 9, 0)
    ctx.profile.vapor_source = "generator"
    ctx.profile.capacidad_litros, ctx.profile.tipo_carga = 45, "V"
    ctx.serial.tarjeta.return_value = {}
    ctx.db.max_numero_ciclo.return_value = 1
    ctx.mantenimiento.resumen.return_value = {}
    ctx.config_idioma.leer.return_value = "es"
    ctx.config_unidades.leer.return_value = {"temperatura": "C", "presion": "kPa"}
    ctx.config_impresora.habilitada.return_value = False
    srv, _ = cargar_servidor(ctx)
    return TestClient(srv.app), ctx


def test_system_info_entrega_capacidad_y_carga(cliente):
    c, ctx = cliente
    eq = c.get("/system/info").json()["equipo"]
    assert eq["modelo"] == "SPK-SAT 45V2-LAB"
    assert eq["capacidad_litros"] == 45 and eq["tipo_carga"] == "V"


def test_system_info_perfil_anterior_sin_campos(cliente):
    c, ctx = cliente
    ctx.profile.capacidad_litros, ctx.profile.tipo_carga = None, None
    eq = c.get("/system/info").json()["equipo"]
    assert eq["capacidad_litros"] is None and eq["tipo_carga"] is None


def test_configuracion_de_la_maquina_muestra_el_modelo_solo_lectura():
    """O2a: el modelo se lee del perfil y no tiene setter (solo lectura)."""
    from autoclave.ui_qml.controllers.parametros_equipo_controller import ParametrosEquipoController
    prop = ParametrosEquipoController.staticMetaObject.property(
        ParametrosEquipoController.staticMetaObject.indexOfProperty("modelo"))
    assert prop.isReadable() and not prop.isWritable()

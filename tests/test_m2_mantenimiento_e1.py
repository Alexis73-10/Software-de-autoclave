"""M2 (tanda 7): Mantenimiento E1 (planeacion_mantenimiento.md §10).

MNT-01: solo el preventivo reinicia el contador (D-2).
MNT-02: `calibracion` ya no es un tipo válido para registrar (D-5).
MNT-03: el controlador QML no duplica la tupla de tipos.
MNT-05: las filas históricas de `calibracion` se muestran como "Calibración
(histórico)" y nunca se ofrecen como opción nueva."""

from datetime import date, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from autoclave.core.runtime import mantenimiento as m
from autoclave.core.runtime.contador_ciclos import ContadorCiclos
from autoclave.core.runtime.servicio_mantenimiento import (
    ErrorMantenimiento, ServicioMantenimiento)
from autoclave.services.domain.logging.db_manager import DbManager
from autoclave.state_machine.alarms.catalogo import MANTENIMIENTO_VENCIDO

INST = datetime(2026, 10, 26, 9, 0)


@pytest.fixture
def entorno(tmp_path):
    db = DbManager(db_path=tmp_path / "t.db")
    hoy = {"d": date(2026, 10, 27)}
    alarmas = MagicMock()
    contador = ContadorCiclos(tmp_path / "ciclo_contador.json")
    s = ServicioMantenimiento(tmp_path / "mantenimiento.json", db, INST, contador, alarmas,
                              hoy=lambda: hoy["d"])
    return s, db, hoy, alarmas, contador


def _ciclos(contador, n):
    for _ in range(n):
        contador.siguiente()


# ── MNT-01: base de datos ───────────────────────────────────────────────────

def test_db_ultimo_mantenimiento_filtra_preventivo_por_defecto(tmp_path):
    db = DbManager(db_path=tmp_path / "t.db")
    assert db.ultimo_mantenimiento() is None
    db.registrar_mantenimiento("2027-01-10", "tec", "preventivo", "", 5)
    db.registrar_mantenimiento("2027-02-10", "tec", "correctivo", "", 9)
    db.registrar_mantenimiento("2027-03-10", "tec", "otro", "", 12)
    u = db.ultimo_mantenimiento()
    assert u["tipo"] == "preventivo" and u["fecha"] == "2027-01-10" and u["ciclos"] == 5
    # sin filtro: el más reciente de cualquier tipo
    assert db.ultimo_mantenimiento(tipo=None)["tipo"] == "otro"
    assert db.ultimo_mantenimiento(tipo="correctivo")["fecha"] == "2027-02-10"
    assert db.ultimo_registro()["tipo"] == "otro"


def test_db_desempate_por_id_en_la_misma_fecha(tmp_path):
    db = DbManager(db_path=tmp_path / "t.db")
    db.registrar_mantenimiento("2027-01-10", "tec", "preventivo", "a", 1)
    db.registrar_mantenimiento("2027-01-10", "tec", "preventivo", "b", 2)
    assert db.ultimo_mantenimiento()["observaciones"] == "b"


def test_db_sin_preventivo_devuelve_none_aunque_haya_otros(tmp_path):
    db = DbManager(db_path=tmp_path / "t.db")
    db.registrar_mantenimiento("2027-01-10", "tec", "correctivo", "", 1)
    assert db.ultimo_mantenimiento() is None
    assert db.ultimo_registro()["tipo"] == "correctivo"


# ── MNT-01: servicio ────────────────────────────────────────────────────────

def test_preventivo_luego_correctivo_la_base_sigue_siendo_el_preventivo(entorno):
    s, db, hoy, alarmas, contador = entorno
    s.guardar_configuracion(365, 100)
    _ciclos(contador, 10)
    hoy["d"] = date(2027, 1, 10)
    s.registrar("tec", "preventivo", "")
    _ciclos(contador, 30)
    hoy["d"] = date(2027, 3, 1)
    s.registrar("tec", "correctivo", "cambio de empaque")
    e = s.estado()
    # días: desde el preventivo (10-ene-2027), no desde el correctivo
    assert e.proximo_fecha == date(2028, 1, 10)
    assert e.ultimo_fecha == date(2027, 1, 10) and e.ultimo_tipo == "preventivo"
    # ciclos: desde los 10 del preventivo, no desde los 40 del correctivo
    assert e.ciclos_restantes == 70


@pytest.mark.parametrize("tipo", ["correctivo"])  # `otro` salió (P-3, tanda 8)
def test_correctivo_y_otro_no_resuelven_el_aviso(entorno, tipo):
    s, db, hoy, alarmas, _ = entorno
    hoy["d"] = date(2027, 11, 1)                     # vencido por fecha
    assert s.evaluar_alarma() is True
    s.registrar("tec", tipo, "")
    assert s.estado().vencido
    alarmas.resolver.assert_not_called()
    assert s.evaluar_alarma() is True


def test_preventivo_resuelve_el_aviso(entorno):
    s, db, hoy, alarmas, _ = entorno
    hoy["d"] = date(2027, 11, 1)
    assert s.evaluar_alarma() is True
    s.registrar("tec", "correctivo", "")
    alarmas.resolver.assert_not_called()
    s.registrar("tec", "preventivo", "")
    alarmas.resolver.assert_called_with(MANTENIMIENTO_VENCIDO)
    assert not s.estado().vencido


def test_vencido_por_ciclos_no_lo_resuelve_un_correctivo(entorno):
    s, db, hoy, alarmas, contador = entorno
    s.guardar_configuracion(0, 20)
    s.estado()                                       # fija el contador de instalación en 0
    _ciclos(contador, 25)
    assert s.evaluar_alarma() is True
    s.registrar("tec", "correctivo", "")
    assert s.estado().vencido_por == "ciclos"
    s.registrar("tec", "preventivo", "")
    assert not s.estado().vencido and s.estado().ciclos_restantes == 20


def test_sin_preventivo_la_base_es_la_instalacion_aunque_haya_correctivos(entorno):
    s, db, hoy, alarmas, contador = entorno
    s.guardar_configuracion(365, 1000)
    s.estado()                                       # fija el contador de instalación en 0
    _ciclos(contador, 5)
    hoy["d"] = date(2027, 5, 1)
    s.registrar("tec", "correctivo", "")
    # fila histórica de `otro` (P-3, tanda 8: ya no se registra)
    db.registrar_mantenimiento("2027-05-01", "tec", "otro", "", 5)
    e = s.estado()
    assert e.proximo_fecha == date(2026, 10, 26) + timedelta(days=365)
    assert e.ultimo_fecha is None and e.ultimo_tipo == ""
    # ciclos desde la instalación (contador en 0 al instalar): 1000 - 5
    assert e.ciclos_restantes == 995


def test_fila_historica_de_calibracion_no_afecta_el_contador(entorno):
    s, db, hoy, alarmas, contador = entorno
    s.guardar_configuracion(365, 100)
    s.estado()                                       # fija el contador de instalación en 0
    _ciclos(contador, 40)
    hoy["d"] = date(2027, 2, 1)
    # fila de una instalación anterior a E1 (ya no se puede registrar por el servicio)
    db.registrar_mantenimiento("2027-01-15", "tec", "calibracion", "", 40)
    e = s.estado()
    assert e.proximo_fecha == date(2027, 10, 26) and e.ultimo_fecha is None
    assert e.ciclos_restantes == 60


def test_reloj_atrasado_respecto_de_un_correctivo_sigue_protegido(entorno):
    """Protección del reloj: ningún registro nuevo puede quedar con fecha
    anterior al último registro existente, sea del tipo que sea."""
    s, db, hoy, alarmas, _ = entorno
    hoy["d"] = date(2027, 3, 1)
    s.registrar("tec", "correctivo", "")
    hoy["d"] = date(2027, 2, 1)                      # alguien atrasa el reloj
    assert s.reloj_no_confiable() == "atrasado"
    assert s.estado().estado == m.SIN_DATO
    with pytest.raises(ErrorMantenimiento) as e:
        s.registrar("tec", "preventivo", "")
    assert e.value.codigo == "reloj_invalido"
    assert len(db.listar_mantenimientos()) == 1


# ── MNT-02: calibración ya no es un tipo de mantenimiento (D-5) ─────────────

def test_calibracion_no_esta_en_los_tipos():
    from autoclave.core.runtime import servicio_mantenimiento as sm
    assert "calibracion" not in sm.TIPOS
    assert sm.TIPOS == ("preventivo", "correctivo")  # sin `otro` (P-3, tanda 8)


def test_el_servicio_rechaza_calibracion(entorno):
    s, db, *_ = entorno
    with pytest.raises(ErrorMantenimiento) as e:
        s.registrar("tec", "calibracion", "")
    assert e.value.codigo == "validacion"
    assert db.listar_mantenimientos() == []


def test_post_calibracion_da_422_validacion(entorno):
    from fastapi.testclient import TestClient

    from tests.backend_doble import cabecera, cargar_servidor
    s, db, *_ = entorno
    ctx = MagicMock()
    ctx.db = db
    ctx.mantenimiento = s
    ctx.sin_base_de_datos = False
    srv, _ = cargar_servidor(ctx)
    client = TestClient(srv.app)
    r = client.post("/maintenance/records", headers=cabecera(srv, "tecnico"),
                    json={"tipo": "calibracion", "observaciones": ""})
    assert r.status_code == 422 and r.json()["codigo"] == "validacion"
    assert db.listar_mantenimientos() == []


# ── MNT-03: una sola tupla de tipos ─────────────────────────────────────────

def test_servicio_y_controlador_comparten_la_misma_tupla():
    pytest.importorskip("PySide6")
    from autoclave.core.runtime import servicio_mantenimiento as sm
    from autoclave.ui_qml.controllers import mantenimiento_controller as mc
    assert mc.TIPOS is m.TIPOS and sm.TIPOS is m.TIPOS


def test_el_controlador_no_ofrece_ni_envia_calibracion():
    pytest.importorskip("PySide6")
    import sys

    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    from autoclave.ui_qml.controllers.mantenimiento_controller import MantenimientoController
    sesion = MagicMock()
    c = MantenimientoController(sesion=sesion)
    assert c.property("tipos") == ["preventivo", "correctivo"]
    assert c.registrar("calibracion") is False
    sesion.enviar.assert_not_called()


def test_el_controlador_no_importa_el_servicio_del_backend():
    """La constante vive en el módulo de lógica pura (sin E/S ni alarmas):
    la UI no arrastra el servicio ni la máquina de estados."""
    import inspect

    from autoclave.ui_qml.controllers import mantenimiento_controller as mc
    fuente = inspect.getsource(mc)
    assert "servicio_mantenimiento" not in fuente and "state_machine" not in fuente


# ── MNT-05: filas históricas de calibración ─────────────────────────────────

def _catalogo(idioma):
    import json
    from pathlib import Path
    ruta = Path(m.__file__).resolve().parents[2] / "i18n" / f"{idioma}.json"
    return json.loads(ruta.read_text(encoding="utf-8"))


def test_calibracion_es_tipo_historico_y_no_registrable():
    assert m.TIPOS_HISTORICOS == ("calibracion", "otro")  # `otro`: P-3, tanda 8
    assert not set(m.TIPOS_HISTORICOS) & set(m.TIPOS)


def test_textos_de_calibracion_historica():
    assert _catalogo("es")["opciones"]["mant_tipo_calibracion"] == "Calibración (histórico)"
    assert _catalogo("en")["opciones"]["mant_tipo_calibracion"] == "Calibration (historical)"


def test_todo_tipo_registrable_o_historico_tiene_texto():
    for idioma in ("es", "en"):
        op = _catalogo(idioma)["opciones"]
        for tipo in m.TIPOS + m.TIPOS_HISTORICOS:
            assert op.get(f"mant_tipo_{tipo}"), (idioma, tipo)


def test_historial_devuelve_la_fila_historica_tal_cual(entorno):
    """La fila vieja se conserva con su tipo para que la UI la rotule como
    histórico; el contador la ignora (ver MNT-01)."""
    s, db, *_ = entorno
    db.registrar_mantenimiento("2026-10-26", "tec", "calibracion", "", 0)
    assert [f["tipo"] for f in s.historial()] == ["calibracion"]
    assert s.estado().ultimo_tipo == ""


def test_la_pantalla_no_ofrece_tipos_fijos():
    """OpcionesMantenimiento.qml arma los chips desde control.tipos (sin
    calibración) y no tiene un tipo escrito a mano."""
    from pathlib import Path
    qml = (Path(m.__file__).resolve().parents[2] / "ui_qml" / "qml" / "Pantallas"
           / "OpcionesMantenimiento.qml").read_text(encoding="utf-8")
    assert "model: control.tipos" in qml
    assert '"calibracion"' not in qml

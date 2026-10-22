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


@pytest.mark.parametrize("tipo", ["correctivo", "otro"])
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
    s.registrar("tec", "otro", "")
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

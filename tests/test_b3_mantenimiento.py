"""B3 (tanda 4): mantenimiento con 365 días / 1000 ciclos desde la instalación,
migración de los valores provisionales y reloj adelantado/atrasado."""

import json
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from autoclave.core.runtime import mantenimiento as m
from autoclave.core.runtime.contador_ciclos import ContadorCiclos
from autoclave.core.runtime.servicio_mantenimiento import (
    ErrorMantenimiento, ServicioMantenimiento)
from autoclave.services.domain.logging.db_manager import DbManager

INST = datetime(2026, 10, 26, 9, 0)


class Reloj:
    """Reloj de pared y monotónico controlables."""

    def __init__(self, ahora=datetime(2026, 10, 27, 8, 0)):
        self.pared = ahora
        self.mono = 1000.0

    def ahora(self):
        return self.pared

    def hoy(self):
        return self.pared.date()

    def monotonic(self):
        return self.mono

    def pasar(self, **kw):
        """Pasa el tiempo real: avanzan el reloj de pared y el monotónico."""
        d = timedelta(**kw)
        self.pared += d
        self.mono += d.total_seconds()

    def saltar_pared(self, **kw):
        """Ajuste manual del reloj de pared (el monotónico no se entera)."""
        self.pared += timedelta(**kw)


@pytest.fixture
def entorno(tmp_path):
    db = DbManager(db_path=tmp_path / "t.db")
    reloj = Reloj()
    contador = ContadorCiclos(tmp_path / "ciclo_contador.json")
    alarmas = MagicMock()
    s = ServicioMantenimiento(tmp_path / "mantenimiento.json", db, INST, contador, alarmas,
                              hoy=reloj.hoy, ahora=reloj.ahora, monotonic=reloj.monotonic)
    return s, db, reloj, contador, alarmas, tmp_path


def _ciclos(contador, n):
    for _ in range(n):
        contador.siguiente()


# ── valores por defecto ─────────────────────────────────────────────────────

def test_valores_por_defecto_son_365_dias_y_1000_ciclos(entorno):
    s, *_ = entorno
    assert (m.INTERVALO_DIAS_DEFECTO, m.INTERVALO_CICLOS_DEFECTO) == (365, 1000)
    assert s.configuracion() == {"intervalo_dias": 365, "intervalo_ciclos": 1000}


def test_primer_vencimiento_es_instalacion_mas_365_dias(entorno):
    s, *_ = entorno
    e = s.estado()
    assert e.proximo_fecha == date(2026, 10, 26) + timedelta(days=365)
    assert e.ciclos_restantes == 1000 and e.estado == m.OK


def test_vence_por_fecha(entorno):
    s, db, reloj, contador, alarmas, _ = entorno
    reloj.pared = datetime(2027, 10, 26, 8, 0)           # día 365: aún no
    reloj.mono += 400 * 86400                            # transcurrió de verdad
    assert not s.estado().vencido
    reloj.pasar(days=1)
    e = s.estado()
    assert e.vencido and e.vencido_por == "fecha"


def test_vence_por_ciclos_contados_desde_la_instalacion(entorno):
    s, db, reloj, contador, alarmas, _ = entorno
    assert s.estado().ciclos_restantes == 1000           # fija la base (0 en equipo nuevo)
    _ciclos(contador, 999)
    assert not s.estado().vencido and s.estado().ciclos_restantes == 1
    _ciclos(contador, 1)
    e = s.estado()
    assert e.vencido and e.vencido_por == "ciclos"


def test_lo_primero_que_ocurra(entorno):
    s, db, reloj, contador, alarmas, _ = entorno
    s.estado()
    _ciclos(contador, 1000)                              # los ciclos se cumplen a los 10 días
    reloj.pasar(days=10)
    assert s.estado().vencido_por == "ciclos"
    reloj.pasar(days=400)                                # y luego también la fecha
    assert s.estado().vencido


def test_la_fecha_vence_antes_que_los_ciclos(entorno):
    s, db, reloj, contador, alarmas, _ = entorno
    s.estado()
    _ciclos(contador, 10)
    reloj.pasar(days=366)
    e = s.estado()
    assert e.vencido and e.vencido_por == "fecha" and e.ciclos_restantes == 990


def test_equipo_con_ciclos_previos_cuenta_desde_la_primera_evaluacion(entorno):
    s, db, reloj, contador, alarmas, tmp = entorno
    _ciclos(contador, 40)                                # ya tenía ciclos al actualizar
    assert s.estado().ciclos_restantes == 1000           # base = 40
    _ciclos(contador, 10)
    assert s.estado().ciclos_restantes == 990
    # la base persiste entre reinicios del servicio
    s_nuevo = ServicioMantenimiento(tmp / "mantenimiento.json", db, INST, contador, alarmas,
                                    hoy=reloj.hoy, ahora=reloj.ahora, monotonic=reloj.monotonic)
    assert s_nuevo.estado().ciclos_restantes == 990


def test_tras_registrar_la_base_es_esa_fecha_y_ese_contador(entorno):
    s, db, reloj, contador, alarmas, _ = entorno
    s.estado()
    _ciclos(contador, 1000)
    reloj.pasar(days=400)
    assert s.estado().vencido
    r = s.registrar("tec", "preventivo", "")
    assert r["ciclos"] == 1000
    e = s.estado()
    assert not e.vencido and e.ciclos_restantes == 1000
    assert e.proximo_fecha == reloj.hoy() + timedelta(days=365)
    _ciclos(contador, 5)
    assert s.estado().ciclos_restantes == 995


def test_ningun_caso_bloquea_un_ciclo():
    from autoclave.state_machine.alarms.catalogo import CATALOGO, MANTENIMIENTO_VENCIDO
    assert CATALOGO[MANTENIMIENTO_VENCIDO].bloquea_inicio is False


def test_estado_y_resumen_nunca_lanzan_con_la_base_rota(tmp_path):
    from autoclave.backend.arranque.sin_bd import BdNoDisponible
    reloj = Reloj()
    s = ServicioMantenimiento(tmp_path / "m.json", BdNoDisponible(), INST, None, None,
                              hoy=reloj.hoy, ahora=reloj.ahora, monotonic=reloj.monotonic)
    assert s.resumen()["estado"] in (m.OK, m.PROXIMO, m.SIN_DATO)
    assert s.evaluar_alarma() is False


# ── migración de los valores provisionales ──────────────────────────────────

def _archivo(tmp, dias, ciclos):
    (tmp / "mantenimiento.json").write_text(
        json.dumps({"intervalo_dias": dias, "intervalo_ciclos": ciclos}), encoding="utf-8")


def test_migra_el_provisional_nunca_editado(entorno):
    s, db, reloj, contador, alarmas, tmp = entorno
    _archivo(tmp, 180, 0)
    assert s.migrar_valores_provisionales() is True
    assert s.configuracion() == {"intervalo_dias": 365, "intervalo_ciclos": 1000}
    fila = db.get_auditoria(evento="mantenimiento_migrado")[0]
    assert fila["usuario"] == "sistema"
    assert s.migrar_valores_provisionales() is False     # una sola vez


def test_no_toca_un_valor_editado_por_la_api(entorno):
    s, db, reloj, contador, alarmas, tmp = entorno
    db.registrar_auditoria("mantenimiento_configurado", usuario="tec", rol="tecnico",
                           entidad="/maintenance/config",
                           valor_anterior={"intervalo_dias": 365, "intervalo_ciclos": 1000},
                           valor_nuevo={"intervalo_dias": 180, "intervalo_ciclos": 0})
    _archivo(tmp, 180, 0)
    assert s.migrar_valores_provisionales() is False
    assert s.configuracion() == {"intervalo_dias": 180, "intervalo_ciclos": 0}


@pytest.mark.parametrize("dias, ciclos", [(90, 0), (180, 500), (365, 1000), (180, 1)])
def test_no_toca_valores_distintos_del_provisional(entorno, dias, ciclos):
    s, db, reloj, contador, alarmas, tmp = entorno
    _archivo(tmp, dias, ciclos)
    assert s.migrar_valores_provisionales() is False
    assert s.configuracion() == {"intervalo_dias": dias, "intervalo_ciclos": ciclos}


def test_sin_archivo_rige_el_defecto_nuevo_y_no_crea_nada(entorno):
    s, db, reloj, contador, alarmas, tmp = entorno
    assert s.migrar_valores_provisionales() is False
    assert not (tmp / "mantenimiento.json").exists()
    assert s.configuracion()["intervalo_dias"] == 365


def test_sin_base_de_datos_no_migra_por_no_poder_comprobar(tmp_path):
    from autoclave.backend.arranque.sin_bd import BdNoDisponible
    reloj = Reloj()
    _archivo(tmp_path, 180, 0)
    s = ServicioMantenimiento(tmp_path / "mantenimiento.json", BdNoDisponible(), INST, None, None,
                              hoy=reloj.hoy, ahora=reloj.ahora, monotonic=reloj.monotonic)
    assert s.migrar_valores_provisionales() is False
    assert s.configuracion() == {"intervalo_dias": 180, "intervalo_ciclos": 0}


# ── reloj atrasado y adelantado (M1-01) ─────────────────────────────────────

def test_reloj_atrasado_respecto_de_la_instalacion(entorno):
    s, db, reloj, contador, alarmas, _ = entorno
    reloj.pared = datetime(2026, 1, 1, 8, 0)
    assert s.estado().estado == m.SIN_DATO
    r = s.resumen()
    assert r["proximo_fecha"] is None and r["estado"] == m.SIN_DATO
    with pytest.raises(ErrorMantenimiento) as e:
        s.registrar("tec", "correctivo", "")
    assert e.value.codigo == "reloj_invalido" and db.listar_mantenimientos() == []


def test_reloj_atrasado_respecto_del_ultimo_mantenimiento(entorno):
    s, db, reloj, contador, alarmas, _ = entorno
    reloj.pasar(days=10)
    s.registrar("tec", "preventivo", "")
    reloj.pared -= timedelta(days=5)                     # alguien atrasa el reloj
    assert s.estado().estado == m.SIN_DATO
    with pytest.raises(ErrorMantenimiento) as e:
        s.registrar("tec", "correctivo", "")
    assert e.value.codigo == "reloj_invalido"
    assert len(db.listar_mantenimientos()) == 1


def test_reloj_adelantado_no_sella_fecha_futura_ni_afirma_vencimiento(entorno):
    s, db, reloj, contador, alarmas, _ = entorno
    assert s.estado().estado == m.OK
    reloj.saltar_pared(days=900)                         # ajuste manual hacia adelante
    e = s.estado()
    assert e.estado == m.SIN_DATO and e.proximo_fecha is None and not e.vencido
    assert s.evaluar_alarma() is False
    alarmas.activar.assert_not_called()
    with pytest.raises(ErrorMantenimiento) as err:
        s.registrar("tec", "preventivo", "")
    assert err.value.codigo == "reloj_adelantado"
    assert db.listar_mantenimientos() == []


def test_reloj_corregido_vuelve_a_la_normalidad(entorno):
    s, db, reloj, contador, alarmas, _ = entorno
    reloj.saltar_pared(days=900)
    assert s.estado().estado == m.SIN_DATO
    reloj.saltar_pared(days=-900)
    assert s.estado().estado == m.OK
    assert s.registrar("tec", "correctivo", "")["fecha"] == reloj.hoy().isoformat()


def test_el_paso_normal_del_tiempo_no_se_confunde_con_un_ajuste(entorno):
    s, db, reloj, contador, alarmas, _ = entorno
    reloj.pasar(days=200)
    assert s.estado().estado == m.OK
    reloj.pasar(hours=23)                                # una deriva pequeña es tolerada
    reloj.saltar_pared(hours=3)
    assert s.estado().estado == m.OK


def test_endpoint_rechaza_con_409_y_codigo_de_reloj_adelantado(entorno):
    from fastapi.testclient import TestClient
    from tests.helpers.backend_doble import cabecera, cargar_servidor
    s, db, reloj, contador, alarmas, _ = entorno
    ctx = MagicMock()
    ctx.db = db
    ctx.mantenimiento = s
    ctx.sin_base_de_datos = False
    srv, _ = cargar_servidor(ctx)
    client = TestClient(srv.app)
    reloj.saltar_pared(days=900)
    r = client.post("/maintenance/records", headers=cabecera(srv, "tecnico"), json={"tipo": "correctivo"})
    assert r.status_code == 409 and r.json()["codigo"] == "reloj_adelantado"


@pytest.mark.parametrize("rol, esperado", [("operador", 403), ("tecnico", 200), ("ingeniero", 200)])
def test_solo_tecnico_o_ingeniero_edita_los_intervalos(entorno, rol, esperado):
    from fastapi.testclient import TestClient
    from tests.helpers.backend_doble import cabecera, cargar_servidor
    s, db, reloj, contador, alarmas, _ = entorno
    ctx = MagicMock()
    ctx.db = db
    ctx.mantenimiento = s
    ctx.sin_base_de_datos = False
    srv, _ = cargar_servidor(ctx)
    client = TestClient(srv.app)
    cuerpo = {"intervalo_dias": 200, "intervalo_ciclos": 0}
    assert client.put("/maintenance/config", json=cuerpo).status_code == 401
    r = client.put("/maintenance/config", headers=cabecera(srv, rol), json=cuerpo)
    assert r.status_code == esperado
    if esperado == 200:
        assert any(f["evento"] == "mantenimiento_configurado" for f in db.get_auditoria(limite=10))

# tests/test_reporte_dashboard_puente.py
#
# ReporteDashboard (ui_qml/bridge/reporte_dashboard.py): periodo, flechas,
# programa, mes/año, panel del día, error con reintento y respuestas tardías,
# con cliente doble y ejecución síncrona.

import json
import os
import sys
from datetime import date
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from autoclave.ui_qml.bridge.reporte_dashboard import ReporteDashboard
from autoclave.utils.periodos import PERIODOS_REPORTES

_HOY = date(2026, 11, 2)
_CLAVES = json.loads((Path(__file__).resolve().parents[1]
                      / "docs/informes/dashboard_reportes/claves_i18n_reportes.json").read_text(encoding="utf-8"))


def _t(clave, idioma=None, **params):
    texto = _CLAVES.get(idioma or "es", _CLAVES["es"]).get(clave)
    if texto is None:
        return clave
    for k, v in params.items():
        texto = texto.replace("{" + k + "}", str(v))
    return texto


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QApplication(sys.argv)


class Doble:
    """Cliente doble: registra las llamadas y responde según la ruta."""

    def __init__(self):
        self.llamadas = []
        self.falla = set()
        self.programa_resuelto = None
        self.estado_dia = "exito"

    def get(self, ruta, params=None, **kw):
        self.llamadas.append((ruta, dict(params or {})))
        if ruta in self.falla:
            raise ConnectionError(ruta)
        p = params or {}
        if ruta == "/report/dashboard":
            periodo = p["periodo"]
            fecha = date.fromisoformat(p["fecha"])
            desde = {"anio": fecha.replace(month=1, day=1), "mes": fecha.replace(day=1)}.get(periodo, fecha)
            return {"periodo": periodo, "desde": desde.isoformat(), "hasta": fecha.isoformat(),
                    "anterior": {"desde": "2026-09-01", "hasta": "2026-09-30"},
                    "indicadores": {"total": 4, "completados": 3, "fallos": 1, "cancelados": 0, "sin_cierre": 0,
                                    "exito_pct": 75, "duracion_media_s": 1800.0, "duraciones_excluidas": 0},
                    "indicadores_anterior": None, "serie": [], "por_programa": [], "causas_fallo": [],
                    "alarmas": [], "operadores": [], "operadores_otros": None}
        if ruta == "/report/calendar":
            return {"periodo": p["periodo"], "programas": [{"numero": 1, "programa_id": "bd", "nombre": "B&D"},
                                                            {"numero": 3, "programa_id": "t", "nombre": "Textiles"}],
                    "programa": self.programa_resuelto or p.get("programa"),
                    "dias": [{"fecha": "2026-11-01", "estado": "exito", "intentos": 1, "exitos": 1}]}
        if ruta == "/report/day-cycles":
            return {"fecha": p["fecha"], "estado": self.estado_dia,
                    "ciclos": [{"id": 7, "numero_ciclo": 12, "fecha_inicio": "2026-11-01T08:00:00",
                                "fecha_fin": "2026-11-01T09:00:00", "resultado": "COMPLETADO"}]}
        if ruta == "/maintenance":
            return {"estado": "ok", "ciclos_restantes": 600, "ultimo_fecha": "2026-06-01", "ultimo_tipo": "preventivo",
                    "configuracion": {"intervalo_dias": 365, "intervalo_ciclos": 1000}}
        if ruta == "/maintenance/records":
            return {"registros": [{"fecha": "2026-06-01", "usuario": "tec", "tipo": "preventivo", "observaciones": ""}]}
        raise AssertionError(ruta)


def _nuevo(doble=None, pendientes=None):
    doble = doble or Doble()
    ejecutar = (lambda tarea: pendientes.append(tarea)) if pendientes is not None else (lambda tarea: tarea())
    r = ReporteDashboard(doble, ejecutar=ejecutar, hoy=lambda: _HOY, idioma=lambda: "es", t=_t)
    return r, doble


def _rutas(doble, ruta):
    return [p for r, p in doble.llamadas if r == ruta]


def test_estado_inicial_mes_actual_programa_1():
    r, _ = _nuevo()
    assert (r.periodo, r.fecha, r.programa, r.esPeriodoActual, r.puedeSiguiente) == ("mes", "2026-11-02", 1, True, False)
    assert r.periodosValidos == list(PERIODOS_REPORTES) and not r.cargando and not r.hayError
    assert r.datos["valido"] is False and r.hayCiclos is False


def test_consultar_pide_todo_y_arma_datos():
    r, d = _nuevo()
    r.consultar()
    assert _rutas(d, "/report/dashboard") == [{"periodo": "mes", "fecha": "2026-11-02"}]
    assert _rutas(d, "/report/calendar") == [{"periodo": "mes", "fecha": "2026-11-02", "programa": 1}]
    assert len(_rutas(d, "/maintenance")) == 1 and len(_rutas(d, "/maintenance/records")) == 1
    assert r.datos["valido"] and r.datos["encabezado"]["titulo"] == "Noviembre 2026" and r.hayCiclos
    assert r.datos["indicadores"][0]["valor"] == "4" and not r.cargando and not r.hayError
    assert r.mantenimiento["disponible"] and r.mantenimiento["ultimo_texto"].startswith("Último preventivo: 01/06/2026")
    assert r.datos["indicadores"][0]["comparacion"]["sin_datos"]


def test_anterior_y_siguiente_no_pasa_del_actual():
    r, d = _nuevo()
    r.consultar()
    r.siguiente()
    assert len(_rutas(d, "/report/dashboard")) == 1 and r.puedeSiguiente is False     # sin efecto en el actual
    r.anterior()
    assert r.fecha == "2026-10-01" and r.puedeSiguiente and not r.esPeriodoActual
    assert _rutas(d, "/report/dashboard")[-1] == {"periodo": "mes", "fecha": "2026-10-01"}
    r.siguiente()
    assert r.fecha == "2026-11-02" and r.esPeriodoActual                              # llega a hoy y se detiene
    n = len(_rutas(d, "/report/dashboard"))
    r.siguiente()
    assert len(_rutas(d, "/report/dashboard")) == n


@pytest.mark.parametrize("periodo", PERIODOS_REPORTES)
def test_cambiar_periodo_valido(periodo):
    r, d = _nuevo()
    r.cambiarPeriodo(periodo)
    assert r.periodo == periodo and _rutas(d, "/report/dashboard")[-1]["periodo"] == periodo
    assert _rutas(d, "/report/calendar")[-1]["periodo"] == periodo


def test_cambiar_periodo_invalido_se_ignora():
    r, d = _nuevo()
    r.cambiarPeriodo("decada")
    r.cambiarPeriodo("")
    assert d.llamadas == [] and r.periodo == "mes"


def test_anio_anterior_y_siguiente():
    r, d = _nuevo()
    r.cambiarPeriodo("anio")
    r.anterior()
    assert r.fecha == "2025-01-01" and _rutas(d, "/report/dashboard")[-1] == {"periodo": "anio", "fecha": "2025-01-01"}
    r.siguiente()
    assert r.fecha == "2026-11-02"


def test_elegir_programa_vuelve_a_pedir_con_el_numero():
    r, d = _nuevo()
    r.consultar()
    r.elegirPrograma(3)
    assert r.programa == 3 and _rutas(d, "/report/calendar")[-1]["programa"] == 3
    n = len(d.llamadas)
    r.elegirPrograma(3)       # el mismo: sin consulta
    r.elegirPrograma(0)       # inválido
    assert len(d.llamadas) == n


def test_programa_resuelto_por_el_backend():
    d = Doble()
    d.programa_resuelto = 3          # no hay 01: el backend cae al primero disponible
    r, _ = _nuevo(d)
    r.consultar()
    assert r.programa == 3


def test_elegir_mes_desde_anio_y_ver_anio():
    r, d = _nuevo()
    r.cambiarPeriodo("anio")
    assert not r.puedeVerAnio
    r.elegirMes(12)                  # futuro: nada
    assert r.periodo == "anio"
    r.elegirMes(5)
    assert (r.periodo, r.fecha, r.puedeVerAnio) == ("mes", "2026-05-01", True)
    assert _rutas(d, "/report/dashboard")[-1] == {"periodo": "mes", "fecha": "2026-05-01"}
    r.elegirMes(6)                   # fuera de la vista de año: ignorado
    assert r.fecha == "2026-05-01"
    r.verAnio()
    assert (r.periodo, r.puedeVerAnio) == ("anio", False)
    r.elegirMes(11)                  # mes actual: usa hoy
    assert r.fecha == "2026-11-02"


def test_mover_desde_vista_de_mes_quita_ver_anio():
    r, _ = _nuevo()
    r.cambiarPeriodo("anio")
    r.elegirMes(5)
    r.anterior()
    assert not r.puedeVerAnio


def test_elegir_dia_consulta_day_cycles():
    r, d = _nuevo()
    r.consultar()
    r.elegirDia("2026-11-01")
    assert _rutas(d, "/report/day-cycles") == [{"programa": 1, "fecha": "2026-11-01"}]
    assert r.diaElegido == "2026-11-01" and not r.cargandoDia and not r.errorDia
    assert r.panelDia["estado"] == "exito" and r.panelDia["titulo"] == "Domingo 1 de noviembre"
    assert len(r.ciclosDia) == 1 and r.ciclosDia[0]["resultado"] if "resultado" in r.ciclosDia[0] else True
    r.cerrarDia()
    assert r.diaElegido == "" and r.ciclosDia == [] and r.panelDia == {}


def test_elegir_dia_invalido_se_ignora():
    r, d = _nuevo()
    r.elegirDia("no-es-fecha")
    r.elegirDia("")
    assert d.llamadas == [] and r.diaElegido == ""


def test_dia_faltó_pide_cuantos_ciclos_hubo():
    d = Doble()
    d.estado_dia = "falto"
    r, _ = _nuevo(d)
    r.consultar()
    r.elegirDia("2026-11-01")
    assert _rutas(d, "/report/dashboard")[-1] == {"periodo": "dia", "fecha": "2026-11-01"}
    assert r.panelDia["explicacion"] == "No se ejecutó Bowie & Dick. El equipo realizó 4 ciclos de otros programas ese día."


def test_cambiar_periodo_o_programa_cierra_el_dia():
    r, _ = _nuevo()
    r.consultar()
    r.elegirDia("2026-11-01")
    r.cambiarPeriodo("semana")
    assert r.diaElegido == ""
    r.elegirDia("2026-11-01")
    r.elegirPrograma(3)
    assert r.diaElegido == ""


def test_error_del_dashboard_y_reintentar():
    d = Doble()
    d.falla = {"/report/dashboard"}
    r, _ = _nuevo(d)
    r.consultar()
    assert r.hayError and r.textoError == "No se pudieron cargar los datos" and r.textoReintentar == "Reintentar"
    assert not r.cargando and r.datos["valido"] is False
    d.falla = set()
    r.reintentar()
    assert not r.hayError and r.datos["valido"]


def test_error_del_calendario_tambien_es_error():
    d = Doble()
    d.falla = {"/report/calendar"}
    r, _ = _nuevo(d)
    r.consultar()
    assert r.hayError


def test_sin_sesion_el_mantenimiento_sigue():
    d = Doble()
    d.falla = {"/maintenance/records"}       # 401/403 sin sesión
    r, _ = _nuevo(d)
    r.consultar()
    assert not r.hayError and r.mantenimiento["disponible"] and r.mantenimiento["registros_disponibles"] is False
    d.falla = {"/maintenance", "/maintenance/records"}
    r.reintentar()
    assert not r.hayError and r.mantenimiento["disponible"] is False


def test_error_dia_y_respuesta_tardia_descartada():
    d = Doble()
    d.falla = {"/report/day-cycles"}
    r, _ = _nuevo(d)
    r.consultar()
    r.elegirDia("2026-11-01")
    assert r.errorDia and not r.cargandoDia and r.ciclosDia == []

    pend = []
    r2, d2 = _nuevo(pendientes=pend)
    r2.cambiarPeriodo("semana")
    r2.cambiarPeriodo("dia")            # la primera queda atrás
    assert r2.cargando and len(pend) == 2
    pend[1]()
    assert not r2.cargando and r2.datos["encabezado"]["periodo"] == "dia"
    pend[0]()                            # llega tarde: se descarta
    assert r2.datos["encabezado"]["periodo"] == "dia"


def test_respuesta_tardia_del_dia_se_descarta():
    pend = []
    r, d = _nuevo(pendientes=pend)
    r.cambiarPeriodo("mes")
    pend.pop()()
    r.elegirDia("2026-11-01")
    r.cerrarDia()
    pend.pop()()
    assert r.panelDia == {} and r.diaElegido == ""


def test_actualizar_idioma_rearma_sin_consultar():
    r, d = _nuevo()
    r.consultar()
    n = len(d.llamadas)
    r.actualizarIdioma()
    assert len(d.llamadas) == n and r.datos["valido"]


def test_slots_y_propiedades_publicas_para_qml():
    r, _ = _nuevo()
    mo = r.metaObject()
    slots = {mo.method(i).name().data().decode() for i in range(mo.methodCount())}
    for s in ("consultar", "reintentar", "cambiarPeriodo", "anterior", "siguiente", "elegirPrograma", "elegirDia",
              "cerrarDia", "elegirMes", "verAnio", "actualizarIdioma"):
        assert s in slots, s
    props = {mo.property(i).name() for i in range(mo.propertyCount())}
    for p in ("periodo", "fecha", "periodosValidos", "esPeriodoActual", "puedeSiguiente", "puedeVerAnio", "cargando",
              "hayError", "textoError", "textoReintentar", "datos", "mantenimiento", "hayCiclos", "programa",
              "diaElegido", "panelDia", "ciclosDia", "cargandoDia", "errorDia"):
        assert p in props, p

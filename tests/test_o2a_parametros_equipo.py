# tests/test_o2a_parametros_equipo.py
#
# O2a (tanda 6): Parámetros del equipo completos. Archivo de fábrica, tabla
# system_params, endpoints con token/rol/auditoría/409, aplicado sin reiniciar,
# alias de erratas y matriz de permisos por rol (decisión 1.9).

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autoclave.core.managers.config_manager import ALIAS, ConfigManager, ErrorParametro

RAIZ = Path(__file__).resolve().parents[1] / "src" / "autoclave"
FABRICA = json.loads((RAIZ / "config" / "global_params.json").read_text(encoding="utf-8"))

# planeacion_opciones.md v4 §3.2 y O2a de la instrucción de la tanda 6
ESPERADO = {
    "timeout_puerta": ("puerta", 60, 5, 600),
    "temp_max_apertura": ("puerta", 80, 40, 120),
    "rango_presion_atm": ("puerta", 5, 1, 10),
    "intervalo_impresion": ("impresion", 60, 10, 3600),
    "intervalo_impresion_esterilizacion": ("impresion", 30, 10, 3600),
    "temp_segura_drenaje": ("drenaje", 70, 40, 90),
    "rango_temp_drenaje": ("drenaje", 5, 1, 20),
    "presion_empaque": ("empaque", 300, 100, 400),
    "vacio_empaque": ("empaque", 30, 0, 100),
    "timeout_chaqueta": ("chaqueta", 60, 10, 180),
    "tiempo_standby": ("sistema", 10, 0, 60),
    "tiempo_estable_alarma": ("sistema", 5, 1, 60),
}


# ── archivo de fábrica ─────────────────────────────────────────────────────

@pytest.mark.parametrize("clave", sorted(ESPERADO))
def test_defectos_rangos_y_submenu(clave):
    grupo, defecto, minimo, maximo = ESPERADO[clave]
    e = FABRICA[clave]
    assert (e["grupo"], e["value"], e["min"], e["max"]) == (grupo, defecto, minimo, maximo)


def test_sin_temp_max_tipo_puerta_ni_erratas():
    for clave in ("temp_max", "tipo_puerta", *ALIAS):
        assert clave not in FABRICA


def test_presion_atmosferica_solo_lectura_y_contadores_fuera():
    assert FABRICA["presion_atmosferica"]["solo_lectura"] is True
    assert "ciclos_servicio" not in FABRICA and "dias_servicio" not in FABRICA


def test_timeout_puerta_e_intervalos_sin_cero():
    for clave in ("timeout_puerta", "intervalo_impresion", "intervalo_impresion_esterilizacion"):
        assert FABRICA[clave]["min"] > 0


# ── ConfigManager ──────────────────────────────────────────────────────────

@pytest.fixture
def cm():
    c = ConfigManager()
    c.load_config()
    return c


@pytest.fixture
def db(tmp_path):
    from autoclave.services.domain.logging.db_manager import DbManager
    d = DbManager(db_path=tmp_path / "t.db")
    yield d
    d.close()


def test_alias_de_erratas(cm):
    assert cm.get("presion_admosferica") == cm.get("presion_atmosferica") == 75
    assert cm.get("intervalo_imprecion_esterilizacion") == 30


def test_sin_bd_no_se_puede_cambiar(cm):
    with pytest.raises(ErrorParametro) as e:
        cm.fijar("timeout_puerta", 90)
    assert e.value.codigo == "sin_base_de_datos"
    assert cm.get("timeout_puerta") == 60


def test_siembra_persiste_y_recarga(cm, db):
    cm.vincular_bd(db)
    filas = db.listar_parametros_sistema()
    assert set(filas) == {c for c, e in FABRICA.items()}
    anterior, nuevo = cm.fijar("timeout_puerta", 120, "tec")
    assert (anterior, nuevo) == (60, 120) and cm.get("timeout_puerta") == 120
    otro = ConfigManager(); otro.load_config(); otro.vincular_bd(db)
    assert otro.get("timeout_puerta") == 120
    d = otro.describir("timeout_puerta")
    assert d["defecto"] == 60 and d["ultima_modificacion"]["usuario"] == "tec"


@pytest.mark.parametrize("clave,valor,codigo", [
    ("timeout_puerta", 0, "fuera_de_rango"), ("timeout_puerta", 601, "fuera_de_rango"),
    ("temp_max_apertura", 121, "fuera_de_rango"), ("presion_empaque", 99, "fuera_de_rango"),
    ("vacio_empaque", 101, "fuera_de_rango"), ("tiempo_standby", 61, "fuera_de_rango"),
    ("timeout_chaqueta", 9, "fuera_de_rango"), ("timeout_puerta", 60.5, "tipo_invalido"),
    ("timeout_puerta", True, "tipo_invalido"), ("timeout_puerta", float("nan"), "tipo_invalido"),
    ("presion_atmosferica", 80, "solo_lectura"), ("no_existe", 1, "no_existe"),
])
def test_rechazos(cm, db, clave, valor, codigo):
    cm.vincular_bd(db)
    with pytest.raises(ErrorParametro) as e:
        cm.fijar(clave, valor)
    assert e.value.codigo == codigo


def test_suspension_cero_permitida(cm, db):
    cm.vincular_bd(db)
    assert cm.fijar("tiempo_standby", 0)[1] == 0


def test_restablecer(cm, db):
    cm.vincular_bd(db)
    cm.fijar("vacio_empaque", 50)
    assert cm.restablecer("vacio_empaque")[1] == 30


def test_fila_fuera_de_rango_se_ignora(cm, db):
    db.guardar_parametro_sistema("timeout_puerta", 9999, 60, 5, 600, "x", "2026-01-01T00:00:00")
    cm.vincular_bd(db)
    assert cm.get("timeout_puerta") == 60


def test_fila_con_errata_se_toma(cm, db):
    db.guardar_parametro_sistema("presion_admosferica", 74.2, 75, 50, 110, "cal", "2026-01-01T00:00:00")
    cm.vincular_bd(db)
    assert cm.get("presion_atmosferica") == 74.2


def test_calibracion_puede_fijar_la_atmosferica(cm, db):
    cm.vincular_bd(db)
    assert cm.fijar("presion_atmosferica", 74.6, "cal", permitir_solo_lectura=True)[1] == 74.6


def test_validacion_de_arranque_sigue_aceptando_fabrica(cm):
    from autoclave.core.managers.validacion_config import errores_config_arranque
    assert errores_config_arranque(cm) == []


# ── OPC-11: lectores que copiaban en __init__ ─────────────────────────────

def test_preparado_lee_tiempo_estable_vigente():
    from autoclave.state_machine.states.preparado import preparado_state as Preparado
    p = Preparado.__new__(Preparado)
    valores = {"tiempo_estable_alarma": 5}
    p.config = MagicMock(); p.config.get.side_effect = lambda k: valores.get(k)
    assert p.tiempo_estable == 5
    valores["tiempo_estable_alarma"] = 30
    assert p.tiempo_estable == 30
    valores["tiempo_estable_alarma"] = None
    assert p.tiempo_estable == 5.0                 # TMG-03


def test_409_deshace_la_escritura(api):
    """TMG-01: si el ciclo arranca entre la escritura y el guard, se revierte."""
    client, srv, ctx, cab = api
    _ciclo(ctx)
    client.patch("/global_params/timeout_puerta", json={"valor": 90}, headers=cab(srv, "tecnico"))
    assert ctx.db.listar_parametros_sistema()["timeout_puerta"]["valor"] == 60


def test_suspension_cero_desactiva():
    from autoclave.ui_qml.bridge.standby import MINUTOS_DEFECTO, debe_estar_en_standby, minutos_standby
    assert MINUTOS_DEFECTO == 10 and minutos_standby(0) == 0
    assert debe_estar_en_standby(True, 1e9, 1e9, 0, "PREPARADO") is False


# ── API: matriz por rol ────────────────────────────────────────────────────

@pytest.fixture
def api(tmp_path):
    from fastapi.testclient import TestClient
    from autoclave.core.runtime.config_idioma import ConfigIdioma
    from autoclave.core.runtime.unidades import ConfigUnidades
    from autoclave.services.domain.logging.db_manager import DbManager
    from autoclave.state_machine.machine.enum_global import GlobalState
    from tests.backend_doble import cabecera, cargar_servidor
    ctx = MagicMock()
    ctx.db = DbManager(db_path=tmp_path / "t.db")
    c = ConfigManager(); c.load_config(); c.vincular_bd(ctx.db)
    ctx.config_manager = c
    ctx.config_idioma = ConfigIdioma(tmp_path / "idioma.json")
    ctx.config_unidades = ConfigUnidades(tmp_path / "unidades.json")
    ctx.sin_base_de_datos = False
    srv, _ = cargar_servidor(ctx)
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    yield TestClient(srv.app), srv, ctx, cabecera
    ctx.db.close()


def _ciclo(ctx):
    from autoclave.state_machine.machine.enum_global import GlobalState
    ctx.estado.get_machine_state.return_value = GlobalState.CICLO


ROLES = ["operador", "admin", "tecnico", "ingeniero"]


@pytest.mark.parametrize("rol", ROLES)
def test_matriz_patch(api, rol):
    client, srv, ctx, cab = api
    r = client.patch("/global_params/timeout_puerta", json={"valor": 90}, headers=cab(srv, rol))
    if rol in ("tecnico", "ingeniero"):
        assert r.status_code == 200 and r.json()["parametro"]["valor"] == 90
        assert ctx.config_manager.get("timeout_puerta") == 90          # sin reiniciar
        filas = ctx.db.get_auditoria(evento="param_sistema_cambio")
        assert filas and filas[0]["usuario"] == f"usuario_{rol}"
        assert json.loads(filas[0]["valor_anterior"]) == {"timeout_puerta": 60}
    else:
        assert r.status_code == 403 and ctx.config_manager.get("timeout_puerta") == 60


@pytest.mark.parametrize("rol", ROLES)
def test_matriz_reset(api, rol):
    client, srv, ctx, cab = api
    ctx.config_manager.fijar("vacio_empaque", 55)
    r = client.post("/global_params/vacio_empaque/reset", headers=cab(srv, rol))
    assert r.status_code == (200 if rol in ("tecnico", "ingeniero") else 403)
    assert ctx.config_manager.get("vacio_empaque") == (30 if r.status_code == 200 else 55)


def test_sin_token_401(api):
    client, *_ = api
    assert client.patch("/global_params/timeout_puerta", json={"valor": 90}).status_code == 401
    assert client.post("/global_params/timeout_puerta/reset").status_code == 401


@pytest.mark.parametrize("rol", ["tecnico", "ingeniero"])
def test_409_en_ciclo_tambien_ingeniero(api, rol):
    client, srv, ctx, cab = api
    _ciclo(ctx)
    r = client.patch("/global_params/timeout_puerta", json={"valor": 90}, headers=cab(srv, rol))
    assert r.status_code == 409 and ctx.config_manager.get("timeout_puerta") == 60
    assert client.post("/global_params/timeout_puerta/reset", headers=cab(srv, rol)).status_code == 409


def test_errores_de_valor(api):
    client, srv, ctx, cab = api
    h = cab(srv, "tecnico")
    r = client.patch("/global_params/timeout_puerta", json={"valor": 0}, headers=h)
    assert r.status_code == 422 and r.json()["codigo"] == "fuera_de_rango" and r.json()["min"] == 5
    assert client.patch("/global_params/timeout_puerta", json={"valor": "90"}, headers=h).status_code == 422
    assert client.patch("/global_params/timeout_puerta", json={"valor": True}, headers=h).status_code == 422
    assert client.patch("/global_params/nada", json={"valor": 1}, headers=h).status_code == 404
    r = client.patch("/global_params/presion_atmosferica", json={"valor": 80}, headers=cab(srv, "ingeniero"))
    assert r.status_code == 403 and ctx.config_manager.get("presion_atmosferica") == 75
    assert client.patch("/global_params/presion_admosferica", json={"valor": 80}, headers=h).status_code == 403


def test_lectura_libre(api):
    client, *_ = api
    lista = client.get("/system_params").json()["parametros"]
    assert {p["clave"] for p in lista} == set(FABRICA)
    assert client.get("/global_params/temp_max_apertura").json()["max"] == 120
    assert client.get("/global_params").json()["timeout_chaqueta"]["value"] == 60


@pytest.mark.parametrize("rol,esperado", [("operador", 403), ("admin", 200), ("tecnico", 403),
                                          ("ingeniero", 200)])
def test_matriz_idioma(api, rol, esperado):
    client, srv, ctx, cab = api
    _ciclo(ctx)                                    # permitido en ciclo
    assert client.put("/language", json={"idioma": "en"}, headers=cab(srv, rol)).status_code == esperado


@pytest.mark.parametrize("rol,esperado", [("operador", 403), ("admin", 403), ("tecnico", 403),
                                          ("ingeniero", 200)])
def test_matriz_unidades(api, rol, esperado):
    client, srv, ctx, cab = api
    r = client.put("/units", json={"temperatura": "F", "presion": "psi"}, headers=cab(srv, rol))
    assert r.status_code == esperado


def test_unidades_ingeniero_409_en_ciclo(api):
    client, srv, ctx, cab = api
    _ciclo(ctx)
    r = client.put("/units", json={"temperatura": "F", "presion": "psi"}, headers=cab(srv, "ingeniero"))
    assert r.status_code == 409


# ── UI: controlador y pantalla ─────────────────────────────────────────────

def _lista_fabrica():
    c = ConfigManager(); c.load_config()
    return c.describir()


class _SesionUI:
    def __init__(self, respuesta=None):
        from autoclave.ui_qml.sesion_backend import Resultado
        self.R = Resultado
        self.respuesta = respuesta
        self.enviados = []
        self.lista = _lista_fabrica()

    def enviar(self, metodo, ruta, cuerpo=None):
        self.enviados.append((metodo, ruta, cuerpo))
        if metodo == "GET":
            datos = {"/system_params": {"parametros": self.lista},
                     "/printer/config": {"habilitada": True},
                     "/units": {"temperatura": "C", "presion": "kPa"},
                     "/language": {"idioma": "es"}}.get(ruta, {})
            return self.R("ok", datos, 200)
        return self.respuesta or self.R("ok", {"ok": True}, 200)


def _ctrl_ui(sesion=None):
    import sys as _sys
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(_sys.argv)
    from autoclave.ui_qml.controllers.parametros_equipo_controller import ParametrosEquipoController

    class Perfil:
        serial_number, model_id = "S-1", "M-1"
    s = sesion or _SesionUI()
    c = ParametrosEquipoController(sesion=s, perfil=lambda: Perfil())
    c.cargar()
    return c, s


def test_controlador_grupos_y_datos():
    c, _ = _ctrl_ui()
    assert c.grupos == ["puerta", "impresion", "drenaje", "empaque", "chaqueta", "sistema", "maquina"]
    assert [p["clave"] for p in c.delGrupo("puerta")] == ["timeout_puerta", "temp_max_apertura",
                                                         "rango_presion_atm"]
    assert {p["clave"] for p in c.delGrupo("sistema")} == {"tiempo_standby", "tiempo_estable_alarma",
                                                           "presion_atmosferica"}
    assert c.numeroSerie == "S-1" and c.modelo == "M-1" and c.idioma == "es"
    c.abrirGrupo("puerta")
    assert c.grupo == "puerta" and c.volver() and c.grupo == "" and not c.volver()


def test_controlador_envia_patch_entero_y_reset():
    c, s = _ctrl_ui()
    assert c.guardar("timeout_puerta", 90.0)
    assert ("PATCH", "/global_params/timeout_puerta", {"valor": 90}) in s.enviados
    assert c.restablecer("vacio_empaque")
    assert ("POST", "/global_params/vacio_empaque/reset", None) in s.enviados


@pytest.mark.parametrize("causa,clave", [("estado_no_permitido", "opciones.equipo_err_ciclo"),
                                         ("rol_sin_permiso", "opciones.err_rol"),
                                         ("fuera_de_rango", "opciones.equipo_err_rango")])
def test_controlador_rechazo(causa, clave):
    from autoclave.ui_qml.sesion_backend import Resultado
    c, _ = _ctrl_ui(_SesionUI(Resultado(causa)))
    assert not c.guardar("timeout_puerta", 90)
    assert c.mensaje == clave


@pytest.mark.parametrize("rol,estado,param,idioma,unidades", [
    ("admin", "PREPARADO", "rol", "", "rol"),
    ("tecnico", "PREPARADO", "", "rol", "rol"),
    ("tecnico", "CICLO", "ciclo", "rol", "rol"),
    ("ingeniero", "PREPARADO", "", "", ""),
    ("ingeniero", "CICLO", "ciclo", "", "ciclo"),
    ("operador", "PREPARADO", "rol", "rol", "rol"),
])
def test_matriz_permisos_ui(rol, estado, param, idioma, unidades):
    c, _ = _ctrl_ui()
    c.rol, c.estadoMaquina = rol, estado
    assert (c.motivoParametro, c.motivoIdioma, c.motivoUnidades) == (param, idioma, unidades)


def test_textos_es_en():
    for lang in ("es", "en"):
        d = json.loads((RAIZ / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))
        for clave in FABRICA:
            assert d["parametros_equipo"][clave] and d["parametros_equipo_desc"][clave], (lang, clave)
        for g in ("puerta", "impresion", "drenaje", "empaque", "chaqueta", "sistema", "maquina"):
            assert d["opciones"]["equipo_grupos"][g] and d["opciones"]["equipo_grupos_desc"][g]


_GUION_QML = r"""
import json, sys
sys.path.insert(0, "src"); sys.path.insert(0, ".")
from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
import autoclave.ui_qml.bridge.i18n_qml  # noqa
import autoclave.ui_qml.bridge.unidades_qml  # noqa
import autoclave.ui_qml.controllers  # noqa
from autoclave.ui_qml import sesion_backend
from tests.test_o2a_parametros_equipo import _SesionUI
sesion_backend.ventana = lambda: _SesionUI()
qml_dir, rol = sys.argv[1], sys.argv[2]
app = QGuiApplication([])
e = QQmlEngine(); e.addImportPath(qml_dir)
avisos = []
e.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
c = QQmlComponent(e)
c.setData(('import QtQuick\nimport "Pantallas"\nItem { width: 1100; height: 1500; '
           'OpcionesParametrosEquipo { objectName: "p"; anchors.fill: parent; '
           'edicionPermitida: %s; rol: "%s"; estadoMaquina: "PREPARADO" } }'
           % ("false" if rol == "admin" else "true", rol)).encode(),
          QUrl.fromLocalFile(qml_dir + "/prueba_o2a.qml"))
raiz = c.create()
assert raiz is not None, c.errorString()
from PySide6.QtQuick import QQuickItem as _QI
p = raiz.findChild(_QI, "p")
ctrl = p.findChild(QObject, "parametrosEquipoController")
def buscar(item, nombre):
    if item.objectName() == nombre:
        return item
    for h in item.childItems():
        r = buscar(h, nombre)
        if r is not None:
            return r
    return None
r = {"tarjetas": sum(1 for g in ctrl.property("grupos") if buscar(p, "tarjeta_" + g) is not None)}
ctrl.abrirGrupo("puerta"); app.processEvents()
fila = buscar(p, "paramEquipo_temp_max_apertura")
r["fila"] = fila is not None and fila.property("valor")
r["chevron"] = fila.property("chevron")
ctrl.abrirGrupo("maquina"); app.processEvents()
r["idioma"] = p.findChild(QObject, "selector_idioma").property("habilitado")
r["unidades"] = p.findChild(QObject, "selector_presion").property("habilitado")
r["serie"] = p.findChild(QObject, "serieEquipo") is not None
r["avisos"] = [a for a in avisos if "sesion" not in a.lower()]
print(json.dumps(r))
"""


@pytest.mark.parametrize("rol,chevron,idioma,unidades", [("admin", False, True, False),
                                                         ("tecnico", True, False, False),
                                                         ("ingeniero", True, True, True)])
def test_pantalla_por_rol(rol, chevron, idioma, unidades):
    import os
    import subprocess
    import sys as _sys
    pytest.importorskip("PySide6")
    raiz = Path(__file__).resolve().parents[1]
    r = subprocess.run([_sys.executable, "-c", _GUION_QML, str(RAIZ / "ui_qml" / "qml"), rol],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=raiz, timeout=90, env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert r.returncode == 0, r.stderr[-2000:]
    d = json.loads(r.stdout.strip().splitlines()[-1])
    assert d["tarjetas"] == 7 and d["fila"] and d["serie"]
    assert (d["chevron"], d["idioma"], d["unidades"]) == (chevron, idioma, unidades)
    assert d["avisos"] == []


@pytest.mark.parametrize("clave,valor", [("presion_empaque", 100), ("presion_empaque", 120),
                                         ("vacio_empaque", 70), ("vacio_empaque", 100)])
def test_empaque_incoherente_con_atm(cm, db, clave, valor):
    """SAF-01 de O2a: con atm 75 kPa, la puerta no puede darse por sellada sin estarlo."""
    cm.vincular_bd(db)
    with pytest.raises(ErrorParametro) as e:
        cm.fijar(clave, valor)
    assert e.value.codigo == "incoherente"


def test_empaque_coherente(cm, db):
    cm.vincular_bd(db)
    assert cm.fijar("presion_empaque", 150)[1] == 150 and cm.fijar("vacio_empaque", 65)[1] == 65

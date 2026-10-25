"""V8a (tanda 8): D8-5.7 (tipo de carga Sólido/Líquido) y D8-5.8 (modos de
la lista de modos válidos), lado backend.

D8-5.7 (Cristian, 22-oct 12:08):
  - al pasar a Líquido el modo de descompresión cambia a 4;
  - con carga líquida solo se permiten los modos 4, 5 y 0, también en el
    backend: cualquier otro se rechaza con su motivo (ebullición violenta);
  - al volver a Sólido, el modo vuelve al defecto de ese programa; si el
    programa no tiene un defecto sólido, modo 1 (DECISIÓN SIN CONFIRMAR);
  - cada cambio, incluido el automático, queda en la bitácora.
"""

import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autoclave.core.managers import catalogo_parametros as cp
from autoclave.core.managers.cycle_manager import CycleManager
from tests.helpers.backend_doble import fijar_en_backend, modulo_backend

RAIZ = Path(__file__).resolve().parents[1]


# ── Catálogo ────────────────────────────────────────────────────────────────

def _params(tipo, modo):
    return {"globals": {"tipo_carga": {"value": tipo}},
            "descompresion": {"modo": {"value": modo},
                              "modo_4": {"presion_camara_enfriamiento": {"value": 400}},
                              "modo_5": {"presion_camara_enfriamiento": {"value": 400}}},
            "esterilizacion": {"temperatura_esterilizacion": {"value": 121.0}}}


@pytest.mark.parametrize("modo", [0, 4, 5])
def test_liquido_admite_4_5_y_0(modo):
    assert cp.errores_coherencia(_params("liquido", modo)) == []


@pytest.mark.parametrize("modo", [1, 2, 3])
def test_liquido_rechaza_1_2_3_con_su_motivo(modo):
    errores = cp.errores_coherencia(_params("liquido", modo))
    assert errores and "ebullición" in errores[0]
    assert cp.codigo_coherencia(errores) == "MODO_NO_PERMITIDO_LIQUIDO"


def test_solido_admite_todos_los_modos():
    for modo in range(6):
        assert cp.errores_coherencia(_params("solido", modo)) == []


def test_modo_0_liquido_no_exige_contrapresion():
    p = _params("liquido", 0)
    p["descompresion"]["modo_4"]["presion_camara_enfriamiento"]["value"] = 1
    assert cp.errores_coherencia(p) == []


def test_modos_validos_por_parametro():
    assert cp.modos_validos(_params("solido", 1), "descompresion", ["modo"]) == [0, 1, 2, 3, 4, 5]
    assert cp.modos_validos(_params("liquido", 4), "descompresion", ["modo"]) == [4, 5, 0]
    assert cp.modos_validos(_params("solido", 1), "secado", ["modo"]) == [1, 2, 3]
    assert cp.modos_validos(_params("solido", 1), "esterilizacion", ["tiempo_esterilizacion"]) == []


# ── Programa: arrastre del modo al cambiar el tipo de carga ───────────────

@pytest.fixture
def cm(tmp_path):
    origen = RAIZ / "src" / "autoclave" / "cycles"
    for sub in ("factory", "user"):
        shutil.copytree(origen / sub, tmp_path / "cycles" / sub)
    m = CycleManager()
    m.raiz = str(tmp_path)
    m.load_all_cycles()
    return m


def _a_liquido_posible(c):
    """Deja un programa sólido en condiciones de pasar a líquido (sin prevacío,
    sin secado, sin apertura automática): lo que exige errores_coherencia."""
    for p in "abcd":
        if c._hoja("prevacio", [f"conteo_pulso_{p}"]) is not None:
            c._hoja("prevacio", [f"conteo_pulso_{p}"])["value"] = 0
    c._hoja("secado", ["tiempo_secado"])["value"] = 0
    if c._hoja("finalizacion", ["apertura_automatica"]) is not None:
        c._hoja("finalizacion", ["apertura_automatica"])["value"] = False
    for m in ("modo_4", "modo_5"):          # contrapresión >= P_sat(T) + 30 kPa
        c._hoja("descompresion", [m, "presion_camara_enfriamiento"])["value"] = 300


def test_arrastre_a_liquido_y_de_vuelta_a_solido(cm):
    c = cm.cycles["instrumental_121"]
    _a_liquido_posible(c)
    assert c.get_param("descompresion", "modo") == 1
    arr = c.arrastres_tipo_carga("liquido", modo_solido=1)
    assert arr == [("descompresion", ["modo"], 4)]
    c.set_param("globals", ["tipo_carga"], "liquido", arrastres=arr)
    assert c.get_param("descompresion", "modo") == 4
    arr = c.arrastres_tipo_carga("solido", modo_solido=1)
    assert arr == [("descompresion", ["modo"], 1)]
    c.set_param("globals", ["tipo_carga"], "solido", arrastres=arr)
    assert c.get_param("descompresion", "modo") == 1


def test_sin_defecto_solido_vuelve_al_modo_1(cm):
    c = cm.cycles["liquidos"]
    assert c.arrastres_tipo_carga("solido", modo_solido=None) == [("descompresion", ["modo"], 1)]


@pytest.mark.parametrize("modo", [0, 5])
def test_a_liquido_con_modo_ya_permitido_no_lo_cambia(cm, modo):
    c = cm.cycles["liquidos"]
    c._hoja("globals", ["tipo_carga"])["value"] = "solido"
    c._hoja("descompresion", ["modo"])["value"] = modo
    assert c.arrastres_tipo_carga("liquido", modo_solido=1) == []


def test_mismo_tipo_no_arrastra(cm):
    c = cm.cycles["134_instrumental"]
    assert c.arrastres_tipo_carga("solido", modo_solido=1) == []


def test_set_param_con_arrastre_es_todo_o_nada(cm):
    """Instrumental 134 tiene prevacío y secado: no puede ser líquido; ni el
    tipo ni el modo cambian."""
    c = cm.cycles["134_instrumental"]
    arr = c.arrastres_tipo_carga("liquido", modo_solido=1)
    with pytest.raises(cp.ErrorCoherencia) as e:
        c.set_param("globals", ["tipo_carga"], "liquido", arrastres=arr)
    assert e.value.codigo == "COHERENCIA_LIQUIDO"
    assert c.get_param("globals", "tipo_carga") == "solido"
    assert c.get_param("descompresion", "modo") == 1


def test_modo_directo_no_permitido_con_liquido(cm):
    c = cm.cycles["liquidos"]
    with pytest.raises(cp.ErrorCoherencia) as e:
        c.set_param("descompresion", ["modo"], 1)
    assert e.value.codigo == "MODO_NO_PERMITIDO_LIQUIDO"
    assert c.get_param("descompresion", "modo") == 4
    assert c.set_param("descompresion", ["modo"], 0) == 0


# ── Endpoint PATCH /cycle/parameter y GET de la sección ───────────────────

@pytest.fixture
def cliente(cm):
    from fastapi.testclient import TestClient
    from tests.helpers.backend_doble import cabecera, cargar_servidor
    ctx = MagicMock()
    ctx.cycle_manager = cm
    ctx.sin_base_de_datos = False
    ctx.db.get_auditoria.return_value = []
    srv, _ = cargar_servidor(ctx)
    return TestClient(srv.app, headers=cabecera(srv, "tecnico")), cm, ctx


def _auditados(ctx):
    # X9 (tanda 9, D9-13.3 SAF-01): el cambio y su arrastre van en un lote
    sueltas = [(c.args[0], c.kwargs.get("entidad"), c.kwargs.get("valor_anterior"),
                c.kwargs.get("valor_nuevo"), c.kwargs.get("detalle") or {})
               for c in ctx.db.registrar_auditoria.call_args_list]
    lote = [(f["evento"], f.get("entidad"), f.get("valor_anterior"), f.get("valor_nuevo"),
             f.get("detalle") or {})
            for c in ctx.db.registrar_auditoria_lote.call_args_list for f in c.args[0]]
    return sueltas + lote


def _patch(client, cycle_id, fase, path, valor):
    return client.patch("/cycle/parameter", json={"cycle_id": cycle_id, "fase": fase,
                                                  "path": path, "value": valor})


def test_endpoint_liquido_a_solido_y_vuelta_con_bitacora(cliente):
    client, cm, ctx = cliente
    r = _patch(client, "liquidos", "globals", ["tipo_carga"], "solido")
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    # Líquidos no tiene defecto sólido: modo 1 (DECISIÓN SIN CONFIRMAR de D8-5.7)
    assert cuerpo["arrastres"] == [{"fase": "descompresion", "path": ["modo"], "clave": "modo",
                                    "anterior": 4, "nuevo": 1}]
    c = cm.cycles["liquidos"]
    assert c.get_param("descompresion", "modo") == 1
    persistido = json.loads(Path(c._path).read_text(encoding="utf-8"))
    assert persistido["parameters"]["descompresion"]["modo"]["value"] == 1
    aud = [a for a in _auditados(ctx) if a[0] == "param_ciclo_cambio"]
    assert ("liquidos/globals/tipo_carga", "liquido", "solido") == aud[0][1:4]
    assert ("liquidos/descompresion/modo", 4, 1) == aud[1][1:4]
    assert aud[1][4]["automatico"] is True and aud[1][4]["causa"] == "liquidos/globals/tipo_carga"

    ctx.db.registrar_auditoria.reset_mock()
    ctx.db.registrar_auditoria_lote.reset_mock()
    r = _patch(client, "liquidos", "globals", ["tipo_carga"], "liquido")
    assert r.status_code == 200, r.text
    assert r.json()["arrastres"][0]["nuevo"] == 4 and c.get_param("descompresion", "modo") == 4
    assert len([a for a in _auditados(ctx) if a[0] == "param_ciclo_cambio"]) == 2


def test_endpoint_vuelta_a_solido_usa_el_defecto_del_programa(cliente):
    client, cm, _ = cliente
    c = cm.cycles["instrumental_121"]
    _a_liquido_posible(c)
    assert _patch(client, "instrumental_121", "globals", ["tipo_carga"], "liquido").status_code == 200
    assert c.get_param("descompresion", "modo") == 4
    assert _patch(client, "instrumental_121", "descompresion", ["modo"], 5).status_code == 200
    r = _patch(client, "instrumental_121", "globals", ["tipo_carga"], "solido")
    assert r.status_code == 200
    defecto = cm.defecto(3).get_param("descompresion", "modo")
    assert c.get_param("descompresion", "modo") == defecto == 1


def test_endpoint_rechaza_modo_no_permitido_con_motivo(cliente):
    client, cm, ctx = cliente
    r = _patch(client, "liquidos", "descompresion", ["modo"], 1)
    assert r.status_code == 422
    assert r.json()["codigo"] == "MODO_NO_PERMITIDO_LIQUIDO"
    assert "ebullición" in r.json()["detail"]
    assert cm.cycles["liquidos"].get_param("descompresion", "modo") == 4
    assert not [a for a in _auditados(ctx) if a[0] == "param_ciclo_cambio"]


def test_endpoint_rechaza_pasar_a_liquido_sin_cumplir_el_resto(cliente):
    client, cm, ctx = cliente
    r = _patch(client, "134_instrumental", "globals", ["tipo_carga"], "liquido")
    assert r.status_code == 422 and r.json()["codigo"] == "COHERENCIA_LIQUIDO"
    c = cm.cycles["134_instrumental"]
    assert c.get_param("globals", "tipo_carga") == "solido"
    assert c.get_param("descompresion", "modo") == 1


def test_endpoint_sin_bitacora_del_arrastre_revierte_todo(cliente):
    client, cm, ctx = cliente
    llamadas = []

    def registrar(filas):
        llamadas.extend(f.get("entidad") for f in filas)
        if any(f.get("entidad") == "liquidos/descompresion/modo" for f in filas):
            raise RuntimeError("BD ocupada")
    ctx.db.registrar_auditoria_lote.side_effect = registrar
    r = _patch(client, "liquidos", "globals", ["tipo_carga"], "solido")
    assert r.status_code == 503
    c = cm.cycles["liquidos"]
    assert c.get_param("globals", "tipo_carga") == "liquido"
    assert c.get_param("descompresion", "modo") == 4
    persistido = json.loads(Path(c._path).read_text(encoding="utf-8"))
    assert persistido["parameters"]["globals"]["tipo_carga"]["value"] == "liquido"
    assert persistido["parameters"]["descompresion"]["modo"]["value"] == 4


def test_seccion_entrega_los_modos_validos(cliente):
    client, _, _ = cliente
    p = {x["clave"]: x for x in client.get("/programas/4/seccion/descompresion").json()["parametros"]}
    assert p["modo"]["modos"] == [4, 5, 0]
    p = {x["clave"]: x for x in client.get("/programas/2/seccion/descompresion").json()["parametros"]}
    assert p["modo"]["modos"] == [0, 1, 2, 3, 4, 5]
    assert p["tiempo_pre_despresurizacion"]["modos"] == []
    p = {x["clave"]: x for x in client.get("/programas/2/seccion/secado").json()["parametros"]}
    assert p["modo"]["modos"] == [1, 2, 3]


# ── Controlador de Parámetros del ciclo (aviso del arrastre y motivos) ─────

@pytest.fixture(scope="module")
def qt_app():
    import os
    import sys
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QCoreApplication
    return QCoreApplication.instance() or QCoreApplication(sys.argv)


def _control(qt_app, patch_resultado):
    from autoclave.ui_qml.sesion_backend import Resultado
    from tests.test_t12_opciones_parametros import _Sesion
    programas = {"programas": [{"numero": 4, "cycle_id": "liquidos", "nombre": "Líquidos",
                                "editable": True, "danado": False,
                                "secciones": [{"clave": "globals", "no_se_ejecuta": False}]}]}
    seccion = {"editable": True, "parametros": [
        {"clave": "tipo_carga", "path": ["tipo_carga"], "tipo": "enum", "valor": "liquido",
         "defecto": "liquido", "min": None, "max": None, "unidad": "", "opciones": ["solido", "liquido"],
         "modos": [], "modificado": False, "ultima_modificacion": None}]}
    s = _Sesion({("GET", "/programas"): Resultado("ok", programas, 200),
                 ("GET", "/programas/4/seccion/globals"): Resultado("ok", seccion, 200),
                 ("PATCH", "/cycle/parameter"): patch_resultado})
    from autoclave.ui_qml.controllers.parametros_ciclo_controller import ParametrosCicloController
    c = ParametrosCicloController(sesion=s)
    c.cargar()
    c.abrirSeccion("globals")
    return c


def test_controlador_avisa_del_cambio_automatico_del_modo(qt_app):
    from autoclave.ui_qml.sesion_backend import Resultado
    arrastre = [{"fase": "descompresion", "path": ["modo"], "clave": "modo", "anterior": 4, "nuevo": 1}]
    c = _control(qt_app, Resultado("ok", {"ok": True, "value": "solido", "arrastres": arrastre}, 200))
    assert c.guardar("tipo_carga", "solido") is True
    assert c.aviso == "opciones.aviso_modo_solido" and c.detalleAviso["modo"] == 1
    c.limpiarAviso()
    assert c.aviso == ""


def test_controlador_avisa_al_pasar_a_liquido(qt_app):
    from autoclave.ui_qml.sesion_backend import Resultado
    arrastre = [{"fase": "descompresion", "path": ["modo"], "clave": "modo", "anterior": 1, "nuevo": 4}]
    c = _control(qt_app, Resultado("ok", {"ok": True, "value": "liquido", "arrastres": arrastre}, 200))
    assert c.guardar("tipo_carga", "liquido") is True
    assert c.aviso == "opciones.aviso_modo_liquido" and c.detalleAviso["modo"] == 4


def test_controlador_sin_arrastre_no_avisa(qt_app):
    from autoclave.ui_qml.sesion_backend import Resultado
    c = _control(qt_app, Resultado("ok", {"ok": True, "value": "solido"}, 200))
    assert c.guardar("tipo_carga", "solido") is True and c.aviso == ""


@pytest.mark.parametrize("codigo, clave", [("MODO_NO_PERMITIDO_LIQUIDO", "opciones.err_modo_liquido"),
                                           ("COHERENCIA_LIQUIDO", "opciones.err_coherencia_liquido")])
def test_controlador_muestra_el_motivo_del_rechazo(qt_app, codigo, clave):
    from autoclave.ui_qml.sesion_backend import Resultado
    c = _control(qt_app, Resultado(codigo, {"codigo": codigo}, 422))
    assert c.guardar("tipo_carga", "solido") is False
    assert c.mensaje == clave


# ── Bitácora: el cambio del parámetro y el automático, con texto propio ───

def test_bitacora_presenta_el_cambio_de_parametro_y_el_automatico():
    from autoclave.core.runtime import bitacora
    manual = bitacora.presentar({"evento": "param_ciclo_cambio", "entidad": "liquidos/globals/tipo_carga",
                                 "valor_anterior": '"solido"', "valor_nuevo": '"liquido"',
                                 "detalle": json.dumps({"programa": "liquidos"})}, {}, {})
    assert manual["clave_texto"] == "bitacora.ev.param_ciclo_cambio"
    auto = bitacora.presentar({"evento": "param_ciclo_cambio", "entidad": "liquidos/descompresion/modo",
                               "valor_anterior": "1", "valor_nuevo": "4",
                               "detalle": json.dumps({"automatico": True,
                                                      "causa": "liquidos/globals/tipo_carga"})}, {}, {})
    assert auto["clave_texto"] == "bitacora.ev.param_ciclo_automatico"
    for lang in ("es", "en"):
        d = json.loads((RAIZ / "src" / "autoclave" / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))
        assert d["bitacora"]["ev"]["param_ciclo_cambio"]
        assert d["bitacora"]["ev"]["param_ciclo_automatico"]


# ── Revisión D8-5.7 (timing-auditor TMG-02): el PATCH se serializa y la
# reversión no pisa a ciegas un cambio posterior ──────────────────────────

@pytest.fixture
def servidor(cm):
    from fastapi.testclient import TestClient
    from tests.helpers.backend_doble import cabecera, cargar_servidor
    ctx = MagicMock()
    ctx.cycle_manager = cm
    ctx.sin_base_de_datos = False
    ctx.db.get_auditoria.return_value = []
    srv, _ = cargar_servidor(ctx)
    return TestClient(srv.app, headers=cabecera(srv, "tecnico")), cm, ctx, srv


def test_patch_serializado_hasta_terminar_la_bitacora(servidor):
    client, cm, ctx, srv = servidor
    tomado = []
    ctx.db.registrar_auditoria_lote.side_effect = lambda *a, **k: tomado.append(modulo_backend("dependencias")._lock_param_ciclo.locked())
    assert _patch(client, "liquidos", "globals", ["tipo_carga"], "solido").status_code == 200
    assert tomado and all(tomado)
    assert not modulo_backend("dependencias")._lock_param_ciclo.locked()


def test_reversion_no_pisa_un_cambio_posterior(servidor):
    """Escenario TMG-02: A cambia el modo 1 -> 2 (sólido); antes de que falle
    su bitácora, otro cambio deja el programa en líquido con modo 4. La
    reversión de A no puede devolver el modo a 1 (líquido con modo 1)."""
    client, cm, ctx, _ = servidor
    c = cm.cycles["instrumental_121"]
    _a_liquido_posible(c)
    assert c.get_param("descompresion", "modo") == 1

    hecho = []

    def registrar(filas):
        if filas and filas[0]["evento"] == "param_ciclo_cambio" and not hecho:
            hecho.append(True)
            c.set_param("globals", ["tipo_carga"], "liquido", arrastres=[("descompresion", ["modo"], 4)])
            raise RuntimeError("BD ocupada")
    ctx.db.registrar_auditoria_lote.side_effect = registrar
    r = _patch(client, "instrumental_121", "descompresion", ["modo"], 2)
    assert r.status_code == 503
    assert c.get_param("globals", "tipo_carga") == "liquido"
    assert c.get_param("descompresion", "modo") == 4
    assert cp.errores_coherencia(c.parameters) == []


# ── Revisión D8-5.7 (timing-auditor TMG-01, anterior a D8-5.7): orden único de
# locks _lock_archivos -> _sm_lock; _gestion lo tenía al revés (interbloqueo
# con /cycle/sensor-roles, la calibración y la restauración) ─────────────

def _registrar_orden_de_locks(srv, ctx):
    import contextlib
    import threading
    tenidos, violaciones = [], []
    real = threading.Lock()

    class _Archivos:
        def __enter__(self):
            if "sm" in tenidos:
                violaciones.append("archivos dentro de sm")
            real.acquire()
            tenidos.append("archivos")

        def __exit__(self, *a):
            tenidos.remove("archivos")
            real.release()

    @contextlib.contextmanager
    def bloqueo():
        tenidos.append("sm")
        try:
            yield
        finally:
            tenidos.remove("sm")
    fijar_en_backend("_lock_archivos", _Archivos())
    ctx.control_loop.bloqueo_maquina = bloqueo
    return violaciones


def test_gestion_toma_los_locks_en_el_orden_unico(servidor):
    client, cm, ctx, srv = servidor
    violaciones = _registrar_orden_de_locks(srv, ctx)
    r = client.put("/programas/2/habilitado", json={"habilitado": False})
    assert r.status_code == 200, r.text
    ctx.db.registrar_auditoria.side_effect = RuntimeError("BD ocupada")     # deshacer
    r = client.put("/programas/2/habilitado", json={"habilitado": True})
    assert r.status_code == 503
    assert violaciones == []


# ── Revisión D8-5.7 (SAF-05 / TMG-05): sin respuesta del backend, si el cambio
# sí se aplicó, la pantalla también avisa del cambio automático del modo ──

def test_sin_respuesta_tambien_avisa_del_cambio_automatico(qt_app):
    from autoclave.ui_qml.sesion_backend import BACKEND_NO_RESPONDE, Resultado
    from autoclave.ui_qml.controllers.parametros_ciclo_controller import ParametrosCicloController
    from tests.test_t12_opciones_parametros import _Sesion
    programas = {"programas": [{"numero": 4, "cycle_id": "liquidos", "nombre": "Líquidos",
                                "editable": True, "danado": False,
                                "secciones": [{"clave": "globals", "no_se_ejecuta": False}]}]}

    def seccion(tipo):
        return {"editable": True, "parametros": [
            {"clave": "tipo_carga", "path": ["tipo_carga"], "tipo": "enum", "valor": tipo,
             "defecto": "liquido", "min": None, "max": None, "unidad": "",
             "opciones": ["solido", "liquido"], "modos": [], "modificado": False,
             "ultima_modificacion": None}]}

    def descompresion(modo):
        return {"editable": True, "parametros": [
            {"clave": "modo", "path": ["modo"], "tipo": "int", "valor": modo, "defecto": 4,
             "min": 0, "max": 5, "unidad": "", "opciones": [], "modos": [0, 1, 2, 3, 4, 5],
             "modificado": False, "ultima_modificacion": None}]}
    estado = {"tipo": "liquido", "modo": 4}

    def patch(cuerpo):
        estado.update(tipo="solido", modo=1)          # se aplicó, pero la respuesta no llegó
        return Resultado(BACKEND_NO_RESPONDE)
    s = _Sesion({("GET", "/programas"): Resultado("ok", programas, 200),
                 ("GET", "/programas/4/seccion/globals"): lambda c: Resultado("ok", seccion(estado["tipo"]), 200),
                 ("GET", "/programas/4/seccion/descompresion"):
                     lambda c: Resultado("ok", descompresion(estado["modo"]), 200),
                 ("PATCH", "/cycle/parameter"): patch})
    c = ParametrosCicloController(sesion=s)
    c.cargar()
    c.abrirSeccion("globals")
    assert c.guardar("tipo_carga", "solido") is True
    assert c.aviso == "opciones.aviso_modo_solido" and c.detalleAviso["modo"] == 1


def test_fallo_al_escribir_el_json_revierte_sin_bitacora(servidor):
    """Medio del timing-auditor (re-revisión): si falla la escritura del JSON,
    el cambio tampoco queda en memoria ni en la bitácora."""
    client, cm, ctx, srv = servidor
    llamadas = {"n": 0}
    real = modulo_backend("rutas.parametros_ciclo")._save_cycle_json

    def guardar(cycle):
        llamadas["n"] += 1
        if llamadas["n"] == 1:
            raise OSError("disco lleno")
        real(cycle)
    modulo_backend("rutas.parametros_ciclo")._save_cycle_json = guardar
    r = _patch(client, "liquidos", "globals", ["tipo_carga"], "solido")
    assert r.status_code == 503
    c = cm.cycles["liquidos"]
    assert c.get_param("globals", "tipo_carga") == "liquido" and c.get_param("descompresion", "modo") == 4
    assert not [a for a in _auditados(ctx) if a[0] == "param_ciclo_cambio"]


# X9 (tanda 9, D9-13.3 TMG-01): la prueba de la reversión que no alcanzaba al
# ciclo en curso se retiró: el ciclo en curso solo recibe el cambio después de
# registrar la bitácora (ver tests/test_x9_d9_13_3_bitacora_param_ciclo.py).

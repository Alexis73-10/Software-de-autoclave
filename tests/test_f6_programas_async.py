"""FASE 6 (P1): crear / duplicar / borrar programas como operación crítica,
sin optimismo. Éxito solo con un 200 o con una relectura de GET /programas que
lo demuestre; si no, «sin confirmar». Una operación a la vez, sin reintento."""
import pytest

from tests.helpers.sesion_f6_controladores import (
    NO_RESPONDE, Resueltas, SesionManual, app, conservar, r)

from autoclave.ui_qml import operacion_critica as oc
from autoclave.ui_qml.controllers.manejo_ciclos_controller import ManejoCiclosController


def _prog(numero, nombre, personalizado=False):
    return {"numero": numero, "nombre": nombre, "origen": "user",
            "personalizado": personalizado, "habilitado": True}


BASE = {"programas": [_prog(1, "Base"), _prog(5, "Copia", True)]}
CON_NUEVO = {"programas": BASE["programas"] + [_prog(6, "Nuevo", True)]}
SIN_5 = {"programas": [_prog(1, "Base")]}


@pytest.fixture(scope="module", autouse=True)
def _app():
    return app()


def _listo():
    s = SesionManual()
    c = conservar(ManejoCiclosController(sesion=s))
    c.cargar()
    s.responder(0, r(datos=BASE))
    assert [p["numero"] for p in c.programas] == [1, 5]
    return c, s, Resueltas(c)


def _post(s, n=1):
    return s.ultimo("POST", f"/programas/{n}/duplicar")


def test_crear_envia_con_plazo_10_bloquea_y_no_anuncia_antes_del_200():
    c, s, res = _listo()
    assert c.crear(1, "  Nuevo ") is True
    e = s.envios[_post(s)]
    assert e["cuerpo"] == {"nombre": "Nuevo", "crear": True} and e["plazo_s"] == 10.0
    assert c.operacionEnCurso and c.estadoDe("programa") == "enviando"
    assert c._op.bloquea() and oc.registro.bloqueaNavegacion
    assert c.mensaje == "" and res.lista == []
    assert [p["numero"] for p in c.programas] == [1, 5]       # sin optimismo


def test_crear_200_confirma_con_los_datos_del_backend_y_relee():
    c, s, res = _listo()
    c.crear(1, "Nuevo")
    n = s.cuenta("GET", "/programas")
    s.responder(_post(s), r(datos={"nombre": "Nuevo", "numero": 6}))
    assert c.mensaje == "manejo_ciclos.ok_creado" and c.exito is True
    assert c.detalleMensaje == {"nombre": "Nuevo", "numero": 6}
    assert res.lista == [("programa", "confirmada", "")]
    assert s.cuenta("GET", "/programas") == n + 1 and not c.operacionEnCurso


def test_duplicar_no_lleva_la_marca_de_crear():
    c, s, _ = _listo()
    c.duplicar(5, "Otra")
    assert s.envios[_post(s, 5)]["cuerpo"] == {"nombre": "Otra"}


@pytest.mark.parametrize("causa,clave", [
    ("nombre_repetido", "manejo_ciclos.err_nombre_repetido"),
    ("estado_no_permitido", "manejo_ciclos.err_estado"),
    ("rol_sin_permiso", "manejo_ciclos.err_rol"),
    ("BASE_OCUPADA", "manejo_ciclos.err_base_ocupada"),
])
def test_rechazo_muestra_su_motivo_y_relee_la_lista(causa, clave):
    c, s, res = _listo()
    c.crear(1, "Nuevo")
    n = s.cuenta("GET", "/programas")
    s.responder(_post(s), r(causa, {}, 409))
    assert c.mensaje == clave and c.exito is False
    assert res.lista == [("programa", "rechazada", clave)]
    assert s.cuenta("GET", "/programas") == n + 1


def test_nombre_vacio_no_envia_y_fija_el_mensaje():
    c, s, res = _listo()
    assert c.crear(1, "   ") is False
    assert s.cuenta("POST", "/programas/1/duplicar") == 0
    assert c.mensaje == "manejo_ciclos.err_nombre_invalido" and res.lista == []


def test_una_operacion_a_la_vez():
    c, s, _ = _listo()
    assert c.crear(1, "Nuevo") is True
    assert c.crear(1, "Otro") is False
    assert c.duplicar(1, "Otro") is False
    assert c.borrar(5) is False
    assert s.cuenta("POST", "/programas/1/duplicar") == 1 and s.cuenta("DELETE", "/programas/5") == 0


def test_crear_sin_respuesta_relectura_con_el_programa_confirma():
    c, s, res = _listo()
    c.crear(1, "Nuevo")
    s.responder(_post(s), r(NO_RESPONDE, None, 0))
    assert c.estadoDe("programa") == "verificando" and c.operacionEnCurso
    s.responder_ultimo("GET", "/programas", r(datos=CON_NUEVO))
    assert res.lista == [("programa", "confirmada", "")]
    assert c.mensaje == "manejo_ciclos.ok_creado" and c.exito is True
    assert [p["numero"] for p in c.programas] == [1, 5, 6]
    assert s.cuenta("POST", "/programas/1/duplicar") == 1       # sin reintento


@pytest.mark.parametrize("relectura", ["sin_el_programa", "falla", "datos_invalidos"])
def test_crear_sin_respuesta_sin_prueba_queda_sin_confirmar(relectura):
    c, s, res = _listo()
    c.crear(1, "Nuevo")
    s.responder(_post(s), r(NO_RESPONDE, None, 0))
    if relectura == "sin_el_programa":
        s.responder_ultimo("GET", "/programas", r(datos=BASE))
    elif relectura == "falla":
        s.responder_ultimo("GET", "/programas", r(NO_RESPONDE, None, 0))
    else:
        s.responder_ultimo("GET", "/programas", r(datos=[]))
    assert res.lista[-1][:2] == ("programa", "sin_confirmar")
    assert c.mensaje == "manejo_ciclos.err_sin_respuesta" and c.exito is False
    assert [p["numero"] for p in c.programas] == [1, 5]         # la lista no se vacía
    assert s.cuenta("POST", "/programas/1/duplicar") == 1


def test_borrar_200_confirma_con_el_nombre():
    c, s, res = _listo()
    assert c.borrar(5) is True
    e = s.envios[s.ultimo("DELETE", "/programas/5")]
    assert e["plazo_s"] == 10.0 and c._op.bloquea()
    s.responder_ultimo("DELETE", "/programas/5", r())
    assert c.mensaje == "manejo_ciclos.ok_borrado" and c.detalleMensaje["nombre"] == "Copia"
    assert res.lista == [("programa", "confirmada", "")]


def test_borrar_sin_respuesta_relectura_sin_el_programa_confirma():
    c, s, res = _listo()
    c.borrar(5)
    s.responder_ultimo("DELETE", "/programas/5", r(NO_RESPONDE, None, 0))
    s.responder_ultimo("GET", "/programas", r(datos=SIN_5))
    assert res.lista == [("programa", "confirmada", "")]
    assert c.mensaje == "manejo_ciclos.ok_borrado"
    assert [p["numero"] for p in c.programas] == [1]


def test_borrar_sin_respuesta_con_el_programa_aun_listado_queda_sin_confirmar():
    c, s, res = _listo()
    c.borrar(5)
    s.responder_ultimo("DELETE", "/programas/5", r(NO_RESPONDE, None, 0))
    s.responder_ultimo("GET", "/programas", r(datos=BASE))
    assert res.lista[-1][:2] == ("programa", "sin_confirmar")
    assert c.mensaje == "manejo_ciclos.err_sin_respuesta"
    assert s.cuenta("DELETE", "/programas/5") == 1


def test_borrar_rechazado_programa_activo():
    c, s, res = _listo()
    c.borrar(5)
    s.responder_ultimo("DELETE", "/programas/5", r("programa_activo", {}, 409))
    assert c.mensaje == "manejo_ciclos.err_programa_activo"
    assert res.lista == [("programa", "rechazada", "manejo_ciclos.err_programa_activo")]


def test_respuesta_tardia_tras_sin_confirmar_confirma_y_relee():
    c, s, res = _listo()
    c.borrar(5)
    i = s.ultimo("DELETE", "/programas/5")
    s.responder(i, r(NO_RESPONDE, None, 0))
    s.responder_ultimo("GET", "/programas", r(datos=BASE))
    assert res.lista[-1][1] == "sin_confirmar"
    n = s.cuenta("GET", "/programas")
    s.tardio(i, r())
    assert res.lista[-1] == ("programa", "confirmada", "operacion.confirmada_tarde")
    assert c.mensaje == "manejo_ciclos.ok_borrado"
    assert s.cuenta("GET", "/programas") > n
    assert s.cuenta("DELETE", "/programas/5") == 1


# ── corrección tras revisión (04-nov) ──────────────────────────────────────

def test_tardio_de_un_crear_con_un_borrar_vigente_no_pisa_su_contexto():
    """MAYOR-1: el 200 tardío del crear no se anuncia ni reescribe lo que
    anunciará el borrado vigente («Programa X borrado» sin respuesta)."""
    c, s, res = _listo()
    c.crear(1, "Nuevo")
    i = _post(s)
    s.responder(i, r(NO_RESPONDE, None, 0))
    s.responder_ultimo("GET", "/programas", r(datos=BASE))
    assert [x[1] for x in res.lista] == ["sin_confirmar"]
    assert c.borrar(5) is True
    s.tardio(i, r(datos={"nombre": "Nuevo", "numero": 6}))
    assert [x[1] for x in res.lista] == ["sin_confirmar"]          # nada anunciado
    assert c.mensaje == "manejo_ciclos.err_sin_respuesta" and c.operacionEnCurso
    s.responder_ultimo("DELETE", "/programas/5", r())
    assert res.lista[-1] == ("programa", "confirmada", "")
    assert c.mensaje == "manejo_ciclos.ok_borrado" and c.detalleMensaje == {"nombre": "Copia"}


@pytest.mark.parametrize("caso", ["sin_cargar", "cargando"])
def test_crear_sin_lista_previa_no_concilia(caso):
    """MENOR-5: sin lista previa cargada, «aparece uno nuevo» no prueba nada."""
    s = SesionManual()
    c = conservar(ManejoCiclosController(sesion=s))
    res = Resueltas(c)
    if caso == "cargando":
        c.cargar()
        assert c.cargando
    c.crear(1, "Nuevo")
    s.responder(_post(s), r(NO_RESPONDE, None, 0))
    s.responder_ultimo("GET", "/programas", r(datos=CON_NUEVO))   # el nuevo «aparece»...
    assert res.lista[-1][:2] == ("programa", "sin_confirmar")      # ...pero no se concilia
    assert c.exito is False


def test_habilitar_bloqueado_mientras_se_borra_ese_programa():
    """MENOR-6: habilitado:<n> no se lanza con el borrado de <n> en vuelo."""
    c, s, _ = _listo()
    assert c.borrar(5) is True
    assert c.borrando(5) and not c.borrando(1)
    assert c.fijarHabilitado(5, False) is False
    assert s.cuenta("PUT", "/programas/5/habilitado") == 0
    c.fijarHabilitado(1, False)
    assert s.cuenta("PUT", "/programas/1/habilitado") == 1          # otro programa sí


def test_borrar_bloqueado_con_su_habilitar_en_vuelo():
    c, s, _ = _listo()
    c.fijarHabilitado(5, False)
    assert "habilitado:5" in c.pendientes
    assert c.borrar(5) is False and s.cuenta("DELETE", "/programas/5") == 0


def test_qml_excluye_habilitar_y_borrar_del_mismo_programa():
    from pathlib import Path
    qml = (Path(__file__).resolve().parents[1]
           / "src/autoclave/ui_qml/qml/Pantallas/OpcionesManejoCiclos.qml").read_text(encoding="utf-8")
    assert "control.borrando(tarjeta.modelData.numero" in qml
    assert 'control.pendientes["habilitado:" + (tarjeta.modelData.numero ?? 0)] === undefined' in qml

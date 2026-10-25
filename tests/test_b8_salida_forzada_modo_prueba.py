"""B8 (tanda 4): un ingeniero con sesión puede terminar un modo prueba HUÉRFANO
(el dueño ya no tiene sesión), con confirmación y auditoría; el técnico no."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from autoclave.backend.autenticacion import AlmacenTokens
from autoclave.core.runtime.sesion_inactividad import PLAZO_TOKEN_BACKEND_S
from autoclave.services.domain.logging.db_manager import DbManager
from tests.backend_doble import cargar_servidor, fijar_en_backend, modulo_backend


class Reloj:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


@pytest.fixture
def api(tmp_path):
    db = DbManager(db_path=tmp_path / "t.db")
    ctx = MagicMock()
    ctx.db = db
    ctx.sin_base_de_datos = False
    ctx.control_loop.test_mode_active = True
    ctx.control_loop.estado_seguro = SimpleNamespace(activo=False)
    srv, _ = cargar_servidor(ctx)
    reloj = Reloj()
    fijar_en_backend("tokens", AlmacenTokens(reloj=reloj))
    dueno = modulo_backend("dependencias").tokens.emitir("tec_dueno", "Dueño", "tecnico", False)
    modulo_backend("rutas.io")._token_modo_prueba = dueno.token
    return TestClient(srv.app), srv, ctx, db, reloj, dueno


def _h(srv, rol, usuario=None):
    s = modulo_backend("dependencias").tokens.emitir(usuario or f"u_{rol}", rol, rol, False)
    return {"Authorization": f"Bearer {s.token}"}


def _huerfano(srv, reloj, dueno):
    """El dueño deja de tener sesión: caduca por inactividad."""
    reloj.t += PLAZO_TOKEN_BACKEND_S + 1
    assert modulo_backend("dependencias").tokens.existe(dueno.token) is False


def _forzar(client, headers, **cuerpo):
    return client.post("/io/test/force-exit", headers=headers, json={"confirmar": True, **cuerpo})


def test_dueno_vencido_el_ingeniero_fuerza_la_salida(api):
    client, srv, ctx, db, reloj, dueno = api
    _huerfano(srv, reloj, dueno)
    r = _forzar(client, _h(srv, "ingeniero", "ing1"), motivo="el técnico se fue")
    assert r.status_code == 200 and r.json() == {"ok": True, "dueno": "tec_dueno"}
    ctx.control_loop.exit_test_mode.assert_called_once()        # salidas a seguro y reanuda
    assert modulo_backend("rutas.io")._token_modo_prueba is None


def test_queda_auditado_quien_fuerza_a_quien_y_por_que(api):
    client, srv, ctx, db, reloj, dueno = api
    _huerfano(srv, reloj, dueno)
    _forzar(client, _h(srv, "ingeniero", "ing1"), motivo="turno terminado")
    f = db.get_auditoria(evento="modo_prueba_salida_forzada")[0]
    assert f["usuario"] == "ing1" and f["rol"] == "ingeniero"
    assert f["detalle"]["dueno"] == "tec_dueno" and f["detalle"]["forzada_por"] == "ing1"
    assert f["detalle"]["motivo"] == "turno terminado"
    assert any(x["detalle"] and "forzada" in x["detalle"]["motivo"]
               for x in db.get_auditoria(evento="modo_prueba_sale"))


def test_dueno_vigente_no_se_puede_forzar(api):
    client, srv, ctx, db, reloj, dueno = api
    r = _forzar(client, _h(srv, "ingeniero"))
    assert r.status_code == 409 and r.json()["codigo"] == "modo_prueba_dueno_vigente"
    ctx.control_loop.exit_test_mode.assert_not_called()
    assert modulo_backend("rutas.io")._token_modo_prueba == dueno.token


def test_dueno_que_cerro_sesion_cuenta_como_huerfano(api):
    client, srv, ctx, db, reloj, dueno = api
    modulo_backend("dependencias").tokens.invalidar(dueno.token)
    assert _forzar(client, _h(srv, "ingeniero")).status_code == 200


def test_el_tecnico_no_puede(api):
    client, srv, ctx, db, reloj, dueno = api
    _huerfano(srv, reloj, dueno)
    r = _forzar(client, _h(srv, "tecnico", "tec2"))
    assert r.status_code == 403 and r.json()["codigo"] == "rol_sin_permiso"
    ctx.control_loop.exit_test_mode.assert_not_called()


def test_sin_sesion_ni_otro_rol_no_pasa(api):
    client, srv, ctx, db, reloj, dueno = api
    _huerfano(srv, reloj, dueno)
    assert client.post("/io/test/force-exit", json={"confirmar": True}).status_code == 401
    for rol in ("operador", "admin"):
        assert _forzar(client, _h(srv, rol)).status_code == 403
    ctx.control_loop.exit_test_mode.assert_not_called()


@pytest.mark.parametrize("cuerpo", [{}, {"confirmar": False}])
def test_exige_confirmacion_explicita(api, cuerpo):
    client, srv, ctx, db, reloj, dueno = api
    _huerfano(srv, reloj, dueno)
    r = client.post("/io/test/force-exit", headers=_h(srv, "ingeniero"), json=cuerpo)
    assert r.status_code == 422 and r.json()["codigo"] == "confirmacion_requerida"
    ctx.control_loop.exit_test_mode.assert_not_called()


def test_sin_modo_prueba_activo_409(api):
    client, srv, ctx, db, reloj, dueno = api
    _huerfano(srv, reloj, dueno)
    ctx.control_loop.test_mode_active = False
    r = _forzar(client, _h(srv, "ingeniero"))
    assert r.status_code == 409 and r.json()["codigo"] == "modo_prueba_inactivo"


def test_con_estado_seguro_activo_la_salida_no_lo_cancela_y_queda_en_la_bitacora(api):
    client, srv, ctx, db, reloj, dueno = api
    ctx.control_loop.estado_seguro = SimpleNamespace(activo=True, cancelar=MagicMock(),
                                                     detener=MagicMock(), reset=MagicMock())
    _huerfano(srv, reloj, dueno)
    assert _forzar(client, _h(srv, "ingeniero")).status_code == 200
    ctx.control_loop.exit_test_mode.assert_called_once()
    est = ctx.control_loop.estado_seguro
    est.cancelar.assert_not_called() and est.detener.assert_not_called() and est.reset.assert_not_called()
    assert db.get_auditoria(evento="modo_prueba_salida_forzada")[0]["detalle"]["estado_seguro_activo"] is True


def test_el_propio_dueno_vigente_tambien_puede_salir_por_esta_ruta_si_es_ingeniero(api):
    client, srv, ctx, db, reloj, dueno = api
    ing = modulo_backend("dependencias").tokens.emitir("ing_dueno", "Ing", "ingeniero", False)
    modulo_backend("rutas.io")._token_modo_prueba = ing.token
    r = client.post("/io/test/force-exit", headers={"Authorization": f"Bearer {ing.token}"},
                    json={"confirmar": True})
    assert r.status_code == 200


def test_la_ruta_normal_de_salida_sigue_exigiendo_al_dueno(api):
    client, srv, ctx, db, reloj, dueno = api
    _huerfano(srv, reloj, dueno)
    r = client.post("/io/test/exit", headers=_h(srv, "ingeniero"))
    assert r.status_code == 409 and r.json()["codigo"] == "modo_prueba_no_dueno"


def test_quien_fue_recuerda_al_dueno_tras_caducar_sin_guardar_el_token_en_claro_en_la_bitacora(api):
    client, srv, ctx, db, reloj, dueno = api
    _huerfano(srv, reloj, dueno)
    assert modulo_backend("dependencias").tokens.quien_fue(dueno.token) == ("tec_dueno", "tecnico")
    assert modulo_backend("dependencias").tokens.quien_fue("desconocido") is None and modulo_backend("dependencias").tokens.quien_fue(None) is None
    _forzar(client, _h(srv, "ingeniero"))
    for f in db.get_auditoria(limite=50):
        assert dueno.token not in str(f)

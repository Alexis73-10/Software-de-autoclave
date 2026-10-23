# Núcleo de seguridad del backend (planeacion_backend_autenticacion.md, etapa 1):
# login, logout, cambio de contraseña obligatorio, bloqueo por intentos,
# requiere_rol, guard de estado, POST /usuarios, /outputs/reset, host fijo y
# registro en audit_log. Base SQLite real en tmp_path; el resto del contexto
# es un MagicMock.

import logging
import threading
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from autoclave.backend import contrasenas
from autoclave.backend.autenticacion import ControlIntentos
from autoclave.core.managers.cycle_manager import Cycle
from autoclave.services.domain.logging.db_manager import DbManager
from autoclave.state_machine.machine.enum_global import GlobalState
from tests.backend_doble import cabecera, cargar_servidor


def _h(clave):
    return contrasenas.hash_password(clave, 1000)   # pocas iteraciones: pruebas rápidas


@pytest.fixture
def db(tmp_path):
    base = DbManager(db_path=tmp_path / "t.db")   # trae admin e ingeniero semilla
    base.crear_usuario("Tec Uno", "tec1", _h("clave1234"), "tecnico")
    base.crear_usuario("Ing Uno", "ing1", _h("clave1234"), "ingeniero")
    base.crear_usuario("Adm Uno", "adm1", _h("clave1234"), "admin")
    base.crear_usuario("Inactivo", "inact", _h("clave1234"), "tecnico", activo=0)
    return base


@pytest.fixture
def entorno(db):
    ctx = MagicMock()
    ctx.db = db
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    ctx.estado.get_flag.return_value = False
    lock = threading.Lock()
    ctx.control_loop.bloqueo_maquina.return_value = lock
    ctx.control_loop.test_mode_active = False
    srv, _ = cargar_servidor(ctx)
    return TestClient(srv.app), ctx, srv


def _login(client, usuario, clave="clave1234"):
    return client.post("/auth/login", json={"usuario": usuario, "clave": clave})


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _eventos(db, evento=None):
    return db.get_auditoria(evento=evento, limite=1000)


# ── Contraseñas (§5.6, decisiones 4 y 27) ────────────────────────────────────

def test_hash_formato_pbkdf2_con_sal_aleatoria():
    h1, h2 = contrasenas.hash_password("secreta1"), contrasenas.hash_password("secreta1")
    partes = h1.split("$")
    assert partes[0] == "pbkdf2" and partes[1] == "600000" and len(partes) == 4
    assert h1 != h2   # sal distinta por usuario
    assert contrasenas.verificar_password("secreta1", h1)
    assert not contrasenas.verificar_password("secreta2", h1)


@pytest.mark.parametrize("guardado", [
    "6ca13d52ca70c883e0f0bb101e425a89e8624de51db2d2392593af6a84118090",   # SHA-256 viejo
    "", None, "pbkdf2$x$00$00", "pbkdf2$1000$$", "sha$1000$aa$bb",
])
def test_hash_que_no_es_pbkdf2_nunca_valida(guardado):
    assert contrasenas.verificar_password("abc123", guardado) is False


def test_usuarios_semilla_y_su_contrasena(db):
    admin = db.get_usuario_by_username("admin")
    ing = db.get_usuario_by_username("ingeniero")
    assert admin["rol"] == "admin" and ing["rol"] == "ingeniero"
    assert admin["debe_cambiar_clave"] == 1 and ing["debe_cambiar_clave"] == 1
    assert contrasenas.verificar_password("admin1234", admin["hash_pw"])
    assert contrasenas.verificar_password("ingeniero1234", ing["hash_pw"])


# ── Login (criterios 9 y 10) ─────────────────────────────────────────────────

def test_login_ok_devuelve_token_rol_y_bandera(entorno, db):
    client, _, _ = entorno
    r = _login(client, "tec1")
    assert r.status_code == 200
    datos = r.json()
    assert datos["rol"] == "tecnico" and datos["debe_cambiar_clave"] is False
    assert len(datos["token"]) >= 40
    assert _eventos(db, "login_ok")[0]["usuario"] == "tec1"


@pytest.mark.parametrize("usuario,clave", [
    ("tec1", "incorrecta"), ("fantasma", "clave1234"), ("inact", "clave1234"), ("", ""),
])
def test_login_401_generico(entorno, db, usuario, clave):
    client, _, _ = entorno
    r = _login(client, usuario, clave)
    assert r.status_code == 401
    assert r.json()["detail"] == "Usuario o contraseña incorrectos"
    assert _eventos(db, "login_fallido")


def test_cinco_fallos_bloquean_aunque_la_clave_sea_correcta(entorno, db):
    """Decisión 33 (v7): el 5.º fallo ya responde 429 con código, segundos
    restantes y Retry-After."""
    client, _, _ = entorno
    for _ in range(4):
        assert _login(client, "tec1", "mala").status_code == 401
    r = _login(client, "tec1", "mala")
    assert r.status_code == 429
    assert r.json() == {"detail": "Usuario bloqueado por intentos fallidos; espere 5 minutos",
                        "codigo": "usuario_bloqueado", "segundos_restantes": 300}
    assert r.headers["retry-after"] == "300"
    assert _login(client, "tec1").status_code == 429
    assert _login(client, "TEC1").status_code == 429   # sin distinguir mayúsculas
    assert len(_eventos(db, "login_fallido")) == 5
    assert _eventos(db, "login_bloqueado")
    assert _eventos(db, "login_fallido")[0]["detalle"] == {"bloqueado": True}


def test_cuatro_fallos_no_bloquean_y_el_exito_reinicia(entorno):
    client, _, _ = entorno
    for _ in range(4):
        _login(client, "tec1", "mala")
    assert _login(client, "tec1").status_code == 200
    for _ in range(4):
        _login(client, "tec1", "mala")
    assert _login(client, "tec1").status_code == 200


def test_usuario_inexistente_tambien_se_bloquea(entorno):
    client, _, _ = entorno
    for _ in range(5):
        _login(client, "fantasma", "x")
    assert _login(client, "fantasma", "x").status_code == 429


def test_segundos_restantes_redondea_hacia_arriba():
    """Decisión 33: segundos enteros hacia arriba, mínimo 1 mientras dure, 0 sin bloqueo."""
    ahora = [1000.0]
    c = ControlIntentos(reloj=lambda: ahora[0])
    assert c.segundos_restantes("ana") == 0
    for _ in range(5):
        c.reservar_intento("ana")
    assert c.segundos_restantes("ana") == 300
    assert c.segundos_restantes("ANA") == 300   # sin distinguir mayúsculas
    ahora[0] += 12.3
    assert c.segundos_restantes("ana") == 288
    ahora[0] += 287.69
    assert c.segundos_restantes("ana") == 1
    ahora[0] += 0.01
    assert c.segundos_restantes("ana") == 0


def test_bloqueo_dura_cinco_minutos():
    ahora = [1000.0]
    c = ControlIntentos(reloj=lambda: ahora[0])
    for _ in range(5):
        assert c.reservar_intento("ana")
    assert c.bloqueado("ana")
    assert not c.reservar_intento("ana")
    ahora[0] += 299
    assert c.bloqueado("ana")
    ahora[0] += 1
    assert not c.bloqueado("ana")
    for _ in range(4):                    # el contador empezó de nuevo
        assert c.reservar_intento("ana")
    assert not c.bloqueado("ana")


def test_intentos_en_paralelo_no_superan_el_maximo():
    """TMG-05: comprobar y contar es una sola operación; 20 hilos a la vez
    solo consiguen 5 intentos."""
    c = ControlIntentos()
    barrera = threading.Barrier(20)
    resultados = []

    def intentar():
        barrera.wait()
        resultados.append(c.reservar_intento("ana"))

    hilos = [threading.Thread(target=intentar) for _ in range(20)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert resultados.count(True) == 5
    assert c.bloqueado("ana")


def test_logins_en_paralelo_contra_el_endpoint_no_superan_el_maximo(entorno):
    """La verificación es lenta; con el intento reservado antes, los logins
    concurrentes no pasan todos la comprobación de bloqueo."""
    client, _, _ = entorno
    barrera = threading.Barrier(10)
    codigos = []

    def intentar():
        barrera.wait()
        codigos.append(_login(client, "tec1", "mala").status_code)

    hilos = [threading.Thread(target=intentar) for _ in range(10)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    # 5 intentos reservados (los que verifican la clave); el resto, 429 directo.
    # De los reservados, los que terminan con el bloqueo ya activo dan 429 (v7).
    assert len(codigos) == 10 and set(codigos) <= {401, 429}
    assert codigos.count(401) <= 4 and codigos.count(429) >= 6
    assert len(_eventos(entorno[1].db, "login_fallido")) == 5


def test_primer_login_de_semillas_obliga_a_cambiar_clave(entorno, db):
    """Criterio 10: antes de cambiarla, cualquier otra escritura devuelve 403."""
    client, ctx, _ = entorno
    ctx.cycle_manager.cycles = {}
    for usuario, clave in (("admin", "admin1234"), ("ingeniero", "ingeniero1234")):
        datos = _login(client, usuario, clave).json()
        assert datos["debe_cambiar_clave"] is True
        tok = datos["token"]
        r = client.patch("/cycle/parameter", headers=_auth(tok),
                         json={"cycle_id": "x", "fase": "f", "path": ["p"], "value": 1})
        assert r.status_code == 403 and "cambiar la contraseña" in r.json()["detail"]
        r = client.post("/auth/change_password", headers=_auth(tok), json={
            "clave_actual": clave, "clave_nueva": "nueva12345", "confirmacion": "nueva12345"})
        assert r.status_code == 200
        assert db.get_usuario_by_username(usuario)["debe_cambiar_clave"] == 0
    # la misma sesión del ingeniero ya puede escribir (404: el ciclo no existe)
    r = client.patch("/cycle/parameter", headers=_auth(tok),
                     json={"cycle_id": "x", "fase": "f", "path": ["p"], "value": 1})
    assert r.status_code == 404
    assert _login(client, "ingeniero", "nueva12345").json()["debe_cambiar_clave"] is False
    assert _login(client, "ingeniero", "ingeniero1234").status_code == 401
    assert len(_eventos(db, "cambio_clave")) == 2


def test_cambio_de_clave_valida(entorno):
    client, _, _ = entorno
    tok = _login(client, "tec1").json()["token"]
    malas = [
        ({"clave_actual": "mala", "clave_nueva": "nueva12345", "confirmacion": "nueva12345"}, 403),
        ({"clave_actual": "clave1234", "clave_nueva": "corta", "confirmacion": "corta"}, 422),
        ({"clave_actual": "clave1234", "clave_nueva": "nueva12345", "confirmacion": "otra12345"}, 422),
        ({"clave_actual": "clave1234", "clave_nueva": "clave1234", "confirmacion": "clave1234"}, 422),
    ]
    for cuerpo, codigo in malas:
        assert client.post("/auth/change_password", headers=_auth(tok), json=cuerpo).status_code == codigo
    assert client.post("/auth/change_password", json=malas[0][0]).status_code == 401


# ── Logout y tokens (criterios 1 y 8) ─────────────────────────────────────────

def test_logout_invalida_solo_su_token(entorno, db):
    client, _, _ = entorno
    t1 = _login(client, "tec1").json()["token"]
    t2 = _login(client, "tec1").json()["token"]   # otra ventana
    assert client.post("/auth/logout", headers=_auth(t1)).status_code == 200
    assert client.post("/auth/logout", headers=_auth(t1)).status_code == 401
    assert client.post("/auth/logout", headers=_auth(t2)).status_code == 200
    assert len(_eventos(db, "logout")) == 2


def test_token_invalidado_no_afecta_al_ciclo_en_curso(entorno):
    client, ctx, _ = entorno
    ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    tok = _login(client, "ing1").json()["token"]
    ctx.control_loop.reset_mock()
    ctx.estado.reset_mock(return_value=False, side_effect=False)
    client.post("/auth/logout", headers=_auth(tok))
    ctx.control_loop.stop.assert_not_called()
    ctx.control_loop.exit_test_mode.assert_not_called()
    ctx.estado.set_flag.assert_not_called()
    ctx.estado.set_machine_state.assert_not_called()


def test_reinicio_del_backend_invalida_los_tokens(db):
    ctx = MagicMock()
    ctx.db = db
    srv1, _ = cargar_servidor(ctx)
    tok = _login(TestClient(srv1.app), "tec1").json()["token"]
    srv2, _ = cargar_servidor(ctx)   # nuevo proceso: almacén vacío
    r = TestClient(srv2.app).post("/auth/logout", headers=_auth(tok))
    assert r.status_code == 401
    ctx.control_loop.stop.assert_not_called()


@pytest.mark.parametrize("valor", ["", "Bearer", "Bearer ", "Basic abc", "Bearer no-existe"])
def test_cabecera_invalida_401_y_queda_registrada(entorno, db, valor, caplog):
    client, _, _ = entorno
    with caplog.at_level(logging.INFO):
        r = client.post("/io/test/enter", headers={"Authorization": valor})
    assert r.status_code == 401
    assert r.headers.get("www-authenticate") == "Bearer"
    # D9-6 (tanda 9): el rechazo queda en el log de desarrollo, no en la bitácora
    assert _eventos(db, "rechazo_401") == []
    assert "rechazo_401" in caplog.text and "/io/test/enter" in caplog.text


# ── Rol (criterios 1 y 2) ─────────────────────────────────────────────────────

_CUERPO_CALIB = {"shown_low": 12.0, "real_low": 9.54, "shown_high": 322.0, "real_high": 300.0}


@pytest.fixture
def entorno_config(entorno, tmp_path):
    client, ctx, srv = entorno
    yaml_path = tmp_path / "calibration.yaml"
    yaml_path.write_text(
        "calibration:\n  user:\n    temperature:\n      - gain: 1.0\n        offset: 0.0\n"
        "    pressure:\n      - gain: 1.3466\n        offset: -67.11\n", encoding="utf-8")
    srv.CALIBRATION_PATH = yaml_path
    params = {"secado": {"tiempo_secado": {"value": 10.0, "type": "float", "min": 0, "max": 120}}}
    otro = Cycle(cycle_id="otro", name="Otro", parameters={
        "secado": {"tiempo_secado": {"value": 10.0, "type": "float", "min": 0, "max": 120}}})
    en_curso = Cycle(cycle_id="en_curso", name="En curso", parameters=params)
    ctx.cycle_manager.cycles = {"otro": otro, "en_curso": en_curso}
    ctx.control_loop.cycle = en_curso
    return client, ctx, srv, otro, en_curso


def _param(client, cab, cycle_id="otro", valor=20.0):
    return client.patch("/cycle/parameter", headers=cab, json={
        "cycle_id": cycle_id, "fase": "secado", "path": ["tiempo_secado"], "value": valor})


@pytest.mark.parametrize("estado", [GlobalState.PREPARADO, GlobalState.CICLO])
def test_configuracion_403_para_admin_en_cualquier_estado(entorno_config, estado):
    client, ctx, srv, otro, _ = entorno_config
    ctx.estado.get_machine_state.return_value = estado
    cab = cabecera(srv, "admin")
    assert client.patch("/calibration/pressure/pres_camara", headers=cab,
                        json=_CUERPO_CALIB).status_code == 403
    assert _param(client, cab).status_code == 403
    assert otro.get_param("secado", "tiempo_secado") == 10.0
    ctx.units.reload_calibration.assert_not_called()
    assert _eventos(ctx.db, "rechazo_403") == []     # D9-6 (tanda 9): solo log de desarrollo


def test_tecnico_calibra_fuera_de_ciclo(entorno_config):
    # Tanda 2026-10-14 §1.1 (C-5): calibración para técnico e ingeniero
    client, ctx, srv, _, _ = entorno_config
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    r = client.patch("/calibration/pressure/pres_camara", headers=cabecera(srv, "tecnico"),
                     json=_CUERPO_CALIB)
    assert r.status_code == 200
    ctx.units.reload_calibration.assert_called_once()


def test_tecnico_no_calibra_en_ciclo(entorno_config):
    client, ctx, srv, _, _ = entorno_config
    ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    r = client.patch("/calibration/pressure/pres_camara", headers=cabecera(srv, "tecnico"),
                     json=_CUERPO_CALIB)
    assert r.status_code == 409
    ctx.units.reload_calibration.assert_not_called()


def test_configuracion_sin_token_401(entorno_config):
    client, ctx, _, _, _ = entorno_config
    assert client.patch("/calibration/pressure/pres_camara", json=_CUERPO_CALIB).status_code == 401
    assert _param(client, {}).status_code == 401


def test_cycle_parameters_eliminado(entorno_config):
    client, _, srv, _, _ = entorno_config
    r = client.patch("/cycle/parameters", headers=cabecera(srv, "ingeniero"),
                     json={"tiempo_secado": 15.0})
    assert r.status_code in (404, 405)


def test_ingeniero_cambia_parametro_fuera_de_ciclo_y_queda_auditado(entorno_config):
    client, ctx, srv, otro, _ = entorno_config
    r = _param(client, cabecera(srv, "ingeniero", "ing1"))
    assert r.status_code == 200 and r.json()["aplica"] == "siguiente"
    assert otro.get_param("secado", "tiempo_secado") == 20.0
    fila = _eventos(ctx.db, "param_ciclo_cambio")[0]
    assert fila["usuario"] == "ing1" and fila["rol"] == "ingeniero"
    assert fila["entidad"] == "otro/secado/tiempo_secado"
    assert fila["valor_anterior"] == "10.0" and fila["valor_nuevo"] == "20.0"
    assert fila["detalle"] == {"programa": "otro", "fase": "secado", "aplica": "siguiente"}


def test_ingeniero_en_ciclo_edita_otro_programa(entorno_config):
    """Decisión 23 (5b): programas no seleccionados se editan en CICLO; el
    registro lleva ciclo y fase en curso."""
    client, ctx, srv, otro, _ = entorno_config
    ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    ctx.estado.fase_ciclo = "ESTERILIZACION"
    ctx.cycle_logger.ciclo_id_pantalla = 77
    r = _param(client, cabecera(srv, "ingeniero"))
    assert r.status_code == 200 and r.json()["aplica"] == "siguiente"
    detalle = _eventos(ctx.db, "param_ciclo_cambio")[0]["detalle"]
    assert detalle["ciclo"] == 77 and detalle["fase_en_curso"] == "ESTERILIZACION"
    assert detalle["programa_en_curso"] == "en_curso"


@pytest.mark.parametrize("aplico,aplica", [(True, "en_curso"), (False, "siguiente")])
def test_ingeniero_en_ciclo_edita_el_programa_en_curso(entorno_config, aplico, aplica):
    """T-17 (§5.8): se guarda en el programa almacenado y el ciclo en curso
    decide, según su fase, si también aplica a su copia."""
    client, ctx, srv, _, en_curso = entorno_config
    ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    ctx.estado.fase_ciclo = "CALENTAMIENTO"
    ctx.control_loop.aplicar_a_ciclo_en_curso.return_value = aplico
    ctx.cycle_logger.ciclo_id_pantalla = 5
    r = _param(client, cabecera(srv, "ingeniero"), cycle_id="en_curso")
    assert r.status_code == 200 and r.json()["aplica"] == aplica
    assert en_curso.get_param("secado", "tiempo_secado") == 20.0
    ctx.control_loop.aplicar_a_ciclo_en_curso.assert_called_once_with(
        "secado", ["tiempo_secado"], 20.0)
    assert _eventos(ctx.db, "param_ciclo_cambio")[0]["detalle"]["aplica"] == aplica


def test_ingeniero_en_ciclo_otro_programa_no_toca_el_ciclo_en_curso(entorno_config):
    """§5.8, 5b: un programa no seleccionado no afecta al ciclo en curso."""
    client, ctx, srv, otro, _ = entorno_config
    ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    ctx.estado.fase_ciclo = "CALENTAMIENTO"
    ctx.cycle_logger.ciclo_id_pantalla = 5
    r = _param(client, cabecera(srv, "ingeniero"))
    assert r.status_code == 200 and r.json()["aplica"] == "siguiente"
    assert otro.get_param("secado", "tiempo_secado") == 20.0
    ctx.control_loop.aplicar_a_ciclo_en_curso.assert_not_called()


def test_parametro_vinculado_se_ajusta_y_se_audita(entorno_config):
    """SAF-02 de T-17: temperatura de calentamiento y de esterilización van juntas."""
    client, ctx, srv, otro, _ = entorno_config
    hoja = {"value": 134.0, "type": "float", "min": 100, "max": 140}
    otro.parameters["calentamiento"] = {"temperatura_calentamiento": dict(hoja)}
    otro.parameters["esterilizacion"] = {"temperatura_esterilizacion": dict(hoja)}
    r = client.patch("/cycle/parameter", headers=cabecera(srv, "ingeniero"), json={
        "cycle_id": "otro", "fase": "esterilizacion", "path": ["temperatura_esterilizacion"],
        "value": 121.0})
    assert r.status_code == 200
    assert otro.get_param("calentamiento", "temperatura_calentamiento") == 121.0
    detalle = _eventos(ctx.db, "param_ciclo_cambio")[0]["detalle"]
    assert detalle["vinculados"] == ["calentamiento/temperatura_calentamiento"]


def test_valor_invalido_en_ciclo_no_toca_nada(entorno_config):
    client, ctx, srv, _, en_curso = entorno_config
    ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    r = _param(client, cabecera(srv, "ingeniero"), cycle_id="en_curso", valor=500.0)
    assert r.status_code == 422
    assert en_curso.get_param("secado", "tiempo_secado") == 10.0
    ctx.control_loop.aplicar_a_ciclo_en_curso.assert_not_called()


def test_ingeniero_calibra_en_ciclo_y_aplica_de_inmediato(entorno_config):
    client, ctx, srv, _, _ = entorno_config
    ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    ctx.estado.fase_ciclo = "SECADO"
    ctx.cycle_logger.ciclo_id_pantalla = 5
    r = client.patch("/calibration/pressure/pres_camara", headers=cabecera(srv, "ingeniero"),
                     json=_CUERPO_CALIB)
    assert r.status_code == 200
    ctx.units.reload_calibration.assert_called_once()
    detalle = _eventos(ctx.db, "calibracion_cambio")[0]["detalle"]
    assert detalle["ciclo"] == 5 and detalle["fase"] == "SECADO"


def test_calibracion_escribe_archivo_y_recarga_fuera_del_lock(entorno_config):
    """Hallazgo D: el YAML y la recarga no detienen el tick; el guard solo
    comprueba el estado con el lock tomado."""
    client, ctx, srv, _, _ = entorno_config
    lock = ctx.control_loop.bloqueo_maquina.return_value
    visto = []
    ctx.units.reload_calibration.side_effect = lambda *_: visto.append(lock.locked())
    ctx.estado.get_machine_state.side_effect = lambda: (
        visto.append(("estado", lock.locked())) or GlobalState.PREPARADO)
    r = client.patch("/calibration/pressure/pres_camara", headers=cabecera(srv, "ingeniero"),
                     json=_CUERPO_CALIB)
    assert r.status_code == 200
    assert visto[0] == ("estado", True)
    assert visto[-1] is False          # recarga sin el lock
    assert not lock.locked()


def test_parametro_cambia_en_memoria_con_lock_y_guarda_json_sin_lock(entorno_config):
    client, ctx, srv, otro, _ = entorno_config
    lock = ctx.control_loop.bloqueo_maquina.return_value
    otro.source, otro._path = "user", "no_se_usa.json"
    guardado = []
    with patch.object(srv, "_save_cycle_json",
                      side_effect=lambda c: guardado.append((lock.locked(),
                                                             c.get_param("secado", "tiempo_secado")))):
        assert _param(client, cabecera(srv, "ingeniero")).status_code == 200
    assert guardado == [(False, 20.0)]


def test_get_calibration_ultimo_cambio_de_audit_log_y_luego_historico(entorno_config):
    client, ctx, srv, _, _ = entorno_config
    ctx.calibration_audit.get_last_change.return_value = {"usuario": "viejo",
                                                          "timestamp": "2026-01-01 10:00"}
    r = client.get("/calibration/pressure/pres_camara")
    assert r.json()["last_change"]["usuario"] == "viejo"
    client.patch("/calibration/pressure/pres_camara", headers=cabecera(srv, "ingeniero", "ing1"),
                 json=_CUERPO_CALIB)
    r = client.get("/calibration/pressure/pres_camara")
    assert r.json()["last_change"]["usuario"] == "ing1"
    assert len(r.json()["last_change"]["timestamp"]) == len("2026-01-01 10:00")


# ── POST /usuarios (criterio 10b) ─────────────────────────────────────────────

def _nuevo(rol="tecnico", usuario="nuevo1", **cambios):
    return {"nombre": "Nuevo Uno", "usuario": usuario, "clave": "clave1234",
            "confirmacion": "clave1234", "rol": rol, "activo": True, **cambios}


@pytest.mark.parametrize("creador,rol,codigo", [
    ("ingeniero", "admin", 200), ("ingeniero", "tecnico", 200), ("ingeniero", "ingeniero", 200),
    ("admin", "admin", 200), ("admin", "tecnico", 200), ("admin", "ingeniero", 403),
    ("tecnico", "tecnico", 403),
])
def test_reglas_de_creacion_por_rol(entorno, creador, rol, codigo):
    client, ctx, srv = entorno
    r = client.post("/usuarios", headers=cabecera(srv, creador, "creador1"), json=_nuevo(rol))
    assert r.status_code == codigo
    assert ctx.db.existe_usuario("nuevo1") is (codigo == 200)


def test_usuario_creado_inicia_sesion_y_queda_auditado(entorno):
    client, ctx, srv = entorno
    r = client.post("/usuarios", headers=cabecera(srv, "admin", "adm1"),
                    json=_nuevo(nombre="  Nuevo Uno  "))
    assert r.status_code == 200
    fila = ctx.db.get_usuario_by_username("nuevo1")
    assert fila["nombre"] == "Nuevo Uno" and fila["creado_por"] == "adm1"
    assert fila["creado_en"] and fila["hash_pw"].startswith("pbkdf2$600000$")
    assert fila["debe_cambiar_clave"] == 0
    evento = _eventos(ctx.db, "usuario_creado")[0]
    assert evento["usuario"] == "adm1" and evento["entidad"] == "nuevo1"
    assert _login(client, "nuevo1").json()["rol"] == "tecnico"


def test_usuario_repetido_sin_distinguir_mayusculas_409(entorno):
    client, ctx, srv = entorno
    r = client.post("/usuarios", headers=cabecera(srv, "admin"), json=_nuevo(usuario="TEC1"))
    assert r.status_code == 409
    assert _eventos(ctx.db, "rechazo_409") == []     # D9-6 (tanda 9): solo log de desarrollo


def test_usuario_invalido_422_con_errores_por_campo(entorno):
    client, ctx, srv = entorno
    r = client.post("/usuarios", headers=cabecera(srv, "admin"),
                    json=_nuevo(usuario="a b", clave="corta", confirmacion="otra", rol="biomedico"))
    assert r.status_code == 422
    assert r.json() == {"detail": "Datos inválidos", "codigo": "validacion", "errores": [
        {"campo": "usuario", "codigo": "formato"},
        {"campo": "clave", "codigo": "corta"},
        {"campo": "confirmacion", "codigo": "no_coinciden"},
        {"campo": "rol", "codigo": "rol_invalido"},
    ]}
    assert not ctx.db.existe_usuario("a b")


def test_crear_usuario_inactivo(entorno):
    client, ctx, srv = entorno
    client.post("/usuarios", headers=cabecera(srv, "ingeniero"), json=_nuevo(activo=False))
    assert ctx.db.existe_usuario("nuevo1") and ctx.db.get_usuario_by_username("nuevo1") is None


def test_crear_usuario_sin_token_401(entorno):
    client, ctx, _ = entorno
    assert client.post("/usuarios", json=_nuevo()).status_code == 401
    assert not ctx.db.existe_usuario("nuevo1")


# ── Operativos sin token (criterios 5 y 11) ───────────────────────────────────

def test_abort_funciona_sin_token(entorno):
    client, ctx, _ = entorno
    ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    assert client.post("/cycle/abort").status_code == 200
    ctx.estado.set_flag.assert_called_with("CICLO_CANCELADO", True)


def test_outputs_reset_409_en_ciclo(entorno):
    client, ctx, _ = entorno
    ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    assert client.post("/outputs/reset").status_code == 409
    ctx.control_loop.stop.assert_not_called()
    ctx.setdo.reset_all_outputs.assert_not_called()
    assert _eventos(ctx.db, "rechazo_409") == []     # D9-6 (tanda 9): solo log de desarrollo


@pytest.mark.parametrize("estado", [GlobalState.PREPARACION, GlobalState.PREPARADO,
                                    GlobalState.FALLA])
def test_outputs_reset_fuera_de_ciclo(entorno, estado):
    client, ctx, _ = entorno
    ctx.estado.get_machine_state.return_value = estado
    assert client.post("/outputs/reset").status_code == 200
    ctx.control_loop.stop.assert_called_once()
    ctx.setdo.reset_all_outputs.assert_called_once()
    # stop() espera al hilo del loop: no puede llamarse con _sm_lock tomado
    assert not ctx.control_loop.bloqueo_maquina.return_value.locked()


# ── Host fijo (criterio 7) ────────────────────────────────────────────────────

def test_backend_escucha_solo_en_localhost():
    from autoclave.backend import main
    assert main.HOST == "127.0.0.1"
    with patch.object(main.uvicorn, "Server") as servidor, \
            patch.object(main.threading, "Thread"):
        main.main()
    assert servidor.call_args.args[0].host == "127.0.0.1"


# ── Revisión de seguridad de la etapa 1 ──────────────────────────────────────

class _LockQueInvalida:
    """Lock real que, al tomarse por primera vez, ejecuta `accion` (simula un
    logout que llega mientras la petición esperaba el lock)."""
    def __init__(self, accion):
        self._lock = threading.RLock()
        self._accion = accion

    def __enter__(self):
        self._lock.acquire()
        if self._accion:
            accion, self._accion = self._accion, None
            accion()
        return self

    def __exit__(self, *exc):
        self._lock.release()


def test_enter_revalida_el_token_dentro_del_lock(entorno):
    """TMG-03: si el logout de la sesión llega mientras /io/test/enter espera
    el lock, la entrada se rechaza y el modo prueba no queda huérfano."""
    client, ctx, srv = entorno
    cab = cabecera(srv, "tecnico")
    token = cab["Authorization"].split()[1]
    ctx.control_loop.bloqueo_maquina.return_value = _LockQueInvalida(
        lambda: srv.tokens.invalidar(token))
    r = client.post("/io/test/enter", headers=cab)
    assert r.status_code == 401
    ctx.control_loop.enter_test_mode.assert_not_called()
    assert srv._token_modo_prueba is None


def test_logout_sale_del_modo_prueba_con_el_lock_tomado(entorno):
    client, ctx, srv = entorno
    ctx.control_loop.enter_test_mode.return_value = (True, "")
    cab = cabecera(srv, "tecnico")
    assert client.post("/io/test/enter", headers=cab).status_code == 200
    ctx.control_loop.test_mode_active = True
    lock = ctx.control_loop.bloqueo_maquina.return_value
    tomado = []
    ctx.control_loop.exit_test_mode.side_effect = lambda: tomado.append(lock.locked())
    assert client.post("/auth/logout", headers=cab).status_code == 200
    assert tomado == [True]
    assert srv._token_modo_prueba is None
    motivos = [f["detalle"]["motivo"] for f in _eventos(ctx.db, "modo_prueba_sale")]
    assert motivos == ["sesión cerrada"]


def test_cancelacion_por_paro_olvida_al_dueno_y_queda_en_la_bitacora(entorno):
    client, ctx, srv = entorno
    aviso = srv._prueba_cancelada_por_paro   # lo registra el arranque (construir_control)
    ctx.control_loop.enter_test_mode.return_value = (True, "")
    cab = cabecera(srv, "tecnico", "tec1")
    client.post("/io/test/enter", headers=cab)

    ctx.control_loop.test_mode_active = False   # el loop ya lo canceló
    aviso()

    assert srv._token_modo_prueba is None
    fila = _eventos(ctx.db, "modo_prueba_sale")[0]
    assert fila["usuario"] == "tec1"
    assert fila["detalle"] == {"motivo": "paro de emergencia"}
    # la sesión puede volver a entrar cuando se suelte el paro
    assert client.post("/io/test/enter", headers=cabecera(srv, "ingeniero")).status_code == 200


def test_aviso_de_paro_tardio_no_toca_un_modo_prueba_nuevo(entorno):
    client, ctx, srv = entorno
    aviso = srv._prueba_cancelada_por_paro   # lo registra el arranque (construir_control)
    srv._token_modo_prueba = "otro"
    ctx.control_loop.test_mode_active = True
    aviso()
    assert srv._token_modo_prueba == "otro"
    assert _eventos(ctx.db, "modo_prueba_sale") == []


def test_apagado_del_backend_detiene_el_loop_y_apaga_salidas(entorno):
    """Hallazgo B: un apagado ordenado del backend (lifespan) ejecuta
    control_loop.stop(), que manda ALL_OFF."""
    _, ctx, srv = entorno
    with TestClient(srv.app):
        ctx.control_loop.stop.assert_not_called()
    ctx.control_loop.stop.assert_called_once()


def test_rechazo_por_estado_se_registra_con_el_lock_libre(entorno):
    """Hallazgo D: el registro del 409 no se hace con _sm_lock tomado. D9-6
    (tanda 9): ese registro pasó de la bitácora al log de desarrollo."""
    client, ctx, srv = entorno
    ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    lock = ctx.control_loop.bloqueo_maquina.return_value
    real = srv._log_desarrollo
    tomado = []

    def registrar(*a, **k):
        tomado.append(lock.locked())
        return real(*a, **k)

    with patch.object(srv, "_log_desarrollo", side_effect=registrar):
        assert client.post("/outputs/reset").status_code == 409
        assert client.post("/io/test/enter", headers=cabecera(srv, "tecnico")).status_code == 409
    assert tomado == [False, False]

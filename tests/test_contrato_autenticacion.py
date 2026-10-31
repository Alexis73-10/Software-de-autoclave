# Contrato de autenticación (planeacion_backend_autenticacion.md v7, decisiones
# 33 a 35; plan_t8_login_qml.md §3.4). La misma batería corre contra cada
# servidor del parámetro `servidor`: el backend real (BD SQLite temporal, resto
# del contexto simulado) y, desde T-14, el simulador. Cada servidor expone los
# mismos usuarios de prueba por papel (ver `_USUARIOS`).

import threading
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from autoclave.backend import contrasenas
from autoclave.services.domain.logging.db_manager import DbManager
from autoclave.state_machine.machine.enum_global import GlobalState
from tests.helpers.backend_doble import cargar_servidor

CLAVE = "clave1234"
BLOQUEADO = "Usuario bloqueado por intentos fallidos; espere 5 minutos"
CREDENCIALES = "Usuario o contraseña incorrectos"

# papel -> (usuario, clave). "pendiente" es la semilla Admin con cambio obligatorio.
_USUARIOS = {
    "tecnico": ("tec1", CLAVE),
    "admin": ("adm1", CLAVE),
    "ingeniero": ("ing1", CLAVE),
    "pendiente": ("Admin", "admin1234"),   # U11: cuenta del sistema Admin
    "bloqueo": ("bloq1", CLAVE),
}


def _backend_real(tmp_path):
    db = DbManager(db_path=tmp_path / "t.db")   # trae admin e ingeniero semilla
    for nombre, (usuario, clave), rol in (
            ("Tec Uno", _USUARIOS["tecnico"], "tecnico"),
            ("Adm Uno", _USUARIOS["admin"], "admin"),
            ("Ing Uno", _USUARIOS["ingeniero"], "ingeniero"),
            ("Bloqueo", _USUARIOS["bloqueo"], "tecnico")):
        db.crear_usuario(nombre, usuario, contrasenas.hash_password(clave, 1000), rol)
    ctx = MagicMock()
    ctx.db = db
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    ctx.estado.get_flag.return_value = False
    ctx.control_loop.bloqueo_maquina.return_value = threading.Lock()
    ctx.control_loop.test_mode_active = False
    srv, _ = cargar_servidor(ctx)
    return TestClient(srv.app)


_SERVIDORES = {"backend": _backend_real}


@pytest.fixture(params=sorted(_SERVIDORES))
def cliente(request, tmp_path):
    return _SERVIDORES[request.param](tmp_path)


def _entrar(cliente, usuario, clave):
    """Login con el nombre de usuario tal cual (sin pasar por los papeles)."""
    return cliente.post("/auth/login", json={"usuario": usuario, "clave": clave})


def _login(cliente, papel, clave=None):
    usuario, clave_ok = _USUARIOS[papel]
    return _entrar(cliente, usuario, clave_ok if clave is None else clave)


def _token(cliente, papel):
    r = _login(cliente, papel)
    assert r.status_code == 200
    return r.json()["token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _cambio(cliente, token, actual, nueva="nueva12345", confirmacion=None):
    return cliente.post("/auth/change_password", headers=_auth(token), json={
        "clave_actual": actual, "clave_nueva": nueva,
        "confirmacion": nueva if confirmacion is None else confirmacion})


def _assert_bloqueo(r, segundos=None):
    assert r.status_code == 429
    datos = r.json()
    assert set(datos) == {"detail", "codigo", "segundos_restantes"}
    assert datos["detail"] == BLOQUEADO and datos["codigo"] == "usuario_bloqueado"
    assert isinstance(datos["segundos_restantes"], int) and 1 <= datos["segundos_restantes"] <= 300
    if segundos is not None:
        assert datos["segundos_restantes"] == segundos
    assert r.headers["retry-after"] == str(datos["segundos_restantes"])


# ── Login ─────────────────────────────────────────────────────────────────────

def test_login_ok_devuelve_los_campos_del_contrato(cliente):
    datos = _login(cliente, "tecnico").json()
    assert set(datos) == {"token", "usuario", "nombre", "rol", "debe_cambiar_clave"}
    assert datos["usuario"] == "tec1" and datos["rol"] == "tecnico"
    assert datos["debe_cambiar_clave"] is False and datos["token"]
    assert _login(cliente, "pendiente").json()["debe_cambiar_clave"] is True


def test_credenciales_invalidas_401_con_codigo(cliente):
    r = _login(cliente, "tecnico", "mala")
    assert r.status_code == 401
    assert r.json() == {"detail": CREDENCIALES, "codigo": "credenciales_invalidas"}


def test_quinto_fallo_responde_429_con_segundos_y_retry_after(cliente):
    for _ in range(4):
        assert _login(cliente, "bloqueo", "mala").status_code == 401
    _assert_bloqueo(_login(cliente, "bloqueo", "mala"), segundos=300)
    _assert_bloqueo(_login(cliente, "bloqueo"))   # bloqueado aunque la clave sea correcta


def test_usuario_inexistente_recibe_las_mismas_respuestas(cliente):
    """No revela si el usuario existe: mismo 401 y mismo 429 al 5.º fallo."""
    respuestas = {}
    for usuario in ("bloq1", "no_existe_1"):
        r = [_entrar(cliente, usuario, "mala") for _ in range(5)]
        respuestas[usuario] = [(x.status_code, x.json()) for x in r]
    assert respuestas["bloq1"] == respuestas["no_existe_1"]
    assert [c for c, _ in respuestas["bloq1"]] == [401, 401, 401, 401, 429]


def test_mayusculas_comparten_contador_y_respuesta(cliente):
    """"Admin" y "admin" comparten contador de bloqueo y reciben la misma respuesta."""
    r_minus = _entrar(cliente, "admin", "mala")
    r_mayus = _entrar(cliente, "Admin", "mala")
    assert (r_minus.status_code, r_minus.json()) == (r_mayus.status_code, r_mayus.json())
    _entrar(cliente, "admin", "mala")
    _entrar(cliente, "Admin", "mala")
    _assert_bloqueo(_entrar(cliente, "admin", "mala"), segundos=300)   # 5.º sumando ambos
    _assert_bloqueo(_entrar(cliente, "Admin", "mala"))
    _assert_bloqueo(_entrar(cliente, "admin", "admin1234"))


def test_clave_correcta_no_cuenta_como_fallo(cliente):
    for _ in range(4):
        assert _login(cliente, "bloqueo", "mala").status_code == 401
    assert _login(cliente, "bloqueo").status_code == 200   # reinicia el contador
    for _ in range(4):
        assert _login(cliente, "bloqueo", "mala").status_code == 401


# ── Token, sesión y logout ────────────────────────────────────────────────────

@pytest.mark.parametrize("cabecera", [{}, {"Authorization": "Bearer no-existe"}])
def test_token_invalido_401_sesion_invalida(cliente, cabecera):
    for r in (cliente.get("/auth/sesion", headers=cabecera),
              cliente.post("/auth/logout", headers=cabecera)):
        assert r.status_code == 401
        assert r.json()["codigo"] == "sesion_invalida"
        assert r.headers.get("www-authenticate") == "Bearer"


def test_get_auth_sesion_devuelve_usuario_y_rol(cliente):
    r = cliente.get("/auth/sesion", headers=_auth(_token(cliente, "ingeniero")))
    assert r.status_code == 200 and r.json() == {"usuario": "ing1", "rol": "ingeniero"}
    # también con el cambio de contraseña pendiente
    r = cliente.get("/auth/sesion", headers=_auth(_token(cliente, "pendiente")))
    assert r.status_code == 200 and r.json() == {"usuario": "Admin", "rol": "admin"}   # U11


def test_dos_sesiones_simultaneas_y_cierre_en_una(cliente):
    """Decisión 8: un logout invalida solo su token."""
    t1, t2 = _token(cliente, "tecnico"), _token(cliente, "tecnico")
    assert t1 != t2
    assert cliente.post("/auth/logout", headers=_auth(t1)).status_code == 200
    assert cliente.get("/auth/sesion", headers=_auth(t1)).status_code == 401
    assert cliente.get("/auth/sesion", headers=_auth(t2)).status_code == 200


def test_clave_pendiente_403_en_escrituras(cliente):
    r = cliente.post("/usuarios", headers=_auth(_token(cliente, "pendiente")), json={
        "nombre": "Otro", "usuario": "otro1", "clave": CLAVE, "confirmacion": CLAVE,
        "rol": "tecnico"})
    assert r.status_code == 403
    assert r.json() == {"detail": "Debe cambiar la contraseña", "codigo": "clave_pendiente"}


# ── Cambio de contraseña ──────────────────────────────────────────────────────

def test_cambio_de_clave_errores_y_exito(cliente):
    tok = _token(cliente, "pendiente")
    r = _cambio(cliente, tok, "mala")
    assert r.status_code == 403
    assert r.json() == {"detail": "La contraseña actual no es correcta",
                        "codigo": "clave_actual_incorrecta"}
    casos = [
        (("", "nueva12345"), [{"campo": "clave_actual", "codigo": "obligatorio"}]),
        (("admin1234", "corta"), [{"campo": "clave_nueva", "codigo": "corta"}]),
        (("admin1234", "nueva12345", "otra12345"),
         [{"campo": "confirmacion", "codigo": "no_coinciden"}]),
        (("admin1234", "admin1234"), [{"campo": "clave_nueva", "codigo": "igual_actual"}]),
    ]
    for args, errores in casos:
        r = _cambio(cliente, tok, *args)
        assert r.status_code == 422
        assert r.json() == {"detail": "Datos inválidos", "codigo": "validacion", "errores": errores}
    assert _cambio(cliente, tok, "admin1234").status_code == 200
    # la misma sesión ya no tiene el cambio pendiente: puede escribir
    r = cliente.post("/usuarios", headers=_auth(tok), json={
        "nombre": "Otro", "usuario": "otro1", "clave": CLAVE, "confirmacion": CLAVE,
        "rol": "tecnico"})
    assert r.status_code == 200
    assert _entrar(cliente, "admin", "nueva12345").json()["debe_cambiar_clave"] is False


def test_fallos_de_clave_actual_bloquean_e_invalidan_el_token(cliente):
    """H-T8-01: al 5.º fallo, 429 con el mismo cuerpo del login y token invalidado."""
    tok = _token(cliente, "bloqueo")
    for _ in range(4):
        assert _cambio(cliente, tok, "mala").status_code == 403
    _assert_bloqueo(_cambio(cliente, tok, "mala"), segundos=300)
    assert cliente.get("/auth/sesion", headers=_auth(tok)).status_code == 401
    _assert_bloqueo(_login(cliente, "bloqueo"))


def test_login_y_cambio_de_clave_comparten_contador(cliente):
    for _ in range(2):
        assert _login(cliente, "bloqueo", "mala").status_code == 401
    tok = _token(cliente, "bloqueo")           # login correcto: reinicia
    for _ in range(2):
        assert _login(cliente, "bloqueo", "mala").status_code == 401
    for _ in range(2):
        assert _cambio(cliente, tok, "mala").status_code == 403
    _assert_bloqueo(_cambio(cliente, tok, "mala"))   # 5.º sumando login y cambio


def test_cambio_de_clave_exitoso_reinicia_el_contador(cliente):
    tok = _token(cliente, "bloqueo")
    for _ in range(4):
        assert _login(cliente, "bloqueo", "mala").status_code == 401
    assert _cambio(cliente, tok, CLAVE).status_code == 200
    for _ in range(4):
        assert _login(cliente, "bloqueo", "mala").status_code == 401


# ── POST /usuarios ────────────────────────────────────────────────────────────

def _nuevo(**cambios):
    return {"nombre": "Nuevo Uno", "usuario": "nuevo1", "clave": CLAVE,
            "confirmacion": CLAVE, "rol": "tecnico", "activo": True, **cambios}


def test_usuarios_422_con_los_nombres_de_campo_del_cuerpo(cliente):
    r = cliente.post("/usuarios", headers=_auth(_token(cliente, "admin")), json=_nuevo(
        nombre="", usuario="a b", clave="x", confirmacion="", rol="biomedico"))
    assert r.status_code == 422
    assert r.json() == {"detail": "Datos inválidos", "codigo": "validacion", "errores": [
        {"campo": "nombre", "codigo": "obligatorio"},
        {"campo": "usuario", "codigo": "formato"},
        {"campo": "clave", "codigo": "corta"},
        {"campo": "confirmacion", "codigo": "obligatorio"},
        {"campo": "rol", "codigo": "rol_invalido"},
    ]}


def test_usuarios_403_rol_no_creable_y_rol_sin_permiso(cliente):
    r = cliente.post("/usuarios", headers=_auth(_token(cliente, "admin")),
                     json=_nuevo(rol="ingeniero"))
    assert r.status_code == 403
    assert r.json() == {"detail": "Su rol no puede crear usuarios con ese rol",
                        "codigo": "rol_no_creable"}
    r = cliente.post("/usuarios", headers=_auth(_token(cliente, "tecnico")), json=_nuevo())
    assert r.status_code == 403
    assert r.json() == {"detail": "Su rol no tiene permiso para esta acción",
                        "codigo": "rol_sin_permiso"}


def test_usuarios_409_usuario_existe_sin_distinguir_mayusculas(cliente):
    cab = _auth(_token(cliente, "ingeniero"))
    assert cliente.post("/usuarios", headers=cab, json=_nuevo()).status_code == 200
    r = cliente.post("/usuarios", headers=cab, json=_nuevo(usuario="NUEVO1"))
    assert r.status_code == 409
    assert r.json() == {"detail": "El usuario ya existe", "codigo": "usuario_existe"}

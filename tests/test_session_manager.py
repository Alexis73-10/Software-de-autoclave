import pytest
from autoclave.ui.service_ui.session_manager import SessionManager, hash_password


@pytest.fixture(autouse=True)
def reset():
    SessionManager.logout()
    yield
    SessionManager.logout()


def test_is_authenticated_false_por_defecto():
    assert not SessionManager.is_authenticated()


def test_current_role_none_sin_sesion():
    assert SessionManager.current_role() is None


def test_current_user_none_sin_sesion():
    assert SessionManager.current_user() is None


def test_login_autentica():
    SessionManager.login({"id": 1, "nombre": "Admin", "usuario": "admin", "rol": "admin"})
    assert SessionManager.is_authenticated()


def test_login_guarda_rol():
    SessionManager.login({"id": 1, "nombre": "Admin", "usuario": "admin", "rol": "admin"})
    assert SessionManager.current_role() == "admin"


def test_login_guarda_nombre_y_usuario():
    SessionManager.login({"id": 2, "nombre": "Ope", "usuario": "op1", "rol": "operador"})
    u = SessionManager.current_user()
    assert u["nombre"] == "Ope"
    assert u["usuario"] == "op1"


def test_logout_cierra_sesion():
    SessionManager.login({"id": 1, "nombre": "Admin", "usuario": "admin", "rol": "admin"})
    SessionManager.logout()
    assert not SessionManager.is_authenticated()
    assert SessionManager.current_user() is None


def test_login_sobrescribe_sesion_anterior():
    SessionManager.login({"id": 1, "nombre": "A", "usuario": "a", "rol": "admin"})
    SessionManager.login({"id": 2, "nombre": "B", "usuario": "b", "rol": "operador"})
    assert SessionManager.current_user()["usuario"] == "b"


def test_hash_password_determinista():
    assert hash_password("abc123") == hash_password("abc123")


def test_hash_password_diferencia_passwords():
    assert hash_password("abc123") != hash_password("abc124")


def test_hash_password_es_sha256_hex():
    import hashlib
    expected = hashlib.sha256("test".encode()).hexdigest()
    assert hash_password("test") == expected


# ── T-8: token aparte del dict de sesión y cambio obligatorio ────────────────

def test_token_fuera_del_dict_y_id_opcional():
    SessionManager.login({"nombre": "N", "usuario": "u", "rol": "admin"}, token="tok-x")
    usuario = SessionManager.current_user()
    assert usuario["id"] is None and "token" not in usuario
    assert "tok-x" not in repr(usuario)
    assert SessionManager.token() == "tok-x"
    SessionManager.logout()
    assert SessionManager.token() is None


def test_bandera_de_cambio_obligatorio():
    SessionManager.login({"nombre": "N", "usuario": "u", "rol": "admin",
                          "debe_cambiar_clave": True}, token="t")
    assert SessionManager.debe_cambiar_clave()
    SessionManager.clave_cambiada()
    assert not SessionManager.debe_cambiar_clave()
    assert SessionManager.token() == "t"

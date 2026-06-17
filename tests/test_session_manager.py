import pytest
from autoclave.ui_pyside.services.session_manager import SessionManager, hash_password


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

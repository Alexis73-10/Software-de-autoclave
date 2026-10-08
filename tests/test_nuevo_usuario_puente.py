# Puente QML ↔ backend de la pantalla Nuevo Usuario
# (planeacion_nuevo_usuario.md, F2 y sección 10; planeacion_backend_autenticacion.md,
# decisión 26 y T-20: crea el usuario con POST /usuarios y el token de la sesión).

import logging

import pytest

from autoclave.ui_pyside.services.roles import ROLES
from autoclave.ui_pyside.services.session_manager import SessionManager
from autoclave.ui_pyside.views.nuevo_usuario.puente import NuevoUsuarioBridge

ADMIN = {"id": 1, "nombre": "Administrador", "usuario": "admin", "rol": "admin", "token": "tok-admin"}
INGENIERO = {"id": 3, "nombre": "Ing", "usuario": "ing1", "rol": "ingeniero", "token": "tok-ing"}
TECNICO = {"id": 2, "nombre": "Tec", "usuario": "tec1", "rol": "tecnico", "token": "tok-tec"}

VALIDOS = dict(nombre="Ana Ruiz", usuario="anar", password="clave1234",
               confirmacion="clave1234", rol="tecnico")


class BackendFalso:
    """Registra los POST y responde con (código, cuerpo) configurables."""
    def __init__(self, respuesta=(200, {"ok": True})):
        self.respuesta = respuesta
        self.llamadas = []

    def __call__(self, ruta, cuerpo, token):
        self.llamadas.append((ruta, cuerpo, token))
        if isinstance(self.respuesta, Exception):
            raise self.respuesta
        return self.respuesta


@pytest.fixture(autouse=True)
def sesion_limpia():
    SessionManager.logout()
    yield
    SessionManager.logout()


@pytest.fixture
def backend():
    return BackendFalso()


@pytest.fixture
def puente(backend):
    return NuevoUsuarioBridge(enviar=backend)


def _validar(puente, **cambios):
    d = {**VALIDOS, **cambios}
    return puente.validar(d["nombre"], d["usuario"], d["password"],
                          d["confirmacion"], d["rol"])


def _guardar(puente, activo=True, **cambios):
    d = {**VALIDOS, **cambios}
    return puente.guardar(d["nombre"], d["usuario"], d["password"],
                          d["confirmacion"], d["rol"], activo)


# ── Propiedades ───────────────────────────────────────────────────────────────

def test_roles_validos_sin_biomedico():
    assert [v for v, _ in ROLES] == ["admin", "tecnico", "ingeniero"]
    assert [e for _, e in ROLES] == ["Admin", "Técnico", "Ingeniero"]


@pytest.mark.parametrize("sesion,esperados", [
    (None, []),
    (TECNICO, []),
    (ADMIN, ["admin", "tecnico"]),
    (INGENIERO, ["admin", "tecnico", "ingeniero"]),
])
def test_roles_ofrecidos_segun_quien_crea(puente, sesion, esperados):
    if sesion:
        SessionManager.login(sesion)
    puente.actualizarSesion()
    assert [r["valor"] for r in puente.roles] == esperados


def test_min_longitud_password(puente):
    assert puente.minLongitudPassword == 8


def test_usuario_actual(puente):
    assert puente.usuarioActual == ""
    SessionManager.login(ADMIN)
    puente.actualizarSesion()
    assert puente.usuarioActual == "admin"


# ── Control de acceso (NU-05) ─────────────────────────────────────────────────

def test_puede_crear_falso_sin_sesion(puente):
    assert puente.puedeCrear() is False


def test_puede_crear_falso_con_tecnico(puente):
    SessionManager.login(TECNICO)
    assert puente.puedeCrear() is False


@pytest.mark.parametrize("sesion", [ADMIN, INGENIERO])
def test_puede_crear_verdadero_con_admin_o_ingeniero(puente, sesion):
    SessionManager.login(sesion)
    assert puente.puedeCrear() is True


def test_guardar_rechaza_tecnico_sin_llamar_al_backend(puente, backend):
    SessionManager.login(TECNICO)
    r = _guardar(puente)
    assert r["ok"] is False
    assert r["errores"].get("general")
    assert backend.llamadas == []


def test_guardar_rechaza_sin_sesion(puente, backend):
    r = _guardar(puente)
    assert r["ok"] is False
    assert backend.llamadas == []


# ── Validaciones (las mismas que aplica el backend) ───────────────────────────

def test_datos_validos_sin_errores(puente):
    assert _validar(puente) == {}


@pytest.mark.parametrize("campo", ["nombre", "usuario", "password", "confirmacion"])
def test_obligatorios(puente, campo):
    assert _validar(puente, **{campo: ""})[campo] == "Campo obligatorio"


def test_nombre_solo_espacios_es_obligatorio(puente):
    assert _validar(puente, nombre="   ")["nombre"] == "Campo obligatorio"


def test_nombre_maximo_50(puente):
    assert "nombre" not in _validar(puente, nombre="a" * 50)
    assert _validar(puente, nombre="a" * 51)["nombre"] == "Máximo 50 caracteres"


@pytest.mark.parametrize("usuario", ["ab", "a" * 31, "ana r", " anar", "anar\t"])
def test_usuario_longitud_y_espacios(puente, usuario):
    assert _validar(puente, usuario=usuario)["usuario"] == "Sin espacios, de 3 a 30 caracteres"


@pytest.mark.parametrize("usuario", ["abc", "a" * 30])
def test_usuario_limites_validos(puente, usuario):
    assert "usuario" not in _validar(puente, usuario=usuario)


def test_password_minimo_8(puente):
    e = _validar(puente, password="1234567", confirmacion="1234567")
    assert e["password"] == "Mínimo 8 caracteres"


def test_password_maximo_64(puente):
    largo = "a" * 65
    e = _validar(puente, password=largo, confirmacion=largo)
    assert e["password"] == "Máximo 64 caracteres"


def test_confirmacion_distinta(puente):
    e = _validar(puente, confirmacion="otra12345")
    assert e["confirmacion"] == "Las contraseñas no coinciden"


@pytest.mark.parametrize("rol", ["", "operador", "Admin", "biomedico"])
def test_rol_invalido(puente, rol):
    assert _validar(puente, rol=rol)["rol"] == "Seleccione un rol"


def test_todos_los_errores_a_la_vez(puente):
    e = puente.validar("", "", "", "", "")
    assert set(e) == {"nombre", "usuario", "password", "confirmacion", "rol"}


def test_unicidad_la_decide_el_backend(puente):
    # sin acceso a la base: la validación local no consulta duplicados
    assert "usuario" not in _validar(puente)


# ── Guardar ───────────────────────────────────────────────────────────────────

def test_guardar_exito_envia_al_backend_con_token(puente, backend):
    SessionManager.login(ADMIN)
    creados = []
    puente.usuarioCreado.connect(creados.append)
    r = _guardar(puente, nombre="  Ana Ruiz  ")
    assert r == {"ok": True, "errores": {}}
    assert backend.llamadas == [("/usuarios", {
        "nombre": "Ana Ruiz", "usuario": "anar", "clave": "clave1234",
        "confirmacion": "clave1234", "rol": "tecnico", "activo": True,
    }, "tok-admin")]
    assert creados == ["anar"]


def test_guardar_inactivo(puente, backend):
    SessionManager.login(ADMIN)
    assert _guardar(puente, activo=False)["ok"] is True
    assert backend.llamadas[0][1]["activo"] is False


def test_guardar_con_errores_no_llama_al_backend(puente, backend):
    SessionManager.login(ADMIN)
    r = _guardar(puente, confirmacion="otra12345")
    assert r["ok"] is False
    assert r["errores"]["confirmacion"] == "Las contraseñas no coinciden"
    assert backend.llamadas == []


def test_guardar_sin_token_en_la_sesion(puente, backend):
    SessionManager.login({**ADMIN, "token": None})
    r = _guardar(puente)
    assert r["ok"] is False
    assert "inicie sesión" in r["errores"]["general"]
    assert backend.llamadas == []


@pytest.mark.parametrize("respuesta,errores", [
    ((409, {"detail": "El usuario ya existe"}), {"usuario": "El usuario ya existe"}),
    ((401, {"detail": "x"}), {"general": "Sesión no válida o vencida; inicie sesión de nuevo"}),
    ((403, {"detail": "Su rol no puede crear usuarios con ese rol"}),
     {"general": "Su rol no puede crear usuarios con ese rol"}),
    ((422, {"detail": {"errores": {"password": "Mínimo 8 caracteres"}}}),
     {"password": "Mínimo 8 caracteres"}),
    ((500, {}), {"general": "No se pudo guardar el usuario"}),
])
def test_guardar_traduce_respuestas_del_backend(respuesta, errores):
    SessionManager.login(ADMIN)
    creados = []
    p = NuevoUsuarioBridge(enviar=BackendFalso(respuesta))
    p.usuarioCreado.connect(creados.append)
    assert _guardar(p) == {"ok": False, "errores": errores}
    assert creados == []


def test_guardar_backend_caido_no_expone_detalles():
    SessionManager.login(ADMIN)
    p = NuevoUsuarioBridge(enviar=BackendFalso(ConnectionError("http://127.0.0.1:8000 interno")))
    r = _guardar(p)
    assert r["ok"] is False
    assert "127.0.0.1" not in r["errores"]["general"]


# ── Logs ──────────────────────────────────────────────────────────────────────

def test_password_no_aparece_en_logs(caplog):
    SessionManager.login(ADMIN)
    with caplog.at_level(logging.DEBUG):
        _guardar(NuevoUsuarioBridge(enviar=BackendFalso()))
        _guardar(NuevoUsuarioBridge(enviar=BackendFalso((409, {}))))
        _guardar(NuevoUsuarioBridge(enviar=BackendFalso()), confirmacion="otra12345")
    texto = caplog.text
    assert "clave1234" not in texto
    assert "usuario creado: anar, rol tecnico, por admin" in texto


# ── Navegación ────────────────────────────────────────────────────────────────

def test_navegar_emite_destino(puente):
    destinos = []
    puente.solicitudNavegar.connect(destinos.append)
    puente.navegar("home")
    assert destinos == ["home"]


def test_salir_cierra_sesion_y_va_a_login(puente):
    SessionManager.login(ADMIN)
    destinos = []
    puente.solicitudNavegar.connect(destinos.append)
    puente.salir()
    assert SessionManager.is_authenticated() is False
    assert destinos == ["login"]

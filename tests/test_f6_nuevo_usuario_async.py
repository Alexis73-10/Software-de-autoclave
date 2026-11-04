# tests/test_f6_nuevo_usuario_async.py
#
# FASE 6 (AJUSTES 2026-11-02, paso 2): alta de usuario asíncrona y sin
# optimismo. `guardar` devuelve {enviado, errores}; el desenlace llega por
# guardadoResuelto(estado, errores). Sin respuesta se relee GET /usuarios; nunca
# se reintenta solo (POST /usuarios no es idempotente).

import sys

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from autoclave.cliente.session_manager import SessionManager
from autoclave.ui_pyside.views.nuevo_usuario.puente import NuevoUsuarioBridge
from autoclave.ui_qml import sesion_backend as sb
from autoclave.ui_qml.operacion_critica import (
    CONFIRMADA, RECHAZADA, SIN_CONFIRMAR, VERIFICANDO)

ADMIN = {"id": 1, "nombre": "Administrador", "usuario": "admin", "rol": "admin", "token": "tok"}
VALIDOS = ("Ana Ruiz", "anar", "clave1234", "clave1234", "tecnico", True)
NO_RESPONDE = sb.Resultado(sb.BACKEND_NO_RESPONDE)


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QApplication(sys.argv)


@pytest.fixture(autouse=True)
def sesion_admin():
    SessionManager.login(ADMIN)
    yield
    SessionManager.logout()


class SesionDoble:
    def __init__(self):
        self.generacion = 0
        self.envios = []

    def enviar_async(self, metodo, ruta, cuerpo=None, al_terminar=None, *, dueno=None,
                     al_tardio=None, plazo_s=None):
        self.envios.append({"metodo": metodo, "ruta": ruta, "cuerpo": cuerpo,
                            "al_terminar": al_terminar, "al_tardio": al_tardio,
                            "plazo_s": plazo_s})
        return True

    def cancelar_envios(self, dueno):
        pass

    def de(self, metodo):
        return [e for e in self.envios if e["metodo"] == metodo]


PREVIA = sb.Resultado("ok", {"usuarios": [{"usuario": "admin", "nombre": "Administrador",
                                           "rol": "admin", "activo": 1}]}, 200)


class _SesionPrevia(SesionDoble):
    """MENOR-4: la lista previa (GET /usuarios antes del POST) se entrega en
    el acto con `previa`; `envios` guarda solo lo posterior (POST y relecturas)."""

    def __init__(self, previa=PREVIA):
        super().__init__()
        self.previa = previa
        self.previas = []

    def enviar_async(self, metodo, ruta, cuerpo=None, al_terminar=None, **kw):
        if metodo == "GET" and not self.previas and not self.envios:
            self.previas.append(ruta)
            if self.previa is not None:
                al_terminar(self.previa)
            return True
        return super().enviar_async(metodo, ruta, cuerpo, al_terminar, **kw)


def _puente(previa=PREVIA):
    s = _SesionPrevia(previa)
    p = NuevoUsuarioBridge(sesion=s)
    res, creados = [], []
    p.guardadoResuelto.connect(lambda e, err: res.append((e, err)))
    p.usuarioCreado.connect(creados.append)
    return p, s, res, creados


def _lista(rol="tecnico", activo=1, usuario="anar", nombre="Ana Ruiz"):
    return sb.Resultado("ok", {"usuarios": [{"usuario": "admin", "nombre": "Administrador",
                                             "rol": "admin", "activo": 1},
                                            {"usuario": usuario, "nombre": nombre,
                                             "rol": rol, "activo": activo}]},
                        200)


def test_200_confirma_y_avisa_al_host():
    p, s, res, creados = _puente()
    assert p.guardar(*VALIDOS) == {"enviado": True, "errores": {}}
    assert s.envios[0]["ruta"] == "/usuarios" and s.envios[0]["plazo_s"] == 10.0
    assert p.operacionEnCurso and p.estadoDe("alta_usuario") == "enviando"
    assert creados == [] and res == []                      # nada antes del 200
    s.envios[0]["al_terminar"](sb.Resultado("ok", {"ok": True}, 200))
    assert res == [(CONFIRMADA, {})] and creados == ["anar"] and not p.operacionEnCurso


def test_rechazo_con_errores_por_campo():
    p, s, res, creados = _puente()
    p.guardar(*VALIDOS)
    s.envios[0]["al_terminar"](sb.Resultado("usuario_existe", {"codigo": "usuario_existe"}, 409))
    assert res == [(RECHAZADA, {"usuario": {"clave": "usuarios.usuario_existe", "valores": {}}})]
    assert creados == []


def test_rechazo_general():
    p, s, res, _ = _puente()
    p.guardar(*VALIDOS)
    s.envios[0]["al_terminar"](sb.Resultado("rol_no_creable", {"codigo": "rol_no_creable"}, 403))
    assert res == [(RECHAZADA, {"general": {"clave": "usuarios.rol_no_creable", "valores": {}}})]


def test_sin_respuesta_relectura_que_coincide_confirma():
    p, s, res, creados = _puente()
    p.guardar(*VALIDOS)
    s.envios[0]["al_terminar"](NO_RESPONDE)
    assert p.estadoDe("alta_usuario") == VERIFICANDO and res == []
    get = s.de("GET")[0]
    assert get["ruta"] == "/usuarios"
    get["al_terminar"](_lista())
    assert res == [(CONFIRMADA, {})] and creados == ["anar"]


@pytest.mark.parametrize("lectura", [
    _lista(usuario="otro"),                 # no existe
    _lista(rol="admin"),                    # existe con otro rol
    _lista(activo=0),                       # existe con otro estado
    _lista(nombre="Otra Persona"),          # existe con otro nombre
    NO_RESPONDE,                            # sin lectura
])
def test_sin_respuesta_relectura_que_no_coincide_es_sin_confirmar(lectura):
    p, s, res, creados = _puente()
    p.guardar(*VALIDOS)
    s.envios[0]["al_terminar"](NO_RESPONDE)
    s.de("GET")[0]["al_terminar"](lectura)
    assert res == [(SIN_CONFIRMAR, {"general": {"clave": "operacion.sin_confirmar", "valores": {}}})]
    assert creados == []
    assert len(s.de("POST")) == 1                           # nunca se reintenta


def test_doble_toque_sin_segundo_envio():
    p, s, _, _ = _puente()
    assert p.guardar(*VALIDOS)["enviado"] is True
    assert p.guardar(*VALIDOS) == {"enviado": False, "errores": {}}
    assert len(s.de("POST")) == 1


def test_validacion_local_no_envia():
    p, s, res, _ = _puente()
    r = p.guardar("Ana Ruiz", "anar", "clave1234", "otra12345", "tecnico", True)
    assert r["enviado"] is False and "confirmacion" in r["errores"]
    assert s.envios == [] and res == []


def test_tardio_200_tras_sin_confirmar():
    p, s, res, creados = _puente()
    p.guardar(*VALIDOS)
    post = s.envios[0]
    post["al_terminar"](NO_RESPONDE)
    s.de("GET")[0]["al_terminar"](_lista(usuario="otro"))
    assert res[-1][0] == SIN_CONFIRMAR
    post["al_tardio"](sb.Resultado("ok", {"ok": True}, 200))
    assert res[-1] == (CONFIRMADA, {}) and creados == ["anar"]
    assert len(s.de("POST")) == 1


def test_la_contrasena_no_va_al_log(caplog):
    import logging
    p, s, _, _ = _puente()
    with caplog.at_level(logging.DEBUG):
        p.guardar(*VALIDOS)
        s.envios[0]["al_terminar"](NO_RESPONDE)
        s.de("GET")[0]["al_terminar"](NO_RESPONDE)
    assert "clave1234" not in caplog.text


# ── MENOR-4 (corrección tras revisión, 04-nov) ─────────────────────────────

def test_toma_la_lista_previa_antes_de_enviar():
    p, s, _, _ = _puente()
    p.guardar(*VALIDOS)
    assert s.previas == ["/usuarios"] and s.envios[0]["metodo"] == "POST"


def test_usuario_que_ya_existia_no_se_confirma_por_relectura():
    """Si «anar» ya estaba antes de enviar (p. ej. 409 que no llegó), verlo en
    la relectura no prueba que esta alta se hiciera."""
    previa = _lista()                       # ya existe con el mismo nombre, rol y estado
    p, s, res, creados = _puente(previa)
    p.guardar(*VALIDOS)
    s.envios[0]["al_terminar"](NO_RESPONDE)
    s.de("GET")[0]["al_terminar"](_lista())
    assert res == [(SIN_CONFIRMAR, {"general": {"clave": "operacion.sin_confirmar", "valores": {}}})]
    assert creados == []


@pytest.mark.parametrize("previa", [NO_RESPONDE, sb.Resultado("ok", {"x": 1}, 200)],
                         ids=["fallo", "invalida"])
def test_sin_lista_previa_la_relectura_no_confirma(previa):
    p, s, res, creados = _puente(previa)
    p.guardar(*VALIDOS)
    assert len(s.de("POST")) == 1           # se envía igual
    s.envios[0]["al_terminar"](NO_RESPONDE)
    s.de("GET")[0]["al_terminar"](_lista())
    assert res[-1][0] == SIN_CONFIRMAR and creados == []


def test_durante_la_lectura_previa_ya_figura_en_curso_y_sin_doble_envio():
    p, s, res, _ = _puente(previa=None)     # la lista previa aún no llega
    assert p.guardar(*VALIDOS) == {"enviado": True, "errores": {}}
    assert p.operacionEnCurso and p.estadoDe("alta_usuario") == "enviando"
    assert p.guardar(*VALIDOS) == {"enviado": False, "errores": {}}
    assert s.de("POST") == [] and res == []


# ── H1-H3 (3.er ciclo de corrección, 04-nov) ───────────────────────────────

OTRO = ("Beto Paz", "betop", "clave5678", "clave5678", "tecnico", True)
OK = sb.Resultado("ok", {"ok": True}, 200)


def _a_sin_confirmar(p, s):
    """Alta A ('anar') sin confirmar: sin respuesta y relectura sin lectura."""
    p.guardar(*VALIDOS)
    post_a = s.de("POST")[0]
    post_a["al_terminar"](NO_RESPONDE)
    s.de("GET")[-1]["al_terminar"](NO_RESPONDE)
    return post_a


def test_h1_tardio_de_A_con_B_en_lectura_previa_no_da_exito_ni_navega():
    """Escenario exacto de la revisión: A sin confirmar -> B en su lectura
    previa -> 200 tardío de A -> ni éxito, ni usuarioCreado, ni desenlace."""
    p, s, res, creados = _puente()
    todos = []
    p.guardadoResuelto.connect(lambda *a: todos.append(a))
    post_a = _a_sin_confirmar(p, s)
    assert res == [(SIN_CONFIRMAR, {"general": {"clave": "operacion.sin_confirmar",
                                                "valores": {}}})]
    assert p.guardar(*OTRO) == {"enviado": True, "errores": {}}
    previa_b = s.de("GET")[-1]                 # lectura previa de B, sin respuesta aún
    assert p.operacionEnCurso and p.estadoDe("alta_usuario") == "enviando"
    post_a["al_tardio"](OK)                    # 200 tardío de A
    assert len(res) == 1 and creados == []     # nada para B (ni para A en pantalla)
    assert len(todos) == 1
    # B sigue su curso con su propio contexto
    previa_b["al_terminar"](PREVIA)
    post_b = s.de("POST")[-1]
    assert post_b["cuerpo"]["usuario"] == "betop"
    post_b["al_terminar"](OK)
    assert res[-1] == (CONFIRMADA, {}) and creados == ["betop"]
    assert todos[-1] == (CONFIRMADA, {}, "", p.altaActual)


def test_h1_tardio_de_A_con_B_vigente_no_da_exito():
    p, s, res, creados = _puente()
    post_a = _a_sin_confirmar(p, s)
    p.guardar(*OTRO)
    s.de("GET")[-1]["al_terminar"](PREVIA)
    assert s.de("POST")[-1]["cuerpo"]["usuario"] == "betop" and p.operacionEnCurso
    post_a["al_tardio"](OK)
    assert len(res) == 1 and creados == []


def test_h1_tardio_de_A_tras_B_rechazado_no_da_exito_para_B():
    p, s, res, creados = _puente()
    post_a = _a_sin_confirmar(p, s)
    p.guardar(*OTRO)
    s.de("GET")[-1]["al_terminar"](PREVIA)
    s.de("POST")[-1]["al_terminar"](sb.Resultado("rol_no_creable",
                                                 {"codigo": "rol_no_creable"}, 403))
    assert res[-1][0] == RECHAZADA and not p.operacionEnCurso
    n = len(res)
    post_a["al_tardio"](OK)                    # A ya no es el alta actual
    assert len(res) == n and creados == []


def test_h1_conciliacion_usa_el_contexto_de_su_operacion():
    """La relectura de B concilia con los datos de B, no con los de A."""
    p, s, res, creados = _puente()
    _a_sin_confirmar(p, s)
    p.guardar(*OTRO)
    s.de("GET")[-1]["al_terminar"](PREVIA)
    s.de("POST")[-1]["al_terminar"](NO_RESPONDE)
    s.de("GET")[-1]["al_terminar"](_lista())   # aparece 'anar' (A), no 'betop'
    assert res[-1][0] == SIN_CONFIRMAR and creados == []


def test_h1_tardio_del_alta_actual_si_avisa_con_mensaje_y_numero():
    p, s, _res, creados = _puente()
    todos = []
    p.guardadoResuelto.connect(lambda *a: todos.append(a))
    post_a = _a_sin_confirmar(p, s)
    post_a["al_tardio"](OK)
    assert todos[-1] == (CONFIRMADA, {}, "operacion.confirmada_tarde", p.altaActual)
    assert creados == ["anar"]


class _SesionQueFalla(SesionDoble):
    def enviar_async(self, *a, **k):
        raise RuntimeError("sin sesión")


def test_h2_fallo_al_pedir_la_lista_previa_no_deja_el_alta_en_curso():
    p = NuevoUsuarioBridge(sesion=_SesionQueFalla())
    cambios = []
    p.operacionEnCursoChanged.connect(lambda: cambios.append(p.operacionEnCurso))
    r = p.guardar(*VALIDOS)
    assert r == {"enviado": False,
                 "errores": {"general": {"clave": "usuarios.guardado_error", "valores": {}}}}
    assert not p.operacionEnCurso and p.estadoDe("alta_usuario") == "inactiva"
    assert cambios and cambios[-1] is False
    # no queda bloqueado: un nuevo intento vuelve a intentarlo
    assert p.guardar(*VALIDOS)["enviado"] is False


def test_h3_abandonar_durante_la_lectura_previa_no_envia_el_post():
    s = SesionDoble()                          # guarda también la lectura previa
    p = NuevoUsuarioBridge(sesion=s)
    res, creados = [], []
    p.guardadoResuelto.connect(lambda *a: res.append(a))
    p.usuarioCreado.connect(creados.append)
    p.guardar(*VALIDOS)
    previa = s.de("GET")[0]
    assert p.operacionEnCurso
    p.abandonarPreparacion()                   # la pantalla se cerró
    assert not p.operacionEnCurso
    previa["al_terminar"](PREVIA)              # la lectura llega después
    assert s.de("POST") == [] and res == [] and creados == []
    # la pantalla nueva puede guardar normalmente
    assert p.guardar(*VALIDOS)["enviado"] is True


def test_h3_abandonar_no_toca_un_alta_ya_enviada():
    p, s, res, _ = _puente()
    p.guardar(*VALIDOS)
    p.abandonarPreparacion()                   # el POST ya salió
    assert p.operacionEnCurso
    s.de("POST")[0]["al_terminar"](OK)
    assert res == [(CONFIRMADA, {})]

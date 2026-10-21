# C1a (tanda 6, P3-1): teclado en pantalla para PySide (sin QInputDialog).

import ast
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QDialog, QDoubleSpinBox, QLineEdit, QSpinBox

from autoclave.ui_pyside.views import _teclado_pantalla as tp

RAIZ = Path(__file__).resolve().parents[1] / "src" / "autoclave"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_ninguna_vista_pyside_usa_qinputdialog():
    culpables = []
    for f in (RAIZ / "ui_pyside").rglob("*.py"):
        arbol = ast.parse(f.read_text(encoding="utf-8"))
        for n in ast.walk(arbol):
            if isinstance(n, ast.Name) and n.id == "QInputDialog":
                culpables.append(str(f))
            if isinstance(n, ast.alias) and n.name == "QInputDialog":
                culpables.append(str(f))
    assert culpables == []


def test_tamano_de_tecla_igual_al_qml():
    qml = (RAIZ / "ui_qml" / "qml" / "Tema" / "Teclado.qml").read_text(encoding="utf-8")
    assert "anchoTecla: %d" % tp.ANCHO_TECLA in qml
    assert "altoTecla: %d" % tp.ALTO_TECLA in qml
    assert "separacion: %d" % tp.SEPARACION in qml


def test_tecla_a_escala_uno_mide_96x88(app):
    t = tp.TecladoAlfanumerico(factor=1.0)
    assert (t._filas[0][0].width(), t._filas[0][0].height()) == (96, 88)
    n = tp.TecladoNumerico(factor=1.0)
    assert (n.teclas["7"].width(), n.teclas["7"].height()) == (96, 88)


def test_alfanumerico_mayuscula_un_solo_uso_y_numeros(app):
    t = tp.TecladoAlfanumerico(factor=0.5)
    assert t.mayusculas is True            # campo vacío: Aa armada
    t.pulsar("a"); t.pulsar("b")
    assert t.texto == "Ab"
    t.alternar_capa(); assert t.capa == "numeros"
    t.pulsar_posicion(0, 0); t.pulsar_posicion(1, 0)
    assert t.texto == "Ab1@"
    t.pulsar("#")                           # fuera del juego TEC-D03
    assert t.texto == "Ab1@"
    t.borrar(); t.borrar(); t.borrar(); t.borrar()
    assert t.texto == "" and t.mayusculas is True


def test_numerico_valida_rango(app):
    n = tp.TecladoNumerico(minimo=0, maximo=10, decimales=1, factor=0.5)
    for k in "12":
        n.pulsar(k)
    assert not n.tecla_confirmar.isEnabled()
    n.borrar(); n.pulsar("."); n.pulsar("5")
    assert n.texto == "1.5" and n.tecla_confirmar.isEnabled()
    assert not n.teclas["-"].isEnabled()    # mínimo >= 0: sin signo


def test_credenciales_confirmar_pasa_a_clave_y_acepta(app):
    d = tp.DialogoCredenciales(None, "T", "M")
    assert d.activo == "usuario"
    for c in "tec1":
        d.teclado.pulsar(c)
    d.teclado.confirmado.emit()
    assert d.activo == "clave"
    for c in "Clave9":
        d.teclado.pulsar(c)
    assert d.campo_clave.echoMode() == QLineEdit.EchoMode.Password
    d.teclado.confirmado.emit()
    assert d.result() == QDialog.DialogCode.Accepted
    assert d.credenciales() == ("Tec1", "Clave9")


def test_credenciales_con_usuario_previo_empieza_en_clave(app):
    d = tp.DialogoCredenciales(None, "T", "M", "tec1")
    assert d.activo == "clave" and d.campo_usuario.text() == "tec1"
    d.teclado.cancelado.emit()
    assert d.result() == QDialog.DialogCode.Rejected


def test_renovacion_usa_el_dialogo_tactil(monkeypatch):
    from autoclave.ui_pyside.services import renovacion_sesion as rs
    import inspect
    src = inspect.getsource(rs)
    assert "pedir_credenciales" in src and "_teclado_pantalla" in src


def test_conectar_teclado_lineedit_y_spinbox(app, monkeypatch):
    e = QLineEdit()
    tp.conectar_teclado(e, "Correo")
    monkeypatch.setattr(tp, "pedir_texto", lambda *a, **k: "a@b.co")
    e._abrir_teclado()
    assert e.text() == "a@b.co"

    s = QSpinBox(); s.setRange(0, 100)
    tp.conectar_teclado(s, "Valor")
    monkeypatch.setattr(tp, "pedir_numero", lambda *a, **k: 42.0)
    s.lineEdit()._abrir_teclado()
    assert s.value() == 42

    ds = QDoubleSpinBox(); ds.setRange(0, 10); ds.setDecimals(2)
    tp.conectar_teclado(ds, "Valor")
    monkeypatch.setattr(tp, "pedir_numero", lambda *a, **k: None)   # cancelado
    ds.setValue(3.5)
    ds.lineEdit()._abrir_teclado()
    assert ds.value() == 3.5


@pytest.mark.parametrize("modulo", ["login", "_email_dialog", "ciclos", "secado",
                                    "params_ciclo/params_ciclo",
                                    "entrdas_salidas/calibracion_sensor"])
def test_vistas_con_campos_de_texto_conectan_el_teclado(modulo):
    src = (RAIZ / "ui_pyside" / "views" / f"{modulo}.py").read_text(encoding="utf-8")
    assert "conectar_todos(self)" in src or "conectar_teclado(" in src


def test_textos_nuevos_en_es_y_en():
    from autoclave import i18n
    for idioma in ("es", "en"):
        for clave in ("sesion.vencida_titulo", "sesion.vencida_mensaje"):
            assert i18n.existe(clave, idioma), (clave, idioma)


def test_numerico_primera_tecla_reemplaza_el_inicial(app):
    n = tp.TecladoNumerico(minimo=0, maximo=60, decimales=0, factor=0.5)
    n.fijar_texto("1")
    n.pulsar("2")
    assert n.texto == "2"
    n.pulsar("5")
    assert n.texto == "25"


def test_usuario_previo_queda_fijo(app):
    d = tp.DialogoCredenciales(None, "T", "M", "tec1")
    assert not d.campo_usuario.isEnabled()
    d.teclado.confirmado.emit()          # sin clave: no acepta ni vuelve al usuario
    assert d.activo == "clave" and d.result() != QDialog.DialogCode.Accepted


def test_caducidad_por_renovacion_conserva_el_usuario_para_reingreso(monkeypatch):
    from autoclave.ui_pyside.services import renovacion_sesion as rs
    from autoclave.ui_pyside.services import auth_backend
    estado = {"token": "t", "user": {"usuario": "tec1"}}
    sm = rs.SessionManager
    monkeypatch.setattr(sm, "token", staticmethod(lambda: estado["token"]))
    monkeypatch.setattr(sm, "current_user", staticmethod(lambda: estado["user"]))
    monkeypatch.setattr(sm, "logout", staticmethod(lambda: estado.update(token=None, user=None)))
    r = rs.RenovadorSesion(consultar=lambda tok: 401, reloj=lambda: 100.0)
    r.actividad()
    r.tick()
    assert estado["token"] is None
    assert rs.usuario_para_reingreso() == "tec1"
    class Exc(Exception):
        response = type("R", (), {"status_code": 401})()
    def guardar():
        raise Exc()
    res = rs.guardar_con_reintento(guardar, lambda: ("otro", "x"),
                                   iniciar_sesion=lambda u, c: None)
    assert res.estado == rs.LOGIN_FALLIDO and res.login == rs.OTRO_USUARIO
    monkeypatch.setattr(rs, "_usuario_caducado", None)

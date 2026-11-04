"""FASE 6 (P1): restaurar respaldo como operación crítica, sin optimismo.

Nunca se muestra «restaurado» sin un 200; sin respuesta queda «sin confirmar»
(la relectura de la lista solo refresca) y NO hay reintento automático; una
sola restauración a la vez; el slot devuelve True = «enviado».
"""
import pytest

from tests.helpers.sesion_f6_controladores import (
    NO_RESPONDE, Resueltas, SesionManual, app, conservar, r)

from autoclave import i18n
from autoclave.ui_qml import operacion_critica as oc
from autoclave.ui_qml import sesion_backend as sb
from autoclave.ui_qml.controllers.respaldo_controller import RespaldoController

USB = {"unidades": [{"ruta": "E:/", "libre_bytes": 5e9,
                     "respaldos": [{"archivo": "a", "valido": True, "serie": "S"}]}]}
RUTA = "/backup/restore"


@pytest.fixture(scope="module", autouse=True)
def _app():
    return app()


def _listo():
    s = SesionManual()
    c = conservar(RespaldoController(sesion=s))
    c.cargar()
    s.responder(0, r(datos=USB))
    c.seleccionar("a")
    assert c.seleccion == "a"
    return c, s, Resueltas(c)


def test_restaurar_envia_con_plazo_60_bloquea_y_no_toca_el_estado_antes_del_200():
    c, s, res = _listo()
    assert c.restaurar() is True
    i = s.ultimo("POST", RUTA)
    assert s.envios[i]["cuerpo"] == {"unidad": "E:/", "archivo": "a", "confirmar": True}
    assert s.envios[i]["plazo_s"] == 60.0
    assert c.operacionEnCurso and c.estadoDe("restaurar") == "enviando"
    assert c._op.bloquea() and oc.registro.bloqueaNavegacion
    assert c.mensaje == "" and res.lista == []        # nada de éxito antes del 200


@pytest.mark.parametrize("reinicio,clave", [(True, "respaldo.restaurado_reinicio"),
                                            (False, "respaldo.restaurado")])
def test_200_confirma_y_relee_la_lista(reinicio, clave):
    c, s, res = _listo()
    c.restaurar()
    antes = s.cuenta("GET", "/backup/usb")
    s.responder_ultimo("POST", RUTA, r(datos={"reinicio_requerido": reinicio}))
    assert c.mensaje == clave
    assert res.lista == [("restaurar", "confirmada", "")]
    assert not c.operacionEnCurso and c.estadoDe("restaurar") == "inactiva"
    assert not c._op.bloquea()
    assert s.cuenta("GET", "/backup/usb") == antes + 1


@pytest.mark.parametrize("causa,clave", [
    ("otra_serie", "respaldo.motivo_otra_serie"),
    ("formato", "respaldo.motivo_formato"),
    ("parametros_invalidos", "respaldo.err_parametros"),
    ("calibracion_otro_enlace", "respaldo.err_calibracion_otro_enlace"),
    ("hash_invalido", "respaldo.err_invalido"),
    ("archivo_invalido", "respaldo.err_invalido"),
    ("confirmacion_requerida", "respaldo.err_confirmacion"),
    ("estado_no_permitido", "opciones.err_bloqueada"),
    ("rol_sin_permiso", "opciones.err_rol"),
])
def test_rechazo_muestra_su_motivo_y_no_dice_restaurado(causa, clave):
    c, s, res = _listo()
    c.restaurar()
    s.responder_ultimo("POST", RUTA, r(causa, {}, 409))
    assert c.mensaje == clave
    assert res.lista == [("restaurar", "rechazada", clave)]
    assert i18n.existe(clave, "es") and i18n.existe(clave, "en")
    assert not c.operacionEnCurso


def test_doble_toque_no_envia_un_segundo_post():
    c, s, _ = _listo()
    assert c.restaurar() is True
    assert c.restaurar() is False
    assert s.cuenta("POST", RUTA) == 1


def test_sin_seleccion_no_envia():
    s = SesionManual()
    c = conservar(RespaldoController(sesion=s))
    assert c.restaurar() is False
    assert s.cuenta("POST", RUTA) == 0


@pytest.mark.parametrize("relectura", ["con_lista", "falla", "sin_datos"])
def test_sin_respuesta_siempre_sin_confirmar_y_sin_reintento(relectura):
    c, s, res = _listo()
    c.restaurar()
    s.responder_ultimo("POST", RUTA, r(NO_RESPONDE, None, 0))
    assert c.estadoDe("restaurar") == "verificando" and c.operacionEnCurso
    n_get = s.cuenta("GET", "/backup/usb")
    assert n_get == 2                           # la carga inicial y la relectura
    if relectura == "con_lista":
        s.responder_ultimo("GET", "/backup/usb", r(datos=USB))      # aunque coincida
    elif relectura == "falla":
        s.responder_ultimo("GET", "/backup/usb", r(NO_RESPONDE, None, 0))
    else:
        s.responder_ultimo("GET", "/backup/usb", r(datos=None))
    assert res.lista == [("restaurar", "sin_confirmar", "respaldo.restaurar_sin_confirmar")]
    assert c.mensaje == "respaldo.restaurar_sin_confirmar"
    assert s.cuenta("POST", RUTA) == 1          # nunca se reintenta
    assert not c.operacionEnCurso


def test_respuesta_tardia_confirma_con_su_texto_y_no_reenvia():
    c, s, res = _listo()
    c.restaurar()
    i = s.ultimo("POST", RUTA)
    s.responder(i, r(NO_RESPONDE, None, 0))
    s.responder_ultimo("GET", "/backup/usb", r(datos=USB))
    assert res.lista[-1][1] == "sin_confirmar"
    s.tardio(i, r(datos={"reinicio_requerido": True}))
    assert res.lista[-1] == ("restaurar", "confirmada", "operacion.confirmada_tarde")
    assert c.mensaje == "respaldo.restaurado_reinicio"
    assert s.cuenta("POST", RUTA) == 1


def test_codigos_de_restaurar_reconocidos_solo_en_su_ruta():
    for codigo in ("archivo_invalido", "confirmacion_requerida"):
        assert sb.interpretar(428, {"codigo": codigo}, RUTA).causa == codigo
        assert sb.interpretar(428, {"codigo": codigo}, "/status").causa == sb.ERROR_GENERICO


def test_restaurar_y_exportar_se_excluyen():
    """MENOR-6: no se restaura con una exportación en vuelo, ni al revés."""
    c, s, _ = _listo()
    assert c.exportar() is True and c.guardando
    assert c.restaurar() is False and s.cuenta("POST", RUTA) == 0
    c2, s2, _ = _listo()
    assert c2.restaurar() is True
    assert c2.exportar() is False and s2.cuenta("POST", "/backup/export") == 0


def test_qml_restaurar_no_se_habilita_con_exportacion_en_vuelo():
    from pathlib import Path
    qml = (Path(__file__).resolve().parents[1]
           / "src/autoclave/ui_qml/qml/Pantallas/OpcionesRespaldo.qml").read_text(encoding="utf-8")
    i = qml.index('objectName: "botonRestaurar"')
    assert "!control.guardando" in qml[i:i + 600]

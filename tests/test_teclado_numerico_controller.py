# tests/test_teclado_numerico_controller.py
#
# Puente QObject entre la lógica pura de domain/teclado_numerico.py y QML:
# expone texto/valor/valido como Qt Properties con notify, y las teclas
# como Slots. Se prueba como objeto Python plano (sin motor QML) — los
# Property/Slot de PySide6 son accesibles como atributos/métodos normales.
# Reglas: §7 y TEC-D08/D12/D13 de planeacion_teclados_qml.md.

import sys
import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QCoreApplication
from PySide6.QtTest import QSignalSpy, QTest

from autoclave.ui_qml.controllers.teclado_numerico_controller import (
    TecladoNumericoController,
)


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QCoreApplication(sys.argv)


class RelojFalso:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


@pytest.fixture
def reloj():
    return RelojFalso()


@pytest.fixture
def controller(reloj):
    return TecladoNumericoController(reloj=reloj)


def _escribir(controller, teclas):
    for t in teclas:
        if t == ".":
            controller.presionarPunto()
        elif t == "-":
            controller.presionarSigno()
        else:
            controller.presionarDigito(t)


def test_estado_inicial_vacio_invalido(controller):
    assert controller.texto == ""
    assert controller.valor is None
    assert controller.valido is False
    assert controller.fueraDeRango is False


def test_presionar_digito_actualiza_texto(controller):
    _escribir(controller, "134")
    assert controller.texto == "134"


def test_decimales_por_defecto_es_cero(controller):
    assert controller.decimales == 0


def test_presionar_punto(controller):
    controller.decimales = 1
    _escribir(controller, "1.5")
    assert controller.texto == "1.5"
    assert controller.valor == 1.5


def test_presionar_punto_bloqueado_sin_decimales(controller):
    controller.decimales = 0
    _escribir(controller, "1.")
    assert controller.texto == "1"


def test_segundo_decimal_bloqueado(controller):
    controller.decimales = 1
    _escribir(controller, "134.55")
    assert controller.texto == "134.5"


def test_no_existe_tecla_de_coma(controller):
    assert not hasattr(controller, "presionarComa")


# ── signo (§7: alterna el valor completo, bloqueado si minimo >= 0) ─────

def test_signo_alterna_el_valor_completo(controller):
    controller.minimo = -100.0
    _escribir(controller, "12")
    controller.presionarSigno()
    assert controller.texto == "-12"
    controller.presionarSigno()
    assert controller.texto == "12"


def test_signo_en_vacio_deja_menos_pendiente(controller):
    controller.minimo = -100.0
    controller.presionarSigno()
    assert controller.texto == "-"


def test_signo_bloqueado_si_minimo_no_es_negativo(controller):
    controller.minimo = 0.0
    assert controller.permiteNegativo is False
    _escribir(controller, "5")
    controller.presionarSigno()
    assert controller.texto == "5"


def test_permite_negativo_se_deriva_de_minimo(controller):
    controller.minimo = -1.0
    assert controller.permiteNegativo is True
    controller.minimo = 10.0
    assert controller.permiteNegativo is False


# ── borrar (TEC-D12) ─────────────────────────────────────────────────────

def test_borrar(controller):
    _escribir(controller, "12")
    controller.borrar()
    assert controller.texto == "1"


def test_limpiar(controller):
    _escribir(controller, "12")
    controller.limpiar()
    assert controller.texto == ""


def test_borrar_toque_corto_quita_un_caracter(controller, reloj):
    _escribir(controller, "123")
    controller.presionarBorrar()
    reloj.t += 0.2
    controller.soltarBorrar()
    assert controller.texto == "12"


def test_borrar_mantenido_600_ms_vacia_el_campo_y_soltar_no_borra_mas(controller, reloj):
    _escribir(controller, "123")
    controller.presionarBorrar()
    reloj.t += 0.6
    controller._borrado.vencer()   # lo que hace el temporizador al cumplirse
    assert controller.texto == ""
    reloj.t += 1.0
    controller.soltarBorrar()
    assert controller.texto == ""


def test_borrar_mantenido_con_temporizador_real():
    # Sin reloj falso: el QTimer de 600 ms del controlador dispara solo.
    c = TecladoNumericoController()
    _escribir(c, "123")
    c.presionarBorrar()
    QTest.qWait(750)
    assert c.texto == ""
    c.soltarBorrar()
    assert c.texto == ""


def test_pulsacion_de_borrar_cancelada_no_borra(controller, reloj):
    # El dedo sale de la tecla (onCanceled en QML): ni uno ni todo.
    _escribir(controller, "123")
    controller.presionarBorrar()
    reloj.t += 0.2
    controller.cancelarPulsacionBorrar()
    controller.soltarBorrar()
    assert controller.texto == "123"


# ── validez en vivo ──────────────────────────────────────────────────────

def test_valido_refleja_rango_configurado(controller):
    controller.minimo = 0.0
    controller.maximo = 100.0
    _escribir(controller, "50")
    assert controller.valido is True
    assert controller.valor == 50.0

    controller.limpiar()
    _escribir(controller, "150")
    assert controller.valido is False  # 150 > maximo=100
    assert controller.valor == 150.0


def test_texto_changed_se_emite_al_presionar_tecla(controller):
    spy = QSignalSpy(controller.textoChanged)
    controller.presionarDigito("1")
    assert spy.count() == 1


def test_valido_changed_se_emite_solo_al_cruzar_el_umbral(controller):
    controller.minimo = 0.0
    controller.maximo = 100.0
    spy = QSignalSpy(controller.validoChanged)

    controller.presionarDigito("5")   # "5" -> válido (era inválido) -> emite
    assert spy.count() == 1

    controller.presionarDigito("0")   # "50" -> sigue válido -> no vuelve a emitir
    assert spy.count() == 1

    controller.presionarDigito("0")   # "500" -> inválido (> 100) -> emite
    assert spy.count() == 2


# ── abrir (TEC-D08/D13) ──────────────────────────────────────────────────

def test_abrir_configura_campo_y_muestra_valor_inicial(controller):
    controller.abrir("Temperatura de esterilización", "°C", 121.0, 105.0, 135.0, 1)
    assert controller.titulo == "Temperatura de esterilización"
    assert controller.unidad == "°C"
    assert controller.texto == "121.0"
    assert controller.valor == 121.0
    assert controller.valido is True
    assert controller.minimoTexto == "105.0"
    assert controller.maximoTexto == "135.0"
    assert controller.permiteNegativo is False


def test_abrir_sin_valor_inicial_queda_vacio(controller):
    controller.abrir("P", "kPa", None, -100.0, 400.0, 1)
    assert controller.texto == ""
    assert controller.valido is False


def test_abrir_reinicia_estado_anterior(controller):
    controller.abrir("A", "°C", None, 0.0, 10.0, 0)
    _escribir(controller, "99")
    controller.confirmar()
    assert controller.fueraDeRango is True
    controller.abrir("B", "kPa", 5.0, 0.0, 10.0, 0)
    assert controller.texto == "5"
    assert controller.fueraDeRango is False


# ── confirmar (§7: inválido no entrega y muestra el rango) ──────────────

def test_confirmar_valido_emite_el_valor(controller):
    controller.abrir("T", "°C", None, -100.0, 400.0, 1)
    _escribir(controller, "134.5")
    spy = QSignalSpy(controller.confirmado)
    controller.confirmar()
    assert spy.count() == 1
    assert spy.at(0)[0] == 134.5
    assert controller.fueraDeRango is False


@pytest.mark.parametrize("teclas", ["", "-", ".", "-.", "500"])
def test_confirmar_invalido_no_emite_y_muestra_rango(controller, teclas):
    controller.abrir("T", "°C", None, -100.0, 400.0, 1)
    _escribir(controller, teclas)
    spy = QSignalSpy(controller.confirmado)
    controller.confirmar()
    assert spy.count() == 0
    assert controller.fueraDeRango is True


def test_nueva_tecla_oculta_el_aviso_de_rango(controller):
    controller.abrir("T", "°C", None, 0.0, 10.0, 0)
    _escribir(controller, "50")
    controller.confirmar()
    assert controller.fueraDeRango is True
    controller.borrar()
    assert controller.fueraDeRango is False


def test_limites_inclusivos_se_entregan(controller):
    controller.abrir("T", "°C", None, -100.0, 400.0, 0)
    spy = QSignalSpy(controller.confirmado)
    _escribir(controller, "-100")
    controller.confirmar()
    assert spy.count() == 1
    assert spy.at(0)[0] == -100.0


# ── cancelar (TEC-D07) ───────────────────────────────────────────────────

def test_cancelar_emite_cancelado_sin_confirmado_y_descarta(controller):
    controller.abrir("T", "°C", 50.0, 0.0, 100.0, 0)
    _escribir(controller, "1")
    spy_ok = QSignalSpy(controller.confirmado)
    spy_cancel = QSignalSpy(controller.cancelado)
    controller.cancelar()
    assert spy_cancel.count() == 1
    assert spy_ok.count() == 0
    assert controller.texto == ""


def test_abrir_apaga_el_aviso_de_rango(controller):
    controller.abrir("T", "°C", None, 0.0, 10.0, 0)
    _escribir(controller, "50")
    controller.confirmar()
    assert controller.fueraDeRango is True
    spy = QSignalSpy(controller.fueraDeRangoChanged)
    controller.abrir("T", "°C", None, 0.0, 10.0, 0)
    assert controller.fueraDeRango is False
    assert spy.count() == 1


def test_abrir_con_el_mismo_texto_tambien_apaga_el_aviso(controller):
    controller.abrir("T", "°C", 50, 0.0, 10.0, 0)
    controller.confirmar()
    assert controller.fueraDeRango is True
    controller.abrir("T", "°C", 50, 0.0, 10.0, 0)   # _set_texto sin cambio de texto
    assert controller.fueraDeRango is False


def test_distribucion_expuesta_a_qml(controller):
    assert controller.filasTeclas == ["789", "456", "123", "-0."]
    assert controller.teclaSigno == "-"
    assert controller.teclaPunto == "."


def test_presionar_tecla_despacha_signo_punto_y_digitos(controller):
    controller.abrir("T", "°C", None, -100.0, 400.0, 1)
    for t in "12.5":
        controller.presionarTecla(t)
    controller.presionarTecla("-")
    assert controller.texto == "-12.5"
    controller.presionarTecla(",")          # no es tecla: se ignora
    assert controller.texto == "-12.5"

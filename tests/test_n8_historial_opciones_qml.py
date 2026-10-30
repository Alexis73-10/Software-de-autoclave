# tests/test_n8_historial_opciones_qml.py
#
# N8 (tanda 8, D8-4.1): OPCIONES lleva su propio historial de navegación.
# - Cambiar de sección desde el cajón agrega un nivel a la pila.
# - Atrás regresa exactamente al nivel anterior, con el mismo programa, la
#   misma fase y el desplazamiento de la lista conservados.
# - Con la ventana de ajuste abierta, Atrás la cierra primero (y pide
#   confirmación si hay un valor editado sin guardar).
# - Con la pila vacía, Atrás sale de OPCIONES (atrasPulsado: Main.qml vuelve a
#   la pantalla desde la que se entró). Home sigue saliendo de todo.
# Banco offscreen con backend doble (tests/banco/opciones_qml_banco.py). Con
# TANDA8_CAPTURAS=1 guarda docs/informes/tanda8/capturas/n8/N8_*.png.

import os

import pytest

pytest.importorskip("PySide6")

from tests.banco.opciones_qml_banco import RAIZ, correr  # noqa: E402

CAPTURAS_N8 = RAIZ / "docs" / "informes" / "tanda8" / "capturas" / "n8"


def _quieren_capturas() -> bool:
    return os.environ.get("TANDA8_CAPTURAS") == "1"


_SECCIONES = [{"clave": c, "no_se_ejecuta": False}
              for c in ("prevacio", "calentamiento", "esterilizacion", "descompresion", "secado")]
_PARAMS = [{"clave": f"parametro_{i:02d}", "valor": float(i), "defecto": float(i), "min": 0.0,
            "max": 500.0, "tipo": "float", "unidad": "s", "modificado": False, "opciones": []}
           for i in range(1, 31)]

RUTAS = {
    "GET /programas": [200, {"programas": [
        {"numero": 1, "nombre": "Bowie & Dick", "secciones": _SECCIONES, "editable": True},
        {"numero": 2, "nombre": "Instrumental", "secciones": _SECCIONES, "editable": True},
        {"numero": 3, "nombre": "Textil", "secciones": _SECCIONES, "editable": True}]}],
    "GET /programas/2/seccion/calentamiento": [200, {"parametros": _PARAMS, "editable": True}],
    "GET /maintenance": [200, {"estado": "ok", "configuracion": {"intervalo_dias": 365,
                                                                   "intervalo_ciclos": 1000}}],
}

_COMUNES = r'''
from PySide6.QtCore import QMetaObject, Q_ARG
senales = []
raiz.atrasPulsado.connect(lambda: senales.append("atras"))
raiz.inicioPulsado.connect(lambda: senales.append("inicio"))
def ir(clave):
    QMetaObject.invokeMethod(raiz, "elegirSeccion", Q_ARG("QVariant", clave)); esperar(250)
def atras():
    QMetaObject.invokeMethod(raiz, "atras"); esperar(300)
def pulsar(nombre, desde=None):
    QMetaObject.invokeMethod(buscar(nombre, desde), "pulsada"); esperar(250)
def nivel():
    return [raiz.property("seccionActiva"), int(raiz.property("profundidadHistorial"))]
'''

# Recorrido principal: Parámetros del ciclo › 02 › Calentamiento (desplazada)
# -> Mantenimiento -> Información del sistema, y de vuelta con Atrás.
PASOS_RECORRIDO = _COMUNES + r'''
salida["inicio"] = nivel()
pc = buscar("parametrosCiclo")
ctrl = pc.findChild(QObject, "parametrosCicloController")
ctrl.elegirPrograma(2); esperar()
pulsar("seccion_calentamiento", pc)
lista = buscar("listaParametros", pc)
lista.setProperty("contentY", 600.0); esperar(250)
salida["y_antes"] = lista.property("contentY")
capturar("N8_01_ciclo_calentamiento.png")
ir("mantenimiento")
salida["a_mantenimiento"] = nivel()
capturar("N8_02_mantenimiento.png")
ir("info_sistema")
salida["a_info"] = nivel()
ir("info_sistema")                       # la misma sección no agrega nivel
salida["misma_seccion"] = nivel()
atras()
salida["atras_1"] = nivel()
capturar("N8_03_atras_mantenimiento.png")
atras()
salida["atras_2"] = nivel()
pc = buscar("parametrosCiclo")
ctrl = pc.findChild(QObject, "parametrosCicloController")
salida["restaurado"] = [pc.property("vista"), ctrl.property("numero"), ctrl.property("seccion")]
esperar(300)
salida["y_despues"] = buscar("listaParametros", pc).property("contentY")
capturar("N8_04_atras_ciclo_calentamiento.png")
atras()
salida["atras_3"] = [nivel(), pc.property("vista")]
salida["senales_antes_de_salir"] = list(senales)
atras()
salida["atras_4"] = nivel()
salida["senales"] = list(senales)
'''

# Ventana de ajuste abierta: Atrás la cierra primero; con valor editado pregunta
PASOS_AJUSTE = _COMUNES + r'''
pc = buscar("parametrosCiclo")
ctrl = pc.findChild(QObject, "parametrosCicloController")
ctrl.elegirPrograma(2); esperar()
pulsar("seccion_calentamiento", pc)
ir("mantenimiento")
atras()                               # vuelve a Calentamiento
pc = buscar("parametrosCiclo")
ajuste = buscar("ventanaAjuste", pc)
pulsar("param_parametro_03", pc)
salida["ajuste_abierta"] = ajuste.isVisible()
capturar("N8_05_ventana_ajuste.png")
atras()
salida["ajuste_cierra"] = [ajuste.isVisible(), pc.property("vista"), nivel(), list(senales)]
pulsar("param_parametro_03", pc)
ajuste.setProperty("nuevo", 42.0); esperar()
atras()
dialogo = buscar("dialogoGuardarAjuste", pc)
salida["pregunta"] = [dialogo.isVisible(), ajuste.isVisible(), pc.property("vista")]
capturar("N8_06_ajuste_sin_guardar.png")
QMetaObject.invokeMethod(dialogo, "descartado"); dialogo.setProperty("visible", False); esperar()
salida["descartado"] = [ajuste.isVisible(), pc.property("vista"), list(senales)]
# con un valor editado, cambiar de sección pide confirmación y, al confirmar,
# la sección anterior queda en la pila
pulsar("param_parametro_03", pc)
ajuste.setProperty("nuevo", 43.0); esperar()
ir("info_sistema")
cambiar = buscar("dialogoCambiarSeccion")
salida["confirma_cambio"] = [cambiar.isVisible(), nivel()]
QMetaObject.invokeMethod(cambiar, "confirmado"); cambiar.setProperty("visible", False); esperar()
salida["tras_confirmar"] = nivel()
atras()
pc = buscar("parametrosCiclo")
salida["vuelve_sin_ajuste"] = [nivel(), pc.property("vista"), buscar("ventanaAjuste", pc).isVisible()]
'''

# Varias secciones con subnivel: equipo (submenú), usuarios (pestaña),
# entradas/salidas (segmento), y Home sale de todo
PASOS_SECCIONES = _COMUNES + r'''
ir("parametros_sistema")
ceq = raiz.findChild(QObject, "parametrosEquipoController")
ceq.abrirGrupo("chaqueta"); esperar()
capturar("N8_07_equipo_chaqueta.png")
ir("usuarios")
us = raiz.findChild(QObject, "cargadorUsuarios").property("item")
us.setProperty("pestana", "operadores"); esperar()
ir("entradas_salidas")
es = raiz.findChild(QObject, "cargadorEntradasSalidas").property("item")
es.setProperty("segmento", "presion"); esperar()
ir("fecha_hora")
salida["profundidad"] = nivel()
atras()
salida["a_es"] = [nivel(), raiz.findChild(QObject, "cargadorEntradasSalidas").property("item").property("segmento")]
atras()
salida["a_usuarios"] = [nivel(), raiz.findChild(QObject, "cargadorUsuarios").property("item").property("pestana")]
capturar("N8_08_atras_usuarios_operadores.png")
atras()
salida["a_equipo"] = [nivel(), raiz.findChild(QObject, "parametrosEquipoController").property("grupo")]
capturar("N8_09_atras_equipo_chaqueta.png")
atras()                                # equipo: submenú -> entrada
salida["equipo_arriba"] = [nivel(), raiz.findChild(QObject, "parametrosEquipoController").property("grupo")]
atras()                                # -> Parámetros del ciclo (sección inicial)
salida["a_inicial"] = nivel()
ir("mantenimiento"); ir("info_sistema")
QMetaObject.invokeMethod(raiz, "inicio"); esperar()
salida["home"] = list(senales)
'''


def _correr(pasos, rutas=RUTAS):
    return correr("tecnico", pasos, rutas=rutas, capturas=_quieren_capturas(),
                  dir_capturas=CAPTURAS_N8)


def test_atras_regresa_al_nivel_anterior_con_programa_fase_y_desplazamiento():
    r = _correr(PASOS_RECORRIDO)
    assert r["avisos"] == []
    assert r["inicio"] == ["parametros_ciclo", 0]
    assert r["a_mantenimiento"] == ["mantenimiento", 1]
    assert r["a_info"] == ["info_sistema", 2]
    assert r["misma_seccion"] == ["info_sistema", 2]
    assert r["atras_1"] == ["mantenimiento", 1]
    assert r["atras_2"] == ["parametros_ciclo", 0]
    assert r["restaurado"] == ["seccion", 2, "calentamiento"]
    assert r["y_antes"] == pytest.approx(600.0)
    assert r["y_despues"] == pytest.approx(r["y_antes"])
    # dentro de la sección, Atrás sube de la fase a la lista de programas
    assert r["atras_3"] == [["parametros_ciclo", 0], "programa"]
    assert r["senales_antes_de_salir"] == []
    # pila vacía: sale de OPCIONES a la pantalla de origen
    assert r["senales"] == ["atras"]


def test_atras_cierra_primero_la_ventana_de_ajuste():
    r = _correr(PASOS_AJUSTE)
    assert r["avisos"] == []
    assert r["ajuste_abierta"] is True
    # sin cambios: Atrás solo cierra la ventana (la fase y la pila no cambian)
    assert r["ajuste_cierra"] == [False, "seccion", ["parametros_ciclo", 0], []]
    # con un valor editado: pregunta antes de cerrar
    assert r["pregunta"] == [True, True, "seccion"]
    assert r["descartado"] == [False, "seccion", []]
    assert r["confirma_cambio"] == [True, ["parametros_ciclo", 0]]
    assert r["tras_confirmar"] == ["info_sistema", 1]
    assert r["vuelve_sin_ajuste"] == [["parametros_ciclo", 0], "seccion", False]


def test_historial_en_varias_secciones_y_home():
    r = _correr(PASOS_SECCIONES)
    assert r["avisos"] == []
    assert r["profundidad"] == ["fecha_hora", 4]
    assert r["a_es"] == [["entradas_salidas", 3], "presion"]
    assert r["a_usuarios"] == [["usuarios", 2], "operadores"]
    assert r["a_equipo"] == [["parametros_sistema", 1], "chaqueta"]
    assert r["equipo_arriba"] == [["parametros_sistema", 1], ""]
    assert r["a_inicial"] == ["parametros_ciclo", 0]
    assert r["home"] == ["inicio"]      # Home sale de todo, sin recorrer la pila

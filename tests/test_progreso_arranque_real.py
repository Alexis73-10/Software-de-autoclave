"""Intro de arranque con el progreso REAL del backend (GET /arranque), en lugar
del simulador de tiempos fijos (observación de Cristian, 19-oct: "la barra de
carga pareciera simulada; solo hay un paso, el de la base de datos").

Contrato de /arranque: backend/arranque/registro.py (RegistroArranque.instantanea)."""

import pytest

pytest.importorskip("PySide6")

from autoclave.backend.arranque.registro import RegistroArranque  # noqa: E402
from autoclave.ui_qml.bridge.progreso_arranque import (  # noqa: E402
    ProgresoArranqueBackend, resumir_arranque,
)


def _registro_hasta(clave_en_curso=None, completas=()):
    r = RegistroArranque()
    for c in completas:
        r.iniciar(c)
        r.completar(c)
    if clave_en_curso:
        r.iniciar(clave_en_curso)
    return r


def test_sin_respuesta_del_backend_es_iniciando_servicios():
    s = resumir_arranque(None)
    assert s == {"fraccion": 0.0, "proceso": "iniciando_servicios",
                 "terminado": False, "fallo": False}


def test_etapas_del_backend_se_ven_una_a_una():
    vistos = []
    completas = []
    for clave in ("verificando_instalacion", "liberando_procesos", "iniciando_servicios",
                  "cargando_configuracion", "verificando_calibracion", "abriendo_base_datos",
                  "conectando_modulos_es", "verificando_sensores"):
        s = resumir_arranque(_registro_hasta(clave, completas).instantanea())
        vistos.append(s["proceso"])
        assert not s["terminado"]
        completas.append(clave)
    # incluye la tarjeta (módulos de E/S) y los servicios, no solo la base de datos
    assert "conectando_modulos_es" in vistos and "iniciando_servicios" in vistos
    assert len(set(vistos)) == 8


def test_fraccion_crece_con_los_pesos():
    r = _registro_hasta("cargando_configuracion",
                        ("verificando_instalacion", "liberando_procesos", "iniciando_servicios"))
    s = resumir_arranque(r.instantanea())
    # pesos 1 + 1 + 2 de un total de 11 (sin la etapa de la interfaz)
    assert s["fraccion"] == pytest.approx(4 / 11)


def test_terminado():
    claves = ("verificando_instalacion", "liberando_procesos", "iniciando_servicios",
              "cargando_configuracion", "verificando_calibracion", "abriendo_base_datos",
              "conectando_modulos_es", "verificando_sensores")
    s = resumir_arranque(_registro_hasta(None, claves).instantanea())
    assert s["terminado"] and s["fraccion"] == pytest.approx(1.0)


def test_sin_tarjeta_pasados_15_s_la_intro_termina_igual():
    # ARR_SIN_ES: el backend sigue reintentando las E/S; la UI no debe quedarse
    # en la intro (la pantalla principal muestra "tarjeta desconectada", U4)
    r = _registro_hasta("conectando_modulos_es",
                        ("verificando_instalacion", "liberando_procesos", "iniciando_servicios",
                         "cargando_configuracion", "verificando_calibracion",
                         "abriendo_base_datos"))
    assert not resumir_arranque(r.instantanea())["terminado"]
    r.anotar("conectando_modulos_es", "ARR_SIN_ES")
    s = resumir_arranque(r.instantanea())
    assert s["terminado"] and not s["fallo"]


def test_fallo_bloqueante():
    r = RegistroArranque()
    r.iniciar("verificando_instalacion")
    r.fallar("verificando_instalacion", "ARR_PERFIL")
    s = resumir_arranque(r.instantanea())
    assert s["fallo"] and not s["terminado"] and s["proceso"] == "verificando_instalacion"


@pytest.mark.parametrize("basura", [{}, {"etapas": "x"}, [], "texto", {"etapas": [{"x": 1}]}])
def test_respuesta_mal_formada_cuenta_como_sin_respuesta(basura):
    assert resumir_arranque(basura) == resumir_arranque(None)


def test_objeto_qml_sondea_y_deja_de_sondear_al_terminar():
    respuestas = [None, _registro_hasta("cargando_configuracion",
                                        ("verificando_instalacion", "liberando_procesos",
                                         "iniciando_servicios")).instantanea()]
    claves = ("verificando_instalacion", "liberando_procesos", "iniciando_servicios",
              "cargando_configuracion", "verificando_calibracion", "abriendo_base_datos",
              "conectando_modulos_es", "verificando_sensores")
    respuestas.append(_registro_hasta(None, claves).instantanea())
    pedidos = []

    def leer():
        pedidos.append(1)
        return respuestas[min(len(pedidos), len(respuestas)) - 1]

    p = ProgresoArranqueBackend(leer=leer, en_hilo=False)
    p.sondear()
    assert p.property("proceso") == "iniciando_servicios" and p.property("fraccion") == 0
    p.sondear()
    assert p.property("proceso") == "cargando_configuracion"
    p.sondear()
    assert p.property("terminado") is True
    p.sondear()
    assert len(pedidos) == 3            # terminado: ya no consulta


def test_leer_que_lanza_cuenta_como_sin_respuesta():
    def leer():
        raise OSError("sin backend")
    p = ProgresoArranqueBackend(leer=leer, en_hilo=False)
    p.sondear()
    assert p.property("proceso") == "iniciando_servicios" and not p.property("falloBloqueante")


# ── repetición visible de las etapas ya cumplidas (19-oct) ──────────────────
# Las etapas de archivos tardan milisegundos: cuando la barra se hace visible
# (3,5 s de intro) el backend ya va por las E/S. Desde reiniciarVista() se
# muestran una a una las etapas REALES ya cumplidas, a un paso por avanzar(),
# nunca por delante del backend.

_CLAVES = ("verificando_instalacion", "liberando_procesos", "iniciando_servicios",
           "cargando_configuracion", "verificando_calibracion", "abriendo_base_datos",
           "conectando_modulos_es", "verificando_sensores")


def _p_con(instantanea):
    p = ProgresoArranqueBackend(leer=lambda: instantanea, en_hilo=False)
    p.sondear()
    return p


def test_repeticion_muestra_cada_etapa_cumplida_y_espera_en_la_actual():
    r = _registro_hasta("conectando_modulos_es", _CLAVES[:6])
    p = _p_con(r.instantanea())
    p.reiniciarVista()
    vistos = [p.property("proceso")]
    fracciones = [p.property("fraccion")]
    for _ in range(10):
        p.avanzarVista()
        vistos.append(p.property("proceso"))
        fracciones.append(p.property("fraccion"))
    assert vistos[:7] == list(_CLAVES[:7])
    assert set(vistos[7:]) == {"conectando_modulos_es"}       # no se adelanta
    assert fracciones == sorted(fracciones) and fracciones[0] == 0
    assert fracciones[-1] == pytest.approx(7 / 11)


def test_terminado_solo_cuando_la_vista_alcanza_al_backend():
    r = _registro_hasta(None, _CLAVES)
    p = _p_con(r.instantanea())
    p.reiniciarVista()
    assert p.property("terminado") is False
    for _ in range(len(_CLAVES)):
        p.avanzarVista()
    assert p.property("terminado") is True and p.property("fraccion") == pytest.approx(1.0)


def test_fallo_se_muestra_sin_esperar_la_repeticion():
    r = _registro_hasta("verificando_calibracion", _CLAVES[:4])
    r.fallar("verificando_calibracion", "ARR_CALIBRACION")
    p = _p_con(r.instantanea())
    p.reiniciarVista()
    assert p.property("falloBloqueante") is True
    assert p.property("proceso") == "verificando_calibracion"


def test_sin_reiniciar_la_vista_publica_el_estado_real():
    r = _registro_hasta("conectando_modulos_es", _CLAVES[:6])
    p = _p_con(r.instantanea())
    assert p.property("proceso") == "conectando_modulos_es"

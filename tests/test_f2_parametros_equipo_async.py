# tests/test_f2_parametros_equipo_async.py
#
# AJUSTES 2026-11-02, paso 2 fase 2: OPCIONES › Parámetros del equipo sin HTTP
# síncrono en el hilo de la GUI.
#   - Idioma, unidades e impresora: optimistas con reversión; el efecto global
#     (i18n.fijar_idioma, unidades_qml.refrescar) solo tras el 200.
#   - Parámetros (/global_params): asíncronos SIN optimismo; el valor vigente
#     se muestra hasta el 200 y la clave queda pendiente.
#   - Carga: GET asíncronos con `cargando`.

import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from autoclave.ui_qml.sesion_backend import BACKEND_NO_RESPONDE, Resultado

_RAIZ = Path(__file__).resolve().parents[1]
_QML = _RAIZ / "src/autoclave/ui_qml/qml/Pantallas/OpcionesParametrosEquipo.qml"


class _SesionDiferida:
    """Doble con `enviar_async`: nada se entrega hasta `responder`. El
    backend simulado aplica los cambios aceptados."""

    def __init__(self):
        from autoclave.core.managers.config_manager import ConfigManager
        c = ConfigManager(); c.load_config()
        self.lista = c.describir()
        self.idioma, self.unidades, self.impresora = "es", ("C", "kPa"), True
        self.en_vuelo = []            # [metodo, ruta, cuerpo, al_terminar, al_tardio]
        self.enviados = []
        self.cancelados = []

    def enviar_async(self, metodo, ruta, cuerpo=None, al_terminar=None, *, dueno=None,
                     al_tardio=None):
        self.enviados.append((metodo, ruta, cuerpo))
        self.en_vuelo.append([metodo, ruta, cuerpo, al_terminar, al_tardio])
        return True

    def cancelar_envios(self, dueno):
        self.cancelados.append(dueno)
        return 0

    def _lectura(self, ruta):
        datos = {"/system_params": {"parametros": [dict(p) for p in self.lista]},   # copia
                 "/printer/config": {"habilitada": self.impresora},
                 "/units": {"temperatura": self.unidades[0], "presion": self.unidades[1]},
                 "/language": {"idioma": self.idioma}}[ruta]
        return Resultado("ok", datos, 200)

    def _aplicar(self, metodo, ruta, cuerpo):
        if ruta == "/language":
            self.idioma = cuerpo["idioma"]
        elif ruta == "/units":
            self.unidades = (cuerpo["temperatura"], cuerpo["presion"])
        elif ruta == "/printer/config":
            self.impresora = cuerpo["habilitada"]
        elif ruta.startswith("/global_params/"):
            clave = ruta.split("/")[2]
            for p in self.lista:
                if p["clave"] == clave:
                    p["valor"] = p["defecto"] if ruta.endswith("/reset") else cuerpo["valor"]

    def responder(self, metodo, ruta, resultado=None, aplicar=None):
        """Entrega la primera petición pendiente con ese método y ruta. Sin
        `resultado`, un GET lee el backend y un cambio se acepta y aplica."""
        i = next(i for i, e in enumerate(self.en_vuelo) if e[0] == metodo and e[1] == ruta)
        m, r, cuerpo, al_terminar, _ = self.en_vuelo.pop(i)
        if resultado is None:
            if m == "GET":
                resultado = self._lectura(r)
            else:
                self._aplicar(m, r, cuerpo)
                resultado = Resultado("ok", {"ok": True}, 200)
        elif aplicar:
            self._aplicar(m, r, cuerpo)
        al_terminar(resultado)

    def responder_gets(self):
        while any(e[0] == "GET" for e in self.en_vuelo):
            e = next(e for e in self.en_vuelo if e[0] == "GET")
            self.responder("GET", e[1])

    def pendiente(self, metodo, ruta):
        return any(e[0] == metodo and e[1] == ruta for e in self.en_vuelo)


@pytest.fixture
def globales(monkeypatch):
    """Registra el efecto global (idioma de la UI y refresco de unidades)."""
    from autoclave import i18n
    from autoclave.ui_qml.bridge import unidades_qml
    llamadas = []
    monkeypatch.setattr(i18n, "fijar_idioma", lambda v: llamadas.append(("idioma", v)))

    class _Unidades:
        def refrescar(self):
            llamadas.append(("unidades", None))
    monkeypatch.setattr(unidades_qml, "instancia", _Unidades(), raising=False)
    return llamadas


def _ctrl():
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    from autoclave.ui_qml.controllers.parametros_equipo_controller import (
        ParametrosEquipoController)
    s = _SesionDiferida()
    c = ParametrosEquipoController(sesion=s, perfil=lambda: None)
    c.cargar()
    s.responder_gets()
    resueltos = []
    c.cambioResuelto.connect(lambda *a: resueltos.append(a))
    return c, s, resueltos


def _valor(c, clave):
    return c.parametro(clave)["valor"]


# ── carga asíncrona ────────────────────────────────────────────────────────

def test_cargar_es_asincrono_con_cargando():
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    from autoclave.ui_qml.controllers.parametros_equipo_controller import (
        ParametrosEquipoController)
    s = _SesionDiferida()
    c = ParametrosEquipoController(sesion=s, perfil=lambda: None)
    c.cargar()
    assert c.cargando is True and c.parametros == [] and c.idioma == ""
    assert [e[1] for e in s.en_vuelo] == ["/system_params", "/printer/config", "/units", "/language"]
    s.responder("GET", "/units")
    assert c.unidadTemperatura == "C" and c.cargando is True
    s.responder_gets()
    assert c.cargando is False and c.idioma == "es" and c.impresoraHabilitada is True
    assert _valor(c, "timeout_puerta") == 60


def test_carga_anterior_se_descarta():
    c, s, _ = _ctrl()
    c.cargar()
    viejas = list(s.en_vuelo)
    s.en_vuelo.clear()
    c.cargar()
    s.idioma = "en"
    for _m, ruta, _c, al_terminar, _t in viejas:       # respuesta de la carga anterior
        al_terminar(Resultado("ok", {"idioma": "zz"} if ruta == "/language" else {}, 200))
    assert c.idioma == "es" and c.cargando is True
    s.responder_gets()
    assert c.idioma == "en" and c.cargando is False


# ── idioma / unidades / impresora: optimistas ──────────────────────────────

def test_idioma_optimista_y_global_solo_tras_200(globales):
    c, s, resueltos = _ctrl()
    assert c.fijarIdioma("en") is True                  # aceptado, en vuelo
    assert c.idioma == "en" and c.pendientes == {"idioma": "enviando"}
    assert globales == []                               # la UI entera aún no cambia
    s.responder("PUT", "/language")
    assert globales == [("idioma", "en")]
    assert c.idioma == "en" and c.pendientes == {} and c.mensaje == ""
    assert resueltos == [("idioma", True, "")]


def test_unidades_optimistas_y_refresco_global_solo_tras_200(globales):
    c, s, _ = _ctrl()
    assert c.fijarUnidades("F", "kPa")
    assert c.unidadTemperatura == "F" and globales == []
    # una lectura que llega mientras tanto no pisa lo pendiente
    c.cargar(); s.responder_gets()
    assert c.unidadTemperatura == "F"
    s.responder("PUT", "/units")
    assert globales == [("unidades", None)] and c.unidadTemperatura == "F"


@pytest.mark.parametrize("clave,slot,args,ruta,leer,antes,causa,mensaje", [
    ("idioma", "fijarIdioma", ("en",), "/language", "idioma", "es",
     "rol_sin_permiso", "opciones.err_rol"),
    ("unidades", "fijarUnidades", ("F", "psi"), "/units", "unidadTemperatura", "C",
     "estado_no_permitido", "opciones.equipo_err_unidades_ciclo"),
    ("impresora", "fijarImpresora", (False,), "/printer/config", "impresoraHabilitada", True,
     "ARCHIVO_NO_ESCRIBIBLE", "opciones.equipo_err_guardar"),
])
def test_rechazo_revierte_sin_efecto_global(globales, clave, slot, args, ruta, leer, antes,
                                            causa, mensaje):
    c, s, resueltos = _ctrl()
    assert getattr(c, slot)(*args) is True
    assert getattr(c, leer) != antes                    # optimista
    s.responder("PUT", ruta, Resultado(causa))
    assert getattr(c, leer) == antes                    # vuelve al último confirmado
    assert c.mensaje == mensaje and c.mensajeRevertido is True
    assert globales == [] and c.pendientes == {}
    assert resueltos == [(clave, False, mensaje)]
    assert s.pendiente("GET", ruta)                     # y se relee el estado real


def test_sin_respuesta_relee_y_confirma_si_se_aplico(globales):
    c, s, resueltos = _ctrl()
    c.fijarIdioma("en")
    s.responder("PUT", "/language", Resultado(BACKEND_NO_RESPONDE), aplicar=True)
    assert c.pendientes == {"idioma": "verificando"} and c.idioma == "en"
    s.responder("GET", "/language")                     # el backend sí lo aplicó
    assert c.idioma == "en" and c.mensaje == "" and resueltos == [("idioma", True, "")]
    assert globales == [("idioma", "en")]


def test_sin_respuesta_relee_y_revierte_si_no_se_aplico(globales):
    c, s, resueltos = _ctrl()
    c.fijarUnidades("C", "psi")
    s.responder("PUT", "/units", Resultado(BACKEND_NO_RESPONDE))
    s.responder("GET", "/units")
    assert c.unidadPresion == "kPa" and c.mensaje == "opciones.err_sin_respuesta"
    assert c.mensajeRevertido is True and globales == []
    assert resueltos == [("unidades", False, "opciones.err_sin_respuesta")]


def test_sin_respuesta_ni_relectura_avisa_sin_confirmar_y_recarga(globales):
    c, s, _ = _ctrl()
    c.fijarImpresora(False)
    s.responder("PUT", "/printer/config", Resultado(BACKEND_NO_RESPONDE))
    s.responder("GET", "/printer/config", Resultado(BACKEND_NO_RESPONDE))
    assert c.impresoraHabilitada is True                # lo último confirmado
    assert c.mensaje == "opciones.cambio_sin_confirmar" and c.mensajeRevertido is False
    # B2: se relee solo la clave afectada, no los 4 GET
    assert s.pendiente("GET", "/printer/config") and not s.pendiente("GET", "/system_params")
    assert globales == []


def test_validacion_local_devuelve_false():
    c, s, _ = _ctrl()
    n = len(s.enviados)
    assert c.fijarIdioma("") is False and c.fijarUnidades("", "kPa") is False
    assert len(s.enviados) == n


# ── parámetros del equipo: asíncronos, sin optimismo ───────────────────────

def test_guardar_no_muestra_el_valor_hasta_el_200():
    c, s, resueltos = _ctrl()
    assert c.guardar("timeout_puerta", 90.0) is True
    assert ("PATCH", "/global_params/timeout_puerta", {"valor": 90}) in s.enviados
    assert _valor(c, "timeout_puerta") == 60            # sigue el vigente
    assert c.pendientes == {"param:timeout_puerta": "enviando"} and c.parametroPendiente
    assert c.guardar("timeout_puerta", 95) is False     # bloqueado mientras se guarda
    s.responder("PATCH", "/global_params/timeout_puerta")
    # M3: aceptado pero sin releer: sigue pendiente («verificando»), sin resolver
    assert c.pendientes == {"param:timeout_puerta": "verificando"} and c.parametroPendiente
    assert _valor(c, "timeout_puerta") == 60 and resueltos == []
    s.responder_gets()
    assert _valor(c, "timeout_puerta") == 90
    assert c.pendientes == {} and not c.parametroPendiente and c.sinConfirmar == []
    assert resueltos == [("param:timeout_puerta", True, "")]


def test_guardar_relee_una_sola_vez_solo_system_params():
    # B2 (c): un guardado hace una sola relectura, y solo de /system_params
    c, s, _ = _ctrl()
    n = len(s.enviados)
    c.guardar("timeout_puerta", 90)
    s.responder("PATCH", "/global_params/timeout_puerta")
    assert s.enviados[n + 1:] == [("GET", "/system_params", None)]
    s.responder_gets()
    assert len(s.enviados) == n + 2


def test_relectura_fallida_tras_200_deja_sin_confirmar():
    # M3 (b): la fila no muestra el valor viejo como vigente
    c, s, resueltos = _ctrl()
    c.guardar("timeout_puerta", 90)
    s.responder("PATCH", "/global_params/timeout_puerta")
    s.responder("GET", "/system_params", Resultado(BACKEND_NO_RESPONDE))
    assert c.sinConfirmar == ["timeout_puerta"]
    assert c.pendientes == {} and not c.parametroPendiente
    assert c.mensaje == "opciones.cambio_sin_confirmar" and c.mensajeRevertido is False
    assert resueltos == [("param:timeout_puerta", False, "opciones.cambio_sin_confirmar")]
    # una lectura válida posterior quita la marca y trae lo vigente
    c.cargar(); s.responder_gets()
    assert c.sinConfirmar == [] and _valor(c, "timeout_puerta") == 90


def test_lectura_anterior_no_pisa_la_relectura():
    # una carga lanzada antes del guardado que responde después no se aplica
    c, s, _ = _ctrl()
    c.cargar()
    vieja = next(e for e in s.en_vuelo if e[1] == "/system_params")
    s.en_vuelo.remove(vieja)
    viejo = s._lectura("/system_params")
    c.guardar("timeout_puerta", 90)
    s.responder("PATCH", "/global_params/timeout_puerta")
    s.responder("GET", "/system_params")
    assert _valor(c, "timeout_puerta") == 90
    vieja[3](viejo)
    assert _valor(c, "timeout_puerta") == 90


def test_lectura_fallida_de_idioma_conserva_lo_mostrado():
    # B2: sin cambio pendiente, una lectura fallida no deja el valor en blanco
    c, s, _ = _ctrl()
    c.cargar()
    s.responder("GET", "/language", Resultado(BACKEND_NO_RESPONDE))
    s.responder("GET", "/units", Resultado(BACKEND_NO_RESPONDE))
    s.responder("GET", "/printer/config", Resultado(BACKEND_NO_RESPONDE))
    assert c.idioma == "es" and c.unidadTemperatura == "C" and c.impresoraConocida


def test_calibracion_en_curso_tiene_mensaje():
    # (d) y el resto de códigos que el cliente deja pasar en estas rutas
    import json
    from autoclave.ui_qml.controllers.parametros_equipo_controller import mensaje_de
    assert mensaje_de("calibracion_en_curso") == "opciones.equipo_err_calibracion_en_curso"
    i18n = _RAIZ / "src/autoclave/i18n"
    for idioma in ("es", "en"):
        textos = json.loads((i18n / f"{idioma}.json").read_text(encoding="utf-8"))
        for causa in ("no_existe", "solo_lectura", "tipo_invalido", "fuera_de_rango", "incoherente",
                      "calibracion_en_curso", "ARCHIVO_NO_ESCRIBIBLE", "reinicio_no_disponible",
                      "estado_seguro_activo", "confirmacion_pendiente", "modo_prueba_activo"):
            clave = mensaje_de(causa)
            seccion, nombre = clave.split(".", 1)
            assert nombre in textos[seccion], (idioma, causa, clave)
    assert mensaje_de("calibracion_en_curso") != "opciones.err_generico"


def test_restablecer_asincrono():
    c, s, resueltos = _ctrl()
    s.lista[[p["clave"] for p in s.lista].index("vacio_empaque")]["valor"] = 50
    c.cargar(); s.responder_gets()
    assert c.restablecer("vacio_empaque") is True and _valor(c, "vacio_empaque") == 50
    s.responder("POST", "/global_params/vacio_empaque/reset")
    s.responder_gets()
    assert _valor(c, "vacio_empaque") == 30
    assert resueltos == [("param:vacio_empaque", True, "")]


def test_guardar_rechazado_conserva_el_vigente():
    c, s, resueltos = _ctrl()
    c.guardar("timeout_puerta", 90)
    s.responder("PATCH", "/global_params/timeout_puerta", Resultado("estado_no_permitido"))
    assert c.mensaje == "opciones.equipo_err_ciclo" and c.pendientes == {}
    assert s.pendiente("GET", "/system_params")
    s.responder_gets()
    assert _valor(c, "timeout_puerta") == 60
    assert resueltos == [("param:timeout_puerta", False, "opciones.equipo_err_ciclo")]


# ── sin respuesta: como el 200, se resuelve con la relectura (M3) ──────────

def test_sin_respuesta_verifica_y_confirma_si_se_aplico():
    c, s, resueltos = _ctrl()
    n = len(s.enviados)
    c.guardar("timeout_puerta", 90)
    s.responder("PATCH", "/global_params/timeout_puerta", Resultado(BACKEND_NO_RESPONDE),
                aplicar=True)
    assert c.pendientes == {"param:timeout_puerta": "verificando"} and c.parametroPendiente
    assert resueltos == [] and _valor(c, "timeout_puerta") == 60
    assert s.enviados[n + 1:] == [("GET", "/system_params", None)]   # solo esa relectura
    s.responder("GET", "/system_params")
    assert _valor(c, "timeout_puerta") == 90 and c.mensaje == ""
    assert c.pendientes == {} and not c.parametroPendiente and c.sinConfirmar == []
    assert resueltos == [("param:timeout_puerta", True, "")]


def test_sin_respuesta_verifica_y_rechaza_si_no_se_aplico():
    c, s, resueltos = _ctrl()
    c.guardar("timeout_puerta", 90)
    s.responder("PATCH", "/global_params/timeout_puerta", Resultado(BACKEND_NO_RESPONDE))
    assert c.pendientes == {"param:timeout_puerta": "verificando"}
    s.responder("GET", "/system_params")
    assert _valor(c, "timeout_puerta") == 60 and c.sinConfirmar == []
    assert c.mensaje == "opciones.err_sin_respuesta" and c.pendientes == {}
    assert resueltos == [("param:timeout_puerta", False, "opciones.err_sin_respuesta")]


def test_sin_respuesta_ni_relectura_deja_sin_confirmar():
    c, s, resueltos = _ctrl()
    c.guardar("timeout_puerta", 90)
    s.responder("PATCH", "/global_params/timeout_puerta", Resultado(BACKEND_NO_RESPONDE),
                aplicar=True)
    s.responder("GET", "/system_params", Resultado(BACKEND_NO_RESPONDE))
    assert c.sinConfirmar == ["timeout_puerta"] and c.pendientes == {}
    assert not c.parametroPendiente
    assert c.mensaje == "opciones.cambio_sin_confirmar"
    assert resueltos == [("param:timeout_puerta", False, "opciones.cambio_sin_confirmar")]


def test_restablecer_sin_respuesta_confirma_con_el_defecto():
    c, s, resueltos = _ctrl()
    s.lista[[p["clave"] for p in s.lista].index("vacio_empaque")]["valor"] = 50
    c.cargar(); s.responder_gets()
    c.restablecer("vacio_empaque")
    s.responder("POST", "/global_params/vacio_empaque/reset", Resultado(BACKEND_NO_RESPONDE),
                aplicar=True)
    s.responder_gets()
    assert _valor(c, "vacio_empaque") == 30
    assert resueltos == [("param:vacio_empaque", True, "")]


# ── salvaguarda: un callback que lanza no deja la clave pendiente ──────────

@pytest.mark.parametrize("patch", [None, Resultado(BACKEND_NO_RESPONDE)])
def test_callback_que_lanza_resuelve_con_fallo(monkeypatch, patch):
    c, s, resueltos = _ctrl()
    c.guardar("timeout_puerta", 90)
    s.responder("PATCH", "/global_params/timeout_puerta", patch)
    assert c.parametroPendiente is True

    def malformado(_datos):                         # cuerpo que el controlador no digiere
        raise TypeError("cuerpo malformado")
    monkeypatch.setattr(c, "_aplicar_parametros", malformado)
    s.responder("GET", "/system_params")
    assert "param:timeout_puerta" not in c._en_vuelo and c.pendientes == {}
    assert c.parametroPendiente is False
    assert resueltos == [("param:timeout_puerta", False, "opciones.err_generico")]
    assert c.mensaje == "opciones.err_generico"
    assert c.guardar("timeout_puerta", 95) is True      # la clave vuelve a poder guardarse


def test_destruir_cancela_los_envios():
    from shiboken6 import Shiboken
    c, s, _ = _ctrl()
    c.guardar("timeout_puerta", 90)
    ident = id(c)
    Shiboken.delete(c)
    assert ident in s.cancelados


# ── pantalla ───────────────────────────────────────────────────────────────

def test_pantalla_espera_cambio_resuelto_y_bloquea_atras():
    texto = _QML.read_text(encoding="utf-8")
    assert "const ok = restablecer" not in texto        # ya no usa el retorno
    assert "function onCambioResuelto(clave, ok, mensaje)" in texto
    assert "if (control.parametroPendiente)\n            return true" in texto
    assert 'raiz.pendiente("param:" + modelData.clave)' in texto
    assert "control.mensajeRevertido" in texto and "opciones.cargando" in texto
    assert "control.fijarImpresoraYReiniciar(v)" in texto   # sigue síncrono


def test_pantalla_expone_guardando_parametro_para_opciones():
    # M2 (a): OPCIONES lee `itemActivo.guardandoParametro` para bloquear
    # Inicio/cajón/Cerrar sesión; un valor ya enviado no es «cambio sin guardar»
    texto = _QML.read_text(encoding="utf-8")
    assert "readonly property bool guardandoParametro: control.parametroPendiente" in texto
    assert "readonly property bool cambiosPendientes: ajuste.cambiado && !ajuste.guardando" in texto
    # B3: la ventana de ajuste vuelve a tomar el parámetro tras la relectura
    assert "function onParametrosGrupoChanged()" in texto
    assert "ajuste.param = p" in texto
    # M3: la fila sin confirmar no muestra el valor anterior
    assert 'control.sinConfirmar.indexOf(modelData.clave)' in texto
    assert '"opciones.cambio_sin_confirmar"' in texto


def test_guardando_parametro_true_con_guardado_pendiente():
    # M2 (a): la propiedad del controlador que lee la pantalla
    c, s, _ = _ctrl()
    assert c.parametroPendiente is False
    c.guardar("timeout_puerta", 90)
    assert c.parametroPendiente is True
    s.responder("PATCH", "/global_params/timeout_puerta")
    assert c.parametroPendiente is True                 # verificando
    s.responder_gets()
    assert c.parametroPendiente is False

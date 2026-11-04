# tests/test_f6_operacion_critica.py
#
# FASE 6 (P1): OperacionCritica, sin optimismo. Nunca CONFIRMADA sin un 200
# o sin una relectura conciliada; una operación por clave; estado fijado
# antes de enviar; tardíos; generación de sesión; registro de proceso que se
# limpia al destruir el dueño.

import sys
import threading

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QObject
from PySide6.QtWidgets import QApplication

from autoclave.cliente.session_manager import SessionManager
from autoclave.ui_qml import operacion_critica as oc_mod
from autoclave.ui_qml import sesion_backend as sb
from autoclave.ui_qml.cambio_optimista import SIN_LECTURA
from autoclave.ui_qml.operacion_critica import (
    CONFIRMADA, ENVIANDO, INACTIVA, RECHAZADA, SIN_CONFIRMAR, VERIFICANDO,
    OperacionCritica, OperacionesCriticas)


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QApplication(sys.argv)


def _procesar(veces=5):
    for _ in range(veces):
        QCoreApplication.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


class SesionDoble:
    """enviar_async que guarda los callbacks; la prueba decide qué entregar."""
    def __init__(self):
        self.generacion = 0
        self.envios = []          # dicts con metodo, ruta, al_terminar, al_tardio, plazo_s
        self.cancelados = []
        self.antes_de_enviar = None

    def enviar_async(self, metodo, ruta, cuerpo=None, al_terminar=None, *, dueno=None,
                     al_tardio=None, plazo_s=None):
        if self.antes_de_enviar:
            self.antes_de_enviar()
        self.envios.append({"metodo": metodo, "ruta": ruta, "cuerpo": cuerpo,
                            "al_terminar": al_terminar, "al_tardio": al_tardio,
                            "plazo_s": plazo_s, "dueno": dueno})
        return True

    def cancelar_envios(self, dueno):
        self.cancelados.append(dueno)

    def responder(self, r, i=-1):
        self.envios[i]["al_terminar"](r)

    def tardio(self, r, i=-1):
        self.envios[i]["al_tardio"](r)


OK = sb.Resultado("ok", {"v": 1}, 200)
NO_RESPONDE = sb.Resultado(sb.BACKEND_NO_RESPONDE)
RECHAZO = sb.Resultado("estado_no_permitido", {}, 409)


class Resueltos:
    def __init__(self, oc):
        self.lista = []
        oc.operacionResuelta.connect(lambda *a: self.lista.append(a))


_VIVOS = []      # los dueños sin padre se destruirían al soltar la referencia


def _dueno():
    d = QObject()
    _VIVOS.append(d)
    return d


def _oc(sesion=None, registro=None):
    sesion = sesion or SesionDoble()
    reg = registro or OperacionesCriticas()
    dueno = _dueno()
    oc = OperacionCritica(dueno, lambda: sesion, registro=reg)
    return oc, sesion, reg, dueno


def _iniciar(oc, clave="k", **kw):
    kw.setdefault("plazo_s", 5.0)
    return oc.iniciar(clave, "POST", "/io/test/enter", {"a": 1}, **kw)


# ── transiciones ────────────────────────────────────────────────────────────

def test_200_confirma_y_ejecuta_al_ok():
    oc, s, reg, _ = _oc()
    res, vistos = Resueltos(oc), []
    assert _iniciar(oc, al_ok=vistos.append) is True
    assert oc.estado("k") == ENVIANDO and oc.en_curso("k") and oc.operacionEnCurso
    assert s.envios[0]["plazo_s"] == 5.0 and s.envios[0]["dueno"] is oc
    s.responder(OK)
    assert vistos == [OK]
    assert res.lista == [("k", CONFIRMADA, "")]
    assert oc.estado("k") == INACTIVA and not oc.en_curso()


def test_rechazo_misma_generacion():
    oc, s, _, _ = _oc()
    res = Resueltos(oc)
    _iniciar(oc)
    s.responder(RECHAZO)
    assert res.lista == [("k", RECHAZADA, "opciones.err_bloqueada")]


def test_rechazo_con_mensaje_de_al_rechazo_y_codigo_de_ruta():
    oc, s, _, _ = _oc()
    res = Resueltos(oc)
    _iniciar(oc, al_rechazo=lambda r: "io.err_rechazado")
    s.responder(RECHAZO)
    _iniciar(oc, clave="b")
    s.responder(sb.Resultado("modo_prueba_dueno_vigente", {}, 409))
    assert res.lista == [("k", RECHAZADA, "io.err_rechazado"),
                         ("b", RECHAZADA, "io.err_dueno_vigente")]


@pytest.mark.parametrize("veredicto,final,msg", [
    (CONFIRMADA, CONFIRMADA, ""),
    (RECHAZADA, RECHAZADA, "opciones.err_sin_respuesta"),
    ((RECHAZADA, "x.propio"), RECHAZADA, "x.propio"),
    (SIN_CONFIRMAR, SIN_CONFIRMAR, "operacion.sin_confirmar"),
    ("cualquier_cosa", SIN_CONFIRMAR, "operacion.sin_confirmar"),
])
def test_no_responde_relee_y_concilia(veredicto, final, msg):
    oc, s, _, _ = _oc()
    res, lecturas, leidos = Resueltos(oc), [], []
    _iniciar(oc, releer=lecturas.append,
             conciliar=lambda v: (leidos.append(v), veredicto)[1])
    s.responder(NO_RESPONDE)
    assert oc.estado("k") == VERIFICANDO and res.lista == [] and len(lecturas) == 1
    lecturas[0]({"activo": True})
    assert leidos == [{"activo": True}]
    assert res.lista == [("k", final, msg)] and oc.estado("k") == INACTIVA


def test_no_responde_sin_lectura_sin_releer_o_sin_conciliar():
    oc, s, _, _ = _oc()
    res, lecturas = Resueltos(oc), []
    _iniciar(oc, releer=lecturas.append, conciliar=lambda v: CONFIRMADA)
    s.responder(NO_RESPONDE)
    lecturas[0](SIN_LECTURA)
    _iniciar(oc, clave="b")                                # sin releer
    s.responder(NO_RESPONDE)
    _iniciar(oc, clave="c", releer=lecturas.append, msg_sin_confirmar="io.prueba_sin_confirmar")
    s.responder(NO_RESPONDE)
    lecturas[1]({"v": 1})                                  # sin conciliar: nunca confirma
    assert res.lista == [("k", SIN_CONFIRMAR, "operacion.sin_confirmar"),
                         ("b", SIN_CONFIRMAR, "operacion.sin_confirmar"),
                         ("c", SIN_CONFIRMAR, "io.prueba_sin_confirmar")]


def test_relectura_vence_a_los_5_s():
    oc, s, _, _ = _oc()
    res, lecturas = Resueltos(oc), []
    _iniciar(oc, releer=lecturas.append, conciliar=lambda v: CONFIRMADA)
    s.responder(NO_RESPONDE)
    op = oc._ops["k"]
    assert op.timer_relectura.interval() == int(oc_mod.PLAZO_RELECTURA_S * 1000)
    op.timer_relectura.timeout.emit()
    lecturas[0]({"v": 1})                                  # lectura que llega tarde: no cuenta
    assert res.lista == [("k", SIN_CONFIRMAR, "operacion.sin_confirmar")]


def test_tope_total_plazo_mas_relectura():
    oc, s, _, _ = _oc()
    res = Resueltos(oc)
    _iniciar(oc, plazo_s=8.0, bloquea_navegacion=True)
    op = oc._ops["k"]
    assert op.timer_total.interval() == int((8.0 + oc_mod.PLAZO_RELECTURA_S) * 1000)
    op.timer_total.timeout.emit()                          # nunca llegó nada
    assert res.lista == [("k", SIN_CONFIRMAR, "operacion.sin_confirmar")]
    assert not oc.bloqueaNavegacion
    s.responder(OK)                                        # ya resuelta: no cambia nada
    assert len(res.lista) == 1


@pytest.mark.parametrize("r", [RECHAZO, sb.Resultado("sesion_invalida"), NO_RESPONDE])
def test_cambio_de_generacion_sin_200_es_sin_confirmar_sin_relectura(r):
    oc, s, _, _ = _oc()
    res, lecturas = Resueltos(oc), []
    _iniciar(oc, releer=lecturas.append, conciliar=lambda v: CONFIRMADA)
    s.generacion += 1                                      # la sesión se cerró en vuelo
    s.responder(r)
    assert res.lista == [("k", SIN_CONFIRMAR, "operacion.sin_confirmar")] and lecturas == []


def test_cambio_de_generacion_con_200_confirma():
    oc, s, _, _ = _oc()
    res = Resueltos(oc)
    _iniciar(oc)
    s.generacion += 1
    s.responder(OK)
    assert res.lista == [("k", CONFIRMADA, "")]


def test_peticion_que_no_salio_es_rechazada_con_la_causa():
    class NoSale(SesionDoble):
        def enviar_async(self, *a, **kw):
            super().enviar_async(*a, **kw)
            return False
    oc, s, _, _ = _oc(NoSale())
    res = Resueltos(oc)
    assert _iniciar(oc, releer=lambda cb: cb({"v": 1}), conciliar=lambda v: CONFIRMADA) is True
    s.responder(NO_RESPONDE)                               # en diferido: sin conexión
    assert res.lista == [("k", RECHAZADA, "sesion.backend_no_responde")]


# ── tardíos ─────────────────────────────────────────────────────────────────

def test_tardio_200_tras_sin_confirmar():
    oc, s, _, _ = _oc()
    res, vistos, lecturas = Resueltos(oc), [], []
    _iniciar(oc, al_ok=vistos.append, releer=lecturas.append)   # sin conciliar
    s.responder(NO_RESPONDE)
    lecturas[0]({"v": 1})
    assert res.lista == [("k", SIN_CONFIRMAR, "operacion.sin_confirmar")] and vistos == []
    s.tardio(OK)
    assert res.lista[-1] == ("k", CONFIRMADA, "operacion.confirmada_tarde")
    assert vistos == [OK] and len(lecturas) == 2           # y relee
    s.tardio(OK)                                           # una sola vez
    assert len(res.lista) == 2 and vistos == [OK]


def test_tardio_rechazo_o_tras_relectura_solo_relee():
    oc, s, _, _ = _oc()
    res, lecturas = Resueltos(oc), []
    _iniciar(oc, releer=lecturas.append)
    s.responder(NO_RESPONDE)
    lecturas[0](SIN_LECTURA)
    s.tardio(RECHAZO)
    assert len(res.lista) == 1 and len(lecturas) == 2
    _iniciar(oc, clave="b", releer=lecturas.append, conciliar=lambda v: SIN_CONFIRMAR)
    s.responder(NO_RESPONDE)
    lecturas[2]({"v": 0})
    s.tardio(RECHAZO)                                      # tardío no-200: solo relee
    assert [x[1] for x in res.lista] == [SIN_CONFIRMAR, SIN_CONFIRMAR] and len(lecturas) == 4


def test_m1_200_tardio_tras_rechazada_por_conciliacion_confirma_tarde():
    """m1 (revisión FASE 6): RECHAZADA que vino de la conciliación tras un
    backend_no_responde + 200 tardío -> CONFIRMADA "confirmada_tarde" (una
    vez), con al_ok y relectura."""
    oc, s, _, _ = _oc()
    res, vistos, lecturas = Resueltos(oc), [], []
    _iniciar(oc, al_ok=vistos.append, releer=lecturas.append, conciliar=lambda v: RECHAZADA)
    s.responder(NO_RESPONDE)
    lecturas[0]({"v": 0})
    assert res.lista == [("k", RECHAZADA, "opciones.err_sin_respuesta")] and vistos == []
    s.tardio(OK)
    assert res.lista[-1] == ("k", CONFIRMADA, "operacion.confirmada_tarde")
    assert vistos == [OK] and len(lecturas) == 2
    s.tardio(OK)
    assert len(res.lista) == 2 and vistos == [OK]


def test_m1_200_tardio_tras_rechazo_real_del_backend_no_confirma():
    oc, s, _, _ = _oc()
    res, vistos = Resueltos(oc), []
    _iniciar(oc, al_ok=vistos.append, releer=lambda cb: None, conciliar=lambda v: CONFIRMADA)
    s.responder(RECHAZO)
    s.tardio(OK)
    assert res.lista == [("k", RECHAZADA, "opciones.err_bloqueada")] and vistos == []


def test_m3_peticion_que_no_salio_pasa_por_al_rechazo():
    class NoSale(SesionDoble):
        def enviar_async(self, *a, **kw):
            super().enviar_async(*a, **kw)
            return False
    oc, s, _, _ = _oc(NoSale())
    res, causas = Resueltos(oc), []
    _iniciar(oc, al_rechazo=lambda r: (causas.append(r.causa), "x.propio")[1])
    s.responder(sb.Resultado("sesion_invalida"))
    assert causas == ["sesion_invalida"] and res.lista == [("k", RECHAZADA, "x.propio")]


def test_200_tardio_durante_la_verificacion_confirma():
    oc, s, _, _ = _oc()
    res, lecturas = Resueltos(oc), []
    _iniciar(oc, releer=lecturas.append, conciliar=lambda v: RECHAZADA)
    s.responder(NO_RESPONDE)
    s.tardio(RECHAZO)                                      # no decide: sigue verificando
    assert oc.estado("k") == VERIFICANDO
    s.tardio(OK)
    lecturas[0]({"v": 0})                                  # lectura vieja: ya no cuenta
    assert res.lista == [("k", CONFIRMADA, "")]


# ── MAYOR-1 (corrección tras revisión, 04-nov): id, grupo y contexto ──────

def test_cada_operacion_tiene_id_y_contexto_propios_en_al_ok_y_desenlace():
    oc, s, _, _ = _oc()
    vistos = []
    oc.operacionResuelta.connect(lambda *a: vistos.append(("res", oc.id_resuelta,
                                                           oc.contexto_resuelta)))
    _iniciar(oc, al_ok=lambda r: vistos.append(("ok", oc.id_resuelta, oc.contexto_resuelta)),
             contexto="A")
    ida = oc.ultimo_id
    assert ida > 0 and oc.id_de("k") == ida and oc.contexto_de("k") == "A"
    s.responder(OK)
    _iniciar(oc, contexto="B")
    idb = oc.ultimo_id
    assert idb != ida
    s.responder(OK)
    assert vistos == [("ok", ida, "A"), ("res", ida, "A"), ("res", idb, "B")]
    assert oc.id_resuelta == 0 and oc.contexto_resuelta is None and oc.id_de("k") == 0


@pytest.mark.parametrize("final", ["sin_confirmar", "rechazo_conciliado"])
def test_200_tardio_con_otra_vigente_de_la_misma_clave_solo_relee(final):
    """El 200 tardío de A con B (misma clave) en vuelo: ni al_ok de A ni
    «confirmada_tarde» (se confundiría con B); solo log y relectura."""
    oc, s, _, _ = _oc()
    res, vistos, lecturas = Resueltos(oc), [], []
    _iniciar(oc, al_ok=vistos.append, releer=lecturas.append,
             conciliar=(lambda v: RECHAZADA) if final == "rechazo_conciliado" else None)
    i_a = len(s.envios) - 1
    s.responder(NO_RESPONDE)
    lecturas[0]({"v": 0})
    assert len(res.lista) == 1
    assert _iniciar(oc, al_ok=vistos.append) is True               # B, vigente
    s.tardio(OK, i=i_a)
    assert len(res.lista) == 1 and vistos == [] and len(lecturas) == 2
    assert oc.estado("k") == ENVIANDO
    s.responder(OK)                                                # el 200 de B: suyo
    assert res.lista[-1] == ("k", CONFIRMADA, "") and vistos == [OK]


def test_200_tardio_con_otra_vigente_del_mismo_grupo_solo_relee():
    oc, s, _, _ = _oc()
    res, vistos, lecturas = Resueltos(oc), [], []
    _iniciar(oc, clave="a", al_ok=vistos.append, releer=lecturas.append, grupo="g")
    s.responder(NO_RESPONDE)
    lecturas[0](SIN_LECTURA)
    _iniciar(oc, clave="b", grupo="g")
    s.tardio(OK, i=0)
    assert [x[1] for x in res.lista] == [SIN_CONFIRMAR] and vistos == []
    # sin grupo común, el tardío sí se anuncia (claves independientes)
    _iniciar(oc, clave="c", al_ok=vistos.append, releer=lecturas.append)
    i_c = len(s.envios) - 1
    s.responder(NO_RESPONDE)
    lecturas[-1](SIN_LECTURA)
    s.tardio(OK, i=i_c)
    assert res.lista[-1] == ("c", CONFIRMADA, "operacion.confirmada_tarde") and vistos == [OK]


def test_al_ok_tardio_reemplaza_a_al_ok_solo_en_el_tardio():
    oc, s, _, _ = _oc()
    res, normal, tardio = Resueltos(oc), [], []
    _iniciar(oc, al_ok=normal.append, al_ok_tardio=tardio.append, releer=lambda cb: cb(SIN_LECTURA))
    s.responder(NO_RESPONDE)
    s.tardio(OK)
    assert normal == [] and tardio == [OK]
    assert res.lista[-1] == ("k", CONFIRMADA, "operacion.confirmada_tarde")


# ── reentrada, excepciones, nunca éxito sin 200 ─────────────────────────────

def test_reentrada_con_doble_sincrono_estado_fijado_antes_de_enviar():
    class Sincrono:                                        # solo `enviar`: entrega en el acto
        def __init__(self):
            self.vistos = []

        def enviar(self, metodo, ruta, cuerpo=None):
            self.vistos.append((oc.estado("k"), oc.operacionEnCurso,
                                _iniciar(oc)))             # reentrada durante el envío
            return OK
    sesion = Sincrono()
    reg = OperacionesCriticas()
    oc = OperacionCritica(_dueno(), lambda: sesion, registro=reg)
    res = Resueltos(oc)
    assert _iniciar(oc) is True
    assert sesion.vistos == [(ENVIANDO, True, False)]
    assert res.lista == [("k", CONFIRMADA, "")] and not oc.en_curso()


def test_una_operacion_por_clave():
    oc, s, _, _ = _oc()
    assert _iniciar(oc) is True
    assert _iniciar(oc) is False and len(s.envios) == 1
    assert _iniciar(oc, clave="otra") is True


@pytest.mark.parametrize("donde", ["al_ok", "al_rechazo", "releer", "conciliar"])
def test_excepcion_en_callback_no_deja_la_clave_en_vuelo(donde):
    def boom(*_a):
        raise RuntimeError("x")
    oc, s, reg, _ = _oc()
    res = Resueltos(oc)
    kw = {"releer": lambda cb: cb({"v": 1}), "conciliar": lambda v: CONFIRMADA}
    kw[donde] = boom
    _iniciar(oc, bloquea_navegacion=True, **kw)
    s.responder({"al_ok": OK, "al_rechazo": RECHAZO}.get(donde, NO_RESPONDE))
    assert not oc.en_curso("k") and not reg.bloqueaNavegacion
    esperado = {"al_ok": CONFIRMADA, "al_rechazo": RECHAZADA}.get(donde, SIN_CONFIRMAR)
    assert res.lista[0][1] == esperado
    if donde == "al_rechazo":
        assert res.lista[0][2] == "opciones.err_bloqueada"


def test_excepcion_al_enviar_no_queda_en_vuelo():
    class Rota(SesionDoble):
        def enviar_async(self, *a, **kw):
            raise RuntimeError("roto")
    oc, _, reg, _ = _oc(Rota())
    res = Resueltos(oc)
    _iniciar(oc, bloquea_navegacion=True)
    assert res.lista == [("k", SIN_CONFIRMAR, "operacion.sin_confirmar")]
    assert not oc.en_curso() and not reg.bloqueaNavegacion


def test_nunca_confirmada_sin_200_ni_conciliacion():
    """Barrido: cualquier respuesta no-200 seguida de cualquier lectura sin
    conciliar a CONFIRMADA nunca da CONFIRMADA."""
    causas = [NO_RESPONDE, RECHAZO, sb.Resultado("sesion_invalida"), sb.Resultado(sb.ERROR_GENERICO)]
    for r in causas:
        for veredicto in (RECHAZADA, SIN_CONFIRMAR, None, "ok", True):
            for leido in (SIN_LECTURA, {"v": 1}, None):
                oc, s, _, _ = _oc()
                res = Resueltos(oc)
                _iniciar(oc, releer=lambda cb, lv=leido: cb(lv),
                         conciliar=lambda v, ve=veredicto: ve)
                s.responder(r)
                assert res.lista and all(x[1] != CONFIRMADA for x in res.lista), (r, veredicto, leido)


# ── registro y navegación ───────────────────────────────────────────────────

def test_bloquea_navegacion_y_registro():
    reg = OperacionesCriticas()
    cambios = []
    reg.bloqueaNavegacionChanged.connect(lambda: cambios.append(reg.bloqueaNavegacion))
    a, s, _, _ = _oc(registro=reg)
    b, s2, _, _ = _oc(registro=reg)
    _iniciar(a, bloquea_navegacion=False)
    assert reg.operacionEnCurso and not reg.bloqueaNavegacion and not a.bloqueaNavegacion
    _iniciar(b, bloquea_navegacion=True)
    assert reg.bloqueaNavegacion and b.bloqueaNavegacion and cambios == [True]
    s2.responder(OK)
    assert not reg.bloqueaNavegacion and cambios == [True, False]
    s.responder(OK)
    assert not reg.operacionEnCurso


def test_registro_se_limpia_al_destruir_el_dueno():
    reg = OperacionesCriticas()
    oc, s, _, dueno = _oc(registro=reg)
    _iniciar(oc, bloquea_navegacion=True)
    assert reg.bloqueaNavegacion and reg.registradas() == 1
    dueno.deleteLater()
    _procesar()
    assert not reg.bloqueaNavegacion and reg.registradas() == 0


def test_cancelar_quita_del_registro_y_no_entrega():
    reg = OperacionesCriticas()
    oc, s, _, _ = _oc(registro=reg)
    res = Resueltos(oc)
    _iniciar(oc, bloquea_navegacion=True)
    oc.cancelar()
    assert s.cancelados == [oc] and reg.registradas() == 0 and not reg.bloqueaNavegacion
    s.responder(OK)
    s.tardio(OK)
    assert res.lista == [] and not oc.en_curso()


def test_registro_de_proceso_por_defecto():
    oc = OperacionCritica(_dueno(), lambda: SesionDoble())
    assert oc._registro is oc_mod.registro


# ── con una SesionVentana real ──────────────────────────────────────────────

class _Transporte:
    def __init__(self):
        self.respuestas = {}

    def __call__(self, metodo, ruta, cuerpo, token, plazo):
        r = self.respuestas.get((metodo, ruta), (200, {}))
        if isinstance(r, Exception):
            raise r
        return r


class _Diferido:
    def __init__(self):
        self.tareas = []

    def __call__(self, tarea):
        self.tareas.append(tarea)

    def correr(self):
        tareas, self.tareas = self.tareas, []
        for t in tareas:
            h = threading.Thread(target=t)
            h.start()
            h.join(5)


class _Reloj:
    t = 100.0

    def __call__(self):
        return self.t


def test_sesion_real_plazo_relectura_y_tardio():
    SessionManager.login({"usuario": "ana", "nombre": "Ana", "rol": "ingeniero"}, token="t-f6")
    try:
        tr, d, reloj = _Transporte(), _Diferido(), _Reloj()
        s = sb.SesionVentana(transporte=tr, ejecutar=d, reloj=reloj)
        assert s.generacion == 0
        oc = OperacionCritica(_dueno(), lambda: s, registro=OperacionesCriticas())
        res, vistos = Resueltos(oc), []

        def releer(al_leido):
            sb.enviar_async(s, "GET", "/io/test", None,
                            lambda r: al_leido(r.datos if r.ok else SIN_LECTURA), dueno=oc)
        oc.iniciar("prueba", "POST", "/io/test/enter", None, plazo_s=3.0, al_ok=vistos.append,
                   releer=releer, conciliar=lambda v: CONFIRMADA if v.get("activo") else RECHAZADA)
        post = d.tareas.pop()                              # el POST no vuelve a tiempo
        reloj.t += 3.0
        s._envios._vaciar()
        assert oc.estado("prueba") == VERIFICANDO
        tr.respuestas[("GET", "/io/test")] = ConnectionError("caído")
        d.correr()
        s._envios._vaciar()
        assert res.lista == [("prueba", SIN_CONFIRMAR, "operacion.sin_confirmar")]
        tr.respuestas[("GET", "/io/test")] = (200, {"activo": True})
        h = threading.Thread(target=post)
        h.start()
        h.join(5)
        s._envios._vaciar()                                # 200 tardío
        assert res.lista[-1] == ("prueba", CONFIRMADA, "operacion.confirmada_tarde")
        assert len(vistos) == 1
        s.cerrar_local()
        assert s.generacion == 1
    finally:
        SessionManager.logout()


def test_funcion_de_modulo_pasa_plazo_solo_si_viene():
    class Antigua:                                         # firma anterior, sin plazo_s
        def __init__(self):
            self.kw = None

        def enviar_async(self, metodo, ruta, cuerpo, al_terminar, *, dueno=None):
            self.kw = {"dueno": dueno}
            return True
    a = Antigua()
    assert sb.enviar_async(a, "GET", "/x", None, lambda r: None) is True
    s = SesionDoble()
    sb.enviar_async(s, "GET", "/x", None, lambda r: None, plazo_s=9.0)
    assert s.envios[0]["plazo_s"] == 9.0

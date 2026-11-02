# tests/test_cambio_optimista.py
#
# CambioOptimista (AJUSTES 2026-11-02, paso 2 fase 1): cambio que se ve al
# instante, una petición en vuelo por clave (solo el último toque espera),
# reversión al último valor CONFIRMADO, verificación por relectura ante
# backend_no_responde y lecturas que nunca pisan un pendiente. Python puro.

from types import SimpleNamespace

from autoclave.ui_qml.cambio_optimista import (
    ENVIANDO, SIN_CONFIRMAR, SIN_LECTURA, VERIFICANDO, CambioOptimista)

K = "usuario:tomas"


def R(causa):
    return SimpleNamespace(causa=causa, ok=causa == "ok")


class Arnes:
    def __init__(self, releer=True):
        self.envios, self.lecturas = [], []
        self.cambios, self.revertidos, self.confirmados = [], [], []
        self.avisos_pendientes = 0
        self.o = CambioOptimista(self._lanzar, lambda k, v: self.cambios.append((k, v)),
                                 lambda k, c: self.revertidos.append((k, c)),
                                 self._releer if releer else None,
                                 al_confirmar=self.confirmados.append,
                                 al_pendientes=self._pend)

    def _pend(self):
        self.avisos_pendientes += 1

    def _lanzar(self, clave, valor, al_terminar):
        self.envios.append((clave, valor, al_terminar))

    def _releer(self, clave, al_leer):
        self.lecturas.append((clave, al_leer))

    def responder(self, i, causa):
        self.envios[i][2](R(causa))


def test_cambia_en_el_acto_y_las_lecturas_no_pisan_el_pendiente():
    a = Arnes()
    assert a.o.confirmar_lectura(K, True)
    a.o.aplicar(K, False)
    assert a.cambios == [(K, False)]                 # antes de cualquier respuesta
    assert a.o.pendiente(K) == ENVIANDO and a.o.pendientes() == {K: ENVIANDO}
    assert a.o.mostrar(K, True) is False             # un sondeo trae el valor viejo
    assert not a.o.confirmar_lectura(K, True)
    a.responder(0, "ok")
    assert a.o.pendiente(K) is None and a.confirmados == [K]
    assert a.o.confirmado(K) is False and a.revertidos == []
    assert a.o.mostrar(K, False) is False


def test_rechazo_vuelve_al_ultimo_confirmado_no_al_previo():
    a = Arnes()
    a.o.confirmar_lectura(K, "A")
    a.o.aplicar(K, "B")
    a.o.aplicar(K, "C")                              # espera a que vuelva B
    a.responder(0, "conflicto")                      # B rechazado: sale C sin avisar
    assert a.revertidos == [] and [e[1] for e in a.envios] == ["B", "C"]
    a.responder(1, "rol_sin_permiso")
    assert a.cambios[-1] == (K, "A")                 # no a «B»
    assert a.revertidos == [(K, "rol_sin_permiso")] and a.o.pendiente(K) is None


def test_toques_rapidos_salen_en_orden_y_solo_el_ultimo_espera():
    a = Arnes()
    a.o.confirmar_lectura(K, 0)
    for v in (1, 2, 3):
        a.o.aplicar(K, v)
    assert [e[1] for e in a.envios] == [1]
    assert a.o.mostrar(K, 0) == 3
    a.responder(0, "ok")
    assert [e[1] for e in a.envios] == [1, 3]        # el 2 nunca sale
    assert a.o.confirmado(K) == 1 and a.o.pendiente(K) == ENVIANDO
    a.responder(1, "ok")
    assert a.o.confirmado(K) == 3 and a.o.pendiente(K) is None and a.confirmados == [K]


def test_sin_respuesta_relee_y_coincide_confirma_en_silencio():
    a = Arnes()
    a.o.confirmar_lectura(K, True)
    a.o.aplicar(K, False)
    a.responder(0, "backend_no_responde")
    assert a.o.pendiente(K) == VERIFICANDO and len(a.lecturas) == 1
    a.lecturas[0][1](False)
    assert a.o.pendiente(K) is None and a.revertidos == [] and a.confirmados == [K]
    assert a.o.confirmado(K) is False


def test_sin_respuesta_relee_y_no_coincide_revierte_y_avisa():
    a = Arnes()
    a.o.confirmar_lectura(K, True)
    a.o.aplicar(K, False)
    a.responder(0, "backend_no_responde")
    a.lecturas[0][1](True)
    assert a.cambios[-1] == (K, True) and a.revertidos == [(K, "backend_no_responde")]


def test_sin_respuesta_y_sin_lectura_revierte_sin_confirmar():
    a = Arnes()
    a.o.confirmar_lectura(K, True)
    a.o.aplicar(K, False)
    a.responder(0, "backend_no_responde")
    a.lecturas[0][1](SIN_LECTURA)
    assert a.cambios[-1] == (K, True) and a.revertidos == [(K, SIN_CONFIRMAR)]
    b = Arnes(releer=False)
    b.o.confirmar_lectura(K, True)
    b.o.aplicar(K, False)
    b.responder(0, "backend_no_responde")
    assert b.revertidos == [(K, SIN_CONFIRMAR)] and b.cambios[-1] == (K, True)


def test_toque_durante_la_verificacion_sale_despues():
    a = Arnes()
    a.o.confirmar_lectura(K, 0)
    a.o.aplicar(K, 1)
    a.responder(0, "backend_no_responde")
    a.o.aplicar(K, 2)
    assert len(a.envios) == 1 and a.o.mostrar(K, 0) == 2
    a.lecturas[0][1](1)
    assert [e[1] for e in a.envios] == [1, 2] and a.revertidos == []
    assert a.o.confirmado(K) == 1


def test_lectura_lanzada_antes_de_un_cambio_se_descarta():
    a = Arnes()
    a.o.confirmar_lectura(K, True)
    marca = a.o.marca()                              # GET lanzado
    a.o.aplicar(K, False)
    a.responder(0, "ok")
    assert not a.o.confirmar_lectura(K, True, marca)  # respuesta vieja del GET
    assert a.o.confirmado(K) is False
    assert a.o.confirmar_lectura(K, False, a.o.marca())
    assert a.o.confirmar_lectura("otra", 5, marca)   # otra clave no se toca


def test_actual_sirve_de_confirmado_si_no_hubo_lectura():
    a = Arnes()
    a.o.aplicar(K, False, True)
    a.responder(0, "conflicto")
    assert a.cambios == [(K, False), (K, True)]


def test_respuesta_sin_resultado_reconocible_se_trata_como_sin_respuesta():
    a = Arnes()
    a.o.confirmar_lectura(K, True)
    a.o.aplicar(K, False)
    a.envios[0][2](None)
    assert a.o.pendiente(K) == VERIFICANDO

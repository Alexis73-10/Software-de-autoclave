# ui_qml/cambio_optimista.py
#
# Cambio de configuración que se ve al instante y se revierte si el backend
# no lo acepta (AJUSTES 2026-11-02, paso 2 fase 1). Python puro, sin Qt: lo
# usan los controladores con `sesion_backend.enviar_async`, y todas las
# llamadas (también las de `lanzar` y `releer` al terminar) ocurren en el
# hilo de la GUI.
#
# Por clave (p. ej. "usuario:tomas_tec"):
#   - `confirmar_lectura(clave, valor)`: valor leído del backend. No pisa un
#     cambio pendiente; con `marca` (de `marca()` al lanzar la lectura) se
#     descarta si la clave cambió o se resolvió después de lanzarla.
#   - `mostrar(clave, valor_backend)`: el valor pendiente si lo hay; si no, el
#     del backend (las lecturas y sondeos nunca pisan un pendiente).
#   - `aplicar(clave, nuevo)`: `al_cambiar(clave, nuevo)` en el acto y envío
#     con `lanzar(clave, valor, al_terminar)`. Una sola petición en vuelo por
#     clave: los toques que llegan mientras tanto dejan solo el último como
#     «siguiente», que sale al volver la respuesta.
# Resolución: ok -> confirmado; rechazo -> vuelve al último CONFIRMADO
# (`al_cambiar`) y `al_revertir(clave, causa)`; backend_no_responde ->
# «verificando»: `releer(clave, al_leer)` y se concilia (coincide: se
# confirma en silencio; otro valor: se muestra ese y se avisa con la causa;
# sin lectura (`SIN_LECTURA`): vuelve a lo confirmado y avisa SIN_CONFIRMAR).
# Una respuesta de una generación anterior (hubo otro toque) no revierte ni
# avisa: solo actualiza lo confirmado y deja salir el «siguiente».

import logging

logger = logging.getLogger(__name__)

ENVIANDO = "enviando"
VERIFICANDO = "verificando"
SIN_CONFIRMAR = "sin_confirmar"          # causa: sin respuesta y sin poder releer
_SIN_RESPUESTA = "backend_no_responde"   # = sesion_backend.BACKEND_NO_RESPONDE (sin Qt aquí)


class _SinLectura:
    def __repr__(self):
        return "SIN_LECTURA"


SIN_LECTURA = _SinLectura()
_NADA = object()


class _Clave:
    __slots__ = ("confirmado", "mostrado", "estado", "siguiente", "gen", "tocada")

    def __init__(self):
        self.confirmado = _NADA      # último valor confirmado por el backend
        self.mostrado = _NADA        # valor pendiente que se muestra
        self.estado = None           # None | ENVIANDO | VERIFICANDO
        self.siguiente = _NADA       # último toque llegado con una petición en vuelo
        self.gen = 0
        self.tocada = 0              # marca del último aplicar o resolución


class CambioOptimista:
    def __init__(self, lanzar, al_cambiar, al_revertir, releer=None, *,
                 al_confirmar=None, al_pendientes=None):
        """`al_confirmar(clave)`: el cambio quedó confirmado (opcional).
        `al_pendientes()`: cambió el conjunto de claves pendientes (opcional)."""
        self._lanzar = lanzar
        self._al_cambiar = al_cambiar
        self._al_revertir = al_revertir
        self._releer = releer
        self._al_confirmar = al_confirmar
        self._al_pendientes = al_pendientes
        self._claves: dict = {}
        self._reloj = 0

    # ── consulta ─────────────────────────────────────────────────────────
    def _c(self, clave) -> _Clave:
        c = self._claves.get(clave)
        if c is None:
            c = self._claves[clave] = _Clave()
        return c

    def _tocar(self, c: _Clave) -> None:
        self._reloj += 1
        c.tocada = self._reloj

    def marca(self) -> int:
        """Para `confirmar_lectura`: tomarla al lanzar la lectura."""
        return self._reloj

    def pendiente(self, clave):
        c = self._claves.get(clave)
        return None if c is None else c.estado

    def pendientes(self) -> dict:
        return {k: c.estado for k, c in self._claves.items() if c.estado}

    def confirmado(self, clave, defecto=None):
        c = self._claves.get(clave)
        return defecto if c is None or c.confirmado is _NADA else c.confirmado

    def mostrar(self, clave, valor_backend):
        c = self._claves.get(clave)
        if c is None or not c.estado:
            return valor_backend
        if c.siguiente is not _NADA:
            return c.siguiente
        return valor_backend if c.mostrado is _NADA else c.mostrado

    def confirmar_lectura(self, clave, valor_backend, marca=None) -> bool:
        """True si la lectura se aceptó como valor confirmado."""
        c = self._c(clave)
        if c.estado:
            return False
        if marca is not None and c.tocada > marca:
            return False                 # lectura lanzada antes del último cambio
        c.confirmado = valor_backend
        return True

    # ── cambio ───────────────────────────────────────────────────────────
    def aplicar(self, clave, nuevo, actual=_NADA) -> None:
        """`actual`: valor que se muestra ahora; solo se usa como confirmado
        si esta clave nunca recibió `confirmar_lectura`."""
        c = self._c(clave)
        if c.confirmado is _NADA and actual is not _NADA:
            c.confirmado = actual
        c.gen += 1
        self._tocar(c)
        if c.estado:
            c.siguiente = nuevo
            self._al_cambiar(clave, nuevo)
            return
        c.mostrado = nuevo
        self._al_cambiar(clave, nuevo)
        self._enviar(clave, c, nuevo)

    def _enviar(self, clave, c: _Clave, valor) -> None:
        c.estado = ENVIANDO
        c.mostrado = valor
        gen = c.gen
        self._notificar()
        self._lanzar(clave, valor, lambda r: self._al_responder(clave, valor, gen, r))

    def _al_responder(self, clave, valor, gen, r) -> None:
        c = self._c(clave)
        causa = getattr(r, "causa", _SIN_RESPUESTA)
        ok = bool(getattr(r, "ok", False))
        if ok:
            c.confirmado = valor
        if self._sacar_siguiente(clave, c):
            return
        if gen != c.gen:
            # no debería ocurrir sin «siguiente»; se resuelve sin avisar
            logger.warning("Respuesta de una generación anterior sin cambio pendiente: %s", clave)
            self._cerrar(clave, c)
            return
        if ok:
            self._cerrar(clave, c)
            if self._al_confirmar:
                self._al_confirmar(clave)
        elif causa == _SIN_RESPUESTA:
            self._verificar(clave, c, valor, gen)
        else:
            self._revertir(clave, c, causa)

    def _sacar_siguiente(self, clave, c: _Clave) -> bool:
        if c.siguiente is _NADA:
            return False
        valor, c.siguiente = c.siguiente, _NADA
        self._tocar(c)
        self._enviar(clave, c, valor)
        return True

    def _verificar(self, clave, c: _Clave, valor, gen) -> None:
        if self._releer is None:
            self._revertir(clave, c, SIN_CONFIRMAR)
            return
        c.estado = VERIFICANDO
        self._notificar()
        self._releer(clave, lambda leido: self._conciliar(clave, valor, gen, leido))

    def _conciliar(self, clave, valor, gen, leido) -> None:
        c = self._c(clave)
        if c.estado != VERIFICANDO:
            return
        if leido is not SIN_LECTURA:
            c.confirmado = leido
        if self._sacar_siguiente(clave, c):
            return
        if leido is SIN_LECTURA:
            self._revertir(clave, c, SIN_CONFIRMAR)
        elif leido == valor:
            self._cerrar(clave, c)
            if self._al_confirmar:
                self._al_confirmar(clave)
        else:
            self._revertir(clave, c, _SIN_RESPUESTA)

    def _cerrar(self, clave, c: _Clave) -> None:
        c.estado = None
        c.mostrado = _NADA
        self._tocar(c)
        self._notificar()

    def _revertir(self, clave, c: _Clave, causa) -> None:
        self._cerrar(clave, c)
        if c.confirmado is not _NADA:
            self._al_cambiar(clave, c.confirmado)
        logger.info("Cambio revertido (%s): %s", clave, causa)
        self._al_revertir(clave, causa)

    def _notificar(self) -> None:
        if self._al_pendientes:
            self._al_pendientes()

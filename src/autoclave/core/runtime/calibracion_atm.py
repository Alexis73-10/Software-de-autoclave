# core/runtime/calibracion_atm.py
#
# Calibración automática de la presión atmosférica de referencia (O2f, tanda 6;
# planeacion_opciones.md v4 §5 y planeacion_backend_parametros.md §8).
#
# Ventana CONTINUA de 120 s medida con time.monotonic(), una muestra de
# presión de cámara cada 5 s (24 muestras). Durante toda la ventana se vigilan
# las precondiciones en cada sondeo (no solo en las muestras):
#   - alguna puerta ABIERTA (en doble puerta basta una);
#   - temperatura de cámara (sensor Principal, falla cerrada) < 80 °C;
#   - fuera de CICLO;
#   - datos de la tarjeta vigentes y lecturas válidas de presión y temperatura.
# Si se pierde una precondición, se cancela o el muestreo se atrasa más de un
# periodo: ABORTA, conserva el valor anterior y NO reintenta.
#
# Aceptación (DECISIÓN SIN CONFIRMAR de la instrucción de la tanda 6; son
# constantes del sistema, no parámetros de usuario):
#   - promedio entre 60 y 105 kPa absolutos;
#   - dispersión (máx − mín) <= 1,5 kPa;
#   - si difiere más de 5 kPa del valor anterior, queda POR_CONFIRMAR hasta que
#     un usuario la confirme o la descarte (vence a los 5 min: se descarta).
#
# Nada de esto actúa sobre salidas: solo lee el estado y, al aceptar, escribe
# la presión atmosférica por la función interna del ConfigManager (la API
# nunca puede). La lectura de sobrepresión y el paro siguen en el ControlLoop.
#
# Hilos: la medición corre en un hilo propio (`iniciar`); toda transición pasa
# por self._lock. `aplicar` y `auditar` se llaman FUERA del lock (E/S).

import math
import threading
import time

DURACION_S = 120.0
PERIODO_S = 5.0
MUESTRAS = 24
SONDEO_S = 0.5
TEMP_MAX_C = 80.0
PROMEDIO_MIN_KPA = 60.0
PROMEDIO_MAX_KPA = 105.0
DISPERSION_MAX_KPA = 1.5
DIFERENCIA_CONFIRMAR_KPA = 5.0
PLAZO_CONFIRMACION_S = 300.0

INACTIVA = "inactiva"
MIDIENDO = "midiendo"
POR_CONFIRMAR = "por_confirmar"
OK = "ok"
ABORTADA = "abortada"
RECHAZADA = "rechazada"
APLICANDO = "aplicando"      # escribiendo la referencia: no se cancela
_VIVOS = ("midiendo", "por_confirmar", "aplicando")

# Precondiciones, en el orden en que se muestran
CONDICIONES = ("puerta_abierta", "temp_baja", "fuera_de_ciclo", "lecturas_validas")


def _numero(v) -> float | None:
    if isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def evaluar_condiciones(estado_maquina: str, puertas: dict, temp, pres,
                        datos_vigentes: bool) -> dict:
    """{condición: bool} para la pantalla y la vigilancia. Falla cerrada:
    sin lectura o sin datos vigentes, la condición no se cumple."""
    t, p = _numero(temp), _numero(pres)
    estados = [str(getattr(v, "name", v)) for v in (puertas or {}).values()]
    return {
        "puerta_abierta": "ABIERTO" in estados,
        "temp_baja": datos_vigentes is True and t is not None and t < TEMP_MAX_C,
        "fuera_de_ciclo": bool(estado_maquina) and estado_maquina != "CICLO",
        "lecturas_validas": datos_vigentes is True and t is not None and p is not None,
    }


def primera_fallida(condiciones: dict) -> str:
    for c in CONDICIONES:
        if not condiciones.get(c):
            return c
    return ""


def validar_muestras(muestras: list, anterior) -> tuple[str, str, float, float]:
    """(resultado, motivo, promedio, dispersión). resultado: OK, POR_CONFIRMAR
    o RECHAZADA; motivo: "" o código (fuera_de_rango, inestable)."""
    prom = sum(muestras) / len(muestras)
    disp = max(muestras) - min(muestras)
    if not (PROMEDIO_MIN_KPA <= prom <= PROMEDIO_MAX_KPA):
        return RECHAZADA, "fuera_de_rango", prom, disp
    if disp > DISPERSION_MAX_KPA:
        return RECHAZADA, "inestable", prom, disp
    ant = _numero(anterior)
    # SAF-01: sin valor anterior válido también se pide confirmación
    if ant is None or abs(prom - ant) > DIFERENCIA_CONFIRMAR_KPA:
        return POR_CONFIRMAR, "diferencia_grande", prom, disp
    return OK, "", prom, disp


class CalibracionAtm:
    """Una medición a la vez. `leer()` -> dict con estado_maquina, puertas,
    temp, pres y datos_vigentes. `aplicar(valor, usuario)` escribe la
    referencia (lanza si no puede). `auditar(evento, usuario, rol, anterior,
    nuevo, detalle)`. `anterior()` -> valor vigente."""

    def __init__(self, leer, aplicar, auditar, anterior, reloj=time.monotonic):
        self._leer = leer
        self._aplicar = aplicar
        self._auditar = auditar
        self._anterior = anterior
        self._reloj = reloj
        self._lock = threading.Lock()
        self._despertar = threading.Event()
        self._hilo = None
        self._reiniciar(INACTIVA)

    def _reiniciar(self, estado: str) -> None:
        self._estado = estado
        self._motivo = ""
        self._muestras: list[float] = []
        self._t0 = None
        self._t_fin = None
        self._usuario = ""
        self._rol = ""
        self._promedio = None
        self._dispersion = None
        self._valor_anterior = None
        self._condiciones = {c: False for c in CONDICIONES}

    # ── consulta ──────────────────────────────────────────────────────────
    @property
    def en_curso(self) -> bool:
        with self._lock:
            return self._estado in _VIVOS

    def condiciones_actuales(self) -> dict:
        try:
            l = self._leer()
            return evaluar_condiciones(l.get("estado_maquina", ""), l.get("puertas", {}),
                                       l.get("temp"), l.get("pres"), l.get("datos_vigentes"))
        except Exception:
            return {c: False for c in CONDICIONES}

    def estado(self) -> dict:
        ahora = self._reloj()
        with self._lock:
            transcurrido = 0.0
            if self._estado == MIDIENDO and self._t0 is not None:
                transcurrido = min(DURACION_S, max(0.0, ahora - self._t0))
            elif self._estado != INACTIVA and self._t0 is not None and self._t_fin is not None:
                transcurrido = min(DURACION_S, max(0.0, self._t_fin - self._t0))
            m = list(self._muestras)
            d = {
                "estado": self._estado,
                "motivo": self._motivo,
                "muestras": len(m),
                "muestras_total": MUESTRAS,
                "transcurrido_s": round(transcurrido, 1),
                "duracion_s": DURACION_S,
                "promedio": round(sum(m) / len(m), 2) if m else None,
                "dispersion": round(max(m) - min(m), 2) if m else None,
                "valor_anterior": self._valor_anterior,
                "usuario": self._usuario,
                "condiciones": dict(self._condiciones),
            }
        if d["estado"] != MIDIENDO:
            d["condiciones"] = self.condiciones_actuales()
        d["criterios"] = {"promedio_min": PROMEDIO_MIN_KPA, "promedio_max": PROMEDIO_MAX_KPA,
                          "dispersion_max": DISPERSION_MAX_KPA,
                          "diferencia_confirmar": DIFERENCIA_CONFIRMAR_KPA,
                          "temp_max": TEMP_MAX_C}
        return d

    # ── órdenes ───────────────────────────────────────────────────────────
    def iniciar(self, usuario: str, rol: str = "", hilo: bool = True) -> tuple[bool, str]:
        """(True, "") o (False, código): en_curso o la condición que falta."""
        cond = self.condiciones_actuales()
        falta = primera_fallida(cond)
        with self._lock:
            if self._estado in _VIVOS:
                return False, "en_curso"
            if falta:
                return False, falta
            self._reiniciar(MIDIENDO)
            self._usuario, self._rol = usuario, rol
            self._t0 = self._reloj()
            self._condiciones = cond
            try:
                self._valor_anterior = _numero(self._anterior())
            except Exception:
                self._valor_anterior = None
            self._despertar.clear()
        if hilo:
            self._hilo = threading.Thread(target=self._bucle, name="calibracion_atm", daemon=True)
            self._hilo.start()
        return True, ""

    def cancelar(self, usuario: str = "", rol: str = "") -> bool:
        with self._lock:
            estado = self._estado
        if estado == POR_CONFIRMAR:
            return self.descartar(usuario, rol)
        if estado != MIDIENDO:
            return False
        return self._terminar(ABORTADA, "cancelada", usuario, rol, solo_de=(MIDIENDO,))

    def confirmar(self, usuario: str, rol: str = "") -> tuple[bool, str]:
        with self._lock:
            if self._estado != POR_CONFIRMAR:
                return False, "sin_pendiente"
            valor = self._promedio
        # SAF-03: al confirmar se revalidan las precondiciones
        falta = primera_fallida(self.condiciones_actuales())
        if falta:
            return False, falta
        return self._aceptar(valor, usuario, rol)

    def descartar(self, usuario: str, rol: str = "") -> bool:
        return self._terminar(RECHAZADA, "descartada", usuario, rol, solo_de=(POR_CONFIRMAR,))

    # ── medición ──────────────────────────────────────────────────────────
    def _bucle(self) -> None:
        while True:
            try:
                seguir = self.paso()
            except Exception:
                self._terminar(ABORTADA, "error_interno", solo_de=(MIDIENDO, POR_CONFIRMAR))
                return
            if not seguir:
                return
            self._despertar.wait(SONDEO_S)

    def paso(self) -> bool:
        """Un sondeo. Devuelve False cuando ya no queda nada por medir."""
        with self._lock:
            estado = self._estado
        if estado == POR_CONFIRMAR:
            with self._lock:
                vencida = self._t_fin is not None and self._reloj() - self._t_fin > PLAZO_CONFIRMACION_S
            if vencida:
                # TMG-01: nunca desde APLICANDO (solo _aceptar sale de ahí)
                self._terminar(RECHAZADA, "confirmacion_vencida", solo_de=(POR_CONFIRMAR,))
                return False
            return True
        if estado != MIDIENDO:
            return False
        try:
            l = self._leer()
        except Exception:
            l = {}
        cond = evaluar_condiciones(l.get("estado_maquina", ""), l.get("puertas", {}),
                                   l.get("temp"), l.get("pres"), l.get("datos_vigentes"))
        ahora = self._reloj()
        falta = primera_fallida(cond)
        with self._lock:
            if self._estado != MIDIENDO:
                return False
            self._condiciones = cond
            if not falta:
                proxima = self._t0 + PERIODO_S * (len(self._muestras) + 1)
                if ahora - proxima > PERIODO_S:
                    falta = "muestreo_irregular"       # ventana no continua
                elif ahora >= proxima:
                    self._muestras.append(float(l["pres"]))
            completa = len(self._muestras) >= MUESTRAS
            muestras = list(self._muestras)
        if falta:
            self._terminar(ABORTADA, falta)
            return False
        if not completa:
            return True
        resultado, motivo, prom, disp = validar_muestras(muestras, self._valor_anterior)
        with self._lock:
            self._promedio, self._dispersion = prom, disp
            self._t_fin = self._reloj()
        if resultado == RECHAZADA:
            self._terminar(RECHAZADA, motivo)
            return False
        if resultado == POR_CONFIRMAR:
            with self._lock:
                if self._estado != MIDIENDO:
                    return False
                self._estado, self._motivo = POR_CONFIRMAR, motivo
            return True
        self._aceptar(prom, self._usuario, self._rol)
        return False

    def _aceptar(self, valor: float, usuario: str, rol: str) -> tuple[bool, str]:
        with self._lock:
            if self._estado not in (MIDIENDO, POR_CONFIRMAR):
                return False, "sin_pendiente"
            self._estado = APLICANDO
        try:
            self._aplicar(round(valor, 2), usuario)
        except Exception as e:
            codigo = getattr(e, "codigo", "") or "no_aplicada"
            self._terminar(RECHAZADA, codigo, usuario, rol, solo_de=(APLICANDO,))
            return False, codigo
        self._terminar(OK, "", usuario, rol, solo_de=(APLICANDO,))
        return True, ""

    def _terminar(self, estado: str, motivo: str, usuario: str = "", rol: str = "",
                  solo_de: tuple = _VIVOS) -> bool:
        with self._lock:
            if self._estado not in solo_de:
                return False
            self._estado, self._motivo = estado, motivo
            if self._t_fin is None:
                self._t_fin = self._reloj()
            m = list(self._muestras)
            detalle = {"motivo": motivo, "muestras": len(m),
                       "promedio": round(self._promedio if self._promedio is not None
                                         else (sum(m) / len(m) if m else 0.0), 3) if m else None,
                       "dispersion": round(max(m) - min(m), 3) if m else None,
                       "iniciada_por": self._usuario,
                       "valor_intentado": round(self._promedio, 3) if self._promedio is not None else None}
            anterior = self._valor_anterior
            quien, quien_rol = usuario or self._usuario, rol or self._rol
            nuevo = round(self._promedio, 2) if estado == OK and self._promedio is not None else None
        self._despertar.set()
        evento = {OK: "calibracion_atm_ok", ABORTADA: "calibracion_atm_abortada",
                  RECHAZADA: "calibracion_atm_rechazada"}[estado]
        try:
            self._auditar(evento, quien, quien_rol, anterior, nuevo, detalle)
        except Exception:
            pass
        return True

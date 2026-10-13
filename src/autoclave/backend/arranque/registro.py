# autoclave/backend/arranque/registro.py
#
# Registro de las etapas de arranque que publica GET /arranque
# (planeacion_barra_arranque_real.md §5 y §7). Lo escribe el hilo de arranque
# y lo leen los hilos de petición: todo pasa por un Lock.
#
# Monotonía (B-03): ok, degradado y fallo son finales; una etapa reintentable
# reintenta dentro de en_curso. Una transición inválida es un error de
# programación (ValueError), no una condición de campo.

import copy
import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class EstadoEtapa(str, Enum):
    OK = "ok"
    EN_CURSO = "en_curso"
    PENDIENTE = "pendiente"
    DEGRADADO = "degradado"
    FALLO = "fallo"


_FINALES = frozenset({EstadoEtapa.OK, EstadoEtapa.DEGRADADO, EstadoEtapa.FALLO})
_COMPLETADAS = frozenset({EstadoEtapa.OK, EstadoEtapa.DEGRADADO})

ORIGEN_LANZADOR = "lanzador"
ORIGEN_BACKEND = "backend"
ORIGEN_UI = "ui"

# (clave de texto, peso, origen) — §7 de planeacion_barra_arranque_real.md.
# Pesos PROVISIONALES (D-D): se calibran con tiempos medidos en el PC industrial.
ETAPAS_ARRANQUE = (
    ("verificando_instalacion", 1.0, ORIGEN_LANZADOR),
    ("liberando_procesos",      1.0, ORIGEN_LANZADOR),
    ("iniciando_servicios",     2.0, ORIGEN_BACKEND),
    ("cargando_configuracion",  1.0, ORIGEN_BACKEND),
    ("verificando_calibracion", 1.0, ORIGEN_BACKEND),
    ("abriendo_base_datos",     1.0, ORIGEN_BACKEND),
    ("conectando_modulos_es",   2.0, ORIGEN_BACKEND),
    ("verificando_sensores",    2.0, ORIGEN_BACKEND),
    ("preparando_interfaz",     1.0, ORIGEN_UI),        # la completa cada UI
)


@dataclass
class Etapa:
    clave: str
    peso: float
    origen: str
    estado: EstadoEtapa = EstadoEtapa.PENDIENTE
    codigo: str | None = None
    t_inicio: float | None = None   # time.monotonic(); solo para el log (medir pesos)
    t_fin: float | None = None


class RegistroArranque:
    def __init__(self, etapas=ETAPAS_ARRANQUE, reloj=time.monotonic):
        self._lock = threading.Lock()
        self._reloj = reloj
        self._etapas = [Etapa(clave, float(peso), origen) for clave, peso, origen in etapas]
        self._por_clave = {e.clave: e for e in self._etapas}
        if len(self._por_clave) != len(self._etapas):
            raise ValueError("Claves de etapa repetidas")

    # ── transiciones ─────────────────────────────────────────────────────────

    def _etapa(self, clave: str) -> Etapa:
        try:
            return self._por_clave[clave]
        except KeyError:
            raise ValueError(f"Etapa de arranque desconocida: {clave}") from None

    def _exigir(self, etapa: Etapa, permitidos, accion: str) -> None:
        if etapa.estado not in permitidos:
            raise ValueError(f"Etapa {etapa.clave}: no se puede {accion} desde {etapa.estado.value}")

    def iniciar(self, clave: str) -> None:
        with self._lock:
            e = self._etapa(clave)
            self._exigir(e, {EstadoEtapa.PENDIENTE}, "iniciar")
            e.estado = EstadoEtapa.EN_CURSO
            e.t_inicio = self._reloj()
        logger.info("Arranque: %s en curso", clave)

    def _cerrar(self, clave: str, estado: EstadoEtapa, codigo: str | None,
                permitidos=frozenset({EstadoEtapa.EN_CURSO})) -> None:
        with self._lock:
            e = self._etapa(clave)
            self._exigir(e, permitidos, estado.value)
            e.estado = estado
            e.codigo = codigo
            e.t_fin = self._reloj()
            duracion = e.t_fin - e.t_inicio if e.t_inicio is not None else 0.0
        nivel = logging.ERROR if estado == EstadoEtapa.FALLO else (
            logging.WARNING if estado == EstadoEtapa.DEGRADADO else logging.INFO)
        logger.log(nivel, "Arranque: %s %s%s (%.2f s)", clave, estado.value,
                   f" [{codigo}]" if codigo else "", duracion)

    def completar(self, clave: str) -> None:
        self._cerrar(clave, EstadoEtapa.OK, None)

    def degradar(self, clave: str, codigo: str) -> None:
        self._cerrar(clave, EstadoEtapa.DEGRADADO, codigo)

    def fallar(self, clave: str, codigo: str) -> None:
        self._cerrar(clave, EstadoEtapa.FALLO, codigo,
                     permitidos=frozenset({EstadoEtapa.EN_CURSO, EstadoEtapa.PENDIENTE}))

    def anotar(self, clave: str, codigo: str | None) -> None:
        """Código sobre una etapa en curso que sigue reintentando (p. ej. ARR_SIN_ES)."""
        with self._lock:
            e = self._etapa(clave)
            self._exigir(e, {EstadoEtapa.EN_CURSO}, "anotar")
            if e.codigo == codigo:
                return
            e.codigo = codigo
        logger.warning("Arranque: %s sigue en curso [%s]", clave, codigo)

    # ── lectura ──────────────────────────────────────────────────────────────

    def _fallo_bloqueante(self) -> bool:
        return any(e.estado == EstadoEtapa.FALLO for e in self._etapas)

    def _terminado(self) -> bool:
        return all(e.estado in _COMPLETADAS for e in self._etapas if e.origen != ORIGEN_UI)

    def _etapa_actual(self) -> str | None:
        for e in self._etapas:
            if e.estado == EstadoEtapa.FALLO:
                return e.clave
        if self._terminado():
            return None
        for e in self._etapas:
            if e.estado == EstadoEtapa.EN_CURSO:
                return e.clave
        for e in self._etapas:
            if e.estado == EstadoEtapa.PENDIENTE and e.origen != ORIGEN_UI:
                return e.clave
        return None

    @property
    def fallo_bloqueante(self) -> bool:
        with self._lock:
            return self._fallo_bloqueante()

    @property
    def terminado(self) -> bool:
        with self._lock:
            return self._terminado()

    @property
    def etapa_actual(self) -> str | None:
        with self._lock:
            return self._etapa_actual()

    def estado_de(self, clave: str) -> EstadoEtapa:
        with self._lock:
            return self._etapa(clave).estado

    def instantanea(self) -> dict:
        """Contrato de GET /arranque (§5). Copia independiente del registro."""
        with self._lock:
            return copy.deepcopy({
                "terminado": self._terminado(),
                "falloBloqueante": self._fallo_bloqueante(),
                "etapaActual": self._etapa_actual(),
                "etapas": [
                    {"clave": e.clave, "estado": e.estado.value, "codigo": e.codigo, "peso": e.peso}
                    for e in self._etapas
                ],
            })

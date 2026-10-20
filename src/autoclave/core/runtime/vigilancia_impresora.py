# core/runtime/vigilancia_impresora.py
#
# Aviso de impresora desconectada (B5, tanda 4). Solo informa:
#
# - La bandera `habilitada` (data/impresora.json) dice si el equipo usa
#   impresora. Por defecto True (se conserva el comportamiento de siempre: el
#   equipo imprime). Hoy NO existe un modo "deshabilitada" de la impresión
#   misma: la bandera solo gobierna la verificación de arranque y el aviso.
# - Al arrancar (con el backend ya operable) se consulta la impresora en un
#   hilo con plazo máximo de `plazo_s` (5 s). Si responde "desconectada" se
#   activa el aviso IMPRESORA_DESCONECTADA (SIS-05, AVISO, no bloquea nada). Si
#   no responde a tiempo, falla o es "desconocida", NO hay aviso.
# - El aviso se limpia solo cuando una impresión tiene éxito
#   (win32_printer.registrar_observador_exito) Y una consulta nueva confirma la
#   impresora conectada (Windows acepta un trabajo RAW en la cola aunque la
#   impresora esté desconectada: TMG-03/SAF-05 de la revisión), o al reiniciar
#   con la impresora presente (la alarma vive en memoria).
# - Nada de esto toca el ControlLoop: ni el inicio ni el cierre de un ciclo
#   dependen de la impresora (una impresión fallida ya degrada sin bloquear).

import json
import logging
import threading
import time
from pathlib import Path

from autoclave.devices.printer import win32_printer
from autoclave.state_machine.alarms.catalogo import IMPRESORA_DESCONECTADA
from autoclave.utils.archivos import escribir_texto_atomico

logger = logging.getLogger(__name__)

PLAZO_CONSULTA_S = 5.0


class ConfigImpresora:
    """data/impresora.json = {"habilitada": bool}. Ausente, ilegible o
    inválido → habilitada (el comportamiento actual)."""

    def __init__(self, ruta: Path):
        self._ruta = Path(ruta)
        self._lock = threading.Lock()

    def habilitada(self) -> bool:
        try:
            valor = json.loads(self._ruta.read_text(encoding="utf-8")).get("habilitada")
        except FileNotFoundError:
            return True
        except Exception:
            logger.exception("%s ilegible: la impresora se considera habilitada", self._ruta)
            return True
        return valor if isinstance(valor, bool) else True

    def guardar(self, habilitada) -> bool:
        if not isinstance(habilitada, bool):
            raise ValueError("habilitada debe ser booleano")
        with self._lock:
            escribir_texto_atomico(self._ruta, json.dumps({"habilitada": habilitada}))
        return habilitada


class VigilanciaImpresora:

    def __init__(self, config: ConfigImpresora, alarm_manager,
                 consultar=win32_printer.conexion_impresora, plazo_s: float = PLAZO_CONSULTA_S,
                 reloj=time.monotonic):
        self._config = config
        self._alarmas = alarm_manager
        self._consultar = consultar
        self._plazo_s = plazo_s
        self._reloj = reloj
        self._ultimo_exito: float | None = None   # reloj() de la última impresión confirmada
        self._verificando = False                 # hay una verificación en curso
        self._lock = threading.Lock()
        win32_printer.registrar_observador_exito(self.impresion_exitosa)

    @property
    def aviso_activo(self) -> bool:
        """Estado real del aviso en el AlarmManager (TMG-09: sin copia propia
        que se pueda desincronizar)."""
        if self._alarmas is None:
            return False
        inst = self._alarmas.obtener(IMPRESORA_DESCONECTADA)
        return inst is not None and getattr(getattr(inst, "estado", None), "name", "") == "ACTIVA"

    def iniciar(self) -> threading.Thread:
        """Lanza la verificación en un hilo y vuelve de inmediato."""
        hilo = threading.Thread(target=self.verificar, name="VerificacionImpresora", daemon=True)
        hilo.start()
        return hilo

    def verificar(self) -> str | None:
        """Consulta con plazo y activa el aviso si está desconectada. Devuelve
        el resultado de la consulta o None si no se consultó / no respondió.
        Nunca lanza."""
        try:
            if not self._config.habilitada():
                return None
            inicio = self._reloj()
            self._verificando = True
            resultado = []

            def consultar():
                try:
                    resultado.append(self._consultar())
                except Exception:
                    logger.exception("Consulta de la impresora")
                    resultado.append(win32_printer.DESCONOCIDA)

            consulta = threading.Thread(target=consultar, name="ConsultaImpresora", daemon=True)
            consulta.start()
            consulta.join(self._plazo_s)
            if not resultado:
                logger.warning("Impresora: sin respuesta en %.1f s; no se avisa", self._plazo_s)
                return None
            if resultado[0] == win32_printer.DESCONECTADA:
                self._activar(inicio)
            return resultado[0]
        except Exception:
            logger.exception("Verificación de la impresora")
            return None
        finally:
            self._verificando = False

    def _activar(self, inicio_consulta: float) -> None:
        with self._lock:
            if self._alarmas is None:
                return
            # TMG-09: una impresión confirmada llegada durante la consulta manda
            if self._ultimo_exito is not None and self._ultimo_exito >= inicio_consulta:
                return
            self._alarmas.activar(IMPRESORA_DESCONECTADA)   # idempotente

    def impresion_exitosa(self) -> None:
        """Una impresión salió del programa sin error. Solo cuenta si una
        consulta nueva confirma la impresora conectada. Corre en el hilo que
        imprimió; nunca lanza (el observador está protegido en win32_printer)."""
        if not self.aviso_activo and not self._verificando:
            return                        # nada que limpiar ni que adelantar
        if self._consultar() != win32_printer.CONECTADA:
            return
        with self._lock:
            self._ultimo_exito = self._reloj()
            if self._alarmas is not None:
                self._alarmas.resolver(IMPRESORA_DESCONECTADA)

# autoclave/services/ui/ui_service_backend.py

import threading
import logging

logger = logging.getLogger(__name__)


class UIServiceBackend:
    """
    Servicio de UI que mantiene un cache del estado del backend.
    Las peticiones HTTP se hacen en un hilo de fondo para no bloquear
    el hilo principal de Tkinter.
    """

    def __init__(self, backend_client, interval: float = 0.5):
        self.backend   = backend_client
        self._interval = interval          # antes nunca se asignaba → hasattr siempre False
        self._lock     = threading.Lock()
        self._cache    = {}
        self._config   = {}
        self._cycle    = {}
        self.connected = False

        # Hilo de actualización en segundo plano
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    # ==============================
    # HILO DE FONDO
    # ==============================

    def _loop(self):
        while not self._stop.is_set():
            self._fetch()
            self._stop.wait(self._interval if hasattr(self, "_interval") else 0.5)

    def _fetch(self):
        try:
            cache  = self.backend.get_status()
            config = self.backend.get_config()
            cycle  = self.backend.get_cycle()
            with self._lock:
                self._cache  = cache
                self._config = config
                self._cycle  = cycle
                self.connected = True
        except Exception as e:
            with self._lock:
                self.connected = False
            logger.warning("⚠️ Backend no disponible: %s", e)

    def update(self):
        """Compatibilidad: el hilo de fondo ya actualiza el cache."""
        pass

    def stop(self):
        """Detiene el hilo de fondo. Llamar al cerrar la aplicación."""
        self._stop.set()

    # ==============================
    # LECTURA THREAD-SAFE DEL CACHE
    # ==============================

    def _snapshot(self):
        with self._lock:
            return self._cache, self._config, self._cycle, self.connected

    # ==============================
    # SENSORES
    # ==============================

    def get_sensores_temp(self):
        with self._lock:
            temp = self._cache.get("sensors", {}).get("temperature", {})
        return {
            "temp_camara":  temp.get("camara"),
            "temp_ref":     temp.get("ref"),
            "temp_chaqueta":temp.get("chaqueta"),
        }

    def get_sensores_pres(self):
        with self._lock:
            pres = self._cache.get("sensors", {}).get("pressure", {})
        return {
            "pres_camara":  pres.get("camara"),
            "pres_chaqueta":pres.get("chaqueta"),
        }

    def get_sensores_di(self):
        with self._lock:
            return self._cache.get("sensors", {}).get("digital_inputs", {})

    # ==============================
    # ALARMAS
    # ==============================

    def get_alarmas(self):
        with self._lock:
            return list(self._cache.get("alarms", []))

    # ==============================
    # ESTADO GLOBAL
    # ==============================

    def get_estado_global(self):
        with self._lock:
            return self._cache.get("machine_state", "DESCONOCIDO")

    # ==============================
    # PUERTAS
    # ==============================

    def get_estado_puertas(self):
        with self._lock:
            return dict(self._cache.get("doors", {}))

    def get_estado_puerta(self, nombre_puerta):
        with self._lock:
            return self._cache.get("doors", {}).get(nombre_puerta)

    def get_estado_flag(self, flag):
        with self._lock:
            return self._cache.get("sensors", {}).get("flags", {}).get(flag)

    # ==============================
    # CONFIGURACION
    # ==============================

    def get_config(self):
        with self._lock:
            return dict(self._config)

    def get_config_param(self, name):
        with self._lock:
            return self._config.get(name)

    # ==============================
    # CICLO ACTUAL
    # ==============================

    def get_cycle(self):
        with self._lock:
            return dict(self._cycle)

    def get_cycle_param(self, param):
        with self._lock:
            return self._cycle.get(param)

    # ==============================
    # FASE CICLO
    # ==============================

    def get_fase_ciclo(self) -> str:
        """Retorna la fase activa del ciclo ('PRECALENTAMIENTO', 'ESTERILIZACION', etc.)."""
        with self._lock:
            return self._cache.get("fase_ciclo", "")

    # ==============================
    # SENSORES EXTENDIDOS
    # ==============================

    def get_temp_camara_2(self):
        """Retorna la temperatura del segundo sensor de cámara."""
        with self._lock:
            return self._cache.get("sensors", {}).get("temperature", {}).get("camara_2")

    # ==============================
    # LECTURAS EN VIVO (gráfica)
    # ==============================

    def get_current_cycle_readings(self) -> dict:
        """
        Llama al endpoint /cycle/current/readings y retorna el dict
        con ciclo_id + lista de lecturas.
        Devuelve {} si falla.
        """
        try:
            return self.backend.get(path="/cycle/current/readings")
        except Exception as e:
            logger.debug("get_current_cycle_readings: %s", e)
            return {}

    # ==============================
    # ACCIONES DE CICLO
    # ==============================

    def start_cycle(self) -> bool:
        """Envía POST /cycle/start. Retorna True si tuvo éxito."""
        try:
            self.backend.post(path="/cycle/start")
            return True
        except Exception as e:
            logger.warning("start_cycle error: %s", e)
            return False

    def abort_cycle(self) -> bool:
        """Envía POST /cycle/abort. Retorna True si tuvo éxito."""
        try:
            self.backend.post(path="/cycle/abort")
            return True
        except Exception as e:
            logger.warning("abort_cycle error: %s", e)
            return False

# autoclave/services/ui/ui_service_backend.py

from unicodedata import name


class UIServiceBackend:
    def __init__(self, backend_client):
        self.backend = backend_client
        self._cache = {}
        self._config = {}
        self._cycle = {}

    def update(self):
        self._cache = self.backend.get_status()

        self._config = self.backend.get_config()
        
        self._cycle = self.backend.get_cycle()

    # ==============================
    # SENSORES
    # ============================== 

    def get_sensores_temp(self):
        temp = self._cache.get("sensors", {}).get("temperature", {})
        return {
            "temp_camara": temp.get("camara"),
            "temp_ref": temp.get("ref"),
            "temp_chaqueta": temp.get("chaqueta"),
        }

    def get_sensores_pres(self):
        pres = self._cache.get("sensors", {}).get("pressure", {})
        return {
            "pres_camara": pres.get("camara"),
            "pres_chaqueta": pres.get("chaqueta"),
        }

    def get_sensores_di(self):
        return self._cache.get("sensors", {}).get("digital_inputs", {})

    # ==============================
    # ALARMAS
    # ==============================

    def get_alarmas(self):
        return self._cache.get("alarms", [])

    # ==============================
    # ESTADO GLOBAL
    # ==============================

    def get_estado_global(self):
        return self._cache.get("machine_state", "DESCONOCIDO")

    # ==============================
    # PUERTAS
    # ==============================

    def get_estado_puertas(self):
        return self._cache.get("doors", {})

    def get_estado_puerta(self, nombre_puerta):
        return self._cache.get("doors", {}).get(nombre_puerta)

    def get_estado_flag (self, flag):
        return self._cache.get("flags", {}).get(flag)
    
    #===============================
    # CONFIGURACION
    #===============================
    def get_config(self):
        return self._config
    
    def get_config_param(self, name):
        return self._config.get(name)
    #===============================
    # CICLO ACTUAL
    #===============================
    def get_cycle(self):
        return self._cycle

    def get_cycle_param(self, param):
        return self._cycle.get(param)
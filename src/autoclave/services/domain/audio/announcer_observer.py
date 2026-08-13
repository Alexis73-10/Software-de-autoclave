# src/autoclave/services/domain/audio/announcer_observer.py
from autoclave.devices.puertas.advanced_door import DoorState
from autoclave.state_machine.machine.enum_global import GlobalState

_ALARMA_A_EVENTO = {
    "PARO_EMERGENCIA": "emg_paro_emergencia",
    "FALLO_SUMINISTRO_ELECTRICO": "emg_fallo_electrico",
    "SENSOR_AUSENTE": "emg_sensor_ausente",
    "SUMINISTRO_AGUA_BOMBA": "alr_sum_agua_bomba",
    "SUMINISTRO_AGUA_GENERADOR": "alr_sum_agua_generador",
    "SUMINISTRO_AIRE_COMPRIMIDO": "alr_sum_aire_comprimido",
    "SUMINISTRO_ELECTRICO": "alr_sum_electrico",
    "ERROR_AI_PRES_CAMARA": "alr_ai_pres_camara",
    "ERROR_AI_PRES_CHAQUETA": "alr_ai_pres_chaqueta",
    "ERROR_AI_PRES_EMPAQUE_1": "alr_ai_pres_empaque_1",
    "ERROR_AI_PRES_EMPAQUE_2": "alr_ai_pres_empaque_2",
    "ERROR_AI_TEMP_CAMARA": "alr_ai_temp_camara",
    "ERROR_AI_TEMP_2_CAMARA": "alr_ai_temp_2_camara",
    "ERROR_AI_TEMP_REF": "alr_ai_temp_ref",
    "ERROR_AI_TEMP_CHAQUETA": "alr_ai_temp_chaqueta",
    "ERROR_AI_TEMP_DRENAJE_CAM": "alr_ai_temp_drenaje_cam",
    "ERROR_AI_TEMP_DRENAJE": "alr_ai_temp_drenaje",
}

_PUERTA_A_SUFIJO = {"Puerta 1": "1", "Puerta 2": "2"}
_ESTADOS_TERMINALES_PUERTA = {DoorState.ABIERTO: "abierta", DoorState.CERRADO: "cerrada"}


class AnnouncerObserver:
    def __init__(self, announcer):
        self._announcer = announcer
        self._alarmas_vistas = None
        self._puertas_previas = None
        self._machine_state_previo = None
        self._camara_segura_previo = None

    def update(self, estado) -> None:
        if self._alarmas_vistas is None:
            self._sembrar(estado)
            return

        self._detectar_alarmas(estado)
        self._detectar_puertas(estado)
        self._detectar_maquina(estado)
        self._detectar_camara_segura(estado)

    def _sembrar(self, estado) -> None:
        self._alarmas_vistas = {a.id for a in estado.Alarmas_activas}
        self._puertas_previas = dict(estado.estado_puertas)
        self._machine_state_previo = estado.get_machine_state()
        self._camara_segura_previo = bool(getattr(estado, "camara_segura_confirmada", False))

    def _detectar_alarmas(self, estado) -> None:
        activas = {a.id for a in estado.Alarmas_activas}
        for alarm_id in activas - self._alarmas_vistas:
            event_id = _ALARMA_A_EVENTO.get(alarm_id)
            if event_id:
                self._announcer.say(event_id)
        self._alarmas_vistas = activas

    def _detectar_puertas(self, estado) -> None:
        for puerta, sufijo in _PUERTA_A_SUFIJO.items():
            if puerta not in estado.estado_puertas:
                continue
            actual = estado.estado_puertas.get(puerta)
            previo = self._puertas_previas.get(puerta)
            if actual != previo:
                if actual == DoorState.ATRAPADA:
                    self._announcer.say(f"emg_puerta_{sufijo}_atrapada")
                elif actual == DoorState.ERROR:
                    self._announcer.say(f"fal_puerta_{sufijo}_error")
                elif actual in _ESTADOS_TERMINALES_PUERTA:
                    self._announcer.say(f"pta_{sufijo}_{_ESTADOS_TERMINALES_PUERTA[actual]}")
            self._puertas_previas[puerta] = actual

    def _detectar_maquina(self, estado) -> None:
        actual = estado.get_machine_state()
        previo = self._machine_state_previo
        if actual != previo:
            if actual == GlobalState.CICLO:
                self._announcer.say("cic_iniciado")
            elif actual == GlobalState.PREPARADO:
                self._announcer.say("equipo_preparado")
                if previo == GlobalState.CICLO and estado.fase_ciclo == "COMPLETADO":
                    self._announcer.say("cic_completado")
            elif actual == GlobalState.FALLA and previo == GlobalState.CICLO:
                self._announcer.say("fal_ciclo_abortado")
        self._machine_state_previo = actual

    def _detectar_camara_segura(self, estado) -> None:
        actual = bool(getattr(estado, "camara_segura_confirmada", False))
        if actual and not self._camara_segura_previo:
            self._announcer.say("fal_camara_segura")
        self._camara_segura_previo = actual

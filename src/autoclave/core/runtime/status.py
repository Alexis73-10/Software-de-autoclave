#este archivo sera un cofre sonde se almacenaran los estados tanto de sensores como del sistema en general
#estos estados seran accedidos por los diferentes modulos del sistema para su funcionamiento
#estos estados podran ser actualizados por el modulo control loop

#Actualizacion : 
    #se agregaran los estados de las (DI) entradas digitales
from autoclave.devices.puertas.advanced_door import DoorState
from autoclave.state_machine.machine.enum_global import GlobalState


class EstadoAutoclave:
    # El índice es la posición de la lectura en la trama de la tarjeta. La
    # posición 3 (temp_chaqueta) ya no se lee: ese sensor se retiró de todos
    # los equipos (planeacion_backend_autenticacion.md, decisión 24, T-19).
    # Los demás conservan su posición.
    # temp_drenaje_cam (posición 4) era de una versión anterior y ya no existe:
    # su entrada la ocupa ahora temp_drenaje, y la posición 5 queda sin sensor
    # (decisión de Cristian, adenda E0/E1, 2026-10-12).
    map_temp = {
        "temp_camara": 0,
        "temp_2_camara": 1,
        "temp_ref": 2,
        "temp_drenaje": 4,
    }

    map_pres = {
        "pres_camara": 0,
        "pres_chaqueta": 1,
        "pres_empaque_1": 2,
        "pres_empaque_2": 3,
    }
    
    map_di = {
        "aire_comprimido": 0,
        "presion_agua": 1,
        "puerta_1_cerrada": 2,
        "puerta_1_abierta": 3,
        "puerta_2_cerrada": 4,
        "puerta_2_abierta": 5,
        "atrapamiento_puerta_1": 6,
        "atrapamiento_puerta_2": 7,
        "agua_bomba": 8, 
        "agua_generador": 9,
        "paro_emergencia": 10,
        "agua_camara": 11,
        "vapor_suministro": 12,
        "suministro_electrico": 13,
    }
    
    map_do = {
        "vapor_generador": 0,
        "vapor_caldera": 1,
        "vapor_chaqueta": 2,
        "vapor_camara": 3,
        "descompresion_rapida": 4,
        "descompresion_lenta": 5,
        "descompresion_chaqueta": 6,
        "vacio_camara": 7,
        "desbloqueo_puerta_1": 8,
        "desbloqueo_puerta_2": 9,
        "bloqueo_puerta_1": 10,
        "bloqueo_puerta_2": 11,
        # 12 (DO 13): libre. Era aire_comprimido_chaqueta, retirada en la
        # tanda 11 (D11-2); las demás conservan su número.
        "aire_comprimido_camara": 13,
        "aire_admosferico_camara": 14,
        "agua_chaqueta": 15,
        "agua_intercambiador": 16,
        "agua_bomba": 17,
        "bomba_vacio": 18,
        "abrir_puerta_1": 19,
        "abrir_puerta_2": 20,
        "cerrar_puerta_1": 21,
        "cerrar_puerta_2": 22,
        "buzer_alarma": 23,
    }
    
    state_doors = {
        "Puerta 1": 0,
        "Puerta 2": 1,
    }
    
    state_maquina = {
        "Estado":0,
    }
    
    _flags_map = {
        "LISTO_PARA_CICLO":             0,
        "START_CICLO":                  1,
        "FALLO_GENERAL":                2,
        "PARO_EMERGENCIA":              3,
        "CICLO_CANCELADO":              4,
        "CICLO_CONFIRMADO":             5,   # operador confirmó la visualización del resultado
        "RESET_FALLA":                  6,   # operador solicitó salir del estado FALLA
        "FALLO_SUMINISTRO_ELECTRICO":   7,
        # U4 (tanda 2): paro de verdad (enlace + DI vigente + entrada en 0).
        # PARO_EMERGENCIA también es True sin datos de la tarjeta (A-3).
        "PARO_REAL":                    8,
    }

    def __init__(self):
        self.data = {}
        self.sensores_temp = {k: None for k in self.map_temp}
        self.sensores_pres = {k: None for k in self.map_pres}
        self.sensores_di = {k: 0 for k in self.map_di}
        self.salidas_do = {k: 0 for k in self.map_do}
        self.estado_puertas = {k: DoorState.DESCONOCIDO for k in self.state_doors}
        self.estado_maquina = {k: GlobalState.PREPARACION for k in self.state_maquina}
        self.flags = {k: False for k in self._flags_map}
        # Fase actual del ciclo (string legible para la UI)
        self.fase_ciclo: str = ""
        # Motivo específico del último fallo de ciclo (para tickets/DB);
        # se limpia al iniciar cada ciclo nuevo
        self.motivo_fallo: str = ""
        self.codigo_fallo: str = ""
        # I4 (tanda 6): parámetros de la alarma del fallo (JSON en la BD)
        self.valores_fallo: dict = {}
        # True cuando la fase activa ya alcanzó las condiciones y está en sostenimiento
        self.fase_en_sostenimiento: bool = False
        # Progreso del pre-vacío: "A 1/4", "B 2/4", etc. (vacío cuando no aplica)
        self.prevacio_progreso: str = ""
        # Paso interno de la fase activa (p.ej. pasos de PRE_VACIO). Cuando cambia,
        # el CycleLogger imprime una línea de referencia aunque no se haya cumplido
        # el intervalo periódico de impresión. Vacío cuando la fase no lo usa.
        self.sub_estado_ciclo: str = ""
        # Letalidad acumulada (F0, min equivalentes a 121.1°C) durante
        # CALENTAMIENTO/ESTABILIZACION/ESTERILIZACION; se limpia al iniciar
        # cada ciclo nuevo (CicloState.reset())
        self.f0_acumulado: float = 0.0
        # O1 (tanda 3): usuario autenticado que pidió el inicio (POST /cycle/start).
        # Lo fija el backend junto con START_CICLO y lo toma el CycleLogger al
        # crear el ciclo. "" = sin sesión.
        self.operador_inicio: str = ""
        # Avisos del ciclo que van al pie del ticket (SAF-04 de T3)
        self.avisos_ciclo: list = []
        # T2-a (tanda 7): segundos del ciclo sin datos de la tarjeta (tolerancia
        # por DI vencida); pausan la exposición y van al pie del ticket
        self.sin_datos_tarjeta_s: float = 0.0
        # D8-2.9 (tanda 8): True si en el tick actual llegó una trama DI
        # vigente, distinta y nueva (lo publica ControlLoop antes de correr la
        # máquina de estados); None = sin información (se cuenta cada tick)
        self.trama_di_nueva = None
        # TMG-01 (revisión S2a): instante (time.monotonic) de la última trama
        # DI vigente; el tramo sin datos del ciclo empieza ahí. None = sin dato
        self.ultima_di_valida_mono = None
        # F4 (tanda 16), contratos del ciclo (los escribe CicloState):
        # - aislamiento_camara: AislamientoCamara del ciclo en curso (VCH-AIS),
        #   una instancia por ciclo, compartida por CALENTAMIENTO y ESTERILIZACION;
        # - inhibir_vapor_chaqueta: corte de chaqueta (D-CHQ / SAF-09) vigente en
        #   el tick; CICLO lo fija antes de fase.update() y las fases no
        #   encienden vapor_chaqueta mientras sea True;
        # - no_conforme / motivo_no_conforme: ciclo NO CONFORME (C-13.7b, P4);
        # - modo_vapor: "chaqueta" / "camara" en ciclo (VCH-SEL), None fuera.
        self.aislamiento_camara = None
        self.inhibir_vapor_chaqueta: bool = False
        self.no_conforme: bool = False
        self.motivo_no_conforme: str = ""
        # P4 (D-14.4): el operador reconoció que la carga NO CONFORME no es
        # liberable (lo pone el backend, auditado); sin él no se confirma
        self.no_conforme_reconocido: bool = False
        self.modo_vapor = None

    def update(self, nuevos_datos):
        self.data.update(nuevos_datos)
        #actualizamos los datos del cofre con los nuevos datos recibidos
        if "temperature" in nuevos_datos:
            temp_list = nuevos_datos["temperature"]
            for nombre, index in self.map_temp.items():
                try:
                    self.sensores_temp[nombre] = temp_list[index]
                except IndexError:
                    pass  # si falta un dato, lo ignora sin romper

        if "pressure" in nuevos_datos:
            pres_list = nuevos_datos["pressure"]
            for nombre, index in self.map_pres.items():
                try:
                    self.sensores_pres[nombre] = pres_list[index]
                except IndexError:
                    pass
                
        if "raw_di" in nuevos_datos:
            di_list = nuevos_datos["raw_di"]
            for nombre, index in self.map_di.items():
                try:
                    self.sensores_di[nombre] = di_list[index]
                except IndexError:
                    pass
        
        if "raw_do" in nuevos_datos:
            do_list = nuevos_datos["raw_do"]
            for nombre, index in self.map_do.items():
                try:
                    self.salidas_do[nombre] = do_list[index]
                except IndexError:
                    pass
    
    def update_door_state(self, door_name, state: DoorState ):
        if door_name in self.estado_puertas:
            self.estado_puertas[door_name] = state
            
    def get_door_state(self, door_name):
        return self.estado_puertas.get(
            door_name,
            DoorState.DESCONOCIDO
        )

            
    def set_machine_state(self, state: GlobalState):
        self.estado_maquina["Estado"] = state
    
    def get_machine_state(self) -> GlobalState:
        return self.estado_maquina.get("Estado")
    
    def set_flag(self, flag, value: bool):
        if flag in self.flags:
            self.flags[flag] = value
        else:
            raise ValueError(f"Flag no definido: {flag}")

    def get_flag(self, flag):
        return self.flags.get(flag, False)


    def reset_flags(self):
        for key in self.flags:
            self.flags[key] = False
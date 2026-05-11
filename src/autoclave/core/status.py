#este archivo sera un cofre sonde se almacenaran los estados tanto de sensores como del sistema en general
#estos estados seran accedidos por los diferentes modulos del sistema para su funcionamiento
#estos estados podran ser actualizados por el modulo control loop

#Actualizacion : 
    #se agregaran los estados de las (DI) entradas digitales
from autoclave.devices.puertas.advanced_door import DoorState
from autoclave.state_machine.machine.eum_global import GlobalState
from matplotlib.pyplot import flag


class EstadoAutoclave:
    map_temp = {
        "temp_camara": 0,
        "temp_2_camara": 1,
        "temp_ref": 2,
        "temp_chaqueta": 3,
        "temp_drenaje_cam": 4,
        "temp_drenaje": 5, 
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
        "aire_comprimido_chaqueta": 12,
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
    
    flags = {
        "LISTO_PARA_CICLO": 0,
        "START_CICLO": 1,
        "FALLO_GENERAL": 2,
        "PARO_EMERGENCIA": 3,
    }

    def __init__(self):
        self.data = {}
        self.sensores_temp = {k: None for k in self.map_temp}
        self.sensores_pres = {k: None for k in self.map_pres}
        self.sensores_di = {k: 0 for k in self.map_di}
        self.salidas_do = {k: 0 for k in self.map_do}
        self.estado_puertas = {k: DoorState.DESCONOCIDO for k in self.state_doors}
        self.estado_maquina = {k: GlobalState.PREPARACION for k in self.state_maquina}
        self.flags = {k: False for k in self.flags}
        self.Alarmas_activas = []
        
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
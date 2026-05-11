#DB_autoclave/Solicitud.py

import src.autoclave.db.config_db.config_global_db as config_global_db
import sqlite3 as sql
import logging

logging.basicConfig(level=logging.DEBUG)


def crear_si_no_existe_db(nombre_db):
    if not config_global_db.verificar_si_db_existe(nombre_db):
        config_global_db.crear_base_datos(nombre_db)
        logging.info(f"Base de datos '{nombre_db}' creada.")
    else:
        logging.info(f"La base de datos '{nombre_db}' ya existe. No se creó una nueva.")

def crear_config_global():
    nombre_tabla = "config_global"
    campos = """
        Clave VARCHAR(50),
        Valor VARCHAR(50),
        Tipo_Dato TEXT CHECK(Tipo_Dato IN ('INT','VARCHAR','DATE','BOOLEAN')),
        Estado TEXT CHECK(Estado IN ('ACTIVO','INACTIVO')),
        Fecha_Creacion DATETIME,
        Usuario_Creacion INTEGER,
        Fecha_actualizacion DATETIME,
        Usuario_actualizacion INTEGER,
        
        FOREIGN KEY (Usuario_Creacion)
            REFERENCES usuario(id)
            ON DELETE CASCADE
            ON UPDATE CASCADE,

        FOREIGN KEY (Usuario_actualizacion)
            REFERENCES usuario(id)
            ON DELETE CASCADE
            ON UPDATE CASCADE
        """
    config_global_db.crear_tabla(nombre_tabla, campos)
    

def crear_tabla_usuario():
    nombre_tabla = "usuario"
    campos = """
        Nombre VARCHAR(100),
        Apellido VARCHAR(100),
        Usuario_sistema VARCHAR(50) UNIQUE,
        Correo VARCHAR(100) UNIQUE,
        Celular VARCHAR(15),
        Rol TEXT CHECK(Rol IN ('ADMIN','OPERADOR','TECNICO')),
        Estado TEXT CHECK(Estado IN ('ACTIVO','INACTIVO')),
        Fecha_Creacion DATETIME,
        Fecha_actualizacion DATETIME
        """
    config_global_db.crear_tabla(nombre_tabla,campos)

def tabla_ac_pantalla_control ():
    nombre = "ac_pantalla_control"
    campos = """
        Autoclave_ID INTEGER,
        Puerta_ID VARCHAR(50),
        Usuario VARCHAR(100),
        Estado TEXT CHECK(Estado IN ('ACTIVO','INACTIVO')),
        Fecha_Creacion DATETIME,
        Usuario_Creacion INTEGER,
        Fecha_actualizacion DATETIME,
        Usuario_actualizacion INTEGER,
        
        FOREIGN KEY (Autoclave_ID)
            REFERENCES autoclave(id)
            ON DELETE CASCADE
            ON UPDATE CASCADE,

        FOREIGN KEY (Puerta_ID)
            REFERENCES ac_puerta(id)
            ON DELETE CASCADE
            ON UPDATE CASCADE,

        FOREIGN KEY (Usuario)
            REFERENCES usuario(id)
            ON DELETE CASCADE
            ON UPDATE CASCADE
        """
    config_global_db.crear_tabla(nombre, campos)
    
    
def tabla_autoclave ():
    nombre = "autoclave"
    campos = """
        Nombre VARCHAR(100),
        Modelo VARCHAR(100),
        Serie VARCHAR(100) UNIQUE,
        Numero_puertas INTEGER,
        Estado TEXT CHECK(Estado IN ('ACTIVO','INACTIVO')),
        Fecha_Creacion DATETIME,
        Usuario_Creacion INTEGER,
        Fecha_actualizacion DATETIME,
        Usuario_actualizacion INTEGER
        """
    config_global_db.crear_tabla(nombre, campos)
    
def tabla_ac_puerta ():
    nombre = "ac_puerta"
    campos = """
        Autoclave_ID INTEGER,
        Codigo VARCHAR(50),
        Nombre VARCHAR(100),
        Estado TEXT CHECK(Estado IN ('ACTIVO','INACTIVO')),
        Fecha_Creacion DATETIME,
        Usuario_Creacion INTEGER,
        Fecha_actualizacion DATETIME,
        Usuario_actualizacion INTEGER,
        
        FOREIGN KEY (Autoclave_ID)
            REFERENCES autoclave(id)
            ON DELETE CASCADE 
            ON UPDATE CASCADE
            
        """
    config_global_db.crear_tabla(nombre, campos)

def tabla_ac_puerto ():
    nombre = "ac_puerto"
    campos = """
        Autoclave_ID INTEGER,
        Puerta_ID VARCHAR(50),
        Tipo_Puerto TEXT CHECK(Tipo_Puerto IN ('DIGITAL','ANALOGO')),
        Direccion_IO TEXT CHECK(Direccion_IO IN ('INPUT','OUTPUT')),
        Numero INTEGER,
        ETIQUETA VARCHAR(100),
        Estado TEXT CHECK(Estado IN ('ACTIVO','INACTIVO')),
        Fecha_Creacion DATETIME,
        Usuario_Creacion INTEGER,
        Fecha_actualizacion DATETIME,
        Usuario_actualizacion INTEGER,
        
        FOREIGN KEY (Autoclave_ID)
            REFERENCES autoclave(id)
            ON DELETE CASCADE
            ON UPDATE CASCADE,
            
        FOREIGN KEY (Puerta_ID)
            REFERENCES ac_puerta(id)
            ON DELETE CASCADE
            ON UPDATE CASCADE
        """
    config_global_db.crear_tabla(nombre, campos)

def tabla_proceso ():
    nombre = "proceso"
    campos = """
        Nombre VARCHAR(100),
        Descripcion VARCHAR(255),
        Estado TEXT CHECK(Estado IN ('ACTIVO','INACTIVO')),
        Fecha_Creacion DATETIME,
        Usuario_Creacion INTEGER,
        Fecha_actualizacion DATETIME,
        Usuario_actualizacion INTEGER
        """
    config_global_db.crear_tabla(nombre, campos)

def tabla_proceso_control ():
    nombre = "proceso_control"
    campos = """ 
        Proceso_ID INTEGER,
        Fecha_Inicio DATETIME,
        Fecha_Fin DATETIME,
        Estado TEXT CHECK(Estado IN ('EN_PROCESO','COMPLETADO','CANCELADO')),
        Fecha_Creacion DATETIME,
        Usuario_Creacion INTEGER,
        Fecha_actualizacion DATETIME,
        Usuario_actualizacion INTEGER,
        
        FOREIGN KEY (Proceso_ID)
            REFERENCES proceso(id)
            ON DELETE CASCADE
            ON UPDATE CASCADE
        """
    config_global_db.crear_tabla(nombre, campos)

def tabla_proceso_fase ():
    nombre = "proceso_fase"
    campos = """
        Proceso_ID INTEGER,
        Fase Text CHECK(Fase IN ('PRECALENTAMIENTO','PURGA',
            'PULSO_VACIO','ESTABILIZACION','CALENTAMIENTO',
            'ESTERILIZACION','ESTABILIZACION 2','ENFRIAMIENTO','ESCAPE','SECADO','FINALIZACION')),
        Nombre VARCHAR(100),
        Orden INTEGER,
        Estado TEXT CHECK(Estado IN ('ACTIVO','INACTIVO')),
        Fecha_Creacion DATETIME,
        Usuario_Creacion INTEGER,
        Fecha_actualizacion DATETIME,
        Usuario_actualizacion INTEGER,
        
        FOREIGN KEY (Proceso_ID)
            REFERENCES proceso(id)
            ON DELETE CASCADE
            ON UPDATE CASCADE
        """
    config_global_db.crear_tabla(nombre, campos)

def tabla_proceso_fase_parametro ():
    nombre = "proceso_fase_parametro"
    campos = """
        Proceso_fase_ID INTEGER,
        Clave VARCHAR(50),
        Valor VARCHAR(50),
        Tipo_Dato TEXT CHECK(Tipo_Dato IN ('INT','VARCHAR','DATE','BOOLEAN')),
        Unidad TEXT CHECK(Unidad IN ('kPa','C','S','MINUTOS')),
        Estado TEXT CHECK(Estado IN ('ACTIVO','INACTIVO')),
        Fecha_Creacion DATETIME,
        Usuario_Creacion INTEGER,
        Fecha_actualizacion DATETIME,
        Usuario_actualizacion INTEGER,
        
        FOREIGN KEY (Proceso_fase_ID)
            REFERENCES proceso_fase(id)
            ON DELETE CASCADE
            ON UPDATE CASCADE
        """
    config_global_db.crear_tabla(nombre, campos)

def tabla_proceso_fase_puerto ():
    nombre = "proceso_fase_puerto"
    campos = """
        Proceso_fase_ID INTEGER,
        Puerto_ID INTEGER,
        Estado TEXT CHECK(Estado IN ('ACTIVO','INACTIVO')),
        Fecha_Creacion DATETIME,
        Usuario_Creacion INTEGER,
        Fecha_actualizacion DATETIME,
        Usuario_actualizacion INTEGER,
        
        FOREIGN KEY (Proceso_fase_ID)
            REFENCES proceso_fase(id)
            ON DELETE CASCADE
            ON UPDATE CASCADE,
            
        FOREIGN KEY (Puerto_ID)
            REFERENCES ac_puerto(id)
            ON DELETE CASCADE
            ON UPDATE CASCADE
        """
    config_global_db.crear_tabla(nombre, campos)

# Crear la base de datos y las tablas necesarias

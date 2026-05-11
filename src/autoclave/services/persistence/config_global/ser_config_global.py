from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime
import os
from autoclave.services.persistence.orm import BaseModel
from autoclave.services.persistence.user.ser_user import Usuario
import tkinter as tk

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Definir la ruta de la base de datos SQLite ubicada en D:\Documentos_y_Código\Código\Python\Proyectos_Funcionales\codigo_autoclave
BASE_DIR = r'D:\Documentos_y_Código\Código\Python\Proyectos_Funcionales\codigo_autoclave'
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'autoclave_vapor.db')}"


# Crear el motor de la base de datos
engine = create_engine(DATABASE_URL, echo=True) #echo=True para ver las consultas SQL generadas echo=false en produccion, echo hace que SQLAlchemy imprima todas las consultas SQL que ejecuta, lo cual es útil para depuración
Base = declarative_base()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
session = SessionLocal()


# ORM tabla "config_global"
class config_global(Base, BaseModel):
    __tablename__ = 'config_global'

    id = Column(Integer, primary_key=True, index=True)
    Clave = Column(String, unique=True, nullable=False)
    Valor = Column(String, nullable=False)
    Tipo_dato = Column(Text, nullable=False)
    Estado = Column(Text, nullable=False)
    Fecha_creacion = Column(DateTime, default=datetime.datetime.utcnow)
    Usuario_creacion = Column(String, nullable=False)
    Fecha_actualizacion = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    Usuario_actualizacion = Column(String, nullable=False)
# Ahora podemos usar la clase config_global para interactuar con la tabla "config_global" en la base de datos
    #Metodos crud
    def __repr__(self): #metodo para representar el objeto como una cadena
        return f"<config_global(Clave='{self.Clave}', Valor='{self.Valor}', Tipo_dato='{self.Tipo_dato}', Estado='{self.Estado}')>"
    
    def to_dict(self): #metodo para convertir el objeto a un diccionario
        return {
            "id": self.id,
            "Clave": self.Clave,
            "Valor": self.Valor,
            "Tipo_dato": self.Tipo_dato,
            "Estado": self.Estado,
            "Fecha_creacion": self.Fecha_creacion,
            "Usuario_creacion": self.Usuario_creacion,
            "Fecha_actualizacion": self.Fecha_actualizacion,
            "Usuario_actualizacion": self.Usuario_actualizacion
        }
        
    @classmethod
    def create(cls, session, datos): #metodo para crear una nueva config global
        
        nueva_config = cls(
            Clave=datos["Clave"],
            Valor=datos["Valor"],
            Tipo_dato=datos["Tipo_dato"],
            Estado=datos["Estado"],
            Usuario_creacion=datos["Usuario"],
            Usuario_actualizacion=datos["Usuario"]
        )
        session.add(nueva_config)
        session.commit()
        session.refresh(nueva_config)
        return nueva_config
    
    def get_by_id(session, config_id): #metodo para obtener una config por id
        return session.query(config_global).filter(config_global.id == config_id).first()
    
    def get_all(session): #metodo para obtener todas las configs
        return session.query(config_global).all() #retorna una lista de objetos config_global
    
    def get_all_dict(session): #metodo para obtener todas las configs en formato diccionario
        configs = session.query(config_global).all()
        return [config.to_dict() for config in configs]
    
    def get_by_key(session, key): #metodo para obtener una config por su clave
        return session.query(config_global).filter(config_global.Clave == key).first()
    
    def get_by_status(session, status): #metodo para obtener configs por su estado
        return session.query(config_global).filter(config_global.Estado == status).all()
    
    def get_by_type(session, tipo): #metodo para obtener configs por su tipo de dato
        return session.query(config_global).filter(config_global.Tipo_dato == tipo).all()
    
    def get_by_value(session, value): #metodo para obtener configs por su valor
        return session.query(config_global).filter(config_global.Valor == value).all()

    def _guardar_config_global(self, entries):
        #obtener los valores de las entradas, se guardaran en un diccionario
        Datos = {key: entry.get() for key, entry in entries.items()}
        #validar que ningun campo este vacio
        if not all([Datos["Clave"], Datos["Valor"], Datos["Tipo_dato"], Datos["Estado"], Datos["Usuario"]]):
            logger.error("Todos los campos son obligatorios.")
            return

        #para poder crear la nueva configuracion global, el Usuario debe existir en la tabla usuarios, estar activo y tener rol admin        
        #convertir el nombre de usuario la primera letra en mayuscula y el resto en 
        Datos["Usuario"] = Datos["Usuario"].capitalize()
        usuario = Usuario.get_by_username(self.session, Datos["Usuario"])

        if not usuario:
            logger.error(f"El usuario '{Datos['Usuario']}' no existe.")
            return
        if usuario.Estado.upper() != "ACTIVO":
            logger.error(f"El usuario '{Datos['Usuario']}' no está activo.")
            return
        if usuario.Rol.upper() != "ADMIN":
            logger.error(f"El usuario '{Datos['Usuario']}' no tiene permisos de administrador.")
            return
        
        
        #convertir el campo Tipo_dato y Estado a mayusculas
        Datos["Tipo_dato"] = Datos["Tipo_dato"].upper()
        Datos["Estado"] = Datos["Estado"].upper()
        
        #crear una nueva configuracion global en la base de datos
        try:
            nueva_config = config_global.create(
                self.session,
                Datos
            )
            logger.info(f"Configuración global creada: {nueva_config}")
            #limpiar las entradas despues de guardar
            for entry in entries.values():
                entry.delete(0, tk.END)
        except Exception as e:
            logger.error(f"Error al crear la configuración global: {e}")
        finally:
            self.session.close()
            
    def update_config_global(self, config_id, entries):
        #obtener los valores de las entradas, se guardaran en un diccionario
        Datos = {key: entry.get() for key, entry in entries.items()}
        #validar que ningun campo este vacio
        if not all([Datos["Clave"], Datos["Valor"], Datos["Tipo_dato"], Datos["Estado"], Datos["Usuario"]]):
            logger.error("Todos los campos son obligatorios.")
            return

        #para poder actualizar la configuracion global, el Usuario debe existir en la tabla usuarios, estar activo y tener rol admin        
        #convertir el nombre de usuario la primera letra en mayuscula y el resto en 
        Datos["Usuario"] = Datos["Usuario"].capitalize()
        usuario = Usuario.get_by_username(self.session, Datos["Usuario"])

        if not usuario:
            logger.error(f"El usuario '{Datos['Usuario']}' no existe.")
            return
        if usuario.Estado.upper() != "ACTIVO":
            logger.error(f"El usuario '{Datos['Usuario']}' no está activo.")
            return
        if usuario.Rol.upper() != "ADMIN":
            logger.error(f"El usuario '{Datos['Usuario']}' no tiene permisos de administrador.")
            return
        
        
        #convertir el campo Tipo_dato y Estado a mayusculas
        Datos["Tipo_dato"] = Datos["Tipo_dato"].upper()
        Datos["Estado"] = Datos["Estado"].upper()
        
        #actualizar la configuracion global en la base de datos
        try:
            config = config_global.get_by_id(self.session, config_id)
            if not config:
                logger.error(f"No se encontró la configuración global con ID {config_id}.")
                return
            
            config.Clave = Datos["Clave"]
            config.Valor = Datos["Valor"]
            config.Tipo_dato = Datos["Tipo_dato"]
            config.Estado = Datos["Estado"]
            config.Usuario_actualizacion = Datos["Usuario"]
            
            self.session.commit()
            logger.info(f"Configuración global actualizada: {config}")
            #limpiar las entradas despues de guardar
            for entry in entries.values():
                entry.delete(0, tk.END)
        except Exception as e:
            logger.error(f"Error al actualizar la configuración global: {e}")
        finally:
            self.session.close()
            
    def confirm_delete(self, id):
        #recibir el id de la configuracion a actualizar
        config = config_global.get_by_id(self.session, id)
        if not config:
            logger.info(f"No se encontró la configuración global con ID {id}.")
            return 
        return config
    
    def delete_config_global(self, config_id):
        try:
            config = config_global.get_by_id(self.session, config_id)
            if not config:
                logger.error(f"No se encontró la configuración global con ID {config_id}.")
                return
            
            self.session.delete(config)
            self.session.commit()
            logger.info(f"Configuración global con ID {config_id} eliminada.")
        except Exception as e:
            logger.error(f"Error al eliminar la configuración global: {e}")
        finally:
            self.session.close()
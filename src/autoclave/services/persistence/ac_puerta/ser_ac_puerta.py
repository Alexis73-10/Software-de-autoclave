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

#---------------------------------------------------------------------------------------------------
# ORM tabla "ac_puerta"
class ac_puerta(Base, BaseModel):
    __tablename__ = 'ac_puerta'
    
    id = Column(Integer, primary_key=True, index=True)
    Autoclave_ID = Column(Integer, nullable=False)
    Codigo = Column(String, nullable=False)
    Nombre = Column(String, nullable=False)
    Estado = Column(Text, nullable=False)
    Fecha_creacion = Column(DateTime, default=datetime.datetime.utcnow)
    Usuario_creacion = Column(String, nullable=False)
    Fecha_actualizacion = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    Usuario_actualizacion = Column(String, nullable=False)
    # Ahora podemos usar la clase ac_puerta para interactuar con la tabla "ac_puerta" en la base de datos
    #metodos crud
    
    def __repr__(self): #metodo para representar el objeto como una cadena
        return f"<ac_puerta(Codigo='{self.Codigo}', Nombre='{self.Nombre}', Estado='{self.Estado}')>"
    
    def to_dict(self): #metodo para convertir el objeto a un diccionario
        return {
            "id": self.id,
            "Autoclave_ID": self.Autoclave_ID,
            "Codigo": self.Codigo,
            "Nombre": self.Nombre,
            "Estado": self.Estado,
            "Fecha_creacion": self.Fecha_creacion,
            "Usuario_creacion": self.Usuario_creacion,
            "Fecha_actualizacion": self.Fecha_actualizacion,
            "Usuario_actualizacion": self.Usuario_actualizacion
        }
    
    @classmethod
    def create(cls, session, Autoclave_ID, Codigo, Nombre, Estado, Usuario_creacion, Usuario_actualizacion):
        nueva_puerta = cls(
            Autoclave_ID=Autoclave_ID,
            Codigo=Codigo,
            Nombre=Nombre,
            Estado=Estado,
            Usuario_creacion=Usuario_creacion,
            Usuario_actualizacion=Usuario_actualizacion
        )
        session.add(nueva_puerta)
        session.commit()
        session.refresh(nueva_puerta)
        return nueva_puerta
    
    def get_by_id(session, puerta_id): #metodo para obtener una puerta por id
        return session.query(ac_puerta).filter(ac_puerta.id == puerta_id).first()
    
    def get_all(session): #metodo para obtener todas las puertas
        return session.query(ac_puerta).all()
    
    def get_by_status(session, status): #metodo para obtener puertas por su estado
        return session.query(ac_puerta).filter(ac_puerta.Estado == status).all()
    
    def get_by_name(session, name): #metodo para obtener puertas por su nombre
        return session.query(ac_puerta).filter(ac_puerta.Nombre == name).all()
    
    def get_by_code(session, code): #metodo para obtener puertas por su codigo
        return session.query(ac_puerta).filter(ac_puerta.Codigo == code).all()
    
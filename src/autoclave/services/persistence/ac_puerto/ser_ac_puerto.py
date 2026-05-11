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

# ---------------------------------------------------------------------------------------------------
#ORM tabla 'ac_puerto'
class ac_puerto(Base, BaseModel):
    __tablename__ = 'ac_puerto'
    
    id = Column(Integer, primary_key=True, index=True)
    Autoclave_ID = Column(Integer, nullable=False)
    Puerta_ID = Column(Integer, nullable=False)
    Tipo_puerto = Column(Text, nullable=False)
    Direccion_IO = Column(Text, nullable=False)
    Numero = Column(Integer, nullable=False)
    ETIQUETA = Column(String, nullable=False)
    Estado = Column(Text, nullable=False)
    Fecha_creacion = Column(DateTime, default=datetime.datetime.utcnow)
    Usuario_creacion = Column(String, nullable=False)
    Fecha_actualizacion = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    Usuario_actualizacion = Column(String, nullable=False)
# Ahora podemos usar la clase ac_puerto para interactuar con la tabla "ac_puerto" en la base de datos
#metodos crud
    def __repr__(self): #metodo para representar el objeto como una cadena
        return f"<ac_puerto(Tipo_puerto='{self.Tipo_puerto}', Direccion_IO='{self.Direccion_IO}', Numero='{self.Numero}', ETIQUETA='{self.ETIQUETA}', Estado='{self.Estado}')>"
    
    def to_dict(self): #metodo para convertir el objeto a un diccionario
        return {
            "id": self.id,
            "Autoclave_ID": self.Autoclave_ID,
            "Puerta_ID": self.Puerta_ID,
            "Tipo_puerto": self.Tipo_puerto,
            "Direccion_IO": self.Direccion_IO,
            "Numero": self.Numero,
            "ETIQUETA": self.ETIQUETA,
            "Estado": self.Estado,
            "Fecha_creacion": self.Fecha_creacion,
            "Usuario_creacion": self.Usuario_creacion,
            "Fecha_actualizacion": self.Fecha_actualizacion,
            "Usuario_actualizacion": self.Usuario_actualizacion
        }
    
    @classmethod
    def create(cls, session, Autoclave_ID, Puerta_ID, Tipo_puerto, Direccion_IO, Numero, ETIQUETA, Estado, Usuario_creacion, Usuario_actualizacion):
        nuevo_puerto = cls(
            Autoclave_ID=Autoclave_ID,
            Puerta_ID=Puerta_ID,
            Tipo_puerto=Tipo_puerto,
            Direccion_IO=Direccion_IO,
            Numero=Numero,
            ETIQUETA=ETIQUETA,
            Estado=Estado,
            Usuario_creacion=Usuario_creacion,
            Usuario_actualizacion=Usuario_actualizacion
        )
        session.add(nuevo_puerto)
        session.commit()
        session.refresh(nuevo_puerto)
        return nuevo_puerto
    
    def get_by_id(session, puerto_id): #metodo para obtener un puerto por id
        return session.query(ac_puerto).filter(ac_puerto.id == puerto_id).first()
    
    def get_all(session): #metodo para obtener todos los puertos
        return session.query(ac_puerto).all()
    
    def get_by_status(session, status): #metodo para obtener puertos por su estado
        return session.query(ac_puerto).filter(ac_puerto.Estado == status).all()
    
    def get_by_type(session, tipo): #metodo para obtener puertos por su tipo
        return session.query(ac_puerto).filter(ac_puerto.Tipo_puerto == tipo).all()
    
    def get_by_io_address(session, address): #metodo para obtener puertos por su direccion IO
        return session.query(ac_puerto).filter(ac_puerto.Direccion_IO == address).all()
    
    def get_by_label(session, label): #metodo para obtener puertos por su etiqueta
        return session.query(ac_puerto).filter(ac_puerto.ETIQUETA == label).all()
    
    def get_by_number(session, number): #metodo para obtener puertos por su numero
        return session.query(ac_puerto).filter(ac_puerto.Numero == number).all()
    

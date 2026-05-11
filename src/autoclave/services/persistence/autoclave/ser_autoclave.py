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
# ORM tabla "autocalve"
class autoclave(Base, BaseModel):
    __tablename__ = 'autoclave'

    id = Column(Integer, primary_key=True, index=True)
    Nombre = Column(String, nullable=False)
    Modelo = Column(String, nullable=False)
    Serie = Column(String, unique=True, nullable=False)
    Numero_puertas = Column(Integer, nullable=False)
    Estado = Column(Text, nullable=False)
    Fecha_creacion = Column(DateTime, default=datetime.datetime.utcnow)
    Fecha_actualizacion = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    Usuario_creacion = Column(String, nullable=False)
    Usuario_actualizacion = Column(String, nullable=False)
# Ahora podemos usar la clase autoclave para interactuar con la tabla "autoclave" en la base de datos
    #metodos crud
    #CRUD: Create, Read, Update, Delete
    def __repr__(self): #metodo para representar el objeto como una cadena
        return f"<autoclave(Nombre='{self.Nombre}', Modelo='{self.Modelo}', Serie='{self.Serie}', Numero_puertas='{self.Numero_puertas}', Estado='{self.Estado}')>" 
    
    def to_dict(self): #metodo para convertir el objeto a un diccionario
        return {
            "id": self.id,
            "Nombre": self.Nombre,
            "Modelo": self.Modelo,
            "Serie": self.Serie,
            "Numero_puertas": self.Numero_puertas,
            "Estado": self.Estado,
            "Fecha_creacion": self.Fecha_creacion,
            "Fecha_actualizacion": self.Fecha_actualizacion,
            "Usuario_creacion": self.Usuario_creacion,
            "Usuario_actualizacion": self.Usuario_actualizacion
        }
        
    
    @classmethod
    def create(cls, session, Nombre, Modelo, Serie, Numero_puertas, Estado, Usuario_creacion, Usuario_actualizacion):
        nueva_autoclave = cls(
            Nombre=Nombre,
            Modelo=Modelo,
            Serie=Serie,
            Numero_puertas=Numero_puertas,
            Estado=Estado,
            Usuario_creacion=Usuario_creacion,
            Usuario_actualizacion=Usuario_actualizacion
        )
        session.add(nueva_autoclave)
        session.commit()
        session.refresh(nueva_autoclave)
        return nueva_autoclave
    

    def get_by_id(session, autoclave_id): #metodo para obtener una autoclave por id
        return session.query(autoclave).filter(autoclave.id == autoclave_id).first()
    
    def get_all(session): #metodo para obtener todas las autoclaves
        return session.query(autoclave).all()
    
    def get_by_serial(session, serial): #metodo para obtener una autoclave por su serie
        return session.query(autoclave).filter(autoclave.Serie == serial).first()
    
    def get_by_status(session, status): #metodo para obtener autoclaves por su estado
        return session.query(autoclave).filter(autoclave.Estado == status).all()
    
    def get_by_name(session, name): #metodo para obtener autoclaves por su nombre
        return session.query(autoclave).filter(autoclave.Nombre == name).all()
    
    def get_by_model(session, model): #metodo para obtener autoclaves por su modelo
        return session.query(autoclave).filter(autoclave.Modelo == model).all()
    
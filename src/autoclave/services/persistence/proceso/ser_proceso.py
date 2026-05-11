from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime
import os
from autoclave.services.persistence.orm import BaseModel
from autoclave.services.persistence.user.ser_user import Usuario
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
# ORM tabla 'proceso'
class proceso(Base, BaseModel):
    __tablename__ = 'proceso'
    
    Nombre = Column(String, nullable=False)
    Descripcion = Column(Text, nullable=True)
    Estado = Column(Text, nullable=False)
    Fecha_creacion = Column(DateTime, default=datetime.datetime.utcnow)
    Usuario_creacion = Column(String, nullable=False)
    Fecha_actualizacion = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    Usuario_actualizacion = Column(String, nullable=False)
    
    def __repr__(self):
        return f"<proceso(Nombre='{self.Nombre}', Descripcion='{self.Descripcion}', Estado='{self.Estado}')>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "Nombre": self.Nombre,
            "Descripcion": self.Descripcion,
            "Estado": self.Estado,
            "Fecha_creacion": self.Fecha_creacion,
            "Usuario_creacion": self.Usuario_creacion,
            "Fecha_actualizacion": self.Fecha_actualizacion,
            "Usuario_actualizacion": self.Usuario_actualizacion
        }
        
    @classmethod
    def create(cls, session, Nombre, Descripcion, Estado, Usuario_creacion, Usuario_actualizacion):
        nuevo_proceso = cls(
            Nombre=Nombre,
            Descripcion=Descripcion,
            Estado=Estado,
            Usuario_creacion=Usuario_creacion,
            Usuario_actualizacion=Usuario_actualizacion
        )
        session.add(nuevo_proceso)
        session.commit()
        session.refresh(nuevo_proceso)
        return nuevo_proceso
    
    def get_by_id(session, proceso_id):
        return session.query(proceso).filter(proceso.id == proceso_id).first()
    
    def get_all(session):
        return session.query(proceso).all()
    
    def get_by_status(session, status):
        return session.query(proceso).filter(proceso.Estado == status).all()
    
    def get_by_name(session, name):
        return session.query(proceso).filter(proceso.Nombre == name).all()

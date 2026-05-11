
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime
import os
from autoclave.services.persistence.orm import BaseModel

BASE_DIR = r'D:\Documentos_y_Código\Código\Python\Proyectos_Funcionales\codigo_autoclave'
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'autoclave_vapor.db')}"


# Crear el motor de la base de datos
engine = create_engine(DATABASE_URL, echo=True) #echo=True para ver las consultas SQL generadas echo=false en produccion, echo hace que SQLAlchemy imprima todas las consultas SQL que ejecuta, lo cual es útil para depuración
Base = declarative_base()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
session = SessionLocal()

class Usuario(Base, BaseModel):
    __tablename__ = 'usuario'

    id = Column(Integer, primary_key=True, index=True)
    Nombre = Column(String, nullable=False)
    Apellido = Column(String, nullable=False)
    Usuario_sistema = Column(String, unique=True, nullable=False)
    Correo = Column(String, unique=True, nullable=False)
    Celular = Column(String, nullable=True)
    #rol solo puede ser 'ADMIN' 'OPERADOR' 'TECNICO', por lo que usaremos Text con CHECK
    Rol = Column(Text, nullable=False)
    #estado solo puede ser 'ACTIVO' 'INACTIVO', por lo que usaremos Text con CHECK
    Estado = Column(Text, nullable=False)
    Fecha_creacion = Column(DateTime, default=datetime.datetime.utcnow)
    Fecha_actualizacion = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
# Ahora podemos usar la clase Usuario para interactuar con la tabla "usuario" en la base de datos
    #definiremos operaciones CRUD como metodos de la clase Usuario
    #CRUD: Create, Read, Update, Delete
    def __repr__(self): #metodo para representar el objeto como una cadena
        #esto es util para depuracion, al representar el ojeto nos mostrara sus atributos principales
        return f"<Usuario(Nombre='{self.Nombre}', Apellido='{self.Apellido}', Usuario_sistema='{self.Usuario_sistema}', Correo='{self.Correo}', Celular='{self.Celular}', Rol='{self.Rol}', Estado='{self.Estado}')>"
    
    def to_dict(self): #metodo para convertir el objeto a un diccionario
        #esto es util para serializar el objeto a JSON o para otras operaciones
        return {
            "id": self.id,
            "Nombre": self.Nombre,
            "Apellido": self.Apellido,
            "Usuario_sistema": self.Usuario_sistema,
            "Correo": self.Correo,
            "Celular": self.Celular,
            "Rol": self.Rol,
            "Estado": self.Estado,
            "Fecha_creacion": self.Fecha_creacion,
            "Fecha_actualizacion": self.Fecha_actualizacion
        }
    #metodo para crear un nuevo usuario
    @classmethod
    def create(cls, session, Nombre, Apellido, Usuario_sistema, Correo, Celular, Rol, Estado):
        nuevo_usuario = cls(
            Nombre=Nombre,
            Apellido=Apellido,
            Usuario_sistema=Usuario_sistema,
            Correo=Correo,
            Celular=Celular,
            Rol=Rol,
            Estado=Estado
        )
        
        session.add(nuevo_usuario)
        session.commit()
        session.refresh(nuevo_usuario)
        return nuevo_usuario
    
    def get_by_id(session, user_id): #metodo para obtener un usuario por id
        return session.query(Usuario).filter(Usuario.id == user_id).first()
    
    def get_all(session): #metodo para obtener todos los usuarios
        return session.query(Usuario).all()
    
    def get_by_username(session, username): #metodo para obtener un usuario por su nombre de usuario
        return session.query(Usuario).filter(Usuario.Usuario_sistema == username).first()
    
    def get_by_email(session, email): #metodo para obtener un usuario por su correo
        return session.query(Usuario).filter(Usuario.Correo == email).first()
    
    def get_by_role(session, role): #metodo para obtener usuarios por su rol
        return session.query(Usuario).filter(Usuario.Rol == role).all()
    
    def get_by_status(session, status): #metodo para obtener usuarios por su estado
        return session.query(Usuario).filter(Usuario.Estado == status).all()

#este archivo manejara la coneccion ORM a la base de datos 
#usaremos SQLAlchemy
#con una base de datos SQLite para simplicidad ya existente llamada autoclave_vapor.db ubicada en la raiz del proyecto
# y trabajaremos con  la tabla "usuario" ya existente en la base de datos
#la tabla usuario tiene las siguientes columnas:
# id (Integer, primary key)
# Nombre (varchar)
# Apellido (varchar)
# Usuario_sistema (varchar)
# Correo (varchar)
# Celular (varchar)
# Rol (text)
# Estado (text)
# Fecha_creacion (datetime)
# Fecha_actualizacion (datetime)
#se comentara cada parte del codigo para mejor entendimiento
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime
import os

# Definir la ruta de la base de datos SQLite ubicada en D:\Documentos_y_Código\Código\Python\Proyectos_Funcionales\codigo_autoclave
BASE_DIR = r'D:\Documentos_y_Código\Código\Python\Proyectos_Funcionales\codigo_autoclave'
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'autoclave_vapor.db')}"


# Crear el motor de la base de datos
engine = create_engine(DATABASE_URL, echo=True) #echo=True para ver las consultas SQL generadas echo=false en produccion, echo hace que SQLAlchemy imprima todas las consultas SQL que ejecuta, lo cual es útil para depuración
Base = declarative_base()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
session = SessionLocal()

#clase base para los modelos ORM
class BaseModel:
    def save(self, session): #metodo para guardar el objeto
        session.add(self)
        session.commit()
        session.refresh(self)
        return self
    
    def delete(self, session): #metodo para eliminar el objeto
        session.delete(self)
        session.commit()
        
    def update(self, session, **kwargs): #metodo para actualizar el objeto
        for key, value in kwargs.items():
            setattr(self, key, value)
        session.commit()
        session.refresh(self)
        return self


# Definir el modelo ORM para la tabla "usuario"
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


#---------------------------------------------------------------------------------------------------
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
    def create(cls, session, Clave, Valor, Tipo_dato, Estado, Usuario_creacion, Usuario_actualizacion):
        nueva_config = cls(
            Clave=Clave,
            Valor=Valor,
            Tipo_dato=Tipo_dato,
            Estado=Estado,
            Usuario_creacion=Usuario_creacion,
            Usuario_actualizacion=Usuario_actualizacion
        )
        session.add(nueva_config)
        session.commit()
        session.refresh(nueva_config)
        return nueva_config
    
    def get_by_id(session, config_id): #metodo para obtener una config por id
        return session.query(config_global).filter(config_global.id == config_id).first()
    
    def get_all(session): #metodo para obtener todas las configs
        return session.query(config_global).all()
    
    def get_by_key(session, key): #metodo para obtener una config por su clave
        return session.query(config_global).filter(config_global.Clave == key).first()
    
    def get_by_status(session, status): #metodo para obtener configs por su estado
        return session.query(config_global).filter(config_global.Estado == status).all()
    
    def get_by_type(session, tipo): #metodo para obtener configs por su tipo de dato
        return session.query(config_global).filter(config_global.Tipo_dato == tipo).all()
    
    def get_by_value(session, value): #metodo para obtener configs por su valor
        return session.query(config_global).filter(config_global.Valor == value).all()

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
    
# ---------------------------------------------------------------------------------------------------
#ORM tabla 'ac_pantalla_control'
class ac_pantalla_control(Base, BaseModel):
    __tablename__ = 'ac_pantalla_control'
    
    id = Column(Integer, primary_key=True, index=True)
    Autoclave_ID = Column(Integer, nullable=False)
    Puerta_ID = Column(Integer, nullable=False)
    Usuario = Column(String, nullable=False)
    Estado = Column(Text, nullable=False)
    Fecha_creacion = Column(DateTime, default=datetime.datetime.utcnow) #utcnow para tener la fecha y hora actual en UTC
    Usuario_creacion = Column(String, nullable=False)
    Fecha_actualizacion = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    Usuario_actualizacion = Column(String, nullable=False)
# Ahora podemos usar la clase ac_pantalla_control para interactuar con la tabla "ac_pantalla_control" en la base de datos
#metodos crud
    def __repr__(self): #metodo para representar el objeto como una cadena
        return f"<ac_pantalla_control(Usuario='{self.Usuario}', Estado='{self.Estado}')>"
    
    def to_dict(self): #metodo para convertir el objeto a un diccionario
        return {
            "id": self.id,
            "Autoclave_ID": self.Autoclave_ID,
            "Puerta_ID": self.Puerta_ID,
            "Usuario": self.Usuario,
            "Estado": self.Estado,
            "Fecha_creacion": self.Fecha_creacion,
            "Usuario_creacion": self.Usuario_creacion,
            "Fecha_actualizacion": self.Fecha_actualizacion,
            "Usuario_actualizacion": self.Usuario_actualizacion
        }
    
    @classmethod
    def create(cls, session, Autoclave_ID, Puerta_ID, Usuario, Estado, Usuario_creacion, Usuario_actualizacion):
        nueva_pantalla = cls(
            Autoclave_ID=Autoclave_ID,
            Puerta_ID=Puerta_ID,
            Usuario=Usuario,
            Estado=Estado,
            Usuario_creacion=Usuario_creacion,
            Usuario_actualizacion=Usuario_actualizacion
        )
        session.add(nueva_pantalla)
        session.commit()
        session.refresh(nueva_pantalla)
        return nueva_pantalla
    
    def get_by_id(session, pantalla_id): #metodo para obtener una pantalla por id
        return session.query(ac_pantalla_control).filter(ac_pantalla_control.id == pantalla_id).first()
    
    def get_all(session): #metodo para obtener todas las pantallas
        return session.query(ac_pantalla_control).all()
    
    def get_by_status(session, status): #metodo para obtener pantallas por su estado
        return session.query(ac_pantalla_control).filter(ac_pantalla_control.Estado == status).all()
    
    def get_by_user(session, user): #metodo para obtener pantallas por su usuario
        return session.query(ac_pantalla_control).filter(ac_pantalla_control.Usuario == user).all()
    
    
        
# ---------------------------------------------------------------------------------------------------
# ORM tabla 'proceso_fase'
class proceso_fase(Base, BaseModel):
    __tablename__ = 'proceso_fase'
    
    id = Column(Integer, primary_key=True, index=True)
    Proceso_ID = Column(Integer, nullable=False) #nullable hace referencia a que no puede ser nulo
    Fase = Column(Text, nullable=False)
    Nombre = Column(String, nullable=False)
    Orden = Column(Integer, nullable=False)
    Estado = Column(Text, nullable=False)
    Fecha_creacion = Column(DateTime, default=datetime.datetime.utcnow)
    Usuario_creacion = Column(String, nullable=False)
    Fecha_actualizacion = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    Usuario_actualizacion = Column(String, nullable=False)
# Ahora podemos usar la clase proceso_fase para interactuar con la tabla "proceso_fase" en la base de datos
#metodos crud
    def __repr__(self): #metodo para representar el objeto como una cadena
        return f"<proceso_fase(Fase='{self.Fase}', Nombre='{self.Nombre}', Orden='{self.Orden}', Estado='{self.Estado}')>"
    
    def to_dict(self): #metodo para convertir el objeto a un diccionario
        return {
            "id": self.id,
            "Proceso_ID": self.Proceso_ID,
            "Fase": self.Fase,
            "Nombre": self.Nombre,
            "Orden": self.Orden,
            "Estado": self.Estado,
            "Fecha_creacion": self.Fecha_creacion,
            "Usuario_creacion": self.Usuario_creacion,
            "Fecha_actualizacion": self.Fecha_actualizacion,
            "Usuario_actualizacion": self.Usuario_actualizacion
        }
    
    @classmethod
    def create(cls, session, Proceso_ID, Fase, Nombre, Orden, Estado, Usuario_creacion, Usuario_actualizacion):
        nueva_fase = cls(
            Proceso_ID=Proceso_ID,
            Fase=Fase,
            Nombre=Nombre,
            Orden=Orden,
            Estado=Estado,
            Usuario_creacion=Usuario_creacion,
            Usuario_actualizacion=Usuario_actualizacion
        )
        session.add(nueva_fase)
        session.commit()
        session.refresh(nueva_fase)
        return nueva_fase
    
    def get_by_id(session, fase_id): #metodo para obtener una fase por id
        return session.query(proceso_fase).filter(proceso_fase.id == fase_id).first()
    
    def get_all(session): #metodo para obtener todas las fases
        return session.query(proceso_fase).all()
    
    def get_by_status(session, status): #metodo para obtener fases por su estado
        return session.query(proceso_fase).filter(proceso_fase.Estado == status).all()
    
    def get_by_name(session, name): #metodo para obtener fases por su nombre
        return session.query(proceso_fase).filter(proceso_fase.Nombre == name).all()
    
    def get_by_phase(session, phase): #metodo para obtener fases por su fase
        return session.query(proceso_fase).filter(proceso_fase.Fase == phase).all()
    
# ---------------------------------------------------------------------------------------------------
# ORM tabla 'proceso_fase_parametro'
class proceso_fase_parametro(Base, BaseModel):
    __tablename__ = 'proceso_fase_parametro'
    
    id = Column(Integer, primary_key=True, index=True)
    Proceso_fase_ID = Column(Integer, nullable=False)
    Clave = Column(String, nullable=False)
    Valor = Column(String, nullable=False)
    Tipo_dato = Column(Text, nullable=False)
    Unidad = Column(Text, nullable=True)
    Estado = Column(Text, nullable=False)
    Usuario_creacion = Column(String, nullable=False)
    Fecha_creacion = Column(DateTime, default=datetime.datetime.utcnow)
    Usuario_actualizacion = Column(String, nullable=False)
    Fecha_actualizacion = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
# Ahora podemos usar la clase proceso_fase_parametro para interactuar con la tabla "proceso_fase_parametro" en la base de datos
#modelos CRUD
    def __repr__(self): #metodo para representar el objeto como una cadena
        return f"<proceso_fase_parametro(Clave='{self.Clave}', Valor='{self.Valor}', Tipo_dato='{self.Tipo_dato}', Unidad='{self.Unidad}', Estado='{self.Estado}')>"
    
    def to_dict(self): #metodo para convertir el objeto a un diccionario
        return {
            "id": self.id,
            "Proceso_fase_ID": self.Proceso_fase_ID,
            "Clave": self.Clave,
            "Valor": self.Valor,
            "Tipo_dato": self.Tipo_dato,
            "Unidad": self.Unidad,
            "Estado": self.Estado,
            "Usuario_creacion": self.Usuario_creacion,
            "Fecha_creacion": self.Fecha_creacion,
            "Usuario_actualizacion": self.Usuario_actualizacion,
            "Fecha_actualizacion": self.Fecha_actualizacion
        }
        
    @classmethod
    def create(cls, session, Proceso_fase_ID, Clave, Valor, Tipo_dato, Unidad, Estado, Usuario_creacion, Usuario_actualizacion):
        nuevo_parametro = cls(
            Proceso_fase_ID=Proceso_fase_ID,
            Clave=Clave,
            Valor=Valor,
            Tipo_dato=Tipo_dato,
            Unidad=Unidad,
            Estado=Estado,
            Usuario_creacion=Usuario_creacion,
            Usuario_actualizacion=Usuario_actualizacion
        )
        session.add(nuevo_parametro)
        session.commit()
        session.refresh(nuevo_parametro)
        return nuevo_parametro
    
    def get_by_id(session, parametro_id): #metodo para obtener un parametro por id
        return session.query(proceso_fase_parametro).filter(proceso_fase_parametro.id == parametro_id).first()
    
    def get_all(session): #metodo para obtener todos los parametros
        return session.query(proceso_fase_parametro).all()
    
    def get_by_status(session, status): #metodo para obtener parametros por su estado
        return session.query(proceso_fase_parametro).filter(proceso_fase_parametro.Estado == status).all()
    
    def get_by_key(session, key): #metodo para obtener parametros por su clave
        return session.query(proceso_fase_parametro).filter(proceso_fase_parametro.Clave == key).all()
    
    def get_by_type(session, tipo): #metodo para obtener parametros por su tipo de dato
        return session.query(proceso_fase_parametro).filter(proceso_fase_parametro.Tipo_dato == tipo).all()
    
    def get_by_unit(session, unit): #metodo para obtener parametros por su unidad
        return session.query(proceso_fase_parametro).filter(proceso_fase_parametro.Unidad == unit).all()
    
# ---------------------------------------------------------------------------------------------------
Base.metadata.create_all(bind=engine)
# Esta línea crea todas las tablas en la base de datos que aún no existen basándose en los modelos definidos
# Si las tablas ya existen, esta línea no hará nada
#este archivo dreara el CRUD para la tabla control_usuario tanto en backend
#CRUD: Create, Read, Update, Delete
import logging
from autoclave.db.config_db import config_global_db
import datetime

logging.basicConfig(level=logging.DEBUG)

fech_cr= datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
fech_mod= datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

class ControlUsuarioDB:
    def __init__(self, nombre_db='autoclave_vapor.db'):
        self.nombre_db = nombre_db
        logging.info("ControlUsuarioDB initialized.")
        
    def verificar_tabla(self):
        # Verifica si la tabla 'usuario' existe en la base de datos
        conn = config_global_db.sql.connect(self.nombre_db)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='usuario';")
        tabla_existe = cursor.fetchone() is not None
        conn.close()
        logging.info(f"Tabla 'usuario' existe: {tabla_existe}")
        return tabla_existe
    
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
        
    def crear_tabla_si_no_existe(self):
        if not self.verificar_tabla():
            self.crear_tabla_usuario()
            logging.info("Tabla 'usuario' creada.")
        else:
            logging.info("La tabla 'usuario' ya existe. No se creó una nueva.")
    
    def leer_usuarios(self):
        # Lee todos los usuarios de la tabla 'usuario'
        conn = config_global_db.sql.connect(self.nombre_db)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuario;")
        usuarios = cursor.fetchall()
        conn.close()
        logging.info(f"Usuarios leídos: {usuarios}")
        return usuarios
    
    def leer_usuario_por_id(self, usuario_id):
        # Lee un usuario específico por ID
        conn = config_global_db.sql.connect(self.nombre_db)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuario WHERE id = ?;", (usuario_id,))
        usuario = cursor.fetchone()
        conn.close()
        logging.info(f"Usuario leído por ID {usuario_id}: {usuario}")
        return usuario
    
    def leer_usuario_por_nombre(self, nombre):
        # Lee un usuario específico por nombre
        conn = config_global_db.sql.connect(self.nombre_db)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuario WHERE Nombre = ?;", (nombre,))
        usuario = cursor.fetchone()
        conn.close()
        logging.info(f"Usuario leído por Nombre {nombre}: {usuario}")
        return usuario
    
    def leer_usuario_por_usuario_sistema(self, usuario_sistema):
        # Lee un usuario específico por nombre de usuario del sistema
        conn = config_global_db.sql.connect(self.nombre_db)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuario WHERE Usuario_sistema = ?;", (usuario_sistema,))
        usuario = cursor.fetchone()
        conn.close()
        logging.info(f"Usuario leído por Usuario_sistema {usuario_sistema}: {usuario}")
        return usuario
    
    def leer_usuario_por_correo(self, correo):
        # Lee un usuario específico por correo
        conn = config_global_db.sql.connect(self.nombre_db)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuario WHERE Correo = ?;", (correo,))
        usuario = cursor.fetchone()
        conn.close()
        logging.info(f"Usuario leído por Correo {correo}: {usuario}")
        return usuario
    
    def leer_usuario_por_celular(self, celular):
        # Lee un usuario específico por celular
        conn = config_global_db.sql.connect(self.nombre_db)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuario WHERE Celular = ?;", (celular,))
        usuario = cursor.fetchone()
        conn.close()
        logging.info(f"Usuario leído por Celular {celular}: {usuario}")
        return usuario
    
    def leer_usuarios_por_rol(self, rol):
        # Lee usuarios específicos por rol
        conn = config_global_db.sql.connect(self.nombre_db)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuario WHERE Rol = ?;", (rol,))
        usuarios = cursor.fetchall()
        conn.close()
        logging.info(f"Usuarios leídos por Rol {rol}: {usuarios}")
        return usuarios
    
    def leer_usuarios_por_estado(self, estado):
        # Lee usuarios específicos por estado
        conn = config_global_db.sql.connect(self.nombre_db)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuario WHERE Estado = ?;", (estado,))
        usuarios = cursor.fetchall()
        conn.close()
        logging.info(f"Usuarios leídos por Estado {estado}: {usuarios}")
        return usuarios
    
    def crear_usuario(self, nombre, apellido, usuario_sistema, correo, celular, rol, estado):
        conn = config_global_db.sql.connect(self.nombre_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO usuario (Nombre, Apellido, Usuario_sistema, Correo, Celular, Rol, Estado, Fecha_creacion, Fecha_modificacion)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (nombre, apellido, usuario_sistema, correo, celular, rol, estado, fech_cr, fech_mod))
        conn.commit()
        conn.close()
        logging.info(f"Usuario creado: {nombre} {apellido}, Usuario_sistema: {usuario_sistema}")
        
    # Actualizar usuario
    def actualizar_estado_usuario(self, usuario_id, nuevo_estado):
        conn = config_global_db.sql.connect(self.nombre_db)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE usuario
            SET Estado = ?, Fecha_modificacion = ?
            WHERE id = ?;
        """, (nuevo_estado, fech_mod, usuario_id))
        conn.commit()
        conn.close()
        logging.info(f"Estado del usuario con ID {usuario_id} actualizado a {nuevo_estado}.")
        
    def actualizar_rol_usuario(self, usuario_id, nuevo_rol):
        conn = config_global_db.sql.connect(self.nombre_db)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE usuario
            SET Rol = ?, Fecha_modificacion = ?
            WHERE id = ?;
        """, (nuevo_rol, fech_mod, usuario_id))
        conn.commit()
        conn.close()
        logging.info(f"Rol del usuario con ID {usuario_id} actualizado a {nuevo_rol}.")
        
    def actualizar_correo_usuario(self, usuario_id, nuevo_correo):
        conn = config_global_db.sql.connect(self.nombre_db)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE usuario
            SET Correo = ?, Fecha_modificacion = ?
            WHERE id = ?;
        """, (nuevo_correo, fech_mod, usuario_id))
        conn.commit()
        conn.close()
        logging.info(f"Correo del usuario con ID {usuario_id} actualizado a {nuevo_correo}.")
        
    def actualizar_celular_usuario(self, usuario_id, nuevo_celular):
        conn = config_global_db.sql.connect(self.nombre_db)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE usuario
            SET Celular = ?, Fecha_modificacion = ?
            WHERE id = ?;
        """, (nuevo_celular, fech_mod, usuario_id))
        conn.commit()
        conn.close()
        logging.info(f"Celular del usuario con ID {usuario_id} actualizado a {nuevo_celular}.")
        
    def actualizar_nombre_usuario(self, usuario_id, nuevo_nombre):
        conn = config_global_db.sql.connect(self.nombre_db)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE usuario
            SET Nombre = ?, Fecha_modificacion = ?
            WHERE id = ?;
        """, (nuevo_nombre, fech_mod, usuario_id))
        conn.commit()
        conn.close()
        logging.info(f"Nombre del usuario con ID {usuario_id} actualizado a {nuevo_nombre}.")
        
    def eliminar_usuario(self, usuario_id):
        conn = config_global_db.sql.connect(self.nombre_db)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM usuario WHERE id = ?;", (usuario_id,))
        conn.commit()
        conn.close()
        logging.info(f"Usuario con ID {usuario_id} eliminado.")
        
    def eliminar_todos_usuarios(self):
        conn = config_global_db.sql.connect(self.nombre_db)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM usuario;")
        conn.commit()
        conn.close()
        logging.info("Todos los usuarios eliminados.")
        
    
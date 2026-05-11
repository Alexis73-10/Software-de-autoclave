#este archivo creara el CRUD para la tabla control_config_global tanto en backend
import logging
from autoclave.db.config_db import config_global_db
import datetime

logging.basicConfig(level=logging.DEBUG)

fech_cr= datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
fech_mod= datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

class ControlConfigGlobalDB:
    def __init__(self, nombre_db='autoclave_vapor.db'):
        self.nombre_db = nombre_db
        logging.info("ControlConfigGlobalDB initialized.")
        
    def verificar_tabla(self):
        # Verifica si la tabla 'config_global' existe en la base de datos
        conn = config_global_db.sql.connect(self.nombre_db)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='config_global';")
        tabla_existe = cursor.fetchone() is not None
        conn.close()
        logging.info(f"Tabla 'config_global' existe: {tabla_existe}")
        return tabla_existe
    
    def crear_tabla_config_global(self):
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
        
    def crear_tabla_si_no_existe(self):
        if not self.verificar_tabla():
            self.crear_tabla_config_global()
            logging.info("Tabla 'config_global' creada.")
        else:
            logging.info("La tabla 'config_global' ya existe. No se creó una nueva.")

    def crear_configuracion(self, clave, valor, tipo_dato, estado, usuario_creacion):
        # Crea una nueva configuración en la tabla 'config_global'
        conn = config_global_db.sql.connect(self.nombre_db)
        cursor = conn.cursor()
        fecha_creacion = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO config_global (Clave, Valor, Tipo_Dato, Estado, Fecha_Creacion, Usuario_Creacion)
            VALUES (?, ?, ?, ?, ?, ?);
        """, (clave, valor, tipo_dato, estado, fecha_creacion, usuario_creacion))
        conn.commit()
        conn.close()
        logging.info(f"Configuración '{clave}' creada.")


    def leer_configuraciones(self):
        # Lee todas las configuraciones de la tabla 'config_global'
        conn = config_global_db.sql.connect(self.nombre_db)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM config_global;")
        configuraciones = cursor.fetchall()
        conn.close()
        logging.info(f"Configuraciones leídas: {configuraciones}")
        return configuraciones
    
    def leer_configuracion_por_id(self, config_id):
        # Lee una configuración específica por ID
        conn = config_global_db.sql.connect(self.nombre_db)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM config_global WHERE id = ?;", (config_id,))
        configuracion = cursor.fetchone()
        conn.close()
        logging.info(f"Configuración leída por ID {config_id}: {configuracion}")
        return configuracion
    
    def leer_configuracion_por_clave(self, clave):
        # Lee una configuración específica por Clave
        conn = config_global_db.sql.connect(self.nombre_db)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM config_global WHERE Clave = ?;", (clave,))
        configuracion = cursor.fetchone()
        conn.close()
        logging.info(f"Configuración leída por Clave {clave}: {configuracion}")
        return configuracion
    
    def leer_configuracion_por_estado(self, estado):
        # Lee configuraciones específicas por Estado
        conn = config_global_db.sql.connect(self.nombre_db)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM config_global WHERE Estado = ?;", (estado,))
        configuraciones = cursor.fetchall()
        conn.close()
        logging.info(f"Configuraciones leídas por Estado {estado}: {configuraciones}")
        return configuraciones

    def actualizar_configuracion(self, config_id, valor, estado, usuario_actualizacion):
        # Actualiza una configuración específica
        conn = config_global_db.sql.connect(self.nombre_db)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE config_global
            SET Valor = ?, Estado = ?, Fecha_actualizacion = ?, Usuario_actualizacion = ?
            WHERE id = ?;
        """, (valor, estado, fech_mod, usuario_actualizacion, config_id))
        conn.commit()
        conn.close()
        logging.info(f"Configuración con ID {config_id} actualizada.")
        
    def actualizar_estado_configuracion(self, config_id, estado, usuario_actualizacion):
        # Actualiza solo el estado de una configuración específica
        conn = config_global_db.sql.connect(self.nombre_db)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE config_global
            SET Estado = ?, Fecha_actualizacion = ?, Usuario_actualizacion = ?
            WHERE id = ?;
        """, (estado, fech_mod, usuario_actualizacion, config_id))
        conn.commit()
        conn.close()
        logging.info(f"Estado de configuración con ID {config_id} actualizado a {estado}.")
        
    def actualizar_valor_configuracion(self, config_id, valor, usuario_actualizacion):
        # Actualiza solo el valor de una configuración específica
        conn = config_global_db.sql.connect(self.nombre_db)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE config_global
            SET Valor = ?, Fecha_actualizacion = ?, Usuario_actualizacion = ?
            WHERE id = ?;
        """, (valor, fech_mod, usuario_actualizacion, config_id))
        conn.commit()
        conn.close()
        logging.info(f"Valor de configuración con ID {config_id} actualizado a {valor}.")
        
    def eliminar_configuracion(self, config_id):
        # Elimina una configuración específica
        conn = config_global_db.sql.connect(self.nombre_db)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM config_global WHERE id = ?;", (config_id,))
        conn.commit()
        conn.close()
        logging.info(f"Configuración con ID {config_id} eliminada.")
    
    def eliminar_configuracion_por_clave(self, clave):
        # Elimina una configuración específica por Clave
        conn = config_global_db.sql.connect(self.nombre_db)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM config_global WHERE Clave = ?;", (clave,))
        conn.commit()
        conn.close()
        logging.info(f"Configuración con Clave {clave} eliminada.")
        
    def eliminar_configuracion_por_estado(self, estado):
        # Elimina configuraciones específicas por Estado
        conn = config_global_db.sql.connect(self.nombre_db)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM config_global WHERE Estado = ?;", (estado,))
        conn.commit()
        conn.close()
        logging.info(f"Configuraciones con Estado {estado} eliminadas.")
        
    def eliminar_todas_configuraciones(self):
        # Elimina todas las configuraciones de la tabla 'config_global'
        conn = config_global_db.sql.connect(self.nombre_db)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM config_global;")
        conn.commit()
        conn.close()
        logging.info("Todas las configuraciones eliminadas de 'config_global'.")

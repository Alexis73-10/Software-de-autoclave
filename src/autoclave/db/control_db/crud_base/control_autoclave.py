#este archivo dreara el CRUD para la tabla autoclave en backend 
#crud: create, read, update, delete
from autoclave.db.config_db import config_global_db
import datetime
import logging

logging.basicConfig(level=logging.DEBUG)
fech_cr= datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
fech_mod= datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

class ControlAutoclaveDB:
    def __init__(self, nombre_db='autoclave_vapor.db'):
        self.nombre_db = nombre_db
        logging.info("ControlAutoclaveDB initialized.")
        
    def verificar_tabla(self):
        # Verifica si la tabla 'autoclave' existe en la base de datos
        conn = config_global_db.sql.connect(self.nombre_db)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='autoclave';")
        tabla_existe = cursor.fetchone() is not None
        conn.close()
        logging.info(f"Tabla 'autoclave' existe: {tabla_existe}")
        return tabla_existe
    
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
        
    def crear_tabla_si_no_existe(self):
        if not self.verificar_tabla():
            self.tabla_autoclave()
            logging.info("Tabla 'autoclave' creada.")
        else:
            logging.info("La tabla 'autoclave' ya existe. No se creó una nueva.")
            
    def leer_autoclaves(self):
        # Lee todos los autoclaves de la tabla 'autoclave'
        conn = config_global_db.sql.connect(self.nombre_db)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM autoclave;")
        autoclaves = cursor.fetchall()
        conn.close()
        logging.info(f"Autoclaves leídos: {autoclaves}")
        return autoclaves
    
    def leer_autoclave_por_id(self, autoclave_id):
        # Lee un autoclave específico por ID
        conn = config_global_db.sql.connect(self.nombre_db)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM autoclave WHERE id = ?;", (autoclave_id,))
        autoclave = cursor.fetchone()
        conn.close()
        logging.info(f"Autoclave leído por ID {autoclave_id}: {autoclave}")
        return autoclave
    
    def leer_autoclave_por_modelo(self, modelo):
        # Lee un autoclave específico por modelo
        conn = config_global_db.sql.connect(self.nombre_db)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM autoclave WHERE Modelo = ?;", (modelo,))
        autoclave = cursor.fetchone()
        conn.close()
        logging.info(f"Autoclave leído por modelo {modelo}: {autoclave}")
        return autoclave
    
    def leer_autoclave_por_serie(self, serie):
        # Lee un autoclave específico por serie
        conn = config_global_db.sql.connect(self.nombre_db)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM autoclave WHERE Serie = ?;", (serie,))
        autoclave = cursor.fetchone()
        conn.close()
        logging.info(f"Autoclave leído por serie {serie}: {autoclave}")
        return autoclave
    
    def crear_autoclave(self, nombre, modelo, capacidad, estado):
        # Crea un nuevo autoclave en la tabla 'autoclave'
        conn = config_global_db.sql.connect(self.nombre_db)
        cursor = conn.cursor()
        fecha_creacion = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO autoclave (Nombre, Modelo, Serie, Numero_puertas, Estado, Fecha_Creacion)
            VALUES (?, ?, ?, ?, ?, ?);
        """, (nombre, modelo, capacidad, estado, fecha_creacion))
        conn.commit()
        conn.close()
        logging.info(f"Autoclave creado: {nombre}, {modelo}, {capacidad}, {estado}")
        
    def actualizar_autoclave(self, autoclave_id, nombre=None, modelo=None, capacidad=None, estado=None):
        # Actualiza un autoclave existente en la tabla 'autoclave'
        conn = config_global_db.sql.connect(self.nombre_db)
        cursor = conn.cursor()
        fecha_actualizacion = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        campos_a_actualizar = []
        valores = []
        
        if nombre is not None:
            campos_a_actualizar.append("Nombre = ?")
            valores.append(nombre)
        if modelo is not None:
            campos_a_actualizar.append("Modelo = ?")
            valores.append(modelo)
        if capacidad is not None:
            campos_a_actualizar.append("Serie = ?")
            valores.append(capacidad)
        if estado is not None:
            campos_a_actualizar.append("Estado = ?")
            valores.append(estado)
        
        campos_a_actualizar.append("Fecha_actualizacion = ?")
        valores.append(fecha_actualizacion)
        
        valores.append(autoclave_id)
        
        sql_update = f"UPDATE autoclave SET {', '.join(campos_a_actualizar)} WHERE id = ?;"
        cursor.execute(sql_update, tuple(valores))
        conn.commit()
        conn.close()
        logging.info(f"Autoclave actualizado ID {autoclave_id} con valores: {valores[:-1]}")
        
    def eliminar_autoclave(self, autoclave_id):
        # Elimina un autoclave de la tabla 'autoclave'
        conn = config_global_db.sql.connect(self.nombre_db)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM autoclave WHERE id = ?;", (autoclave_id,))
        conn.commit()
        conn.close()
        logging.info(f"Autoclave eliminado ID {autoclave_id}")
        

#DB_autoclave/creacion.py

import sqlite3 as sql
import logging 

logging.basicConfig(level=logging.DEBUG)


def crear_base_datos(autoclave_vapor):  #Crea la base de datos para el autoclave de vapor
    conn = sql.connect(autoclave_vapor)
    conn.commit()
    logging.info("Base de datos creada exitosamente.")
    conn.close()
    
def crear_tabla(nombre, campos, id=True):  #Crea una tabla en la base de datos
    conn = sql.connect('autoclave_vapor.db')
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    if id:
        campos = "id INTEGER PRIMARY KEY, " + campos
    
    consulta = f"CREATE TABLE IF NOT EXISTS {nombre} ({campos})"
    cursor.execute(consulta)
    
    conn.commit()
    logging.info(f"Tabla '{nombre}' creada exitosamente.")
    conn.close()
    
def borrar_tabla(nombre):  #Elimina una tabla de la base de datos
    conn = sql.connect('autoclave_vapor.db')
    cursor = conn.cursor()
    
    consulta = f"DROP TABLE IF EXISTS {nombre}"
    cursor.execute(consulta)
    
    conn.commit()
    logging.info(f"Tabla '{nombre}' eliminada exitosamente.")
    conn.close()

def verificar_si_db_existe(nombre_db):
    try:
        conn = sql.connect(nombre_db)
        conn.close()
        logging.info(f"La base de datos '{nombre_db}' existe.")
        return True
    except sql.Error as e:
        logging.error(f"Error al conectar a la base de datos '{nombre_db}': {e}")
        return False


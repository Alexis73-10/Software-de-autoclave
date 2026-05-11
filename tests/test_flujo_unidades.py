#tests/test_flujo_unidades.py
import time
from autoclave.protocols.serial_link import SerialLink
from autoclave.hal.units import Units

# Creamos la instancia de Units que manejará los datos convertidos
units = Units("src/autoclave/config/calibration.yaml")

# Callback que recibe los datos crudos del serial
def on_update(data):
    units.update_from_serial(data) # Actualiza los datos en unidades físicas
    estado = units.get_all() # Obtiene todos los datos convertidos

    temp = estado["temperature"]
    pres = estado["pressure"]

    print(f"🌡️ Temp[0]: {temp[0]:6.2f} °C | ⛽ Pres[0]: {pres[0]:6.2f} kPa | "
          f"Conectado: {estado['connected']}")
    
# Creamos y lanzamos el enlace serial
link = SerialLink(on_update=on_update)
link._scan_ports = lambda: "COM7"  # Fuerza el puerto correcto

print("🚀 Iniciando flujo de lectura desde ESP32...")
link.start()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n🛑 Deteniendo comunicación...")
    link.stop()


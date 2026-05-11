# test_enviar_comando.py
from autoclave.protocols.serial_link import SerialLink
import time

def on_update(data):
    """Callback opcional para ver los cambios en DO."""
    print("📊 Estado actualizado:", data["do"])

# Crear enlace serial con el ESP32
link = SerialLink(
    baudrate=115200,
    scan_interval=3.0,
    on_update=on_update
)

print("🔌 Conectando con ESP32...")
link.start()

# Esperar a que conecte
time.sleep(3)

if not link.data["connected"]:
    print("❌ No se pudo conectar al ESP32.")
else:
    print("✅ Conectado. Enviando comandos...")

    # Alternar una salida digital (por ejemplo DO1)
    print("⚡ Activando DO1...")
    link.set_output(1, True)
    time.sleep(2)

    print("💤 Apagando DO1...")
    link.set_output(1, False)

    # Esperar un poco para ver respuesta
    time.sleep(2)

print("🛑 Deteniendo comunicación...")
link.stop()

from src.autoclave.protocols.serial_link import SerialLink
import time

# Forzamos el patrón de escaneo al puerto detectado manualmente
class SerialLinkForzado(SerialLink):
    def _scan_ports(self):
        return "COM3" # <--- puerto detectado

def on_update(data):
    print("📡 Datos recibidos:", data["ai"][:4], "...")

if __name__ == "__main__":
    link = SerialLinkForzado(on_update=on_update)
    link.start()

    print("🔌 Esperando datos del ESP32... (Ctrl+C para salir)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        link.stop()
        print("\n🛑 Comunicación detenida.")

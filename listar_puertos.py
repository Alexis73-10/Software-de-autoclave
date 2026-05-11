import serial.tools.list_ports

print("🔍 Puertos seriales disponibles:\n")
for port in serial.tools.list_ports.comports():
    print(f" - {port.device} | {port.description}")

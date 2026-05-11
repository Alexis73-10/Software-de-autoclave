import tkinter as tk
import Interfaz as interfaz

class VentanaEmergente:

        ventana_secundaria=tk.Toplevel(interfaz.ventana)
        ventana_secundaria.title("Ventana Secundaria")
        ventana_secundaria.geometry("300x200")
        etiqueta=tk.Label(ventana_secundaria, text="Esta es una ventana secundaria")
        etiqueta.pack(pady=20)
        boton_cerrar=tk.Button(ventana_secundaria, text="Cerrar", command=ventana_secundaria.destroy)
        boton_cerrar.pack(pady=10)
        
    
def abrir_ventana_secundaria():
    VentanaEmergente()
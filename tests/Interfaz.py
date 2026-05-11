import tkinter as tk
import logging 

# Configuración del logger
logging.basicConfig(level=logging.DEBUG)
#-----------------------------------------------------------------------------------------------

ventana = tk.Tk()

menu_boton = tk.Menubutton(ventana, text="Menú")
menu_boton.pack()


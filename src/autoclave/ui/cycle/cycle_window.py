#src/autoclave/ui/cycle_window.py

#interfaz para el ciclo de esterilizacion
import tkinter as tk
import customtkinter as ctk
import PIL.Image as image
import logging
import autoclave.ui.components.components as components

# Configuracion del logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CycleWindow(tk.Toplevel):
    #ventana para el ciclo de esterilizacion
    #abrira una nueva ventana desde la ventana principal
    #abrira en pantalla completa
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.title("Ciclo de Esterilización")
        self.geometry("1280x720")
        self.configure(bg="#b6ccd9")
        self.attributes("-fullscreen", True)


        components._crear_encabezado(self, "Ciclo de Esterilización")
        self._layout_cycle_info()
        components._crear_pie_pagina(self)
        
    def _layout_cycle_info(self):
        fondo = components._crear_fondo_principal(self)
        
        def boton_stop_cycle():
            #funcion para detener el ciclo de esterilizacion
            #creacion del boton para iniciar el ciclo
            #este boton estara en la parte inferior derecha del contenedor fondo, separado del borde derecho por un espacio correspondiente al 4.5% del ancho del contenedor fondo
            #y separado del borde inferior por un espacio correspondiente al 5% de la altura del contenedor fondo
            #tendra una imagen de inicio hubicada en src/autoclave/images/stop_cycle.png
            img= ctk.CTkImage(
                light_image=image.open("src/autoclave/images/stop_cycle.png"),
                dark_image=image.open("src/autoclave/images/stop_cycle.png"),
                size=(100, 100),
            )
            #el boton al ser presionado llamara a la funcion stop_cycle
            boton_iniciar = ctk.CTkButton(
                fondo,
                text="",
                image=img,
                compound="left",
                #banco
                fg_color="white",
                #gris claro
                hover_color="lightgray",
                command=self.stop_cycle
            )
            boton_iniciar.place(
                relx=0.85,
                rely=0.73,
                relwidth=0.1,
                relheight=0.18,
            )
        boton_stop_cycle()
        
    def stop_cycle(self):
        #funcion para detener el ciclo de esterilizacion
        logger.info("⏹️ Ciclo de esterilización detenido por el usuario.")
        self.destroy()
        
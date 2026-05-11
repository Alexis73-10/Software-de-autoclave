import tkinter as tk
import customtkinter as ctk
import PIL.Image as image
from autoclave.services.persistence.config_global.ser_config_global import config_global, session

import logging
import autoclave.ui.components.components as components

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__) 

class ReadConfigGlobal(tk.Toplevel):
    def __init__(self, parent, root ):
        super().__init__(parent)
        self.parent = parent
        self.root = root
        self.title("Leer Configuración Global")
        self.geometry("400x500")
        self.configure(bg="#b6ccd9")
        self.attributes("-fullscreen", True)

        self.session = session
        components._crear_encabezado(self, "Leer Configuración Global")
        self.layout_config()
        self._pie_page()
        
    
    def layout_config (self):
        # Crear fondo principal
        fondo = components._crear_fondo_principal(self)
        
        #este metodo recibira un diccionario con los datos de la configuracion global
        # y mostrara una tabla con los datos de la configuracion global
        datos_config = config_global.get_all_dict(self.session)
        tabla = components._crear_tabla(fondo, datos_config)
        
    def _pie_page(self):
        pie = components._crear_pie_pagina(self)
        
        def back_to_menu():
            #crear boton para volver al menu principal 
            #con imagen ubicada en D:\Documentos_y_Código\Código\Python\Proyectos_Funcionales\codigo_autoclave\src\autoclave\images\back_icon.png
            img = ctk.CTkImage(
                light_image=image.open("src/autoclave/images/back_icon.png"),
                dark_image=image.open("src/autoclave/images/back_icon.png"),
                size=(80, 40))
            back_btn = ctk.CTkButton(
                pie, 
                corner_radius=50,
                text="",
                image=img,
                fg_color="#5789a7",
                hover_color="#406080",
                command= self.cerrar_ventana
            )
        
            back_btn.place(
                relx=0.95, 
                rely=0.5, 
                anchor="e",  #alinear a la derecha
                relwidth=0.1,
                relheight=0.6
                )
        back_to_menu()
        
        def home_btn ():
            #crear boton para volver al menu principal 
            #con imagen ubicada en D:\Documentos_y_Código\Código\Python\Proyectos_Funcionales\codigo_autoclave\src\autoclave\images\home_icon.png
            img = ctk.CTkImage(
                light_image=image.open("src/autoclave/images/home_icon.png"),
                dark_image=image.open("src/autoclave/images/home_icon.png"),
                size=(80, 40))
            home_btn = ctk.CTkButton(
                pie, 
                corner_radius=50,
                text="",
                image=img,
                fg_color="#5789a7",
                hover_color="#406080",
                command= self.home
            )
        
            home_btn.place(
                relx=0.1, 
                rely=0.5, 
                anchor="w",  #alinear a la izquierda
                relwidth=0.1,
                relheight=0.6
                )
        home_btn()
        
    def cerrar_ventana(self):
        self.parent.deiconify()
        self.parent.grab_set()
        self.destroy()
    
    def home(self):
        #esta funcion cierra la ventana actual y todas las hijas, y abre la ventana principal sin reiniciar la aplicacion
        #esto se logra cerrando todas las ventanas hijas y mostrando la ventana principal
        for window in self.root.winfo_children():
            if isinstance(window, tk.Toplevel):
                window.destroy()
                
        self.root.deiconify()
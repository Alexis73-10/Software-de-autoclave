#este archivo creara la interfaz grafica para la gestion de config_global
#src/autoclave/ui/ui_db/config_global/create_config.py
#sera la interfaz para la creacion de nuevas configuraciones globales en la base de datos
import tkinter as tk
import customtkinter as ctk
import PIL.Image as image
from autoclave.services.persistence.config_global.ser_config_global import config_global, session

import logging
import autoclave.ui.components.components as components

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CreateConfigGlobal(tk.Toplevel):
    def __init__(self, parent,root):
        super().__init__(parent)
        self.parent = parent
        self.root = root
        self.title("Crear Configuración Global")
        self.geometry("400x500")
        self.configure(bg="#b6ccd9")
        self.attributes("-fullscreen", True)
        

        self.session = session
        components._crear_encabezado(self, "Crear Configuración Global")
        self.layout_widgets()
        self._pie_page()


    def layout_widgets(self):
        # Crear fondo principal
        fondo = components._crear_fondo_principal(self)

        labels = [
            "Clave",
            "Valor",
            "Tipo_dato",
            "Estado",
            "Usuario",
            
        ]

        #crear las entradas y etiquetas
        #las entradas se guardaran en un diccionario
        #la clave sera el nombre del campo y el valor sera la entrada
        #se crearan frames para cada etiqueta y entrada, y se empaquetaran en el fondo principal
        #el contenido de los frames estara: etiqueta a la izquierda y entrada a la derecha
        #cada frame tendra un tamaño correspondiente al 90% del ancho del fondo principal y una altura correspondiente al 10% de la altura del fondo principal
        #y un espacio correspondiente al 2% de la altura del fondo principal entre cada frame
        # las etiquetas tendran un ancho correspondiente al 30% del ancho del frame y una altura correspondiente al 90% de la altura del frame
        
        self.entries = {}
        for label in labels:
            place = (0.05, 0.05 + (labels.index(label) * 0.12), 0.9, 0.1)
            frame = components._frame_widgets(fondo, place)
            entry = components._label_entry(frame, label)
            self.entries[label] = entry
        # Crear botón de guardar
        guardar_btn = ctk.CTkButton(
            fondo,
            text="Guardar Configuración",
            command=lambda: config_global._guardar_config_global(self, self.entries)
        )
        guardar_btn.place(relx=0.5, rely=0.85, anchor=tk.CENTER)
        
        cancelar_btn = ctk.CTkButton(
            fondo,
            text="Cancelar",
            # cerrar ventana actual
            command=self.cerrar_ventana
            
        )
        cancelar_btn.place(relx=0.5, rely=0.92, anchor=tk.CENTER)
        
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
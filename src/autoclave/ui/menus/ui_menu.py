#esta interfas gestiona los menus de la aplicacion
import tkinter as tk
import customtkinter as ctk
import autoclave.ui.db.ui_config_global as ui_config_global
import autoclave.ui.components.components as components
from autoclave.ui.db.ui_usuario import UIUsuario

import logging
import PIL.Image as image

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UIMenu(tk.Toplevel):
    def __init__(self, parent,root):
        super().__init__()
        self.parent = parent
        self.root = root
        self.title("Menú Principal")
        self.geometry("1280x720")
        self.configure(bg="#b6ccd9")
        self.attributes("-fullscreen", True)
        
        
        components._crear_encabezado(self, "Menú Principal")
        self.layout_menu()
        self.pie_pagina()

        
    def layout_menu(self):
        fondo = components._crear_fondo_principal(self)
        
        def create_widgets(fondo):
            # titulo menu principal centrado, en la parte superior del contenedor fondo
            label_title = ctk.CTkLabel(
                fondo,
                text="Menú Principal",
                font=ctk.CTkFont(size=60, weight="bold"),
                fg_color="white",
                bg_color="white",
                text_color="black"
            )
            label_title.place(relx=0.5, rely=0.05, anchor="n")
        create_widgets(fondo)
            
        def boton_config_global(fondo):
            #funcion para abrir la ventana de configuracion global
            #creacion del boton para abrir la ventana de configuracion global
            boton = components._crear_boton_menu(
                fondo,
                "Configuración Global",
                comando=self.open_config_global,
                posicion=(0.1, 0.25, 0.8, 0.1),
            )
        boton_config_global(fondo)
        
        def boton_gestion_usuarios(fondo):
            #funcion para abrir la ventana de gestion de usuarios
            boton = components._crear_boton_menu(
                fondo,
                "Gestión de Usuarios",
                comando=self.open_gestion_usuarios,
                posicion=(0.1, 0.4, 0.8, 0.1),
            )
        boton_gestion_usuarios(fondo)
        
    def pie_pagina(self):
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


    def open_config_global(self):
        self.withdraw()
        config_window = ui_config_global.UIConfigGlobal(self, self.root)
        config_window.grab_set()
        
    def open_gestion_usuarios(self):
        self.withdraw()
        gestion_usuarios_window = UIUsuario(self, self.root)
        gestion_usuarios_window.grab_set()
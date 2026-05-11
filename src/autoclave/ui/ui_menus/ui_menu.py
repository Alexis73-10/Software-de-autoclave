#esta interfas gestiona los menus de la aplicacion
import tkinter as tk
import customtkinter as ctk
import src.autoclave.ui.ui_db.ui_config_global as ui_config_global
import autoclave.ui.components.components as components
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UIMenu(tk.Toplevel):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.title("Menú Principal")
        self.geometry("1280x720")
        self.configure(bg="#b6ccd9")
        self.attributes("-fullscreen", True)
        
        
        components._crear_encabezado(self, "Menú Principal")
        self.layout_menu()
        self.pie_pagina()

        
    def layout_menu(self):
        fondo = components._crear_fondo_principal(
            self,
            rx=0.04,
            ry=0.066,
            rw=0.92,
            rh=0.7525,
        )
        
        def create_widgets(fondo):
            # titulo menu principal centrado, en la parte superior del contenedor fondo
            label_title = ctk.CTkLabel(
                fondo,
                text="Menú Principal",
                font=ctk.CTkFont(size=60, weight="bold"),
                fg_color="white",
                bg_color="#000000",
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
                rx=0.35,
                ry=0.3,
                rw=0.3,
                rh=0.15,
            )
        boton_config_global(fondo)
        
    def pie_pagina(self):
        pie = components._crear_pie_pagina(self,0.2,0.85,0.6,0.12)

        #tendra 1 boton a la derecha para cerrar el menu y volver a la ventana principal
        boton_cerrar = ctk.CTkButton(
            pie,
            text="Cerrar Menú",
            font=ctk.CTkFont(size=20, weight="bold"),
            fg_color="#ff5c5c",
            hover_color="#ff1a1a",
            command=lambda: (print("Cerrando menú..."), self.destroy())
            
        )
        boton_cerrar.place(relx=0.9, rely=0.92, anchor="center")
        
    def open_config_global(self):
        config_window = ui_config_global.UIConfigGlobal(self)
        config_window.grab_set()
                
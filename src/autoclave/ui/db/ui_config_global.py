#src/autoclave/ui/ui_db/ui_config_global.py

#este modulo creara la interfaz grafica para la gestion de config_global
#por la curva de aprendizaje utilizaremos tkinter y customtkinter
import tkinter as tk
import customtkinter as ctk
import logging
import autoclave.ui.components.components as components
import autoclave.ui.db.config_global.create_config as create_config
import autoclave.ui.db.config_global.read_config as read_config
import autoclave.ui.db.config_global.update_config as update_config
import autoclave.ui.db.config_global.delete_config as delete_config
import PIL.Image as image



logger = logging.getLogger(__name__)

class UIConfigGlobal(tk.Toplevel):
    def __init__(self, parent, root):
        super().__init__(parent)
        self.parent = parent
        self.root = root
        self.title("Configuración Global")
        self.geometry("600x400")
        self.configure(bg="#b6ccd9")
        self.attributes("-fullscreen", True)
        
        
        components._crear_encabezado(self, "Configuración Global")
        self.create_widgets()
        self._pie_page_()

    def create_widgets(self):
        fondo = components._crear_fondo_principal(self)
        
        def create_title(fondo):
            self.label_title = ctk.CTkLabel(fondo, text="Configuración Global", font=ctk.CTkFont(size=20, weight="bold"))
            self.label_title.pack(pady=10)

        def create_buttons(fondo):
            crear_config = components._crear_boton_menu(
                fondo,
                "Crear Nueva Configuración", 
                self._create_config_,
                posicion=(0.1, 0.1, 0.8, 0.1))
            
            leer_config = components._crear_boton_menu(
                fondo,
                "Leer Configuración Existente", 
                comando=self._ui_read_config_,
                posicion=(0.1, 0.25, 0.8, 0.1))
            
            actualizar_config = components._crear_boton_menu(
                fondo,
                "Actualizar Configuración ",
                comando=self._update_config_,
                posicion=(0.1, 0.4, 0.8, 0.1))
            
            borrar_config = components._crear_boton_menu(
                fondo,
                "Borrar Configuración ",
                comando= self.delete_config,
                posicion=(0.1, 0.55, 0.8, 0.1))

        create_buttons(fondo)
    
    def _pie_page_(self):
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
    

        
    def _ui_read_config_(self):
        self.withdraw()
        ui_read = read_config.ReadConfigGlobal(self, self.root)
        ui_read.grab_set()
    
    def _create_config_(self):
        self.withdraw()
        ui_create = create_config.CreateConfigGlobal(self, self.root)
        ui_create.grab_set()
        #cierra la ventada de configuracion global al abrir la ventana de crear nueva configuracion global
        #despues de 1 segundo
    
    def _update_config_(self): 
        self.withdraw()
        ui_update = update_config.UpdateConfigGlobal(self, self.root)
        ui_update.grab_set()

    def delete_config(self):
        self.withdraw()
        ui_delete = delete_config.DeleteConfigGlobal(self, self.root)
        ui_delete.grab_set()
            
    def cerrar_ventana(self):
        self.parent.deiconify()
        self.parent.grab_set()
        self.destroy()
import tkinter as tk
import customtkinter as ctk
import PIL.Image as image
import logging
import autoclave.ui.components.components as components

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
class UIUsuario(tk.Toplevel):
    def __init__(self, parent, root):
        super().__init__(parent)
        self.parent = parent
        self.root = root
        self.title("Gestión de Usuarios")
        self.geometry("600x400")
        self.configure(bg="#b6ccd9")
        self.attributes("-fullscreen", True)
        
        components._crear_encabezado(self, "Gestión de Usuarios")
        self.create_widgets()
        self._pie_page_()

    def create_widgets(self):
        fondo = components._crear_fondo_principal(self)
        
        def create_title(fondo):
            self.label_title = ctk.CTkLabel(fondo, text="Gestión de Usuarios", font=ctk.CTkFont(size=20, weight="bold"))
            self.label_title.pack(pady=10)

        def create_buttons(fondo):
            crear_usuario = components._crear_boton_menu(
                fondo,
                "Crear Nuevo Usuario", 
                self._create_user_,
                posicion=(0.1, 0.1, 0.8, 0.1))
            
            leer_usuario = components._crear_boton_menu(
                fondo,
                "Leer Usuario Existente", 
                comando=self._ui_read_user_,
                posicion=(0.1, 0.25, 0.8, 0.1))
            
            actualizar_usuario = components._crear_boton_menu(
                fondo,
                "Actualizar Usuario ",
                comando=self._update_user_,
                posicion=(0.1, 0.4, 0.8, 0.1))
            
            borrar_usuario = components._crear_boton_menu(
                fondo,
                "Borrar Usuario ",
                comando= self.delete_user,
                posicion=(0.1, 0.55, 0.8, 0.1))

        create_title(fondo)
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
        
    def _create_user_(self):
        logger.info("Funcionalidad de crear usuario no implementada aún.")
        
    def _ui_read_user_(self):
        logger.info("Funcionalidad de leer usuario no implementada aún.")
        
    def _update_user_(self):
        logger.info("Funcionalidad de actualizar usuario no implementada aún.")
        
    def delete_user(self):
        logger.info("Funcionalidad de borrar usuario no implementada aún.")
        
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
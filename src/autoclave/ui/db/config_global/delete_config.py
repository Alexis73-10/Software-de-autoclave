import tkinter as tk
import customtkinter as ctk
import PIL.Image as image
from autoclave.services.persistence.config_global.ser_config_global import config_global, session
import logging
import autoclave.ui.components.components as components

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DeleteConfigGlobal(tk.Toplevel):
    def __init__(self, parent,root):
        super().__init__(parent)
        self.parent = parent
        self.root = root
        self.title("Eliminar Configuración Global")
        self.geometry("400x500")
        self.configure(bg="#b6ccd9")
        self.attributes("-fullscreen", True)
        

        self.session = session
        components._crear_encabezado(self, "Eliminar Configuración Global")
        self.layout_widgets()
        self._pie_page()


    def layout_widgets(self):
        # Crear fondo principal
        fondo = components._crear_fondo_principal(self)

        labels = [
            "ID"
        ]
            
        self.entries = {}
        for label in labels:
            place = (0.05, 0.05 + (labels.index(label) * 0.12), 0.9, 0.1)
            frame = components._frame_widgets(fondo, place)
            entry = components._label_entry(frame, label)
            self.entries[label] = entry
        # Crear boton de confirmar
        confirmar_btn = ctk.CTkButton(
            fondo,
            text=" Confirmar",
            command=self.confirm,
            fg_color="#4caf50",
            hover_color="#45a049"
        )
        confirmar_btn.place(relx=0.35, rely=0.85, relwidth=0.3, relheight=0.08)
        
    def confirm(self):
        config_id = self.entries["ID"].get()
        config = config_global.confirm_delete(self, config_id)
        if config:
            self.entries["ID"].configure(state="disabled")
            self.show_config_info(config)
            
        # mostrar la informacion del retun de confirm_delete almacenada en config
        #al mostrar la informacion, deshabilitar la entrada del ID y cambiar el boton confirmar por un boton guardar
    def show_config_info(self, config):
        #si la configuracion existe, mostrar la informacion en label
        if not config:
            info_text = (f"No se encontró la configuración global con ID {self.entries['ID'].get()}.")
        else:
            info_text = (
                f"Clave: {config.Clave}\n"
                f"Valor: {config.Valor}\n"
                f"Tipo de Dato: {config.Tipo_dato}\n"
                f"Estado: {config.Estado}\n"
                f"Usuario Actualización: {config.Usuario_actualizacion}\n"
            )
        info_label = ctk.CTkLabel(
            self,
            text=info_text,
            text_color="#000000",
            fg_color="#f0f0f0",
            corner_radius=10,
            padx=10,
            pady=10
        )
        info_label.place(relx=0.05, rely=0.6, relwidth=0.9, relheight=0.2)

    def delete_config_global(self, config_id):
        config_global.delete_config_global(self, config_id)
        #limpiar entry y quitar info_label
        self.entries["ID"].configure(state="normal")
        self.entries["ID"].delete(0, tk.END)
        for widget in self.winfo_children():
            if isinstance(widget, ctk.CTkLabel) and widget != self.label_title:
                widget.destroy()
    
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
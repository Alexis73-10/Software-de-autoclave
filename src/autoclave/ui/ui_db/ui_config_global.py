#src/autoclave/ui/ui_db/ui_config_global.py

#este modulo creara la interfaz grafica para la gestion de config_global
#por la curva de aprendizaje utilizaremos tkinter y customtkinter
import tkinter as tk
import customtkinter as ctk
import src.autoclave.services.control_db as control_db
import logging

logger = logging.getLogger(__name__)

class UIConfigGlobal(tk.Toplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("Configuración Global")
        self.geometry("600x400")
        self.create_widgets()
        self.load_config_global()

    def create_widgets(self):
        self.label_title = ctk.CTkLabel(self, text="Configuración Global", font=ctk.CTkFont(size=20, weight="bold"))
        self.label_title.pack(pady=10)

        self.frame_form = ctk.CTkFrame(self)
        self.frame_form.pack(pady=10, padx=10, fill="both", expand=True)

        self.label_param1 = ctk.CTkLabel(self.frame_form, text="Parámetro 1:")
        self.label_param1.grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.entry_param1 = ctk.CTkEntry(self.frame_form)
        self.entry_param1.grid(row=0, column=1, padx=5, pady=5)

        self.label_param2 = ctk.CTkLabel(self.frame_form, text="Parámetro 2:")
        self.label_param2.grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.entry_param2 = ctk.CTkEntry(self.frame_form)
        self.entry_param2.grid(row=1, column=1, padx=5, pady=5)

        self.button_save = ctk.CTkButton(self, text="Guardar", command=self.save_config_global)
        self.button_save.pack(pady=10)

    def load_config_global(self):
        try:
            config = control_db.get_config_global()
            if config:
                self.entry_param1.insert(0, config.param1)
                self.entry_param2.insert(0, config.param2)
            else:
                logger.warning("No se encontró configuración global.")
        except Exception as e:
            logger.error(f"Error al cargar configuración global: {e}")

    def save_config_global(self):
        param1 = self.entry_param1.get()
        param2 = self.entry_param2.get()
        try:
            control_db.update_config_global(param1, param2)
            logger.info("Configuración global guardada exitosamente.")
        except Exception as e:
            logger.error(f"Error al guardar configuración global: {e}")
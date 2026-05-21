# src/autoclave/ui/cycle_window.py
# Ventana de ciclo de esterilización

import tkinter as tk
import customtkinter as ctk
import PIL.Image as image
import logging
import autoclave.ui.components.components as components
from autoclave.utils.resources import resource_path

logger = logging.getLogger(__name__)


class CycleWindow(tk.Toplevel):
    """Ventana de ciclo — se abre sobre la ventana principal."""

    def __init__(self, parent):
        super().__init__(parent)          # parent correcto para grab_set y ciclo de vida
        self.parent = parent
        self.title("Ciclo de Esterilización")
        self.configure(bg="#b6ccd9")
        self.attributes("-fullscreen", True)

        components._crear_encabezado(self, "Ciclo de Esterilización")
        self._layout_cycle_info()
        components._crear_pie_pagina(self)

    def _layout_cycle_info(self):
        fondo = components._crear_fondo_principal(self)

        img = ctk.CTkImage(
            light_image=image.open(resource_path("autoclave/images/stop_cycle.png")),
            dark_image=image.open(resource_path("autoclave/images/stop_cycle.png")),
            size=(100, 100),
        )

        ctk.CTkButton(
            fondo,
            text="",
            image=img,
            compound="left",
            fg_color="white",
            hover_color="lightgray",
            command=self.stop_cycle,
        ).place(relx=0.85, rely=0.73, relwidth=0.1, relheight=0.18)

    def stop_cycle(self):
        logger.info("Ciclo de esterilizacion detenido por el usuario.")
        self.destroy()

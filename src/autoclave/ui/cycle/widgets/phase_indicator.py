# ui/cycle/widgets/phase_indicator.py
#
# Pill oscura que muestra la fase activa del ciclo y el timer X/Y Min.
#
# Layout:  [ PRECALENTAMIENTO ·············  1 / 5 Min ]

import customtkinter as ctk

CLR_DARK = "#2d4757"
CLR_W    = "white"


class PhaseIndicator(ctk.CTkFrame):
    """
    Pill oscura con nombre de fase (izquierda) y timer X/Y Min (derecha).
    Uso:
        ind = PhaseIndicator(parent, bg_color="#ffffff")
        ind.place(...)
        ind.update("ESTERILIZACION", elapsed_min=2.5, total_min=5.0)
    """

    def __init__(self, parent, bg_color: str = "#ffffff",
                 font_size_label: int = 22, font_size_timer: int = 20, **kwargs):
        super().__init__(
            parent,
            corner_radius=30,
            fg_color=CLR_DARK,
            bg_color=bg_color,
            **kwargs,
        )
        self._font_size_label = font_size_label
        self._font_size_timer = font_size_timer

        self._lbl_fase = ctk.CTkLabel(
            self,
            text="---",
            font=("Segoe UI", font_size_label, "bold"),
            text_color=CLR_W,
            fg_color="transparent",
            anchor="w",
        )
        self._lbl_fase.pack(side="left", padx=24, pady=0, fill="y")

        self._lbl_timer = ctk.CTkLabel(
            self,
            text="",
            font=("Segoe UI", font_size_timer),
            text_color=CLR_W,
            fg_color="transparent",
            anchor="e",
        )
        self._lbl_timer.pack(side="right", padx=24, pady=0, fill="y")

    # ------------------------------------------------------------------

    def update(self, fase: str, elapsed_min: float, total_min: float):
        """
        Modo tiempo: muestra progreso del sostenimiento  "X / Y Min".

        fase        : nombre interno de la fase ('PRECALENTAMIENTO', etc.)
        elapsed_min : minutos transcurridos desde que empezó el sostenimiento
        total_min   : duración total configurada para la fase (0 = desconocida)
        """
        nombre = fase.replace("_", " ").title() if fase else "---"
        self._lbl_fase.configure(text=nombre)

        if total_min and total_min > 0:
            self._lbl_timer.configure(
                text=f"{elapsed_min:.0f} / {total_min:.0f} Min"
            )
        else:
            if elapsed_min > 0:
                self._lbl_timer.configure(text=f"{elapsed_min:.0f} Min")
            else:
                self._lbl_timer.configure(text="")

    def update_info(self, fase: str, info_text: str):
        """
        Modo informativo: muestra texto libre en el lado derecho.
        Útil para fases con progreso no basado en tiempo ni temperatura.

        Ejemplo:  PRE VACIO  ·············  A  1/4
        """
        nombre = fase.replace("_", " ").title() if fase else "---"
        self._lbl_fase.configure(text=nombre)
        self._lbl_timer.configure(text=info_text if info_text else "")

    def update_approach(self, fase: str, current_val, target_val, unit: str = "°C"):
        """
        Modo aproximación: muestra el valor actual vs el objetivo
        mientras la fase aún no alcanzó las condiciones.

        Ejemplo:  PRECALENTAMIENTO  ·······  87 / 121 °C
        """
        nombre = fase.replace("_", " ").title() if fase else "---"
        self._lbl_fase.configure(text=nombre)

        if current_val is not None and target_val:
            self._lbl_timer.configure(
                text=f"{current_val:.0f} / {target_val:.0f} {unit}"
            )
        else:
            self._lbl_timer.configure(text="Alcanzando...")

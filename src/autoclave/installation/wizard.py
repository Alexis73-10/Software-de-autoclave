# src/autoclave/installation/wizard.py
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import logging

from .profile import InstallationProfile, Role
from .storage import save
from .activation import validate_code

logger = logging.getLogger(__name__)


def launch_installation_wizard() -> bool:
    """
    Show the two-step installation wizard.
    Returns True if installation completed successfully, False if cancelled.
    """
    result = {"done": False}

    root = tk.Tk()
    root.title("Instalación — Autoclave Especifika")
    root.resizable(False, False)
    root.grab_set()

    # ── Variables ──────────────────────────────────────────────────────────
    serial_var         = tk.StringVar()
    code_var           = tk.StringVar()
    model_var          = tk.StringVar()
    door_count_var     = tk.IntVar(value=2)
    door_type_var      = tk.StringVar(value="advanced")
    equipment_type_var = tk.StringVar(value="horizontal")
    drying_type_var    = tk.StringVar(value="vacuum")
    door_id_var        = tk.IntVar(value=1)

    # ── PASO 1: Código de activación ───────────────────────────────────────
    frame1 = tk.Frame(root, padx=30, pady=20)

    tk.Label(
        frame1, text="Instalación del equipo",
        font=("", 14, "bold")
    ).pack(pady=(0, 20))

    tk.Label(frame1, text="Número de serie del equipo:", anchor="w").pack(fill="x")
    tk.Entry(frame1, textvariable=serial_var, width=35).pack(fill="x", pady=(0, 12))

    tk.Label(frame1, text="Código de activación:", anchor="w").pack(fill="x")
    tk.Entry(frame1, textvariable=code_var, width=35).pack(fill="x", pady=(0, 16))

    err1 = tk.Label(frame1, text="", fg="red")
    err1.pack()

    def ir_a_paso2():
        serial = serial_var.get().strip()
        code   = code_var.get().strip()
        if not serial:
            err1.config(text="Ingrese el número de serie")
            return
        if not code:
            err1.config(text="Ingrese el código de activación")
            return
        if not validate_code(serial, code):
            err1.config(text="Código de activación incorrecto")
            logger.warning("Intento de instalación con código inválido para serie '%s'", serial)
            return
        err1.config(text="")
        frame1.pack_forget()
        frame2.pack()

    tk.Button(frame1, text="Siguiente →", command=ir_a_paso2, width=20).pack(pady=(10, 0))

    # ── PASO 2: Datos del equipo ───────────────────────────────────────────
    frame2 = tk.Frame(root, padx=30, pady=20)

    tk.Label(
        frame2, text="Datos del equipo",
        font=("", 14, "bold")
    ).pack(pady=(0, 16))

    def fila(label_text, widget_factory):
        f = tk.Frame(frame2)
        tk.Label(f, text=label_text, width=22, anchor="w").pack(side="left")
        w = widget_factory(f)
        w.pack(side="left", fill="x", expand=True)
        f.pack(fill="x", pady=4)

    fila("Modelo:", lambda p: tk.Entry(p, textvariable=model_var))
    fila("N° de puertas:", lambda p: ttk.Spinbox(
        p, from_=1, to=2, textvariable=door_count_var, width=6, state="readonly"))
    fila("Tipo de puerta:", lambda p: ttk.Combobox(
        p, textvariable=door_type_var,
        values=["simple", "advanced"], state="readonly"))
    fila("Tipo de equipo:", lambda p: ttk.Combobox(
        p, textvariable=equipment_type_var,
        values=["horizontal", "vertical"], state="readonly"))
    fila("Tipo de secado:", lambda p: ttk.Combobox(
        p, textvariable=drying_type_var,
        values=["vacuum", "gravity"], state="readonly"))
    fila("Puerta de este PC (1/2):", lambda p: ttk.Spinbox(
        p, from_=1, to=2, textvariable=door_id_var, width=6, state="readonly"))

    err2 = tk.Label(frame2, text="", fg="red")
    err2.pack(pady=(10, 0))

    def instalar():
        model = model_var.get().strip()
        if not model:
            err2.config(text="El modelo es obligatorio")
            return

        serial = serial_var.get().strip().upper()
        profile = InstallationProfile(
            machine_id=f"ACV-{datetime.utcnow().strftime('%Y')}-{serial}",
            model_id=model,
            serial_number=serial,
            door_count=door_count_var.get(),
            door_type=door_type_var.get(),
            equipment_type=equipment_type_var.get(),
            drying_type=drying_type_var.get(),
            door_id=door_id_var.get(),
            role=Role.OPERATOR_FRONT,
            created_at=datetime.utcnow(),
            locked=True,
        )

        try:
            save(profile)
        except Exception as e:
            err2.config(text=f"Error al guardar: {e}")
            logger.error("Error guardando perfil de instalación: %s", e)
            return

        result["done"] = True
        logger.info("Instalación completada para serie '%s'", serial)
        messagebox.showinfo(
            "Instalación completada",
            "El equipo ha sido registrado correctamente.\n"
            "Reinicie el software para continuar."
        )
        root.destroy()

    tk.Button(
        frame2, text="Instalar", command=instalar,
        width=20, bg="#27ae60", fg="white", font=("", 10, "bold")
    ).pack(pady=(14, 0))

    frame1.pack()
    root.mainloop()

    return result["done"]

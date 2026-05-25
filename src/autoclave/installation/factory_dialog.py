# src/autoclave/installation/factory_dialog.py
import tkinter as tk
from tkinter import messagebox

from .activation import validate_factory_key


def launch_factory_dialog(serial_number: str) -> bool:
    """
    Show the factory key entry dialog for the given serial number.
    Returns True if a valid factory key was entered, False if cancelled.
    The factory key is valid only for today — it must be generated fresh each time.
    """
    result = {"granted": False}

    root = tk.Tk()
    root.title("Acceso de fabricante — Autoclave Especifika")
    root.resizable(False, False)
    root.grab_set()

    frame = tk.Frame(root, padx=30, pady=20)
    frame.pack()

    tk.Label(frame, text="Acceso de fabricante", font=("", 14, "bold")).pack(pady=(0, 16))
    tk.Label(frame, text=f"Serial: {serial_number}", fg="gray").pack(pady=(0, 12))

    tk.Label(frame, text="Clave de fabricante:", anchor="w").pack(fill="x")
    key_var = tk.StringVar()
    tk.Entry(frame, textvariable=key_var, width=30, show="*").pack(fill="x", pady=(0, 12))

    err_label = tk.Label(frame, text="", fg="red")
    err_label.pack()

    def verificar():
        key = key_var.get().strip()
        if not key:
            err_label.config(text="Ingrese la clave")
            return
        if validate_factory_key(serial_number, key):
            result["granted"] = True
            messagebox.showinfo("Acceso concedido", "Modo fabricante activado.")
            root.destroy()
        else:
            err_label.config(text="Clave incorrecta o expirada")

    tk.Button(frame, text="Verificar", command=verificar, width=20).pack(pady=(8, 4))
    tk.Button(frame, text="Cancelar", command=root.destroy, width=20).pack()

    root.mainloop()
    return result["granted"]

# src/autoclave/installation/wizard.py
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import logging

from .profile import InstallationProfile, Role
from .equipment import EquipmentClass, get_capabilities
from .storage import save
from .activation import validate_installation_code
from autoclave.devices.puertas.door_type import DoorType

logger = logging.getLogger(__name__)

_EQUIPMENT_LABELS = {
    EquipmentClass.MESA_N:     "Mesa Clase N",
    EquipmentClass.MESA_B:     "Mesa Clase B",
    EquipmentClass.MESA_B_LAB: "Mesa Clase B Laboratorio",
    EquipmentClass.PISO:       "Piso",
    EquipmentClass.PISO_LAB:   "Piso Laboratorio",
}

def launch_installation_wizard() -> bool:
    result = {"done": False}

    root = tk.Tk()
    root.title("Instalación — Autoclave Especifika")
    root.resizable(False, False)
    root.grab_set()

    # ── Variables ──────────────────────────────────────────────────────────
    serial_var       = tk.StringVar()
    code_var         = tk.StringVar()
    model_var        = tk.StringVar()
    door_count_var   = tk.IntVar(value=1)
    door_type_var    = tk.StringVar(value=DoorType.ADVANCED.value)
    equipment_var    = tk.StringVar(value=EquipmentClass.MESA_B.value)
    cooling_var      = tk.IntVar(value=0)
    door_id_var      = tk.IntVar(value=1)

    # Estado compartido derivado del perfil seleccionado
    _cap_holder = [None]  # cap actual, actualizado en paso 2

    # ── PASO 1: Código de activación ───────────────────────────────────────
    frame1 = tk.Frame(root, padx=30, pady=20)

    tk.Label(frame1, text="Instalación del equipo",
             font=("", 14, "bold")).pack(pady=(0, 20))
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
            err1.config(text="Ingrese el número de serie"); return
        if not code:
            err1.config(text="Ingrese el código de activación"); return
        if not validate_installation_code(serial, code):
            err1.config(text="Código de activación incorrecto o expirado")
            logger.warning("Intento de instalación con código inválido para serie '%s'", serial)
            return
        err1.config(text="")
        frame1.pack_forget()
        frame2.pack()

    tk.Button(frame1, text="Siguiente →", command=ir_a_paso2, width=20).pack(pady=(10, 0))

    # ── PASO 2: Selección de perfil ────────────────────────────────────────
    frame2 = tk.Frame(root, padx=30, pady=20)

    tk.Label(frame2, text="Perfil de equipo",
             font=("", 14, "bold")).pack(pady=(0, 12))
    tk.Label(frame2, text="Seleccione el tipo de equipo:", anchor="w").pack(fill="x")

    for ec in EquipmentClass:
        cap_preview = get_capabilities(ec)
        cap_str = (
            f"{'Vacío ' if cap_preview.has_vacuum else ''}"
            f"{'Chaqueta ' if cap_preview.has_full_jacket else ''}"
            f"{'Líquidos ' if cap_preview.has_liquids else ''}"
            f"Puertas: {cap_preview.door_count_max}"
        ).strip()
        ttk.Radiobutton(
            frame2,
            text=f"{_EQUIPMENT_LABELS[ec]}  ({cap_str})",
            variable=equipment_var,
            value=ec.value,
        ).pack(anchor="w", pady=2)

    err2 = tk.Label(frame2, text="", fg="red")
    err2.pack(pady=(8, 0))

    def ir_a_paso3():
        ec_value = equipment_var.get()
        cap = get_capabilities(EquipmentClass(ec_value))
        _cap_holder[0] = cap
        # Ajustar defaults condicionados por cap
        door_count_var.set(min(door_count_var.get(), cap.door_count_max))
        cooling_var.set(min(cooling_var.get(), cap.cooling_level_max))
        err2.config(text="")
        frame2.pack_forget()
        frame3.pack()
        _actualizar_frame3(cap)

    tk.Button(frame2, text="Siguiente →", command=ir_a_paso3, width=20).pack(pady=(10, 0))

    # ── PASO 3: Configuración de puertas ───────────────────────────────────
    frame3 = tk.Frame(root, padx=30, pady=20)

    tk.Label(frame3, text="Configuración de puertas",
             font=("", 14, "bold")).pack(pady=(0, 12))

    _door_count_frame = tk.Frame(frame3)
    _door_count_frame.pack(fill="x", pady=4)
    tk.Label(_door_count_frame, text="N° de puertas:", width=22, anchor="w").pack(side="left")
    _door_count_spin = ttk.Spinbox(_door_count_frame, from_=1, to=2,
                                   textvariable=door_count_var, width=6, state="readonly")
    _door_count_spin.pack(side="left")

    _door_type_frame = tk.Frame(frame3)
    _door_type_frame.pack(fill="x", pady=4)
    tk.Label(_door_type_frame, text="Tipo de puerta:", width=22, anchor="w").pack(side="left")
    _door_type_combo = ttk.Combobox(
        _door_type_frame, textvariable=door_type_var,
        values=[dt.value for dt in DoorType], state="readonly"
    )
    _door_type_combo.pack(side="left", fill="x", expand=True)

    err3 = tk.Label(frame3, text="", fg="red")
    err3.pack(pady=(8, 0))

    def _actualizar_frame3(cap):
        if cap.door_count_max == 1:
            door_count_var.set(1)
            _door_count_spin.config(state="disabled")
        else:
            _door_count_spin.config(state="readonly")

    def ir_a_paso4():
        err3.config(text="")
        cap = _cap_holder[0]
        frame3.pack_forget()
        if cap.cooling_level_max == 0:
            frame4.pack_forget()
            _mostrar_frame5()
        else:
            _actualizar_frame4(cap)
            frame4.pack()

    tk.Button(frame3, text="Siguiente →", command=ir_a_paso4, width=20).pack(pady=(10, 0))

    # ── PASO 4: Configuración de enfriamiento (opcional) ──────────────────
    frame4 = tk.Frame(root, padx=30, pady=20)

    tk.Label(frame4, text="Configuración de enfriamiento",
             font=("", 14, "bold")).pack(pady=(0, 12))
    tk.Label(frame4, text="Nivel de enfriamiento (0 = sin enfriamiento):",
             anchor="w").pack(fill="x")

    _cooling_spin = ttk.Spinbox(frame4, from_=0, to=4,
                                textvariable=cooling_var, width=6, state="readonly")
    _cooling_spin.pack(anchor="w", pady=(4, 0))

    def _actualizar_frame4(cap):
        _cooling_spin.config(to=cap.cooling_level_max)

    err4 = tk.Label(frame4, text="", fg="red")
    err4.pack(pady=(8, 0))

    def ir_a_paso5():
        frame4.pack_forget()
        _mostrar_frame5()

    tk.Button(frame4, text="Siguiente →", command=ir_a_paso5, width=20).pack(pady=(10, 0))

    # ── PASO 5: Datos finales ──────────────────────────────────────────────
    frame5 = tk.Frame(root, padx=30, pady=20)

    tk.Label(frame5, text="Datos del equipo",
             font=("", 14, "bold")).pack(pady=(0, 16))

    def fila(parent, label_text, widget_factory):
        f = tk.Frame(parent)
        tk.Label(f, text=label_text, width=22, anchor="w").pack(side="left")
        w = widget_factory(f)
        w.pack(side="left", fill="x", expand=True)
        f.pack(fill="x", pady=4)

    fila(frame5, "Modelo:", lambda p: tk.Entry(p, textvariable=model_var))

    _door_id_row = tk.Frame(frame5)
    tk.Label(_door_id_row, text="Puerta de este PC (1/2):", width=22, anchor="w").pack(side="left")
    _door_id_spin = ttk.Spinbox(_door_id_row, from_=1, to=2,
                                textvariable=door_id_var, width=6, state="readonly")
    _door_id_spin.pack(side="left")
    _door_id_row.pack(fill="x", pady=4)

    def _mostrar_frame5():
        cap = _cap_holder[0]
        _door_id_spin.config(to=cap.door_count_max)
        door_id_var.set(min(door_id_var.get(), cap.door_count_max))
        frame5.pack()

    err5 = tk.Label(frame5, text="", fg="red")
    err5.pack(pady=(10, 0))

    def instalar():
        model = model_var.get().strip()
        if not model:
            err5.config(text="El modelo es obligatorio"); return

        serial = serial_var.get().strip().upper()
        profile = InstallationProfile(
            machine_id=f"ACV-{datetime.utcnow().strftime('%Y')}-{serial}",
            model_id=model,
            serial_number=serial,
            equipment_class=EquipmentClass(equipment_var.get()),
            door_count=door_count_var.get(),
            door_type=DoorType(door_type_var.get()),
            cooling_level=cooling_var.get(),
            door_id=door_id_var.get(),
            role=Role.OPERATOR_FRONT,
            created_at=datetime.utcnow(),
            locked=True,
        )

        try:
            save(profile)
        except Exception as e:
            err5.config(text=f"Error al guardar: {e}")
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

    tk.Button(frame5, text="Instalar", command=instalar,
              width=20, bg="#27ae60", fg="white",
              font=("", 10, "bold")).pack(pady=(14, 0))

    frame1.pack()
    root.mainloop()
    return result["done"]

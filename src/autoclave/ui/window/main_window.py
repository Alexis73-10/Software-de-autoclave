# autoclave/ui/main_window.py

import time
import tkinter as tk
import customtkinter as ctk
import PIL.Image as Image
from PIL import ImageTk
import logging

from autoclave.ui.cycle.cycle_window import CycleWindow
from autoclave.utils.resources import resource_path

logger = logging.getLogger(__name__)

# ── Paleta ────────────────────────────────────────────────────────────────────
CLR_BG      = "#b6ccd9"   # fondo azul-grisáceo
CLR_DARK    = "#2d4757"   # panel oscuro y pills
CLR_CARD    = "#ffffff"   # tarjeta blanca principal
CLR_FOOTER  = "#5789a7"   # barra footer
CLR_W       = "white"
CLR_B       = "black"

_MAX_COND   = 5           # máximo de condiciones/alarmas visibles en panel izq.


# ══════════════════════════════════════════════════════════════════════════════
class InterfazPrincipal(tk.Tk):
# ══════════════════════════════════════════════════════════════════════════════

    def __init__(self, ui_service, door_commands, on_shutdown=None, source_door=1):
        super().__init__()
        self._on_shutdown  = on_shutdown
        self.ui_service    = ui_service
        self.door_commands = door_commands
        self._source_door  = source_door                      # 1 o 2
        self._door_name    = f"Puerta {source_door}"          # "Puerta 1" o "Puerta 2"

        # ── ventana ───────────────────────────────────────────────────────────
        self.title("Autoclave de vapor")
        self.configure(bg=CLR_BG)
        self.attributes("-fullscreen", True)
        self.update_idletasks()                               # forzar render antes de medir pantalla

        # ── estado interno ────────────────────────────────────────────────────
        self.cycle_name = self.ui_service.get_cycle_param("name") or "Cargando..."

        # ── construir UI ──────────────────────────────────────────────────────
        self._build_header()
        self._build_body()
        self._build_footer()

        # ── arrancar loop ─────────────────────────────────────────────────────
        self.after(300, self._load_action_images)   # cargar imágenes después de fullscreen
        self.after(500, self._update_ui)

        logger.info("✅ Interfaz creada correctamente.")

    # ══════════════════════════════════════════════════════════════════════════
    # HEADER
    # ══════════════════════════════════════════════════════════════════════════

    def _build_header(self):
        hdr = tk.Frame(self, bg=CLR_DARK, height=58)
        hdr.pack(fill=tk.X, side=tk.TOP)
        hdr.pack_propagate(False)

        tk.Label(hdr, text="ESPECIFIKA S.A.S",
                 font=("Segoe UI", 14, "italic"),
                 bg=CLR_DARK, fg=CLR_W).pack(side=tk.LEFT, padx=20)

        self._lbl_modelo = tk.Label(hdr, text="AUTOCLAVE",
                                     font=("Segoe UI", 16, "bold"),
                                     bg=CLR_DARK, fg=CLR_W)
        self._lbl_modelo.pack(side=tk.LEFT, expand=True)

        self._lbl_hora = tk.Label(hdr, text="",
                                   font=("Segoe UI", 14),
                                   bg=CLR_DARK, fg=CLR_W)
        self._lbl_hora.pack(side=tk.RIGHT, padx=20)
        self._tick_hora()

    def _tick_hora(self):
        self._lbl_hora.config(text=time.strftime("%d/%m/%Y   %I:%M:%S %p"))
        self.after(1000, self._tick_hora)

    # ══════════════════════════════════════════════════════════════════════════
    # BODY  (fondo azul → tarjeta blanca → panel izq + panel der)
    # ══════════════════════════════════════════════════════════════════════════

    def _build_body(self):
        self._body_bg = tk.Frame(self, bg=CLR_BG)
        self._body_bg.pack(fill=tk.BOTH, expand=True)

        # tarjeta blanca con bordes redondeados
        self._card = ctk.CTkFrame(self._body_bg, corner_radius=28,
                                   fg_color=CLR_CARD, bg_color=CLR_BG)
        self._card.place(relx=0.02, rely=0.03, relwidth=0.96, relheight=0.94)

        self._build_left_panel()
        self._build_right_panel()

    # ── Panel izquierdo ───────────────────────────────────────────────────────

    def _build_left_panel(self):
        pnl = ctk.CTkFrame(self._card, corner_radius=22,
                            fg_color=CLR_DARK, bg_color=CLR_CARD)
        pnl.place(relx=0.02, rely=0.04, relwidth=0.26, relheight=0.92)

        # número de ciclo
        self._lbl_n_ciclo = ctk.CTkLabel(
            pnl, text="01",
            font=("Segoe UI", 90, "bold"),
            text_color=CLR_W, fg_color="transparent")
        self._lbl_n_ciclo.place(relx=0.5, rely=0.20, anchor="center")

        # estado de máquina
        self._lbl_estado = ctk.CTkLabel(
            pnl, text="Cargando...",
            font=("Segoe UI", 22, "bold"),
            text_color=CLR_W, fg_color="transparent",
            wraplength=190)
        self._lbl_estado.place(relx=0.5, rely=0.43, anchor="center")

        # alarmas y condiciones dinámicas
        self._lbl_cond = []
        for i in range(_MAX_COND):
            lbl = ctk.CTkLabel(
                pnl, text="",
                font=("Segoe UI", 16),
                text_color=CLR_W, fg_color="transparent")
            lbl.place(relx=0.5, rely=0.57 + i * 0.082, anchor="center")
            self._lbl_cond.append(lbl)

    # ── Panel derecho ─────────────────────────────────────────────────────────

    def _build_right_panel(self):
        pnl = ctk.CTkFrame(self._card, corner_radius=0,
                            fg_color=CLR_CARD, bg_color=CLR_CARD)
        pnl.place(relx=0.30, rely=0.04, relwidth=0.68, relheight=0.92)
        self._panel_der = pnl

        # título del ciclo
        self._lbl_ciclo_nombre = ctk.CTkLabel(
            pnl, text=self.cycle_name.upper(),
            font=("Segoe UI", 46, "bold"),
            text_color=CLR_B, fg_color="transparent")
        self._lbl_ciclo_nombre.place(relx=0.5, rely=0.09, anchor="center")

        # línea separadora
        ctk.CTkFrame(pnl, fg_color="#cccccc", corner_radius=0,
                     bg_color=CLR_CARD).place(
            relx=0.01, rely=0.19, relwidth=0.98, relheight=0.004)

        # ── pills parámetros ciclo (columna izquierda) ────────────────────────
        PX, PW, PH = 0.01, 0.46, 0.135
        rows = [0.26, 0.43, 0.60]

        self._val_temp_ester   = self._pill(pnl, "Temp. Ester",   "---", "°C",  PX, rows[0], PW, PH)
        self._val_tiempo_ester = self._pill(pnl, "Tiempo. Ester", "---", "min", PX, rows[1], PW, PH)
        self._val_tiempo_sec   = self._pill(pnl, "Tiempo. Sec",   "---", "min", PX, rows[2], PW, PH)

        # ── pills sensores (columna derecha) ──────────────────────────────────
        SX = 0.52
        self._val_temp_cam = self._pill(pnl, "Temp.",   "---", "°C",  SX, rows[0], PW, PH)
        self._val_temp_ref = self._pill(pnl, "Temp. 1", "---", "°C",  SX, rows[1], PW, PH)
        self._val_pres_cam = self._pill(pnl, "Presión", "---", "kPa", SX, rows[2], PW, PH)

        # ── botones de acción (tk.Label para evitar conflictos z-order con CTK) ─
        self._boton_puerta = tk.Label(pnl, bg=CLR_CARD, cursor="hand2")
        self._boton_puerta.bind("<Button-1>", lambda e: self._accion_puerta_1())
        self._boton_puerta.bind("<Enter>", lambda e: self._boton_puerta.configure(bg=CLR_BG))
        self._boton_puerta.bind("<Leave>", lambda e: self._boton_puerta.configure(bg=CLR_CARD))
        self._boton_puerta.place(relx=0.05, rely=0.76, relwidth=0.16, relheight=0.21)

        self._boton_iniciar = tk.Label(pnl, bg=CLR_CARD, cursor="")
        self._boton_iniciar.bind("<Enter>", lambda e: self._boton_iniciar.configure(bg=CLR_BG) if self._inicio_habilitado else None)
        self._boton_iniciar.bind("<Leave>", lambda e: self._boton_iniciar.configure(bg=CLR_CARD))
        self._boton_iniciar.place(relx=0.79, rely=0.76, relwidth=0.16, relheight=0.21)
        self._inicio_habilitado = False

    def _pill(self, parent, label, value, unit, relx, rely, relwidth, relheight):
        """
        Pill oscura con:  [ Label ·····  valor  unidad ]
        Retorna el CTkLabel del valor para actualizarlo.
        """
        frame = ctk.CTkFrame(parent, corner_radius=30,
                            fg_color=CLR_DARK, bg_color=CLR_CARD)
        frame.place(relx=relx, rely=rely, relwidth=relwidth, relheight=relheight)

        ctk.CTkLabel(frame, text=label,
                     font=("Segoe UI", 18, "bold"),
                     text_color=CLR_W, fg_color="transparent",
                     anchor="w").place(relx=0.05, rely=0.5, anchor="w")

        ctk.CTkLabel(frame, text=unit,
                     font=("Segoe UI", 15),
                     text_color=CLR_W, fg_color="transparent",
                     anchor="e").place(relx=0.97, rely=0.5, anchor="e")

        lbl_val = ctk.CTkLabel(frame, text=value,
                                font=("Segoe UI", 20, "bold"),
                                text_color=CLR_W, fg_color="transparent",
                                anchor="e")
        lbl_val.place(relx=0.74, rely=0.5, anchor="e")

        return lbl_val

    # ══════════════════════════════════════════════════════════════════════════
    # FOOTER
    # ══════════════════════════════════════════════════════════════════════════

    def _build_footer(self):
        footer = tk.Frame(self, bg=CLR_BG, height=90)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        footer.pack_propagate(False)

        # píldora central
        pill = ctk.CTkFrame(footer, corner_radius=45,
                             fg_color=CLR_FOOTER, bg_color=CLR_BG)
        pill.place(relx=0.5, rely=0.5, anchor="center",
                   relwidth=0.52, relheight=0.82)

        # cargar iconos footer
        def _ico(name, size=(46, 40)):
            img = Image.open(resource_path(f"autoclave/images/{name}"))
            return ctk.CTkImage(light_image=img, dark_image=img, size=size)

        self._img_info     = _ico("info_icon.png")
        self._img_settings = _ico("settings_icon.png")
        self._img_OFF     = _ico("power_icon.png")

        ctk.CTkButton(pill, text="", image=self._img_info,
                      fg_color="transparent", hover_color="#406080",
                      width=56).pack(side=tk.LEFT, padx=18)

        ctk.CTkButton(pill, text="", image=self._img_settings,
                      fg_color="transparent", hover_color="#406080",
                      width=56).pack(side=tk.LEFT, padx=8)

        ctk.CTkButton(pill, text="", image=self._img_OFF,
                      fg_color="transparent", hover_color="#406080",
                      command=self.apagar_equipo,
                      width=56).pack(side=tk.RIGHT, padx=18)

        # indicador de conexión
        self._lbl_conexion = tk.Label(footer, text="⚪ Conectando...",
                                       font=("Segoe UI", 12),
                                       bg=CLR_BG, fg="white")
        self._lbl_conexion.place(relx=0.01, rely=0.5, anchor="w")

    # ══════════════════════════════════════════════════════════════════════════
    # IMÁGENES DE BOTONES DE ACCIÓN (cargadas después de render)
    # ══════════════════════════════════════════════════════════════════════════

    def _load_action_images(self):
        try:
            # forzar que la ventana esté completamente renderizada
            self.update()

            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            bw = max(80, int(sw * 0.085))
            bh = max(80, int(sh * 0.15))

            logger.info("Cargando imagenes de botones (%dx%d)...", bw, bh)

            def _ico(name):
                path = resource_path(f"autoclave/images/{name}")
                img = Image.open(path)
                # mantener proporción original: caber dentro de bw×bh sin deformar
                img.thumbnail((bw, bh), Image.LANCZOS)
                return ImageTk.PhotoImage(img)

            # usar imágenes de puerta 1 o puerta 2 según SOURCE_DOOR
            n = self._source_door
            self._img_puerta_ab = _ico(f"open_door_{n}.png")
            self._img_puerta_ce = _ico(f"close_door_{n}.png")
            self._img_start     = _ico("start_cycle.png")

            self._boton_iniciar.configure(image=self._img_start)
            self._boton_puerta.lift()    # traer al frente sobre CTkFrame internos
            self._boton_iniciar.lift()
            self._actualizar_imagen_puerta()

            logger.info("Imagenes de botones cargadas correctamente")

        except Exception as e:
            logger.error("Error cargando imagenes de botones: %s", e, exc_info=True)

    # ══════════════════════════════════════════════════════════════════════════
    # ACCIONES
    # ══════════════════════════════════════════════════════════════════════════

    def _accion_puerta_1(self):
        estado = self.ui_service.get_estado_puerta(self._door_name)
        if estado == "ABIERTO":
            self.door_commands.close(self._door_name)
        else:
            self.door_commands.open(self._door_name)

    def start_cycle(self):
        logger.info("▶️ Iniciando ciclo...")
        w = CycleWindow(self)
        w.grab_set()

    def apagar_equipo(self):
        logger.info("⏻ Apagando equipo...")
        self.withdraw()
        win = tk.Toplevel(self)
        win.attributes("-fullscreen", True)
        win.configure(bg="#37596C")
        win.wm_attributes("-alpha", 0.92)
        ctk.CTkLabel(win, text="Apagando equipo...",
                     font=("Segoe UI", 42, "bold"),
                     bg_color="#37596C", fg_color="#37596C",
                     text_color=CLR_W).pack(expand=True)

        def _shutdown():
            if self._on_shutdown:
                self._on_shutdown()   # on_close() ya llama app.destroy()
            else:
                self.destroy()        # solo si no hay callback externo

        win.after(3000, _shutdown)

    # ══════════════════════════════════════════════════════════════════════════
    # LOOP DE ACTUALIZACIÓN
    # ══════════════════════════════════════════════════════════════════════════

    def _update_ui(self):
        if not hasattr(self, "_tick"):
            self._tick = 0
        self._tick += 1

        self._upd_conexion()

        if self.ui_service.connected:
            try:
                # cada 500 ms
                self._upd_sensores()

                # cada 1 s
                if self._tick % 2 == 0:
                    self._upd_ciclo_nombre()
                    self._upd_params_ciclo()
                    self._upd_panel_izquierdo()
                    self._upd_listo()
                    self._actualizar_imagen_puerta()

            except Exception as e:
                logger.warning("⚠️ Error UI loop: %s", e)

        self.after(500, self._update_ui)

    # ── helpers de actualización ──────────────────────────────────────────────

    def _upd_conexion(self):
        if self.ui_service.connected:
            self._lbl_conexion.configure(text="🟢 Conectado",    fg="#7FFF7F")
        else:
            self._lbl_conexion.configure(text="🔴 Sin conexión", fg="#FF7F7F")

    def _upd_ciclo_nombre(self):
        nombre = self.ui_service.get_cycle_param("name")
        if nombre and nombre != self.cycle_name:
            self.cycle_name = nombre
            self._lbl_ciclo_nombre.configure(text=self.cycle_name.upper())

    def _upd_sensores(self):
        def _f(v):
            return f"{v:.1f}" if v is not None else "---"

        t = self.ui_service.get_sensores_temp()
        p = self.ui_service.get_sensores_pres()
        self._val_temp_cam.configure(text=_f(t.get("temp_camara")))
        self._val_temp_ref.configure(text=_f(t.get("temp_ref")))
        self._val_pres_cam.configure(text=_f(p.get("pres_camara")))

    def _upd_params_ciclo(self):
        def _f(v):
            if v == "---":
                return "---"
            return str(int(v)) if isinstance(v, float) and v == int(v) else str(v)

        self._val_temp_ester.configure(  text=_f(self._cycle_param("temperatura_esterilizacion")))
        self._val_tiempo_ester.configure(text=_f(self._cycle_param("tiempo_esterilizacion")))
        self._val_tiempo_sec.configure(  text=_f(self._cycle_param("tiempo_secado")))

    def _upd_panel_izquierdo(self):
        # estado de máquina
        estado = self.ui_service.get_estado_global()
        self._lbl_estado.configure(text=estado.replace("_", " ").title())

        conds = []

        # puertas: solo cuando NO están cerradas
        for nombre in ("Puerta 1", "Puerta 2"):
            ep = self.ui_service.get_estado_puerta(nombre)
            if ep and ep not in ("CERRADO", "DESCONOCIDO"):
                conds.append(f"{nombre}: {ep.title()}")

        # alarmas activas del sistema
        for alarma in self.ui_service.get_alarmas()[:_MAX_COND]:
            conds.append(f"⚠ {alarma.get('id', '')}")

        # actualizar labels
        for i, lbl in enumerate(self._lbl_cond):
            lbl.configure(text=conds[i] if i < len(conds) else "")

    def _upd_listo(self):
        ok = self.ui_service.get_estado_flag("LISTO_PARA_CICLO")
        self._boton_iniciar.configure(state="normal" if ok else "disabled")

    def _actualizar_imagen_puerta(self):
        if not hasattr(self, "_img_puerta_ab"):
            return
        estado = self.ui_service.get_estado_puerta(self._door_name)
        img = self._img_puerta_ce if estado == "CERRADO" else self._img_puerta_ab
        self._boton_puerta.configure(image=img)
        self._boton_puerta.update_idletasks()

    # ══════════════════════════════════════════════════════════════════════════
    # HELPERS
    # ══════════════════════════════════════════════════════════════════════════

    def _cycle_param(self, param):
        """Busca parámetro en estructura plana o anidada del ciclo."""
        params = self.ui_service.get_cycle().get("parameters", {})
        entry = params.get(param)
        if isinstance(entry, dict) and "value" in entry:
            return entry["value"]
        for section in params.values():
            if isinstance(section, dict):
                entry = section.get(param)
                if isinstance(entry, dict) and "value" in entry:
                    return entry["value"]
        return "---"

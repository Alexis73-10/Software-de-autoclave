# autoclave/ui/main_window.py

import time
import tkinter as tk
import customtkinter as ctk
import PIL.Image as Image
from PIL import ImageTk
import logging

from autoclave.ui.cycle.cycle_window import CycleWindow

from autoclave.utils.resources import resource_path
from autoclave.ui.layout import (
    is_portrait, font_scale, scaled_font,
    check_orientation_changed,
    load_footer_icons,
)

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
        self.cycle_name        = self.ui_service.get_cycle_param("name") or "Cargando..."
        self._prev_machine_state = ""
        self._cycle_win          = None
        self._toast_widget       = None

        self._scale            = 1.0   # factor de escala de fuente, calculado en _build_ui
        self._current_portrait = None  # None = no determinado todavía
        self._update_job       = None  # handle del after() del loop de polling
        self._resize_job       = None  # handle del debounce de <Configure>
        self._tick             = 0

        # ── construir UI ──────────────────────────────────────────────────────
        self._build_ui()

        # ── arrancar loop e imagen ────────────────────────────────────────────
        self.after(300, self._load_action_images)
        self._schedule_update()

        # ── detección de orientación (para ambos monitores) ───────────────────
        self.bind("<Configure>", self._on_configure)

        logger.info("✅ Interfaz creada correctamente.")

    # ══════════════════════════════════════════════════════════════════════════
    # PUNTO DE ENTRADA DE CONSTRUCCIÓN
    # ══════════════════════════════════════════════════════════════════════════

    def _build_ui(self):
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self._scale = font_scale(sw, sh)
        self._build_header(sh)
        if is_portrait(sw, sh):
            self._build_body_portrait(sw, sh)
        else:
            self._build_body_landscape(sw, sh)
        self._build_footer(sh)

    def _schedule_update(self):
        self._update_job = self.after(500, self._run_update)

    def _run_update(self):
        self._update_ui()
        self._update_job = self.after(500, self._run_update)

    # ══════════════════════════════════════════════════════════════════════════
    # HEADER
    # ══════════════════════════════════════════════════════════════════════════

    def _build_header(self, sh: int):
        hdr = tk.Frame(self, bg=CLR_DARK, height=int(sh * 0.04))
        hdr.pack(fill=tk.X, side=tk.TOP)
        hdr.pack_propagate(False)

        tk.Label(hdr, text="ESPECIFIKA S.A.S",
                 font=("Segoe UI", scaled_font(14, self._scale), "italic"),
                 bg=CLR_DARK, fg=CLR_W).pack(side=tk.LEFT, padx=20)

        self._lbl_modelo = tk.Label(hdr, text="AUTOCLAVE",
                                     font=("Segoe UI", scaled_font(16, self._scale), "bold"),
                                     bg=CLR_DARK, fg=CLR_W)
        self._lbl_modelo.pack(side=tk.LEFT, expand=True)

        self._lbl_hora = tk.Label(hdr, text="",
                                   font=("Segoe UI", scaled_font(14, self._scale)),
                                   bg=CLR_DARK, fg=CLR_W)
        self._lbl_hora.pack(side=tk.RIGHT, padx=20)
        self._tick_hora()

    def _tick_hora(self):
        try:
            self._lbl_hora.config(text=time.strftime("%d/%m/%Y   %I:%M:%S %p"))
        except tk.TclError:
            return  # widget destroyed — stop silently
        self.after(1000, self._tick_hora)

    # ══════════════════════════════════════════════════════════════════════════
    # BODY  (fondo azul → tarjeta blanca → panel izq + panel der)
    # ══════════════════════════════════════════════════════════════════════════

    def _build_body_landscape(self, sw: int, sh: int):
        self._body_bg = tk.Frame(self, bg=CLR_BG)
        self._body_bg.pack(fill=tk.BOTH, expand=True)

        # tarjeta blanca con bordes redondeados
        self._card = ctk.CTkFrame(self._body_bg, corner_radius=28,
                                   fg_color=CLR_CARD, bg_color=CLR_BG)
        self._card.place(relx=0.02, rely=0.03, relwidth=0.96, relheight=0.94)

        self._build_left_panel()
        self._build_right_panel()

        # Guardar coordenadas para _upd_panel_izquierdo
        self._boton_iniciar_pos   = dict(relx=0.79, rely=0.76, relwidth=0.16, relheight=0.21)
        self._btn_reset_falla_pos = dict(relx=0.30, rely=0.76, relwidth=0.65, relheight=0.21)

    def _build_body_portrait(self, sw: int, sh: int):
        self._body_bg = tk.Frame(self, bg=CLR_BG)
        self._body_bg.pack(fill=tk.BOTH, expand=True)

        self._card = ctk.CTkFrame(self._body_bg, corner_radius=28,
                                   fg_color=CLR_CARD, bg_color=CLR_BG)
        self._card.place(relx=0.02, rely=0.03, relwidth=0.96, relheight=0.94)

        # ── Banda de estado (22%) ─────────────────────────────────────────────
        band = ctk.CTkFrame(self._card, corner_radius=16,
                            fg_color=CLR_DARK, bg_color=CLR_CARD)
        band.place(relx=0.02, rely=0.03, relwidth=0.96, relheight=0.22)

        self._lbl_n_ciclo = ctk.CTkLabel(
            band, text="01",
            font=("Segoe UI", scaled_font(90, self._scale), "bold"),
            text_color=CLR_W, fg_color="transparent")
        self._lbl_n_ciclo.place(relx=0.12, rely=0.5, anchor="center")

        ctk.CTkFrame(band, fg_color="#ffffff", corner_radius=0,
                     bg_color=CLR_DARK).place(
            relx=0.27, rely=0.1, relwidth=0.003, relheight=0.8)

        self._lbl_ciclo_nombre = ctk.CTkLabel(
            band, text=self.cycle_name.upper(),
            font=("Segoe UI", scaled_font(30, self._scale), "bold"),
            text_color=CLR_W, fg_color="transparent")
        self._lbl_ciclo_nombre.place(relx=0.63, rely=0.22, anchor="center")

        self._lbl_estado = ctk.CTkLabel(
            band, text="Cargando...",
            font=("Segoe UI", scaled_font(22, self._scale), "bold"),
            text_color=CLR_W, fg_color="transparent",
            wraplength=int(sw * 0.55))
        self._lbl_estado.place(relx=0.63, rely=0.52, anchor="center")

        self._lbl_cond = []
        for i in range(_MAX_COND):
            lbl = ctk.CTkLabel(
                band, text="",
                font=("Segoe UI", scaled_font(14, self._scale)),
                text_color=CLR_W, fg_color="transparent")
            lbl.place(relx=0.63, rely=0.70 + i * 0.065, anchor="center")
            self._lbl_cond.append(lbl)

        # ── Grid de pills 2×3 (34%) ───────────────────────────────────────────
        pills_zone = ctk.CTkFrame(self._card, corner_radius=0,
                                   fg_color=CLR_CARD, bg_color=CLR_CARD)
        pills_zone.place(relx=0.02, rely=0.27, relwidth=0.96, relheight=0.34)

        PW, PH = 0.485, 0.30
        cols = [0.0, 0.515]
        rows = [0.02, 0.36, 0.68]

        self._val_temp_ester   = self._pill(pills_zone, "Temp. Ester",   "---", "°C",  cols[0], rows[0], PW, PH)
        self._val_tiempo_ester = self._pill(pills_zone, "Tiempo Ester",  "---", "min", cols[0], rows[1], PW, PH)
        self._val_tiempo_sec   = self._pill(pills_zone, "Tiempo Sec",    "---", "min", cols[0], rows[2], PW, PH)
        self._val_temp_cam     = self._pill(pills_zone, "Temp.",         "---", "°C",  cols[1], rows[0], PW, PH)
        self._val_temp_ref     = self._pill(pills_zone, "Temp. 1",       "---", "°C",  cols[1], rows[1], PW, PH)
        self._val_pres_cam     = self._pill(pills_zone, "Presión",       "---", "kPa", cols[1], rows[2], PW, PH)

        # ── Zona de acción (28%) ──────────────────────────────────────────────
        action_zone = ctk.CTkFrame(self._card, corner_radius=0,
                                    fg_color=CLR_CARD, bg_color=CLR_CARD)
        action_zone.place(relx=0.02, rely=0.63, relwidth=0.96, relheight=0.28)
        self._panel_der = action_zone

        self._boton_puerta = tk.Label(action_zone, bg=CLR_CARD, cursor="hand2")
        self._boton_puerta.bind("<Button-1>", lambda e: self._accion_puerta_1())
        self._boton_puerta.bind("<Enter>", lambda e: self._boton_puerta.configure(bg=CLR_BG))
        self._boton_puerta.bind("<Leave>", lambda e: self._boton_puerta.configure(bg=CLR_CARD))
        self._boton_puerta.place(relx=0.04, rely=0.15, relwidth=0.42, relheight=0.75)

        self._boton_iniciar = tk.Label(action_zone, bg=CLR_CARD, cursor="")
        self._boton_iniciar.bind("<Enter>", lambda e: self._boton_iniciar.configure(bg=CLR_BG) if self._inicio_habilitado else None)
        self._boton_iniciar.bind("<Leave>", lambda e: self._boton_iniciar.configure(bg=CLR_CARD))
        self._boton_iniciar.place(relx=0.54, rely=0.15, relwidth=0.42, relheight=0.75)
        self._inicio_habilitado = False

        self._btn_reset_falla = ctk.CTkButton(
            action_zone,
            text="RECONOCER\nFALLA",
            font=("Segoe UI", scaled_font(14, self._scale), "bold"),
            fg_color="#c0392b", hover_color="#922b21",
            text_color=CLR_W, corner_radius=14,
            command=self._do_reset_falla,
        )

        self._boton_iniciar_pos   = dict(relx=0.54, rely=0.15, relwidth=0.42, relheight=0.75)
        self._btn_reset_falla_pos = dict(relx=0.04, rely=0.15, relwidth=0.92, relheight=0.75)

    # ── Panel izquierdo ───────────────────────────────────────────────────────

    def _build_left_panel(self):
        pnl = ctk.CTkFrame(self._card, corner_radius=22,
                            fg_color=CLR_DARK, bg_color=CLR_CARD)
        pnl.place(relx=0.02, rely=0.04, relwidth=0.26, relheight=0.92)

        # número de ciclo
        self._lbl_n_ciclo = ctk.CTkLabel(
            pnl, text="01",
            font=("Segoe UI", scaled_font(90, self._scale), "bold"),
            text_color=CLR_W, fg_color="transparent")
        self._lbl_n_ciclo.place(relx=0.5, rely=0.20, anchor="center")

        # estado de máquina
        self._lbl_estado = ctk.CTkLabel(
            pnl, text="Cargando...",
            font=("Segoe UI", scaled_font(22, self._scale), "bold"),
            text_color=CLR_W, fg_color="transparent",
            wraplength=int(self.winfo_screenwidth() * 0.10))
        self._lbl_estado.place(relx=0.5, rely=0.43, anchor="center")

        # alarmas y condiciones dinámicas
        self._lbl_cond = []
        for i in range(_MAX_COND):
            lbl = ctk.CTkLabel(
                pnl, text="",
                font=("Segoe UI", scaled_font(16, self._scale)),
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
            font=("Segoe UI", scaled_font(46, self._scale), "bold"),
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

        # ── Botón RESET FALLA (oculto hasta entrar en estado FALLA) ───
        self._btn_reset_falla = ctk.CTkButton(
            pnl,
            text="RECONOCER\nFALLA",
            font=("Segoe UI", scaled_font(14, self._scale), "bold"),
            fg_color="#c0392b",
            hover_color="#922b21",
            text_color=CLR_W,
            corner_radius=14,
            command=self._do_reset_falla,
        )
        # Se posiciona al entrar en FALLA; oculto por defecto

    def _pill(self, parent, label, value, unit, relx, rely, relwidth, relheight):
        """
        Pill oscura con:  [ Label ·····  valor  unidad ]
        Retorna el CTkLabel del valor para actualizarlo.
        """
        frame = ctk.CTkFrame(parent, corner_radius=30,
                            fg_color=CLR_DARK, bg_color=CLR_CARD)
        frame.place(relx=relx, rely=rely, relwidth=relwidth, relheight=relheight)

        ctk.CTkLabel(frame, text=label,
                     font=("Segoe UI", scaled_font(18, self._scale), "bold"),
                     text_color=CLR_W, fg_color="transparent",
                     anchor="w").place(relx=0.05, rely=0.5, anchor="w")

        ctk.CTkLabel(frame, text=unit,
                     font=("Segoe UI", scaled_font(15, self._scale)),
                     text_color=CLR_W, fg_color="transparent",
                     anchor="e").place(relx=0.97, rely=0.5, anchor="e")

        lbl_val = ctk.CTkLabel(frame, text=value,
                                font=("Segoe UI", scaled_font(20, self._scale), "bold"),
                                text_color=CLR_W, fg_color="transparent",
                                anchor="e")
        lbl_val.place(relx=0.74, rely=0.5, anchor="e")

        return lbl_val

    # ══════════════════════════════════════════════════════════════════════════
    # FOOTER
    # ══════════════════════════════════════════════════════════════════════════

    def _build_footer(self, sh: int):
        footer = tk.Frame(self, bg=CLR_BG, height=int(sh * 0.065))
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        footer.pack_propagate(False)

        # píldora central
        pill = ctk.CTkFrame(footer, corner_radius=45,
                             fg_color=CLR_FOOTER, bg_color=CLR_BG)
        pill.place(relx=0.5, rely=0.5, anchor="center",
                   relwidth=0.52, relheight=0.82)

        # cargar iconos footer
        icons = load_footer_icons(self._scale)
        self._img_info     = icons["info"]
        self._img_settings = icons["settings"]

        # Power icon — loaded separately (not in load_footer_icons)
        _off_raw = Image.open(resource_path("autoclave/images/power_icon.png"))
        ico_size = (scaled_font(46, self._scale), scaled_font(40, self._scale))
        self._img_OFF = ctk.CTkImage(light_image=_off_raw, dark_image=_off_raw, size=ico_size)

        ctk.CTkButton(pill, text="", image=self._img_info,
                      fg_color="transparent", hover_color="#406080",
                      width=scaled_font(56, self._scale)).pack(side=tk.LEFT, padx=18)

        ctk.CTkButton(pill, text="", image=self._img_settings,
                      fg_color="transparent", hover_color="#406080",
                      width=scaled_font(56, self._scale)).pack(side=tk.LEFT, padx=8)

        ctk.CTkButton(pill, text="", image=self._img_OFF,
                      fg_color="transparent", hover_color="#406080",
                      command=self.apagar_equipo,
                      width=scaled_font(56, self._scale)).pack(side=tk.RIGHT, padx=18)

        # indicador de conexión
        self._lbl_conexion = tk.Label(footer, text="⚪ Conectando...",
                                       font=("Segoe UI", scaled_font(12, self._scale)),
                                       bg=CLR_BG, fg="white")
        self._lbl_conexion.place(relx=0.01, rely=0.5, anchor="w")

        # indicador de suministro eléctrico
        self._lbl_suministro = tk.Label(
            footer,
            text="⚡ Suministro: OK",
            font=("Segoe UI", scaled_font(12, self._scale)),
            bg=CLR_BG,
            fg="#7FFF7F",
        )
        self._lbl_suministro.place(relx=0.17, rely=0.5, anchor="w")

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
            ok, motivo = self.door_commands.close(self._door_name)
        else:
            ok, motivo = self.door_commands.open(self._door_name)

        if not ok and motivo:
            self._mostrar_toast(motivo)

    def start_cycle(self):
        logger.info("▶️ Iniciando ciclo...")
        if not self.ui_service.start_cycle():
            logger.warning("Backend rechazó el inicio del ciclo")
            return
        self._open_cycle_window()

    def _open_cycle_window(self):
        """Abre la CycleWindow si no hay una ya abierta."""
        if self._cycle_win is not None:
            try:
                if self._cycle_win.winfo_exists():
                    return   # ya está abierta
            except tk.TclError:
                pass

        def _on_cycle_win_close():
            """Callback: la CycleWindow se cerró — limpiar referencia."""
            self._cycle_win = None

        self._cycle_win = CycleWindow(
            parent     = self,
            ui_service = self.ui_service,
            door_name  = self._door_name,
            on_close   = _on_cycle_win_close,
        )

    def _do_reset_falla(self):
        logger.info("Operador reconoció la falla — enviando RESET_FALLA")
        if not self.ui_service.reset_fault():
            logger.warning("Backend rechazó el reset de falla")

    def apagar_equipo(self):
        logger.info("⏻ Apagando equipo...")

        # Apagar todas las salidas ANTES de la pantalla de apagado
        try:
            self.ui_service.reset_outputs()
            logger.info("Salidas digitales apagadas")
        except Exception as e:
            logger.warning("No se pudieron apagar las salidas: %s", e)

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
                    self._upd_suministro()
                    self._actualizar_imagen_puerta()

                    # Auto-abrir CycleWindow solo al ENTRAR en estado CICLO
                    # (no en cada tick; evita reabrir después de confirmar fin de ciclo)
                    estado_actual = self.ui_service.get_estado_global()
                    if estado_actual == "CICLO" and self._prev_machine_state != "CICLO":
                        self._open_cycle_window()
                    self._prev_machine_state = estado_actual

            except Exception as e:
                logger.warning("⚠️ Error UI loop: %s", e)

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
            alarm_id = alarma.get("id", "")
            legible  = alarm_id.replace("_", " ").title()
            conds.append(f"⚠ {legible}")

        # actualizar labels
        for i, lbl in enumerate(self._lbl_cond):
            lbl.configure(text=conds[i] if i < len(conds) else "")

        # mostrar / ocultar botón de reset según estado FALLA
        en_falla = (estado == "FALLA")
        if en_falla:
            self._boton_iniciar.place_forget()
            self._btn_reset_falla.place(**self._btn_reset_falla_pos)
        else:
            self._btn_reset_falla.place_forget()
            self._boton_iniciar.place(**self._boton_iniciar_pos)

    def _upd_suministro(self):
        di = self.ui_service.get_sensores_di()
        ok = bool(di.get("suministro_electrico", 1))
        if ok:
            self._lbl_suministro.configure(text="⚡ Suministro: OK", fg="#7FFF7F")
        else:
            self._lbl_suministro.configure(text="⚡ Sin suministro", fg="#FF7F7F")

    def _upd_listo(self):
        ok = bool(self.ui_service.get_estado_flag("LISTO_PARA_CICLO"))
        if ok == self._inicio_habilitado:
            return   # sin cambio

        self._inicio_habilitado = ok
        if ok:
            self._boton_iniciar.bind("<Button-1>", lambda e: self.start_cycle())
            self._boton_iniciar.configure(cursor="hand2")
        else:
            self._boton_iniciar.unbind("<Button-1>")
            self._boton_iniciar.configure(cursor="")

    def _actualizar_imagen_puerta(self):
        if not hasattr(self, "_img_puerta_ab"):
            return
        estado = self.ui_service.get_estado_puerta(self._door_name)
        img = self._img_puerta_ce if estado == "CERRADO" else self._img_puerta_ab
        self._boton_puerta.configure(image=img)
        self._boton_puerta.update_idletasks()

    # ══════════════════════════════════════════════════════════════════════════
    # DETECCIÓN DE ORIENTACIÓN
    # ══════════════════════════════════════════════════════════════════════════

    def _on_configure(self, event):
        if event.widget is not self:
            return
        if self._resize_job:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(
            150, lambda: self._check_orientation(event.width, event.height)
        )

    def _check_orientation(self, w: int, h: int):
        self._resize_job = None
        try:
            new_portrait, should_rebuild = check_orientation_changed(
                w, h, self._current_portrait
            )
            self._current_portrait = new_portrait
            if should_rebuild:
                self._rebuild_layout()
        except tk.TclError:
            return  # window destroyed during debounce

    def _rebuild_layout(self):
        if self._update_job:
            self.after_cancel(self._update_job)
            self._update_job = None
        for child in self.winfo_children():
            if self._cycle_win is not None and child is self._cycle_win:
                continue  # CycleWindow handles its own rebuild via <Configure>
            try:
                child.destroy()
            except tk.TclError:
                pass
        self._build_ui()
        self.after(300, self._load_action_images)
        self._schedule_update()

    # ══════════════════════════════════════════════════════════════════════════
    # NOTIFICACIÓN DE ERROR — overlay centrado con botón confirmar
    # ══════════════════════════════════════════════════════════════════════════

    def _mostrar_toast(self, mensaje: str):
        """
        Muestra un overlay centrado con el motivo del rechazo y un botón
        "Aceptar" para cerrarlo.  Si ya hay uno visible, lo reemplaza.
        """
        # Destruir overlay anterior si existe
        if getattr(self, "_toast_widget", None):
            try:
                self._toast_widget.destroy()
            except tk.TclError:
                pass
            self._toast_widget = None

        # Tarjeta flotante centrada (sin fondo oscuro)
        card = tk.Frame(
            self,
            bg="#c0392b",
            highlightbackground="#7b0d0d",
            highlightthickness=2,
        )
        card.place(relx=0.5, rely=0.5, anchor="center",
                   relwidth=0.40, relheight=0.26)
        card.lift()

        # Icono + título
        tk.Label(
            card,
            text="⚠  Acción no permitida",
            font=("Segoe UI", 15, "bold"),
            bg="#c0392b",
            fg="white",
        ).pack(pady=(18, 6))

        # Mensaje de motivo
        tk.Label(
            card,
            text=mensaje,
            font=("Segoe UI", 13),
            bg="#c0392b",
            fg="white",
            wraplength=380,
            justify="center",
        ).pack(pady=(0, 16), padx=20)

        # Botón Aceptar
        def _cerrar():
            try:
                card.destroy()
            except tk.TclError:
                pass
            if self._toast_widget is card:
                self._toast_widget = None

        tk.Button(
            card,
            text="Aceptar",
            font=("Segoe UI", 13, "bold"),
            bg="white",
            fg="#c0392b",
            activebackground="#f0f0f0",
            activeforeground="#c0392b",
            relief="flat",
            cursor="hand2",
            padx=24,
            pady=6,
            command=_cerrar,
        ).pack()

        self._toast_widget = card

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

# ui/cycle/cycle_window.py
#
# Ventana de ciclo de esterilización (Toplevel fullscreen).
#
# Se abre sobre la ventana principal al iniciar un ciclo.
# Muestra: nombre del ciclo, fase activa con timer X/Y Min,
# gráfica T/P en vivo, lecturas de sensores, estado de puertas
# y botón de abortar con confirmación.
#
# Cierre: NO automático.  El operador debe confirmar explícitamente
# que vio el resultado; solo entonces la máquina transiciona.

import time
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk
import logging

from autoclave.ui.cycle.data.cycle_buffer import CycleBuffer, FASE_DURACION_PARAM
from autoclave.ui.cycle.widgets.phase_indicator import PhaseIndicator
from autoclave.ui.cycle.widgets.live_graph import LiveGraph
from autoclave.utils.resources import resource_path
from autoclave.ui.layout import is_portrait, font_scale, scaled_font, load_footer_icons, check_orientation_changed

logger = logging.getLogger(__name__)

# ── Paleta (misma que main_window) ────────────────────────────────────────────
CLR_BG     = "#b6ccd9"
CLR_DARK   = "#2d4757"
CLR_CARD   = "#ffffff"
CLR_FOOTER = "#5789a7"
CLR_W      = "white"
CLR_B      = "black"
CLR_OK     = "#1e8449"   # verde confirmación
CLR_WARN   = "#c0392b"   # rojo abortar

# Gráfica se actualiza cada N ticks de 1 segundo
_GRAPH_TICKS = 2

# Fases que indican fin de ciclo (esperando confirmación)
_FASES_TERMINALES = {"COMPLETADO", "CANCELADO", "EMERGENCIA"}

# Parámetros de temperatura objetivo por fase (sección, clave)
_FASE_TEMP_TARGET = {
    "PRECALENTAMIENTO": ("precalentamiento", "temperatura_precalentamiento"),
    "CALENTAMIENTO":    ("calentamiento",    "temperatura_calentamiento"),
    "ESTABILIZACION":   ("estabilizacion",   "temperatura_estabilizacion"),
    "ESTERILIZACION":   ("esterilizacion",   "temperatura_esterilizacion"),
}


def _es_fase_terminal(fase: str) -> bool:
    return fase in _FASES_TERMINALES or fase.startswith("FALLO_")


class CycleWindow(tk.Toplevel):
    """
    Ventana fullscreen de ciclo de esterilización.

    Parámetros:
        parent      : ventana padre (InterfazPrincipal)
        ui_service  : UIServiceBackend (acceso a sensores, fases, etc.)
        door_name   : nombre de la puerta del operador ("Puerta 1" o "Puerta 2")
    """

    def __init__(self, parent, ui_service, door_name: str = "Puerta 1",
                 on_close=None):
        super().__init__(parent)
        self.ui_service = ui_service
        self._door_name = door_name
        self._tick      = 0
        self._buffer    = CycleBuffer()
        self._closing   = False
        self._on_close  = on_close   # callback opcional al destruir la ventana

        # ── Estado de fin de ciclo ────────────────────────────────────
        self._ciclo_activo_detectado = False  # True al ver CICLO + fase no-terminal
        self._ciclo_terminado        = False   # True cuando se detecta fase terminal
        self._confirm_habilitado     = False   # True cuando la presión es segura

        # ── Estado del indicador de fase ─────────────────────────────
        self._prev_fase          = ""     # para detectar cambio de fase
        self._prev_sostenimiento = False  # para detectar transición a sostenimiento
        self._hold_start_time: float | None = None   # momento en que empezó el sostenimiento
        self._fase_temp_targets: dict[str, float] = {}  # temp objetivo por fase

        # ── Ventana ───────────────────────────────────────────────────────
        self.title("Ciclo de Esterilización")
        self.configure(bg=CLR_BG)
        self.attributes("-fullscreen", True)
        self.grab_set()

        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self._scale = font_scale(sw, sh)
        self._sh    = sh

        self._current_portrait = None
        self._update_job_cw    = None
        self._resize_job_cw    = None

        # ── Construir UI ──────────────────────────────────────────────────
        self._build_ui_cw()

        # ── Diferir init de buffer e imágenes (ventana debe renderizarse) ─
        self.after(150, self._init_buffer)
        self.after(350, self._load_images)
        self.after(1000, self._update_loop)
        self.bind("<Configure>", self._on_configure_cw)

        logger.info("CycleWindow abierta")

    # ══════════════════════════════════════════════════════════════════════
    # BUILD UI (dispatcher landscape / portrait)
    # ══════════════════════════════════════════════════════════════════════

    def _build_ui_cw(self):
        # Recalcula dimensiones para soportar rebuild tras cambio de orientación
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self._scale = font_scale(sw, sh)
        self._sh    = sh
        self._build_header()
        if is_portrait(sw, sh):
            self._build_body_portrait_cw(sw, sh)
        else:
            self._build_body_landscape()
        self._build_footer()

    # ══════════════════════════════════════════════════════════════════════
    # HEADER
    # ══════════════════════════════════════════════════════════════════════

    def _build_header(self):
        hdr = tk.Frame(self, bg=CLR_DARK, height=58)
        hdr.pack(fill=tk.X, side=tk.TOP)
        hdr.pack_propagate(False)

        tk.Label(hdr, text="ESPECIFIKA S.A.S",
                font=("Segoe UI", 14, "italic"),
                bg=CLR_DARK, fg=CLR_W).pack(side=tk.LEFT, padx=20)

        tk.Label(hdr, text="CICLO EN CURSO",
                font=("Segoe UI", 16, "bold"),
                bg=CLR_DARK, fg=CLR_W).pack(side=tk.LEFT, expand=True)

        self._lbl_hora = tk.Label(hdr, text="",
                                    font=("Segoe UI", 14),
                                    bg=CLR_DARK, fg=CLR_W)
        self._lbl_hora.pack(side=tk.RIGHT, padx=20)
        self._tick_hora()

    def _tick_hora(self):
        try:
            self._lbl_hora.config(text=time.strftime("%d/%m/%Y   %I:%M:%S %p"))
            self.after(1000, self._tick_hora)
        except tk.TclError:
            pass   # ventana ya destruida

    # ══════════════════════════════════════════════════════════════════════
    # BODY LANDSCAPE
    # ══════════════════════════════════════════════════════════════════════

    def _build_body_landscape(self):
        body = tk.Frame(self, bg=CLR_BG)
        body.pack(fill=tk.BOTH, expand=True)

        card = ctk.CTkFrame(body, corner_radius=28,
                            fg_color=CLR_CARD, bg_color=CLR_BG)
        card.place(relx=0.02, rely=0.03, relwidth=0.96, relheight=0.94)
        self._card = card

        # Nombre del ciclo
        nombre = (self.ui_service.get_cycle_param("name") or "CICLO").upper()
        self._lbl_nombre = ctk.CTkLabel(
            card, text=nombre,
            font=("Segoe UI", 40, "bold"),
            text_color=CLR_B, fg_color="transparent",
        )
        self._lbl_nombre.place(relx=0.5, rely=0.07, anchor="center")

        # Separador
        ctk.CTkFrame(card, fg_color="#cccccc", corner_radius=0,
                    bg_color=CLR_CARD).place(
            relx=0.01, rely=0.15, relwidth=0.98, relheight=0.003)

        self._build_left_panel(card)
        self._build_right_panel(card)

    # ── Panel izquierdo: pill de fase + gráfica ───────────────────────────

    def _build_left_panel(self, parent):
        pnl = tk.Frame(parent, bg=CLR_CARD)
        pnl.place(relx=0.01, rely=0.17, relwidth=0.62, relheight=0.81)

        # Pill de fase
        self._phase_ind = PhaseIndicator(pnl, bg_color=CLR_CARD)
        self._phase_ind.place(relx=0.0, rely=0.0, relwidth=1.0, relheight=0.14)

        # Gráfica
        self._graph = LiveGraph(pnl, bg=CLR_CARD)
        self._graph.place(relx=0.0, rely=0.16, relwidth=1.0, relheight=0.84)

    # ── Panel derecho: sensores + puertas + acción ───────────────────────

    def _build_right_panel(self, parent):
        pnl = tk.Frame(parent, bg=CLR_CARD)
        pnl.place(relx=0.65, rely=0.17, relwidth=0.34, relheight=0.81)
        self._right_pnl = pnl

        # Pills de sensores
        self._val_temp  = self._pill(pnl, "Temp.",   "---", "°C",  0.0, 0.02,  1.0, 0.14)
        self._val_temp2 = self._pill(pnl, "Temp. 1", "---", "°C",  0.0, 0.19,  1.0, 0.14)
        self._val_pres  = self._pill(pnl, "Presión", "---", "kPa", 0.0, 0.36,  1.0, 0.14)

        # Iconos de puertas
        doors_frame = tk.Frame(pnl, bg=CLR_CARD)
        doors_frame.place(relx=0.0, rely=0.56, relwidth=0.63, relheight=0.26)

        self._lbl_puerta1 = tk.Label(doors_frame, bg=CLR_CARD)
        self._lbl_puerta1.pack(side=tk.LEFT, padx=6)

        self._lbl_puerta2 = tk.Label(doors_frame, bg=CLR_CARD)
        self._lbl_puerta2.pack(side=tk.LEFT, padx=6)

        # ── Botón ABORTAR (imagen stop_cycle) ─────────────────────────
        self._btn_abort = tk.Label(pnl, bg=CLR_CARD, cursor="hand2")
        self._btn_abort.bind("<Button-1>", lambda e: self._confirmar_abort())
        self._btn_abort.bind("<Enter>",    lambda e: self._btn_abort.configure(bg=CLR_BG))
        self._btn_abort.bind("<Leave>",    lambda e: self._btn_abort.configure(bg=CLR_CARD))
        self._btn_abort.place(relx=0.65, rely=0.56, relwidth=0.35, relheight=0.26)

        # ── Botón CONFIRMAR (oculto hasta fin de ciclo) ────────────────
        self._btn_confirm = ctk.CTkButton(
            pnl,
            text="CONFIRMAR",
            font=("Segoe UI", scaled_font(15, self._scale), "bold"),
            fg_color=CLR_OK,
            hover_color="#155d32",
            text_color=CLR_W,
            corner_radius=14,
            state="disabled",
            command=self._do_confirm,
        )
        # No se hace place() todavía; se posiciona al reemplazar el abort

    def _pill(self, parent, label, value, unit,
            relx, rely, relwidth, relheight):
        """Pill oscura reutilizable — igual que en main_window."""
        frame = ctk.CTkFrame(parent, corner_radius=30,
                            fg_color=CLR_DARK, bg_color=CLR_CARD)
        frame.place(relx=relx, rely=rely,
                    relwidth=relwidth, relheight=relheight)

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

    # ══════════════════════════════════════════════════════════════════════
    # BODY PORTRAIT — CycleWindow
    # ══════════════════════════════════════════════════════════════════════

    def _build_body_portrait_cw(self, sw: int, sh: int):
        body = tk.Frame(self, bg=CLR_BG)
        body.pack(fill=tk.BOTH, expand=True)

        card = ctk.CTkFrame(body, corner_radius=28,
                            fg_color=CLR_CARD, bg_color=CLR_BG)
        card.place(relx=0.02, rely=0.03, relwidth=0.96, relheight=0.94)
        self._card = card

        # Nombre del ciclo
        nombre = (self.ui_service.get_cycle_param("name") or "CICLO").upper()
        self._lbl_nombre = ctk.CTkLabel(
            card, text=nombre,
            font=("Segoe UI", scaled_font(34, self._scale), "bold"),
            text_color=CLR_B, fg_color="transparent",
        )
        self._lbl_nombre.place(relx=0.5, rely=0.04, anchor="center")

        # Separador
        ctk.CTkFrame(card, fg_color="#cccccc", corner_radius=0,
                    bg_color=CLR_CARD).place(
            relx=0.01, rely=0.10, relwidth=0.98, relheight=0.003)

        # Pill de fase
        self._phase_ind = PhaseIndicator(
            card, bg_color=CLR_CARD,
            font_size_label=scaled_font(20, self._scale),
            font_size_timer=scaled_font(18, self._scale),
        )
        self._phase_ind.place(relx=0.01, rely=0.11, relwidth=0.98, relheight=0.10)

        # Gráfica (zona dominante)
        graph_frame = tk.Frame(card, bg=CLR_CARD)
        graph_frame.place(relx=0.01, rely=0.23, relwidth=0.98, relheight=0.44)
        self._graph = LiveGraph(graph_frame, bg=CLR_CARD)
        self._graph.pack(fill=tk.BOTH, expand=True)

        # Separador
        ctk.CTkFrame(card, fg_color="#cccccc", corner_radius=0,
                    bg_color=CLR_CARD).place(
            relx=0.01, rely=0.68, relwidth=0.98, relheight=0.003)

        # Sensores en fila horizontal
        self._val_temp  = self._pill(card, "Temp.",   "---", "°C",  0.01, 0.69, 0.32, 0.13)
        self._val_temp2 = self._pill(card, "Temp. 1", "---", "°C",  0.34, 0.69, 0.32, 0.13)
        self._val_pres  = self._pill(card, "Presión", "---", "kPa", 0.67, 0.69, 0.32, 0.13)

        # Separador
        ctk.CTkFrame(card, fg_color="#cccccc", corner_radius=0,
                    bg_color=CLR_CARD).place(
            relx=0.01, rely=0.83, relwidth=0.98, relheight=0.003)

        # Puertas + botón acción
        doors_frame = tk.Frame(card, bg=CLR_CARD)
        doors_frame.place(relx=0.01, rely=0.84, relwidth=0.35, relheight=0.13)

        self._lbl_puerta1 = tk.Label(doors_frame, bg=CLR_CARD)
        self._lbl_puerta1.pack(side=tk.LEFT, padx=6)

        self._lbl_puerta2 = tk.Label(doors_frame, bg=CLR_CARD)
        self._lbl_puerta2.pack(side=tk.LEFT, padx=6)

        self._btn_abort = tk.Label(card, bg=CLR_CARD, cursor="hand2")
        self._btn_abort.bind("<Button-1>", lambda e: self._confirmar_abort())
        self._btn_abort.bind("<Enter>",    lambda e: self._btn_abort.configure(bg=CLR_BG))
        self._btn_abort.bind("<Leave>",    lambda e: self._btn_abort.configure(bg=CLR_CARD))
        self._btn_abort.place(relx=0.37, rely=0.84, relwidth=0.62, relheight=0.13)

        self._btn_confirm = ctk.CTkButton(
            card,
            text="CONFIRMAR",
            font=("Segoe UI", scaled_font(15, self._scale), "bold"),
            fg_color=CLR_OK, hover_color="#155d32",
            text_color=CLR_W, corner_radius=14,
            state="disabled",
            command=self._do_confirm,
        )

    # ══════════════════════════════════════════════════════════════════════
    # FOOTER
    # ══════════════════════════════════════════════════════════════════════

    def _build_footer(self):
        footer = tk.Frame(self, bg=CLR_BG, height=int(self._sh * 0.065))
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        footer.pack_propagate(False)

        # Pill izquierda: info + settings
        icons = load_footer_icons(self._scale)
        self._img_info_cw     = icons["info"]
        self._img_settings_cw = icons["settings"]

        pill_left = ctk.CTkFrame(footer, corner_radius=30,
                                  fg_color=CLR_FOOTER, bg_color=CLR_BG)
        pill_left.place(relx=0.01, rely=0.5, anchor="w",
                        relwidth=0.20, relheight=0.82)

        ctk.CTkButton(pill_left, text="", image=self._img_info_cw,
                      fg_color="transparent", hover_color="#406080",
                      width=scaled_font(56, self._scale)).pack(side=tk.LEFT, padx=12)

        ctk.CTkButton(pill_left, text="", image=self._img_settings_cw,
                      fg_color="transparent", hover_color="#406080",
                      width=scaled_font(56, self._scale)).pack(side=tk.LEFT, padx=8)

        # Pill central: estado del ciclo
        pill = ctk.CTkFrame(footer, corner_radius=45,
                            fg_color=CLR_FOOTER, bg_color=CLR_BG)
        pill.place(relx=0.5, rely=0.5, anchor="center",
                   relwidth=0.52, relheight=0.82)

        self._lbl_estado = ctk.CTkLabel(
            pill, text="Ciclo en progreso...",
            font=("Segoe UI", scaled_font(16, self._scale)),
            text_color=CLR_W, fg_color="transparent",
        )
        self._lbl_estado.pack(expand=True)

    # ══════════════════════════════════════════════════════════════════════
    # IMÁGENES
    # ══════════════════════════════════════════════════════════════════════

    def _load_images(self):
        try:
            self.update()
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            bw = max(55, int(sw * 0.05))
            bh = max(55, int(sh * 0.11))

            def _ico(name):
                img = Image.open(resource_path(f"autoclave/images/{name}"))
                img.thumbnail((bw, bh), Image.LANCZOS)
                return ImageTk.PhotoImage(img)

            self._img_p1_ab  = _ico("open_door_1.png")
            self._img_p1_ce  = _ico("close_door_1.png")
            self._img_p2_ab  = _ico("open_door_2.png")
            self._img_p2_ce  = _ico("close_door_2.png")
            self._img_stop   = _ico("stop_cycle.png")

            self._btn_abort.configure(image=self._img_stop)
            self._btn_abort.lift()
            self._upd_puertas()
            logger.info("CycleWindow: imágenes cargadas")

        except Exception as e:
            logger.error("CycleWindow: error cargando imágenes: %s", e, exc_info=True)

    # ══════════════════════════════════════════════════════════════════════
    # INICIALIZACIÓN DEL BUFFER (duraciones y targets desde el ciclo JSON)
    # ══════════════════════════════════════════════════════════════════════

    def _init_buffer(self):
        durations: dict[str, float] = {}
        try:
            params = self.ui_service.get_cycle().get("parameters", {})

            # Duraciones de sostenimiento por fase
            for fase, param_key in FASE_DURACION_PARAM.items():
                val = self._buscar_param(params, param_key)
                if val is not None:
                    durations[fase] = float(val)

            # Temperaturas objetivo por fase (para modo aproximación)
            for fase, (seccion, clave) in _FASE_TEMP_TARGET.items():
                sec = params.get(seccion, {})
                entry = sec.get(clave) if isinstance(sec, dict) else None
                if entry is None:
                    entry = self._buscar_param(params, clave)
                val = entry.get("value") if isinstance(entry, dict) else entry
                if val is not None:
                    self._fase_temp_targets[fase] = float(val)

        except Exception as e:
            logger.warning("CycleWindow: no se leyeron parámetros: %s", e)

        self._buffer.reset(durations)

    def _buscar_param(self, params: dict, key: str):
        """Busca un parámetro en estructura plana o en secciones anidadas."""
        entry = params.get(key)
        if entry is None:
            for section in params.values():
                if isinstance(section, dict):
                    entry = section.get(key)
                    if entry is not None:
                        break
        if isinstance(entry, dict):
            return entry.get("value")
        return entry

    # ══════════════════════════════════════════════════════════════════════
    # LOOP DE ACTUALIZACIÓN (1 s / tick)
    # ══════════════════════════════════════════════════════════════════════

    def _update_loop(self):
        if self._closing:
            return
        self._tick += 1
        try:
            self._update_loop_body()
        except Exception as e:
            logger.warning("CycleWindow update error: %s", e)
        self.after(1000, self._update_loop)

    def _update_loop_body(self):
        self._upd_sensores()
        self._upd_fase()

        if self._tick % _GRAPH_TICKS == 0:
            self._graph.update_data(
                self._buffer.points,
                self._buffer.phase_boundaries,
            )

        if self._tick % 4 == 0:
            self._upd_puertas()

        # ── Detección de fin de ciclo ─────────────────────────────
        machine_state = self.ui_service.get_estado_global()
        fase_actual   = self.ui_service.get_fase_ciclo()

        # Paso 1: confirmar que el ciclo llegó a estar activo
        # (máquina en CICLO con una fase no-terminal)
        if not self._ciclo_activo_detectado:
            if machine_state == "CICLO" and not _es_fase_terminal(fase_actual):
                self._ciclo_activo_detectado = True

        # Paso 2: solo DESPUÉS de estar activo detectar el fin
        if self._ciclo_activo_detectado and not self._ciclo_terminado:
            if _es_fase_terminal(fase_actual):
                self._on_ciclo_fin(fase_actual)

        # Si ya terminó, verificar seguridad para habilitar confirmación
        if self._ciclo_terminado:
            self._upd_confirm_safety()

    # ══════════════════════════════════════════════════════════════════════
    # DETECCIÓN DE ORIENTACIÓN — CycleWindow
    # ══════════════════════════════════════════════════════════════════════

    def _schedule_update_cw(self):
        self._update_job_cw = self.after(1000, self._run_update_cw)

    def _run_update_cw(self):
        if self._closing:
            return
        try:
            self._update_loop_body()
        except Exception as e:
            logger.warning("CycleWindow update error: %s", e)
        self._update_job_cw = self.after(1000, self._run_update_cw)

    def _on_configure_cw(self, event):
        if event.widget is not self:
            return
        if self._resize_job_cw:
            self.after_cancel(self._resize_job_cw)
        self._resize_job_cw = self.after(
            150, lambda: self._check_orientation_cw(event.width, event.height)
        )

    def _check_orientation_cw(self, w: int, h: int):
        self._resize_job_cw = None
        try:
            new_portrait, should_rebuild = check_orientation_changed(
                w, h, self._current_portrait
            )
            self._current_portrait = new_portrait
            if should_rebuild:
                self._rebuild_layout_cw()
        except tk.TclError:
            return

    def _rebuild_layout_cw(self):
        if self._update_job_cw:
            self.after_cancel(self._update_job_cw)
            self._update_job_cw = None
        for child in self.winfo_children():
            try:
                child.destroy()
            except tk.TclError:
                pass
        self._build_ui_cw()
        self.grab_set()              # re-aplicar grab modal
        self.after(350, self._load_images)
        self._schedule_update_cw()

    # ── Helpers de actualización ──────────────────────────────────────────

    def _upd_sensores(self):
        def _f(v):
            return f"{v:.1f}" if v is not None else "---"

        t  = self.ui_service.get_sensores_temp()
        p  = self.ui_service.get_sensores_pres()
        t2 = self.ui_service.get_temp_camara_2()

        temp  = t.get("temp_camara")
        pres  = p.get("pres_camara")
        fase  = self.ui_service.get_fase_ciclo()

        self._val_temp.configure(text=_f(temp))
        self._val_temp2.configure(text=_f(t2))
        self._val_pres.configure(text=_f(pres))

        self._buffer.add(temp, pres, fase)

    def _upd_fase(self):
        """
        Actualiza el PhaseIndicator.

        - Mientras las condiciones no se cumplen (no en sostenimiento):
            muestra "XX / XX °C" (temp actual / temp objetivo).
        - Una vez en sostenimiento:
            muestra "X / Y Min" (tiempo transcurrido / duración configurada).
        """
        fase = self._buffer.fase_actual

        # Detectar cambio de fase → resetear estado de sostenimiento
        if fase != self._prev_fase:
            self._prev_fase          = fase
            self._hold_start_time    = None
            self._prev_sostenimiento = False

        en_sostenimiento = self.ui_service.get_fase_en_sostenimiento()

        # Detectar transición a sostenimiento
        if en_sostenimiento and not self._prev_sostenimiento:
            self._hold_start_time    = time.time()
            self._prev_sostenimiento = True
        elif not en_sostenimiento:
            self._prev_sostenimiento = False

        if fase == "PRE_VACIO":
            # Modo pulsos: mostrar tipo y progreso "A 1/4"
            progreso = self.ui_service.get_prevacio_progreso()
            self._phase_ind.update_info(fase, progreso)
        elif en_sostenimiento and self._hold_start_time is not None:
            # Modo tiempo: mostrar progreso del sostenimiento
            elapsed_seg = time.time() - self._hold_start_time
            elapsed_min = elapsed_seg / 60.0
            total_min   = self._buffer.get_fase_total_min()
            self._phase_ind.update(fase, elapsed_min, total_min)
        else:
            # Modo aproximación: mostrar temp actual / temp objetivo
            temp        = self.ui_service.get_sensores_temp().get("temp_camara")
            target_temp = self._fase_temp_targets.get(fase)
            self._phase_ind.update_approach(fase, temp, target_temp, "°C")

    def _upd_puertas(self):
        try:
            e1 = self.ui_service.get_estado_puerta("Puerta 1")
            self._lbl_puerta1.configure(
                image=self._img_p1_ce if e1 == "CERRADO" else self._img_p1_ab
            )
            e2 = self.ui_service.get_estado_puerta("Puerta 2")
            self._lbl_puerta2.configure(
                image=self._img_p2_ce if e2 == "CERRADO" else self._img_p2_ab
            )
        except AttributeError:
            pass   # imágenes aún no cargadas

    def _upd_confirm_safety(self):
        """
        Habilita el botón CONFIRMAR cuando la cámara está en condiciones
        seguras para volver a PREPARADO:
          - Presión dentro del rango atmosférico
          - Temperatura de cámara <= temp_max_apertura
        """
        try:
            pres      = self.ui_service.get_sensores_pres().get("pres_camara")
            temp      = self.ui_service.get_sensores_temp().get("temp_camara")
            pres_atm  = self.ui_service.get_config_param("presion_admosferica") or 101.3
            rango_atm = self.ui_service.get_config_param("rango_presion_atm")   or 20.0
            temp_max  = self.ui_service.get_config_param("temp_max_apertura")   or 120.0

            pres_ok = (pres is not None) and (abs(pres - pres_atm) <= rango_atm)
            temp_ok = (temp is not None) and (temp <= temp_max)
            seguro  = pres_ok and temp_ok
        except Exception:
            seguro = False

        if seguro != self._confirm_habilitado:
            self._confirm_habilitado = seguro
            try:
                self._btn_confirm.configure(
                    state="normal" if seguro else "disabled",
                    fg_color=CLR_OK if seguro else "#4a7a58",
                )
            except tk.TclError:
                pass

    # ══════════════════════════════════════════════════════════════════════
    # FIN DE CICLO
    # ══════════════════════════════════════════════════════════════════════

    def _on_ciclo_fin(self, fase_terminal: str):
        """
        Llamado una sola vez cuando se detecta una fase terminal.
        Reemplaza el botón ABORTAR por el botón CONFIRMAR.
        """
        logger.info("CycleWindow: ciclo finalizado → fase=%s", fase_terminal)
        self._ciclo_terminado = True

        # Última actualización del gráfico
        try:
            self._graph.update_data(
                self._buffer.points,
                self._buffer.phase_boundaries,
            )
        except Exception:
            pass

        # Mensaje en footer según resultado
        _MENSAJES = {
            "COMPLETADO":           ("✅  Ciclo completado correctamente",              "#1e8449"),
            "CANCELADO":            ("⏹  Ciclo cancelado por el operador",             "#7d6608"),
            "EMERGENCIA":           ("🚨  Ciclo detenido — PARO DE EMERGENCIA",         "#922b21"),
            "FALLO_PUERTA_1_ABIERTA": ("⚠️  Fallo de seguridad — Puerta 1 se abrió",          "#922b21"),
            "FALLO_PUERTA_2_ABIERTA": ("⚠️  Fallo de seguridad — Puerta 2 se abrió",          "#922b21"),
            "FALLO_PUERTA_1_EMPAQUE": ("⚠️  Fallo de seguridad — Puerta 1: pérdida de empaque","#922b21"),
            "FALLO_PUERTA_2_EMPAQUE": ("⚠️  Fallo de seguridad — Puerta 2: pérdida de empaque","#922b21"),
        }

        if fase_terminal in _MENSAJES:
            msg, color_ftr = _MENSAJES[fase_terminal]
        else:
            # FALLO_<NOMBRE_FASE> genérico
            fase_nombre = fase_terminal.replace("FALLO_", "").replace("_", " ").title()
            msg       = f"⚠️  Fallo en fase {fase_nombre}"
            color_ftr = "#922b21"

        try:
            self._lbl_estado.configure(text=msg)
            # Cambiar color del footer
            pill = self._lbl_estado.master
            pill.configure(fg_color=color_ftr)
        except tk.TclError:
            pass

        # Ocultar botón ABORTAR y mostrar botón CONFIRMAR
        try:
            info = self._btn_abort.place_info()
            self._btn_abort.place_forget()
            if info:
                self._btn_confirm.place(
                    relx=float(info["relx"]),
                    rely=float(info["rely"]),
                    relwidth=float(info["relwidth"]),
                    relheight=float(info["relheight"]),
                    in_=self._btn_abort.master,
                )
            else:
                logger.warning("_on_ciclo_fin: _btn_abort not placed — CONFIRMAR not shown")
        except tk.TclError:
            pass

    # ══════════════════════════════════════════════════════════════════════
    # CONFIRMACIÓN DEL OPERADOR
    # ══════════════════════════════════════════════════════════════════════

    def _do_confirm(self):
        """El operador confirma que vio el resultado del ciclo."""
        logger.info("CycleWindow: operador confirmó resultado del ciclo")
        self.ui_service.acknowledge_cycle()
        self._close()

    # ══════════════════════════════════════════════════════════════════════
    # ABORTAR
    # ══════════════════════════════════════════════════════════════════════

    def _confirmar_abort(self):
        """Diálogo de confirmación antes de ejecutar el abort."""
        if self._closing or self._ciclo_terminado:
            return

        dlg = tk.Toplevel(self)
        dlg.overrideredirect(True)   # sin barra de título ni botones del SO
        dlg.configure(bg=CLR_DARK)
        dlg.resizable(False, False)
        dlg.grab_set()

        # Centrar sobre CycleWindow
        self.update_idletasks()
        w, h = 440, 230
        x = self.winfo_x() + (self.winfo_width()  - w) // 2
        y = self.winfo_y() + (self.winfo_height() - h) // 2
        dlg.geometry(f"{w}x{h}+{x}+{y}")

        ctk.CTkLabel(dlg,
                    text="¿Abortar el ciclo?",
                    font=("Segoe UI", 22, "bold"),
                    text_color=CLR_W, fg_color="transparent",
                    ).pack(pady=(30, 8))

        ctk.CTkLabel(dlg,
                    text="La cámara ejecutará el protocolo de seguridad.",
                    font=("Segoe UI", 14),
                    text_color="#b0c4d4", fg_color="transparent",
                    ).pack(pady=(0, 22))

        btns = tk.Frame(dlg, bg=CLR_DARK)
        btns.pack()

        ctk.CTkButton(btns, text="Cancelar",
                    font=("Segoe UI", 16),
                    fg_color="#5789a7", hover_color="#406080",
                    width=160, height=44,
                    command=dlg.destroy,
                    ).pack(side=tk.LEFT, padx=12)

        ctk.CTkButton(btns, text="ABORTAR",
                    font=("Segoe UI", 16, "bold"),
                    fg_color=CLR_WARN, hover_color="#922b21",
                    width=160, height=44,
                    command=lambda: [dlg.destroy(), self._do_abort()],
                    ).pack(side=tk.LEFT, padx=12)

    def _do_abort(self):
        logger.warning("Operador ABORTÓ el ciclo")
        self.ui_service.abort_cycle()
        try:
            self._lbl_estado.configure(text="⏹  Abortando ciclo...")
        except tk.TclError:
            pass

    # ══════════════════════════════════════════════════════════════════════
    # CIERRE
    # ══════════════════════════════════════════════════════════════════════

    def _close(self):
        self._closing = True
        self.grab_release()
        self.destroy()
        logger.info("CycleWindow cerrada")
        if self._on_close:
            try:
                self._on_close()
            except Exception:
                pass

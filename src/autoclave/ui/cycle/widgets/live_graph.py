# ui/cycle/widgets/live_graph.py
#
# Gráfica en tiempo real de temperatura y presión.
# Usa matplotlib embebido en Tkinter (FigureCanvasTkAgg).
#
# - Temperatura: línea negra, eje Y izquierdo (°C)
# - Presión:     línea azul,  eje Y derecho  (kPa)
# - Líneas verticales grises en cada cambio de fase

import tkinter as tk
import logging

logger = logging.getLogger(__name__)

CLR_BG   = "#ffffff"
CLR_TEMP = "#1a1a1a"   # negro
CLR_PRES = "#3a9ad9"   # azul
CLR_GRID = "#e8e8e8"
CLR_FASE = "#9aabbf"   # gris azulado para líneas de fase

try:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    _MPL_OK = True
except ImportError:
    _MPL_OK = False
    logger.warning("matplotlib no instalado — gráfica de ciclo deshabilitada")


class LiveGraph(tk.Frame):
    """
    Gráfica T/P en tiempo real embebida en un Frame de Tkinter.

    Uso:
        g = LiveGraph(parent)
        g.place(...)
        g.update_data(points, phase_boundaries)   # cada N segundos
        g.clear()                                  # al reiniciar ciclo
    """

    def __init__(self, parent, bg: str = CLR_BG, **kwargs):
        super().__init__(parent, bg=bg, **kwargs)
        self._vlines: list        = []   # objetos axvline activos
        self._vtexts: list        = []   # etiquetas de fase
        self._prev_n_boundaries   = 0    # para añadir solo líneas nuevas

        if _MPL_OK:
            self._build_figure(bg)
        else:
            tk.Label(
                self,
                text="matplotlib no disponible\nInstala: pip install matplotlib",
                bg=bg, fg="#aaaaaa",
                font=("Segoe UI", 13),
                justify="center",
            ).pack(expand=True)

    # ------------------------------------------------------------------
    # Construcción
    # ------------------------------------------------------------------

    def _build_figure(self, bg: str):
        self._fig = Figure(facecolor=bg)
        self._fig.subplots_adjust(left=0.09, right=0.91, top=0.93, bottom=0.13)

        self._ax_t = self._fig.add_subplot(111)
        self._ax_p = self._ax_t.twinx()

        # ── Eje temperatura (izquierdo) ───────────────────────────────────
        self._ax_t.set_facecolor(bg)
        self._ax_t.tick_params(axis="y", labelcolor=CLR_TEMP, labelsize=8)
        self._ax_t.tick_params(axis="x", labelsize=8)
        self._ax_t.set_xlabel("Tiempo (min)", fontsize=8, color="#666666")
        self._ax_t.set_ylabel("°C", fontsize=9, color=CLR_TEMP, labelpad=4)
        self._ax_t.grid(True, color=CLR_GRID, linewidth=0.6, linestyle="--")
        self._ax_t.spines["top"].set_visible(False)

        # ── Eje presión (derecho) ─────────────────────────────────────────
        self._ax_p.tick_params(axis="y", labelcolor=CLR_PRES, labelsize=8)
        self._ax_p.set_ylabel("kPa", fontsize=9, color=CLR_PRES, labelpad=4)
        self._ax_p.spines["top"].set_visible(False)

        # ── Líneas de datos (vacías al inicio) ────────────────────────────
        (self._line_t,) = self._ax_t.plot(
            [], [], color=CLR_TEMP, linewidth=1.8, label="Temp"
        )
        (self._line_p,) = self._ax_p.plot(
            [], [], color=CLR_PRES, linewidth=1.8, label="Pres"
        )

        # ── Canvas Tkinter ────────────────────────────────────────────────
        self._canvas = FigureCanvasTkAgg(self._fig, master=self)
        widget = self._canvas.get_tk_widget()
        widget.configure(bg=bg, highlightthickness=0)
        widget.pack(fill=tk.BOTH, expand=True)

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def update_data(self, points: list, phase_boundaries: list):
        """
        Actualiza la gráfica con los datos del buffer.

        points          : [(t_min, temp, pres), ...]
        phase_boundaries: [(t_min, fase_nombre), ...]
        """
        if not _MPL_OK or not points:
            return

        # ── Datos de las curvas ───────────────────────────────────────────
        t_list    = [p[0] for p in points]
        temp_list = [p[1] if p[1] is not None else float("nan") for p in points]
        pres_list = [p[2] if p[2] is not None else float("nan") for p in points]

        self._line_t.set_data(t_list, temp_list)
        self._line_p.set_data(t_list, pres_list)

        # Escalar ejes automáticamente
        self._ax_t.relim()
        self._ax_t.autoscale_view()
        self._ax_p.relim()
        self._ax_p.autoscale_view()

        # ── Líneas de fase (solo añadir las nuevas) ───────────────────────
        if len(phase_boundaries) > self._prev_n_boundaries:
            nuevas = phase_boundaries[self._prev_n_boundaries:]
            ylim = self._ax_t.get_ylim()
            y_label = ylim[1] - (ylim[1] - ylim[0]) * 0.05

            for t_fase, nombre in nuevas:
                vl = self._ax_t.axvline(
                    x=t_fase,
                    color=CLR_FASE,
                    linewidth=1.0,
                    linestyle="--",
                    alpha=0.8,
                    zorder=3,
                )
                # Etiqueta abreviada encima de la línea
                abrev = nombre[:4].upper()
                txt = self._ax_t.text(
                    t_fase, y_label, abrev,
                    fontsize=6, color=CLR_FASE,
                    ha="center", va="top", zorder=4,
                )
                self._vlines.append(vl)
                self._vtexts.append(txt)

            self._prev_n_boundaries = len(phase_boundaries)

        self._canvas.draw_idle()

    def clear(self):
        """Limpia la gráfica para un nuevo ciclo."""
        if not _MPL_OK:
            return

        self._line_t.set_data([], [])
        self._line_p.set_data([], [])

        for obj in self._vlines + self._vtexts:
            try:
                obj.remove()
            except Exception:
                pass

        self._vlines.clear()
        self._vtexts.clear()
        self._prev_n_boundaries = 0
        self._canvas.draw_idle()

# ui_qml/domain/ciclo_en_curso.py
#
# Datos de la pantalla de ciclo en curso (Pantallas/PantallaCicloEnCurso.qml)
# a partir de las respuestas del backend:
#   GET /cycle/current/progress -> fases que aplican, estado y duración por fase,
#                                  transcurrido y restante (s, reloj monotónico)
#   GET /cycle/current/graph    -> serie de la gráfica (histórico + incremental)
#
# La UI no calcula tiempos ni traduce fases: solo valida (frontera de confianza,
# §6.1 principio 3 de planeacion_ui_dual_pantalla.md) y reorganiza para QML.
# Un dato mal formado se descarta o queda sin lectura (None), nunca tumba el resto.

import math

from autoclave.core.runtime.progreso_ciclo import FASES_UI

_ESTADOS_FASE = {"completada", "activa", "pendiente"}
_RESULTADOS = {"exitoso", "cancelado", "fallo"}
_SERIES = ("temp_camara", "temp_ref", "pres_camara")


def _numero(valor) -> float | None:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    return float(valor) if math.isfinite(valor) else None


class AcumuladorGrafica:
    """Serie de la gráfica del ciclo en curso, acumulada de forma incremental.

    desde_id: último id recibido (None = pedir el histórico completo).
    Si el backend responde con otro ciclo, se descarta lo acumulado.
    """

    def __init__(self):
        self.ciclo_db_id: int | None = None
        self._reiniciar()

    def _reiniciar(self):
        self.desde_id: int | None = None
        self._t_min: list[float] = []
        self._fase_ui: list[str | None] = []
        self._series: dict[str, list] = {s: [] for s in _SERIES}

    def incorporar(self, respuesta) -> bool:
        """Agrega las lecturas nuevas; True si cambió algo."""
        if not isinstance(respuesta, dict):
            return False
        lecturas = respuesta.get("lecturas")
        if not isinstance(lecturas, list):
            return False

        cambio = False
        ciclo = respuesta.get("ciclo_db_id")
        if ciclo != self.ciclo_db_id:
            cambio = bool(self._t_min) or self.ciclo_db_id is not None
            self.ciclo_db_id = ciclo
            self._reiniciar()

        for lectura in lecturas:
            if not isinstance(lectura, dict):
                continue
            ident, t_s = lectura.get("id"), _numero(lectura.get("t_s"))
            if isinstance(ident, bool) or not isinstance(ident, int) or t_s is None:
                continue
            if self.desde_id is not None and ident <= self.desde_id:
                continue
            self.desde_id = ident
            self._t_min.append(t_s / 60.0)
            fase = lectura.get("fase_ui")
            self._fase_ui.append(fase if fase in FASES_UI else None)
            for s in _SERIES:
                self._series[s].append(_numero(lectura.get(s)))
            cambio = True
        return cambio

    def datos(self) -> dict:
        return {"t_min": list(self._t_min), **{s: list(v) for s, v in self._series.items()}}

    def inicios_de_fase(self, aplicables) -> list[dict]:
        """Inicio (min) de cada fase que aplica, en orden de aparición. La
        primera dibujada arranca en 0 (una fase saltada deja un instante suelto)."""
        inicios: list[dict] = []
        vistas: set[str] = set()
        for t, fase in zip(self._t_min, self._fase_ui):
            if fase is None or fase in vistas or fase not in aplicables:
                continue
            vistas.add(fase)
            inicios.append({"clave": fase, "inicioMin": 0.0 if not inicios else t})
        return inicios


def normalizar_progreso(respuesta) -> dict:
    """Respuesta de GET /cycle/current/progress validada para la pantalla."""
    vacio = {"activo": False, "ciclo_db_id": None, "fase_ciclo": "", "fase_activa": None,
             "resultado": None,
             "no_conforme": False, "motivo_no_conforme": "", "no_conforme_reconocido": False,
             "fases": [], "aplicables": [], "transcurrido_s": None, "restante_s": None}
    if not isinstance(respuesta, dict) or respuesta.get("activo") is not True:
        return vacio

    fases = []
    for f in respuesta.get("fases") if isinstance(respuesta.get("fases"), list) else []:
        if not isinstance(f, dict) or f.get("fase") not in FASES_UI:
            continue
        estado = f.get("estado")
        fases.append({
            "fase": f["fase"],
            "estado": estado if estado in _ESTADOS_FASE else "pendiente",
            "duracion_s": _numero(f.get("duracion_s")),
        })

    no_conforme = respuesta.get("no_conforme") is True
    motivo = respuesta.get("motivo_no_conforme")
    fase_activa = respuesta.get("fase_activa")
    fase_ciclo = respuesta.get("fase_ciclo")
    ciclo = respuesta.get("ciclo_db_id")
    return {
        "activo": True,
        "ciclo_db_id": ciclo if isinstance(ciclo, int) and not isinstance(ciclo, bool) else None,
        "fase_ciclo": fase_ciclo if isinstance(fase_ciclo, str) else "",
        "fase_activa": fase_activa if fase_activa in FASES_UI else None,
        "resultado": respuesta.get("resultado") if respuesta.get("resultado") in _RESULTADOS else None,
        # P4 (tanda 16, D-14.4): solo True estricto (un dato mal formado no
        # marca NO CONFORME ni da por reconocida la carga)
        "no_conforme": no_conforme,
        "motivo_no_conforme": motivo if no_conforme and isinstance(motivo, str) else "",
        "no_conforme_reconocido": no_conforme and respuesta.get("no_conforme_reconocido") is True,
        "fases": fases,
        "aplicables": [f["fase"] for f in fases],
        "transcurrido_s": _numero(respuesta.get("transcurrido_s")),
        "restante_s": _numero(respuesta.get("restante_s")),
    }

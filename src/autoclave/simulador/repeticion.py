# simulador/repeticion.py
#
# Reproducción de un ciclo COMPLETADO guardado en la BD, para el backend simulado
# (simulador/servidor.py). HERRAMIENTA DE DESARROLLO: sirve para probar la UI sin
# módulo E/S; no forma parte del control ni toca hardware. La BD se abre en solo
# lectura.
#
# Las lecturas del ticket son escasas (cada 30–60 s y en cada cambio de fase), así
# que entre lecturas se interpola linealmente. Aproximaciones (solo simulación):
#   - PG (purga, ya eliminada) y W (código antiguo) se cuentan como PRE_VACIO.
#   - Descompresión y secado comparten el código " " y casi no dejan lecturas:
#     se separan donde la presión interpolada cruza la atmosférica.
#   - La BD no guarda temp_ref: se simula como temp_camara con RETRASO_REF_S de retraso.

import sqlite3
from pathlib import Path

MIN_LECTURAS = 20
P_ATMOSFERICA_KPA = 101.3
RETRASO_REF_S = 20.0

_CODIGO_A_FASE = {
    "PH": "PRECALENTAMIENTO",
    "PG": "PRE_VACIO",
    "PV": "PRE_VACIO",
    "W":  "PRE_VACIO",
    "H":  "CALENTAMIENTO",
    "S":  "ESTERILIZACION",
    " ":  "DESCOMPRESION",   # + SECADO, ver _separar_descompresion
}


def _segundos(rel: str) -> int:
    h, m, s = (int(x) for x in rel.split(":"))
    return h * 3600 + m * 60 + s


def cargar_ciclo(db_path, ciclo_id: int | None = None) -> dict:
    """Ciclo y sus lecturas, leídos en solo lectura. Sin ciclo_id: el último
    COMPLETADO con al menos MIN_LECTURAS lecturas."""
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    try:
        if ciclo_id is None:
            fila = con.execute(
                "SELECT c.* FROM ciclos c WHERE c.resultado='COMPLETADO'"
                " AND (SELECT COUNT(*) FROM lecturas l WHERE l.ciclo_id=c.id) >= ?"
                " ORDER BY c.id DESC LIMIT 1", (MIN_LECTURAS,)).fetchone()
        else:
            fila = con.execute("SELECT * FROM ciclos WHERE id=?", (ciclo_id,)).fetchone()
        if fila is None:
            raise LookupError("No hay un ciclo COMPLETADO con lecturas suficientes para simular")
        lecturas = [
            {"t_s": _segundos(r["timestamp_rel"]), "codigo": r["fase_codigo"],
             "temp_camara": r["temp_camara"], "pres_camara": r["pres_camara"]}
            for r in con.execute("SELECT * FROM lecturas WHERE ciclo_id=? ORDER BY id", (fila["id"],))
        ]
    finally:
        con.close()
    return {"id": fila["id"], "numero_ciclo": fila["numero_ciclo"],
            "tipo_ciclo": fila["tipo_ciclo"], "nombre_ciclo": fila["nombre_ciclo"],
            "fila": dict(fila), "lecturas": lecturas}


def _interpolar(puntos, t):
    """puntos: [(t, valor)] ordenados; valores None se ignoran."""
    validos = [(x, v) for x, v in puntos if v is not None]
    if not validos:
        return None
    if t <= validos[0][0]:
        return validos[0][1]
    for (x0, v0), (x1, v1) in zip(validos, validos[1:]):
        if t <= x1:
            return v0 if x1 == x0 else v0 + (v1 - v0) * (t - x0) / (x1 - x0)
    return validos[-1][1]


class Repeticion:
    def __init__(self, ciclo: dict):
        self.ciclo = ciclo
        ordenadas = sorted(ciclo["lecturas"], key=lambda l: l["t_s"])
        fin = next((l["t_s"] for l in ordenadas if l["codigo"] == "E"), ordenadas[-1]["t_s"])
        self.duracion_s = fin
        # lecturas del ciclo hasta el fin (incluida la primera E, que da el valor final)
        self._lecturas = [l for l in ordenadas if l["t_s"] <= fin]
        self._temp = [(l["t_s"], l["temp_camara"]) for l in self._lecturas]
        self._pres = [(l["t_s"], l["pres_camara"]) for l in self._lecturas]
        self.tramos = self._construir_tramos()

    def _construir_tramos(self):
        inicios = []
        for l in self._lecturas:
            fase = _CODIGO_A_FASE.get(l["codigo"])
            if fase is None or (inicios and inicios[-1][0] == fase):
                continue
            inicios.append((fase, l["t_s"]))
        tramos = []
        for i, (fase, t0) in enumerate(inicios):
            t1 = inicios[i + 1][1] if i + 1 < len(inicios) else self.duracion_s
            if fase == "DESCOMPRESION":
                tramos.extend(self._separar_descompresion(t0, t1))
            else:
                tramos.append((fase, t0, t1))
        if tramos:   # la primera fase arranca con el ciclo
            fase, _, t1 = tramos[0]
            tramos[0] = (fase, 0, t1)
        return tramos

    def _separar_descompresion(self, t0, t1):
        corte = None
        for t in range(int(t0), int(t1) + 1):
            p = _interpolar(self._pres, t)
            if p is not None and p <= P_ATMOSFERICA_KPA:
                corte = t
                break
        if corte is None or corte >= t1:
            return [("DESCOMPRESION", t0, t1)]
        return [("DESCOMPRESION", t0, corte), ("SECADO", corte, t1)]

    def fase_en(self, t: float) -> str:
        for fase, t0, t1 in self.tramos:
            if t < t1:
                return fase
        return self.tramos[-1][0]

    def muestra(self, t: float) -> dict:
        t = max(0.0, min(float(t), float(self.duracion_s)))
        return {
            "fase": self.fase_en(t),
            "temp_camara": _interpolar(self._temp, t),
            "temp_ref": _interpolar(self._temp, max(0.0, t - RETRASO_REF_S)),   # SIMULADA
            "pres_camara": _interpolar(self._pres, t),
        }

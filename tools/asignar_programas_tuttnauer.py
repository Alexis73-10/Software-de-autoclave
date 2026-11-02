"""Asigna numero_programa y tipo_ciclo a los ciclos importados de Tuttnauer
(herramienta de desarrollo; BD del simulador data/autoclave.db).

Uso: python tools/asignar_programas_tuttnauer.py [--bd data/autoclave.db]

Hace un respaldo previo (API de respaldo de sqlite) en <bd>.bak-AAAAMMDD_HHMM y
actualiza solo las filas con numero_programa NULL, según nombre_ciclo. Es
idempotente y no toca nombre_ciclo.
"""
import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

# nombre_ciclo de Tuttnauer -> (numero_programa, id de programa = tipo_ciclo)
MAPA_PROGRAMAS = {
    "INSTRUMENTAL PL": (2, "134_instrumental"),
    "Liquidos A": (4, "liquidos"),
    "TEXTILES": (5, "textiles"),
}


def respaldar(bd):
    destino = Path(f"{bd}.bak-{datetime.now():%Y%m%d_%H%M}")
    origen, copia = sqlite3.connect(bd), sqlite3.connect(destino)
    try:
        origen.backup(copia)
    finally:
        copia.close()
        origen.close()
    return destino


def asignar(bd):
    """Devuelve {nombre_ciclo: filas actualizadas}."""
    con = sqlite3.connect(bd)
    try:
        cuenta = {}
        for nombre, (numero, tipo) in MAPA_PROGRAMAS.items():
            cur = con.execute(
                "UPDATE ciclos SET numero_programa=?, tipo_ciclo=?"
                " WHERE nombre_ciclo=? AND numero_programa IS NULL", (numero, tipo, nombre))
            cuenta[nombre] = cur.rowcount
        con.commit()
        return cuenta
    finally:
        con.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bd", default="data/autoclave.db")
    a = ap.parse_args()
    if not Path(a.bd).is_file():
        raise SystemExit(f"No existe {a.bd}")
    print("Respaldo:", respaldar(a.bd))
    for nombre, n in asignar(a.bd).items():
        print(f"{nombre}: {n} filas")

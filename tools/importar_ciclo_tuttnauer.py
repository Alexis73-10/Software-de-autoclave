"""Importa un ticket de historial Tuttnauer (cycle_NNNNNN.txt) como un ciclo en la
BD del simulador (data/autoclave.db). Herramienta de desarrollo.

Uso: python tools/importar_ciclo_tuttnauer.py <archivo.txt> [--bd data/autoclave.db]

Códigos del ticket: W/H/S se conservan; la E de Tuttnauer (escape) pasa a " "
(descompresión, como espera simulador/repeticion.py) y la última lectura queda
como "E" (fin del ciclo).
"""
import argparse
import re
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from autoclave.services.domain.logging.db_manager import DB_DEFAULT

try:
    from asignar_programas_tuttnauer import MAPA_PROGRAMAS
except ImportError:      # importado como tools.importar_ciclo_tuttnauer
    from tools.asignar_programas_tuttnauer import MAPA_PROGRAMAS

_MESES = {"ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6, "JUL": 7,
          "AGO": 8, "JAN": 1, "APR": 4, "AUG": 8, "DEC": 12, "SEP": 9, "SET": 9, "OCT": 10, "NOV": 11, "DIC": 12}
_LECTURA = re.compile(r"^([WHSE ])\s*(\d\d:\d\d:\d\d)\s+(\d+\.\d)\s+(\d+\.\d)\s*$")


def _campo(texto, clave):
    m = re.search(rf"^{clave}\s*(.+?)\s*$", texto, re.M)
    return m.group(1) if m else ""


def leer(ruta):
    texto = Path(ruta).read_text(encoding="utf-8", errors="replace")
    d, mes, a = re.match(r"(\d+)/(\w+)/(\d+)", _campo(texto, "Fecha:")).groups()
    hora = _campo(texto, "Hora:").split()[0]
    inicio = datetime.strptime(f"{a}-{_MESES[mes.upper()]:02d}-{int(d):02d} {hora}", "%Y-%m-%d %H:%M:%S")
    fin_h = re.findall(r"^Hora:\s*(\S+)", texto, re.M)[-1]
    fin = datetime.combine(inicio.date(), datetime.strptime(fin_h, "%H:%M:%S").time())
    lecturas, vistas = [], set()
    for linea in texto.splitlines():
        m = _LECTURA.match(linea)
        if not m:
            continue
        clave = (m[1], m[2])
        if clave in vistas:          # el ticket repite la última S
            continue
        vistas.add(clave)
        lecturas.append([m[1], m[2], float(m[3]), float(m[4])])
    for l in lecturas:
        if l[0] == "E":
            l[0] = " "
    lecturas[-1][0] = "E"
    error = re.search(r"Error de ciclo:[ \t]*\n(.+)", texto)
    motivo = error.group(1).strip() if error else ""
    resultado = ("COMPLETADO" if "Ciclo acabado" in texto
                 else "CANCELADO" if "Cancelado" in motivo else "FALLO")
    return {
        "numero": int(_campo(texto, "Número de ciclo:")),
        "inicio": inicio, "fin": fin, "lecturas": lecturas,
        "serie": _campo(texto, "Núm de serie:"), "modelo": _campo(texto, "Modelo:"),
        "version": _campo(texto, r"Ver de SoftW\.:"),
        "nombre": re.search(r"Número de ciclo:.*\n(.+)", texto).group(1).strip(),
        "tipo": (re.search(r"^\((.+)\)", texto, re.M) or [None, ""])[1],
        "temp": float((re.search(r"Temp\. Ester\.\s*([\d.]+)", texto) or [0, 0])[1]) or None,
        "tiempo": float((re.search(r"Tiempo Ester\s*([\d.]+)", texto) or [0, 0])[1]) or None,
        "resultado": resultado, "motivo": "" if resultado == "CANCELADO" else motivo,
    }


def importar(ruta, bd):
    c = leer(ruta)
    numero_programa, tipo_programa = MAPA_PROGRAMAS.get(c["nombre"], (None, c["tipo"]))
    con = sqlite3.connect(bd)
    try:
        con.execute("PRAGMA foreign_keys = ON")
        if con.execute("SELECT 1 FROM ciclos WHERE numero_ciclo=?", (c["numero"],)).fetchone():
            raise SystemExit(f"Ya existe el ciclo {c['numero']} en {bd}")
        cur = con.execute(
            "INSERT INTO ciclos (numero_ciclo, fecha_inicio, fecha_fin, tipo_ciclo, nombre_ciclo,"
            " resultado, temp_esterilizacion, tiempo_esterilizacion, modelo, serie, version_sw,"
            " operador, uuid, motivo_fallo, numero_programa) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (c["numero"], c["inicio"].isoformat(), c["fin"].isoformat(), tipo_programa, c["nombre"],
             c["resultado"], c["temp"], c["tiempo"], c["modelo"], c["serie"], c["version"], "",
             str(uuid.uuid4()), c["motivo"], numero_programa))
        cid = cur.lastrowid
        con.executemany(
            "INSERT INTO lecturas (ciclo_id, timestamp_rel, timestamp_abs, fase_codigo,"
            " temp_camara, pres_camara, para_imprimir, temp_principal) VALUES (?,?,?,?,?,?,1,?)",
            [(cid, rel, (c["inicio"] + timedelta(
                seconds=sum(int(x) * k for x, k in zip(rel.split(":"), (3600, 60, 1))))).isoformat(),
              cod, t, p, t) for cod, rel, t, p in c["lecturas"]])
        con.commit()
        return cid, c["numero"], len(c["lecturas"])
    finally:
        con.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("ruta", help="archivo .txt o carpeta con cycle_*.txt")
    ap.add_argument("--bd", default=str(DB_DEFAULT))
    a = ap.parse_args()
    ruta = Path(a.ruta)
    for f in (sorted(ruta.glob("cycle_*.txt")) if ruta.is_dir() else [ruta]):
        try:
            print(f.name, "id=%d numero=%d lecturas=%d" % importar(f, a.bd))
        except (Exception, SystemExit) as e:
            print(f.name, "OMITIDO:", e)

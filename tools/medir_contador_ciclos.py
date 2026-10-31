"""Mide cuánto tardan `ContadorCiclos.siguiente` y `marcar_en_curso` (las dos
llamadas síncronas que CycleLogger hace en el tick al iniciar un ciclo; B9a de
la tanda 4). Uso: python tools/medir_contador_ciclos.py [N] [carpeta]
La carpeta debe estar en el disco del equipo (el fsync depende del disco)."""

import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from autoclave.core.runtime.contador_ciclos import ContadorCiclos  # noqa: E402


def medir(n: int = 100, carpeta: str | None = None) -> dict:
    base = Path(carpeta or tempfile.mkdtemp())
    contador = ContadorCiclos(base / "ciclo_contador.json")
    programa = {"id": "x", "parameters": {"a": {"b": 1}}}
    siguiente, marcar = [], []
    for _ in range(n):
        t = time.perf_counter()
        numero = contador.siguiente(None)
        siguiente.append((time.perf_counter() - t) * 1000)
        t = time.perf_counter()
        contador.marcar_en_curso(numero, programa)
        marcar.append((time.perf_counter() - t) * 1000)
        contador.limpiar_en_curso(solo_numero=numero)

    def resumen(v):
        v = sorted(v)
        return {"p50_ms": round(statistics.median(v), 2), "p95_ms": round(v[int(len(v) * 0.95) - 1], 2),
                "max_ms": round(v[-1], 2)}
    return {"n": n, "siguiente": resumen(siguiente), "marcar_en_curso": resumen(marcar)}


if __name__ == "__main__":
    print(medir(int(sys.argv[1]) if len(sys.argv) > 1 else 100, sys.argv[2] if len(sys.argv) > 2 else None))

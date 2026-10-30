# tools/registro_pruebas/definiciones.py
#
# Definiciones de las pruebas, generadas desde la fuente única
# docs/mis_plans/hoja_pruebas_banco/pruebas.py (F1, tanda 3). Al crear un
# registro se guarda una COPIA (snapshot) con su versión y hash SHA-256: un
# cambio posterior de pruebas.py no altera un registro ya iniciado.

import hashlib
import importlib.util
import json
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
FUENTE = RAIZ / "docs" / "mis_plans" / "hoja_pruebas_banco" / "pruebas.py"

# Orden seguro de la hoja: antes del bloque E (y de los siguientes en operación)
# deben estar hechas estas pruebas. Solo se AVISA, no se bloquea.
REQUERIDAS_ANTES = {"E": ["A-04", "B-01", "B-03", "B-04"],
                    "F": ["A-04", "B-01", "B-03", "B-04"],
                    "G": ["A-04", "B-01", "B-03", "B-04"]}
RESULTADOS = ("aprobada", "fallada", "no_aplica")


def hash_canonico(obj) -> str:
    texto = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def cargar_fuente(ruta: Path | None = None) -> dict:
    """Importa pruebas.py (la ruta puede cambiarse con REGISTRO_PRUEBAS_FUENTE)."""
    ruta = Path(ruta or os.environ.get("REGISTRO_PRUEBAS_FUENTE") or FUENTE)
    spec = importlib.util.spec_from_file_location("pruebas_fuente", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return {"bloques": [list(b) for b in modulo.BLOQUES],
            "pruebas": [dict(p) for p in modulo.PRUEBAS],
            "registros": list(getattr(modulo, "REGISTROS", []))}


def construir_snapshot(ruta: Path | None = None) -> dict:
    """Snapshot listo para guardar: definiciones + hash (la 'versión')."""
    datos = cargar_fuente(ruta)
    datos["requeridas_antes"] = REQUERIDAS_ANTES
    pruebas_ids = [p["id"] for p in datos["pruebas"]]
    if len(set(pruebas_ids)) != len(pruebas_ids):
        raise ValueError("pruebas.py tiene ids de prueba repetidos")
    return {**datos, "hash": hash_canonico(datos), "total": len(pruebas_ids)}


def verificar_snapshot(snapshot: dict) -> bool:
    """True si el snapshot guardado no fue alterado (el hash coincide)."""
    sin_hash = {k: v for k, v in snapshot.items() if k not in ("hash", "total")}
    return hash_canonico(sin_hash) == snapshot.get("hash")


def prueba_por_id(snapshot: dict, prueba_id: str) -> dict | None:
    return next((p for p in snapshot["pruebas"] if p["id"] == prueba_id), None)


def avisos_orden(snapshot: dict, prueba_id: str, estados: dict) -> list[str]:
    """Pruebas requeridas por el orden seguro que aún no están aprobadas.
    `estados`: {prueba_id: resultado vigente}. No bloquea: solo informa."""
    prueba = prueba_por_id(snapshot, prueba_id)
    if prueba is None:
        return []
    return [f"{req}" for req in snapshot.get("requeridas_antes", {}).get(prueba["bloque"], [])
            if estados.get(req) != "aprobada"]

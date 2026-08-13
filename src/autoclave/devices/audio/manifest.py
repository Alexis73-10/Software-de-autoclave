import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import soundfile as sf


class ManifestError(Exception):
    pass


@dataclass
class EventoAudio:
    event_id: str
    prioridad: int
    cooldown_s: float
    texto: str
    samples: object
    sample_rate: int


def load_manifest(manifest_path: Path, idioma: str = "es") -> dict:
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        raise ManifestError(f"No se pudo leer el manifiesto: {exc}") from exc

    if not isinstance(data, dict):
        raise ManifestError("Manifiesto invalido: la raiz debe ser un objeto")

    eventos = {}
    base_dir = Path(manifest_path).parent

    eventos_raw = data.get("eventos", {})
    if not isinstance(eventos_raw, dict):
        raise ManifestError("Manifiesto invalido: 'eventos' debe ser un objeto")

    for event_id, meta in eventos_raw.items():
        if not isinstance(meta, dict):
            raise ManifestError(f"Manifiesto invalido: entrada de evento no es un objeto: {event_id}")

        archivos = meta.get("archivos", {})
        if not isinstance(archivos, dict):
            raise ManifestError(f"Manifiesto invalido: 'archivos' no es un objeto para '{event_id}'")
        archivo = archivos.get(idioma)
        if not archivo:
            raise ManifestError(f"Evento sin archivo para idioma '{idioma}': {event_id}")

        wav_path = base_dir / archivo
        try:
            raw = wav_path.read_bytes()
        except OSError as exc:
            raise ManifestError(f"Archivo faltante para '{event_id}': {wav_path}") from exc

        sha256_raw = meta.get("sha256", {})
        if not isinstance(sha256_raw, dict):
            raise ManifestError(f"Manifiesto invalido: 'sha256' no es un objeto para '{event_id}'")
        sha_esperado = sha256_raw.get(idioma)
        if not sha_esperado:
            raise ManifestError(f"Falta sha256 para '{event_id}' (idioma '{idioma}')")
        sha_real = hashlib.sha256(raw).hexdigest()
        if sha_real != sha_esperado:
            raise ManifestError(f"SHA-256 no coincide para '{event_id}'")

        try:
            samples, sample_rate = sf.read(wav_path, dtype="float32")
        except Exception as exc:
            raise ManifestError(f"No se pudo decodificar '{event_id}': {exc}") from exc

        try:
            prioridad = int(meta["prioridad"])
            cooldown_s = float(meta["cooldown_s"])
        except (KeyError, ValueError, TypeError) as exc:
            raise ManifestError(f"Metadato invalido para '{event_id}': {exc}") from exc

        eventos[event_id] = EventoAudio(
            event_id=event_id,
            prioridad=prioridad,
            cooldown_s=cooldown_s,
            texto=meta.get("texto", ""),
            samples=samples,
            sample_rate=sample_rate,
        )

    return eventos

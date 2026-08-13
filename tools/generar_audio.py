# Genera WAV placeholder (tono sintetico, NO locucion real) y el
# manifest.json correspondiente. Sustituir por locucion real (Piper TTS
# u otra) es un paso posterior: basta con reemplazar los .wav y volver a
# correr este script para regenerar el manifiesto con los sha256 nuevos.
import hashlib
import json
from pathlib import Path

import numpy as np
import soundfile as sf

SAMPLE_RATE = 22050

_COOLDOWN_POR_PRIORIDAD = {0: 60, 1: 60, 2: 60, 3: 5, 4: 5, 5: 5}

# (event_id, prioridad, texto) — catalogo de spec docs/mis_plans/planeacion_anuncios_voz.md §4
CATALOGO = [
    ("emg_paro_emergencia", 0, "Paro de emergencia activado."),
    ("emg_fallo_electrico", 0, "Fallo de suministro electrico."),
    ("emg_sensor_ausente", 0, "Sensor critico ausente. Ciclo abortado."),
    ("emg_puerta_1_atrapada", 0, "Atrapamiento en puerta uno."),
    ("emg_puerta_2_atrapada", 0, "Atrapamiento en puerta dos."),
    ("fal_ciclo_abortado", 1, "Ciclo abortado por fallo."),
    ("fal_camara_segura", 1, "Camara en condiciones seguras."),
    ("fal_puerta_1_error", 1, "Fallo en puerta uno."),
    ("fal_puerta_2_error", 1, "Fallo en puerta dos."),
    ("alr_sum_agua_bomba", 2, "Falta suministro de agua de bomba."),
    ("alr_sum_agua_generador", 2, "Falta suministro de agua de generador."),
    ("alr_sum_aire_comprimido", 2, "Falta suministro de aire comprimido."),
    ("alr_sum_electrico", 2, "Alerta de suministro electrico."),
    ("alr_ai_pres_camara", 2, "Error en sensor de presion de camara."),
    ("alr_ai_pres_chaqueta", 2, "Error en sensor de presion de chaqueta."),
    ("alr_ai_pres_empaque_1", 2, "Error en sensor de presion de empaque uno."),
    ("alr_ai_pres_empaque_2", 2, "Error en sensor de presion de empaque dos."),
    ("alr_ai_temp_camara", 2, "Error en sensor de temperatura de camara."),
    ("alr_ai_temp_2_camara", 2, "Error en sensor de temperatura de camara dos."),
    ("alr_ai_temp_ref", 2, "Error en sensor de temperatura de referencia."),
    ("alr_ai_temp_chaqueta", 2, "Error en sensor de temperatura de chaqueta."),
    ("alr_ai_temp_drenaje_cam", 2, "Error en sensor de temperatura de drenaje de camara."),
    ("alr_ai_temp_drenaje", 2, "Error en sensor de temperatura de drenaje."),
    ("pta_1_abierta", 3, "Puerta uno abierta."),
    ("pta_1_cerrada", 3, "Puerta uno cerrada."),
    ("pta_2_abierta", 3, "Puerta dos abierta."),
    ("pta_2_cerrada", 3, "Puerta dos cerrada."),
    ("cic_iniciado", 4, "Ciclo iniciado."),
    ("cic_completado", 4, "Ciclo completado."),
    ("equipo_preparado", 4, "Equipo preparado."),
    ("sys_bienvenida", 5, "Bienvenido. Autoclave Especifika."),
    ("sys_prueba_audio", 5, "Prueba de audio correcta."),
]


def _tono_placeholder(duracion_s: float = 0.4):
    t = np.linspace(0, duracion_s, int(SAMPLE_RATE * duracion_s), endpoint=False)
    return (0.2 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)


def generar(output_dir: Path) -> None:
    audio_dir = output_dir / "es"
    audio_dir.mkdir(parents=True, exist_ok=True)

    eventos = {}
    onda = _tono_placeholder()
    for event_id, prioridad, texto in CATALOGO:
        wav_path = audio_dir / f"{event_id}.wav"
        sf.write(wav_path, onda, SAMPLE_RATE, subtype="PCM_16")
        sha256 = hashlib.sha256(wav_path.read_bytes()).hexdigest()
        eventos[event_id] = {
            "prioridad": prioridad,
            "cooldown_s": _COOLDOWN_POR_PRIORIDAD[prioridad],
            "texto": texto,
            "archivos": {"es": f"es/{event_id}.wav"},
            "sha256": {"es": sha256},
        }

    manifest = {"version": "1.0", "idioma_default": "es", "eventos": eventos}
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )


if __name__ == "__main__":
    destino = Path(__file__).resolve().parents[1] / "src" / "autoclave" / "assets" / "audio"
    generar(destino)
    print(f"Generados {len(CATALOGO)} audios placeholder en {destino}")

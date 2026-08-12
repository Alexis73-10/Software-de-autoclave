import hashlib
import json

import numpy as np
import pytest
import soundfile as sf

from autoclave.devices.audio.manifest import ManifestError, load_manifest


def _escribir_wav(path, duracion_s=0.1, sample_rate=22050):
    t = np.linspace(0, duracion_s, int(sample_rate * duracion_s), endpoint=False)
    onda = (0.1 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    sf.write(path, onda, sample_rate, subtype="PCM_16")
    return path


def _manifest_valido(tmp_path):
    audio_dir = tmp_path / "es"
    audio_dir.mkdir()
    wav_path = _escribir_wav(audio_dir / "evt_test.wav")
    sha256 = hashlib.sha256(wav_path.read_bytes()).hexdigest()
    manifest = {
        "version": "1.0",
        "idioma_default": "es",
        "eventos": {
            "evt_test": {
                "prioridad": 3,
                "cooldown_s": 5,
                "texto": "Evento de prueba.",
                "archivos": {"es": "es/evt_test.wav"},
                "sha256": {"es": sha256},
            }
        },
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


def test_carga_evento_valido(tmp_path):
    eventos = load_manifest(_manifest_valido(tmp_path))
    assert set(eventos) == {"evt_test"}
    evt = eventos["evt_test"]
    assert evt.event_id == "evt_test"
    assert evt.prioridad == 3
    assert evt.cooldown_s == 5
    assert evt.texto == "Evento de prueba."
    assert evt.sample_rate == 22050
    assert len(evt.samples) > 0


def test_manifest_inexistente_lanza_manifest_error(tmp_path):
    with pytest.raises(ManifestError):
        load_manifest(tmp_path / "no_existe.json")


def test_wav_faltante_lanza_manifest_error(tmp_path):
    manifest_path = _manifest_valido(tmp_path)
    (tmp_path / "es" / "evt_test.wav").unlink()
    with pytest.raises(ManifestError):
        load_manifest(manifest_path)


def test_sha256_incorrecto_lanza_manifest_error(tmp_path):
    manifest_path = _manifest_valido(tmp_path)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["eventos"]["evt_test"]["sha256"]["es"] = "0" * 64
    manifest_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ManifestError):
        load_manifest(manifest_path)

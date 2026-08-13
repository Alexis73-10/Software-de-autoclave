import json

from tools.generar_audio import CATALOGO, generar
from autoclave.devices.audio.manifest import load_manifest

_PRIORIDADES_VALIDAS = {0, 1, 2, 3, 4, 5}


def test_catalogo_tiene_32_eventos_unicos():
    ids = [event_id for event_id, _, _ in CATALOGO]
    assert len(ids) == 32
    assert len(set(ids)) == 32


def test_catalogo_prioridades_validas():
    for _, prioridad, _ in CATALOGO:
        assert prioridad in _PRIORIDADES_VALIDAS


def test_generar_produce_manifiesto_cargable(tmp_path):
    generar(tmp_path)
    eventos = load_manifest(tmp_path / "manifest.json")
    assert set(eventos) == {event_id for event_id, _, _ in CATALOGO}


def test_generar_produce_archivos_wav_para_cada_evento(tmp_path):
    generar(tmp_path)
    for event_id, _, _ in CATALOGO:
        assert (tmp_path / "es" / f"{event_id}.wav").exists()


def test_manifest_tiene_texto_por_evento(tmp_path):
    generar(tmp_path)
    data = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    for event_id, _, texto in CATALOGO:
        assert data["eventos"][event_id]["texto"] == texto

import json

from autoclave.config.preferences import load_preferences, save_preferences


def test_carga_defaults_si_no_existe_archivo(tmp_path):
    prefs = load_preferences(tmp_path / "no_existe.json")
    assert prefs == {"audio": {"enabled": True, "volume": 80}}


def test_carga_defaults_si_json_corrupto(tmp_path):
    path = tmp_path / "preferences.json"
    path.write_text("{esto no es json", encoding="utf-8")
    prefs = load_preferences(path)
    assert prefs == {"audio": {"enabled": True, "volume": 80}}


def test_volumen_fuera_de_rango_usa_default(tmp_path):
    path = tmp_path / "preferences.json"
    path.write_text(json.dumps({"audio": {"enabled": False, "volume": 500}}), encoding="utf-8")
    prefs = load_preferences(path)
    assert prefs == {"audio": {"enabled": False, "volume": 80}}


def test_guardar_y_recargar_conserva_valores(tmp_path):
    path = tmp_path / "preferences.json"
    save_preferences({"audio": {"enabled": False, "volume": 42}}, path)
    assert load_preferences(path) == {"audio": {"enabled": False, "volume": 42}}


def test_guardar_es_atomico_no_deja_archivos_temporales(tmp_path):
    path = tmp_path / "preferences.json"
    save_preferences({"audio": {"enabled": True, "volume": 10}}, path)
    restantes = list(tmp_path.iterdir())
    assert restantes == [path]

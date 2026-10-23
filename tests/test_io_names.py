# B-ES-2 / ES-02: una sola fuente de nombres para Entradas / Salidas.
from autoclave.core.runtime import io_names
from autoclave.core.runtime.status import EstadoAutoclave as E


def test_lee_io_enabled_del_equipo_activo():
    io = io_names.leer_io_enabled()
    # D8-3.17 (tanda 8): el YAML es el máximo físico de la tarjeta
    assert len(io["DI"]) == 14 and len(io["DO"]) == 24 and len(io["AI"]) == 9


def test_canales_di_acv_2026_001():
    canales = io_names.canales_digitales("DI")
    assert len(canales) == 14
    primero = canales[0]
    assert primero["name"] == "aire_comprimido"
    assert primero["i18n"] == "io.di.aire_comprimido"
    assert primero["id"] == "DI 01"
    assert canales[-1]["name"] == "suministro_electrico"


def test_canales_do_con_alias_de_errata_y_momentaneas():
    canales = {c["name"]: c for c in io_names.canales_digitales("DO")}
    assert len(canales) == 24
    # YAML dice atmosferico; EstadoAutoclave.map_do conserva la errata
    aire = canales["aire_atmosferico_camara"]
    assert aire["estado_key"] == "aire_admosferico_camara"
    assert aire["id"] == f"DO {E.map_do['aire_admosferico_camara'] + 1:02d}"
    for nombre in ("abrir_puerta_1", "abrir_puerta_2", "cerrar_puerta_1",
                   "cerrar_puerta_2", "bomba_vacio"):
        assert canales[nombre]["momentanea"] is True
    assert canales["vapor_camara"]["momentanea"] is False


def test_sensores_temperatura_y_presion_sin_canales_inexistentes():
    temp = io_names.sensores("temperature")
    pres = io_names.sensores("pressure")
    # temp_drenaje_camara no tiene posición en la trama: no se lista
    assert [s["name"] for s in temp] == ["temp_camara", "temp_2_camara", "temp_referencia",
                                         "temp_drenaje"]
    assert temp[2]["estado_key"] == "temp_ref"     # alias del YAML
    assert [s["name"] for s in pres] == ["pres_camara", "pres_chaqueta",
                                         "pres_empaque_1", "pres_empaque_2"]
    assert all(s["i18n"].startswith("io.ai.") for s in temp + pres)


def test_sin_archivo_de_instancia_no_lista_nada(tmp_path):
    io = io_names.leer_io_enabled(config_dir=tmp_path)
    assert io == {"DI": [], "DO": [], "AI": []}

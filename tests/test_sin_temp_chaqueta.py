# T-19 (planeacion_backend_autenticacion.md, decisión 24): temp_chaqueta se
# retiró de todos los equipos y sale del mapa de ejecución. La posición 3 de
# la trama de temperaturas ya no se lee y los demás sensores conservan la suya.

from autoclave.core.runtime.status import EstadoAutoclave


def test_temp_chaqueta_fuera_del_mapa_y_el_resto_en_su_posicion():
    assert "temp_chaqueta" not in EstadoAutoclave.map_temp
    assert EstadoAutoclave.map_temp == {
        "temp_camara": 0, "temp_2_camara": 1, "temp_ref": 2,
        "temp_drenaje_cam": 4, "temp_drenaje": 5,
    }


def test_la_trama_se_lee_por_posicion_sin_la_chaqueta():
    estado = EstadoAutoclave()
    estado.update({"temperature": [121.0, 120.5, 119.0, 99.9, 60.0, 40.0]})
    assert estado.sensores_temp == {
        "temp_camara": 121.0, "temp_2_camara": 120.5, "temp_ref": 119.0,
        "temp_drenaje_cam": 60.0, "temp_drenaje": 40.0,
    }

"""S3a (tanda 2, pendiente T3 SAF-03 a): límites de plausibilidad de la
calibración de dos puntos, por tipo de canal, en el catálogo
(core/managers/catalogo_parametros.py). Dos niveles:
- rechazo (422 CALIBRACION_IMPLAUSIBLE): puntos fuera del rango físico del
  canal, puntos demasiado juntos o corrección mayor que la máxima;
- aviso (409 CALIBRACION_REQUIERE_CONFIRMACION): corrección mayor que la de
  aviso; se aplica solo con `confirmar_fuera_de_rango: true` y queda auditada.
Las calibraciones reales que ya existen (calibration.yaml) caben en aviso."""

import textwrap
from unittest.mock import MagicMock

import pytest

from autoclave.core.managers.catalogo_parametros import (
    CALIBRACION_PLAUSIBLE, evaluar_calibracion,
)
from tests.backend_doble import cabecera, cargar_servidor, fijar_en_backend


def _p(sl, rl, sh, rh):
    return {"shown_low": sl, "real_low": rl, "shown_high": sh, "real_high": rh}


@pytest.mark.parametrize("tipo, puntos", [
    ("temperature", _p(60.0, 60.0, 134.5, 135.7)),      # recalibración real 2026-08-04
    ("pressure", _p(12.0, 9.54, 322.0, 300.0)),
])
def test_correcciones_normales_se_aceptan(tipo, puntos):
    assert evaluar_calibracion(tipo, puntos) == (None, "")


@pytest.mark.parametrize("tipo, puntos", [
    ("pressure", _p(105.0, 75.0, 316.0, 365.0)),         # real 2026-07-23: 30 y 49 kPa
    ("pressure", _p(55.0, 10.0, 296.0, 337.0)),          # real 2026-07-23: 45 kPa
    ("temperature", _p(60.0, 52.0, 134.0, 134.0)),       # 8 °C
])
def test_correcciones_grandes_piden_confirmacion(tipo, puntos):
    nivel, motivo = evaluar_calibracion(tipo, puntos)
    assert nivel == "aviso" and motivo


@pytest.mark.parametrize("tipo, puntos", [
    ("temperature", _p(60.0, 60.0, 134.0, 260.0)),       # fuera del rango físico
    ("temperature", _p(-30.0, -30.0, 134.0, 134.0)),
    ("temperature", _p(100.0, 100.0, 110.0, 110.0)),     # puntos a 10 °C
    ("temperature", _p(60.0, 80.0, 134.0, 134.0)),       # corrección de 20 °C
    ("pressure", _p(100.0, 100.0, 120.0, 120.0)),        # puntos a 20 kPa
    ("pressure", _p(100.0, 100.0, 300.0, 380.0)),        # corrección de 80 kPa
    ("pressure", _p(100.0, 100.0, 300.0, 600.0)),        # fuera del rango físico
    ("pressure", _p(float("nan"), 100.0, 300.0, 300.0)),
])
def test_calibraciones_implausibles_se_rechazan(tipo, puntos):
    nivel, motivo = evaluar_calibracion(tipo, puntos)
    assert nivel == "rechazo" and motivo


def test_hay_limites_para_cada_tipo_de_canal():
    assert set(CALIBRACION_PLAUSIBLE) == {"temperature", "pressure"}


# ── Endpoint ─────────────────────────────────────────────────────────────────

@pytest.fixture
def cliente(tmp_path):
    yaml_path = tmp_path / "calibration.yaml"
    yaml_path.write_text(textwrap.dedent("""
        calibration:
          user:
            temperature:
              - gain: 1.0
                offset: 0.0
            pressure:
              - gain: 1.0
                offset: 0.0
              - gain: 1.0
                offset: 0.0
              - gain: 1.0
                offset: 0.0
              - gain: 1.0
                offset: 0.0
    """), encoding="utf-8")
    ctx = MagicMock()
    ctx.db.get_auditoria.return_value = []
    ctx.sin_base_de_datos = False
    srv, _ = cargar_servidor(ctx)
    fijar_en_backend("CALIBRATION_PATH", yaml_path)
    from fastapi.testclient import TestClient
    return TestClient(srv.app, headers=cabecera(srv, "ingeniero")), ctx, yaml_path


def test_endpoint_rechaza_implausible_sin_tocar_el_archivo(cliente):
    client, ctx, yaml_path = cliente
    antes = yaml_path.read_text(encoding="utf-8")
    r = client.patch("/calibration/temperature/temp_camara", json=_p(60.0, 80.0, 134.0, 134.0))
    assert r.status_code == 422 and r.json()["codigo"] == "CALIBRACION_IMPLAUSIBLE"
    assert yaml_path.read_text(encoding="utf-8") == antes
    ctx.units.reload_calibration.assert_not_called()


def test_endpoint_pide_confirmar_la_correccion_grande(cliente):
    client, ctx, yaml_path = cliente
    antes = yaml_path.read_text(encoding="utf-8")
    r = client.patch("/calibration/pressure/pres_chaqueta", json=_p(55.0, 10.0, 296.0, 337.0))
    assert r.status_code == 409 and r.json()["codigo"] == "CALIBRACION_REQUIERE_CONFIRMACION"
    assert yaml_path.read_text(encoding="utf-8") == antes


def test_endpoint_aplica_la_correccion_grande_confirmada_y_lo_audita(cliente):
    client, ctx, _ = cliente
    r = client.patch("/calibration/pressure/pres_chaqueta",
                     json={**_p(55.0, 10.0, 296.0, 337.0), "confirmar_fuera_de_rango": True})
    assert r.status_code == 200
    (llamada,) = [c for c in ctx.db.registrar_auditoria.call_args_list
                  if c.args[0] == "calibracion_cambio"]
    assert llamada.kwargs["detalle"]["plausibilidad"]["nivel"] == "aviso"
    assert llamada.kwargs["detalle"]["plausibilidad"]["confirmado"] is True


def test_endpoint_confirmar_no_salva_un_rechazo(cliente):
    client, _, _ = cliente
    r = client.patch("/calibration/temperature/temp_camara",
                     json={**_p(60.0, 80.0, 134.0, 134.0), "confirmar_fuera_de_rango": True})
    assert r.status_code == 422


# ── Revisión de seguridad de S3a ─────────────────────────────────────────────

@pytest.mark.parametrize("tipo, puntos", [
    ("temperature", _p(20.0, 35.0, 40.0, 25.0)),         # pendiente −0,5 (la lectura bajaría)
    ("temperature", _p(20.0, 5.0, 40.0, 55.0)),          # pendiente 2,5: +156 °C a 134 °C
    ("pressure", _p(100.0, 160.0, 150.0, 120.0)),        # pendiente invertida
    ("pressure", _p(50.0, 10.0, 100.0, 175.0)),          # pendiente 3,3
])
def test_pendiente_invertida_o_amplificada_se_rechaza(tipo, puntos):
    nivel, motivo = evaluar_calibracion(tipo, puntos)
    assert nivel == "rechazo" and motivo      # por separación, pendiente o ganancia


def test_la_extrapolacion_a_los_extremos_cuenta():
    # 3 °C en cada punto (aviso por puntos) pero con pendiente 1,25 el desvío
    # a 0 °C y a 150 °C supera la corrección máxima de cámara
    nivel, _ = evaluar_calibracion("temperature", _p(60.0, 57.0, 100.0, 107.0), "temp_camara")
    assert nivel == "rechazo"


def test_la_camara_es_mas_estricta_que_la_chaqueta():
    puntos = _p(100.0, 45.0, 300.0, 245.0)               # −55 kPa en todo el rango
    assert evaluar_calibracion("pressure", puntos, "pres_chaqueta")[0] == "aviso"
    assert evaluar_calibracion("pressure", puntos, "pres_camara")[0] == "rechazo"


def test_drenaje_tiene_su_propio_rango():
    assert evaluar_calibracion("temperature", _p(20.0, 20.0, 160.0, 160.0), "temp_drenaje")[0] == "rechazo"
    assert evaluar_calibracion("temperature", _p(20.0, 20.0, 160.0, 160.0), "temp_camara")[0] is None


@pytest.mark.parametrize("valor", [float("nan"), float("inf")])
def test_no_finito_se_rechaza(valor):
    assert evaluar_calibracion("temperature", _p(valor, 20.0, 100.0, 100.0))[0] == "rechazo"


def test_las_calibraciones_reales_del_yaml_no_se_rechazan():
    reales = [("pressure", "pres_camara", _p(20.0, 20.0, 307.0, 318.0)),
              ("pressure", "pres_camara", _p(12.0, 9.54, 322.0, 300.0)),
              ("pressure", "pres_chaqueta", _p(105.0, 75.0, 316.0, 365.0)),
              ("pressure", "pres_empaque_1", _p(55.0, 10.0, 296.0, 337.0)),
              ("temperature", "temp_camara", _p(60.0, 60.0, 134.5, 135.7)),
              ("temperature", "temp_camara", _p(20.0, 20.0, 131.3, 132.5))]
    for tipo, sensor, puntos in reales:
        assert evaluar_calibracion(tipo, puntos, sensor)[0] in (None, "aviso"), (sensor, puntos)


def test_el_endpoint_usa_los_limites_del_canal(cliente):
    client, _, _ = cliente
    r = client.patch("/calibration/pressure/pres_camara", json=_p(100.0, 45.0, 300.0, 245.0))
    assert r.status_code == 422
    r = client.patch("/calibration/pressure/pres_chaqueta", json=_p(100.0, 45.0, 300.0, 245.0))
    assert r.status_code == 409


# ── Acumulación y polinomio (revisión de S3a) ────────────────────────────────

from autoclave.core.managers.catalogo_parametros import evaluar_desviacion_acumulada  # noqa: E402


@pytest.mark.parametrize("tipo, sensor, ganancia, offset, esperado", [
    ("temperature", "temp_camara", 1.079022, -6.163755, None),     # calibration.yaml
    ("pressure", "pres_camara", 1.364056, -75.348611, None),
    ("pressure", "pres_chaqueta", 1.313705, -71.829031, None),
    ("temperature", "temp_camara", 1.0, 15.0, "aviso"),
    ("temperature", "temp_camara", 1.0, 30.0, "rechazo"),
    ("pressure", "pres_camara", 1.0, 100.0, "aviso"),
    ("pressure", "pres_camara", 1.0, 130.0, "rechazo"),
    ("temperature", "temp_camara", float("nan"), 0.0, "rechazo"),
])
def test_desviacion_acumulada(tipo, sensor, ganancia, offset, esperado):
    assert evaluar_desviacion_acumulada(tipo, ganancia, offset, sensor)[0] == esperado


def test_pasos_pequenos_repetidos_no_suman_una_deriva_ilimitada(cliente):
    """Cada paso corrige 2,9 °C (< aviso de 3 °C), pero la suma pide confirmación
    y luego se rechaza."""
    client, _, yaml_path = cliente
    niveles = []
    for _ in range(14):
        r = client.patch("/calibration/temperature/temp_camara",
                         json=_p(30.0, 32.9, 130.0, 132.9))
        niveles.append(r.status_code)
        if r.status_code != 200:
            break
    assert 409 in niveles and niveles[-1] == 409          # primero pide confirmar
    from autoclave.config import load_config
    offset = load_config(yaml_path).calibration.user.temperature[0].offset
    assert offset <= 12.0 + 3.0
    r = client.patch("/calibration/temperature/temp_camara",
                     json={**_p(30.0, 32.9, 130.0, 132.9), "confirmar_fuera_de_rango": True})
    assert r.status_code == 200
    # y la deriva acumulada tiene techo duro
    for _ in range(14):
        r = client.patch("/calibration/temperature/temp_camara",
                         json={**_p(30.0, 32.9, 130.0, 132.9), "confirmar_fuera_de_rango": True})
        if r.status_code != 200:
            break
    assert r.status_code == 422 and r.json()["codigo"] == "CALIBRACION_IMPLAUSIBLE"


def test_canal_con_polinomio_pide_confirmar(tmp_path):
    import textwrap
    from fastapi.testclient import TestClient
    yaml_path = tmp_path / "calibration.yaml"
    yaml_path.write_text(textwrap.dedent("""
        calibration:
          user:
            temperature:
              - poly: [0.0, 1.0, 0.0001]
            pressure:
              - gain: 1.0
                offset: 0.0
    """), encoding="utf-8")
    ctx = MagicMock()
    ctx.db.get_auditoria.return_value = []
    ctx.sin_base_de_datos = False
    srv, _ = cargar_servidor(ctx)
    fijar_en_backend("CALIBRATION_PATH", yaml_path)
    client = TestClient(srv.app, headers=cabecera(srv, "ingeniero"))
    r = client.patch("/calibration/temperature/temp_camara", json=_p(30.0, 30.0, 130.0, 131.0))
    assert r.status_code == 409 and "polinomio" in r.json()["detail"]

# tests/test_t12_c13_excursion_referencia.py
#
# Tanda 12, C-13: Referencia fuera de la banda [T_est - brecha_error_temperatura,
# T_est + rango_temperatura_ester] durante la exposición. Excursión confirmada
# tras 5 s continuos: el conteo se detiene; al volver, se reinicia desde cero;
# F0 no se reinicia; sin retorno en timeout_excursion_referencia -> CIC-14.
# Reloj monotonic simulado.

from types import SimpleNamespace

from autoclave.core.runtime import progreso_ciclo as pc
from autoclave.services.domain.logging import ticket_formatter as tf
from autoclave.state_machine.cycle_phases.base_fase import FaseResult
from tests.helpers import t12_e12_apoyo as ap

T_EST = 121.0          # banda de la Referencia: [120.9, 124.0]
DENTRO = 121.5


def _fase(monkeypatch, ref=DENTRO, **kw):
    kw.setdefault("tiempo_min", 1)                       # 60 s de exposición
    return ap.fase(monkeypatch, t_est=T_EST, sensores=ap.ASIG_REF,
                   temp=DENTRO, pres=ap.psat(DENTRO), refs={"temp_ref": ref}, **kw)


def _ticks(f, reloj, segundos, paso=0.5):
    resultados = []
    for _ in range(int(round(segundos / paso))):
        reloj.avanzar(paso)
        resultados.append(f.update())
    return resultados


def test_excursion_mayor_a_5_s_detiene_y_al_volver_reinicia_desde_cero(monkeypatch):
    f, estado, _, reloj = _fase(monkeypatch)
    f.update()                                            # t = 0, fin en 60
    _ticks(f, reloj, 20)                                  # t = 20
    estado.sensores_temp["temp_ref"] = 119.0              # sale de la banda
    f.update()                                            # t = 20 (inicio)
    _ticks(f, reloj, 5.0)                                 # t = 25: confirmada
    assert f.exposicion_detenida is True
    res = _ticks(f, reloj, 60)                            # t = 85: ya pasó el fin original
    assert FaseResult.COMPLETADO not in res and FaseResult.FALLO not in res
    estado.sensores_temp["temp_ref"] = DENTRO             # vuelve
    reloj.avanzar(0.5)
    assert f.update() == FaseResult.EN_CURSO              # t = 85.5
    assert f.exposicion_detenida is False
    assert f._timer_fin == reloj.t + 60                   # reinicio desde cero
    reloj.avanzar(59.9)
    assert f.update() == FaseResult.EN_CURSO
    reloj.avanzar(0.1)
    assert f.update() == FaseResult.COMPLETADO


def test_excursion_menor_a_5_s_no_detiene(monkeypatch):
    f, estado, _, reloj = _fase(monkeypatch)
    f.update()
    fin = f._timer_fin
    estado.sensores_temp["temp_ref"] = 119.0
    f.update()
    reloj.avanzar(4.9)
    f.update()
    assert f.exposicion_detenida is False
    estado.sensores_temp["temp_ref"] = DENTRO
    reloj.avanzar(0.1)
    f.update()
    assert f._timer_fin == fin                            # sin reinicio
    assert not [a for a in estado.avisos_ciclo if "excursion" in a["clave"]]
    reloj.t = fin
    assert f.update() == FaseResult.COMPLETADO


def test_no_termina_con_una_referencia_fuera_aun_sin_confirmar(monkeypatch):
    f, estado, _, reloj = _fase(monkeypatch)
    f.update()
    reloj.t = f._timer_fin - 1.0
    estado.sensores_temp["temp_ref"] = 119.0
    f.update()
    reloj.avanzar(1.0)                                    # fin vencido, excursión de 1 s
    assert f.update() == FaseResult.EN_CURSO


def test_f0_no_se_reinicia_ni_cambia_su_timeout(monkeypatch):
    f, estado, _, reloj = _fase(monkeypatch, f0_activo=True, f0_objetivo=12.0,
                                f0_acumulado_inicial=7.0)
    f.cap = SimpleNamespace(has_liquid_sensor=True)
    f.update()
    timeout = f._timer_timeout_max
    estado.sensores_temp["temp_ref"] = 119.0
    f.update()
    _ticks(f, reloj, 10)
    estado.sensores_temp["temp_ref"] = DENTRO
    reloj.avanzar(0.5)
    f.update()
    assert estado.f0_acumulado == 7.0
    assert f._timer_timeout_max == timeout


def test_reinicios_repetidos_con_f0_terminan_en_el_timeout_de_f0(monkeypatch):
    f, estado, _, reloj = _fase(monkeypatch, f0_activo=True, f0_objetivo=1.0,
                                f0_acumulado_inicial=5.0)
    f.cap = SimpleNamespace(has_liquid_sensor=True)
    f.update()                                            # timeout F0 en 120 s
    resultado = FaseResult.EN_CURSO
    while resultado == FaseResult.EN_CURSO and reloj.t < 1000.0 + 200:
        estado.sensores_temp["temp_ref"] = 119.0          # 30 s fuera, 20 s dentro
        for r in _ticks(f, reloj, 30):
            resultado = r
            if r != FaseResult.EN_CURSO:
                break
        if resultado != FaseResult.EN_CURSO:
            break
        estado.sensores_temp["temp_ref"] = DENTRO
        for r in _ticks(f, reloj, 20):
            resultado = r
            if r != FaseResult.EN_CURSO:
                break
    assert resultado == FaseResult.FALLO
    assert "TIMEOUT_F0" in estado.motivo_fallo


def test_sin_retorno_en_el_timeout_falla_con_cic14(monkeypatch):
    f, estado, set_do, reloj = _fase(monkeypatch, timeout_exc=5, tiempo_min=30)
    f.update()
    estado.sensores_temp["temp_ref"] = 119.0
    f.update()                                            # inicio de la excursión
    res = _ticks(f, reloj, 299.5, paso=0.5)
    assert FaseResult.FALLO not in res
    reloj.avanzar(0.5)                                    # 300 s
    assert f.update() == FaseResult.FALLO
    codigo, valores = f.alarma_fallo
    assert codigo == "CIC-14"
    assert valores == {"sensor": "Referencia", "minutos": "5"}
    set_do.vapor_camara_off.assert_called()
    # la excursión abierta queda en el ticket
    assert [a["clave"] for a in estado.avisos_ciclo] == ["ticket_ciclo.aviso_excursion"]


def test_timeout_por_defecto_5_min_y_recorte(monkeypatch):
    f, *_ = _fase(monkeypatch)
    assert f._timeout_excursion_min() == 5.0
    f, *_ = _fase(monkeypatch, timeout_exc=99)
    assert f._timeout_excursion_min() == 30.0
    f, *_ = _fase(monkeypatch, timeout_exc="x")
    assert f._timeout_excursion_min() == 5.0


def test_ticket_lista_sensor_duracion_y_minima(monkeypatch):
    f, estado, _, reloj = _fase(monkeypatch)
    f.update()
    estado.sensores_temp["temp_ref"] = 119.0
    f.update()
    _ticks(f, reloj, 10)
    estado.sensores_temp["temp_ref"] = 118.4
    _ticks(f, reloj, 20)                                  # 30 s fuera
    estado.sensores_temp["temp_ref"] = DENTRO
    f.update()
    assert estado.avisos_ciclo == [{"clave": "ticket_ciclo.aviso_excursion",
                                    "sensor": "Referencia", "duracion": 30, "temp_min": 118.4}]
    texto = tf.aviso_ticket(estado.avisos_ciclo[0], tf.Presentacion(idioma="es"))
    assert texto == "Excursión de Referencia: 30 s fuera de banda, mínima 118.4 C"
    texto_en = tf.aviso_ticket(estado.avisos_ciclo[0],
                               tf.Presentacion(idioma="en", temperatura="F"))
    assert texto_en == "Excursion of Referencia: 30 s out of band, minimum 245.1 F"


def test_ticket_salida_por_arriba_incluye_maxima(monkeypatch):
    f, estado, _, reloj = _fase(monkeypatch)
    f.update()
    estado.sensores_temp["temp_ref"] = 124.6
    f.update()
    _ticks(f, reloj, 8)
    estado.sensores_temp["temp_ref"] = DENTRO
    f.update()
    aviso = estado.avisos_ciclo[0]
    assert aviso["clave"] == "ticket_ciclo.aviso_excursion_alta"
    assert aviso["temp_max"] == 124.6 and aviso["temp_min"] == 124.6
    assert aviso["duracion"] == 8


def test_cic09_una_vez_por_sensor_y_sin_aviso_de_uniformidad(monkeypatch):
    f, estado, _, reloj = _fase(monkeypatch)
    f.update()
    for _ in range(2):
        estado.sensores_temp["temp_ref"] = 119.0
        f.update()
        _ticks(f, reloj, 6)
        estado.sensores_temp["temp_ref"] = DENTRO
        f.update()
    llamadas = ap.activaciones(f, "CIC-09")
    assert len(llamadas) == 1 and llamadas[0].kwargs["sensor"] == "Referencia"
    claves = [a["clave"] for a in estado.avisos_ciclo]
    assert "ticket_ciclo.aviso_uniformidad" not in claves     # reemplazado (C-13.5)
    assert claves.count("ticket_ciclo.aviso_excursion") == 2


def test_principal_fuera_de_banda_sigue_fallando(monkeypatch):
    f, estado, _, reloj = _fase(monkeypatch)
    f.update()
    ap.poner(estado, 120.5, ap.psat(120.5))               # < 121 - 0.1
    f.update()
    reloj.avanzar(5.0)
    assert f.update() == FaseResult.FALLO
    assert getattr(estado.motivo_fallo, "codigo", None) == "est_temp_baja"


def test_referencia_sin_lectura_no_detiene_ni_reinicia(monkeypatch):
    f, estado, _, reloj = _fase(monkeypatch)
    f.update()
    fin = f._timer_fin
    estado.sensores_temp["temp_ref"] = None
    _ticks(f, reloj, 30)
    assert f.exposicion_detenida is False and f._timer_fin == fin
    reloj.t = fin
    assert f.update() == FaseResult.COMPLETADO


def test_excursion_confirmada_que_pierde_lectura_sigue_su_timeout(monkeypatch):
    f, estado, _, reloj = _fase(monkeypatch, timeout_exc=1, tiempo_min=30)
    f.update()
    estado.sensores_temp["temp_ref"] = 119.0
    f.update()
    _ticks(f, reloj, 6)
    assert f.exposicion_detenida is True
    estado.sensores_temp["temp_ref"] = None
    res = _ticks(f, reloj, 54)                            # 60 s desde el inicio
    assert res[-1] == FaseResult.FALLO
    assert f.alarma_fallo[0] == "CIC-14"


# ── C-13.7: tiempo restante de la UI ─────────────────────────────────────────

def test_restante_de_exposicion_refleja_la_detencion_y_el_reinicio(monkeypatch):
    f, estado, _, reloj = _fase(monkeypatch)
    f.update()
    _ticks(f, reloj, 20)
    assert estado.exposicion_restante_s == 40.0
    estado.sensores_temp["temp_ref"] = 119.0
    f.update()
    _ticks(f, reloj, 10)                                  # confirmada, t = 30
    assert estado.exposicion_restante_s == 60.0          # volverá a empezar completo
    estado.sensores_temp["temp_ref"] = DENTRO
    f.update()
    _ticks(f, reloj, 15)
    assert estado.exposicion_restante_s == 45.0


def test_progreso_usa_el_restante_de_la_exposicion():
    aplicables = ["calentamiento", "esterilizacion", "descompresion"]
    filas = [{"fase": "CALENTAMIENTO", "inicio_s": 0.0, "fin_s": 100.0, "duracion_s": 100.0},
             {"fase": "ESTERILIZACION", "inicio_s": 100.0, "fin_s": None, "duracion_s": None}]
    referencias = {"calentamiento": 100.0, "esterilizacion": 60.0, "descompresion": 30.0}
    # sin dato de la fase: estimación por historial (60 - 50 + 30)
    sin = pc.armar_progreso(aplicables, filas, "ESTERILIZACION", 150.0, referencias)
    assert sin["restante_s"] == 40.0
    # con reinicio por excursión: 60 s de exposición completos + 30 de descompresión
    con = pc.armar_progreso(aplicables, filas, "ESTERILIZACION", 150.0, referencias,
                            restante_exposicion_s=60.0)
    assert con["restante_s"] == 90.0
    # sin historial de la esterilización pero con el dato de la fase
    sin_ref = pc.armar_progreso(aplicables, filas, "ESTERILIZACION", 150.0,
                                {"descompresion": 30.0}, restante_exposicion_s=12.0)
    assert sin_ref["restante_s"] == 42.0
    # en otra fase el dato se ignora (estimación por historial)
    filas_cal = [{"fase": "CALENTAMIENTO", "inicio_s": 0.0, "fin_s": None, "duracion_s": None}]
    otra = pc.armar_progreso(aplicables, filas_cal, "CALENTAMIENTO", 50.0, referencias,
                             restante_exposicion_s=5.0)
    assert otra["restante_s"] == 50.0 + 60.0 + 30.0

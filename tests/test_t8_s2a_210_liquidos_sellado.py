"""Tanda 8 / S2a / D8-2.10: carga líquida, modos 4/5, se pierde el Principal
durante el enfriamiento con contrapresión.

- NO se ventea de inmediato: la cámara queda SELLADA. DECISIÓN de S2a (la
  instrucción lo permite si no está claro en el código que la contrapresión se
  pueda mantener): espera sellada con TODAS las salidas del protocolo cerradas
  (vapor, descompresiones lenta/rápida/chaqueta, aire comprimido, agua de
  chaqueta, aire atmosférico). PREGUNTA PARA CRISTIAN en el informe.
- Mientras alguna sonda válida (Referencia del programa o drenaje) esté por
  encima de temp_max_apertura, sigue sellada; con todas las válidas en o por
  debajo (3 lecturas seguidas) se ventea por la lenta.
- Sin ninguna sonda válida: se espera sellado espera_sellado_sin_sonda_min
  (parámetro del equipo, 30 min, 10-240) y luego se ventea por la lenta.
- El ciclo termina en FALLO y "NO ABRIR" sigue según la cámara segura."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import autoclave.state_machine.cycle_phases.protocolo_fallo as modulo
from autoclave.state_machine.cycle_phases.protocolo_fallo import (
    _DEBOUNCE_LECTURAS, ProtocoloFallo)
from autoclave.state_machine.estado_seguro import ProtocoloEstadoSeguro

_ASIG = {"temp_camara": "principal", "temp_2_camara": "no_en_uso", "temp_ref": "referencia"}
_CFG = {"presion_admosferica": 101.3, "rango_presion_atm": 10.0, "temp_max_apertura": 80.0}

_CERRAR = ("descompresion_lenta_off", "descompresion_rapida_off",
           "descompresion_chaqueta_off", "aire_comprimido_camara_off",
           "agua_chaqueta_off", "aire_admosferico_camara_off",
           "vapor_camara_off", "vapor_chaqueta_off")
_ABRIR = ("descompresion_lenta_on", "descompresion_rapida_on",
          "descompresion_chaqueta_on", "aire_comprimido_camara_on",
          "agua_chaqueta_on", "aire_admosferico_camara_on",
          "vapor_camara_on", "vapor_chaqueta_on")


class _Config(dict):
    def get(self, k, d=None):
        return super().get(k, d)


@pytest.fixture
def reloj(monkeypatch):
    t = [1000.0]
    monkeypatch.setattr(modulo.time, "monotonic", lambda: t[0])
    return t


def _protocolo(modo=4, liquido=True, pres=220.0, temp=118.0, ref=118.0,
               drenaje=None, config=None):
    estado = SimpleNamespace(
        sensores_pres={"pres_camara": pres},
        sensores_temp={"temp_camara": temp, "temp_2_camara": None,
                       "temp_ref": ref, "temp_drenaje": drenaje})
    params = {("descompresion", "modo"): modo,
              ("globals", "tipo_carga"): "liquido" if liquido else "solido",
              ("descompresion", f"modo_{modo}", "temperatura_enfriamiento"): 80.0,
              ("descompresion", f"modo_{modo}", "presion_camara_enfriamiento"): 200,
              ("descompresion", f"modo_{modo}", "timeout"): 30}

    def get_param(*a, default=None):
        return params.get(a, params.get(a[:2], default))

    cycle = SimpleNamespace(sensores=dict(_ASIG), get_param=get_param)
    set_do = MagicMock()
    cfg = _Config(_CFG if config is None else config)
    return ProtocoloFallo(estado, set_do, cycle, cfg), estado, set_do


def _ninguna_abierta(set_do):
    for nombre in _ABRIR:
        getattr(set_do, nombre).assert_not_called()


def _todas_cerradas(set_do):
    for nombre in _CERRAR:
        getattr(set_do, nombre).assert_called()


def _perder_principal(prot, estado):
    estado.sensores_temp["temp_camara"] = None
    for _ in range(_DEBOUNCE_LECTURAS):
        prot.update()


# ── Protocolo ya en enfriamiento (otra causa) y luego se pierde el Principal ─

@pytest.mark.parametrize("modo", [4, 5])
def test_no_ventea_de_inmediato_y_queda_sellada(modo):
    prot, estado, set_do = _protocolo(modo)
    prot.ejecutar()
    prot.update()
    assert prot.sellado is False
    set_do.reset_mock()

    _perder_principal(prot, estado)

    assert prot.solo_lenta is True
    assert prot.sellado is True
    _ninguna_abierta(set_do)
    _todas_cerradas(set_do)
    set_do.reset_mock()
    for _ in range(10):
        prot.update()
    _ninguna_abierta(set_do)


def test_una_lectura_invalida_no_ventea_ni_sigue_inyectando_aire():
    # Antes de D8-2.10 una sola lectura inválida abría la lenta en el acto
    prot, estado, set_do = _protocolo(4)
    prot.ejecutar()
    prot.update()
    set_do.reset_mock()
    estado.sensores_temp["temp_camara"] = None
    prot.update()
    _ninguna_abierta(set_do)
    set_do.aire_comprimido_camara_off.assert_called()
    set_do.descompresion_lenta_off.assert_called()


def test_si_vuelve_antes_del_debounce_sigue_el_enfriamiento():
    prot, estado, set_do = _protocolo(4, pres=150.0)
    prot.ejecutar()
    estado.sensores_temp["temp_camara"] = None
    prot.update()
    estado.sensores_temp["temp_camara"] = 118.0
    set_do.reset_mock()
    prot.update()
    assert prot.sellado is False and prot.solo_lenta is False
    set_do.aire_comprimido_camara_on.assert_called()   # contrapresión de nuevo


def test_referencia_caliente_mantiene_el_sellado():
    prot, estado, set_do = _protocolo(4, ref=95.0)
    prot.ejecutar()
    _perder_principal(prot, estado)
    set_do.reset_mock()
    for _ in range(20):
        prot.update()
    assert prot.sellado is True
    _ninguna_abierta(set_do)


def test_todas_las_sondas_frias_tres_lecturas_ventea_por_la_lenta():
    prot, estado, set_do = _protocolo(4, ref=95.0, drenaje=60.0)
    prot.ejecutar()
    _perder_principal(prot, estado)
    estado.sensores_temp["temp_ref"] = 80.0           # en el límite: vale
    set_do.reset_mock()
    for _ in range(_DEBOUNCE_LECTURAS - 1):
        prot.update()
    assert prot.sellado is True
    set_do.descompresion_lenta_on.assert_not_called()
    prot.update()
    assert prot.sellado is False
    set_do.descompresion_lenta_on.assert_called()
    set_do.descompresion_rapida_on.assert_not_called()
    set_do.aire_comprimido_camara_on.assert_not_called()
    # sigue por la lenta (enclavado) aunque la Referencia vuelva a subir
    estado.sensores_temp["temp_ref"] = 100.0
    set_do.reset_mock()
    prot.update()
    assert prot.sellado is False
    set_do.descompresion_rapida_on.assert_not_called()


def test_una_lectura_caliente_reinicia_la_confirmacion():
    prot, estado, set_do = _protocolo(4, ref=90.0)
    prot.ejecutar()
    _perder_principal(prot, estado)
    estado.sensores_temp["temp_ref"] = 70.0
    prot.update(); prot.update()
    estado.sensores_temp["temp_ref"] = 90.0
    prot.update()
    estado.sensores_temp["temp_ref"] = 70.0
    prot.update(); prot.update()
    assert prot.sellado is True
    prot.update()
    assert prot.sellado is False


def test_drenaje_caliente_mantiene_el_sellado_aunque_la_referencia_este_fria():
    prot, estado, set_do = _protocolo(4, ref=60.0, drenaje=90.0)
    prot.ejecutar()
    _perder_principal(prot, estado)
    for _ in range(10):
        prot.update()
    assert prot.sellado is True


def test_drenaje_frio_sin_referencia_no_ventea_y_rige_la_espera(reloj):
    # DECISIÓN SIN CONFIRMAR de S2a: el agua del drenaje lo mantiene frío
    prot, estado, set_do = _protocolo(4, ref=None, drenaje=40.0)
    prot.ejecutar()
    _perder_principal(prot, estado)
    for _ in range(10):
        prot.update()
    assert prot.sellado is True
    reloj[0] += 30 * 60
    prot.update()
    assert prot.sellado is False and prot.motivo_venteo == "espera_sin_sonda"


def test_drenaje_caliente_sin_referencia_mantiene_el_sellado_pasada_la_espera(reloj):
    prot, estado, _ = _protocolo(4, ref=None, drenaje=95.0)
    prot.ejecutar()
    _perder_principal(prot, estado)
    reloj[0] += 240 * 60
    prot.update()
    assert prot.sellado is True


def test_usa_el_menor_entre_el_global_y_el_del_programa():
    prot, estado, _ = _protocolo(4, ref=75.0)
    params_base = prot.cycle.get_param
    prot.cycle.get_param = lambda *a, default=None: (
        70.0 if a == ("finalizacion", "temp_max_apertura") else params_base(*a, default=default))
    prot.ejecutar()
    _perder_principal(prot, estado)
    for _ in range(10):
        prot.update()
    assert prot.sellado is True                       # 75 > min(80, 70)


@pytest.mark.parametrize("invalida", [None, 0, float("nan")])
def test_sin_sonda_valida_espera_el_parametro_y_luego_ventea(reloj, invalida):
    cfg = dict(_CFG, espera_sellado_sin_sonda_min=45)
    prot, estado, set_do = _protocolo(4, ref=invalida, drenaje=invalida, config=cfg)
    prot.ejecutar()
    _perder_principal(prot, estado)
    assert prot.sellado is True
    reloj[0] += 45 * 60 - 1
    prot.update()
    assert prot.sellado is True
    set_do.descompresion_lenta_on.assert_not_called()
    reloj[0] += 1
    prot.update()
    assert prot.sellado is False
    set_do.descompresion_lenta_on.assert_called()


@pytest.mark.parametrize("valor,esperado_min", [(None, 30), ("x", 30), (True, 30),
                                                (1, 10), (999, 240), (60, 60)])
def test_espera_sin_sonda_por_defecto_y_recortada(valor, esperado_min):
    cfg = dict(_CFG)
    if valor is not None:
        cfg["espera_sellado_sin_sonda_min"] = valor
    prot, _, _ = _protocolo(4, config=cfg)
    assert prot._espera_sellado_sin_sonda_s() == esperado_min * 60


def test_si_vuelve_una_sonda_caliente_se_desarma_la_espera(reloj):
    prot, estado, set_do = _protocolo(4, ref=None)
    prot.ejecutar()
    _perder_principal(prot, estado)
    reloj[0] += 29 * 60
    prot.update()
    estado.sensores_temp["temp_ref"] = 110.0          # vuelve, caliente (3 lecturas)
    for _ in range(_DEBOUNCE_LECTURAS):
        prot.update()
    estado.sensores_temp["temp_ref"] = None           # se vuelve a perder
    reloj[0] += 2 * 60
    prot.update()
    assert prot.sellado is True                       # la espera empieza de nuevo
    reloj[0] += 30 * 60
    prot.update()
    assert prot.sellado is False


def test_bloqueado_motivo_mientras_esta_sellada():
    prot, estado, _ = _protocolo(4)
    prot.ejecutar()
    _perder_principal(prot, estado)
    assert "sellada" in prot.bloqueado_motivo


def test_reset_quita_el_sellado():
    prot, estado, _ = _protocolo(4)
    prot.ejecutar()
    _perder_principal(prot, estado)
    prot.reset()
    assert prot.sellado is False


# ── Fuera del alcance de D8-2.10: sin cambios ─────────────────────────────

def test_carga_solida_modo_4_sigue_venteando_por_la_lenta():
    prot, estado, set_do = _protocolo(4, liquido=False)
    prot.ejecutar()
    prot.update()
    set_do.reset_mock()
    _perder_principal(prot, estado)
    assert prot.sellado is False
    set_do.descompresion_lenta_on.assert_called()


def test_liquido_no_presurizado_al_disparo_sigue_por_la_lenta():
    prot, estado, set_do = _protocolo(4, pres=101.3)
    prot.ejecutar()
    _perder_principal(prot, estado)
    assert prot.sellado is False


def test_liquido_modo_2_sigue_por_la_lenta():
    prot, estado, set_do = _protocolo(2)
    prot.ejecutar()
    _perder_principal(prot, estado)
    assert prot.sellado is False
    set_do.descompresion_lenta_on.assert_called()


# ── Disparo desde CicloState durante la DESCOMPRESION (enfriamiento) ───────

@pytest.mark.parametrize("modo", [4, 5])
def test_ejecutar_en_enfriamiento_de_la_fase_sella_sin_abrir(modo):
    prot, estado, set_do = _protocolo(modo, temp=None)
    prot.ejecutar(solo_lenta=True, en_enfriamiento_contrapresion=True)
    assert prot.solo_lenta is True and prot.sellado is True
    _ninguna_abierta(set_do)
    set_do.reset_all_outputs.assert_called()
    for _ in range(5):
        prot.update()
    _ninguna_abierta(set_do)


def test_ejecutar_en_enfriamiento_con_carga_solida_no_sella():
    prot, _, set_do = _protocolo(4, liquido=False, temp=None)
    prot.ejecutar(solo_lenta=True, en_enfriamiento_contrapresion=True)
    assert prot.sellado is False
    set_do.descompresion_lenta_on.assert_called()


def _ciclo_en_descompresion(modo, liquido=True, sub_etapa="enfriamiento"):
    from tests.test_t3_sensores_ciclo import _ASIG_REF, _ciclo
    from autoclave.state_machine.cycle_phases.descompresion import DescompresionFase
    ciclo, estado, _ = _ciclo(_ASIG_REF, {"temp_camara": None, "temp_ref": 120.0})
    fase = DescompresionFase.__new__(DescompresionFase)
    fase._modo = modo
    fase._sub_etapa = sub_etapa
    ciclo._fases = [fase]
    ciclo._fase_idx = 0
    return ciclo, estado


@pytest.mark.parametrize("modo", [4, 5])
def test_cicloestado_pasa_el_enfriamiento_de_la_fase_al_protocolo(modo):
    ciclo, estado = _ciclo_en_descompresion(modo)
    ciclo.run()
    assert estado.fase_ciclo == "SENSOR_AUSENTE"
    ciclo._protocolo.ejecutar.assert_called_once_with(
        solo_lenta=True, en_enfriamiento_contrapresion=True)


@pytest.mark.parametrize("modo,sub", [(4, "descompresion"), (2, None), (3, "lenta")])
def test_cicloestado_fuera_del_enfriamiento_no_cambia(modo, sub):
    ciclo, estado = _ciclo_en_descompresion(modo, sub_etapa=sub)
    ciclo.run()
    ciclo._protocolo.ejecutar.assert_called_once_with(solo_lenta=True)


# ── Estado seguro: sale de FALLA (D8-2.6) pero NO ABRIR sigue ─────────────

def test_estado_seguro_sellado_permite_salir_de_falla_y_no_es_segura():
    prot, estado, set_do = _protocolo(4, ref=95.0)
    prot.ejecutar()
    _perder_principal(prot, estado)
    estado.get_flag = lambda f: False
    eventos = []
    es = ProtocoloEstadoSeguro(estado, _Config(_CFG),
                               al_evento=lambda e, d: eventos.append((e, d)))
    es.iniciar(prot)
    for _ in range(5):
        es.update()
    assert es.activo is True                          # la cámara no es segura
    assert es.permite_salir_de_falla is True
    estado.sensores_temp["temp_ref"] = 70.0
    for _ in range(_DEBOUNCE_LECTURAS):
        es.update()
    assert prot.sellado is False
    assert any(e == "estado_seguro_venteo_tras_sellado" for e, _ in eventos)


# ── Revisión S2a ───────────────────────────────────────────────────────────

def test_sonda_intermitente_no_reinicia_la_espera_para_siempre(reloj):
    # TMG-03: válida y caliente 1 de cada 3 lecturas
    prot, estado, _ = _protocolo(4, ref=None)
    prot.ejecutar()
    _perder_principal(prot, estado)
    for i in range(30 * 60 * 2 + 10):                 # 30 min a 0,5 s
        estado.sensores_temp["temp_ref"] = 110.0 if i % 3 == 0 else None
        prot.update()
        reloj[0] += 0.5
        if not prot.sellado:
            break
    assert prot.sellado is False and prot.motivo_venteo == "espera_sin_sonda"


def test_principal_que_vuelve_caliente_veta_el_venteo():
    # SAF-02: vuelve a leer caliente; la Referencia fría no basta
    prot, estado, _ = _protocolo(4, ref=70.0)
    prot.ejecutar()
    _perder_principal(prot, estado)
    estado.sensores_temp["temp_camara"] = 110.0
    for _ in range(10):
        prot.update()
    assert prot.sellado is True and prot.solo_lenta is True


@pytest.mark.parametrize("pres,abre", [(279.0, False), (281.0, True)])
def test_sobrepresion_sellada_alivia_por_la_lenta(pres, abre):
    # SAF-01: tope = max(200, P_sat(121)) + 30 con los parámetros de la prueba
    from autoclave.core.runtime.steam import p_saturacion_kpa
    prot, estado, set_do = _protocolo(4, ref=110.0)
    tope = max(200.0, p_saturacion_kpa(121.0)) + 30.0
    prot.ejecutar()
    _perder_principal(prot, estado)
    estado.sensores_pres["pres_camara"] = tope + (pres - 280.0)
    set_do.reset_mock()
    for _ in range(_DEBOUNCE_LECTURAS - 1):
        prot.update()
    set_do.descompresion_lenta_on.assert_not_called()
    prot.update()
    assert set_do.descompresion_lenta_on.called is abre
    assert prot.sellado is True                       # sigue sellada por temperatura
    estado.sensores_pres["pres_camara"] = tope - 5
    set_do.reset_mock()
    prot.update()
    set_do.descompresion_lenta_on.assert_not_called()
    set_do.descompresion_lenta_off.assert_called()


def test_sin_presion_sellada_no_alivia():
    prot, estado, set_do = _protocolo(4, ref=110.0)
    prot.ejecutar()
    _perder_principal(prot, estado)
    estado.sensores_pres["pres_camara"] = None
    set_do.reset_mock()
    for _ in range(10):
        prot.update()
    set_do.descompresion_lenta_on.assert_not_called()


def test_cic10_vuelve_si_el_reinicio_la_resolvio():
    # SAF-03: al salir de FALLA se resuelven todas; con la cámara sellada
    # CIC-10 tiene que volver a verse
    from autoclave.state_machine.alarms.alarm_manager import AlarmManager
    from autoclave.state_machine.alarms.catalogo import CIC_10
    prot, estado, _ = _protocolo(4, ref=110.0)
    prot.ejecutar()
    _perder_principal(prot, estado)
    estado.get_flag = lambda f: False
    am = AlarmManager()
    es = ProtocoloEstadoSeguro(estado, _Config(_CFG), alarm_manager=am)
    es.iniciar(prot)
    es.update()
    assert CIC_10 in [i.codigo for i in am.activas()]
    for i in list(am.activas()):
        am.resolver(i.codigo)
    es.update()
    assert CIC_10 in [i.codigo for i in am.activas()]

"""S9 (tanda 9, D9-1), rehecho en el hotfix ES (6-nov-2026): celdas del
arranque con la cámara no segura, con la planta simulada de T11/E1 en los 4
programas de fábrica y el ControlLoop REAL (máquina de estados, PREPARACION,
alarmas y SetOutput reales; el enlace es un doble con tramas vigentes).

Desde el hotfix ES ya no hay protocolo automático de estado seguro: con la
cámara no segura al arrancar, PREPARACION la nivela (sobrepresión: venteo,
con carga líquida por la lenta; vacío: aire atmosférico) y "NO ABRIR" y el
bloqueo de inicio siguen mientras no sea segura.

Celdas por programa (el programa es el del "ciclo interrumpido"):
- arranque_presurizado: cámara caliente y a presión: PREPARACION ventea
  hasta la banda atmosférica (líquidos: nunca la rápida).
- arranque_vacio: cámara en vacío: aire atmosférico, nunca la lenta.
- arranque_sin_presion: transductor de cámara sin lectura: ninguna válvula
  de cámara, SEN-06 sin CIC-10, modo prueba y cambio de programa
  permitidos, inicio de ciclo bloqueado.
- paro_real_en_arranque: paro real pulsado y liberado: confirmación; nada
  se mueve hasta confirmar; al confirmar, PREPARACION.
- modo_prueba_en_arranque: ESG-02 con la cámara presurizada.
- arranque_vacio_con_fuga (revisión SAF-03): con el aire abierto la
  presión sube sobre atm + brecha: el aire se cierra en el mismo tick.

En TODAS las celdas, cualquier tick con el aire atmosférico abierto y la
presión publicada sobre atm + brecha cuenta como falla.

Con S9_ESCRIBIR_INFORME=1 escribe docs/informes/tanda9/S9_ensayo_tabla.md."""

from tests.helpers.arranque_doble import evento_liberado  # H3 (tanda 26)
import os
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autoclave.core.managers.config_manager import ConfigManager
from autoclave.core.runtime import camara_segura
from autoclave.core.runtime import presion_sin_lectura as psl
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.devices.io.set_io import SetOutput
from autoclave.installation.equipment import EquipmentClass, get_capabilities
from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.alarms.instancia import EstadoInstancia
from autoclave.state_machine.machine.enum_global import GlobalState
from tests import test_t11_programas_integracion as t11
from tests.test_e1_ensayo_simulador import PROGRAMAS, programas  # noqa: F401
from tests.test_t11_programas_integracion import DT, _Planta, _ModuloEs, psat

RESULTADOS: dict[tuple[int, str], dict] = {}
PASOS_PLANTA = 4                     # pasos de planta (DT) por tick del lazo
TICK_S = DT * PASOS_PLANTA
VALVULAS_PROHIBIDAS_LIQUIDO = ("descompresion_rapida", "descompresion_chaqueta",
                               "aire_comprimido_camara", "vapor_camara")
DE_PROCESO = ("descompresion_lenta", "descompresion_rapida", "descompresion_chaqueta",
              "aire_admosferico_camara", "aire_comprimido_camara", "vapor_camara",
              "vapor_chaqueta", "agua_chaqueta", "vacio_camara", "bomba_vacio")


def _equipo(programa, monkeypatch, programas_fabrica):
    from autoclave.services.domain.loop.control_loop import ControlLoop
    reloj = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: reloj[0])
    monkeypatch.setattr(psl, "_ai_habilitadas", lambda: ("pres_camara", "pres_chaqueta"))
    estado = EstadoAutoclave()
    for di in estado.sensores_di:
        estado.sensores_di[di] = 1
    estado.sensores_di["agua_camara"] = 0
    modulo_es = _ModuloEs(estado)
    config = ConfigManager()
    config.load_config()
    t11.P_ATM = float(config.get("presion_admosferica") or 101.3)
    planta = _Planta(modulo_es)
    alarmas = AlarmManager()
    set_do = SetOutput(modulo_es, estado, profile=None)
    cm = MagicMock()
    seleccionado = programas_fabrica[1]          # el seleccionado al arrancar
    cm.get_selected_cycle.return_value = seleccionado
    link = MagicMock()
    link.is_connected.return_value = True
    link.edad_ultima_di.return_value = 0.1
    link.edad_ultima_ai.return_value = 0.1
    link.expansor_fuera_de_linea.return_value = False
    units = MagicMock()
    units.get_all.return_value = {}
    loop = ControlLoop(arranque_liberado=evento_liberado(), units=units, door_service=MagicMock(), doors=[], estado=estado,
                       link=link, set_do=set_do, alarm_manager=alarmas, cycle_manager=cm,
                       config_manager=config, cap=get_capabilities(EquipmentClass.PISO_LAB))
    estado.set_machine_state(GlobalState.PREPARACION)
    return dict(reloj=reloj, estado=estado, modulo_es=modulo_es, config=config, planta=planta,
                alarmas=alarmas, loop=loop, programa=programa, publicar=planta.publicar,
                link=link)


def _caliente_a_presion(planta):
    planta.t = planta.t_sonda = 134.0
    planta.p_v = psat(134.0)
    planta.p_aire = 5.0


def _en_vacio(planta):
    planta.t = planta.t_sonda = 30.0
    planta.p_v = psat(30.0)
    planta.p_aire = 12.0


def _tick(a):
    a["publicar"](a["estado"])
    a["p_publicada"] = a["planta"].p          # la que decidió este tick
    a["loop"]._tick()
    for _ in range(PASOS_PLANTA):
        a["planta"].paso()
    a["reloj"][0] += TICK_S


def _activas(a):
    return sorted({i.codigo for i in a["alarmas"].activas() if i.estado is EstadoInstancia.ACTIVA})


def _arrancar(a):
    a["loop"].recuperar_ciclo_interrumpido(a["programa"].copia())


def _seguir(a, limite_s=2 * 3600, cada=None):
    """Hasta que la presión de cámara queda en la banda atmosférica 3 ticks
    seguidos (o el límite). Devuelve lo visto."""
    visto = {"confirmacion": False, "causas": set(), "abiertas": set(), "lenta_en_vacio": False,
             "listo": False, "t0": a["reloj"][0], "aire_con_presion": 0, "activo": False}
    es = a["loop"].estado_seguro
    atm, rango = t11.P_ATM, float(a["config"].get("rango_presion_atm"))
    seguidos = 0
    for i in range(int(limite_s / TICK_S)):
        _tick(a)
        if cada is not None:
            cada(i)
        visto["confirmacion"] |= es.requiere_confirmacion
        visto["activo"] |= es.activo
        if es.causa:
            visto["causas"].add(es.causa)
        visto["abiertas"] |= {k for k in DE_PROCESO if a["modulo_es"].on(k)}
        if a["modulo_es"].on("descompresion_lenta") and a["p_publicada"] < atm - rango:
            visto["lenta_en_vacio"] = True
        # SAF-03 (revisión): por tick
        if a["modulo_es"].on("aire_admosferico_camara") and a["p_publicada"] > atm + rango:
            visto["aire_con_presion"] += 1
        # con la presión fuera de la banda la cámara no es segura: nunca listo
        if abs(a["p_publicada"] - atm) > rango:
            visto["listo"] |= bool(a["estado"].get_flag("LISTO_PARA_CICLO"))
        segura, _ = camara_segura.evaluar_presion(a["estado"], a["config"])
        seguidos = seguidos + 1 if segura else 0
        if i > 2 and seguidos >= 3 and a["loop"]._recuperacion_pendiente is None:
            break
    visto["minutos"] = round((a["reloj"][0] - visto["t0"]) / 60, 1)
    visto["presion_nivelada"] = seguidos >= 3
    visto["T"], visto["P"] = round(a["planta"].t_sonda, 1), round(a["planta"].p, 1)
    return visto


def _resumen(visto, **extra):
    return {"confirmacion_pedida": visto["confirmacion"], "causas": sorted(visto["causas"]),
            "salidas_abiertas": sorted(visto["abiertas"]) or ["ninguna"],
            "lenta_en_vacio": visto["lenta_en_vacio"],
            "ticks_aire_abierto_con_presion": visto["aire_con_presion"],
            "presion_nivelada": visto["presion_nivelada"], "protocolo_activo": visto["activo"],
            "listo_con_camara_no_segura": visto["listo"], "min": visto["minutos"],
            "T_final": visto["T"], "P_final": visto["P"], **extra}


# ── celdas ─────────────────────────────────────────────────────────────────

def _arranque_presurizado(a, **_):
    _caliente_a_presion(a["planta"])
    _arrancar(a)
    return _resumen(_seguir(a))


def _arranque_vacio(a, **_):
    _en_vacio(a["planta"])
    _arrancar(a)
    return _resumen(_seguir(a, limite_s=1800))


def _arranque_sin_presion(a, programas_fabrica=None, **_):
    original = a["planta"].publicar

    def publicar(estado):
        original(estado)
        estado.sensores_pres["pres_camara"] = None
    a["publicar"] = publicar
    _arrancar(a)
    visto = _seguir(a, limite_s=60)
    loop = a["loop"]
    activas = _activas(a)
    ok_prueba, motivo_prueba = loop.enter_test_mode()
    _tick(a)
    loop.exit_test_mode()
    otro = programas_fabrica[2]
    ok_programa, motivo_programa = loop.set_active_cycle(otro)
    a["estado"].set_flag("START_CICLO", True)
    for _ in range(5):
        _tick(a)
    return _resumen(visto, alarmas=activas,
                    modo_prueba_permitido=ok_prueba, motivo_prueba=motivo_prueba or "—",
                    cambio_programa_permitido=ok_programa, motivo_programa=motivo_programa or "—",
                    inicio_bloqueado=a["estado"].get_machine_state() != GlobalState.CICLO)


def _paro_real_en_arranque(a, **_):
    _caliente_a_presion(a["planta"])
    _arrancar(a)
    loop = a["loop"]
    for _ in range(10):
        _tick(a)
    a["estado"].sensores_di["paro_emergencia"] = 0          # paro pulsado (NC abierto)
    for _ in range(5):
        _tick(a)
    a["estado"].sensores_di["paro_emergencia"] = 1          # liberado
    for _ in range(3):
        _tick(a)
    pide = loop.estado_seguro.requiere_confirmacion
    causa = loop.estado_seguro.causa
    movidas = set()
    for _ in range(int(60 / TICK_S)):                      # sin confirmar nada se mueve
        _tick(a)
        movidas |= {k for k in DE_PROCESO if a["modulo_es"].on(k)}
    confirmado = loop.confirmar_estado_seguro()
    estado_tras_confirmar = a["estado"].get_machine_state()
    visto = _seguir(a)
    return _resumen(visto, confirmacion_tras_paro=pide, causa_tras_paro=causa,
                    salidas_sin_confirmar=sorted(movidas) or ["ninguna"], confirmado=confirmado,
                    estado_tras_confirmar=estado_tras_confirmar)


def _modo_prueba_en_arranque(a, **_):
    from autoclave.core.runtime import salidas_prueba_seguridad as sps
    _caliente_a_presion(a["planta"])
    _arrancar(a)
    loop = a["loop"]
    for _ in range(10):
        _tick(a)
    ok, motivo = loop.enter_test_mode()
    # Tanda 17 (ESG-02, decisión de Cristian; corrección R3 V17-s3-05): la
    # regla se evalúa con la presión vigente, como dentro del tick (el reloj
    # simulado ya avanzó tras el último tick y la presión quedaría vencida)
    loop._estado_publicado_mono = time.monotonic()
    bloqueadas = loop.salidas_prueba_bloqueadas()
    # una orden que se hubiera colado: el lazo la apaga en el tick siguiente
    for k in ("abrir_puerta_1", "desbloqueo_puerta_1", "vapor_camara", "descompresion_rapida"):
        a["modulo_es"].set_output(EstadoAutoclave.map_do[k] + 1, True)
    _tick(a)
    encendidas = sorted(k for k in (*sps.SALIDAS_PUERTA, *sps.SALIDAS_VAPOR)
                        if a["modulo_es"].on(k))
    loop.exit_test_mode()
    visto = _seguir(a)
    return _resumen(visto, modo_prueba_permitido=ok, motivo_prueba=motivo or "—",
                    bloqueadas_en_prueba=sorted(bloqueadas),
                    encendidas_tras_un_tick=encendidas or ["ninguna"])


def _arranque_vacio_con_fuga(a, **_):
    _en_vacio(a["planta"])
    _arrancar(a)
    fuga = {"desde": None, "ticks": 0}

    def cada(_i):
        # cuando el aire ya está abierto, una fuga sube la presión ~60 kPa
        # sobre la atmosférica en 6 ticks
        if fuga["desde"] is None and a["modulo_es"].on("aire_admosferico_camara"):
            fuga["desde"] = _i
        if fuga["desde"] is not None and fuga["ticks"] < 6:
            a["planta"].p_aire += 10.0 + max(0.0, t11.P_ATM - a["planta"].p)
            fuga["ticks"] += 1
    visto = _seguir(a, cada=cada)
    return _resumen(visto, fuga_aplicada=fuga["ticks"] == 6)


_CELDAS = {"arranque_presurizado": _arranque_presurizado, "arranque_vacio": _arranque_vacio,
           "arranque_sin_presion": _arranque_sin_presion,
           "paro_real_en_arranque": _paro_real_en_arranque,
           "modo_prueba_en_arranque": _modo_prueba_en_arranque,
           "arranque_vacio_con_fuga": _arranque_vacio_con_fuga}


@pytest.mark.parametrize("numero", sorted(PROGRAMAS))
@pytest.mark.parametrize("celda", list(_CELDAS))
def test_ensayo_s9(programas, monkeypatch, numero, celda):  # noqa: F811
    a = _equipo(programas[numero], monkeypatch, programas)
    r = _CELDAS[celda](a, programas_fabrica=programas)
    RESULTADOS[(numero, celda)] = r
    liquido = programas[numero].get_param("globals", "tipo_carga", default=None) in (None, "liquido")
    # Hotfix ES: nunca hay protocolo automático
    assert r["protocolo_activo"] is False, r
    if celda != "paro_real_en_arranque":
        assert r["confirmacion_pedida"] is False, r
        assert "paro_liberado" not in r["causas"], r
    assert r["listo_con_camara_no_segura"] is False, r
    assert r["ticks_aire_abierto_con_presion"] == 0, r        # SAF-03, por tick
    if celda in ("arranque_presurizado", "paro_real_en_arranque", "modo_prueba_en_arranque"):
        venteo = "descompresion_lenta" if liquido else "descompresion_rapida"
        assert venteo in r["salidas_abiertas"], r
        if liquido:
            assert not set(r["salidas_abiertas"]) & set(VALVULAS_PROHIBIDAS_LIQUIDO), r
        assert r["lenta_en_vacio"] is False, r
        assert r["presion_nivelada"] is True, r
    if celda == "arranque_vacio":
        assert "aire_admosferico_camara" in r["salidas_abiertas"], r
        assert r["lenta_en_vacio"] is False, r
        assert r["presion_nivelada"] is True, r
    if celda == "arranque_sin_presion":
        assert not set(r["salidas_abiertas"]) & {"descompresion_lenta", "descompresion_rapida",
                                                 "aire_admosferico_camara", "vapor_camara"}, r
        assert "SEN-06" in r["alarmas"] and "CIC-10" not in r["alarmas"], r
        assert r["modo_prueba_permitido"] and r["cambio_programa_permitido"], r
        assert r["inicio_bloqueado"], r
        assert r["causas"] == [], r
    if celda == "paro_real_en_arranque":
        assert r["confirmacion_tras_paro"] is True and r["causa_tras_paro"] == "paro_liberado", r
        assert r["salidas_sin_confirmar"] == ["ninguna"], r
        assert r["confirmado"] is True, r
        assert r["estado_tras_confirmar"] == GlobalState.PREPARACION, r
    if celda == "modo_prueba_en_arranque":
        assert r["modo_prueba_permitido"] is True, r
        # ESG-02: con lectura vigente de presión solo quedan apertura y
        # desbloqueo de puertas con la cámara presurizada
        assert set(r["bloqueadas_en_prueba"]) == {
            "abrir_puerta_1", "abrir_puerta_2", "desbloqueo_puerta_1", "desbloqueo_puerta_2"}, r
        assert r["encendidas_tras_un_tick"] == ["descompresion_rapida", "vapor_camara"], r
    if celda == "arranque_vacio_con_fuga":
        assert r["fuga_aplicada"] is True, r
        assert "aire_admosferico_camara" in r["salidas_abiertas"], r


def test_escribir_informe_s9():
    if os.environ.get("S9_ESCRIBIR_INFORME") != "1":
        pytest.skip("solo con S9_ESCRIBIR_INFORME=1")
    filas = ["# S9 — tabla de ensayo con la planta simulada (tanda 9, D9-1)", "",
             "Generada por `tests/test_s9_planta_simulada.py` con `S9_ESCRIBIR_INFORME=1`. "
             "Planta simulada de T11/E1 (valores provisionales), ControlLoop real.", "",
             "| Programa | Celda | Resultado |", "|---|---|---|"]
    for numero in sorted(PROGRAMAS):
        for celda in _CELDAS:
            r = RESULTADOS.get((numero, celda))
            if r is not None:
                datos = ", ".join(f"{k}={v}" for k, v in r.items())
                filas.append(f"| {numero} {PROGRAMAS[numero]} | {celda} | {datos} |")
    destino = Path("docs/informes/tanda9/S9_ensayo_tabla.md")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(filas) + "\n", encoding="utf-8")

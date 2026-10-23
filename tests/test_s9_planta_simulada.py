"""S9 (tanda 9, D9-1): celdas de transición del arranque con la cámara no
segura, repetidas con la planta simulada de T11/E1 en los 4 programas de
fábrica, con el ControlLoop REAL (máquina de estados, estado seguro,
PREPARACION, alarmas y SetOutput reales; el enlace es un doble que informa
conexión y tramas vigentes).

Celdas por programa (el programa es el del "ciclo interrumpido"):
- arranque_presurizado: corte en esterilización, cámara caliente y a presión.
  Sin confirmación, solo la lenta (nunca la rápida, la chaqueta ni el aire),
  hasta la cámara segura.
- arranque_vacio: corte en vacío. Sin confirmación, aire atmosférico y nunca
  la lenta mientras hay vacío.
- arranque_sin_presion: transductor de presión de cámara sin lectura (equipo
  de pruebas sin sensores). Sin confirmación, ninguna válvula, CIC-10 + SEN-06,
  modo prueba y cambio de programa permitidos, inicio de ciclo bloqueado.
- paro_real_en_arranque: paro real pulsado y liberado durante el protocolo:
  sí exige confirmación; nada se mueve hasta confirmar.
- cambio_programa_en_protocolo: se elige otro programa con el protocolo en
  marcha; el programa del protocolo sigue contando para la seguridad.
- modo_prueba_en_protocolo (revisión ★ SAF-01): arranque presurizado, el
  técnico entra a modo prueba: apertura/desbloqueo de puertas, rápida,
  chaqueta y vapor bloqueados y forzados a cero por el lazo; al salir el
  protocolo sigue hasta la cámara segura.
- arranque_vacio_con_fuga (revisión ★ SAF-03): arranque en vacío (aire
  atmosférico abierto) y después la presión sube sobre atm + brecha: el aire
  se cierra en el mismo tick.

En TODAS las celdas, cualquier tick con el aire atmosférico abierto y la
presión publicada sobre atm + brecha cuenta como falla (revisión ★ SAF-03:
por tick, no la unión de la corrida).

Con S9_ESCRIBIR_INFORME=1 escribe docs/informes/tanda9/S9_ensayo_tabla.md."""

import os
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autoclave.core.managers.config_manager import ConfigManager
from autoclave.core.runtime import presion_sin_lectura as psl
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.devices.io.set_io import SetOutput
from autoclave.installation.equipment import EquipmentClass, get_capabilities
from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.alarms.instancia import EstadoInstancia
from autoclave.state_machine.machine.enum_global import GlobalState
from tests import test_t11_programas_integracion as t11
from tests.test_e1_ensayo_simulador import PROGRAMAS, programas  # noqa: F401
from tests.test_t11_programas_integracion import DT, _Planta, _Tarjeta, psat

RESULTADOS: dict[tuple[int, str], dict] = {}
PASOS_PLANTA = 4                     # pasos de planta (DT) por tick del lazo
TICK_S = DT * PASOS_PLANTA
VALVULAS_PROHIBIDAS_LENTA = ("descompresion_rapida", "descompresion_chaqueta",
                             "aire_comprimido_camara", "vapor_camara", "vapor_chaqueta")
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
    tarjeta = _Tarjeta(estado)
    config = ConfigManager()
    config.load_config()
    t11.P_ATM = float(config.get("presion_admosferica") or 101.3)
    planta = _Planta(tarjeta)
    alarmas = AlarmManager()
    set_do = SetOutput(tarjeta, estado, profile=None)
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
    loop = ControlLoop(units=units, door_service=MagicMock(), doors=[], estado=estado,
                       link=link, set_do=set_do, alarm_manager=alarmas, cycle_manager=cm,
                       config_manager=config, cap=get_capabilities(EquipmentClass.PISO_LAB))
    estado.set_machine_state(GlobalState.PREPARACION)
    return dict(reloj=reloj, estado=estado, tarjeta=tarjeta, config=config, planta=planta,
                alarmas=alarmas, loop=loop, programa=programa, publicar=planta.publicar)


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


def _seguir(a, limite_s=4 * 3600, cada=None):
    """Hasta que termina el estado seguro (o el límite). Devuelve lo visto."""
    visto = {"confirmacion": False, "causas": set(), "abiertas": set(), "lenta_en_vacio": False,
             "listo": False, "t0": a["reloj"][0], "aire_con_presion": 0}
    es = a["loop"].estado_seguro
    atm, rango = t11.P_ATM, float(a["config"].get("rango_presion_atm"))
    for i in range(int(limite_s / TICK_S)):
        _tick(a)
        if cada is not None:
            cada(i)
        visto["confirmacion"] |= es.requiere_confirmacion
        if es.causa:
            visto["causas"].add(es.causa)
        if es.activo:
            # salidas mientras el protocolo manda (al terminar, PREPARACION
            # retoma su control normal en el mismo tick)
            visto["abiertas"] |= {k for k in DE_PROCESO if a["tarjeta"].on(k)}
            if a["tarjeta"].on("descompresion_lenta") and a["p_publicada"] < atm - rango:
                visto["lenta_en_vacio"] = True
        # SAF-03 (revisión ★): por tick, con o sin protocolo activo
        if a["tarjeta"].on("aire_admosferico_camara") and a["p_publicada"] > atm + rango:
            visto["aire_con_presion"] += 1
            visto["listo"] |= bool(a["estado"].get_flag("LISTO_PARA_CICLO"))
        if i > 2 and not es.activo and a["loop"]._recuperacion_pendiente is None:
            break
    visto["minutos"] = round((a["reloj"][0] - visto["t0"]) / 60, 1)
    visto["estado_seguro_alcanzado"] = not es.activo
    visto["T"], visto["P"] = round(a["planta"].t_sonda, 1), round(a["planta"].p, 1)
    return visto


def _resumen(visto, **extra):
    return {"confirmacion_pedida": visto["confirmacion"], "causas": sorted(visto["causas"]),
            "salidas_abiertas": sorted(visto["abiertas"]) or ["ninguna"],
            "lenta_en_vacio": visto["lenta_en_vacio"],
            "ticks_aire_abierto_con_presion": visto["aire_con_presion"],
            "estado_seguro_alcanzado": visto["estado_seguro_alcanzado"],
            "listo_durante_el_protocolo": visto["listo"], "min": visto["minutos"],
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
    return _resumen(visto, alarmas=activas, cic10_motivo=loop.estado_seguro.bloqueado_motivo,
                    modo_prueba_permitido=ok_prueba, motivo_prueba=motivo_prueba or "—",
                    cambio_programa_permitido=ok_programa, motivo_programa=motivo_programa or "—",
                    estado_seguro_sigue_activo=loop.estado_seguro.activo,
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
        movidas |= {k for k in DE_PROCESO if a["tarjeta"].on(k)}
    confirmado = loop.confirmar_estado_seguro()
    visto = _seguir(a)
    return _resumen(visto, confirmacion_tras_paro=pide, causa_tras_paro=causa,
                    salidas_sin_confirmar=sorted(movidas) or ["ninguna"], confirmado=confirmado)


def _cambio_programa_en_protocolo(a, programas_fabrica=None, **_):
    _caliente_a_presion(a["planta"])
    _arrancar(a)
    loop = a["loop"]
    for _ in range(20):
        _tick(a)
    del_protocolo = loop.estado_seguro.programa
    otro = next(p for n, p in sorted(programas_fabrica.items())
                if p.id != a["programa"].id)
    ok, motivo = loop.set_active_cycle(otro)
    sigue = {"en_programas": True, "temp_max": []}

    def revisar(_i):
        if loop.estado_seguro.activo:
            sigue["en_programas"] &= any(p is del_protocolo for p in loop.programas_para_seguridad())
            sigue["temp_max"].append(loop.temp_max_tras_ciclo())
    visto = _seguir(a, cada=revisar)
    return _resumen(visto, cambio_permitido=ok, motivo_cambio=motivo or "—",
                    programa_protocolo_sigue_contando=sigue["en_programas"],
                    temp_max_durante=sorted({v for v in sigue["temp_max"] if v is not None}))


def _modo_prueba_en_protocolo(a, **_):
    from autoclave.core.runtime import salidas_prueba_seguridad as sps
    _caliente_a_presion(a["planta"])
    _arrancar(a)
    loop = a["loop"]
    for _ in range(10):
        _tick(a)
    ok, motivo = loop.enter_test_mode()
    bloqueadas = loop.salidas_prueba_bloqueadas()
    # una orden que se hubiera colado: el lazo la apaga en el tick siguiente
    for k in ("abrir_puerta_1", "desbloqueo_puerta_1", "vapor_camara", "descompresion_rapida"):
        a["tarjeta"].set_output(EstadoAutoclave.map_do[k] + 1, True)
    _tick(a)
    encendidas = sorted(k for k in (*sps.SALIDAS_PUERTA, *sps.SALIDAS_VAPOR)
                        if a["tarjeta"].on(k))
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
        if fuga["desde"] is None and a["tarjeta"].on("aire_admosferico_camara"):
            fuga["desde"] = _i
        if fuga["desde"] is not None and fuga["ticks"] < 6:
            a["planta"].p_aire += 10.0 + max(0.0, t11.P_ATM - a["planta"].p)
            fuga["ticks"] += 1
    visto = _seguir(a, cada=cada)
    return _resumen(visto, fuga_aplicada=fuga["ticks"] == 6)


_CELDAS = {"arranque_presurizado": _arranque_presurizado, "arranque_vacio": _arranque_vacio,
           "arranque_sin_presion": _arranque_sin_presion,
           "paro_real_en_arranque": _paro_real_en_arranque,
           "cambio_programa_en_protocolo": _cambio_programa_en_protocolo,
           "modo_prueba_en_protocolo": _modo_prueba_en_protocolo,
           "arranque_vacio_con_fuga": _arranque_vacio_con_fuga}


@pytest.mark.parametrize("numero", sorted(PROGRAMAS))
@pytest.mark.parametrize("celda", list(_CELDAS))
def test_ensayo_s9(programas, monkeypatch, numero, celda):  # noqa: F811
    a = _equipo(programas[numero], monkeypatch, programas)
    r = _CELDAS[celda](a, programas_fabrica=programas)
    RESULTADOS[(numero, celda)] = r
    if celda != "paro_real_en_arranque":
        assert r["confirmacion_pedida"] is False, r
        assert "paro_liberado" not in r["causas"], r
    assert r["listo_durante_el_protocolo"] is False, r
    assert r["ticks_aire_abierto_con_presion"] == 0, r        # SAF-03, por tick
    if celda in ("arranque_presurizado", "paro_real_en_arranque", "cambio_programa_en_protocolo",
                 "modo_prueba_en_protocolo"):
        assert "descompresion_lenta" in r["salidas_abiertas"], r
        assert not set(r["salidas_abiertas"]) & set(VALVULAS_PROHIBIDAS_LENTA), r
        assert r["lenta_en_vacio"] is False, r      # al enfriarse en vacío: aire atmosférico
        assert r["estado_seguro_alcanzado"] is True, r
    if celda == "arranque_vacio":
        assert "aire_admosferico_camara" in r["salidas_abiertas"], r
        assert r["lenta_en_vacio"] is False, r
        assert r["estado_seguro_alcanzado"] is True, r
    if celda == "arranque_sin_presion":
        assert r["salidas_abiertas"] == ["ninguna"], r
        assert {"CIC-10", "SEN-06"} <= set(r["alarmas"]), r
        assert r["cic10_motivo"].startswith("Sensor de presión de cámara"), r
        assert r["modo_prueba_permitido"] and r["cambio_programa_permitido"], r
        assert r["estado_seguro_sigue_activo"] and r["inicio_bloqueado"], r
        assert r["causas"] == ["arranque"], r
    if celda == "paro_real_en_arranque":
        assert r["confirmacion_tras_paro"] is True and r["causa_tras_paro"] == "paro_liberado", r
        assert r["salidas_sin_confirmar"] == ["ninguna"], r
        assert r["confirmado"] is True, r
    if celda == "modo_prueba_en_protocolo":
        assert r["modo_prueba_permitido"] is True, r
        assert {"abrir_puerta_1", "desbloqueo_puerta_1", "vapor_camara",
                "descompresion_rapida"} <= set(r["bloqueadas_en_prueba"]), r
        assert r["encendidas_tras_un_tick"] == ["ninguna"], r
    if celda == "arranque_vacio_con_fuga":
        assert r["fuga_aplicada"] is True, r
        assert "aire_admosferico_camara" in r["salidas_abiertas"], r
    if celda == "cambio_programa_en_protocolo":
        assert r["cambio_permitido"] is True, r
        assert r["programa_protocolo_sigue_contando"] is True, r
        assert r["temp_max_durante"] and max(r["temp_max_durante"]) <= 80.0, r


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

"""E1 (tanda 3): ensayo completo en simulador — 4 programas × eventos.

Usa la planta simulada de T11 (modelo físico simple de la cámara, valores
PROVISIONALES) con CicloState real, SetOutput real, CycleLogger real (ticket y
respaldo) y, para el reinicio, DbManager real y el protocolo de estado seguro.
El simulador del repositorio (autoclave.simulador) solo repite ciclos grabados:
no puede provocar fallas.

Eventos por programa: ciclo completo, cancelación, paro de emergencia en ciclo,
pérdida de la tarjeta en ciclo, corte de energía y reinicio con la cámara
caliente. Los eventos que no dependen del programa (apagado en FALLA y sin
tarjeta, A1; cambio de programa en FALLA, S2) se verifican con sus pruebas
(ver el informe). Con E1_ESCRIBIR_INFORME=1 se escribe la tabla en
docs/informes/tanda3/E1_tabla.md.
"""

import os
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autoclave.core.managers.config_manager import ConfigManager
from autoclave.core.runtime import camara_segura
from autoclave.core.runtime.contador_ciclos import ContadorCiclos
from autoclave.core.runtime.respaldo_ciclos import RespaldoCiclos
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.devices.io.set_io import SetOutput
from autoclave.installation.equipment import EquipmentClass, get_capabilities
from autoclave.services.domain.logging.cycle_logger import CycleLogger
from autoclave.services.domain.logging.db_manager import DbManager
from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.cycle_phases.protocolo_fallo import ProtocoloFallo
from autoclave.state_machine.estado_seguro import ProtocoloEstadoSeguro
from autoclave.state_machine.machine.enum_global import GlobalState
from autoclave.state_machine.states.ciclo import CicloResultado, CicloState
from tests import test_t11_programas_integracion as t11
from tests.test_t11_programas_integracion import DT, _Planta, _Tarjeta

PROGRAMAS = {1: "Bowie & Dick", 2: "Instrumental 134", 3: "Instrumental 121", 4: "Líquidos"}
EVENTOS = ("completo", "cancelacion", "paro", "perdida_tarjeta", "corte_y_reinicio")
SALIDAS_DE_PROCESO = ("vapor_camara", "vapor_chaqueta", "vacio_camara", "bomba_vacio",
                      "aire_comprimido_camara")
RESULTADOS: dict[tuple[int, str], dict] = {}


@pytest.fixture(scope="module")
def programas():
    from autoclave.core.managers.cycle_manager import CycleManager
    cm = CycleManager()
    cm._load_from_folder("cycles/factory", source="factory")
    return {c.number: c for c in cm.cycles.values() if c.number is not None}


def _armar(programa, monkeypatch, tmp_path, db=None, contador=None):
    reloj = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: reloj[0])
    estado = EstadoAutoclave()
    for di in estado.sensores_di:
        estado.sensores_di[di] = 1
    estado.sensores_di["paro_emergencia"] = 1
    estado.set_machine_state(GlobalState.CICLO)
    tarjeta = _Tarjeta(estado)
    config = ConfigManager()
    config.load_config()
    t11.P_ATM = float(config.get("presion_admosferica") or 101.3)
    planta = _Planta(tarjeta)
    alarmas = AlarmManager()
    set_do = SetOutput(tarjeta, estado, profile=None)
    ciclo = CicloState(estado, set_do, programa, config, alarmas,
                       cap=get_capabilities(EquipmentClass.PISO_LAB))
    printer = MagicMock()
    cm = MagicMock()
    cm.get_selected_cycle.return_value = programa
    contador = contador or ContadorCiclos(tmp_path / "ciclo_contador.json")
    registro = CycleLogger(db or MagicMock(), estado, config, MagicMock(serial_number="BANCO-1", model_id="LAB"),
                           cm, printer=printer, contador=contador,
                           respaldo=RespaldoCiclos(tmp_path / "respaldo"),
                           sin_base_de_datos=db is None and False)
    planta.publicar(estado)
    ciclo.reset()
    estado.operador_inicio = "ensayo"
    return dict(reloj=reloj, estado=estado, tarjeta=tarjeta, config=config, planta=planta, alarmas=alarmas,
                set_do=set_do, ciclo=ciclo, printer=printer, registro=registro, contador=contador)


def _tick(a):
    a["planta"].publicar(a["estado"])
    r = a["ciclo"].run()
    a["registro"].update()
    return r


def _avanzar(a):
    a["planta"].paso()
    a["reloj"][0] += DT


def _hasta_fase(a, fase, extra_s=0.0, limite_s=4 * 3600):
    t_extra = None
    for _ in range(int(limite_s / DT)):
        r = _tick(a)
        if r == CicloResultado.ESPERANDO_CONFIRMACION:
            return r
        if a["estado"].fase_ciclo == fase:
            t_extra = 0.0 if t_extra is None else t_extra + DT
            if t_extra >= extra_s:
                return None
        _avanzar(a)
    raise AssertionError(f"no se llegó a {fase}")


def _terminar(a, limite_s=3 * 3600):
    """Sigue hasta ESPERANDO_CONFIRMACION y luego unos minutos de protocolo."""
    for _ in range(int(limite_s / DT)):
        r = _tick(a)
        if r == CicloResultado.ESPERANDO_CONFIRMACION:
            break
        _avanzar(a)
    for _ in range(int(900 / DT)):          # 15 min más de protocolo de fallo / reposo
        _tick(a)
        _avanzar(a)


def _ticket(a) -> str:
    return "\n".join(c.args[0] for c in a["printer"].enqueue.call_args_list)


def _linea(ticket: str, prefijo: str) -> str:
    return next((l.strip() for l in ticket.splitlines() if l.strip().startswith(prefijo)), "—")


def _resumen(a, evento, extra=None):
    e, p = a["estado"], a["planta"]
    activas = sorted(i.codigo if hasattr(i, "codigo") else getattr(i, "clave", str(i))
                     for i in a["alarmas"].activas())
    ticket = _ticket(a)
    fuera = [k for k, v in e.salidas_do.items() if v and k in SALIDAS_DE_PROCESO]
    return {"evento": evento, "fase_final": e.fase_ciclo, "motivo": e.motivo_fallo or "—",
            "alarmas": activas or ["—"], "estado_ticket": _linea(ticket, "Estado:"),
            "operador_ticket": _linea(ticket, "Operador:"),
            "lecturas_ticket": sum(1 for l in ticket.splitlines() if l[:1] in "WHSE" and ":" in l),
            "salidas_proceso_al_final": fuera, "T": round(p.t_sonda, 1), "P": round(p.p, 1),
            "minutos": round((a["reloj"][0] - 1000.0) / 60, 1), **(extra or {})}


# ── eventos ────────────────────────────────────────────────────────────────

def _evento_completo(a, **_):
    r = None
    for _ in range(int(4 * 3600 / DT)):
        r = _tick(a)
        if r == CicloResultado.ESPERANDO_CONFIRMACION:
            break
        _avanzar(a)
    assert r == CicloResultado.ESPERANDO_CONFIRMACION
    return _resumen(a, "completo")


def _evento_cancelacion(a, **_):
    _hasta_fase(a, "ESTERILIZACION", extra_s=60)
    a["estado"].set_flag("CICLO_CANCELADO", True)
    _terminar(a)
    return _resumen(a, "cancelacion")


def _evento_paro(a, **_):
    _hasta_fase(a, "ESTERILIZACION", extra_s=60)
    a["estado"].set_flag("PARO_EMERGENCIA", True)
    a["estado"].set_flag("PARO_REAL", True)
    a["estado"].sensores_di["paro_emergencia"] = 0
    _terminar(a)
    con_paro = _resumen(a, "paro")
    a["estado"].set_flag("PARO_EMERGENCIA", False)               # se suelta el paro: sin avance automático
    a["estado"].set_flag("PARO_REAL", False)
    a["estado"].sensores_di["paro_emergencia"] = 1
    for _ in range(int(120 / DT)):
        _tick(a)
        _avanzar(a)
    movio = [k for k, v in a["estado"].salidas_do.items() if v and k in SALIDAS_DE_PROCESO]
    con_paro["tras_soltar_paro_sin_confirmar"] = "salidas de proceso en 0" if not movio else movio
    return con_paro


def _evento_perdida_tarjeta(a, **_):
    _hasta_fase(a, "ESTERILIZACION", extra_s=60)
    a["ciclo"].abortar_por_desconexion(5.0)                     # lo que hace el ControlLoop pasada la tolerancia
    _terminar(a)
    return _resumen(a, "perdida_tarjeta")


def _evento_corte_y_reinicio(a, tmp_path=None, programa=None, monkeypatch=None, db_ruta=None, **_):
    _hasta_fase(a, "ESTERILIZACION", extra_s=60)
    planta, programa_ciclo = a["planta"], a["ciclo"].cycle
    marca = a["contador"].en_curso()
    # ── corte de energía: se pierde todo lo que está en memoria ──────────────
    a["tarjeta"].all_off()                                      # el watchdog de la tarjeta apaga las salidas
    # ── reinicio: base nueva (cierra el ciclo interrumpido), estado nuevo, cámara física intacta ──
    db2 = DbManager(db_ruta)
    cerrados = db2.cerrar_ciclos_interrumpidos("Ciclo interrumpido: el equipo se reinició o perdió energía")
    marca2 = ContadorCiclos(tmp_path / "ciclo_contador.json").en_curso()
    estado2 = EstadoAutoclave()
    for di in estado2.sensores_di:
        estado2.sensores_di[di] = 1
    estado2.set_machine_state(GlobalState.PREPARACION)
    tarjeta2 = _Tarjeta(estado2)
    planta.tarjeta = tarjeta2
    set_do2 = SetOutput(tarjeta2, estado2, profile=None)
    planta.publicar(estado2)
    segura0, motivo0 = camara_segura.evaluar(estado2, a["config"], [programa_ciclo], None, datos_vigentes=True)
    prot = ProtocoloFallo(estado2, set_do2, programa_ciclo, a["config"])
    prot.ejecutar(abrir_valvulas=False)                         # recuperación: todo en 0, sin válvulas
    es = ProtocoloEstadoSeguro(estado2, a["config"], programas_seguridad=lambda: [programa_ciclo])
    es.iniciar(prot, requiere_confirmacion=True)
    a["reloj"][0] += 5
    sin_confirmar = []
    for _ in range(int(60 / DT)):                               # sin confirmar nada se mueve
        planta.publicar(estado2)
        es.update()
        sin_confirmar += [k for k, v in estado2.salidas_do.items() if v]
        planta.paso()
        a["reloj"][0] += DT
    assert es.confirmar() is True                               # "Confirmar y llevar a estado seguro"
    t0 = a["reloj"][0]
    rapida_caliente = None
    for _ in range(int(3 * 3600 / DT)):
        planta.publicar(estado2)
        es.update()
        if tarjeta2.on("descompresion_rapida") and planta.t > 80.5:
            rapida_caliente = max(rapida_caliente or 0, planta.t)
        if not es.activo:
            break
        planta.paso()
        a["reloj"][0] += DT
    return {"evento": "corte_y_reinicio", "fase_final": "ESTADO SEGURO" if not es.activo else "NO LLEGÓ",
            "motivo": "Ciclo interrumpido" if cerrados else "—", "alarmas": ["—"],
            "estado_ticket": "—", "operador_ticket": "—", "lecturas_ticket": 0,
            "salidas_proceso_al_final": [], "T": round(planta.t_sonda, 1), "P": round(planta.p, 1),
            "minutos": round((a["reloj"][0] - 1000.0) / 60, 1),
            "ciclos_cerrados_al_arrancar": len(cerrados), "marca_en_curso": bool(marca),
            "marca_sobrevive_al_corte": bool(marca2), "camara_segura_al_reiniciar": segura0,
            "sin_confirmar_salidas": sorted(set(sin_confirmar)) or "ninguna",
            "min_hasta_estado_seguro": round((a["reloj"][0] - t0) / 60, 1),
            "rapida_con_carga_caliente": rapida_caliente}


_FUNCIONES = {"completo": _evento_completo, "cancelacion": _evento_cancelacion, "paro": _evento_paro,
              "perdida_tarjeta": _evento_perdida_tarjeta, "corte_y_reinicio": _evento_corte_y_reinicio}


@pytest.mark.parametrize("numero", sorted(PROGRAMAS))
@pytest.mark.parametrize("evento", EVENTOS)
def test_ensayo(programas, monkeypatch, tmp_path, numero, evento):
    db_ruta = tmp_path / "ensayo.db"
    db = DbManager(db_ruta) if evento == "corte_y_reinicio" else None
    a = _armar(programas[numero], monkeypatch, tmp_path, db=db)
    r = _FUNCIONES[evento](a, tmp_path=tmp_path, db_ruta=db_ruta)
    RESULTADOS[(numero, evento)] = r

    # invariantes de seguridad de TODOS los eventos
    assert not a["tarjeta"].on("vapor_camara") or evento == "completo"
    if evento == "completo":
        assert r["fase_final"] == "COMPLETADO" and "Estado: COMPLETADO" in r["estado_ticket"], r
        assert r["operador_ticket"] == "Operador: ensayo" and r["lecturas_ticket"] >= 3
        assert r["salidas_proceso_al_final"] == []
    elif evento == "cancelacion":
        assert r["fase_final"] == "CANCELADO" and "CANCELADO" in r["estado_ticket"], r
        assert r["salidas_proceso_al_final"] == []
        assert r["P"] <= t11.P_ATM + 25, r                      # el protocolo venteó la cámara
    elif evento == "paro":
        assert r["fase_final"] == "EMERGENCIA" and "SIS-01" in r["alarmas"], r
        assert r["salidas_proceso_al_final"] == []
        assert r["tras_soltar_paro_sin_confirmar"] == "salidas de proceso en 0"
    elif evento == "perdida_tarjeta":
        assert r["fase_final"] == "FALLO_CONEXION" and "COM-02" in r["alarmas"], r
        assert r["salidas_proceso_al_final"] == []
    else:
        assert r["marca_en_curso"] and r["marca_sobrevive_al_corte"] and r["ciclos_cerrados_al_arrancar"] == 1, r
        assert r["camara_segura_al_reiniciar"] is False                       # caliente y presurizada
        assert r["sin_confirmar_salidas"] == "ninguna"                       # sin confirmar, nada se mueve
        assert r["fase_final"] == "ESTADO SEGURO", r
        if numero == 4:                                                       # líquidos: nunca la rápida caliente
            assert r["rapida_con_carga_caliente"] is None, r
        # sólidos: la descompresión del programa puede usar la rápida con la carga caliente
        # (no hay líquido que hierva); el valor queda en la tabla como dato
    if evento in ("cancelacion", "paro", "perdida_tarjeta"):
        assert r["estado_ticket"] != "—"                         # el ticket se cerró con el estado del fallo


def test_escribir_informe():
    """Se ejecuta al final (orden de definición): escribe la tabla si se pide."""
    if os.environ.get("E1_ESCRIBIR_INFORME") != "1":
        pytest.skip("solo con E1_ESCRIBIR_INFORME=1")
    filas = ["| Programa | Evento | Fase/estado final | Alarmas | Ticket | Salidas de proceso al final | T (°C) / P (kPa) | Min simulados |",
             "|---|---|---|---|---|---|---|---|"]
    notas = []
    for numero in sorted(PROGRAMAS):
        for evento in EVENTOS:
            r = RESULTADOS.get((numero, evento))
            if r is None:
                continue
            filas.append(f"| {numero} {PROGRAMAS[numero]} | {evento} | {r['fase_final']} | {', '.join(r['alarmas'])} | "
                         f"{r['estado_ticket']} · {r['operador_ticket']} | {r['salidas_proceso_al_final'] or 'ninguna'} | "
                         f"{r['T']} / {r['P']} | {r['minutos']} |")
            if evento == "paro":
                notas.append(f"- {numero} paro: tras soltar el paro sin confirmar → {r['tras_soltar_paro_sin_confirmar']}")
            if evento == "corte_y_reinicio":
                notas.append(f"- {numero} corte y reinicio: ciclos cerrados como interrumpidos={r['ciclos_cerrados_al_arrancar']}, "
                             f"marca en curso sobrevive={r['marca_sobrevive_al_corte']}, cámara segura al reiniciar="
                             f"{r['camara_segura_al_reiniciar']}, salidas sin confirmar={r['sin_confirmar_salidas']}, "
                             f"estado seguro en {r['min_hasta_estado_seguro']} min, rápida con carga caliente={r['rapida_con_carga_caliente']}")
    Path("docs/informes/tanda3/E1_tabla.md").write_text("\n".join(filas) + "\n\n" + "\n".join(notas) + "\n", encoding="utf-8")

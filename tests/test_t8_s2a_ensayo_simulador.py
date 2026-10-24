"""Tanda 8 / S2a: repetición con la planta simulada de E1 (tanda 3) de las
celdas de transición que toca S2a (D8-2.6 a D8-2.10), en los 4 programas de
fábrica (modelo: tests/test_q1_ensayo_simulador.py). Con
S2A_ESCRIBIR_INFORME=1 escribe la tabla en
docs/informes/tanda8/S2a_ensayo_tabla.md.

- d826: cancelación en ESTERILIZACION y luego se pierde el Principal: FALLA
  se puede dejar sin técnico (solo_lenta) y la cámara no es segura.
- d827: desconexión total breve (antes de COM-02) en ESTERILIZACION: la
  exposición se alarga lo que duró la desconexión y no se acumula F0.
- d828: pausas repetidas por DI vencida en una exposición que suman más que
  pausa_max_esterilizacion_s: FALLO con CIC-11.
- d829: tras una DI vencida vuelven los datos sin tramas nuevas: la
  tolerancia no se reinicia y una segunda caída aborta (FALLO_CONEXION).
- d8210: se pierde el Principal en DESCOMPRESION. En Líquidos (modo 4) con el
  enfriamiento con contrapresión en curso: cámara sellada sin abrir nada
  mientras la Referencia esté caliente; con las sondas frías, la lenta. En
  los programas sólidos (modo 1) sigue el criterio P-2 (la lenta).
"""

import os
from pathlib import Path

import pytest

from autoclave.state_machine.alarms.catalogo import CIC_11
from autoclave.state_machine.cycle_phases.protocolo_fallo import _DEBOUNCE_LECTURAS
from autoclave.state_machine.estado_seguro import ProtocoloEstadoSeguro
from autoclave.state_machine.states import ciclo as modulo_ciclo
from autoclave.state_machine.states.ciclo import CicloResultado
from tests import test_e1_ensayo_simulador as e1
from tests.test_e1_ensayo_simulador import PROGRAMAS, programas  # noqa: F401
from tests.test_t11_programas_integracion import DT

RESULTADOS: dict[tuple[int, str], dict] = {}
_VALVULAS = ("descompresion_lenta", "descompresion_rapida", "descompresion_chaqueta",
             "aire_comprimido_camara", "agua_chaqueta", "aire_admosferico_camara",
             "vapor_camara")


def _hasta_pendiente(a, limite_s=4 * 3600):
    for _ in range(int(limite_s / DT)):
        r = e1._tick(a)
        if r == CicloResultado.ESPERANDO_CONFIRMACION:
            return r
        e1._avanzar(a)
    raise AssertionError("el ciclo no terminó")


def _ticks(a, segundos):
    for _ in range(int(segundos / DT)):
        e1._tick(a)
        e1._avanzar(a)


def _quitar_sondas(a, sensores, valor=None):
    original = a["planta"].publicar

    def publicar(estado):
        original(estado)
        for s in sensores:
            estado.sensores_temp[s] = valor
    a["planta"].publicar = publicar
    return original


def _evento_d826(a):
    e1._hasta_fase(a, "ESTERILIZACION", extra_s=60)
    a["estado"].set_flag("CICLO_CANCELADO", True)
    _hasta_pendiente(a)
    _ticks(a, 30)
    principal = modulo_ciclo.sensor_principal(a["ciclo"].cycle)
    _quitar_sondas(a, [principal])
    _ticks(a, _DEBOUNCE_LECTURAS * DT + 60)
    es = ProtocoloEstadoSeguro(a["estado"], a["config"],
                               programas_seguridad=lambda: [a["ciclo"].cycle])
    es.iniciar(a["ciclo"]._protocolo)
    for _ in range(5):
        es.update()
    return {"fase_final": a["estado"].fase_ciclo,
            "solo_lenta": a["ciclo"]._protocolo.solo_lenta,
            "sale_de_falla_sin_tecnico": es.permite_salir_de_falla,
            "camara_segura": not es.activo,
            "rapida_abierta": bool(a["tarjeta"].on("descompresion_rapida"))}


def _evento_d827(a):
    tiempo_s = (a["ciclo"].cycle.get_param("esterilizacion", "tiempo_esterilizacion") or 3.5) * 60
    marcas = {}

    def registrar():
        fase = a["estado"].fase_ciclo
        if fase == "ESTERILIZACION" and "inicio" not in marcas:
            marcas["inicio"] = a["reloj"][0]
        elif "inicio" in marcas and fase != "ESTERILIZACION" and "fin" not in marcas:
            marcas["fin"] = a["reloj"][0]

    for _ in range(int(4 * 3600 / DT)):
        e1._tick(a)
        registrar()
        if "inicio" in marcas and a["reloj"][0] - marcas["inicio"] >= 60:
            break
        e1._avanzar(a)
    e1._avanzar(a)
    # 3 s sin enlace: el ControlLoop no corre run(), solo marca el tramo
    for _ in range(int(3.0 / DT)):
        a["ciclo"].marcar_sin_datos_tarjeta()
        e1._avanzar(a)
    for _ in range(int(4 * 3600 / DT)):
        r = e1._tick(a)
        registrar()
        if r == CicloResultado.ESPERANDO_CONFIRMACION:
            break
        e1._avanzar(a)
    duracion = marcas.get("fin", a["reloj"][0]) - marcas["inicio"]
    return {"fase_final": a["estado"].fase_ciclo, "tiempo_programado_s": tiempo_s,
            "extension_s": round(duracion - tiempo_s, 1),
            "sin_datos_s": round(a["estado"].sin_datos_tarjeta_s, 1)}


def _evento_d828(a):
    e1._hasta_fase(a, "ESTERILIZACION", extra_s=10)
    pausas = 0
    for _ in range(15):                    # 15 tramos de 3 s de DI vencida
        if a["estado"].fase_ciclo != "ESTERILIZACION":
            break
        a["estado"].set_flag("PARO_EMERGENCIA", True)
        for _ in range(int(3.0 / DT)):
            e1._tick(a)
            e1._avanzar(a)
        a["estado"].set_flag("PARO_EMERGENCIA", False)
        pausas += 1
        _ticks(a, 2.0)
    r = e1._tick(a)
    activas = [i.codigo for i in a["alarmas"].activas()]
    return {"fase_final": a["estado"].fase_ciclo, "pausas": pausas,
            "resultado": getattr(r, "name", r),
            "cic_11": CIC_11 in activas or a["estado"].codigo_fallo == CIC_11}


def _evento_d829(a):
    e1._hasta_fase(a, "ESTERILIZACION", extra_s=10)
    a["estado"].set_flag("PARO_EMERGENCIA", True)
    for _ in range(int(3.0 / DT)):
        e1._tick(a)
        e1._avanzar(a)
    # vuelven los datos, pero sin tramas DI nuevas (la misma trama vigente)
    a["estado"].set_flag("PARO_EMERGENCIA", False)
    a["estado"].trama_di_nueva = False
    for _ in range(6):
        e1._tick(a)
        e1._avanzar(a)
    a["estado"].set_flag("PARO_EMERGENCIA", True)
    r = None
    for _ in range(int(2.0 / DT)):
        r = e1._tick(a)
        if r == CicloResultado.ESPERANDO_CONFIRMACION:
            break
        e1._avanzar(a)
    return {"fase_final": a["estado"].fase_ciclo,
            "aborto": r == CicloResultado.ESPERANDO_CONFIRMACION}


def _evento_d8210(a, con_referencia=False):
    """Principal perdido en DESCOMPRESION (con el enfriamiento en curso si el
    modo es 4/5). Sin Referencia (asignación de fábrica) solo queda el
    drenaje, que su agua mantiene frío: rige la espera sin sonda. Con
    Referencia: sellada mientras esté caliente; fría (70 °C), la lenta."""
    if con_referencia:
        a["ciclo"].cycle.sensores = {"temp_camara": "principal", "temp_2_camara": "no_en_uso",
                                     "temp_ref": "referencia"}
        # Tanda 12 (C-01): con p_obj = Psat(T_obj) el Principal se estabiliza
        # justo sobre T_obj; la planta publica temp_ref = T - 0.2 y esa
        # Referencia nunca llegaría a la consigna (FALLO cal_no_sostuvo antes
        # de DESCOMPRESION, que es lo que este evento ensaya). Físicamente el
        # Principal está en la zona más fría de la cámara: la Referencia va
        # 0.2 K por encima.
        original = a["planta"].publicar

        def publicar(estado):
            original(estado)
            t = estado.sensores_temp.get("temp_camara")
            if t is not None:
                estado.sensores_temp["temp_ref"] = t + 0.2
        a["planta"].publicar = publicar
    e1._hasta_fase(a, "DESCOMPRESION", extra_s=2)
    enfriando = a["ciclo"]._fase_en_enfriamiento_con_contrapresion()
    principal = modulo_ciclo.sensor_principal(a["ciclo"].cycle)
    _quitar_sondas(a, [principal])
    _hasta_pendiente(a, limite_s=60)
    t0 = a["reloj"][0]
    prot = a["ciclo"]._protocolo
    abiertas = set()
    for _ in range(int(600 / DT)):                     # 10 min
        e1._tick(a)
        abiertas |= {v for v in _VALVULAS if a["tarjeta"].on(v)}
        e1._avanzar(a)
    sellado = prot.sellado
    ref_c = a["estado"].sensores_temp.get("temp_ref")
    if con_referencia:
        _quitar_sondas(a, ["temp_ref"], valor=70.0)
    minuto_venteo = None
    for _ in range(int(45 * 60 / DT)):
        e1._tick(a)
        if minuto_venteo is None and a["tarjeta"].on("descompresion_lenta"):
            minuto_venteo = round((a["reloj"][0] - t0) / 60, 1)
            break
        e1._avanzar(a)
    return {"fase_final": a["estado"].fase_ciclo, "enfriando_al_perder": enfriando,
            "sellado_10_min": sellado, "abiertas_10_min": ",".join(sorted(abiertas)) or "ninguna",
            "ref_C": round(ref_c, 1) if ref_c is not None else None,
            "minuto_venteo_lenta": minuto_venteo,
            "rapida_al_ventear": bool(a["tarjeta"].on("descompresion_rapida")),
            "motivo_venteo": prot.motivo_venteo}


def _evento_d8210_ref(a):
    return _evento_d8210(a, con_referencia=True)


_EVENTOS = {"d826": _evento_d826, "d827": _evento_d827, "d828": _evento_d828,
            "d829": _evento_d829, "d8210": _evento_d8210, "d8210_ref": _evento_d8210_ref}


@pytest.mark.parametrize("numero", sorted(PROGRAMAS))
@pytest.mark.parametrize("evento", list(_EVENTOS))
def test_ensayo_s2a(programas, monkeypatch, tmp_path, numero, evento):  # noqa: F811
    a = e1._armar(programas[numero], monkeypatch, tmp_path)
    r = _EVENTOS[evento](a)
    RESULTADOS[(numero, evento)] = r
    if evento == "d826":
        assert r["fase_final"] == "CANCELADO" and r["solo_lenta"] is True, r
        assert r["sale_de_falla_sin_tecnico"] is True and r["camara_segura"] is False, r
        assert r["rapida_abierta"] is False, r
    elif evento == "d827":
        assert r["fase_final"] == "COMPLETADO", r
        assert r["extension_s"] >= 3.0 - DT, r
        assert r["sin_datos_s"] >= 3.0 - DT, r
    elif evento == "d828":
        assert r["cic_11"] is True and r["fase_final"] != "COMPLETADO", r
    elif evento == "d829":
        assert r["aborto"] is True and r["fase_final"] == "FALLO_CONEXION", r
    else:
        assert r["fase_final"] == "SENSOR_AUSENTE", r
        assert r["rapida_al_ventear"] is False, r
        if numero == 4:                                   # Líquidos, modo 4
            assert r["enfriando_al_perder"] is True, r
            assert r["sellado_10_min"] is True and r["abiertas_10_min"] == "ninguna", r
            if evento == "d8210":
                assert r["motivo_venteo"] == "espera_sin_sonda", r
                assert 30.0 <= r["minuto_venteo_lenta"] <= 31.0, r
            else:
                assert r["motivo_venteo"] == "sondas_frias", r
                assert r["minuto_venteo_lenta"] <= 10.2, r
        else:
            assert r["sellado_10_min"] is False, r
            assert "descompresion_lenta" in r["abiertas_10_min"], r


def test_escribir_informe_s2a():
    if os.environ.get("S2A_ESCRIBIR_INFORME") != "1":
        pytest.skip("solo con S2A_ESCRIBIR_INFORME=1")
    filas = ["| Programa | Evento | Resultado |", "|---|---|---|"]
    for numero in sorted(PROGRAMAS):
        for evento in _EVENTOS:
            r = RESULTADOS.get((numero, evento))
            if r is not None:
                datos = ", ".join(f"{k}={v}" for k, v in r.items())
                filas.append(f"| {numero} {PROGRAMAS[numero]} | {evento} | {datos} |")
    destino = Path("docs/informes/tanda8/S2a_ensayo_tabla.md")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(filas) + "\n", encoding="utf-8")

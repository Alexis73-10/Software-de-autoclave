"""Q1 (tanda 7): repetición con la planta simulada de E1 (tanda 3) de las celdas
de la matriz de transiciones de T2 (docs/informes/tanda6/T2_matriz_actualizada.md)
afectadas por la decisión 1.3 (R1-P3, R1-P4, R1-P5, T2-a y T2-c), en los 4
programas de fábrica. R1-P1, R1-P2 y T2-b no dependen del programa ni de la
planta (modo prueba, PREPARADO y alarmas): tienen sus pruebas propias
(tests/test_q1_*). Con Q1_ESCRIBIR_INFORME=1 escribe la tabla en
docs/informes/tanda7/Q1_ensayo_tabla.md."""

import os
from pathlib import Path

import pytest

from autoclave.state_machine.estado_seguro import ProtocoloEstadoSeguro
from autoclave.state_machine.states import ciclo as modulo_ciclo
from autoclave.state_machine.states.ciclo import CicloResultado
from tests import test_e1_ensayo_simulador as e1
from tests.test_e1_ensayo_simulador import PROGRAMAS, SALIDAS_DE_PROCESO, programas  # noqa: F401
from tests.test_t11_programas_integracion import DT

RESULTADOS: dict[tuple[int, str], dict] = {}
_NO_ESTERIL = "CARGA NO ESTÉRIL"


def _ticket(a) -> str:
    return e1._ticket(a)


def _hasta_pendiente(a, limite_s=4 * 3600, durante=None):
    for _ in range(int(limite_s / DT)):
        r = e1._tick(a)
        if durante is not None:
            durante(a)
        if r == CicloResultado.ESPERANDO_CONFIRMACION:
            return r
        e1._avanzar(a)
    raise AssertionError("el ciclo no terminó")


def _di_vencida(a, segundos):
    """Trama DI vencida (PARO_EMERGENCIA sin PARO_REAL) durante `segundos`."""
    a["estado"].set_flag("PARO_EMERGENCIA", True)
    vapor = []
    for _ in range(int(segundos / DT)):
        assert e1._tick(a) == CicloResultado.EN_CURSO
        vapor.append(bool(a["tarjeta"].on("vapor_camara")))
        e1._avanzar(a)
    a["estado"].set_flag("PARO_EMERGENCIA", False)
    return any(vapor)


def _evento_r1p3_completo(a):
    """Ciclo completo con rango_calentamiento_temp/_pres separados."""
    cyc = a["ciclo"].cycle
    rangos = (cyc.get_param("calentamiento", "rango_calentamiento_temp"),
              cyc.get_param("calentamiento", "rango_calentamiento_pres"),
              cyc.get_param("calentamiento", "rango_calentamiento"))
    _hasta_pendiente(a)
    ticket = _ticket(a)
    return {"fase_final": a["estado"].fase_ciclo, "rango_temp": rangos[0],
            "rango_pres": rangos[1], "rango_viejo": rangos[2],
            "no_esteril_en_ticket": _NO_ESTERIL in ticket,
            "minutos": round((a["reloj"][0] - 1000.0) / 60, 1)}


def _evento_r1p4_cancelacion_y_principal_perdido(a):
    """Cancelación en ESTERILIZACION (protocolo normal) y, ya en marcha el
    protocolo, se pierde el Principal: pasa a solo la lenta."""
    e1._hasta_fase(a, "ESTERILIZACION", extra_s=60)
    a["estado"].set_flag("CICLO_CANCELADO", True)
    _hasta_pendiente(a)
    for _ in range(int(30 / DT)):                      # protocolo normal en marcha
        e1._tick(a)
        e1._avanzar(a)
    solo_lenta_antes = a["ciclo"]._protocolo.solo_lenta
    principal = modulo_ciclo.sensor_principal(a["ciclo"].cycle)
    original = a["planta"].publicar

    def sin_principal(estado):
        original(estado)
        estado.sensores_temp[principal] = None
    a["planta"].publicar = sin_principal
    e1._tick(a)                                         # el tick que lo detecta
    e1._avanzar(a)
    rapida = chaqueta = aire = False
    for _ in range(int(1200 / DT)):
        e1._tick(a)
        rapida |= bool(a["tarjeta"].on("descompresion_rapida"))
        chaqueta |= bool(a["tarjeta"].on("descompresion_chaqueta"))
        aire |= bool(a["tarjeta"].on("aire_comprimido_camara"))
        e1._avanzar(a)
    # tras el reconocimiento sigue el estado seguro con el mismo criterio
    es = ProtocoloEstadoSeguro(a["estado"], a["config"],
                               programas_seguridad=lambda: [a["ciclo"].cycle])
    es.iniciar(a["ciclo"]._protocolo)
    es.update()
    return {"fase_final": a["estado"].fase_ciclo, "solo_lenta_antes": solo_lenta_antes,
            "solo_lenta_despues": a["ciclo"]._protocolo.solo_lenta,
            "rapida_tras_perdida": rapida, "chaqueta_tras_perdida": chaqueta,
            "contrapresion_tras_perdida": aire,
            "lenta_al_final": bool(a["tarjeta"].on("descompresion_lenta")),
            "estado_seguro_sale_sin_tecnico": es.permite_salir_de_falla,
            "P": round(a["planta"].p, 1)}


def _evento_r1p5_abort_en_tolerancia(a):
    """Cancelación aceptada durante la tolerancia por DI vencida; se procesa
    al volver los datos."""
    e1._hasta_fase(a, "ESTERILIZACION", extra_s=60)
    a["estado"].set_flag("PARO_EMERGENCIA", True)
    assert e1._tick(a) == CicloResultado.EN_CURSO
    tolerancia = a["ciclo"].tolerancia_di_activa
    a["estado"].set_flag("CICLO_CANCELADO", True)     # lo que hace /cycle/abort (R1-P5)
    e1._avanzar(a)
    for _ in range(int(2.0 / DT)):
        assert e1._tick(a) == CicloResultado.EN_CURSO
        e1._avanzar(a)
    protocolo_durante = a["ciclo"]._protocolo.ejecutado
    a["estado"].set_flag("PARO_EMERGENCIA", False)
    _hasta_pendiente(a)
    for _ in range(int(60 / DT)):
        e1._tick(a)
        e1._avanzar(a)
    ticket = _ticket(a)
    return {"tolerancia_activa": tolerancia, "protocolo_durante_tolerancia": protocolo_durante,
            "fase_final": a["estado"].fase_ciclo,
            "cancelado_pendiente": a["estado"].get_flag("CICLO_CANCELADO"),
            "sin_datos_ticket": e1._linea(ticket, "Sin datos de la tarjeta:"),
            "no_esteril_en_ticket": _NO_ESTERIL in ticket}


def _evento_t2a_pausa_exposicion(a):
    """3 s de DI vencida en ESTERILIZACION: la exposición se alarga 3 s."""
    tiempo_s = (a["ciclo"].cycle.get_param("esterilizacion", "tiempo_esterilizacion") or 3.5) * 60
    marcas = {}

    def registrar(a_):
        fase = a_["estado"].fase_ciclo
        if fase == "ESTERILIZACION" and "inicio" not in marcas:
            marcas["inicio"] = a_["reloj"][0]
        elif "inicio" in marcas and fase != "ESTERILIZACION" and "fin" not in marcas:
            marcas["fin"] = a_["reloj"][0]

    for _ in range(int(4 * 3600 / DT)):
        e1._tick(a)
        registrar(a)
        if "inicio" in marcas and a["reloj"][0] - marcas["inicio"] >= 60:
            break
        e1._avanzar(a)
    e1._avanzar(a)
    vapor = _di_vencida(a, 3.0)
    _hasta_pendiente(a, durante=registrar)
    ticket = _ticket(a)
    duracion = (marcas.get("fin", a["reloj"][0]) - marcas["inicio"])
    return {"fase_final": a["estado"].fase_ciclo, "tiempo_programado_s": tiempo_s,
            "duracion_esterilizacion_s": round(duracion, 1),
            "extension_s": round(duracion - tiempo_s, 1),
            "vapor_durante_tolerancia": vapor,
            "sin_datos_ticket": e1._linea(ticket, "Sin datos de la tarjeta:"),
            "no_esteril_en_ticket": _NO_ESTERIL in ticket}


def _evento_t2c_paro_y_fallo(a):
    """Paro real en ESTERILIZACION: EMERGENCIA con la marca en el ticket."""
    e1._hasta_fase(a, "ESTERILIZACION", extra_s=60)
    a["estado"].set_flag("PARO_EMERGENCIA", True)
    a["estado"].set_flag("PARO_REAL", True)
    a["estado"].sensores_di["paro_emergencia"] = 0
    _hasta_pendiente(a)
    for _ in range(int(10 / DT)):
        e1._tick(a)
        e1._avanzar(a)
    ticket = _ticket(a)
    return {"fase_final": a["estado"].fase_ciclo, "estado_ticket": e1._linea(ticket, "Estado:"),
            "no_esteril_en_ticket": _NO_ESTERIL in ticket}


_EVENTOS = {
    "r1p3_completo": _evento_r1p3_completo,
    "r1p4_cancelacion_y_principal_perdido": _evento_r1p4_cancelacion_y_principal_perdido,
    "r1p5_abort_en_tolerancia_di": _evento_r1p5_abort_en_tolerancia,
    "t2a_pausa_exposicion": _evento_t2a_pausa_exposicion,
    "t2c_paro": _evento_t2c_paro_y_fallo,
}


@pytest.mark.parametrize("numero", sorted(PROGRAMAS))
@pytest.mark.parametrize("evento", list(_EVENTOS))
def test_ensayo_q1(programas, monkeypatch, tmp_path, numero, evento):  # noqa: F811
    a = e1._armar(programas[numero], monkeypatch, tmp_path)
    r = _EVENTOS[evento](a)
    RESULTADOS[(numero, evento)] = r
    if evento == "r1p3_completo":
        assert r["fase_final"] == "COMPLETADO", r
        assert r["rango_temp"] == 2.0 and r["rango_pres"] == 2.0 and r["rango_viejo"] is None, r
        assert r["no_esteril_en_ticket"] is False, r
    elif evento == "r1p4_cancelacion_y_principal_perdido":
        assert r["fase_final"] == "CANCELADO", r
        assert r["solo_lenta_antes"] is False and r["solo_lenta_despues"] is True, r
        assert not (r["rapida_tras_perdida"] or r["chaqueta_tras_perdida"]
                    or r["contrapresion_tras_perdida"]), r
        assert r["estado_seguro_sale_sin_tecnico"] is True, r
    elif evento == "r1p5_abort_en_tolerancia_di":
        assert r["tolerancia_activa"] is True and r["protocolo_durante_tolerancia"] is False, r
        assert r["fase_final"] == "CANCELADO" and r["cancelado_pendiente"] is False, r
        assert r["sin_datos_ticket"].startswith("Sin datos de la tarjeta:"), r
        assert r["no_esteril_en_ticket"] is True, r
    elif evento == "t2a_pausa_exposicion":
        assert r["fase_final"] == "COMPLETADO", r
        assert r["vapor_durante_tolerancia"] is False, r
        assert r["extension_s"] >= 3.0 - DT, r
        assert r["sin_datos_ticket"] == "Sin datos de la tarjeta: 3 s", r
        assert r["no_esteril_en_ticket"] is False, r
    else:
        assert r["fase_final"] == "EMERGENCIA" and r["no_esteril_en_ticket"] is True, r


def test_escribir_informe_q1():
    if os.environ.get("Q1_ESCRIBIR_INFORME") != "1":
        pytest.skip("solo con Q1_ESCRIBIR_INFORME=1")
    filas = ["| Programa | Evento | Resultado |", "|---|---|---|"]
    for numero in sorted(PROGRAMAS):
        for evento in _EVENTOS:
            r = RESULTADOS.get((numero, evento))
            if r is not None:
                datos = ", ".join(f"{k}={v}" for k, v in r.items())
                filas.append(f"| {numero} {PROGRAMAS[numero]} | {evento} | {datos} |")
    destino = Path("docs/informes/tanda7/Q1_ensayo_tabla.md")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(filas) + "\n", encoding="utf-8")

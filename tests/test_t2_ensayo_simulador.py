"""T2 (tanda 6): repetición con la planta simulada de E1 (tanda 3) de las celdas
de la matriz de transiciones afectadas por P-1, P-2 y P-3, en los 4 programas
de fábrica. Con T2_ESCRIBIR_INFORME=1 escribe la tabla en
docs/informes/tanda6/T2_ensayo_tabla.md."""

import os
from pathlib import Path

import pytest

from autoclave.core.runtime import camara_segura
from autoclave.state_machine.estado_seguro import ProtocoloEstadoSeguro
from autoclave.state_machine.states import ciclo as modulo_ciclo
from autoclave.state_machine.states.ciclo import CicloResultado
from tests import test_e1_ensayo_simulador as e1
from tests.test_e1_ensayo_simulador import PROGRAMAS, SALIDAS_DE_PROCESO, programas  # noqa: F401
from tests.test_t11_programas_integracion import DT

RESULTADOS: dict[tuple[int, str], dict] = {}


def _hasta_pendiente(a, limite_s=4 * 3600):
    for _ in range(int(limite_s / DT)):
        r = e1._tick(a)
        if r == CicloResultado.ESPERANDO_CONFIRMACION:
            return r
        e1._avanzar(a)
    raise AssertionError("el ciclo no terminó")


def _estado_seguro(a, limite_s=3 * 3600):
    """Lo que hace la StateMachine al reconocer: protocolo + estado seguro."""
    es = ProtocoloEstadoSeguro(a["estado"], a["config"],
                               programas_seguridad=lambda: [a["ciclo"].cycle])
    es.mantener_drenaje = a["ciclo"]._mantener_drenaje
    es.iniciar(a["ciclo"]._protocolo)
    rapida_caliente, t0 = None, a["reloj"][0]
    for _ in range(int(limite_s / DT)):
        a["planta"].publicar(a["estado"])
        es.update()
        if a["tarjeta"].on("descompresion_rapida") and a["planta"].t > 80.5:
            rapida_caliente = max(rapida_caliente or 0, a["planta"].t)
        if not es.activo:
            break
        e1._avanzar(a)
    return es, rapida_caliente, round((a["reloj"][0] - t0) / 60, 1)


def _evento_p1(a):
    """Completo + reconocimiento: si la cámara no está segura, estado seguro."""
    _hasta_pendiente(a)
    a["estado"].set_flag("CICLO_CONFIRMADO", True)
    a["planta"].publicar(a["estado"])
    assert a["ciclo"].run() == CicloResultado.COMPLETADO
    segura, motivo = camara_segura.evaluar(a["estado"], a["config"], [a["ciclo"].cycle], None)
    if segura:
        return {"camara_segura_al_reconocer": True, "fase_final": "PREPARADO",
                "rapida_caliente": None, "min_estado_seguro": 0.0}
    a["ciclo"]._protocolo.ejecutar(abrir_valvulas=True)
    es, rapida, minutos = _estado_seguro(a)
    return {"camara_segura_al_reconocer": False, "motivo": motivo,
            "fase_final": "ESTADO SEGURO" if not es.activo else "NO LLEGÓ",
            "rapida_caliente": rapida, "min_estado_seguro": minutos}


def _evento_p2(a):
    """Principal perdido en ESTERILIZACION: FALLO, solo la lenta."""
    e1._hasta_fase(a, "ESTERILIZACION", extra_s=60)
    principal = modulo_ciclo.sensor_principal(a["ciclo"].cycle)
    original = a["planta"].publicar

    def sin_principal(estado):
        original(estado)
        estado.sensores_temp[principal] = None
    a["planta"].publicar = sin_principal
    _hasta_pendiente(a)
    rapida = chaqueta = aire = False
    for _ in range(int(1800 / DT)):
        e1._tick(a)
        rapida |= bool(a["tarjeta"].on("descompresion_rapida"))
        chaqueta |= bool(a["tarjeta"].on("descompresion_chaqueta"))
        aire |= bool(a["tarjeta"].on("aire_comprimido_camara"))
        e1._avanzar(a)
    return {"fase_final": a["estado"].fase_ciclo, "solo_lenta": a["ciclo"]._protocolo.solo_lenta,
            "rapida_abierta": rapida, "chaqueta_abierta": chaqueta, "contrapresion": aire,
            "lenta_al_final": bool(a["tarjeta"].on("descompresion_lenta")),
            "bloqueado": a["ciclo"]._protocolo.bloqueado_motivo is not None,
            "P": round(a["planta"].p, 1)}


def _evento_p3(a):
    """DI vencida en ESTERILIZACION más allá de la tolerancia."""
    e1._hasta_fase(a, "ESTERILIZACION", extra_s=60)
    a["estado"].set_flag("PARO_EMERGENCIA", True)            # sin PARO_REAL: DI vencida
    durante = []
    r = None
    for _ in range(int((modulo_ciclo._TOLERANCIA_DI_VENCIDA_SEG + 2) / DT) + 1):
        r = e1._tick(a)
        if r == CicloResultado.ESPERANDO_CONFIRMACION:
            break
        durante.append(bool(a["tarjeta"].on("vapor_camara")))
        e1._avanzar(a)
    fuera = [k for k, v in a["estado"].salidas_do.items() if v and k in SALIDAS_DE_PROCESO]
    return {"fase_final": a["estado"].fase_ciclo, "resultado": r,
            "vapor_durante_tolerancia": any(durante),
            "alarmas": sorted(i.codigo for i in a["alarmas"].activas()),
            "salidas_proceso": fuera}


_EVENTOS = {"p1_completo_reconocido": _evento_p1, "p2_principal_perdido": _evento_p2,
            "p3_di_vencida": _evento_p3}


@pytest.mark.parametrize("numero", sorted(PROGRAMAS))
@pytest.mark.parametrize("evento", list(_EVENTOS))
def test_ensayo_t2(programas, monkeypatch, tmp_path, numero, evento):  # noqa: F811
    a = e1._armar(programas[numero], monkeypatch, tmp_path)
    r = _EVENTOS[evento](a)
    RESULTADOS[(numero, evento)] = r
    liquido = programas[numero].get_param("globals", "tipo_carga", default="solido") == "liquido"
    if evento == "p1_completo_reconocido":
        assert r["fase_final"] in ("PREPARADO", "ESTADO SEGURO"), r
        if liquido:
            assert r["rapida_caliente"] is None, r
    elif evento == "p2_principal_perdido":
        assert r["fase_final"] == "SENSOR_AUSENTE" and r["solo_lenta"] is True, r
        assert not r["rapida_abierta"] and not r["chaqueta_abierta"] and not r["contrapresion"], r
        assert r["bloqueado"] is True                         # CIC-10: no puede terminar solo
    else:
        assert r["fase_final"] == "FALLO_CONEXION" and "COM-03" in r["alarmas"], r
        assert r["vapor_durante_tolerancia"] is False, r
        assert r["salidas_proceso"] == [], r


def test_escribir_informe_t2():
    if os.environ.get("T2_ESCRIBIR_INFORME") != "1":
        pytest.skip("solo con T2_ESCRIBIR_INFORME=1")
    filas = ["| Programa | Evento | Resultado |", "|---|---|---|"]
    for numero in sorted(PROGRAMAS):
        for evento in _EVENTOS:
            r = RESULTADOS.get((numero, evento))
            if r is not None:
                datos = ", ".join(f"{k}={v}" for k, v in r.items())
                filas.append(f"| {numero} {PROGRAMAS[numero]} | {evento} | {datos} |")
    Path("docs/informes/tanda6/T2_ensayo_tabla.md").write_text("\n".join(filas) + "\n",
                                                               encoding="utf-8")

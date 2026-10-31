"""S1 (tanda 8, D8-1): repetición con la planta simulada de E1 (tanda 3), en
los 4 programas de fábrica, de las celdas de transición que toca SEN-01:
transductor de presión sin lectura con ciclo en curso (cámara en PRE_VACIO,
con la cámara en vacío; cámara en ESTERILIZACION, presurizada; chaqueta en
ESTERILIZACION). En todos: FALLO con código propio, vapor cortado, venteo
solo por la lenta, nunca aire atmosférico ni rápida ni chaqueta tras la
pérdida, y el FALLO no se revierte si la lectura vuelve. Con
S1_ESCRIBIR_INFORME=1 escribe la tabla en
docs/informes/tanda8/S1_ensayo_tabla.md."""

import os
from pathlib import Path

import pytest

from autoclave.core.runtime import presion_sin_lectura as psl
from autoclave.state_machine.estado_seguro import ProtocoloEstadoSeguro
from autoclave.state_machine.states.ciclo import CicloResultado
from tests import test_e1_ensayo_simulador as e1
from tests.test_e1_ensayo_simulador import PROGRAMAS, programas  # noqa: F401
from tests.test_t11_programas_integracion import DT

RESULTADOS: dict[tuple[int, str], dict] = {}


def _perder(a, canal, fase, extra_s):
    """Lleva el ciclo a `fase` (+extra_s) y desde ahí el canal publica None.
    Devuelve una función que devuelve la lectura."""
    llego = e1._hasta_fase(a, fase, extra_s=extra_s)
    p_al_perder = round(a["planta"].p, 1)
    original = a["planta"].publicar
    estado_lectura = {"perdida": True}

    def publicar(estado):
        original(estado)
        if estado_lectura["perdida"]:
            estado.sensores_pres[canal] = None
    a["planta"].publicar = publicar

    def recuperar():
        estado_lectura["perdida"] = False
    return llego, p_al_perder, recuperar


def _evento(canal, fase, extra_s):
    def correr(a):
        llego, p_al_perder, recuperar = _perder(a, canal, fase, extra_s)
        primero = e1._tick(a)
        codigo = a["estado"].codigo_fallo
        fase_tras = a["estado"].fase_ciclo
        e1._avanzar(a)
        vapor = aire = aire_recuperada = rapida = chaqueta = False
        lenta = []
        for i in range(int(600 / DT)):
            if i == int(60 / DT):
                recuperar()                       # la lectura vuelve a los 60 s
            e1._tick(a)
            vapor |= bool(a["modulo_es"].on("vapor_camara"))
            if i < int(60 / DT):
                aire |= bool(a["modulo_es"].on("aire_admosferico_camara"))
            else:
                # con lectura válida de vacío real, el aire atmosférico es la
                # acción normal (no "por" la falta de lectura)
                aire_recuperada |= bool(a["modulo_es"].on("aire_admosferico_camara"))
            rapida |= bool(a["modulo_es"].on("descompresion_rapida"))
            chaqueta |= bool(a["modulo_es"].on("descompresion_chaqueta"))
            lenta.append(bool(a["modulo_es"].on("descompresion_lenta")))
            e1._avanzar(a)
        es = ProtocoloEstadoSeguro(a["estado"], a["config"],
                                   programas_seguridad=lambda: [a["ciclo"].cycle])
        es.iniciar(a["ciclo"]._protocolo)
        return {"llego_a_fase": llego is None, "P_al_perder": p_al_perder,
                "resultado": primero, "fase_tras": fase_tras, "codigo": codigo,
                "solo_lenta": a["ciclo"]._protocolo.solo_lenta,
                "vapor_camara_tras": vapor, "aire_atm_sin_lectura": aire,
                "aire_atm_con_lectura_vuelta": aire_recuperada,
                "rapida_tras": rapida, "chaqueta_tras": chaqueta,
                "lenta_abierta": any(lenta),
                "sigue_en_fallo_tras_recuperar": a["estado"].fase_ciclo == "SENSOR_AUSENTE"
                or a["ciclo"]._resultado_pendiente is not None,
                "sale_de_falla_sin_tecnico": es.permite_salir_de_falla,
                "P_final": round(a["planta"].p, 1)}
    return correr


_EVENTOS = {
    # Líquidos (4) no tiene PRE_VACIO: la celda equivalente es CALENTAMIENTO
    "sen04_camara_en_prevacio": _evento("pres_camara", "PRE_VACIO", 20),
    "sen04_camara_en_esterilizacion": _evento("pres_camara", "ESTERILIZACION", 60),
    "sen05_chaqueta_en_esterilizacion": _evento("pres_chaqueta", "ESTERILIZACION", 60),
}


@pytest.mark.parametrize("numero", sorted(PROGRAMAS))
@pytest.mark.parametrize("evento", list(_EVENTOS))
def test_ensayo_s1(programas, monkeypatch, tmp_path, numero, evento):  # noqa: F811
    monkeypatch.setattr(psl, "_ai_habilitadas", lambda: ("pres_camara", "pres_chaqueta"))
    a = e1._armar(programas[numero], monkeypatch, tmp_path)
    if evento == "sen04_camara_en_prevacio" and numero == 4:
        r = _evento("pres_camara", "CALENTAMIENTO", 20)(a)
    else:
        r = _EVENTOS[evento](a)
    RESULTADOS[(numero, evento)] = r
    assert r["llego_a_fase"], r
    assert r["resultado"] == CicloResultado.ESPERANDO_CONFIRMACION, r
    assert r["fase_tras"] == "SENSOR_AUSENTE", r
    assert r["codigo"] == ("SEN-05" if "chaqueta" in evento else "SEN-04"), r
    assert r["solo_lenta"] is True, r
    assert not (r["vapor_camara_tras"] or r["aire_atm_sin_lectura"] or r["rapida_tras"]
                or r["chaqueta_tras"]), r
    assert r["lenta_abierta"] is True, r
    assert r["sigue_en_fallo_tras_recuperar"] is True, r
    assert r["sale_de_falla_sin_tecnico"] is True, r


def test_escribir_informe_s1():
    if os.environ.get("S1_ESCRIBIR_INFORME") != "1":
        pytest.skip("solo con S1_ESCRIBIR_INFORME=1")
    filas = ["| Programa | Evento | Resultado |", "|---|---|---|"]
    for numero in sorted(PROGRAMAS):
        for evento in _EVENTOS:
            r = RESULTADOS.get((numero, evento))
            if r is not None:
                datos = ", ".join(f"{k}={v}" for k, v in r.items())
                filas.append(f"| {numero} {PROGRAMAS[numero]} | {evento} | {datos} |")
    destino = Path("docs/informes/tanda8/S1_ensayo_tabla.md")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(filas) + "\n", encoding="utf-8")

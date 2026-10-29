"""S2b (tanda 8): repetición con la planta simulada de E1 (tanda 3), en los 4
programas de fábrica, de las celdas de transición que tocan D8-2.12 a D8-2.16
(modelo: tests/test_q1_ensayo_simulador.py de la tanda 7). D8-2.11 (salida del
modo prueba) y D8-2.15 (textos de la QML) no dependen del programa ni de la
planta: tienen sus pruebas propias. Con S2B_ESCRIBIR_INFORME=1 escribe la tabla
en docs/informes/tanda8/S2b_ensayo_tabla.md.

Celdas:
- D8-2.12: 3 s de DI vencida dentro de una ventana de estabilidad (hold de
  PRE_VACIO, ESTABLE_PREESTERILIZACION de CALENTAMIENTO, fin del SECADO): la
  ventana se corre lo que duró el tramo, sin vapor durante la tolerancia, y el
  ciclo termina COMPLETADO. El sostenimiento de PRECALENTAMIENTO no entra: en
  esta planta (como en el equipo) el ciclo arranca en PRE_VACIO; queda cubierto
  por tests/test_s2b_d8_2_12_ventanas_pausa_di.py.
- D8-2.14: en esos ciclos la reimpresión desde la base (DbManager real) tiene el
  mismo pie que el ticket impreso en vivo ("Sin datos de la tarjeta: 3 s").
- D8-2.13: módulo E/S totalmente desconectado en ESTERILIZACION (el ControlLoop no
  corre la máquina de estados): la cancelación pedida dentro de los 5 s queda en
  espera y al volver los datos el ciclo termina CANCELADO; si la desconexión
  vence la tolerancia, FALLO_CONEXION.
- D8-2.16: la pantalla de resultado marca "CARGA NO ESTÉRIL" (resultado de la
  UI distinto de "exitoso") exactamente en los ciclos no COMPLETADO.
"""

import os
from pathlib import Path

import pytest

from autoclave.core.runtime import progreso_ciclo
from autoclave.services.domain.logging.db_manager import DbManager
from autoclave.services.domain.logging.ticket_formatter import format_ticket
from autoclave.state_machine.states.ciclo import CicloResultado
from tests import test_e1_ensayo_simulador as e1
from tests.test_e1_ensayo_simulador import PROGRAMAS, programas  # noqa: F401
from tests.test_t11_programas_integracion import DT

RESULTADOS: dict[tuple[int, str], dict] = {}
_NO_ESTERIL = "CARGA NO ESTÉRIL"
_TOLERANCIA_COM02_S = 5.0     # ControlLoop._TOLERANCIA_DESCONEXION_SEG

# fase (estado.fase_ciclo) → atributo de la ventana (D8-2.12)
_VENTANAS = {
    "PRE_VACIO": "_hold_inicio",
    "CALENTAMIENTO": "_timer_sostenido_desde",
    "SECADO": "_timer_fin",
}


def _fase(a):
    c = a["ciclo"]
    return c._fases[c._fase_idx] if c._fase_idx < len(c._fases) else None


def _hasta_pendiente(a, limite_s=4 * 3600):
    for _ in range(int(limite_s / DT)):
        r = e1._tick(a)
        if r == CicloResultado.ESPERANDO_CONFIRMACION:
            return r
        e1._avanzar(a)
    raise AssertionError("el ciclo no terminó")


def _pie(texto: str) -> list[str]:
    lineas = [l.rstrip() for l in texto.split("\n")]
    i = max(k for k, l in enumerate(lineas) if l.startswith("Temp. final"))
    return [l for l in lineas[i:] if l]


def _evento_ventana(fase_objetivo):
    def evento(a):
        attr = _VENTANAS[fase_objetivo]
        # hasta que la ventana esté abierta (y lleve 1 s abierta)
        abierta = 0.0
        for _ in range(int(4 * 3600 / DT)):
            if e1._tick(a) == CicloResultado.ESPERANDO_CONFIRMACION:
                # el programa no abre esa ventana (Líquidos: sin pulsos con
                # hold ni secado): la celda no aplica
                return {"fase_final": a["estado"].fase_ciclo, "ventana_no_aplica": True}
            f = _fase(a)
            if (a["estado"].fase_ciclo == fase_objetivo
                    and getattr(f, attr, None) is not None):
                abierta += DT
                if abierta >= 1.0:
                    break
            e1._avanzar(a)
        else:
            raise AssertionError(f"no se abrió la ventana de {fase_objetivo}")
        f = _fase(a)
        registro = {}
        original = f.pausar_ventanas_estabilidad

        def espia(segundos):
            antes = getattr(f, attr, None)
            original(segundos)
            registro.update(segundos=segundos, antes=antes, despues=getattr(f, attr, None))
        f.pausar_ventanas_estabilidad = espia
        e1._avanzar(a)
        # 3 s de DI vencida (PARO_EMERGENCIA sin PARO_REAL)
        a["estado"].set_flag("PARO_EMERGENCIA", True)
        vapor = False
        for _ in range(int(3.0 / DT)):
            assert e1._tick(a) == CicloResultado.EN_CURSO
            vapor |= bool(a["modulo_es"].on("vapor_camara"))
            e1._avanzar(a)
        a["estado"].set_flag("PARO_EMERGENCIA", False)
        _hasta_pendiente(a)
        en_vivo = e1._ticket(a)
        db = a["db"]
        ciclo_id = db._conn.execute("SELECT max(id) FROM ciclos").fetchone()[0]
        fila = db.get_ciclo(ciclo_id)
        reimpreso = format_ticket(dict(fila), [dict(l) for l in db.get_lecturas_para_imprimir(ciclo_id)])
        corrimiento = (None if registro.get("antes") is None or registro.get("despues") is None
                       else round(registro["despues"] - registro["antes"], 2))
        fase_final = a["estado"].fase_ciclo
        return {"fase_final": fase_final,
                "pausa_s": round(registro.get("segundos") or 0.0, 2),
                "ventana_corrida_s": corrimiento,
                "vapor_durante_tolerancia": vapor,
                "sin_datos_ticket": e1._linea(en_vivo, "Sin datos de la tarjeta:"),
                "pie_reimpreso_identico": _pie(reimpreso) == _pie(en_vivo),
                "no_esteril_pantalla": progreso_ciclo.resultado(fase_final) != "exitoso",
                "no_esteril_en_ticket": _NO_ESTERIL in en_vivo}
    return evento


def _desconexion(a, segundos, cancelar):
    """El módulo E/S se cae `segundos` en ESTERILIZACION: el ControlLoop no corre
    la máquina de estados; si vence la tolerancia llama abortar_por_desconexion.
    `cancelar`: /cycle/abort aceptado en espera (D8-2.13) a mitad del tramo."""
    e1._hasta_fase(a, "ESTERILIZACION", extra_s=60)
    e1._avanzar(a)
    t0 = a["reloj"][0]
    abortado = False
    while a["reloj"][0] - t0 < segundos:
        if cancelar and a["reloj"][0] - t0 >= 1.0:
            a["estado"].set_flag("CICLO_CANCELADO", True)
        if a["reloj"][0] - t0 >= _TOLERANCIA_COM02_S and not abortado:
            a["ciclo"].abortar_por_desconexion(segundos=a["reloj"][0] - t0)
            abortado = True
        e1._avanzar(a)
    _hasta_pendiente(a)
    for _ in range(int(60 / DT)):
        e1._tick(a)
        e1._avanzar(a)
    fase_final = a["estado"].fase_ciclo
    ticket = e1._ticket(a)
    return {"fase_final": fase_final, "abortado_por_com02": abortado,
            "no_esteril_pantalla": progreso_ciclo.resultado(fase_final) != "exitoso",
            "no_esteril_en_ticket": _NO_ESTERIL in ticket}


def _evento_abort_en_desconexion(a):
    return _desconexion(a, 3.0, cancelar=True)


def _evento_desconexion_vence(a):
    return _desconexion(a, 6.0, cancelar=False)


def _evento_completo(a):
    _hasta_pendiente(a)
    fase_final = a["estado"].fase_ciclo
    return {"fase_final": fase_final,
            "no_esteril_pantalla": progreso_ciclo.resultado(fase_final) != "exitoso",
            "no_esteril_en_ticket": _NO_ESTERIL in e1._ticket(a)}


_EVENTOS = {
    **{f"d8_2_12_ventana_{f.lower()}": _evento_ventana(f) for f in _VENTANAS},
    "d8_2_13_abort_en_desconexion": _evento_abort_en_desconexion,
    "d8_2_13_desconexion_vence_com02": _evento_desconexion_vence,
    "d8_2_16_completo": _evento_completo,
}


@pytest.mark.parametrize("numero", sorted(PROGRAMAS))
@pytest.mark.parametrize("evento", list(_EVENTOS))
def test_ensayo_s2b(programas, monkeypatch, tmp_path, numero, evento):  # noqa: F811
    db = DbManager(tmp_path / "ensayo.db") if evento.startswith("d8_2_12") else None
    a = e1._armar(programas[numero], monkeypatch, tmp_path, db=db)
    a["db"] = db
    try:
        r = _EVENTOS[evento](a)
    finally:
        if db is not None:
            db.close()
    RESULTADOS[(numero, evento)] = r
    if evento.startswith("d8_2_12") and r.get("ventana_no_aplica"):
        assert numero == 4 and r["fase_final"] == "COMPLETADO", r
    elif evento.startswith("d8_2_12"):
        assert r["fase_final"] == "COMPLETADO", r
        assert r["vapor_durante_tolerancia"] is False, r
        assert r["pausa_s"] >= 3.0 - DT, r
        assert r["ventana_corrida_s"] == r["pausa_s"], r
        assert r["sin_datos_ticket"] == "Sin datos de la tarjeta: 3 s", r
        assert r["pie_reimpreso_identico"] is True, r
        assert r["no_esteril_pantalla"] is False and r["no_esteril_en_ticket"] is False, r
    elif evento == "d8_2_13_abort_en_desconexion":
        assert r["fase_final"] == "CANCELADO" and r["abortado_por_com02"] is False, r
        assert r["no_esteril_pantalla"] is True and r["no_esteril_en_ticket"] is True, r
    elif evento == "d8_2_13_desconexion_vence_com02":
        assert r["fase_final"] == "FALLO_CONEXION" and r["abortado_por_com02"] is True, r
        assert r["no_esteril_pantalla"] is True and r["no_esteril_en_ticket"] is True, r
    else:
        assert r["fase_final"] == "COMPLETADO", r
        assert r["no_esteril_pantalla"] is False and r["no_esteril_en_ticket"] is False, r


def test_escribir_informe_s2b():
    if os.environ.get("S2B_ESCRIBIR_INFORME") != "1":
        pytest.skip("solo con S2B_ESCRIBIR_INFORME=1")
    filas = ["| Programa | Evento | Resultado |", "|---|---|---|"]
    for numero in sorted(PROGRAMAS):
        for evento in _EVENTOS:
            r = RESULTADOS.get((numero, evento))
            if r is not None:
                datos = ", ".join(f"{k}={v}" for k, v in r.items())
                filas.append(f"| {numero} {PROGRAMAS[numero]} | {evento} | {datos} |")
    destino = Path("docs/informes/tanda8/S2b_ensayo_tabla.md")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(filas) + "\n", encoding="utf-8")

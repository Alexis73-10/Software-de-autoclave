"""T2 / P-9 (tanda 6): el ticket de un ciclo INTERRUMPIDO se reimprime desde el
Historial con la marca "CARGA NO ESTÉRIL" (en el idioma vigente); el resto de
resultados no la lleva."""

from autoclave.services.domain.logging import ticket_formatter as tf
from autoclave.state_machine.machine.enum_global import GlobalState
from tests.test_backend_cycle_summary import _crear, cliente, db, estado_maquina  # noqa: F401

_ATM = 101.3


def _fila(resultado, motivo=None):
    return {"numero_ciclo": 7, "serie": "S", "modelo": "M", "version_sw": "1",
            "nombre_ciclo": "Instrumental 134", "tipo_ciclo": "instrumental_134",
            "temp_esterilizacion": 134, "tiempo_esterilizacion": 4,
            "fecha_inicio": "2026-10-20T08:00:00", "fecha_fin": "2026-10-20T09:00:00",
            "resultado": resultado, "motivo_fallo": motivo, "codigo_fallo": None,
            "operador": "ana"}


def test_ticket_interrumpido_lleva_la_marca_carga_no_esteril():
    t = tf.format_ticket(_fila("INTERRUMPIDO", "Ciclo interrumpido"), [])
    assert "Estado: INTERRUMPIDO" in t
    assert "CARGA NO ESTÉRIL" in t
    t.encode("cp437")                                   # imprimible en la térmica


def test_ticket_interrumpido_en_ingles():
    tf.fijar_proveedor(lambda: tf.Presentacion("en", "C", "kPa", _ATM))
    try:
        t = tf.format_ticket(_fila("INTERRUMPIDO"), [])
    finally:
        tf.fijar_proveedor(None)
    assert "INTERRUPTED" in t and "LOAD NOT STERILE" in t


def test_otros_resultados_no_llevan_la_marca():
    for r in ("COMPLETADO", "CANCELADO", "FALLO_CALENTAMIENTO"):
        assert "NO ESTÉRIL" not in tf.format_ticket(_fila(r), [])


def test_reimpresion_desde_historial_de_un_interrumpido(cliente, db, estado_maquina):  # noqa: F811
    cid = _crear(db)
    db.cerrar_ciclos_interrumpidos("Ciclo interrumpido: la carga NO está estéril.")
    assert db.get_ciclo(cid)["resultado"] == "INTERRUMPIDO"
    estado_maquina.estado.get_machine_state.return_value = GlobalState.PREPARACION
    r = cliente.post("/cycle/history/print", json={"ids": [cid]})
    assert r.status_code == 200 and r.json()["impresos"] == 1
    ticket = estado_maquina.realtime_printer.enqueue.call_args.args[0]
    assert "INTERRUMPIDO" in ticket and "CARGA NO ESTÉRIL" in ticket

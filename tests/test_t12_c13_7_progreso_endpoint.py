# Tanda 12 (C-13.7): GET /cycle/current/progress usa el tiempo restante de
# exposición que publica ESTERILIZACION (estado.exposicion_restante_s), así
# la pantalla refleja el reinicio del conteo tras una excursión de Referencia.

from test_backend_ciclo_en_curso_endpoints import _crear_ciclo, entorno  # noqa: F401


def _en_esterilizacion(ctx, db):
    _crear_ciclo(db, "COMPLETADO", [("PRE_VACIO", 600.0), ("CALENTAMIENTO", 180.0),
                                    ("ESTERILIZACION", 420.0), ("DESCOMPRESION", 120.0),
                                    ("SECADO", 900.0)])
    cid = _crear_ciclo(db, None, [("PRE_VACIO", 600.0), ("CALENTAMIENTO", 180.0),
                                  ("ESTERILIZACION", None)])
    ctx.estado.fase_ciclo = "ESTERILIZACION"
    ctx.cycle_logger.ciclo_id_pantalla = cid
    ctx.cycle_logger.transcurrido_s.return_value = 880.0   # 100 s de exposición


def test_restante_usa_exposicion_publicada_por_la_fase(entorno):  # noqa: F811
    client, ctx, db = entorno
    _en_esterilizacion(ctx, db)
    ctx.estado.exposicion_restante_s = 420.0     # conteo reiniciado desde cero
    body = client.get("/cycle/current/progress").json()
    assert body["fase_activa"] == "esterilizacion"
    assert body["restante_s"] == 420.0 + 120.0 + 900.0


def test_sin_dato_de_la_fase_usa_el_historial(entorno):  # noqa: F811
    client, ctx, db = entorno
    _en_esterilizacion(ctx, db)
    ctx.estado.exposicion_restante_s = None
    body = client.get("/cycle/current/progress").json()
    assert body["restante_s"] == (420.0 - 100.0) + 120.0 + 900.0

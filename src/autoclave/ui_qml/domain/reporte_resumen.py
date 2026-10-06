# ui_qml/domain/reporte_resumen.py
#
# Formateo del resumen de ciclos por periodo (GET /report/summary) para la
# pantalla Reportes. Frontera de confianza como resumen_sistema.py: un dato
# ausente o mal formado cuenta como 0 y no tumba el resto.

from autoclave.ui_qml.domain.resumen_sistema import formatear_numero_programa, SIN_DATO

CLAVES = ("completados", "fallos", "cancelados", "sin_cierre")


def _entero(valor) -> int:
    return valor if isinstance(valor, int) and not isinstance(valor, bool) and valor > 0 else 0


def _porcentaje(n: int, total: int) -> str:
    return f"{round(100 * n / total)}%" if total else "0%"


def presentable(respuesta) -> dict:
    r = respuesta if isinstance(respuesta, dict) else {}
    t = r.get("totales") if isinstance(r.get("totales"), dict) else {}
    total = _entero(t.get("total"))
    programas = r.get("por_programa") if isinstance(r.get("por_programa"), list) else []
    causas = r.get("causas_fallo") if isinstance(r.get("causas_fallo"), list) else []

    def programa(p: dict) -> str:
        nombre = p.get("programa_nombre") if isinstance(p.get("programa_nombre"), str) else ""
        numero = formatear_numero_programa(p.get("programa_numero"))
        partes = [x for x in (numero if numero != SIN_DATO else "", nombre) if x]
        return " · ".join(partes) or SIN_DATO

    return {
        "total": str(total),
        "totales": [{"clave": c, "cantidad": str(_entero(t.get(c))),
                     "porcentaje": _porcentaje(_entero(t.get(c)), total),
                     "fraccion": _entero(t.get(c)) / total if total else 0.0} for c in CLAVES],
        "por_programa": [{"programa": programa(p), "total": str(_entero(p.get("total"))),
                          **{c: str(_entero(p.get(c))) for c in CLAVES}}
                         for p in programas if isinstance(p, dict)],
        "causas": [{"causa": c["causa"], "cantidad": str(_entero(c.get("cantidad")))}
                   for c in causas if isinstance(c, dict) and isinstance(c.get("causa"), str)],
    }

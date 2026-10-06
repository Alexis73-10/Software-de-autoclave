# ui_qml/exportacion/textos.py
#
# Rótulos de los PDF de ciclos (pdf_ciclo.dibujar_ciclo) tomados de es.json, en
# un módulo sin Qt para que los usen el puente y los generadores de PDF.


def textos_ciclo(textos: dict) -> dict:
    """{"fases", "series", "consignas", "eje_tiempo", "eje_temp", "eje_pres",
    "sin_grafica", "ticket"} desde es.json completo."""
    ciclo = textos.get("ciclo") or {}
    exportacion = textos.get("exportacion") or {}
    return {
        "fases": textos.get("fases") or {},
        "series": {"temp_camara": ciclo.get("serie_temp_camara", ""),
                   "temp_ref": ciclo.get("serie_temp_ref", ""),
                   "pres_camara": ciclo.get("serie_presion", "")},
        "consignas": {"temp": exportacion.get("consigna_temp", ""),
                      "pres": exportacion.get("consigna_pres", "")},
        **{k: exportacion.get(k, "")
           for k in ("eje_tiempo", "eje_temp", "eje_pres", "sin_grafica", "ticket")},
    }

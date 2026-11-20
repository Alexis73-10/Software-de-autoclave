# ui_qml/domain/registro_carga.py
#
# Registro de la carga con lector (RCB, 19-nov). Lógica y textos de la
# interfaz, sin Qt (el QML solo dibuja):
# - sección «Carga del ciclo» del PDF, del correo y del detalle del ciclo
#   (RCB-07.1/07.2), con el aviso de carga no estéril si el ciclo no terminó
#   COMPLETADO (HAZ-RCB-02);
# - borrador de la ventana «Carga del ciclo» de Preciclo (RCB-02, RCB-09).
# Las reglas de validación son las del backend (core/runtime/registro_carga).

from autoclave.core.runtime import registro_carga as rc

RESULTADO_COMPLETADO = "COMPLETADO"


def _t_defecto(clave, **params):
    from autoclave import i18n
    return i18n.t(clave, **params)


def carga_no_esteril(carga, resultado) -> bool:
    """RCB-D9 / HAZ-RCB-02: una carga de un ciclo que no terminó COMPLETADO
    (falló, se canceló, se interrumpió o sin resultado) no está estéril.
    Igualdad exacta, como el pie del ticket (SAF-05 de Q1)."""
    return bool(isinstance(carga, dict) and carga.get("lote")) and \
        str(resultado or "") != RESULTADO_COMPLETADO


def _observacion(e: dict, t) -> str:
    marcas = []
    if e.get("manual"):
        marcas.append(t("exportacion.carga_obs_manual"))
    if not e.get("en_catalogo") or not e.get("nombre"):
        marcas.append(t("exportacion.carga_obs_sin_catalogo"))
    return " · ".join(marcas)


def seccion_carga(carga, resultado, operador=None, t=_t_defecto) -> dict | None:
    """RCB-07.1/07.2: datos ya formateados de la sección «Carga del ciclo»
    (lista completa, sin importar el modo de impresión): {"titulo", "resumen",
    "columnas": [4], "filas": [[cant, elemento, código, observación]], "nota",
    "no_esteril": texto o ""}. None si el ciclo no tiene carga. Nunca lanza."""
    try:
        if not isinstance(carga, dict) or not carga.get("lote"):
            return None
        elementos = [e for e in carga.get("elementos") or [] if isinstance(e, dict)]
        unidades = sum(int(e.get("cantidad") or 0) for e in elementos)
        resumen = t("exportacion.carga_resumen", lote=carga["lote"], codigos=len(elementos),
                    unidades=unidades)
        if isinstance(operador, str) and operador.strip():
            resumen += " · " + t("exportacion.carga_operador", operador=operador.strip())
        filas = [[str(int(e.get("cantidad") or 0)),
                  e.get("nombre") if e.get("nombre") else str(e.get("codigo") or ""),
                  str(e.get("codigo") or ""), _observacion(e, t)] for e in elementos]
        return {
            "titulo": t("exportacion.carga_titulo"),
            "resumen": resumen,
            "columnas": [t("exportacion.carga_col_cantidad"), t("exportacion.carga_col_elemento"),
                         t("exportacion.carga_col_codigo"), t("exportacion.carga_col_observacion")],
            "filas": filas,
            "nota": t("exportacion.carga_nota"),
            "no_esteril": (t("exportacion.carga_no_esteril")
                           if carga_no_esteril(carga, resultado) else ""),
        }
    except Exception:
        return None


def lineas_cuerpo_correo(ciclos, t=_t_defecto) -> list[str]:
    """RCB-07.1: una línea por ciclo con carga en el cuerpo del correo (lote,
    códigos y unidades; la lista completa va en el PDF adjunto) y, si no
    terminó COMPLETADO, el aviso de carga no estéril."""
    lineas = []
    for c in ciclos or []:
        carga = c.get("carga") if isinstance(c, dict) else None
        if not isinstance(carga, dict) or not carga.get("lote"):
            continue
        elementos = [e for e in carga.get("elementos") or [] if isinstance(e, dict)]
        numero = c.get("numero_ciclo")
        numero = f"{numero:06d}" if isinstance(numero, int) else str(numero or "")
        linea = t("exportacion.cuerpo_carga", numero=numero, lote=carga["lote"],
                  codigos=len(elementos),
                  unidades=sum(int(e.get("cantidad") or 0) for e in elementos))
        if carga_no_esteril(carga, c.get("resultado")):
            linea += " " + t("exportacion.cuerpo_carga_no_esteril")
        lineas.append(linea)
    return lineas

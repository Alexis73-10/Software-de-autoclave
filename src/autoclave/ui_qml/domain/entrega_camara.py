# ui_qml/domain/entrega_camara.py
#
# ENT-09 (tanda 31, planeacion_entrega_camara_fin_ciclo.md): lo que la pantalla
# de ciclo en curso muestra mientras la cámara no esté entregada. Parte de
# `entrega` de GET /cycle/current/progress:
#   {entregada, motivos, motivos_detalle: [{motivo_codigo, motivo_valores,
#    motivo_textos}], espera_restante_s, forzable}
# y arma el texto del indicador en el idioma pedido. Módulo puro (sin Qt).
#
# Falla cerrada: con resultado y sin `entrega` (o mal formada) la cámara NO está
# entregada y no es forzable (la confirmación forzada solo se ofrece cuando el
# backend la declara). Los textos de cada motivo vienen armados por el backend
# en las unidades vigentes (`motivo_textos`, como NO ABRIR).

from autoclave import i18n


def _entero(v):
    return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else None


def normalizar_entrega(respuesta, resultado) -> dict:
    """`entrega` validada. Sin resultado no hay nada que entregar (todo vacío)."""
    vacio = {"entregada": False, "forzable": False, "espera_restante_s": None,
             "motivos": [], "detalle": []}
    if resultado is None:
        return vacio
    if not isinstance(respuesta, dict):
        return vacio
    motivos = respuesta.get("motivos")
    motivos = [m for m in motivos if isinstance(m, str)] if isinstance(motivos, list) else []
    detalle = []
    crudo = respuesta.get("motivos_detalle")
    for d in crudo if isinstance(crudo, list) else []:
        textos = d.get("motivo_textos") if isinstance(d, dict) else None
        detalle.append({k: v for k, v in textos.items() if isinstance(k, str) and isinstance(v, str)}
                       if isinstance(textos, dict) else {})
    return {"entregada": respuesta.get("entregada") is True,
            "forzable": respuesta.get("forzable") is True,
            "espera_restante_s": _entero(respuesta.get("espera_restante_s")),
            "motivos": motivos, "detalle": detalle}


def _mss(segundos: int) -> str:
    return f"{segundos // 60}:{segundos % 60:02d}"


def _motivo(entrega: dict, idioma: str) -> str:
    partes = []
    for i, texto_base in enumerate(entrega["motivos"]):
        textos = entrega["detalle"][i] if i < len(entrega["detalle"]) else {}
        partes.append(textos.get(idioma) or texto_base)
    return "; ".join(p for p in partes if p)


def _t(clave: str, idioma: str, **params) -> str:
    try:
        return i18n.t(clave, idioma, **params)
    except Exception:
        return ""


def texto_entrega(entrega: dict, idioma: str) -> str:
    """Texto del indicador: la espera fija de COMPLETADO («Esperando condiciones
    de apertura: m:ss»), si no el motivo vigente («Esperando cámara segura:
    {motivo}») y, sin motivo, «Esperando cámara segura»."""
    espera = entrega.get("espera_restante_s")
    if espera is not None:
        return _t("ciclo.entrega_espera", idioma, tiempo=_mss(espera))
    motivo = _motivo(entrega, idioma)
    if motivo:
        return _t("ciclo.entrega_motivo", idioma, motivo=motivo)
    return _t("ciclo.entrega_sin_motivo", idioma)


def texto_rechazo(clave: str, cuerpo, idioma: str) -> str:
    """Texto de un rechazo de POST /cycle/acknowledge: el de `clave` y, si el
    cuerpo trae el motivo (409 camara_no_entregada), el motivo en `idioma`."""
    base = _t(clave, idioma)
    cuerpo = cuerpo if isinstance(cuerpo, dict) else {}
    textos = cuerpo.get("motivo_textos")
    motivo = textos.get(idioma) if isinstance(textos, dict) else None
    if not isinstance(motivo, str) or not motivo:
        motivo = cuerpo.get("detail") if isinstance(cuerpo.get("detail"), str) else ""
    return f"{base}\n{motivo}" if base and motivo else base

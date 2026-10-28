# ui_qml/domain/fin_de_ciclo.py
#
# FC-01..FC-03, FC-07 y FC-09 (tanda 21, planeacion_fin_de_ciclo.md): textos
# del panel de fin de ciclo y de las notas del modal de CONFIRMAR a partir de
# `terminacion` y `alarmas_ciclo` de GET /cycle/current/progress (FC-13), en el
# idioma pedido. Módulo puro (sin Qt): los textos de alarma salen de
# core/runtime/alarmas_i18n con el código y los parámetros, igual que el
# historial; los rótulos fijos, de i18n (ciclo.fin_*).
#
# Falla cerrada: una terminación desconocida o mal formada se presenta como
# fallo, y la fila de causa nunca queda vacía (FC-02).

from autoclave import i18n
from autoclave.core.runtime import alarmas_i18n
from autoclave.core.runtime.progreso_ciclo import FASES_UI

TIPOS = ("fallo", "emergencia", "cancelado", "exitoso")

# Nivel guardado en alarmas_historial (Nivel.name del catálogo) -> prioridad de
# la UI (mismos colores que FilaAlarma: EMERGENCIA alta, FALLA media, ALERTA
# baja). Desconocido -> "alta" (ante la duda, lo más llamativo).
_PRIORIDAD_POR_NIVEL = {
    "FALLO_CRITICO": "alta",
    "ALARMA": "media",
    "AVISO": "baja",
    "INFORMATIVO": "baja",
}


def prioridad(nivel) -> str:
    return _PRIORIDAD_POR_NIVEL.get(nivel, "alta")


def _texto(valor) -> str:
    return valor if isinstance(valor, str) else ""


def _hms(iso) -> str:
    """"HH:MM:SS" de un ISO de pared ("2026-10-28T13:21:07"); "" si no se puede."""
    iso = _texto(iso)
    if "T" in iso:
        hora = iso.split("T", 1)[1]
    elif " " in iso:
        hora = iso.split(" ", 1)[1]
    else:
        return ""
    hora = hora[:8]
    return hora if len(hora) == 8 and hora[2] == ":" and hora[5] == ":" else ""


def _fecha(iso, idioma) -> str:
    """"28-oct-2026" de un ISO de pared; "" si no se puede."""
    iso = _texto(iso)
    try:
        anio, mes, dia = iso[:10].split("-")
        meses = i18n.valor("fecha.meses", idioma) or []
        nombre = meses[int(mes) - 1].lower() if 0 < int(mes) <= len(meses) else mes
        return f"{int(dia):02d}-{nombre}-{int(anio)}"
    except Exception:
        return ""


def _fase(fase, idioma) -> str:
    """Nombre de la fase de la UI; "—" si no se sabe."""
    if fase in FASES_UI:
        return i18n.t(f"fases.{fase}", idioma)
    return i18n.t("sistema.sin_lectura", idioma)


def _textos_alarma(codigo, valores, idioma, titulo_guardado="", descripcion_guardada=""):
    """{titulo, descripcion, accion} de una alarma del catálogo en `idioma`;
    sin código conocido, lo guardado (nunca vacío el título)."""
    from autoclave.state_machine.alarms.catalogo import CATALOGO
    definicion = CATALOGO.get(codigo or "")
    if definicion is None:
        return {"titulo": titulo_guardado or (codigo or ""),
                "descripcion": descripcion_guardada, "accion": ""}
    t = alarmas_i18n.textos(definicion, valores if isinstance(valores, dict) else {}, idioma)
    if not (valores if isinstance(valores, dict) else {}) and descripcion_guardada and idioma == "es":
        t = dict(t, descripcion=descripcion_guardada)
    return t


def normalizar_terminacion(valor, resultado) -> dict | None:
    """`terminacion` validada (frontera de confianza). None si el ciclo no
    terminó. Mal formada con el ciclo terminado: tipo "fallo" (FC-13)."""
    if resultado is None:
        return None
    t = valor if isinstance(valor, dict) else {}
    tipo = t.get("tipo") if t.get("tipo") in TIPOS else "fallo"
    # el resultado manda sobre un tipo incoherente: nunca se presenta como
    # exitoso un ciclo que el backend no dio por COMPLETADO
    if tipo == "exitoso" and resultado != "exitoso":
        tipo = "fallo"
    if resultado == "exitoso" and tipo != "exitoso":
        tipo = "fallo"
    valores = t.get("valores")
    obs = []
    for o in t.get("observaciones") if isinstance(t.get("observaciones"), list) else []:
        if isinstance(o, dict) and isinstance(o.get("sensor"), str) and o["sensor"]:
            obs.append({"sensor": o["sensor"], "hora": _texto(o.get("hora")),
                        "fase": o.get("fase") if o.get("fase") in FASES_UI else None})
    return {
        "tipo": tipo,
        "codigo": t.get("codigo") if isinstance(t.get("codigo"), str) and t.get("codigo") else None,
        "valores": valores if isinstance(valores, dict) else {},
        "motivo": _texto(t.get("motivo")),
        "fase": t.get("fase") if t.get("fase") in FASES_UI else None,
        "hora_fin": _texto(t.get("hora_fin")),
        "cancelado_por": _texto(t.get("cancelado_por")),
        "observaciones": obs,
    }


def normalizar_alarmas(valor) -> list[dict]:
    """`alarmas_ciclo` validada: lista de dicts con código; lo demás se descarta."""
    salida = []
    for a in valor if isinstance(valor, list) else []:
        if not isinstance(a, dict) or not isinstance(a.get("codigo"), str) or not a["codigo"]:
            continue
        salida.append({
            "codigo": a["codigo"],
            "nivel": _texto(a.get("nivel")),
            "titulo": _texto(a.get("titulo")),
            "descripcion": _texto(a.get("descripcion")),
            "valores": a.get("valores") if isinstance(a.get("valores"), dict) else {},
            "aparecida": _texto(a.get("aparecida")),
            "resuelta": _texto(a.get("resuelta")),
        })
    return salida


def _causa(term: dict, idioma: str) -> dict:
    """Fila de causa (FC-02); {} en un ciclo exitoso."""
    tipo = term["tipo"]
    fase = _fase(term["fase"], idioma)
    hora = _hms(term["hora_fin"])
    fecha = " ".join(p for p in (_fecha(term["hora_fin"], idioma), hora) if p)
    if tipo == "exitoso":
        return {}
    if tipo == "cancelado":
        usuario = term["cancelado_por"]
        sub = (i18n.t("ciclo.fin_causa_cancelado_sub_usuario", idioma, usuario=usuario, fase=fase)
               if usuario else i18n.t("ciclo.fin_causa_cancelado_sub", idioma, fase=fase))
        return {"titulo": i18n.t("ciclo.fin_causa_cancelado", idioma), "subtitulo": sub,
                "hora": hora, "descripcion": "",
                "queHacer": i18n.t("ciclo.fin_causa_cancelado_accion", idioma),
                "meta": i18n.t("ciclo.fin_meta_causa_sin_codigo", idioma, fase=fase, fecha=fecha),
                "nivel": "cancelado"}
    if tipo == "emergencia":
        codigo = term["codigo"] or "SIS-01"
        t = _textos_alarma(codigo, term["valores"], idioma)
        return {"titulo": i18n.t("ciclo.fin_causa_emergencia", idioma),
                "subtitulo": i18n.t("ciclo.fin_causa_emergencia_sub", idioma, fase=fase),
                "hora": hora, "descripcion": t.get("descripcion", ""),
                "queHacer": i18n.t("ciclo.fin_causa_emergencia_accion", idioma),
                "meta": i18n.t("ciclo.fin_meta_causa", idioma, fase=fase, fecha=fecha, codigo=codigo),
                "nivel": "fallo"}
    # fallo
    codigo = term["codigo"]
    from autoclave.state_machine.alarms.catalogo import CATALOGO
    if codigo is None or CATALOGO.get(codigo) is None:
        # FC-02: fallo sin código conocido: título genérico y el motivo crudo
        detalle = term["motivo"] or (codigo or "")
        meta = (i18n.t("ciclo.fin_meta_causa", idioma, fase=fase, fecha=fecha, codigo=codigo)
                if codigo else i18n.t("ciclo.fin_meta_causa_sin_codigo", idioma, fase=fase, fecha=fecha))
        return {"titulo": i18n.t("ciclo.fin_causa_generica", idioma), "subtitulo": "",
                "hora": hora, "descripcion": detalle, "queHacer": "", "meta": meta,
                "nivel": "fallo"}
    t = _textos_alarma(codigo, term["valores"], idioma)
    # DECISIÓN SIN CONFIRMAR: la descripción es la de la plantilla con los
    # valores (sin el prefijo "CÓDIGO · título:" de motivo_fallo, que ya están
    # en el subtítulo y en la línea meta); sin valores, el motivo registrado.
    descripcion = t.get("descripcion", "") if term["valores"] else (
        alarmas_i18n.motivo_fallo(codigo, term["valores"], term["motivo"], idioma) or "")
    titulo = (i18n.t("ciclo.fin_causa_fallo_fase", idioma, fase=fase.lower())
              if term["fase"] else i18n.t("ciclo.fin_causa_generica", idioma))
    return {"titulo": titulo, "subtitulo": t.get("titulo", ""), "hora": hora,
            "descripcion": descripcion, "queHacer": t.get("accion", ""),
            "meta": i18n.t("ciclo.fin_meta_causa", idioma, fase=fase, fecha=fecha, codigo=codigo),
            "nivel": "fallo"}


def _fila_alarma(a: dict, idioma: str) -> dict:
    """Fila de una alarma del ciclo (FC-03)."""
    t = _textos_alarma(a["codigo"], a["valores"], idioma, a["titulo"], a["descripcion"])
    hora = _hms(a["aparecida"])
    resuelta = _hms(a["resuelta"])
    meta = (i18n.t("ciclo.fin_meta_alarma_resuelta", idioma, hora=hora, codigo=a["codigo"],
                   resuelta=resuelta)
            if a["resuelta"] else
            i18n.t("ciclo.fin_meta_alarma_activa", idioma, hora=hora, codigo=a["codigo"]))
    return {"titulo": t.get("titulo") or a["codigo"], "hora": hora,
            "nivel": prioridad(a["nivel"]), "descripcion": t.get("descripcion", ""),
            "queHacer": t.get("accion", ""), "meta": meta}


def _fila_observacion(o: dict, idioma: str) -> dict:
    """Fila de una observación de Referencia sin su fila SEN-11 (SAF-04)."""
    fase = _fase(o["fase"], idioma)
    t = _textos_alarma("SEN-11", {"sensor": o["sensor"], "fase": fase}, idioma)
    return {"titulo": t.get("titulo") or "SEN-11", "hora": o["hora"], "nivel": prioridad("AVISO"),
            "descripcion": t.get("descripcion", ""), "queHacer": t.get("accion", ""),
            "meta": i18n.t("ciclo.fin_meta_alarma_activa", idioma, hora=o["hora"], codigo="SEN-11")}


def nota_observaciones(term: dict | None, idioma: str) -> str:
    """Nota ámbar del modal de CONFIRMAR exitoso (FC-07/FC-09): una línea por
    Referencia sin lectura, con la hora y la fase; "" sin observaciones."""
    if not term:
        return ""
    lineas = [i18n.t("ciclo.modal_nota_observacion", idioma, sensor=o["sensor"],
                     hora=o["hora"] or i18n.t("sistema.sin_lectura", idioma),
                     fase=_fase(o["fase"], idioma))
              for o in term["observaciones"]]
    return "\n".join(lineas)


def armar(term: dict | None, alarmas: list, idioma: str) -> dict:
    """Datos del panel de fin de ciclo para QML.

    {modo, horaFin ("HH:MM"), causa, alarmas, cantidad, notaObservaciones}
    modo: "" (sin terminar, o exitoso sin alarmas), "fallo", "cancelado",
    "emergencia" u "observaciones" (exitoso con alarmas o avisos, FC-07)."""
    vacio = {"modo": "", "horaFin": "", "causa": {}, "alarmas": [], "cantidad": 0,
             "notaObservaciones": ""}
    if term is None:
        return vacio
    filas = []
    for a in alarmas:
        try:
            filas.append(_fila_alarma(a, idioma))
        except Exception:
            filas.append({"titulo": a.get("titulo") or a.get("codigo") or "", "hora": "",
                          "nivel": "alta", "descripcion": a.get("descripcion", ""),
                          "queHacer": "", "meta": a.get("codigo") or ""})
    # Revisión R (tanda 21, SAF-04): una observación de Referencia sin su fila
    # SEN-11 en el historial (sin base de datos, o fila sin ciclo) se muestra
    # igual, armada con los datos de la terminación (no depende de la base)
    if term["observaciones"] and not any(a.get("codigo") == "SEN-11" for a in alarmas):
        for o in term["observaciones"]:
            filas.append(_fila_observacion(o, idioma))
    tipo = term["tipo"]
    if tipo == "exitoso":
        modo = "observaciones" if filas else ""
        causa = {}
    else:
        modo = tipo
        causa = _causa(term, idioma)
    return {
        "modo": modo,
        "horaFin": _hms(term["hora_fin"])[:5],
        "causa": causa,
        "alarmas": filas,
        "cantidad": (0 if tipo == "exitoso" else 1) + len(filas),
        "notaObservaciones": nota_observaciones(term, idioma),
    }

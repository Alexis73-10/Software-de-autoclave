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


# ── Borrador de la ventana «Carga del ciclo» (RCB-02, RCB-09) ──────────────

PASO_LOTE = "lote"
PASO_ELEMENTOS = "elementos"

AVISO_OK = "ok"
AVISO_ERROR = "error"


class BorradorCarga:
    """Carga en preparación en la pantalla de carga, solo en memoria (RCB-02.5:
    no se guarda en disco antes del inicio). Dos pasos (RCB-02.1): el primero
    acepta el lote (una lectura válida que no esté en el catálogo activo); el
    segundo, elementos (cada lectura suma 1, RCB-D5). Cada operación devuelve
    (tipo de aviso, clave i18n, parámetros) para que la UI lo muestre; una
    lectura rechazada no cambia nada."""

    def __init__(self):
        self.catalogo: dict[str, str] = {}
        self.lote: str = ""
        self.elementos: list[dict] = []     # {"codigo", "cantidad", "manual"} en orden de lectura
        self.ultimo: str = ""               # código de la última lectura aceptada

    # ── estado ────────────────────────────────────────────────────────────
    @property
    def paso(self) -> str:
        return PASO_ELEMENTOS if self.lote else PASO_LOTE

    def vacio(self) -> bool:
        return not self.lote and not self.elementos

    def total_unidades(self) -> int:
        return sum(e["cantidad"] for e in self.elementos)

    def nombre_de(self, codigo: str):
        return self.catalogo.get(codigo) if isinstance(self.catalogo, dict) else None

    def fijar_catalogo(self, elementos) -> None:
        """{codigo: nombre} de los activos, de GET /carga/catalogo?activos=true."""
        catalogo = {}
        for e in elementos or []:
            if isinstance(e, dict) and isinstance(e.get("codigo"), str) \
                    and isinstance(e.get("nombre"), str) and e.get("activo") is not False:
                catalogo[e["codigo"]] = e["nombre"]
        self.catalogo = catalogo

    # ── lecturas ──────────────────────────────────────────────────────────
    def leer(self, texto, manual: bool = False) -> tuple[str, str, dict]:
        codigo, motivo = rc.validar_codigo(texto)
        if motivo:
            return AVISO_ERROR, "registro_carga.aviso_lectura_invalida", {}
        if not self.lote:
            if self.nombre_de(codigo) is not None:
                return AVISO_ERROR, "registro_carga.aviso_es_elemento", {}
            self.lote = codigo
            self.ultimo = ""
            return AVISO_OK, "registro_carga.aviso_lote", {"codigo": codigo}
        if codigo == self.lote and self.nombre_de(codigo) is None:
            # DECISIÓN SIN CONFIRMAR: leer otra vez el lote no lo suma como elemento
            return AVISO_ERROR, "registro_carga.aviso_es_lote", {}
        existente = next((e for e in self.elementos if e["codigo"] == codigo), None)
        if existente is None:
            if len(self.elementos) >= rc.MAX_CODIGOS:
                return AVISO_ERROR, "registro_carga.aviso_max_codigos", {}
            existente = {"codigo": codigo, "cantidad": 0, "manual": False}
            self.elementos.append(existente)
        elif existente["cantidad"] >= rc.MAX_CANTIDAD:
            return AVISO_ERROR, "registro_carga.aviso_max_cantidad", {}
        existente["cantidad"] += 1
        existente["manual"] = existente["manual"] or bool(manual)
        self.ultimo = codigo
        nombre = self.nombre_de(codigo) or codigo
        return AVISO_OK, "registro_carga.aviso_elemento", {
            "nombre": f"{codigo} · {nombre} ({existente['cantidad']})" if nombre != codigo
            else f"{codigo} ({existente['cantidad']})"}

    def quitar_uno(self, codigo: str) -> None:
        """«−1»: con cantidad 1 la fila desaparece (RCB-02.3)."""
        for i, e in enumerate(self.elementos):
            if e["codigo"] == codigo:
                e["cantidad"] -= 1
                if e["cantidad"] <= 0:
                    del self.elementos[i]
                    if self.ultimo == codigo:
                        self.ultimo = ""
                return

    def cambiar_lote(self) -> None:
        """RCB-02.2: borra el lote y vuelve al paso 1 sin borrar los elementos."""
        self.lote = ""

    def vaciar(self) -> None:
        self.lote = ""
        self.elementos = []
        self.ultimo = ""

    # ── salida ────────────────────────────────────────────────────────────
    def para_inicio(self) -> dict | None:
        """Cuerpo `carga` de POST /cycle/start; None si no hay nada. Un
        borrador con elementos y sin lote se envía igual y el backend lo
        rechaza (422 carga_invalida): no se descarta en silencio."""
        if self.vacio():
            return None
        return {"lote": self.lote,
                "elementos": [{"codigo": e["codigo"], "cantidad": e["cantidad"],
                               "manual": e["manual"]} for e in self.elementos]}

    def filas(self) -> list[dict]:
        """Filas para la lista de la ventana (orden de lectura)."""
        return [{"codigo": e["codigo"], "nombre": self.nombre_de(e["codigo"]) or "",
                 "enCatalogo": self.nombre_de(e["codigo"]) is not None,
                 "cantidad": e["cantidad"], "manual": e["manual"],
                 "ultimo": e["codigo"] == self.ultimo} for e in self.elementos]


def resumen_boton(borrador: BorradorCarga, t=_t_defecto) -> str:
    """Texto del botón «Carga» de Preciclo (RCB-09.1)."""
    if borrador.vacio():
        return t("registro_carga.resumen_sin")
    if not borrador.lote:
        return t("registro_carga.sin_lote") + " · " + t(
            "registro_carga.total", codigos=len(borrador.elementos),
            unidades=borrador.total_unidades())
    return t("registro_carga.resumen", lote=borrador.lote, n=borrador.total_unidades())


def carga_requerida_falta(parametros_programa, borrador: BorradorCarga) -> bool:
    """RCB-09.1: el programa exige la carga y falta el lote o un elemento."""
    from autoclave.core.managers import catalogo_parametros as cp
    try:
        exige = cp.registro_carga_obligatorio(parametros_programa)
    except Exception:
        exige = False
    return bool(exige and not (borrador.lote and borrador.elementos))

# ui_qml/domain/resumen_sistema.py
#
# Formateo del Resumen del Sistema del Menú Principal a partir de la respuesta
# de GET /cycle/summary (planeacion_menu_principal_ui_qml.md §6.3).
#
# Frontera de confianza (como pantalla_ciclo.py): un dato ausente o mal formado
# se muestra como SIN_DATO y no tumba el resto. Fechas del backend en hora
# local sin zona (ciclos.fecha_inicio = datetime.now().isoformat()); se
# presentan con tabla propia (DD/MM/AAAA, HH:MM), sin configuración regional.

from datetime import date, datetime, timedelta

from autoclave.core.runtime import progreso_ciclo
from autoclave.utils import periodos

SIN_DATO = "—"

# ciclos.resultado guarda la fase_ciclo con que terminó el ciclo (COMPLETADO,
# CANCELADO, FALLO_ESTERILIZACION, FALLO_CONEXION, EMERGENCIA, ...). Se agrupa en
# tres claves con la misma regla del backend (progreso_ciclo.resultado).
_CLAVE_POR_RESULTADO = {"exitoso": "COMPLETADO", "cancelado": "CANCELADO", "fallo": "FALLO"}


def _entero(valor) -> int | None:
    if isinstance(valor, bool) or not isinstance(valor, int):
        return None
    return valor


def formatear_entero(valor) -> str:
    """Conteo sin separador de miles (1234567); negativo o no entero -> SIN_DATO."""
    v = _entero(valor)
    return SIN_DATO if v is None or v < 0 else str(v)


def _fecha_hora(iso) -> datetime | None:
    if not isinstance(iso, str) or not iso:
        return None
    try:
        return datetime.fromisoformat(iso)
    except ValueError:
        return None


def formatear_fecha(iso) -> str:
    """DD/MM/AAAA."""
    d = _fecha_hora(iso)
    return SIN_DATO if d is None else f"{d.day:02d}/{d.month:02d}/{d.year:04d}"


def formatear_hora(iso) -> str:
    """HH:MM, 24 h."""
    d = _fecha_hora(iso)
    return SIN_DATO if d is None else f"{d.hour:02d}:{d.minute:02d}"


def formatear_numero_programa(numero) -> str:
    """Número de programa con dos dígitos como mínimo (02), como el indicativo
    de la pantalla de preciclo (pantalla_ciclo.numero_de_ciclo)."""
    v = _entero(numero)
    return SIN_DATO if v is None or v < 1 else f"{v:02d}"


def clave_resultado(valor) -> str:
    """COMPLETADO, CANCELADO o FALLO (cualquier otro cierre); "" si no hay
    resultado (proceso interrumpido) o es una fase en curso. La pantalla traduce
    la clave con es.json y muestra SIN_DATO para ""."""
    if not isinstance(valor, str):
        return ""
    return _CLAVE_POR_RESULTADO.get(progreso_ciclo.resultado(valor), "")


def detalle_resultado(valor) -> str:
    """El cierre tal como se guardó (p. ej. FALLO_CALENTAMIENTO) cuando dice más
    que su clave; "" si coincide con ella o no hay resultado."""
    clave = clave_resultado(valor)
    return valor if clave and valor != clave else ""


from autoclave.ui_qml.domain.nombres_ciclo import nombre_programa  # noqa: E402


def ciclo_presentable(ciclo) -> dict:
    """Textos de un ciclo (forma de /cycle/summary -> ultimo_ciclo y de cada
    fila de /cycle/list), listos para QML. id = -1 si no es válido."""
    u = ciclo if isinstance(ciclo, dict) else {}
    nombre = u.get("programa_nombre")
    operador = u.get("operador")
    ident = _entero(u.get("id"))
    return {
        "id": ident if ident is not None else -1,
        "numero": formatear_entero(u.get("numero_ciclo")),
        "fecha": formatear_fecha(u.get("fecha_inicio")),
        "hora": formatear_hora(u.get("fecha_inicio")),
        "programa": formatear_numero_programa(u.get("programa_numero")),
        # I4 (tanda 6): un ciclo de fábrica sin renombrar se ve en el idioma vigente
        "programa_nombre": nombre_programa(nombre) if isinstance(nombre, str) and nombre else SIN_DATO,
        "resultado": clave_resultado(u.get("resultado")),
        "resultado_detalle": detalle_resultado(u.get("resultado")),
        # quién inició el ciclo (O1, tanda 3); los ciclos anteriores o sin sesión: SIN_DATO
        "operador": operador.strip() if isinstance(operador, str) and operador.strip()
                    else SIN_DATO,
    }


def resumen_presentable(resumen) -> dict:
    """Textos del resumen listos para QML. resumen None = sin respuesta del
    backend: todo SIN_DATO (D-16)."""
    r = resumen if isinstance(resumen, dict) else {}
    u = ciclo_presentable(r.get("ultimo_ciclo"))
    return {
        "ciclos_totales": formatear_entero(r.get("ciclos_totales")),
        "ciclos_hoy": formatear_entero(r.get("ciclos_hoy")),
        "ultimo_fecha": u["fecha"],
        "ultimo_hora": u["hora"],
        "ultimo_programa": u["programa"],
        "ultimo_programa_nombre": u["programa_nombre"],
        "ultimo_resultado": u["resultado"],
        "ultimo_resultado_detalle": u["resultado_detalle"],
        "ultimo_operador": u["operador"],
    }


def mantenimiento_presentable(respuesta) -> dict:
    """GET /maintenance listo para QML (M1, tanda 3). Sin respuesta, sin dato
    (reloj anterior a la instalación) o sin intervalos: SIN_DATO, nunca un
    valor inventado. `vencido` lo traduce la pantalla ("VENCIDO")."""
    r = respuesta if isinstance(respuesta, dict) else {}
    valido = r.get("estado") in ("ok", "proximo", "vencido")
    restantes = r.get("ciclos_restantes")
    return {
        "proximo": formatear_fecha(r.get("proximo_fecha")) if valido else SIN_DATO,
        "vencido": valido and r.get("vencido") is True,
        "ultimo": formatear_fecha(r.get("ultimo_fecha")) if valido else SIN_DATO,
        "ciclos_restantes": (formatear_entero(max(0, restantes))
                             if valido and _entero(restantes) is not None else SIN_DATO),
    }


def lista_presentable(respuesta) -> dict:
    """Respuesta de GET /cycle/list lista para QML; las filas mal formadas se
    descartan. Sin respuesta: lista vacía."""
    r = respuesta if isinstance(respuesta, dict) else {}
    ciclos = r.get("ciclos")
    filas = [ciclo_presentable(c) for c in ciclos if isinstance(c, dict)]         if isinstance(ciclos, list) else []
    return {"ciclos": filas, "truncado": r.get("truncado") is True}


def id_ultimo_ciclo(resumen) -> int | None:
    """id en BD del último ciclo, para pedir su curva; None si no hay o es inválido."""
    u = resumen.get("ultimo_ciclo") if isinstance(resumen, dict) else None
    return _entero(u.get("id")) if isinstance(u, dict) else None


_DIAS = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")
_MESES = ("Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto",
          "Septiembre", "Octubre", "Noviembre", "Diciembre")
_MESES_CORTOS = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")


def _lista_catalogo(clave: str, respaldo: tuple, idioma: str | None) -> tuple:
    """I4 (tanda 6): días y meses del catálogo en el idioma vigente; si falta
    o no tiene el largo esperado, la lista en español."""
    try:
        from autoclave import i18n
        v = i18n.valor(clave, idioma)
        if isinstance(v, list) and len(v) == len(respaldo) and all(isinstance(x, str) for x in v):
            return tuple(v)
    except Exception:
        pass
    return respaldo


def rotulo_periodo(periodo: str, fecha: date, idioma: str | None = None) -> str:
    """Rótulo del periodo de calendario de `fecha` entre las flechas del Historial:
    "Martes 6 oct 2026", "28 sep – 4 oct 2026" o "Octubre 2026" (en el idioma
    vigente, I4)."""
    dias = _lista_catalogo("fecha.dias", _DIAS, idioma)
    meses = _lista_catalogo("fecha.meses_largos", _MESES, idioma)
    cortos = _lista_catalogo("fecha.meses", _MESES_CORTOS, idioma)

    def corta(d: date) -> str:
        return f"{d.day} {cortos[d.month - 1]}"

    inicio, fin = periodos.rango(periodo, fecha)
    if periodo == "dia":
        return f"{dias[inicio.weekday()]} {corta(inicio)} {inicio.year}"
    if periodo == "semana":
        ultimo = fin - timedelta(days=1)
        desde = corta(inicio) + (f" {inicio.year}" if inicio.year != ultimo.year else "")
        return f"{desde} – {corta(ultimo)} {ultimo.year}"
    return f"{meses[inicio.month - 1]} {inicio.year}"

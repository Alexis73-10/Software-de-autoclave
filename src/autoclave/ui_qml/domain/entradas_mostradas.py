# ui_qml/domain/entradas_mostradas.py
#
# O3 (tanda 6): entradas mostradas del programa seleccionado (O1 de la tanda 5,
# `entradas_mostradas` del JSON del programa, 1 a 3) en Preciclo, Ciclo en curso
# y la gráfica. Solo presentación: no lee hardware ni toca la lógica de ciclo.
#
# Frontera de confianza: una entrada desconocida o sin lectura se muestra como
# "—" y nunca rompe la pantalla. O11 (tanda 11, D11-7.1): una entrada cuyo
# sensor está "No en uso" en el programa ya no se muestra (antes, fila con "—").

import math

from autoclave.core.runtime import unidades as u

SIN_LECTURA = u.SIN_DATO     # "—"
MAX_ENTRADAS = 3

# Sin /cycle todavía. O11 (D11-7.4): la omisión de la asignación de fábrica
# (Principal = Cámara 1, resto No en uso): Cámara 1 y presión de cámara.
# DECISIÓN SIN CONFIRMAR: antes eran las tres de siempre, con la Referencia.
POR_OMISION = ("temp_camara", "pres_camara")

# Nombre de la AI (io_enabled) -> (tipo, ruta en sensors de GET /status)
_RUTA_STATUS = {
    "temp_camara": ("temp", ("temperature", "camara")),
    "temp_2_camara": ("temp", ("temperature", "camara_2")),
    "temp_referencia": ("temp", ("temperature", "ref")),
    "temp_drenaje": ("temp", ("temperature", "drenaje")),
    "temp_drenaje_camara": ("temp", ("temperature", "drenaje_camara")),
    "pres_camara": ("pres", ("pressure", "camara")),
    "pres_chaqueta": ("pres", ("pressure", "chaqueta")),
    "pres_empaque_1": ("pres", ("pressure", "empaque_1")),
    "pres_empaque_2": ("pres", ("pressure", "empaque_2")),
}

# Entradas que el backend registra para la gráfica (lecturas_grafica) -> serie
SERIE_GRAFICA = {"temp_camara": "temp_camara", "temp_referencia": "temp_ref",
                 "pres_camara": "pres_camara"}

# Colores de la gráfica por posición (los de siempre)
COLORES = ("#6599FC", "#9732DA", "#00CCB0")


def tipo_de(clave: str) -> str:
    """"temp", "pres" o "" (desconocida)."""
    return _RUTA_STATUS.get(clave, ("", ()))[0]


def normalizar(lista) -> list[str]:
    """1 a 3 nombres distintos; lista inválida o vacía -> las de omisión."""
    if not isinstance(lista, list):
        return list(POR_OMISION)
    vistas: list[str] = []
    for e in lista:
        if isinstance(e, str) and e and e not in vistas:
            vistas.append(e)
    return vistas[:MAX_ENTRADAS] or list(POR_OMISION)


def visibles(lista, no_en_uso=()) -> list[str]:
    """O11 (D11-7.1): las entradas a mostrar, sin las de un sensor No en uso
    en el programa; si no queda ninguna, la omisión sin las No en uso (y, en
    último caso, la presión de cámara)."""
    no = set(no_en_uso or ())
    quedan = [e for e in normalizar(lista) if e not in no]
    return quedan or [e for e in POR_OMISION if e not in no] or ["pres_camara"]


def _numero(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return None
    return float(v)


def _lectura(sensors, clave):
    ruta = _RUTA_STATUS.get(clave, ("", ()))[1]
    dato = sensors
    for paso in ruta:
        if not isinstance(dato, dict):
            return None
        dato = dato.get(paso)
    return _numero(dato) if ruta else None


def _formatear(tipo: str, valor, t_unidad: str, p_unidad: str, p_atm) -> tuple[str, str]:
    """(valor, símbolo) en la unidad vigente; "—" si no hay número."""
    if tipo == "temp":
        simbolo = u.simbolo_temp(t_unidad)
        if valor is None:
            return SIN_LECTURA, simbolo
        return u.formatear_temp(valor, t_unidad, con_simbolo=False), simbolo
    if tipo == "pres":
        if valor is None:
            return SIN_LECTURA, u.simbolo_pres(p_unidad)
        mostrado, simbolo = u.pres_a_mostrar(valor, p_unidad, p_atm)
        if mostrado is None:
            return SIN_LECTURA, u.simbolo_pres(p_unidad)
        return u.formatear_pres(valor, p_unidad, p_atm, con_simbolo=False), u.SIMBOLOS.get(simbolo, simbolo)
    return SIN_LECTURA, ""


def construir(lista, sensors, no_en_uso=(), t_unidad: str = "C", p_unidad: str = "kPa",
              p_atm=None) -> list[dict]:
    """Filas para QML: {clave, tipo, valor, unidad, enUso}. `no_en_uso`: entradas
    cuyo sensor está "No en uso" en el programa: O11 (D11-7.1) no se muestran
    (enUso queda siempre True; se conserva por compatibilidad con QML)."""
    filas = []
    for clave in visibles(lista, no_en_uso):
        tipo = tipo_de(clave)
        valor = _lectura(sensors, clave)
        texto, simbolo = _formatear(tipo, valor, t_unidad, p_unidad, p_atm)
        filas.append({"clave": clave, "tipo": tipo, "valor": texto, "unidad": simbolo,
                      "enUso": True})
    return filas


# ── gráfica ──────────────────────────────────────────────────────────────

def simbolo_grafica_pres(p_unidad: str) -> str:
    """DECISIÓN SIN CONFIRMAR (O3): en psi la gráfica usa psi ABSOLUTO (psia),
    continuo a ambos lados de la atmosférica; psig/inHg cambiarían de signo y de
    unidad a mitad de la curva."""
    return "psia" if p_unidad == "psi" else u.simbolo_pres(p_unidad)


def pres_grafica(kpa_abs, p_unidad: str):
    v = _numero(kpa_abs)
    if v is None:
        return None
    if p_unidad == "psi":
        return v / u.KPA_POR_PSI
    return u.pres_a_mostrar(v, p_unidad)[0]


def series_grafica(lista, t_unidad: str = "C", p_unidad: str = "kPa",
                   no_en_uso=()) -> list[dict]:
    """Series de GraficaCiclo para las entradas elegidas: {clave (serie de
    datos), entrada, color, eje, unidad, registrada}. Una entrada que el backend
    no registra en la gráfica queda en la leyenda con registrada=False y sin
    trazo (DECISIÓN SIN CONFIRMAR: hoy solo se registran temp_camara,
    temp_referencia y pres_camara). O11 (D11-7.1): sin las No en uso."""
    series = []
    for i, clave in enumerate(visibles(lista, no_en_uso)):
        tipo = tipo_de(clave)
        series.append({
            "clave": SERIE_GRAFICA.get(clave, clave),
            "entrada": clave,
            "color": COLORES[i % len(COLORES)],
            "eje": "derecho" if tipo == "pres" else "izquierdo",
            "unidad": simbolo_grafica_pres(p_unidad) if tipo == "pres" else u.simbolo_temp(t_unidad),
            "registrada": clave in SERIE_GRAFICA,
        })
    return series


def convertir_datos_grafica(datos: dict, t_unidad: str = "C", p_unidad: str = "kPa") -> dict:
    """Datos de la gráfica (°C / kPa abs) en la unidad vigente."""
    salida = dict(datos)
    for clave in ("temp_camara", "temp_ref"):
        if isinstance(datos.get(clave), list):
            salida[clave] = [None if _numero(v) is None else u.temp_a_mostrar(_numero(v), t_unidad)
                             for v in datos[clave]]
    if isinstance(datos.get("pres_camara"), list):
        salida["pres_camara"] = [pres_grafica(v, p_unidad) for v in datos["pres_camara"]]
    return salida

# ui_qml/domain/posicion_card.py
#
# Tanda 28 (A11): posición de la card (globo) del cursor de la gráfica del
# ciclo. Función pura en píxeles de la tarjeta; QML solo dibuja donde ella dice.
#
# Regla (DECISIÓN SIN CONFIRMAR, fijada por el prompt de Cristian, 5-nov):
#   - la card nunca sale del área de la gráfica ni tapa el cursor (queda
#     entera a un lado de la línea, con una reserva a cada lado de ella);
#   - se busca, en el rango horizontal que ocuparía la card, una posición
#     vertical que no cruce ninguna curva, empezando por la mitad opuesta a
#     los puntos de las curvas (arriba si las curvas están abajo y al revés);
#   - el lado preferido es el que tiene más espacio (a igualdad, la derecha);
#     si en ese lado no hay hueco libre se prueba el otro;
#   - si ningún lado tiene hueco libre, se elige la posición que menos cruza
#     curvas (`libre` = False).

import math

# posiciones verticales candidatas entre el borde superior e inferior del área
_PASOS_Y = 24


def _finito(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _limpiar(curvas) -> list:
    """Cada curva como lista de (x, y) finitos, en orden; descarta lo demás."""
    salida = []
    for curva in curvas or []:
        pts = []
        for p in curva or []:
            if isinstance(p, dict):
                x, y = p.get("x"), p.get("y")
            else:
                try:
                    x, y = p[0], p[1]
                except (TypeError, IndexError, KeyError):
                    continue
            if _finito(x) and _finito(y):
                pts.append((float(x), float(y)))
        salida.append(pts)
    return salida


def _largo_cruce(curvas, x0, x1, y0, y1) -> float:
    """Largo horizontal (px) de curva que cae dentro del rectángulo
    [x0, x1] x [y0, y1]. 0 = la card no cubre ninguna serie."""
    total = 0.0
    for pts in curvas:
        if len(pts) == 1:
            x, y = pts[0]
            if x0 <= x <= x1 and y0 <= y <= y1:
                total += 1.0
            continue
        for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
            if xa > xb:
                xa, ya, xb, yb = xb, yb, xa, ya
            lo, hi = max(xa, x0), min(xb, x1)
            if lo > hi:
                continue
            if xb == xa:                                # tramo vertical
                if min(ya, yb) <= y1 and max(ya, yb) >= y0:
                    total += 1.0
                continue
            ylo = ya + (yb - ya) * (lo - xa) / (xb - xa)
            yhi = ya + (yb - ya) * (hi - xa) / (xb - xa)
            if min(ylo, yhi) <= y1 and max(ylo, yhi) >= y0:
                total += max(hi - lo, 1.0)
    return total


def _y_de_curvas(curvas, x0, x1):
    """Y media de las curvas dentro de [x0, x1] (interpolando los tramos largos
    entre dos lecturas), o None si ninguna pasa por ahí."""
    ys = []
    for pts in curvas:
        if len(pts) == 1 and x0 <= pts[0][0] <= x1:
            ys.append(pts[0][1])
        for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
            if xa > xb:
                xa, ya, xb, yb = xb, yb, xa, ya
            lo, hi = max(xa, x0), min(xb, x1)
            if lo > hi:
                continue
            if xb == xa:
                ys.extend((ya, yb))
                continue
            ys.append(ya + (yb - ya) * (lo - xa) / (xb - xa))
            ys.append(ya + (yb - ya) * (hi - xa) / (xb - xa))
    return sum(ys) / len(ys) if ys else None


def posicionar_card(area, x_cursor, ancho, alto, curvas, reserva_cursor=0.0) -> dict:
    """Esquina superior izquierda de la card.

    area: (izq, arriba, der, abajo) de la gráfica, en px; x_cursor: x de la
    línea del cursor; ancho/alto: tamaño de la card; curvas: lista de curvas,
    cada una lista de puntos {x, y} (o (x, y)) en px; reserva_cursor: mitad del
    ancho que se deja libre alrededor del cursor (línea y su punto).
    Devuelve {"x", "y", "lado": "derecha"|"izquierda", "franja":
    "superior"|"inferior"|"media", "libre": bool}."""
    izq, arr, der, aba = (float(v) for v in area)
    ancho, alto = max(0.0, float(ancho)), max(0.0, float(alto))
    reserva = max(0.0, float(reserva_cursor)) if _finito(reserva_cursor) else 0.0
    cur = float(x_cursor) if _finito(x_cursor) else (izq + der) / 2
    cur = min(max(cur, izq), der)
    curvas = _limpiar(curvas)

    # x de cada lado, entera a un costado de la línea y dentro del área; un lado
    # que no cabe entero no es candidato (salvo que ninguno quepa)
    x_der = cur + reserva
    x_izq = cur - reserva - ancho
    espacio_der = der - x_der
    espacio_izq = (cur - reserva) - izq
    lados = {}
    if x_der + ancho <= der + 1e-9:
        lados["derecha"] = (x_der, espacio_der)
    if x_izq >= izq - 1e-9:
        lados["izquierda"] = (x_izq, espacio_izq)
    if not lados:       # área más estrecha que la card: el lado con más espacio, acotado
        if espacio_der >= espacio_izq:
            lados["derecha"] = (min(x_der, max(izq, der - ancho)), espacio_der)
        else:
            lados["izquierda"] = (max(izq, min(x_izq, der - ancho)), espacio_izq)
    orden = sorted(lados, key=lambda k: (-lados[k][1], k != "derecha"))

    y_min, y_max = arr, max(arr, aba - alto)
    pasos = [y_min + (y_max - y_min) * i / _PASOS_Y for i in range(_PASOS_Y + 1)]

    mejor = None
    for lado in orden:
        x, _espacio = lados[lado]
        y_cur = _y_de_curvas(curvas, x, x + ancho)
        mitad = (arr + aba) / 2
        # mitad opuesta a las curvas: curvas abajo → arriba; sin curvas → arriba
        arriba_primero = y_cur is None or y_cur >= mitad
        centro = y_min if arriba_primero else y_max
        # más lejos de las curvas primero = más cerca de la mitad opuesta
        for y in sorted(pasos, key=lambda p: abs(p - centro)):
            cruce = _largo_cruce(curvas, x, x + ancho, y, y + alto)
            if cruce == 0.0:
                franja = ("superior" if y <= y_min + 1e-9 else
                          "inferior" if y >= y_max - 1e-9 else "media")
                return {"x": x, "y": y, "lado": lado, "franja": franja, "libre": True}
            if mejor is None or cruce < mejor[0] - 1e-9:
                franja = ("superior" if y <= y_min + 1e-9 else
                          "inferior" if y >= y_max - 1e-9 else "media")
                mejor = (cruce, {"x": x, "y": y, "lado": lado, "franja": franja, "libre": False})
    return mejor[1]

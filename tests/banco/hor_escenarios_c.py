# tests/banco/hor_escenarios_c.py
#
# Tanda horizontal, grupo C (Menú principal y sus ventanas, Historial y Detalle
# de ciclo, Reportes). Lo ejecuta tests/banco/hor_capturas.py dentro de su guion
# (qml(), arnes(), ACCIONES, QTest... a la vista); no se importa solo.
# Estados equivalentes a los de tests/banco/rep_capturas_reportes.py (día
# elegido, selector abierto, año, alarmas «Ver todas», correo sin sesión) más
# el ciclo abierto en Historial, Ciclos hoy y Reportes.


def _c_items(win):
    # recorrido por hijos visuales: los delegados de ListView/Repeater no siempre
    # tienen padre QObject (findChildren no los ve)
    salida, pila = [], [win.contentItem()]
    while pila:
        it = pila.pop()
        salida.append(it)
        pila.extend(reversed(it.childItems()))
    return salida


def _c_visibles(h, prefijo):
    return [o for o in _c_items(h.win) if o.objectName().startswith(prefijo) and o.isVisible()]


def _c_uno(h, nombre):
    for o in _c_items(h.win):
        if o.objectName() == nombre:
            return o
    for o in h.por_nombre(nombre):
        return o
    return None


def _c_ir_a(h, nombre, margen=20):
    flick = _c_uno(h, "contenidoReportes")
    o = _c_uno(h, nombre)
    if flick is None or o is None:
        return
    y = o.mapToItem(flick.property("contentItem"), h.QPointF(0, 0)).y()
    tope = max(0, flick.property("contentHeight") - flick.height())
    flick.setProperty("contentY", max(0, min(tope, y - margen)))
    h.QTest.qWait(300)


def _c_rd(win):
    return win.property("reporteDashboard")


def _c_tocar_fila(prefijo):
    def accion(win, h):
        h.QTest.qWait(600)
        filas = _c_visibles(h, prefijo)
        if filas:
            h.tocar(filas[0])
            h.QTest.qWait(900)
    return accion


def _c_historial_destino(win, h):
    h.QTest.qWait(600)
    casillas = [o for o in _c_visibles(h, "casilla_") if o.objectName() != "casillaTodas"]
    if casillas:
        h.tocar(casillas[0])
        h.QTest.qWait(300)
    b = _c_uno(h, "botonEnviarMarcados")
    if b is not None:
        h.tocar(b)
    h.QTest.qWait(600)


def _c_reportes_dia(win, h):
    _c_rd(win).elegirDia("2026-10-08")
    h.QTest.qWait(400)
    _c_ir_a(h, "seccionCalendario")


def _c_reportes_panel(win, h):
    _c_rd(win).elegirDia("2026-10-08")
    h.QTest.qWait(400)
    _c_ir_a(h, "panelDiaCalendario", margen=300)


def _c_reportes_medio(win, h):
    _c_ir_a(h, "seccionCiclosDia")


def _c_reportes_selector(win, h):
    _c_ir_a(h, "seccionCalendario")
    sel = _c_uno(h, "selectorProgramaCalendario")
    if sel is not None:
        try:
            h.QMetaObject.invokeMethod(sel, "abrir")
        except Exception:
            sel.setProperty("abierto", True)
    h.QTest.qWait(400)


def _c_reportes_anio(win, h):
    _c_rd(win).cambiarPeriodo("anio")
    h.QTest.qWait(500)
    _c_ir_a(h, "seccionCalendario")


def _c_reportes_alarmas(win, h):
    _c_ir_a(h, "seccionAlarmas")
    lista = _c_uno(h, "listaAlarmasPeriodo")
    if lista is not None:
        h.QMetaObject.invokeMethod(lista, "abrirTodas")
    h.QTest.qWait(300)


def _c_reportes_correo(win, h):
    win.setProperty("sesionActiva", False)
    h.QTest.qWait(200)
    _c_ir_a(h, "seccionAcciones")
    b = _c_uno(h, "botonEnviarResumen")
    if b is not None:
        h.tocar(b)
    h.QTest.qWait(400)


def _c_reportes_ciclo(win, h):
    _c_rd(win).elegirDia("2026-10-08")
    h.QTest.qWait(400)
    _c_ir_a(h, "panelDiaCalendario", margen=300)
    filas = _c_visibles(h, "intento_")
    if filas:
        h.tocar(filas[0])
    h.QTest.qWait(900)


def _c_reportes_fallo(win, h):
    causas = (_c_rd(win).property("datos") or {}).get("causas") or []
    if causas:
        _c_rd(win).abrirFallo(causas[0]["causa"])
    h.QTest.qWait(500)


def _c_con_win(f):
    def accion(win, h):
        h.win = win
        f(win, h)
    return accion


for _n, _f in [("c_hist_ciclo", _c_tocar_fila("resultado_")),
               ("c_hist_destino", _c_historial_destino),
               ("c_rep_dia", _c_reportes_dia), ("c_rep_panel", _c_reportes_panel),
               ("c_rep_medio", _c_reportes_medio), ("c_rep_selector", _c_reportes_selector),
               ("c_rep_anio", _c_reportes_anio), ("c_rep_alarmas", _c_reportes_alarmas),
               ("c_rep_correo", _c_reportes_correo), ("c_rep_ciclo", _c_reportes_ciclo),
               ("c_rep_fallo", _c_reportes_fallo)]:
    ACCIONES[_n] = _c_con_win(_f)  # noqa: F821 (lo da hor_capturas.py)

arnes("menu_historial_ciclo", "PruebaMenuPrincipal.qml", {"ventanaInicial": "historial"},  # noqa: F821
      py="menu", accion="py:c_hist_ciclo")
arnes("menu_ciclos_hoy_ciclo", "PruebaMenuPrincipal.qml", {"ventanaInicial": "ciclos_hoy"},  # noqa: F821
      py="menu", accion="py:c_hist_ciclo")
arnes("menu_historial_destino", "PruebaMenuPrincipal.qml", {"ventanaInicial": "historial"},  # noqa: F821
      py="menu", accion="py:c_hist_destino")
for _n in ("dia", "panel", "medio", "selector", "anio", "alarmas", "correo", "ciclo", "fallo"):
    arnes("reportes_" + _n, "PruebaReportes.qml", py="reportes", accion="py:c_rep_" + _n)  # noqa: F821

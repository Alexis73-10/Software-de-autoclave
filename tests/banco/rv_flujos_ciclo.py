# tests/banco/rv_flujos_ciclo.py
#
# Revisión visual (RV, etapa E): flujos de Preciclo, Ciclo en curso, Historial
# y Reportes, y standby. Los reexporta tests/banco/rv_flujos.py.

from tests.banco.rv_flujos_base import (CAMPANA, QTestWait, _hay, _principal, al_menu,
                                        despertar, volver_principal)


def _ancho(it):
    return it.width() if it is not None else 0


def _iniciar_por_deslizador(h):
    m = h.buscar(nombre="manijaDeslizadorInicio")
    d = h.buscar(nombre="deslizadorIniciarCiclo")
    if m is None or d is None:
        return False
    h.arrastrar(m, _ancho(d) * 1.1)
    if h.esperar(lambda: _hay(h, "modalOperador"), 3):
        h.captura("modal_operador", esperado="modal de operador al iniciar", ok=True)
        filas = h.buscar(prefijo="filaOperador_", todos=True)
        if filas:
            h.tocar(filas[0])
        h.tocar(h.buscar(nombre="botonIniciarOperador"))
    return True


def _manija_cancelar(h):
    c = h.buscar(nombre="deslizadorCancelarCiclo")
    if c is None:
        return None, None
    for it in h.items(c):
        if it.objectName() == "manijaDeslizadorInicio" and h.visible(it):
            return c, it
    return c, None


def flujo_preciclo(h, status):
    despertar(h)
    volver_principal(h)
    h.captura("preciclo", esperado="Preciclo con el deslizador de inicio", ok=_hay(h, "tarjetaPreciclo"))
    h.tocar(h.buscar(nombre="zonaProgramaTocable"))
    ok = h.esperar(lambda: _hay(h, "ventanaSelectorCiclo"), 3)
    h.captura("selector_programa", esperado="selector de programas abierto", ok=ok)
    filas = h.buscar(prefijo="filaCiclo_", todos=True)
    if len(filas) > 1:
        h.tocar(filas[1])
    else:
        h.tocar_en(600, 60, "fuera del selector")
    ok = h.esperar(lambda: not _hay(h, "ventanaSelectorCiclo"), 3)
    h.captura("programa_elegido", esperado="selector cerrado tras elegir", ok=ok)
    h.tocar_en(*CAMPANA, descripcion="campana")
    ok = h.esperar(lambda: _hay(h, "grupoAlarmas", "grupoAvisos", "textoSinNotificaciones"), 3)
    h.captura("campana", esperado="panel de notificaciones abierto", ok=ok)
    fila = h.buscar(prefijo="filaAlarmaPanel_")
    if fila is not None:
        h.tocar(fila)
        ok = h.esperar(lambda: _hay(h, "tarjetaDetalleAlarma"), 3)
        h.captura("detalle_alarma", esperado="detalle de la alarma", ok=ok)
        h.tocar(h.buscar(nombre="botonCerrarDetalle"))
    h.tocar_en(60, 1000, "fuera del panel")
    h.esperar(lambda: not _hay(h, "grupoAlarmas", "textoSinNotificaciones"), 3)
    p = h.buscar(nombre="botonPuertaPreciclo")
    if p is not None:
        h.tocar(p)
        QTestWait(h, 1500)
        h.captura("puerta_abrir", esperado="orden de abrir la puerta (cambia el estado)",
                  ok=any(v != "CERRADO" for v in (status().get("doors") or {}).values()))
        h.tocar(h.buscar(nombre="botonPuertaPreciclo"))
        QTestWait(h, 1500)
        h.captura("puerta_cerrar", esperado="puerta cerrada de nuevo",
                  ok=all(v == "CERRADO" for v in (status().get("doors") or {"x": "?"}).values()))
    else:
        h.nota("sin botón de puerta visible (puerta sin actuador)")
    d = h.buscar(nombre="deslizadorIniciarCiclo")
    m = h.buscar(nombre="manijaDeslizadorInicio")
    if d is None or m is None:
        h.captura("sin_deslizador", esperado="deslizador de inicio visible", ok=False)
        return
    x0 = h.centro(m)[0]
    h.arrastrar(m, _ancho(d) * 0.3)
    QTestWait(h, 1200)
    h.captura("deslizador_incompleto", esperado="la manija regresa y no inicia el ciclo",
              ok=abs(h.centro(m)[0] - x0) < 8 and status().get("machine_state") != "CICLO")
    _iniciar_por_deslizador(h)
    ok = h.esperar(lambda: status().get("machine_state") == "CICLO", 8)
    h.captura("deslizador_completo", esperado="inicia el ciclo", ok=ok)


def flujo_ciclo(h, status):
    despertar(h)
    if status().get("machine_state") != "CICLO":
        volver_principal(h)
        _iniciar_por_deslizador(h)
    ok = h.esperar(lambda: _hay(h, "tarjetaCicloEnCurso"), 10)
    h.captura("en_curso", esperado="Ciclo en curso con barra de fases y gráfica", ok=ok)
    QTestWait(h, 4000)
    g = h.buscar(nombre="graficaCicloEnCurso")
    if g is not None:
        x, y = h.centro(g)
        h.tocar_en(x, y, "cursor de la gráfica")
        h.captura("cursor_grafica", esperado="globo del cursor en la gráfica", ok=_hay(h, "globoGrafica"))
    h.tocar_en(*CAMPANA, descripcion="campana")
    ok = h.esperar(lambda: _hay(h, "grupoAlarmas", "grupoAvisos", "textoSinNotificaciones"), 3)
    h.captura("campana_ciclo", esperado="panel de notificaciones", ok=ok)
    h.tocar_en(60, 1000, "fuera del panel")
    QTestWait(h, 600)
    c, mc = _manija_cancelar(h)
    if mc is not None:
        h.arrastrar(mc, _ancho(c) * 0.3)
        QTestWait(h, 1500)
        h.captura("cancelar_incompleto", esperado="no cancela; la manija regresa",
                  ok=status().get("fase_ciclo") != "CANCELADO")
    else:
        h.nota("sin deslizador de cancelar visible")
    ok = h.esperar(lambda: h.buscar(texto="CONFIRMAR") is not None or h.buscar(texto="CONFIRM") is not None, 300)
    h.captura("fin", esperado="fin del ciclo con CONFIRMAR", ok=ok)
    b = h.buscar(texto="CONFIRMAR") or h.buscar(texto="CONFIRM")
    if b is not None:
        h.tocar(b)
        ok = h.esperar(lambda: _hay(h, "tarjetaModalConfirmacion"), 3)
        h.captura("modal_confirmar", esperado="modal de confirmación", ok=ok)
        h.tocar(h.buscar(nombre="botonAccionModal"))
        ok = h.esperar(lambda: status().get("machine_state") != "CICLO", 6)
        h.captura("confirmado", esperado="regresa a Preciclo tras confirmar", ok=ok)


def flujo_ciclo_cancelar(h, status):
    despertar(h)
    volver_principal(h)
    _iniciar_por_deslizador(h)
    h.esperar(lambda: _hay(h, "tarjetaCicloEnCurso"), 10)
    QTestWait(h, 3000)
    c, mc = _manija_cancelar(h)
    if mc is None:
        h.captura("sin_cancelar", esperado="deslizador de cancelar visible", ok=False)
        return
    h.arrastrar(mc, _ancho(c) * 1.1)
    ok = h.esperar(lambda: status().get("fase_ciclo") == "CANCELADO"
                   or _hay(h, "panelFinCiclo", "pildoraFinCiclo"), 8)
    h.captura("cancelado", esperado="ciclo cancelado sin modal", ok=ok)
    if _hay(h, "botonVerGrafica"):
        h.tocar(h.buscar(nombre="botonVerGrafica"))
        h.captura("ver_grafica", esperado="la gráfica reemplaza al panel", ok=_hay(h, "graficaCicloEnCurso"))
    b = h.buscar(texto="CONFIRMAR") or h.buscar(texto="CONFIRM")
    if b is not None:
        h.tocar(b)
        h.esperar(lambda: _hay(h, "tarjetaModalConfirmacion"), 3)
        h.captura("modal_confirmar", esperado="modal de confirmación", ok=_hay(h, "tarjetaModalConfirmacion"))
        h.tocar(h.buscar(nombre="botonAccionModal"))
        ok = h.esperar(lambda: status().get("machine_state") != "CICLO", 6)
        h.captura("confirmado", esperado="regresa a Preciclo", ok=ok)


def flujo_reportes(h, status):
    despertar(h)
    al_menu(h)
    h.tocar(h.buscar(nombre="tarjetaHistorial"))
    h.esperar(lambda: _hay(h, "ventanaHistorial"), 4)
    h.captura("historial", esperado="ventana de Historial", ok=_hay(h, "ventanaHistorial"))
    fila = h.buscar(prefijo="resultado_")
    if fila is not None:
        h.tocar(fila)
        h.captura("detalle", esperado="detalle del ciclo", ok=_hay(h, "detalleCicloHistorial"))
        e = h.buscar(nombre="botonEnviarCiclo")
        if e is not None:
            h.nota("no accionado por seguridad: envío por correo")
    for _ in range(3):
        b = h.buscar(nombre="botonVolverHistorial") or h.buscar(nombre="botonVolverListado")
        if b is None:
            break
        h.tocar(b)
    h.tocar_en(600, 60, "fuera de la ventana")
    QTestWait(h, 500)
    al_menu(h)
    h.tocar(h.buscar(nombre="tarjetaReportes"))
    QTestWait(h, 1500)
    h.captura("reportes", esperado="Reportes", ok=not _hay(h, "tituloMenu"))
    for vista in ("Día", "Semana", "Mes", "Año", "Day", "Week", "Month", "Year"):
        b = h.buscar(texto=vista)
        if b is not None and b.property("text") == vista:
            h.tocar(b)
            QTestWait(h, 1000)
            h.captura("vista_" + vista, esperado=f"vista {vista}", ok=True)
    ok = volver_principal(h)
    h.captura("volver", esperado="vuelve con Inicio", ok=ok)


def flujo_standby(h, status):
    despertar(h)
    volver_principal(h)
    h.captura("principal", esperado="Preciclo", ok=_principal(h))
    ok = h.esperar(lambda: not _principal(h) and not _hay(h, "tituloMenu"), 420)
    h.captura("reposo", esperado="Reposo por inactividad", ok=ok)
    h.tocar_en(600, 960, "reposo")
    ok = h.esperar(lambda: _principal(h), 8)
    h.captura("despierta", esperado="vuelve a Preciclo al tocar", ok=ok)

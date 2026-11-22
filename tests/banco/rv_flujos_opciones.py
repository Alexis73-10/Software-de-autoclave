# tests/banco/rv_flujos_opciones.py
#
# Revisión visual (RV, etapa E): flujos de Opciones contra el backend REAL del
# worktree aislado (módulo E/S simulado en 127.0.0.1). Los reexporta
# tests/banco/rv_flujos.py. No acciona: Respaldo/restaurar, Fecha y hora,
# configurar módulo, red, envío de correo, Aplicar de Reasignación ni Apagar.

from tests.banco.rv_flujos_base import QTestWait, _hay, despertar, escribir_campo, login, volver_principal

SECCIONES = ("parametros_ciclo", "parametros_sistema", "entradas_salidas", "mantenimiento",
             "opciones_avanzadas", "usuarios", "conectividad", "fecha_hora", "info_sistema",
             "bitacora", "respaldo")


CARGADOR = {"parametros_ciclo": "cargadorParametrosCiclo", "parametros_sistema": "cargadorParametrosEquipo",
            "entradas_salidas": "cargadorEntradasSalidas", "mantenimiento": "cargadorMantenimiento",
            "opciones_avanzadas": "cargadorOpcionesAvanzadas", "usuarios": "cargadorUsuarios",
            "conectividad": "cargadorConectividad", "fecha_hora": "cargadorFechaHora",
            "info_sistema": "cargadorInfoSistema", "bitacora": "cargadorBitacora", "respaldo": "cargadorRespaldo"}


def _seccion(h, clave):
    """Abre una sección por su entrada del menú de Opciones (abre el cajón si hace
    falta) y comprueba que su cargador quedó visible; si no, reintenta una vez
    (la sección anterior puede seguir cargando al primer toque)."""
    for intento in range(2):
        e = h.buscar(nombre="entrada_" + clave)
        if e is None:
            h.tocar(h.buscar(nombre="botonHamburguesa"))
            e = h.esperar_item(nombre="entrada_" + clave, s=3)
        if e is None:
            return False
        QTestWait(h, 800)
        h.tocar(e)
        if h.buscar(nombre="dialogoCambiarSeccion") is not None:
            h.nota("diálogo de cambiar de sección con cambios pendientes")
        if h.esperar(lambda: h.buscar(nombre=CARGADOR.get(clave, "")) is not None, 4):
            QTestWait(h, 800)
            return True
        h.nota(f"la sección {clave} no se abrió al primer toque; reintento")
    return False


ACEPTAR = ("continuar", "continue", "confirmar", "confirm", "aceptar", "accept", "cambiar", "change",
           "habilitar", "enable", "guardar", "save")


def _confirmar_dialogo(h, nombre):
    """Toca el botón de aceptar (por su texto) del diálogo `nombre`, si está abierto."""
    d = h.buscar(nombre=nombre)
    if d is None:
        return False
    cands = [x for x in h.items(d) if isinstance(x.property("text"), str) and h.visible(x)
             and x.property("text").strip().lower() in ACEPTAR]
    if not cands:
        h.nota(f"diálogo {nombre} sin botón de aceptar reconocible")
        return False
    h.tocar(cands[-1])
    QTestWait(h, 1200)
    return True


def _en(h, contenedor, texto):
    """Ítem visible con ese texto dentro del ítem `contenedor` (objectName)."""
    c = h.buscar(nombre=contenedor)
    if c is None:
        return None
    for it in h.items(c):
        t = it.property("text")
        if isinstance(t, str) and t == texto and h.visible(it):
            return it
    return None


def flujo_opciones(h, status):
    despertar(h)
    ok = login(h)
    h.captura("opciones", esperado="Opciones tras el login de ingeniero", ok=ok and _hay(h, "pantallaOpciones"))
    for clave in SECCIONES:
        ok = _seccion(h, clave)
        h.captura("seccion_" + clave, esperado=f"sección {clave} abierta", ok=ok)
        if clave in ("respaldo", "fecha_hora"):
            h.nota(f"no accionado por seguridad: controles de {clave} (solo se abrió la sección)")
    volver_principal(h)


def flujo_parametros(h, status):
    despertar(h)
    login(h)
    _seccion(h, "parametros_ciclo")
    sec = h.esperar_item(nombre="seccion_esterilizacion", s=4)
    h.tocar(sec)
    ok = h.esperar(lambda: _hay(h, "listaParametros"), 4)
    h.captura("seccion_esterilizacion", esperado="parámetros de Esterilización", ok=ok)
    p = h.esperar_item(nombre="param_temperatura_esterilizacion", s=3) or h.buscar(prefijo="param_")
    nombre = p.objectName() if p else ""
    h.tocar(p)
    ok = h.esperar(lambda: _hay(h, "ventanaAjuste"), 3)
    h.captura("ajuste", esperado=f"ventana de ajuste de {nombre}", ok=ok)
    h.tocar(h.buscar(nombre="campoNuevoValor"))
    ok = h.esperar(lambda: _hay(h, "tecladoNumerico"), 3)
    h.captura("teclado_numerico", esperado="teclado numérico abierto", ok=ok)
    h.teclear("999")
    h.captura("fuera_de_rango", esperado="rango resaltado con 999 °C fuera de rango", ok=True)
    h.tocar(h.buscar(nombre="teclaConfirmar"))
    QTestWait(h, 600)
    h.captura("fuera_de_rango_confirmar", esperado="999 °C no se acepta (el teclado sigue abierto o hay error)",
              ok=_hay(h, "tecladoNumerico", "errorIngreso"))
    if not _hay(h, "tecladoNumerico"):
        h.tocar(h.buscar(nombre="campoNuevoValor"))
        h.esperar(lambda: _hay(h, "tecladoNumerico"), 3)
    for _ in range(6):
        b = h.buscar(nombre="teclaBorrar")
        if b is None:
            break
        h.tocar(b)
    h.teclear("135")
    h.tocar(h.buscar(nombre="teclaConfirmar"))
    QTestWait(h, 600)
    h.captura("valor_valido", esperado="135 °C en el campo nuevo valor", ok=not _hay(h, "tecladoNumerico"))
    h.tocar(h.buscar(nombre="guardarAjuste"))
    QTestWait(h, 800)
    if _hay(h, "dialogoGuardarAjuste"):
        h.captura("dialogo_guardar", esperado="diálogo de confirmar el guardado", ok=True)
        _confirmar_dialogo(h, "dialogoGuardarAjuste")
    ok = h.esperar(lambda: not _hay(h, "ventanaAjuste"), 6)
    QTestWait(h, 1500)
    h.captura("guardado", esperado="ventana cerrada y la fila muestra 135", ok=ok)
    volver_principal(h)


def flujo_usuarios(h, status):
    despertar(h)
    login(h)
    _seccion(h, "usuarios")
    h.captura("usuarios", esperado="lista de usuarios", ok=_hay(h, "listaUsuarios"))
    h.tocar(h.buscar(nombre="botonNuevoUsuario"))
    ok = h.esperar(lambda: _hay(h, "tarjetaNuevoUsuario"), 4)
    h.captura("nuevo_usuario", esperado="formulario de nuevo usuario", ok=ok)
    escribir_campo(h, "campoNombre", "prueba visual")
    escribir_campo(h, "campoUsuario", "rvprueba2")
    escribir_campo(h, "campoClave", "clave5678")
    escribir_campo(h, "campoConfirmacion", "clave5678")
    h.tocar(h.buscar(nombre="campoRol"))
    if not h.esperar(lambda: _hay(h, "listaRoles"), 2):
        # con el teclado abierto el primer toque fuera lo cierra; se toca otra vez
        h.nota("el primer toque en Rol cerró el teclado; segundo toque")
        h.tocar(h.buscar(nombre="campoRol"))
        h.esperar(lambda: _hay(h, "listaRoles"), 2)
    h.captura("roles", esperado="lista de roles abierta", ok=_hay(h, "listaRoles"))
    # el ingeniero crea admin, técnico o ingeniero (los operadores van en su pestaña)
    op = _en(h, "listaRoles", "Técnico") or _en(h, "listaRoles", "Technician")
    h.tocar(op)
    h.captura("formulario_lleno", esperado="formulario completo", ok=True)
    h.tocar(h.buscar(nombre="botonGuardarUsuario"))
    ok = h.esperar(lambda: _hay(h, "listaUsuarios"), 6)
    h.esperar(lambda: h.buscar(prefijo="filaUsuario_rvprueba2") is not None, 8)
    h.captura("usuario_creado", esperado="vuelve a Usuarios con el usuario nuevo",
              ok=ok and h.buscar(prefijo="filaUsuario_rvprueba2") is not None)
    fila = h.buscar(prefijo="filaUsuario_rvprueba2") or h.buscar(texto="rvprueba2")
    if fila is None:
        h.nota("no se encontró la fila del usuario nuevo")
        return
    h.tocar(fila)
    h.tocar(h.buscar(nombre="botonCambiarRol"))
    ok = h.esperar(lambda: _hay(h, "elegirRol"), 3)
    h.captura("cambiar_rol", esperado="selector de rol nuevo", ok=ok)
    op = h.buscar(prefijo="opcionRol_tecnico") or h.buscar(prefijo="opcionRol_")
    h.tocar(op)
    if _hay(h, "confirmarCambiarRol"):
        h.captura("confirmar_rol", esperado="confirmación del cambio de rol", ok=True)
        b = h.buscar(texto="Cambiar") or h.buscar(texto="Change") or h.buscar(texto="Confirmar")
        h.tocar(b)
    QTestWait(h, 1500)
    h.captura("rol_cambiado", esperado="rol cambiado en la fila", ok=True)
    h.tocar(h.buscar(prefijo="filaUsuario_rvprueba2") or fila)
    h.tocar(h.buscar(nombre="botonActivoUsuario"))
    ok = h.esperar(lambda: _hay(h, "confirmarActivoUsuario"), 3)
    h.captura("desactivar", esperado="confirmación de desactivar", ok=ok)
    b = h.buscar(texto="Desactivar") if ok else None
    cands = [x for x in h.buscar(texto="Desactivar", todos=True)] if ok else []
    h.tocar(cands[-1] if cands else b)
    QTestWait(h, 1500)
    h.captura("desactivado", esperado="usuario desactivado", ok=True)
    h.tocar(h.buscar(prefijo="filaUsuario_rvprueba2") or fila)
    h.tocar(h.buscar(nombre="botonEliminarUsuario"))
    ok = h.esperar(lambda: _hay(h, "confirmarEliminarUsuario"), 3)
    h.captura("eliminar", esperado="modal de eliminar", ok=ok)
    cands = h.buscar(texto="Eliminar", todos=True) + h.buscar(texto="Delete", todos=True)
    if cands:
        h.tocar(cands[-1])
    QTestWait(h, 1500)
    h.captura("eliminado", esperado="el usuario sale de la lista",
              ok=h.buscar(prefijo="filaUsuario_rvprueba2") is None)
    volver_principal(h)


def flujo_bitacora(h, status):
    despertar(h)
    login(h)
    _seccion(h, "bitacora")
    h.captura("bitacora", esperado="bitácora con filas", ok=h.buscar(prefijo="filaBitacora_") is not None)
    h.tocar(h.buscar(nombre="filtroDesde"))
    ok = h.esperar(lambda: _hay(h, "calendarioBitacora"), 3)
    h.captura("calendario", esperado="calendario táctil del filtro Desde", ok=ok)
    b = h.buscar(texto="Hoy") or h.buscar(texto="Today")
    h.tocar(b)
    QTestWait(h, 1200)
    h.captura("filtro_hoy", esperado="filtrado desde hoy", ok=not _hay(h, "calendarioBitacora"))
    volver_principal(h)


def flujo_reasignacion(h, status):
    despertar(h)
    login(h)
    _seccion(h, "opciones_avanzadas")
    seg = h.buscar(texto="Reasignación de entradas y salidas") or h.buscar(texto="I/O reassignment")
    if seg is None:
        for it in h.items():
            t = it.property("text")
            if isinstance(t, str) and ("Reasignación" in t or "eassign" in t) and h.visible(it):
                seg = it
                break
    h.tocar(seg)
    ok = h.esperar(lambda: _hay(h, "tablaReasignacion"), 4)
    h.captura("reasignacion", esperado="tabla de reasignación", ok=ok)
    h.nota("no accionado por seguridad: Aplicar y Restaurar fábrica de Reasignación (reinician el control)")
    volver_principal(h)


def flujo_entradas_salidas(h, status):
    despertar(h)
    login(h)
    _seccion(h, "entradas_salidas")
    h.captura("entradas", esperado="entradas digitales", ok=_hay(h, "paginaEntradas"))
    seg = h.buscar(texto="Salidas") or h.buscar(texto="Outputs")
    h.tocar(seg)
    QTestWait(h, 800)
    h.captura("salidas", esperado="salidas", ok=_hay(h, "paginaSalidas"))
    b = h.buscar(nombre="botonHabilitarModoPrueba")
    h.tocar(b)
    ok = h.esperar(lambda: _hay(h, "dialogoModoPrueba"), 3)
    h.captura("dialogo_modo_prueba", esperado="diálogo para habilitar el modo prueba", ok=ok)
    if ok:
        _confirmar_dialogo(h, "dialogoModoPrueba")
        ok = h.esperar(lambda: _hay(h, "bannerModoPrueba"), 5)
        h.captura("modo_prueba", esperado="modo prueba activo (banner)", ok=ok)
        s = h.buscar(prefijo="botonSalida_")
        if s is not None:
            nombre = s.objectName()
            h.tocar(s)
            QTestWait(h, 2000)
            h.captura("salida_on", esperado=f"{nombre} encendida o pendiente", ok=True)
            h.tocar(h.buscar(nombre=nombre))
            QTestWait(h, 2000)
            h.captura("salida_off", esperado=f"{nombre} apagada", ok=True)
        h.tocar(h.buscar(nombre="botonSalirModoPrueba"))
        ok = h.esperar(lambda: not _hay(h, "bannerModoPrueba"), 5)
        h.captura("sale_modo_prueba", esperado="sale del modo prueba", ok=ok)
    volver_principal(h)


def flujo_idioma(h, status):
    """Cambia idioma, unidades y tema desde Parámetros del equipo › Máquina."""
    despertar(h)
    login(h)
    _seccion(h, "parametros_sistema")
    t = h.esperar_item(nombre="tarjeta_maquina", s=3) or h.buscar(nombre="recuadroMaquinaVertical")
    h.tocar(t)
    ok = h.esperar(lambda: _hay(h, "idiomaEquipo"), 4)
    h.captura("maquina", esperado="configuración de la máquina", ok=ok)
    for contenedor, texto in (("temaEquipo", "Oscuro"), ("temaEquipo", "Dark")):
        b = _en(h, contenedor, texto)
        if b is not None:
            h.tocar(b)
            QTestWait(h, 800)
            h.captura("dialogo_tema", esperado="confirmación del cambio de tema", ok=_hay(h, "dialogoMaquinaEquipo"))
            _confirmar_dialogo(h, "dialogoMaquinaEquipo")
            h.captura("tema_oscuro", esperado="tema oscuro aplicado", ok=True)
            break
    b = _en(h, "idiomaEquipo", "English")
    h.tocar(b)
    QTestWait(h, 1500)
    if _hay(h, "dialogoMaquinaEquipo"):
        h.captura("dialogo_idioma", esperado="confirmación del cambio", ok=True)
        _confirmar_dialogo(h, "dialogoMaquinaEquipo")
        QTestWait(h, 1500)
    h.captura("idioma_ingles", esperado="textos en inglés", ok=h.buscar(texto="English") is not None)
    for contenedor, texto in (("temaEquipo", "Light"), ("temaEquipo", "Claro")):
        b = _en(h, contenedor, texto)
        if b is not None:
            h.tocar(b)
            QTestWait(h, 800)
            _confirmar_dialogo(h, "dialogoMaquinaEquipo")
            break
    b = _en(h, "idiomaEquipo", "Español")
    h.tocar(b)
    QTestWait(h, 1200)
    if _hay(h, "dialogoMaquinaEquipo"):
        _confirmar_dialogo(h, "dialogoMaquinaEquipo")
        QTestWait(h, 1200)
    h.captura("vuelta_espanol", esperado="de vuelta a español y tema claro", ok=h.buscar(texto="Español") is not None)
    volver_principal(h)


def _cambiar_idioma(h, destino):
    despertar(h)
    login(h)
    _seccion(h, "parametros_sistema")
    t = h.esperar_item(nombre="tarjeta_maquina", s=3) or h.buscar(nombre="recuadroMaquinaVertical")
    h.tocar(t)
    h.esperar(lambda: _hay(h, "idiomaEquipo"), 4)
    h.tocar(_en(h, "idiomaEquipo", destino))
    QTestWait(h, 800)
    _confirmar_dialogo(h, "dialogoMaquinaEquipo")
    h.captura("idioma_" + destino, esperado=f"idioma {destino}", ok=True)
    volver_principal(h)


def flujo_a_ingles(h, status):
    _cambiar_idioma(h, "English")


def flujo_a_espanol(h, status):
    _cambiar_idioma(h, "Español")

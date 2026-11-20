# tests/banco/rv_flujos.py
#
# Revisión visual (RV, etapa E): flujos de interacción que ejecuta
# tests/banco/rv_interaccion.py. Cada flujo_<nombre>(h, status) opera la UI con
# toques reales (h.tocar, h.tocar_en, h.arrastrar, h.teclear) y deja una
# captura por paso (h.captura) con el resultado esperado y si se cumplió. No es
# una prueba automática; no fuerza estados desde el código.
#
# Coordenadas lógicas del lienzo de 1200x1920 para los controles sin
# objectName (engranaje y campana de la cabecera de Preciclo y Ciclo en curso).

ENGRANAJE = (1072, 92)
CAMPANA = (915, 87)
import os

# usuario del simulador (autenticacion_simulada.py) o, contra el backend real
# del worktree aislado, la cuenta de prueba creada solo en su copia de la base
USUARIO = os.environ.get("RV_USUARIO", "ing1")
CLAVE = os.environ.get("RV_CLAVE", "clave1234")


def _hay(h, *nombres):
    return any(h.buscar(nombre=n) is not None for n in nombres)


def _principal(h):
    return _hay(h, "tarjetaPreciclo", "tarjetaCicloEnCurso")


def despertar(h, s=60):
    """Espera a que termine la intro; si queda el Reposo, lo toca."""
    h.esperar(lambda: h.buscar(nombre="introArranque") is None, s)
    if not _principal(h) and not _hay(h, "tituloMenu"):
        h.tocar_en(600, 960, "reposo")
    return h.esperar(lambda: _principal(h) or _hay(h, "tituloMenu"), 10)


def al_menu(h):
    if _hay(h, "tituloMenu"):
        return True
    if not _principal(h):
        despertar(h)
    h.tocar_en(*ENGRANAJE, descripcion="engranaje")
    return h.esperar(lambda: _hay(h, "tituloMenu"), 5)


def volver_principal(h):
    for _ in range(4):
        if _principal(h):
            return True
        b = h.buscar(nombre="botonInicio") or h.buscar(nombre="botonAtras")
        if b is None:
            break
        h.tocar(b)
        h.esperar(lambda: _principal(h), 3)
    return _principal(h)


def escribir_campo(h, campo, texto, confirmar=True):
    h.tocar(h.buscar(nombre=campo))
    abierto = h.esperar(lambda: _hay(h, "tecladoAlfanumerico", "tecladoNumerico"), 3)
    if not abierto:
        return False
    h.teclear(texto)
    if confirmar:
        h.tocar(h.buscar(nombre="teclaConfirmar"))
    return True


def login(h, usuario=USUARIO, clave=CLAVE):
    al_menu(h)
    h.tocar(h.buscar(nombre="tarjetaIniciarSesion"))
    if not h.esperar(lambda: _hay(h, "tarjetaLogin"), 4):
        return False
    escribir_campo(h, "campoUsuario", usuario)
    escribir_campo(h, "campoClave", clave)
    h.tocar(h.buscar(nombre="botonIniciarSesion"))
    return h.esperar(lambda: _hay(h, "pantallaOpciones", "areaCambioClave"), 6)


# ── 1. arranque ─────────────────────────────────────────────────────────────

def flujo_arranque(h, status):
    h.captura("intro", esperado="intro de arranque visible", ok=_hay(h, "introArranque"))
    h.esperar(lambda: h.buscar(nombre="introArranque") is None, 60)
    h.captura("tras_intro", esperado="Reposo o pantalla principal al terminar la intro",
              ok=h.buscar(nombre="introArranque") is None)
    ok = despertar(h)
    h.captura("principal", esperado="Preciclo (puerta 1) tras tocar el Reposo", ok=ok)


# ── 2. sesión ───────────────────────────────────────────────────────────────

def flujo_login(h, status):
    despertar(h)
    ok = al_menu(h)
    h.captura("menu", esperado="Menú Principal por el engranaje", ok=ok)
    h.tocar(h.buscar(nombre="tarjetaIniciarSesion"))
    ok = h.esperar(lambda: _hay(h, "tarjetaLogin"), 4)
    h.captura("login", esperado="pantalla de login", ok=ok)
    h.tocar(h.buscar(nombre="campoUsuario"))
    ok = h.esperar(lambda: _hay(h, "tecladoAlfanumerico"), 3)
    h.captura("teclado_usuario", esperado="teclado alfanumérico abierto sin tapar el campo", ok=ok)
    h.teclear("ing1x")
    h.tocar(h.buscar(nombre="teclaBorrar"))
    h.captura("escrito_y_borrado", esperado="valor «ing1» en el teclado",
              ok=(h.buscar(nombre="valorAlfanumerico") or object()).property("text") == "ing1"
              if h.buscar(nombre="valorAlfanumerico") else None)
    h.tocar(h.buscar(nombre="teclaCancelar"))
    h.captura("cancelado", esperado="teclado cerrado, campo vacío",
              ok=not _hay(h, "tecladoAlfanumerico"))
    # clave incorrecta
    escribir_campo(h, "campoUsuario", USUARIO)
    escribir_campo(h, "campoClave", "malaclave")
    h.tocar(h.buscar(nombre="botonIniciarSesion"))
    ok = h.esperar(lambda: _hay(h, "mensajeLogin"), 4)
    h.captura("clave_incorrecta", esperado="mensaje de usuario o contraseña incorrectos", ok=ok)
    # bloqueo por intentos con el usuario de bloqueo
    for i in range(6):
        escribir_campo(h, "campoUsuario", "bloq1")
        escribir_campo(h, "campoClave", "malaclave")
        h.tocar(h.buscar(nombre="botonIniciarSesion"))
        QTestWait(h, 800)
    m = h.buscar(nombre="mensajeLogin")
    h.captura("bloqueo", esperado="mensaje de usuario bloqueado tras varios intentos",
              ok=m is not None and ("bloque" in (m.property("text") or "").lower()
                                    or "lock" in (m.property("text") or "").lower()))
    # login correcto
    escribir_campo(h, "campoUsuario", USUARIO)
    escribir_campo(h, "campoClave", CLAVE)
    h.tocar(h.buscar(nombre="botonIniciarSesion"))
    ok = h.esperar(lambda: _hay(h, "pantallaOpciones"), 6)
    h.captura("opciones", esperado="Opciones tras el login correcto", ok=ok)
    b = h.buscar(nombre="botonCerrarSesion")
    h.tocar(b)
    ok = h.esperar(lambda: not _hay(h, "pantallaOpciones"), 4)
    h.captura("cerrar_sesion", esperado="sale de Opciones al cerrar sesión", ok=ok)


def QTestWait(h, ms):
    from PySide6.QtTest import QTest
    QTest.qWait(ms)


# ── 3. menú principal ───────────────────────────────────────────────────────

def flujo_menu(h, status):
    despertar(h)
    al_menu(h)
    h.captura("menu", esperado="Menú Principal", ok=_hay(h, "tituloMenu"))
    for tarjeta, destino in (("resumenUltimoCiclo", "ventanaUltimoCiclo"),
                             ("resumenMantenimiento", "ventanaMantenimiento"),
                             ("resumenCiclosHoy", "ventanaCiclosHoy"),
                             ("tarjetaHistorial", "ventanaHistorial"),
                             ("tarjetaInformacion", "panelEquipoMenu")):
        h.tocar(h.buscar(nombre=tarjeta))
        ok = h.esperar(lambda: _hay(h, destino), 4)
        h.captura(tarjeta, esperado=f"abre {destino}", ok=ok)
        # cerrar: botón de volver de la ventana o toque fuera
        cerrar = (h.buscar(nombre="botonVolverHistorial") or h.buscar(nombre="botonCerrarVentana")
                  or h.buscar(texto="Cerrar") or h.buscar(texto="Close"))
        if cerrar is not None:
            h.tocar(cerrar)
        else:
            h.tocar_en(600, 60, "fuera de la ventana")
        ok = h.esperar(lambda: not _hay(h, destino), 3)
        h.captura(tarjeta + "_cerrada", esperado="vuelve al menú", ok=ok)
    h.tocar(h.buscar(nombre="tarjetaReportes"))
    ok = h.esperar(lambda: h.buscar(prefijo="contenidoReportes") is not None, 5)
    h.captura("reportes", esperado="pantalla de Reportes", ok=ok)
    ok = volver_principal(h)
    h.captura("volver", esperado="vuelve a la pantalla principal con Inicio", ok=ok)

# ui_qml/domain/permisos_opciones.py
#
# Secciones de OPCIONES y quién ve cada una (planeacion_opciones_parametros_ciclo.md,
# U-2, U-7 y §4.3). Único lugar con la política de acceso: las pantallas nunca
# comparan roles, solo preguntan puede_ver(seccion, rol).
#
# Política inicial (U-7, Q-1 con la recomendación del documento): las cinco
# secciones técnicas para técnico e ingeniero; admin no (nivel alto
# pero sin conocimientos técnicos). Usuarios para admin e ingeniero (confirmado
# por Cristian el 2026-10-08, planeacion_opciones.md v4 §2); Conectividad para
# admin, técnico e ingeniero (tanda 2026-10-14 §1.6).
# La matriz fina por rol sigue pendiente en el plan de roles: cambiarla aquí no
# requiere tocar la pantalla. Un rol desconocido (p. ej. "operador", defecto de
# la tabla usuarios) o vacío no ve nada.
#
# Mientras el backend no autentique, esta restricción es solo defensa en
# profundidad (R-2).

from dataclasses import dataclass

from autoclave.ui_pyside.services.roles import ROL_ADMIN, ROL_INGENIERO

_TECNICOS = frozenset({"tecnico", "ingeniero"})
_CONECTIVIDAD = frozenset({ROL_ADMIN, "tecnico", ROL_INGENIERO})
_GESTION_USUARIOS = frozenset({ROL_ADMIN, ROL_INGENIERO})
# C1b (tanda 6, decisión 1.5; revierte P2-1 de la tanda 5): el admin VE
# Parámetros del equipo, en solo lectura.
_PARAMETROS_EQUIPO = _TECNICOS | {ROL_ADMIN}
_SOLO_LECTURA_POR_ROL = {"parametros_sistema": frozenset({ROL_ADMIN})}


@dataclass(frozen=True)
class Seccion:
    clave: str          # identificador estable; también la clave de texto en es.json (opciones.secciones)
    icono: str          # archivo de assets/iconos/{color,mono}/
    roles: frozenset    # roles que la ven


# Orden de la navegación lateral: las cinco de AdminMenuView._OPTIONS (U-2) y,
# al final, Usuarios y Conectividad (§5.0). Iconos PROVISIONALES donde el diseñador no
# entregó el definitivo (Entradas / Salidas, Opciones avanzadas).
SECCIONES = (
    Seccion("parametros_ciclo",   "reloj.svg",              _TECNICOS),
    Seccion("parametros_sistema", "engranaje.svg",          _PARAMETROS_EQUIPO),
    Seccion("entradas_salidas",   "sensor_temperatura.svg", _TECNICOS),
    Seccion("mantenimiento",      "mantenimiento.svg",      _TECNICOS),
    Seccion("opciones_avanzadas", "programas.svg",          _TECNICOS),
    Seccion("usuarios",           "usuarios.svg",           _GESTION_USUARIOS),
    Seccion("conectividad",       "conectividad.svg",       _CONECTIVIDAD),
)

_POR_CLAVE = {s.clave: s for s in SECCIONES}


def puede_ver(seccion: str, rol: str | None) -> bool:
    s = _POR_CLAVE.get(seccion)
    return s is not None and bool(rol) and rol in s.roles


def secciones_visibles(rol: str | None) -> list[Seccion]:
    return [s for s in SECCIONES if puede_ver(s.clave, rol)]


# Edición de parámetros (tanda 2026-10-14 §1.6, alineado con el backend:
# guard DISTINTO_DE_CICLO): técnico en cualquier estado distinto de CICLO. El
# backend lo impone; la interfaz solo lo refleja.
ESTADOS_EDICION = frozenset({"PREPARACION", "PREPARADO", "FALLA"})   # P-8 (tanda 6)

# Excepción (Cristian, 2026-10-07): el ingeniero puede modificar cualquier
# sección en cualquier estado; técnico, solo en ESTADOS_EDICION.
# Un cambio hecho con ciclo en curso surte efecto desde la fase activa (lo
# implementa el backend en la Fase 3; la especificación 1, RB-01, debe reflejarlo).
_EDICION_SIEMPRE = frozenset({"ingeniero"})


def edicion_permitida(estado_maquina: str | None, rol: str | None = None,
                      seccion: str | None = None) -> bool:
    if rol in _SOLO_LECTURA_POR_ROL.get(seccion, ()):
        return False
    if rol in _EDICION_SIEMPRE:
        return True
    return estado_maquina in ESTADOS_EDICION


def motivo_solo_lectura(estado_maquina: str | None, rol: str | None = None,
                        seccion: str | None = None) -> str:
    """"" si se puede editar; "rol" si el rol solo ve la sección (admin en
    Parámetros del equipo); "estado" si lo impide el estado de la máquina."""
    if edicion_permitida(estado_maquina, rol, seccion):
        return ""
    return "rol" if rol in _SOLO_LECTURA_POR_ROL.get(seccion, ()) else "estado"


def seccion_inicial(rol: str | None) -> str:
    """Sección en la que aterriza el rol: la primera que puede editar por su
    rol (el admin, en Usuarios); si no hay, la primera visible."""
    visibles = secciones_visibles(rol)
    for s in visibles:
        if rol not in _SOLO_LECTURA_POR_ROL.get(s.clave, ()):
            return s.clave
    return visibles[0].clave if visibles else ""


# Entradas / Salidas (planeacion_opciones_entradas_salidas.md §3, OPC-28). Solo
# técnico e ingeniero entran a la sección (admin no); la UI refleja las reglas
# del backend, que es la autoridad.
_ES_MODO_PRUEBA_ESTADOS = frozenset({"PREPARACION", "PREPARADO", "FALLA"})   # D-ES-07


def puede_modo_prueba(rol: str | None, estado_maquina: str | None) -> bool:
    return rol in _TECNICOS and estado_maquina in _ES_MODO_PRUEBA_ESTADOS


def puede_calibrar(rol: str | None, estado_maquina: str | None) -> bool:
    """Técnico solo fuera de CICLO; ingeniero también en CICLO (aplica de inmediato)."""
    if rol == "ingeniero":
        return True
    return rol == "tecnico" and estado_maquina != "CICLO"


# Parámetros del equipo (O2a, tanda 6). Refleja el backend: cambiar un
# parámetro, técnico e ingeniero fuera de CICLO (409 también al ingeniero);
# idioma, admin e ingeniero, también en ciclo; unidades, solo el ingeniero y
# fuera de ciclo (decisión 1.9, que prevalece sobre O2a).
_EDITA_PARAMETROS_EQUIPO = frozenset({"tecnico", ROL_INGENIERO})
_CAMBIA_IDIOMA = frozenset({ROL_ADMIN, ROL_INGENIERO})
_CAMBIA_UNIDADES = frozenset({ROL_INGENIERO})


def motivo_parametro_equipo(rol: str | None, estado_maquina: str | None) -> str:
    """"" si puede cambiar; "rol" o "ciclo" si no."""
    if rol not in _EDITA_PARAMETROS_EQUIPO:
        return "rol"
    return "ciclo" if estado_maquina == "CICLO" else ""


def motivo_idioma(rol: str | None) -> str:
    return "" if rol in _CAMBIA_IDIOMA else "rol"


def motivo_unidades(rol: str | None, estado_maquina: str | None) -> str:
    if rol not in _CAMBIA_UNIDADES:
        return "rol"
    return "ciclo" if estado_maquina == "CICLO" else ""

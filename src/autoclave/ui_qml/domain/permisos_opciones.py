# ui_qml/domain/permisos_opciones.py
#
# Secciones de OPCIONES y quién ve cada una (planeacion_opciones_parametros_ciclo.md,
# U-2, U-7 y §4.3). Único lugar con la política de acceso: las pantallas nunca
# comparan roles, solo preguntan puede_ver(seccion, rol).
#
# Política inicial (U-7, Q-1 con la recomendación del documento): las cinco
# secciones técnicas para técnico e ingeniero; admin no (nivel alto
# pero sin conocimientos técnicos). Usuarios y Conectividad solo para admin.
# La matriz fina por rol sigue pendiente en el plan de roles: cambiarla aquí no
# requiere tocar la pantalla. Un rol desconocido (p. ej. "operador", defecto de
# la tabla usuarios) o vacío no ve nada.
#
# Mientras el backend no autentique, esta restricción es solo defensa en
# profundidad (R-2).

from dataclasses import dataclass

from autoclave.ui_pyside.services.roles import ROL_ADMIN

_TECNICOS = frozenset({"tecnico", "ingeniero"})
_SOLO_ADMIN = frozenset({ROL_ADMIN})


@dataclass(frozen=True)
class Seccion:
    clave: str          # identificador estable; también la clave de texto en es.json (opciones.secciones)
    icono: str          # archivo de assets/iconos/{color,mono}/
    roles: frozenset    # roles que la ven


# Orden de la navegación lateral: las cinco de AdminMenuView._OPTIONS (U-2) y,
# al final, las dos de admin (§5.0). Iconos PROVISIONALES donde el diseñador no
# entregó el definitivo (Entradas / Salidas, Opciones avanzadas).
SECCIONES = (
    Seccion("parametros_ciclo",   "reloj.svg",              _TECNICOS),
    Seccion("parametros_sistema", "engranaje.svg",          _TECNICOS),
    Seccion("entradas_salidas",   "sensor_temperatura.svg", _TECNICOS),
    Seccion("mantenimiento",      "mantenimiento.svg",      _TECNICOS),
    Seccion("opciones_avanzadas", "programas.svg",          _TECNICOS),
    Seccion("usuarios",           "usuarios.svg",           _SOLO_ADMIN),
    Seccion("conectividad",       "conectividad.svg",       _SOLO_ADMIN),
)

_POR_CLAVE = {s.clave: s for s in SECCIONES}


def puede_ver(seccion: str, rol: str | None) -> bool:
    s = _POR_CLAVE.get(seccion)
    return s is not None and bool(rol) and rol in s.roles


def secciones_visibles(rol: str | None) -> list[Seccion]:
    return [s for s in SECCIONES if puede_ver(s.clave, rol)]


# Edición de parámetros solo en estos estados globales (U-8, especificación 1
# D-1). El backend lo impone; la interfaz solo lo refleja.
ESTADOS_EDICION = frozenset({"PREPARACION", "PREPARADO"})

# Excepción (Cristian, 2026-10-07): el ingeniero puede modificar cualquier
# sección en cualquier estado; técnico, solo en ESTADOS_EDICION.
# Un cambio hecho con ciclo en curso surte efecto desde la fase activa (lo
# implementa el backend en la Fase 3; la especificación 1, RB-01, debe reflejarlo).
_EDICION_SIEMPRE = frozenset({"ingeniero"})


def edicion_permitida(estado_maquina: str | None, rol: str | None = None,
                      seccion: str | None = None) -> bool:
    if rol in _EDICION_SIEMPRE:
        return True
    return estado_maquina in ESTADOS_EDICION

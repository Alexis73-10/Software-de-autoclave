# tests/banco/hor_escenarios_f.py
#
# Revisión visual (RV, etapa B, 19-nov): escenarios que faltaban en los grupos
# A a E (modales y diálogos de Opciones abiertos por un toque real sobre su
# botón). Lo ejecuta tests/banco/hor_capturas.py después de los grupos A a E,
# con _d_abrir, _d_luego, _d_fijar, _d_pulsar y _D_QML (del grupo D) a la vista.
# No es una prueba automática. Nombres con el prefijo f_.
# flake8: noqa  (los nombres los define el guion que hace exec de este archivo)

_F_SECCIONES = {
    # Bitácora: calendario táctil del filtro Desde
    "f_bitacora_calendario": ("bitacora", _d_pulsar("filtroDesde")),
    # Usuarios: modales de eliminar, cambiar rol y restablecer contraseña
    "f_usuarios_eliminar": ("usuarios", _d_luego(_d_fijar("opcionesUsuarios", "seleccionado", "tgutierrez"),
                                                 _d_pulsar("botonEliminarUsuario"))),
    "f_usuarios_rol": ("usuarios", _d_luego(_d_fijar("opcionesUsuarios", "seleccionado", "tgutierrez"),
                                            _d_pulsar("botonCambiarRol"))),
    "f_usuarios_restablecer": ("usuarios", _d_luego(_d_fijar("opcionesUsuarios", "seleccionado", "lperez"),
                                                    _d_pulsar("botonRestablecerClave"))),
    "f_usuarios_desactivar": ("usuarios", _d_luego(_d_fijar("opcionesUsuarios", "seleccionado", "cramirez"),
                                                   _d_pulsar("botonActivoUsuario"))),
}

for _n, (_s, _f) in _F_SECCIONES.items():
    ACCIONES[_n] = (lambda s, f: (lambda win, h: _d_abrir(win, h, s, f)))(_s, _f)
    qml(_n, _D_QML, accion="py:" + _n)

# ui_qml/controllers/usuarios_controller.py
#
# OPCIONES › Usuarios (O2b, tanda 6; mockup 6 aprobado). Pestañas Usuarios /
# Operadores. Usuarios: lista (GET /usuarios), desactivar / reactivar
# (PUT /usuarios/{u}/activo) y restablecer contraseña (POST
# /usuarios/{u}/restablecer_clave). Operadores: lista (GET /operadores),
# agregar (POST /operadores) y desactivar / reactivar (PUT /operadores/{id}/activo).
# Nuevo usuario abre la pantalla existente (Opciones.nuevoUsuarioPulsado).
#
# U11 (tanda 11, D11-6): las cuentas del sistema (Admin, Ingeniero; marca
# `cuenta_sistema` del backend) no se pueden desactivar: la pantalla deshabilita
# ese botón y explica el motivo; restablecer su contraseña sigue disponible.
#
# Permisos (domain/permisos_opciones, decisión 1.9): admin e ingeniero
# modifican; el técnico ve todo deshabilitado con el motivo. La pantalla solo
# los refleja; el backend es la autoridad (403/409).

from urllib.parse import quote

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtQml import qmlRegisterType

from autoclave.ui_qml import sesion_backend
from autoclave.ui_qml.domain import permisos_opciones as permisos

_MENSAJES = {
    "rol_sin_permiso": "gestion_usuarios.err_rol",
    "rol_no_gestionable": "gestion_usuarios.err_rol_objetivo",
    "autodesactivacion": "gestion_usuarios.err_propio",
    "usar_cambio_clave": "gestion_usuarios.err_propia_clave",
    "ultimo_ingeniero": "gestion_usuarios.err_ultimo_ingeniero",
    "cuenta_sistema": "gestion_usuarios.err_cuenta_sistema",
    "operador_existe": "gestion_usuarios.err_operador_existe",
    "validacion": "gestion_usuarios.err_validacion",
    "no_existe": "gestion_usuarios.err_no_existe",
    "sesion_invalida": "opciones.err_identidad",
    sesion_backend.BACKEND_NO_RESPONDE: "opciones.err_sin_respuesta",
}


def mensaje_de(causa: str) -> str:
    return _MENSAJES.get(causa, "opciones.err_generico")


class UsuariosController(QObject):
    datosChanged = Signal()
    mensajeChanged = Signal()
    permisosChanged = Signal()

    def __init__(self, parent=None, sesion=None):
        super().__init__(parent)
        self._sesion = sesion
        self._usuarios: list[dict] = []
        self._operadores: list[dict] = []
        self._gestionables: list[str] = []
        self._mensaje = ""
        self._rol = ""
        self._yo = ""

    def _s(self):
        return self._sesion or sesion_backend.ventana()

    def _fijar_mensaje(self, clave: str) -> None:
        if clave != self._mensaje:
            self._mensaje = clave
            self.mensajeChanged.emit()

    # ── contexto (lo fija la pantalla) ───────────────────────────────────
    def _get_rol(self):
        return self._rol

    def _set_rol(self, v):
        if (v or "") != self._rol:
            self._rol = v or ""
            self.permisosChanged.emit()

    def _get_yo(self):
        return self._yo

    def _set_yo(self, v):
        if (v or "") != self._yo:
            self._yo = v or ""
            self.permisosChanged.emit()

    rol = Property(str, _get_rol, _set_rol, notify=permisosChanged)
    usuarioActual = Property(str, _get_yo, _set_yo, notify=permisosChanged)

    @Property(str, notify=permisosChanged)
    def motivo(self) -> str:
        """"" si el rol puede gestionar; "rol" si no (técnico)."""
        return permisos.motivo_gestion_usuarios(self._rol)

    @Slot(str, result=str)
    def motivoSobre(self, usuario: str) -> str:
        """Motivo por el que la sesión no puede modificar a `usuario`:
        "" | "rol" | "rol_objetivo" | "propio"."""
        if permisos.motivo_gestion_usuarios(self._rol):
            return "rol"
        if usuario and usuario == self._yo:
            return "propio"
        fila = next((u for u in self._usuarios if u.get("usuario") == usuario), None)
        if fila is not None and self._gestionables and fila.get("rol") not in self._gestionables:
            return "rol_objetivo"
        return ""

    # ── carga ────────────────────────────────────────────────────────────
    @Slot()
    def cargar(self) -> None:
        r = self._s().enviar("GET", "/usuarios")
        if r.ok and isinstance(r.datos, dict) and isinstance(r.datos.get("usuarios"), list):
            self._usuarios = [u for u in r.datos["usuarios"] if isinstance(u, dict)]
            g = r.datos.get("gestionables")
            self._gestionables = [x for x in g if isinstance(x, str)] if isinstance(g, list) else []
        else:
            self._fijar_mensaje(mensaje_de(r.causa))
        r = self._s().enviar("GET", "/operadores")
        if r.ok and isinstance(r.datos, dict) and isinstance(r.datos.get("operadores"), list):
            self._operadores = [o for o in r.datos["operadores"] if isinstance(o, dict)]
        self.datosChanged.emit()
        self.permisosChanged.emit()

    @Property("QVariantList", notify=datosChanged)
    def usuarios(self) -> list:
        return [{"usuario": u.get("usuario") or "", "nombre": u.get("nombre") or "",
                 "rol": u.get("rol") or "", "activo": bool(u.get("activo")),
                 "cuentaSistema": u.get("cuenta_sistema") is True,
                 "ultimoIngreso": (u.get("ultimo_ingreso") or "")[:16].replace("T", " ")}
                for u in self._usuarios]

    @Property("QVariantList", notify=datosChanged)
    def operadores(self) -> list:
        return [{"id": int(o.get("id") or 0), "nombre": o.get("nombre") or "",
                 "activo": bool(o.get("activo"))} for o in self._operadores]

    # ── acciones ─────────────────────────────────────────────────────────
    def _tras(self, r) -> bool:
        if r.ok:
            self._fijar_mensaje("")
        self.cargar()                      # sin respuesta el resultado es incierto: se relee
        if not r.ok:
            self._fijar_mensaje(mensaje_de(r.causa))
        return r.ok

    @Slot(str, bool, result=bool)
    def fijarActivo(self, usuario: str, activo: bool) -> bool:
        return self._tras(self._s().enviar("PUT", f"/usuarios/{quote(usuario, safe='')}/activo",
                                           {"activo": bool(activo)}))

    @Slot(str, str, str, result=bool)
    def restablecer(self, usuario: str, clave: str, confirmacion: str) -> bool:
        return self._tras(self._s().enviar("POST", f"/usuarios/{quote(usuario, safe='')}/restablecer_clave",
                                           {"clave": clave, "confirmacion": confirmacion}))

    @Slot(str, result=bool)
    def agregarOperador(self, nombre: str) -> bool:
        if not (nombre or "").strip():
            self._fijar_mensaje(mensaje_de("validacion"))
            return False
        return self._tras(self._s().enviar("POST", "/operadores", {"nombre": nombre}))

    @Slot(int, bool, result=bool)
    def fijarActivoOperador(self, id_: int, activo: bool) -> bool:
        return self._tras(self._s().enviar("PUT", f"/operadores/{int(id_)}/activo",
                                           {"activo": bool(activo)}))

    @Property(str, notify=mensajeChanged)
    def mensaje(self) -> str:
        return self._mensaje

    @Slot()
    def limpiarMensaje(self) -> None:
        self._fijar_mensaje("")


qmlRegisterType(UsuariosController, "Autoclave.Controllers", 1, 0, "UsuariosController")

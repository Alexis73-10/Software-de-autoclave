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
#
# Sin HTTP síncrono en la GUI (AJUSTES 2026-11-02, paso 2 fase 1; piloto):
#   - Activo / desactivado (usuarios y operadores): cambio optimista con
#     reversión (CambioOptimista; claves "usuario:<u>" y "operador:<id>").
#   - Restablecer contraseña y agregar operador: asíncronos; lo mostrado no
#     cambia hasta el 200 y la clave ("clave:<u>", "nuevo_operador") queda
#     en `pendientes` (píldora «guardando…», acción bloqueada) mientras tanto.
#   - Lista: GET asíncrono con `cargando`.
# Los slots devuelven False si falla la validación local; si el resultado
# llegó en el acto (sesión de prueba con solo `enviar`), el `ok` real; si
# quedó en vuelo, True («aceptado»). El desenlace llega por `cambioResuelto`.

from urllib.parse import quote

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtQml import qmlRegisterType

from autoclave.ui_qml import sesion_backend
from autoclave.ui_qml.cambio_optimista import (
    ENVIANDO, SIN_CONFIRMAR, SIN_LECTURA, CambioOptimista)
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
MENSAJE_SIN_CONFIRMAR = "opciones.cambio_sin_confirmar"


def mensaje_de(causa: str) -> str:
    return _MENSAJES.get(causa, "opciones.err_generico")


def _cancelar_al_destruir(sesion, ident):
    return lambda *_: sesion_backend.cancelar_envios(sesion, ident)


class UsuariosController(QObject):
    datosChanged = Signal()
    mensajeChanged = Signal()
    permisosChanged = Signal()
    pendientesChanged = Signal()
    cargandoChanged = Signal()
    # clave del cambio, aceptado, clave i18n del mensaje ("" si aceptado)
    cambioResuelto = Signal(str, bool, str)

    def __init__(self, parent=None, sesion=None):
        super().__init__(parent)
        self._sesion = sesion
        self._usuarios: list[dict] = []
        self._operadores: list[dict] = []
        self._gestionables: list[str] = []
        self._mensaje = ""
        self._revertido = False            # el mensaje es el motivo de una reversión
        self._rol = ""
        self._yo = ""
        self._en_vuelo: dict[str, str] = {}   # acciones B pendientes
        self._gen_carga = 0
        self._cargas: set = set()
        self._resuelto = None              # desenlace síncrono del último slot
        self._opt = CambioOptimista(self._lanzar_activo, self._al_cambiar, self._al_revertir,
                                    self._releer, al_confirmar=self._al_confirmar,
                                    al_pendientes=self.pendientesChanged.emit)
        # sin referencia a self: el destructor de C++ ya está en marcha
        self.destroyed.connect(_cancelar_al_destruir(sesion, id(self)))

    def _s(self):
        return self._sesion or sesion_backend.ventana()

    def _enviar(self, metodo, ruta, cuerpo, al_terminar, al_tardio=None) -> None:
        sesion_backend.enviar_async(self._s(), metodo, ruta, cuerpo, al_terminar,
                                    dueno=self, al_tardio=al_tardio)

    def _fijar_mensaje(self, clave: str, revertido: bool = False) -> None:
        if clave != self._mensaje or revertido != self._revertido:
            self._mensaje = clave
            self._revertido = revertido
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

    # ── estado de los envíos ─────────────────────────────────────────────
    @Property("QVariantMap", notify=pendientesChanged)
    def pendientes(self) -> dict:
        """clave -> "enviando" | "verificando"."""
        return {**self._opt.pendientes(), **self._en_vuelo}

    @Property(bool, notify=cargandoChanged)
    def cargando(self) -> bool:
        return bool(self._cargas)

    def _fijar_cargas(self, cargas: set) -> None:
        antes = bool(self._cargas)
        self._cargas = cargas
        if antes != bool(cargas):
            self.cargandoChanged.emit()

    # ── carga ────────────────────────────────────────────────────────────
    @Slot()
    def cargar(self) -> None:
        self._gen_carga += 1
        gen, marca = self._gen_carga, self._opt.marca()
        self._fijar_cargas({"usuarios", "operadores"})
        self._enviar("GET", "/usuarios", None, lambda r: self._al_cargar(r, gen, marca, "usuarios"))
        self._enviar("GET", "/operadores", None, lambda r: self._al_cargar(r, gen, marca, "operadores"))

    def _al_cargar(self, r, gen, marca, cual) -> None:
        if gen != self._gen_carga:
            return                         # una carga posterior manda
        self._fijar_cargas(self._cargas - {cual})
        lista = r.datos.get(cual) if r.ok and isinstance(r.datos, dict) else None
        if not isinstance(lista, list):
            if cual == "usuarios":
                self._fijar_mensaje(mensaje_de(r.causa))
            self.datosChanged.emit()
            self.permisosChanged.emit()
            return
        nuevos = [dict(x) for x in lista if isinstance(x, dict)]
        viejos = self._usuarios if cual == "usuarios" else self._operadores
        for fila in nuevos:
            clave = self._clave_fila(cual, fila)
            leido = bool(fila.get("activo"))
            if not self._opt.confirmar_lectura(clave, leido, marca):
                # cambio pendiente o lectura lanzada antes del último cambio:
                # se conserva lo que se muestra
                previa = next((v for v in viejos if self._clave_fila(cual, v) == clave), None)
                fila["activo"] = self._opt.mostrar(
                    clave, leido if previa is None else bool(previa.get("activo")))
        if cual == "usuarios":
            self._usuarios = nuevos
            g = r.datos.get("gestionables")
            self._gestionables = [x for x in g if isinstance(x, str)] if isinstance(g, list) else []
        else:
            self._operadores = nuevos
        self.datosChanged.emit()
        self.permisosChanged.emit()

    @staticmethod
    def _clave_fila(cual, fila) -> str:
        if cual == "usuarios":
            return f"usuario:{fila.get('usuario') or ''}"
        try:
            return f"operador:{int(fila.get('id') or 0)}"
        except (TypeError, ValueError):
            return "operador:?"

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

    # ── activo / desactivado: optimista con reversión ────────────────────
    def _fila_de(self, clave):
        cual = "usuarios" if clave.startswith("usuario:") else "operadores"
        lista = self._usuarios if cual == "usuarios" else self._operadores
        return next((f for f in lista if self._clave_fila(cual, f) == clave), None)

    def _lanzar_activo(self, clave, valor, al_terminar) -> None:
        tipo, ident = clave.split(":", 1)
        ruta = (f"/usuarios/{quote(ident, safe='')}/activo" if tipo == "usuario"
                else f"/operadores/{ident}/activo")
        # la respuesta tardía (tras backend_no_responde) no pasa por el cambio
        # optimista: se relee la lista, y la marca protege lo aún pendiente
        self._enviar("PUT", ruta, {"activo": bool(valor)}, al_terminar,
                     al_tardio=lambda _r: self.cargar())

    def _releer(self, clave, al_leer) -> None:
        cual = "usuarios" if clave.startswith("usuario:") else "operadores"

        def leido(r):
            lista = r.datos.get(cual) if r.ok and isinstance(r.datos, dict) else None
            if isinstance(lista, list):
                for fila in lista:
                    if isinstance(fila, dict) and self._clave_fila(cual, fila) == clave:
                        al_leer(bool(fila.get("activo")))
                        return
            al_leer(SIN_LECTURA)
        self._enviar("GET", f"/{cual}", None, leido)

    def _al_cambiar(self, clave, valor) -> None:
        fila = self._fila_de(clave)
        if fila is not None and bool(fila.get("activo")) != bool(valor):
            fila["activo"] = bool(valor)
            self.datosChanged.emit()

    def _al_confirmar(self, clave) -> None:
        self._resuelto = True
        self._fijar_mensaje("")
        self.cambioResuelto.emit(clave, True, "")

    def _al_revertir(self, clave, causa) -> None:
        self._resuelto = False
        if causa == SIN_CONFIRMAR:
            self._fijar_mensaje(MENSAJE_SIN_CONFIRMAR)
            self.cargar()                  # mostrar el estado real del equipo
        else:
            self._fijar_mensaje(mensaje_de(causa), revertido=True)
        self.cambioResuelto.emit(clave, False, self._mensaje)

    def _aplicar(self, clave: str, valor: bool) -> bool:
        fila = self._fila_de(clave)
        self._resuelto = None
        if fila is None:
            self._opt.aplicar(clave, valor)
        else:
            self._opt.aplicar(clave, valor, bool(fila.get("activo")))
        resuelto, self._resuelto = self._resuelto, None
        return True if resuelto is None else resuelto

    @Slot(str, bool, result=bool)
    def fijarActivo(self, usuario: str, activo: bool) -> bool:
        return self._aplicar(f"usuario:{usuario}", bool(activo))

    @Slot(int, bool, result=bool)
    def fijarActivoOperador(self, id_: int, activo: bool) -> bool:
        return self._aplicar(f"operador:{int(id_)}", bool(activo))

    # ── restablecer contraseña, agregar operador: asíncronos ─────────────
    def _accion(self, clave: str, metodo: str, ruta: str, cuerpo: dict) -> bool:
        if clave in self._en_vuelo:
            return False                   # esa acción sigue pendiente
        self._en_vuelo[clave] = ENVIANDO
        self.pendientesChanged.emit()
        self._resuelto = None

        def terminar(r):
            self._en_vuelo.pop(clave, None)
            self.pendientesChanged.emit()
            self._resuelto = r.ok
            if r.ok or r.causa == sesion_backend.BACKEND_NO_RESPONDE:
                self.cargar()              # sin respuesta el resultado es incierto: se relee
            self._fijar_mensaje("" if r.ok else mensaje_de(r.causa))
            self.cambioResuelto.emit(clave, r.ok, self._mensaje)

        self._enviar(metodo, ruta, cuerpo, terminar)
        resuelto, self._resuelto = self._resuelto, None
        return True if resuelto is None else resuelto

    @Slot(str, str, str, result=bool)
    def restablecer(self, usuario: str, clave: str, confirmacion: str) -> bool:
        return self._accion(f"clave:{usuario}", "POST",
                            f"/usuarios/{quote(usuario, safe='')}/restablecer_clave",
                            {"clave": clave, "confirmacion": confirmacion})

    @Slot(str, result=bool)
    def agregarOperador(self, nombre: str) -> bool:
        if not (nombre or "").strip():
            self._fijar_mensaje(mensaje_de("validacion"))
            return False
        return self._accion("nuevo_operador", "POST", "/operadores", {"nombre": nombre})

    @Property(str, notify=mensajeChanged)
    def mensaje(self) -> str:
        return self._mensaje

    @Property(bool, notify=mensajeChanged)
    def mensajeRevertido(self) -> bool:
        """El mensaje es el motivo de un cambio que no se aplicó: la pantalla
        lo muestra dentro de opciones.cambio_revertido."""
        return self._revertido

    @Slot()
    def limpiarMensaje(self) -> None:
        self._fijar_mensaje("")


qmlRegisterType(UsuariosController, "Autoclave.Controllers", 1, 0, "UsuariosController")

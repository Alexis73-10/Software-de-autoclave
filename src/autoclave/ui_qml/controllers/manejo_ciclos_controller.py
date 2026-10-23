# ui_qml/controllers/manejo_ciclos_controller.py
#
# OPCIONES › Opciones avanzadas › Manejo de ciclos (C9, tanda 9, D9-10). Antes
# estos botones vivían en Parámetros del ciclo (O1, tanda 5). Usa los
# endpoints existentes:
#   - GET /programas (lista);
#   - POST /programas/{n}/duplicar {nombre[, crear]} — "Crear" = duplicar un
#     programa existente con un nombre nuevo (Q2); `crear` solo cambia el
#     evento de la bitácora (programa_creado);
#   - PUT /programas/{n}/habilitado {habilitado};
#   - DELETE /programas/{n} (solo personalizados; el backend rechaza los de
#     fábrica y el programa seleccionado).
# El backend es la autoridad (rol, fuera de ciclo, nombre válido y único). Un
# resultado sin respuesta es incierto: la lista se relee siempre.

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtQml import qmlRegisterType

from autoclave.ui_qml import sesion_backend

# Código del backend -> clave del catálogo
_MENSAJES = {
    "estado_no_permitido": "manejo_ciclos.err_estado",
    "rol_sin_permiso": "manejo_ciclos.err_rol",
    "sesion_invalida": "manejo_ciclos.err_identidad",
    "VALOR_INVALIDO": "manejo_ciclos.err_nombre_invalido",
    "nombre_repetido": "manejo_ciclos.err_nombre_repetido",
    "programa_activo": "manejo_ciclos.err_programa_activo",
    "programa_de_fabrica": "manejo_ciclos.err_de_fabrica",
    "PROGRAMA_NO_EDITABLE": "manejo_ciclos.err_no_duplicable",
    "programa_no_encontrado": "manejo_ciclos.err_no_encontrado",
    "programa_existente": "manejo_ciclos.err_generico",
    "BASE_OCUPADA": "manejo_ciclos.err_base_ocupada",
    sesion_backend.BACKEND_NO_RESPONDE: "manejo_ciclos.err_sin_respuesta",
}


def mensaje_de(causa: str) -> str:
    return _MENSAJES.get(causa, "manejo_ciclos.err_generico")


class ManejoCiclosController(QObject):
    programasChanged = Signal()
    mensajeChanged = Signal()

    def __init__(self, parent=None, sesion=None):
        super().__init__(parent)
        self._sesion = sesion
        self._programas: list = []
        self._mensaje = ""
        self._detalle: dict = {}
        self._exito = False

    def _s(self):
        return self._sesion or sesion_backend.ventana()

    def _fijar_mensaje(self, clave: str, detalle: dict | None = None, exito: bool = False) -> None:
        self._mensaje, self._detalle, self._exito = clave, dict(detalle or {}), exito
        self.mensajeChanged.emit()

    # ── lista ────────────────────────────────────────────────────────

    @Slot()
    def cargar(self) -> None:
        r = self._s().enviar("GET", "/programas")
        if not r.ok or not isinstance(r.datos, dict):
            self._programas = []
            self.programasChanged.emit()
            self._fijar_mensaje(mensaje_de(r.causa))
            return
        filas = []
        for p in r.datos.get("programas") or []:
            # solo los programas operables (cycles/user); los de cycles/factory
            # son la referencia de fábrica y no se manejan aquí
            if p.get("origen") != "user":
                continue
            danado = bool(p.get("danado"))
            personalizado = p.get("personalizado") is True
            filas.append({**p, "personalizado": personalizado,
                          "habilitado": p.get("habilitado", True) is not False,
                          "duplicable": not danado,
                          "borrable": personalizado})
        self._programas = filas
        self.programasChanged.emit()

    @Property("QVariantList", notify=programasChanged)
    def programas(self) -> list:
        return self._programas

    @Property("QVariantList", notify=programasChanged)
    def bases(self) -> list:
        """Programas que sirven de base para Crear."""
        return [p for p in self._programas if p["duplicable"]]

    def _nombre(self, numero: int) -> str:
        return next((p.get("nombre", "") for p in self._programas if p.get("numero") == numero), "")

    # ── operaciones ──────────────────────────────────────────────────

    def _tras(self, r, clave_ok: str, detalle: dict) -> bool:
        self.cargar()         # sin respuesta el resultado es incierto: se relee siempre
        if r.ok:
            self._fijar_mensaje(clave_ok, detalle, exito=True)
            return True
        self._fijar_mensaje(mensaje_de(r.causa))
        return False

    def _duplicar(self, numero: int, nombre: str, crear: bool) -> bool:
        nombre = " ".join(str(nombre or "").split())
        if not nombre:
            self._fijar_mensaje("manejo_ciclos.err_nombre_invalido")
            return False
        cuerpo = {"nombre": nombre, "crear": True} if crear else {"nombre": nombre}
        r = self._s().enviar("POST", f"/programas/{int(numero)}/duplicar", cuerpo)
        datos = r.datos if r.ok and isinstance(r.datos, dict) else {}
        return self._tras(r, "manejo_ciclos.ok_creado",
                          {"nombre": datos.get("nombre", nombre), "numero": datos.get("numero")})

    @Slot(int, str, result=bool)
    def crear(self, numero_base: int, nombre: str) -> bool:
        return self._duplicar(numero_base, nombre, True)

    @Slot(int, str, result=bool)
    def duplicar(self, numero: int, nombre: str) -> bool:
        return self._duplicar(numero, nombre, False)

    @Slot(int, bool, result=bool)
    def fijarHabilitado(self, numero: int, habilitado: bool) -> bool:
        nombre = self._nombre(numero)
        r = self._s().enviar("PUT", f"/programas/{int(numero)}/habilitado",
                             {"habilitado": bool(habilitado)})
        clave = "manejo_ciclos.ok_habilitado" if habilitado else "manejo_ciclos.ok_deshabilitado"
        return self._tras(r, clave, {"nombre": nombre})

    @Slot(int, result=bool)
    def borrar(self, numero: int) -> bool:
        nombre = self._nombre(numero)
        r = self._s().enviar("DELETE", f"/programas/{int(numero)}")
        return self._tras(r, "manejo_ciclos.ok_borrado", {"nombre": nombre})

    # ── mensajes ─────────────────────────────────────────────────────

    @Property(str, notify=mensajeChanged)
    def mensaje(self) -> str:
        return self._mensaje

    @Property("QVariantMap", notify=mensajeChanged)
    def detalleMensaje(self) -> dict:
        return self._detalle

    @Property(bool, notify=mensajeChanged)
    def exito(self) -> bool:
        return self._exito

    @Slot()
    def limpiarMensaje(self) -> None:
        self._fijar_mensaje("")


qmlRegisterType(ManejoCiclosController, "Autoclave.Controllers", 1, 0, "ManejoCiclosController")

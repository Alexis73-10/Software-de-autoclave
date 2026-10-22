# ui_qml/controllers/bitacora_controller.py
#
# OPCIONES › Bitácora de auditoría (O2e, tanda 6; mockup 9). Solo lectura:
# GET /audit_log con paginación y filtros Desde (fecha), Usuario y Tipo
# (evento). El backend entrega cada fila con su clave de texto y los valores
# ya en la unidad vigente; la pantalla arma la frase en el idioma vigente.
# Nadie edita ni borra (audit_log es de solo anexar, migración v4).

import re
from urllib.parse import urlencode

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtQml import qmlRegisterType

from autoclave.ui_qml import sesion_backend

_MENSAJES = {
    "rol_sin_permiso": "opciones.err_rol",
    "sesion_invalida": "opciones.err_identidad",
    "validacion": "bitacora.err_fecha",
    sesion_backend.BACKEND_NO_RESPONDE: "opciones.err_sin_respuesta",
}
POR_PAGINA = 12
_FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class BitacoraController(QObject):
    datosChanged = Signal()
    filtrosChanged = Signal()
    mensajeChanged = Signal()

    def __init__(self, parent=None, sesion=None):
        super().__init__(parent)
        self._sesion = sesion
        self._filas: list[dict] = []
        self._pagina = 1
        self._paginas = 1
        self._total = 0
        self._usuarios: list[str] = []
        self._tipos: list[str] = []
        self._desde = ""
        self._usuario = ""
        self._tipo = ""
        self._mensaje = ""

    def _s(self):
        return self._sesion or sesion_backend.ventana()

    def _fijar_mensaje(self, clave: str) -> None:
        if clave != self._mensaje:
            self._mensaje = clave
            self.mensajeChanged.emit()

    def ruta(self) -> str:
        q = {"pagina": self._pagina, "por_pagina": POR_PAGINA}
        if self._desde:
            q["desde"] = self._desde
        if self._usuario:
            q["usuario"] = self._usuario
        if self._tipo:
            q["evento"] = self._tipo
        return "/audit_log?" + urlencode(q)

    @Slot()
    def cargar(self) -> None:
        r = self._s().enviar("GET", self.ruta())
        d = r.datos if r.ok and isinstance(r.datos, dict) else None
        if d is not None and isinstance(d.get("filas"), list):
            self._filas = [f for f in d["filas"] if isinstance(f, dict)]
            self._pagina = int(d.get("pagina") or 1)
            self._paginas = max(1, int(d.get("paginas") or 1))
            self._total = int(d.get("total") or 0)
            self._usuarios = [x for x in d.get("usuarios") or [] if isinstance(x, str)]
            self._tipos = [x for x in d.get("tipos") or [] if isinstance(x, str)]
            self._fijar_mensaje("")
        else:
            self._fijar_mensaje(_MENSAJES.get(r.causa, "opciones.err_generico"))
        self.datosChanged.emit()

    # ── filtros ──────────────────────────────────────────────────────────
    @Slot(str, result=bool)
    def fijarDesde(self, fecha: str) -> bool:
        fecha = (fecha or "").strip()
        if fecha and not _FECHA.match(fecha):
            self._fijar_mensaje("bitacora.err_fecha")
            return False
        self._desde, self._pagina = fecha, 1
        self.filtrosChanged.emit()
        self.cargar()
        return True

    @Slot(str)
    def fijarUsuario(self, usuario: str) -> None:
        self._usuario, self._pagina = usuario or "", 1
        self.filtrosChanged.emit()
        self.cargar()

    @Slot(str)
    def fijarTipo(self, tipo: str) -> None:
        self._tipo, self._pagina = tipo or "", 1
        self.filtrosChanged.emit()
        self.cargar()

    @staticmethod
    def _siguiente(actual: str, opciones: list[str]) -> str:
        ciclo = [""] + opciones
        return ciclo[(ciclo.index(actual) + 1) % len(ciclo)] if actual in ciclo else ""

    @Slot()
    def siguienteUsuario(self) -> None:
        self.fijarUsuario(self._siguiente(self._usuario, self._usuarios))

    @Slot()
    def siguienteTipo(self) -> None:
        self.fijarTipo(self._siguiente(self._tipo, self._tipos))

    @Slot()
    def paginaSiguiente(self) -> None:
        if self._pagina < self._paginas:
            self._pagina += 1
            self.cargar()

    @Slot()
    def paginaAnterior(self) -> None:
        if self._pagina > 1:
            self._pagina -= 1
            self.cargar()

    # ── propiedades ──────────────────────────────────────────────────────
    @Property("QVariantList", notify=datosChanged)
    def filas(self) -> list:
        out = []
        for f in self._filas:
            ts = str(f.get("ts") or "")
            out.append({"id": f.get("id") or 0, "fecha": ts[:10], "hora": ts[11:19],
                        "usuario": str(f.get("usuario") or "") or "sistema",
                        "evento": str(f.get("evento") or ""), "entidad": str(f.get("entidad") or ""),
                        "anterior": str(f.get("anterior") or ""), "nuevo": str(f.get("nuevo") or ""),
                        "claveTexto": str(f.get("clave_texto") or "bitacora.ev_generico")})
        return out

    @Property(int, notify=datosChanged)
    def pagina(self) -> int:
        return self._pagina

    @Property(int, notify=datosChanged)
    def paginas(self) -> int:
        return self._paginas

    @Property(int, notify=datosChanged)
    def total(self) -> int:
        return self._total

    @Property(str, notify=filtrosChanged)
    def desde(self) -> str:
        return self._desde

    @Property(str, notify=filtrosChanged)
    def usuario(self) -> str:
        return self._usuario

    @Property(str, notify=filtrosChanged)
    def tipo(self) -> str:
        return self._tipo

    @Property(str, notify=mensajeChanged)
    def mensaje(self) -> str:
        return self._mensaje


qmlRegisterType(BitacoraController, "Autoclave.Controllers", 1, 0, "BitacoraController")

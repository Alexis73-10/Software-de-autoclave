# ui_qml/controllers/bitacora_controller.py
#
# OPCIONES › Bitácora de auditoría (O2e, tanda 6; mockup 9). Solo lectura:
# GET /audit_log con paginación y filtros. Tanda 17 (BIT-05): rango de fechas
# Desde–Hasta (AAAA-MM-DD, `desde`/`hasta`; el backend trata `hasta` como
# inclusivo; por omisión Hasta = hoy y Desde vacío, como antes), Usuario
# ("Todos" + los de la respuesta `usuarios`) y Tipo por CATEGORÍA (`categoria`,
# las de core.runtime.bitacora.CATEGORIAS o las de la respuesta `categorias`). El backend entrega cada fila con su clave de texto y los valores
# ya en la unidad vigente; la pantalla arma la frase en el idioma vigente.
# Nadie edita ni borra (audit_log es de solo anexar, migración v4).

import re
from datetime import date
from urllib.parse import urlencode

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtQml import qmlRegisterType

from autoclave.core.runtime.bitacora import CATEGORIAS
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
        self._categorias: list[str] = list(CATEGORIAS)
        self._desde = ""
        self._hasta = ""            # "" = hoy (se calcula en cada consulta)
        self._hoy_visto = self._hoy()
        self._usuario = ""
        self._categoria = ""
        self._mensaje = ""

    def _s(self):
        return self._sesion or sesion_backend.ventana()

    def _fijar_mensaje(self, clave: str) -> None:
        if clave != self._mensaje:
            self._mensaje = clave
            self.mensajeChanged.emit()

    @staticmethod
    def _hoy() -> str:
        return date.today().isoformat()

    def _hasta_efectivo(self) -> str:
        return self._hasta or self._hoy()

    def ruta(self) -> str:
        q = {"pagina": self._pagina, "por_pagina": POR_PAGINA}
        if self._desde:
            q["desde"] = self._desde
        q["hasta"] = self._hasta_efectivo()
        if self._usuario:
            q["usuario"] = self._usuario
        if self._categoria:
            q["categoria"] = self._categoria
        return "/audit_log?" + urlencode(q)

    @Slot()
    def cargar(self) -> None:
        # R4 (V17-s4-04): si cambió el día, `hoy` y `hasta` (por omisión) se refrescan
        if self._hoy() != self._hoy_visto:
            self._hoy_visto = self._hoy()
            self.filtrosChanged.emit()
        r = self._s().enviar("GET", self.ruta())
        d = r.datos if r.ok and isinstance(r.datos, dict) else None
        if d is not None and isinstance(d.get("filas"), list):
            self._filas = [f for f in d["filas"] if isinstance(f, dict)]
            self._pagina = int(d.get("pagina") or 1)
            self._paginas = max(1, int(d.get("paginas") or 1))
            self._total = int(d.get("total") or 0)
            self._usuarios = [x for x in d.get("usuarios") or [] if isinstance(x, str)]
            self._tipos = [x for x in d.get("tipos") or [] if isinstance(x, str)]
            cats = [x for x in d.get("categorias") or [] if isinstance(x, str)]
            # el desplegable ofrece siempre las 5 (BIT-05), en su orden
            self._categorias = [c for c in CATEGORIAS if not cats or c in cats] or list(CATEGORIAS)
            self._fijar_mensaje("")
        else:
            self._fijar_mensaje(_MENSAJES.get(r.causa, "opciones.err_generico"))
        self.datosChanged.emit()

    # ── filtros ──────────────────────────────────────────────────────────
    @staticmethod
    def _valida(fecha: str) -> bool:
        if not _FECHA.match(fecha):
            return False
        try:
            date.fromisoformat(fecha)
        except ValueError:
            return False
        return True

    @Slot(str, result=bool)
    def fijarDesde(self, fecha: str) -> bool:
        fecha = (fecha or "").strip()
        if fecha and not self._valida(fecha):
            self._fijar_mensaje("bitacora.err_fecha")
            return False
        if fecha and fecha > self._hasta_efectivo():
            self._fijar_mensaje("bitacora.err_rango")
            return False
        self._desde, self._pagina = fecha, 1
        self.filtrosChanged.emit()
        self.cargar()
        return True

    @Slot(str, result=bool)
    def fijarHasta(self, fecha: str) -> bool:
        """BIT-05: "" vuelve al defecto (hoy)."""
        fecha = (fecha or "").strip()
        if fecha and not self._valida(fecha):
            self._fijar_mensaje("bitacora.err_fecha")
            return False
        if self._desde and self._desde > (fecha or self._hoy()):
            self._fijar_mensaje("bitacora.err_rango")
            return False
        self._hasta, self._pagina = fecha, 1
        self.filtrosChanged.emit()
        self.cargar()
        return True

    @Slot(str)
    def fijarUsuario(self, usuario: str) -> None:
        self._usuario, self._pagina = usuario or "", 1
        self.filtrosChanged.emit()
        self.cargar()

    @Slot(str)
    def fijarCategoria(self, categoria: str) -> None:
        """BIT-05: "" = todas; una de CATEGORIAS."""
        categoria = categoria or ""
        if categoria and categoria not in CATEGORIAS:
            categoria = ""
        self._categoria, self._pagina = categoria, 1
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
        """Siguiente categoría (BIT-05; antes, el siguiente evento)."""
        self.fijarCategoria(self._siguiente(self._categoria, self._categorias))

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
    def hasta(self) -> str:
        """Fecha Hasta vigente (hoy si no se eligió otra)."""
        return self._hasta_efectivo()

    @Property(bool, notify=filtrosChanged)
    def hastaEsHoy(self) -> bool:
        return self._hasta == ""

    @Property(str, notify=filtrosChanged)
    def hoy(self) -> str:
        return self._hoy()

    @Property(str, notify=filtrosChanged)
    def categoria(self) -> str:
        return self._categoria

    @Property(str, notify=filtrosChanged)
    def tipo(self) -> str:
        """Compatibilidad: la categoría elegida (BIT-05)."""
        return self._categoria

    @Property("QVariantList", notify=datosChanged)
    def usuarios(self) -> list:
        return list(self._usuarios)

    @Property("QVariantList", notify=datosChanged)
    def categorias(self) -> list:
        return list(self._categorias)

    @Property(str, notify=mensajeChanged)
    def mensaje(self) -> str:
        return self._mensaje


qmlRegisterType(BitacoraController, "Autoclave.Controllers", 1, 0, "BitacoraController")

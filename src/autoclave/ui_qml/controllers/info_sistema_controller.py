# ui_qml/controllers/info_sistema_controller.py
#
# OPCIONES › Información del sistema (O2d, tanda 6; mockup 8 aprobado). Solo
# lectura, en grupos de clave–valor (GET /system/info):
#   - Equipo: modelo, capacidad nominal y tipo de carga (M1, tanda 7; "—" en
#     perfiles anteriores), tipo de equipo (E2, tanda 8: Hospitalario o
#     Laboratorio), serie, fecha de instalación, fuente de vapor.
#   - Software y tarjeta: versión del software, firmware e ID de la tarjeta y,
#     desde la tanda 19 (MOD-01), el enlace de E/S activo (Modbus o serial).
#   - Uso y mantenimiento: ciclos realizados, próximo mantenimiento (fecha y
#     ciclos restantes).
#   - Configuración vigente: idioma, unidades, impresora y red (chips).
# Un dato sin fuente se muestra "—"; nunca "No disponible" si el dato existe.

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtQml import qmlRegisterType

from autoclave.installation.equipment import EquipmentClass
from autoclave.ui_qml import sesion_backend
from autoclave.ui_qml.domain import resumen_sistema as dominio

_MENSAJES = {sesion_backend.BACKEND_NO_RESPONDE: "opciones.err_sin_respuesta"}

# Tanda 19 (MOD-01): enlaces de E/S con texto en equipo.enlace_io_<enlace>
ENLACES_IO = ("modbus", "serial")
GRUPOS = ("equipo", "software", "uso", "configuracion")
ESTADOS_IMPRESORA = ("lista", "no_instalada", "desconectada", "sin_papel", "error", "deshabilitada",
                     "desconocido")
# E2 (tanda 8; D8-0): la clase se muestra con su nombre del catálogo
# (equipo.clase_*: "Hospitalario"/"Laboratorio"), nunca el valor interno
CLASES_EQUIPO = tuple(c.value for c in EquipmentClass)
CLAVES_FILA = ("modelo", "capacidad", "tipo_carga", "clase", "serie", "fecha_instalacion", "fuente_vapor", "version_software", "firmware",
               "id_tarjeta", "enlace_io", "ciclos_realizados", "proximo_mantenimiento", "ciclos_restantes", "idioma",
               "unidades", "impresora", "red")


def _txt(v) -> str:
    return "" if v is None or v == "" else str(v)


def grupos_de(d: dict) -> list[dict]:
    """[{grupo, filas: [{clave, valor, valorClave, chip}]}] a partir de /system/info.
    valorClave: clave de catálogo (texto en el idioma vigente) en lugar de valor;
    chip: "ok" | "aviso" | "" para los estados de impresora y red."""
    d = d if isinstance(d, dict) else {}
    eq = d.get("equipo") if isinstance(d.get("equipo"), dict) else {}
    sw = d.get("software") if isinstance(d.get("software"), dict) else {}
    uso = d.get("uso") if isinstance(d.get("uso"), dict) else {}
    cfg = d.get("configuracion") if isinstance(d.get("configuracion"), dict) else {}
    mant = dominio.mantenimiento_presentable(uso.get("mantenimiento")
                                             if isinstance(uso.get("mantenimiento"), dict) else None)

    def fila(clave, valor="", valor_clave="", chip=""):
        return {"clave": clave, "valor": _txt(valor), "valorClave": valor_clave, "chip": chip}

    vapor = _txt(eq.get("fuente_vapor"))
    capacidad = eq.get("capacidad_litros")
    carga = eq.get("tipo_carga")
    clase = eq.get("clase")
    unidades = cfg.get("unidades") if isinstance(cfg.get("unidades"), dict) else {}
    impresora = _txt(cfg.get("impresora"))       # deshabilitada | lista | <otro estado>
    if impresora and impresora not in ESTADOS_IMPRESORA:
        impresora = "desconocido"
    red = _txt(cfg.get("red"))                   # conectada | sin_red
    proximo = mant["proximo"] if uso.get("mantenimiento") else ""
    if mant.get("vencido"):
        proximo = "!"
    return [
        {"grupo": "equipo", "filas": [
            fila("modelo", eq.get("modelo")),
            fila("capacidad", f"{capacidad} L" if type(capacidad) is int else ""),
            fila("tipo_carga", "", f"info_sistema.carga_{carga}" if carga in ("V", "H") else ""),
            fila("clase", "", f"equipo.clase_{clase}" if clase in CLASES_EQUIPO else ""),
            fila("serie", eq.get("serie")),
            fila("fecha_instalacion", _txt(eq.get("instalacion"))[:10]),
            fila("fuente_vapor", "", f"info_sistema.vapor_{vapor}" if vapor else ""),
        ]},
        {"grupo": "software", "filas": [
            fila("version_software", sw.get("version")),
            fila("firmware", sw.get("firmware")),
            fila("id_tarjeta", sw.get("id_tarjeta")),
            fila("enlace_io", "", f"equipo.enlace_io_{sw.get('enlace_io')}"
                 if sw.get("enlace_io") in ENLACES_IO else ""),
        ]},
        {"grupo": "uso", "filas": [
            fila("ciclos_realizados", uso.get("ciclos")),
            fila("proximo_mantenimiento", "" if proximo == "!" else proximo,
                 "menu.vencido" if proximo == "!" else ""),
            fila("ciclos_restantes", mant["ciclos_restantes"] if uso.get("mantenimiento") else ""),
        ]},
        {"grupo": "configuracion", "filas": [
            fila("idioma", "", f"info_sistema.idioma_{cfg.get('idioma')}" if cfg.get("idioma") in ("es", "en") else ""),
            fila("unidades", " / ".join(x for x in (_txt(unidades.get("temperatura")) and
                                                    "°" + _txt(unidades.get("temperatura")),
                                                    _txt(unidades.get("presion"))) if x)),
            fila("impresora", "", f"info_sistema.impresora_{impresora}" if impresora else "",
                 "ok" if impresora == "lista" else ("aviso" if impresora else "")),
            fila("red", "", f"info_sistema.red_{red}" if red else "",
                 "ok" if red == "conectada" else ("aviso" if red else "")),
        ]},
    ]


class InfoSistemaController(QObject):
    datosChanged = Signal()
    mensajeChanged = Signal()

    def __init__(self, parent=None, sesion=None):
        super().__init__(parent)
        self._sesion = sesion
        self._grupos = grupos_de({})
        self._mensaje = ""

    def _s(self):
        return self._sesion or sesion_backend.ventana()

    @Slot()
    def cargar(self) -> None:
        r = self._s().enviar("GET", "/system/info")
        nuevo = ""
        if r.ok and isinstance(r.datos, dict):
            self._grupos = grupos_de(r.datos)
        else:
            nuevo = _MENSAJES.get(r.causa, "opciones.err_generico")
        if nuevo != self._mensaje:
            self._mensaje = nuevo
            self.mensajeChanged.emit()
        self.datosChanged.emit()

    @Property("QVariantList", notify=datosChanged)
    def grupos(self) -> list:
        return self._grupos

    @Property(str, notify=mensajeChanged)
    def mensaje(self) -> str:
        return self._mensaje


qmlRegisterType(InfoSistemaController, "Autoclave.Controllers", 1, 0, "InfoSistemaController")

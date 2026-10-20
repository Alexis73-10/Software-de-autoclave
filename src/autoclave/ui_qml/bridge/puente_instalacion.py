# ui_qml/bridge/puente_instalacion.py
#
# Puente real del asistente de instalación QML (Pantallas/Instalacion.qml;
# contrato en planeacion_menu_instalacion_ui.md §5; tanda 2026-10-14 T9,
# ARR-02 / MIG-07). Único asistente de instalación (el anterior se retiró en R1
# de la tanda 2):
#
#   clases                         capacidades por clase (get_capabilities)
#   validarCodigo(serie, codigo)   código de activación del día (activation.py)
#   instalar(perfil) -> {ok, error}
#
# instalar() vuelve a validar todo lo que la pantalla ya validó (la UI no es
# la barrera): código del día, clase, puertas y enfriamiento dentro de la
# capacidad de la clase, tipo de puerta, fuente de vapor y la sonda de cámara
# obligatoria. Nunca sobrescribe un perfil válido. Un perfil existente pero
# inválido no se borra: se aparta como installation_profile.json.invalido-<fecha>.
# Sin diálogo de clave de fabricante (decisión 1.7).

import logging
import os
from datetime import datetime

from PySide6.QtCore import Property, QObject, Signal, Slot

from autoclave.devices.puertas.door_type import DoorType
from autoclave.installation import storage
from autoclave.installation.activation import validate_installation_code
from autoclave.installation.bootstrap import get_installation_profile
from autoclave.installation.clock_guard import ClockTamperedError
from autoclave.installation.equipment import EquipmentClass, get_capabilities
from autoclave.installation.profile import (SUPPLY_INPUT_KEYS, InstallationProfile, Role,
                                            normalizar_supply_inputs,
                                            normalizar_temperature_probes)

logger = logging.getLogger(__name__)

FUENTES_VAPOR = ("generator", "boiler", "mixed")
SONDA_OBLIGATORIA = "temp_camara"


def clases_disponibles() -> list[dict]:
    """Capacidades por clase, con los nombres del contrato de la pantalla."""
    salida = []
    for ec in EquipmentClass:
        cap = get_capabilities(ec)
        salida.append({
            "valor": ec.value,
            "vacio": cap.has_vacuum,
            "chaqueta": cap.has_full_jacket,
            "liquidos": cap.has_liquids,
            "puertasMax": cap.door_count_max,
            "enfriamientoMax": cap.cooling_level_max,
        })
    return salida


def requiere_instalacion() -> bool:
    """True si falta el perfil o es inválido (ARR-02). Un reloj alterado no
    abre el asistente: lo informa el arranque (ARR_RELOJ, bloqueante)."""
    try:
        return get_installation_profile() is None
    except ClockTamperedError:
        return False
    except Exception:
        # SAF-06 de T9: JSON con raíz que no es objeto, permisos, etc.: perfil inválido
        logger.exception("Perfil de instalación ilegible: se abre el asistente")
        return True


def _entero(datos: dict, clave: str) -> int:
    valor = datos.get(clave)
    if isinstance(valor, bool):
        raise ValueError(clave)
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    if not isinstance(valor, int):
        raise ValueError(clave)
    return valor


def construir_perfil(datos: dict, codigo: str, ahora: datetime | None = None,
                     validar_codigo=validate_installation_code) -> InstallationProfile:
    """Valida los datos de la pantalla y arma el perfil (bloqueado). Lanza
    ValueError con el motivo en español."""
    serie = str(datos.get("serial_number") or "").strip().upper()
    if not serie:
        raise ValueError("Número de serie vacío")
    if not validar_codigo(serie, str(codigo or "")):
        raise ValueError("Código de activación inválido")
    modelo = str(datos.get("model_id") or "").strip()
    if not modelo:
        raise ValueError("Modelo vacío")
    try:
        clase = EquipmentClass(datos.get("equipment_class"))
    except ValueError:
        raise ValueError("Tipo de equipo inválido") from None
    cap = get_capabilities(clase)
    try:
        puertas = _entero(datos, "door_count")
        puerta_pc = _entero(datos, "door_id")
        enfriamiento = _entero(datos, "cooling_level")
    except ValueError as e:
        raise ValueError(f"Valor inválido: {e}") from None
    if not 1 <= puertas <= cap.door_count_max:
        raise ValueError(f"Número de puertas fuera de la capacidad del equipo (1 a {cap.door_count_max})")
    if puertas == 1:
        puerta_pc = 1
    if not 1 <= puerta_pc <= puertas:
        raise ValueError("Puerta de este PC inválida")
    if not 0 <= enfriamiento <= cap.cooling_level_max:
        raise ValueError(f"Nivel de enfriamiento fuera de la capacidad del equipo (0 a {cap.cooling_level_max})")
    try:
        tipo_puerta = DoorType(datos.get("door_type"))
    except ValueError:
        raise ValueError("Tipo de puerta inválido") from None
    vapor = datos.get("vapor_source")
    if vapor not in FUENTES_VAPOR:
        raise ValueError("Fuente de vapor inválida")
    suministros = datos.get("supply_inputs") or {}
    sondas = datos.get("temperature_probes") or {}
    if not isinstance(suministros, dict) or not isinstance(sondas, dict):
        raise ValueError("Suministros o sondas inválidos")
    suministros = {k: suministros.get(k, True) is not False for k in SUPPLY_INPUT_KEYS}
    sondas = normalizar_temperature_probes({k: v is not False for k, v in sondas.items()})
    sondas[SONDA_OBLIGATORIA] = True      # la sonda de cámara no se puede desactivar
    # Hora local sin zona (TMG-01 de T9): clock_guard compara date.today()
    # (local) con created_at.date(); en UTC, instalar después de las 19:00 en
    # Colombia daba ARR_RELOJ hasta la medianoche
    ahora = ahora or datetime.now()
    return InstallationProfile(
        machine_id=f"ACV-{ahora.strftime('%Y')}-{serie}",
        model_id=modelo,
        serial_number=serie,
        equipment_class=clase,
        door_count=puertas,
        door_type=tipo_puerta,
        cooling_level=enfriamiento,
        door_id=puerta_pc,
        role=Role.OPERATOR_FRONT,
        created_at=ahora,
        locked=True,
        supply_inputs=normalizar_supply_inputs(suministros),
        temperature_probes=sondas,
        vapor_source=vapor,
    )


def escribir_perfil(perfil: InstallationProfile, ahora: datetime | None = None) -> None:
    """Escribe el perfil. Nunca sobrescribe uno válido; uno inválido se
    aparta con fecha (no se borra)."""
    if storage.exists():
        try:
            valido = get_installation_profile() is not None
        except ClockTamperedError:
            valido = True       # el perfil existe y es legible: no se toca
        if valido:
            raise RuntimeError("El equipo ya tiene un perfil de instalación válido")
        sello = (ahora or datetime.now()).strftime("%Y%m%d-%H%M%S")
        destino = storage.INSTALLATION_FILE.with_name(
            f"{storage.INSTALLATION_FILE.name}.invalido-{sello}")
        os.replace(storage.INSTALLATION_FILE, destino)
        logger.warning("Perfil de instalación inválido apartado en %s", destino.name)
    storage.save(perfil)


class PuenteInstalacion(QObject):
    instalado = Signal()

    def __init__(self, parent=None, validar_codigo=validate_installation_code):
        super().__init__(parent)
        self._validar_codigo = validar_codigo
        self._clases = clases_disponibles()
        self._codigo = ""

    @Property("QVariantList", constant=True)
    def clases(self) -> list:
        return self._clases

    @Slot(str, str, result=bool)
    def validarCodigo(self, serie: str, codigo: str) -> bool:
        ok = bool(self._validar_codigo(serie.strip().upper(), codigo))
        if ok:
            self._codigo = codigo
        else:
            logger.warning("Código de activación inválido para la serie '%s'", serie.strip().upper())
        return ok

    @Slot("QVariantMap", result="QVariantMap")
    def instalar(self, datos) -> dict:
        try:
            perfil = construir_perfil(dict(datos or {}), self._codigo,
                                      validar_codigo=self._validar_codigo)
            escribir_perfil(perfil)
        except (ValueError, RuntimeError, OSError) as e:
            logger.error("Instalación rechazada: %s", e)
            return {"ok": False, "error": str(e)}
        logger.info("Instalación completada para la serie '%s'", perfil.serial_number)
        self.instalado.emit()
        return {"ok": True, "error": ""}

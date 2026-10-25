# ui_qml/bridge/puente_instalacion.py
#
# Puente real del asistente de instalación QML (Pantallas/Instalacion.qml;
# contrato en planeacion_menu_instalacion_ui.md §5; tanda 2026-10-14 T9,
# ARR-02 / MIG-07). Único asistente de instalación (el anterior se retiró en R1
# de la tanda 2):
#
#   clases                         capacidades por clase (get_capabilities);
#                                  solo piso y piso_lab (M1, AM-3)
#   validarCodigo(serie, codigo)   código de activación del día (activation.py)
#   calcularModelo(clase, litros, carga, puertas) -> nombre o "" (vista previa)
#   validarContrasenas(admin, conf_admin, ingeniero, conf_ingeniero) -> {campo: error_ui}
#   instalar(perfil) -> {ok, error}   (perfil.contrasenas: las 4 de arriba)
#
# instalar() vuelve a validar todo lo que la pantalla ya validó (la UI no es
# la barrera): código del día, clase, puertas y enfriamiento dentro de la
# capacidad de la clase, tipo de puerta, fuente de vapor y la sonda de cámara
# obligatoria. Nunca sobrescribe un perfil válido. Un perfil existente pero
# inválido no se borra: se aparta como installation_profile.json.invalido-<fecha>.
# Sin diálogo de clave de fabricante (decisión 1.7).
#
# LIC-02 (licencia L0): paso obligatorio de contraseñas de Admin e Ingeniero,
# también en reinstalación. Reglas de contraseña nueva del backend
# (validacion_usuario), distintas de las semilla y entre sí. instalar() las
# guarda en la base (hash, debe_cambiar_clave=0, auditoría) ANTES de escribir
# el perfil: si el guardado falla, el asistente no termina. El asistente
# corre sin backend (exe_unico), así que escribe la base directamente.
#
# M1 (tanda 7, planeacion_asistente_modelo.md): el puente recibe
# capacidad_litros y tipo_carga y calcula model_id él mismo con
# installation/modelo.py; ignora cualquier model_id que mande la pantalla
# (AM-6: no hay texto libre). Una clase de mesa se rechaza con un error i18n.

import logging
import os
from datetime import datetime

from PySide6.QtCore import Property, QObject, Signal, Slot

from autoclave.devices.puertas.door_type import DoorType
from autoclave.installation import storage
from autoclave.installation.activation import validate_installation_code
from autoclave.installation.bootstrap import get_installation_profile
from autoclave.installation.clock_guard import ClockTamperedError
from autoclave import i18n
from autoclave.installation.equipment import EquipmentClass, get_capabilities
from autoclave.installation.modelo import (CAPACIDAD_MAX, CAPACIDAD_MIN, TIPOS_CARGA,
                                           calcular_modelo, clase_instalable)
from autoclave.installation.profile import (SUPPLY_INPUT_KEYS, InstallationProfile, Role,
                                            normalizar_supply_inputs,
                                            normalizar_temperature_probes)
from autoclave.backend.contrasenas import hash_password
from autoclave.services.domain.logging.db_manager import es_clave_semilla
from autoclave.ui_pyside.services.validacion_usuario import (codigo_clave, codigo_confirmacion,
                                                            error_ui)

logger = logging.getLogger(__name__)

FUENTES_VAPOR = ("generator", "boiler", "mixed")
SONDA_OBLIGATORIA = "temp_camara"

# LIC-02: campos del paso de contraseñas (mismos nombres en la pantalla)
CAMPOS_CONTRASENAS = ("clave_admin", "confirmacion_admin",
                      "clave_ingeniero", "confirmacion_ingeniero")
COD_SEMILLA = "semilla"      # es la contraseña de fábrica de alguna de las dos cuentas
COD_IGUALES = "iguales"      # la de Ingeniero es igual a la de Admin


def clases_disponibles() -> list[dict]:
    """Capacidades por clase, con los nombres del contrato de la pantalla."""
    salida = []
    for ec in EquipmentClass:
        if not clase_instalable(ec):        # AM-3: los equipos de mesa no se instalan
            continue
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
    try:
        clase = EquipmentClass(datos.get("equipment_class"))
    except ValueError:
        raise ValueError("Tipo de equipo inválido") from None
    if not clase_instalable(clase):
        raise ValueError(i18n.t("instalacion.error_clase_fuera_alcance"))
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
    try:
        capacidad = _entero(datos, "capacidad_litros")
    except ValueError:
        raise ValueError(i18n.t("instalacion.error_capacidad")) from None
    if not CAPACIDAD_MIN <= capacidad <= CAPACIDAD_MAX:
        raise ValueError(i18n.t("instalacion.error_capacidad"))
    carga = datos.get("tipo_carga")
    if not isinstance(carga, str) or carga not in TIPOS_CARGA:
        raise ValueError(i18n.t("instalacion.error_tipo_carga"))
    # El nombre lo calcula el software (AM-6): el model_id de la pantalla se ignora
    modelo = calcular_modelo(clase, capacidad, carga, puertas)
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
        capacidad_litros=capacidad,
        tipo_carga=carga,
    )


def errores_contrasenas(claves: dict, es_semilla=es_clave_semilla) -> dict[str, str]:
    """LIC-02: {campo: código} del paso de contraseñas; vacío si es válido.
    Reglas de contraseña nueva del backend (obligatoria, longitud,
    confirmación), más: ninguna es la contraseña semilla de alguna de las dos
    cuentas, y la de Ingeniero es distinta de la de Admin."""
    claves = {c: str((claves or {}).get(c) or "") for c in CAMPOS_CONTRASENAS}
    admin, ingeniero = claves["clave_admin"], claves["clave_ingeniero"]
    errores = {}
    for campo, clave in (("clave_admin", admin), ("clave_ingeniero", ingeniero)):
        codigo = codigo_clave(clave)
        if codigo is None and campo == "clave_ingeniero" and clave == admin:
            codigo = COD_IGUALES
        if codigo is None and es_semilla(clave):
            codigo = COD_SEMILLA
        if codigo:
            errores[campo] = codigo
    for campo, clave in (("confirmacion_admin", admin), ("confirmacion_ingeniero", ingeniero)):
        codigo = codigo_confirmacion(claves[campo], clave)
        if codigo:
            errores[campo] = codigo
    return errores


def _abrir_bd():
    from autoclave.services.domain.logging.db_manager import DbManager
    return DbManager()


def fijar_contrasenas(claves: dict, abrir_bd=_abrir_bd) -> list[str]:
    """LIC-02: guarda el hash de las dos contraseñas (ya validadas), baja
    debe_cambiar_clave y audita, en una sola transacción. Lanza si falla."""
    hashes = {"admin": hash_password(claves["clave_admin"]),
              "ingeniero": hash_password(claves["clave_ingeniero"])}
    db = abrir_bd()
    try:
        return db.fijar_claves_instalacion(hashes)
    finally:
        db.close()


def _hay_perfil_valido() -> bool:
    if not storage.exists():
        return False
    try:
        return get_installation_profile() is not None
    except ClockTamperedError:
        return True       # el perfil existe y es legible: no se toca


def escribir_perfil(perfil: InstallationProfile, ahora: datetime | None = None) -> None:
    """Escribe el perfil. Nunca sobrescribe uno válido; uno inválido se
    aparta con fecha (no se borra)."""
    if storage.exists():
        if _hay_perfil_valido():
            raise RuntimeError("El equipo ya tiene un perfil de instalación válido")
        sello = (ahora or datetime.now()).strftime("%Y%m%d-%H%M%S")
        destino = storage.INSTALLATION_FILE.with_name(
            f"{storage.INSTALLATION_FILE.name}.invalido-{sello}")
        os.replace(storage.INSTALLATION_FILE, destino)
        logger.warning("Perfil de instalación inválido apartado en %s", destino.name)
    storage.save(perfil)


class PuenteInstalacion(QObject):
    instalado = Signal()

    def __init__(self, parent=None, validar_codigo=validate_installation_code,
                 abrir_bd=_abrir_bd, es_semilla=es_clave_semilla):
        super().__init__(parent)
        self._validar_codigo = validar_codigo
        self._abrir_bd = abrir_bd
        self._es_semilla = es_semilla
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

    @Slot(str, "QVariant", str, int, result=str)
    def calcularModelo(self, clase: str, capacidad, carga: str, puertas: int) -> str:
        """Vista previa del nombre (paso Cámara). "" si falta o sobra un dato:
        la pantalla muestra "—". Misma regla que instalar()."""
        if isinstance(capacidad, float) and capacidad.is_integer():
            capacidad = int(capacidad)
        try:
            return calcular_modelo(clase, capacidad, carga, puertas)
        except ValueError:
            return ""

    @Slot(str, str, str, str, result="QVariantMap")
    def validarContrasenas(self, clave_admin: str, confirmacion_admin: str,
                           clave_ingeniero: str, confirmacion_ingeniero: str) -> dict:
        """LIC-02: {campo: {clave, valores}} (error_ui) para pintar cada campo;
        vacío si todo es válido. Nunca registra las contraseñas."""
        errores = errores_contrasenas(
            {"clave_admin": clave_admin, "confirmacion_admin": confirmacion_admin,
             "clave_ingeniero": clave_ingeniero, "confirmacion_ingeniero": confirmacion_ingeniero},
            es_semilla=self._es_semilla)
        return {campo: error_ui("clave", codigo) for campo, codigo in errores.items()}

    @Slot("QVariantMap", result="QVariantMap")
    def instalar(self, datos) -> dict:
        datos = dict(datos or {})
        claves = datos.pop("contrasenas", None)
        claves = dict(claves) if hasattr(claves, "keys") else {}
        try:
            perfil = construir_perfil(datos, self._codigo, validar_codigo=self._validar_codigo)
            if errores_contrasenas(claves, es_semilla=self._es_semilla):
                raise ValueError(i18n.t("instalacion.error_contrasenas"))
            if _hay_perfil_valido():
                raise RuntimeError("El equipo ya tiene un perfil de instalación válido")
            # LIC-02: primero las contraseñas; sin ellas no hay perfil
            usuarios = fijar_contrasenas(claves, abrir_bd=self._abrir_bd)
            logger.info("Contraseñas fijadas en la instalación: %s", ", ".join(usuarios))
            escribir_perfil(perfil)
        except (ValueError, RuntimeError, OSError) as e:
            logger.error("Instalación rechazada: %s", e)
            return {"ok": False, "error": str(e)}
        except Exception as e:
            # p. ej. sqlite3.Error o BdBloqueadaError al guardar las contraseñas
            logger.exception("Instalación rechazada: no se pudieron guardar las contraseñas")
            return {"ok": False, "error": i18n.t("instalacion.error_guardar_contrasenas", detalle=str(e))}
        logger.info("Instalación completada para la serie '%s'", perfil.serial_number)
        self.instalado.emit()
        return {"ok": True, "error": ""}

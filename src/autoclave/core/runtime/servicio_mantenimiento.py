# core/runtime/servicio_mantenimiento.py
#
# Servicio de mantenimiento (M1, tanda 3): une la configuración de intervalos
# (data/mantenimiento.json, escritura atómica), el registro en la base
# (tabla `mantenimientos`), la fecha de instalación (perfil), el contador de
# ciclos persistente y el aviso no bloqueante MANTENIMIENTO_VENCIDO.
#
# Nunca interviene en un ciclo: solo informa. Sin base de datos el último
# mantenimiento se desconoce y se calcula desde la instalación.

import json
import logging
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from autoclave.core.runtime import mantenimiento as m
from autoclave.state_machine.alarms.catalogo import MANTENIMIENTO_VENCIDO
from autoclave.utils.archivos import escribir_texto_atomico

logger = logging.getLogger(__name__)

TIPOS = ("preventivo", "correctivo", "calibracion", "otro")
OBSERVACIONES_MAX = 500


class ErrorMantenimiento(Exception):
    """Rechazo con código y motivo para el backend."""

    def __init__(self, codigo: str, motivo: str):
        super().__init__(motivo)
        self.codigo = codigo
        self.motivo = motivo


class ServicioMantenimiento:

    def __init__(self, ruta_config: Path, db, instalado_en, contador_ciclos=None,
                 alarm_manager=None, hoy=date.today, ahora=datetime.now,
                 monotonic=time.monotonic, ruta_base: Path | None = None):
        """`db` y `instalado_en` pueden ser callables (la base cambia a
        BdNoDisponible en caliente; el perfil se lee al consultar). `ahora` y
        `monotonic` son inyectables para probar el reloj adelantado.
        `ruta_base`: contador de ciclos al instalar (por defecto, junto a la
        configuración)."""
        self._ruta = Path(ruta_config)
        self._ruta_base = (Path(ruta_base) if ruta_base is not None
                           else self._ruta.with_name("mantenimiento_base.json"))
        self._db = db
        self._instalado_en = instalado_en
        self._contador = contador_ciclos
        self._alarmas = alarm_manager
        self._hoy = hoy
        self._ahora = ahora
        self._monotonic = monotonic
        # referencia para detectar un reloj de pared adelantado mientras corre
        # el proceso: el tiempo monotónico no se altera con el ajuste del reloj
        self._ref_pared = ahora()
        self._ref_mono = monotonic()
        self._lock = threading.Lock()
        self._alarma_activa = False

    # ── configuración ────────────────────────────────────────────────────
    def configuracion(self) -> dict:
        defecto = {"intervalo_dias": m.INTERVALO_DIAS_DEFECTO,
                   "intervalo_ciclos": m.INTERVALO_CICLOS_DEFECTO}
        try:
            datos = json.loads(self._ruta.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return defecto
        except Exception:
            logger.exception("mantenimiento.json ilegible: se usan los valores por defecto")
            return defecto
        if not isinstance(datos, dict) or m.validar_intervalos(
                datos.get("intervalo_dias"), datos.get("intervalo_ciclos")):
            logger.error("mantenimiento.json inválido (%r): se usan los valores por defecto", datos)
            return defecto
        return {"intervalo_dias": datos["intervalo_dias"],
                "intervalo_ciclos": datos["intervalo_ciclos"]}

    def guardar_configuracion(self, intervalo_dias, intervalo_ciclos) -> dict:
        errores = m.validar_intervalos(intervalo_dias, intervalo_ciclos)
        if errores:
            raise ErrorMantenimiento("validacion", "; ".join(errores))
        nueva = {"intervalo_dias": intervalo_dias, "intervalo_ciclos": intervalo_ciclos}
        with self._lock:
            escribir_texto_atomico(self._ruta, json.dumps(nueva, indent=2))
        return nueva

    def migrar_valores_provisionales(self) -> bool:
        """Instalaciones de la tanda 3: si mantenimiento.json sigue en el valor
        provisional (180 días / 0 ciclos) y NADIE lo editó por la API (sin
        auditoría de configuración ni de migración previa), pasa a los
        definitivos 365 / 1000. Sin archivo ya rige el defecto nuevo. Sin base
        de datos no se puede comprobar la auditoría: no se toca. Devuelve True
        si migró. Nunca lanza."""
        try:
            datos = json.loads(self._ruta.read_text(encoding="utf-8"))
            if not (isinstance(datos, dict)
                    and datos.get("intervalo_dias") == m.INTERVALO_DIAS_PROVISIONAL
                    and datos.get("intervalo_ciclos") == m.INTERVALO_CICLOS_PROVISIONAL
                    and not isinstance(datos.get("intervalo_dias"), bool)):
                return False
            db = self._valor(self._db)
            for evento in ("mantenimiento_configurado", "mantenimiento_migrado"):
                if db.get_auditoria(evento=evento, limite=1):
                    return False
            anterior = {"intervalo_dias": datos["intervalo_dias"],
                        "intervalo_ciclos": datos["intervalo_ciclos"]}
            nueva = self.guardar_configuracion(m.INTERVALO_DIAS_DEFECTO,
                                               m.INTERVALO_CICLOS_DEFECTO)
            db.registrar_auditoria(
                "mantenimiento_migrado", usuario="sistema", entidad="/maintenance/config",
                valor_anterior=anterior, valor_nuevo=nueva,
                detalle={"motivo": "valores provisionales de la tanda 3 sin edición previa"})
            logger.info("Mantenimiento: intervalos provisionales migrados a %s", nueva)
            return True
        except FileNotFoundError:
            return False
        except Exception:
            logger.exception("No se pudo migrar la configuración de mantenimiento")
            return False

    # ── lectura ──────────────────────────────────────────────────────────
    def _valor(self, fuente):
        return fuente() if callable(fuente) else fuente

    def _ultimo(self) -> dict | None:
        try:
            return self._valor(self._db).ultimo_mantenimiento()
        except Exception:
            logger.debug("Sin base de datos: el último mantenimiento se desconoce")
            return None

    def _ciclos(self) -> int | None:
        try:
            return int(self._contador.ultimo) if self._contador is not None else None
        except Exception:
            return None

    def _ciclos_instalacion(self) -> int:
        """Contador de ciclos al instalar: 0 en un equipo nuevo. Se fija una
        sola vez (la primera vez que se conoce el contador) y persiste. En un
        equipo que ya tenía ciclos al actualizar, cuenta desde ese momento."""
        try:
            valor = json.loads(self._ruta_base.read_text(encoding="utf-8")).get("ciclos_instalacion")
            if isinstance(valor, int) and not isinstance(valor, bool) and valor >= 0:
                return valor
        except FileNotFoundError:
            pass
        except Exception:
            logger.exception("%s ilegible: se vuelve a fijar", self._ruta_base)
        actual = self._ciclos()
        if actual is None:
            return 0
        try:
            with self._lock:
                escribir_texto_atomico(self._ruta_base,
                                       json.dumps({"ciclos_instalacion": actual}))
        except Exception:
            logger.exception("No se pudo guardar el contador de ciclos de instalación")
        return actual

    def reloj_no_confiable(self, hoy: date | None = None) -> str:
        """"" si el reloj es creíble; si no, el motivo: "atrasado" (anterior a
        la instalación o al último mantenimiento) o "adelantado" (el reloj de
        pared avanzó más de un día respecto del tiempo monotónico desde que
        arrancó el proceso: ajuste manual hacia adelante). En ambos casos no se
        sella ninguna fecha ni se afirma un vencimiento (M1-01)."""
        hoy = hoy or self._hoy()
        instalado = m._a_fecha(self._valor(self._instalado_en))
        ultimo = self._ultimo()
        previa = m._a_fecha(ultimo.get("fecha")) if ultimo else None
        if (instalado is not None and hoy < instalado) or (previa is not None and hoy < previa):
            return "atrasado"
        transcurrido = timedelta(seconds=self._monotonic() - self._ref_mono)
        if self._ahora() - self._ref_pared - transcurrido > timedelta(days=1):
            return "adelantado"
        return ""

    def estado(self) -> m.EstadoMantenimiento:
        cfg = self.configuracion()
        hoy = self._hoy()
        ultimo = self._ultimo()
        if self.reloj_no_confiable(hoy):
            return m.EstadoMantenimiento(
                m.SIN_DATO, ultimo_fecha=m._a_fecha(ultimo.get("fecha")) if ultimo else None,
                ultimo_tipo=(ultimo or {}).get("tipo", ""))
        return m.calcular(self._valor(self._instalado_en), cfg["intervalo_dias"],
                          cfg["intervalo_ciclos"], ultimo, self._ciclos(), hoy,
                          ciclos_instalacion=self._ciclos_instalacion())

    def resumen(self) -> dict:
        """Nunca lanza (GET /maintenance es abierto): ante un dato corrupto
        devuelve el estado sin_dato."""
        try:
            return {**self.estado().a_dict(), "configuracion": self.configuracion(),
                    "ciclos_actuales": self._ciclos()}
        except Exception:
            logger.exception("No se pudo calcular el mantenimiento")
            return {**m.EstadoMantenimiento(m.SIN_DATO).a_dict(),
                    "configuracion": self.configuracion(), "ciclos_actuales": None}

    def historial(self, limite: int = 50) -> list[dict]:
        try:
            return self._valor(self._db).listar_mantenimientos(limite)
        except Exception:
            logger.exception("Historial de mantenimientos no disponible")
            return []

    # ── registro ─────────────────────────────────────────────────────────
    def registrar(self, usuario: str, tipo: str, observaciones: str) -> dict:
        if tipo not in TIPOS:
            raise ErrorMantenimiento("validacion", f"tipo inválido (use {', '.join(TIPOS)})")
        observaciones = (observaciones or "").strip()
        if len(observaciones) > OBSERVACIONES_MAX:
            raise ErrorMantenimiento("validacion",
                                     f"observaciones: máximo {OBSERVACIONES_MAX} caracteres")
        hoy = self._hoy()
        # un reloj atrasado o adelantado no puede sellar un mantenimiento con
        # fecha falsa (la tabla es de solo anexar: no se corregiría después)
        motivo_reloj = self.reloj_no_confiable(hoy)
        if motivo_reloj == "atrasado":
            raise ErrorMantenimiento(
                "reloj_invalido",
                "El reloj del sistema es anterior a la instalación o al último mantenimiento; "
                "corrija la fecha y hora antes de registrar")
        if motivo_reloj == "adelantado":
            raise ErrorMantenimiento(
                "reloj_adelantado",
                "El reloj del sistema se adelantó respecto de su avance real; "
                "corrija la fecha y hora antes de registrar")
        ciclos = self._ciclos()
        fila_id = self._valor(self._db).registrar_mantenimiento(
            hoy.isoformat(), usuario, tipo, observaciones, ciclos)
        self.evaluar_alarma()
        return {"id": fila_id, "fecha": hoy.isoformat(), "tipo": tipo, "ciclos": ciclos}

    # ── aviso no bloqueante ──────────────────────────────────────────────
    def evaluar_alarma(self) -> bool:
        """Activa o resuelve MANTENIMIENTO_VENCIDO según el cálculo. Devuelve
        True si está vencido. Nunca lanza."""
        if self._alarmas is None:
            return False
        try:
            e = self.estado()
            if e.vencido:
                motivo = ("Mantenimiento vencido por fecha"
                          + (f" (debía hacerse el {e.proximo_fecha.isoformat()})"
                             if e.proximo_fecha else "") if e.vencido_por == "fecha"
                          else "Mantenimiento vencido por número de ciclos")
                self._alarmas.activar(MANTENIMIENTO_VENCIDO, motivo=motivo)
                self._alarma_activa = True
            elif self._alarma_activa:
                self._alarmas.resolver(MANTENIMIENTO_VENCIDO)
                self._alarma_activa = False
            return e.vencido
        except Exception:
            logger.exception("No se pudo evaluar el aviso de mantenimiento")
            return False

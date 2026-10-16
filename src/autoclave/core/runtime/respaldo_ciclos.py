# core/runtime/respaldo_ciclos.py
#
# Respaldo por ciclo en archivo de solo-anexar (planeacion_arranque_y_modo_sin_bd
# §7.4; tanda 2026-10-14 T8). Un archivo por ciclo en
# `data/respaldo_ciclos/<uuid>.jsonl`, con una línea JSON por registro:
#
#   {"registro": "encabezado", ...metadatos del ciclo...}
#   {"registro": "lectura", ...}          (las mismas lecturas del ticket)
#   {"registro": "cierre", "resultado": ..., "motivo": ..., ...}
#
# Cada escritura hace flush y os.fsync: un corte de energía deja como mucho la
# última línea incompleta, que la lectura descarta. Se escribe SIEMPRE, con y
# sin base de datos: si la base falla a mitad de ciclo, el registro sigue aquí.
#
# Al arrancar con la base disponible, `pendientes()` entrega los respaldos para
# reimportar (idempotente por uuid) y `archivar()` los mueve a `importados/`.
# Nunca se borra un respaldo.

import json
import logging
import os
import re
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

_UUID_VALIDO = re.compile(r"^[0-9a-fA-F-]{8,64}$")


class RespaldoCiclos:

    def __init__(self, directorio: Path, al_fallar=None):
        self.directorio = Path(directorio)
        self._lock = threading.Lock()
        self.ultimo_error: str | None = None
        # SAF-01 de T8: aviso (alarma SIS-03) al fallar una escritura
        self.al_fallar = al_fallar

    def ruta(self, uuid_ciclo: str) -> Path:
        if not _UUID_VALIDO.match(str(uuid_ciclo or "")):
            raise ValueError(f"uuid de ciclo inválido: {uuid_ciclo!r}")
        return self.directorio / f"{uuid_ciclo}.jsonl"

    def _anexar(self, uuid_ciclo: str, registro: dict) -> bool:
        """Anexa una línea con flush y fsync. False (y registro en el log) si
        no se pudo: el ciclo continúa igual (§7.4)."""
        try:
            linea = json.dumps(registro, ensure_ascii=False, default=str)
            with self._lock:
                self.directorio.mkdir(parents=True, exist_ok=True)
                with open(self.ruta(uuid_ciclo), "a", encoding="utf-8") as f:
                    f.write(linea + "\n")
                    f.flush()
                    os.fsync(f.fileno())
            self.ultimo_error = None
            return True
        except Exception as e:
            self.ultimo_error = str(e)
            logger.exception("RespaldoCiclos: no se pudo escribir el respaldo de %s", uuid_ciclo)
            if self.al_fallar is not None:
                try:
                    self.al_fallar(str(e))
                except Exception:
                    logger.exception("RespaldoCiclos: error al avisar la falla")
            return False

    def probar_escritura(self) -> str | None:
        """SAF-01 de T8: antes de aceptar un ciclo sin base de datos, escribe
        y borra un archivo de prueba con fsync. None si se pudo; si no, el error."""
        prueba = self.directorio / ".prueba_escritura"
        try:
            with self._lock:
                self.directorio.mkdir(parents=True, exist_ok=True)
                with open(prueba, "w", encoding="utf-8") as f:
                    f.write("ok\n")
                    f.flush()
                    os.fsync(f.fileno())
                prueba.unlink()
            return None
        except Exception as e:
            logger.exception("RespaldoCiclos: el directorio de respaldo no admite escritura")
            return str(e)

    def encabezado(self, uuid_ciclo: str, datos: dict) -> bool:
        return self._anexar(uuid_ciclo, {**datos, "registro": "encabezado", "uuid": uuid_ciclo})

    def lectura(self, uuid_ciclo: str, datos: dict) -> bool:
        return self._anexar(uuid_ciclo, {**datos, "registro": "lectura"})

    def cierre(self, uuid_ciclo: str, datos: dict) -> bool:
        return self._anexar(uuid_ciclo, {**datos, "registro": "cierre"})

    # ── Reimportación ─────────────────────────────────────────────────────

    def pendientes(self) -> list[Path]:
        if not self.directorio.is_dir():
            return []
        return sorted(p for p in self.directorio.glob("*.jsonl") if p.is_file())

    @staticmethod
    def leer(ruta: Path) -> dict | None:
        """{"encabezado", "lecturas", "cierre"} del archivo. Las líneas
        ilegibles (p. ej. la última, cortada por un corte de energía) se
        descartan. None si no hay encabezado."""
        encabezado, lecturas, cierre = None, [], None
        try:
            texto = Path(ruta).read_text(encoding="utf-8")
        except Exception:
            logger.exception("RespaldoCiclos: no se pudo leer %s", ruta)
            return None
        for numero, linea in enumerate(texto.splitlines(), start=1):
            if not linea.strip():
                continue
            try:
                registro = json.loads(linea)
            except ValueError:
                logger.warning("RespaldoCiclos: %s línea %d ilegible; se descarta", ruta, numero)
                continue
            if not isinstance(registro, dict):
                continue
            tipo = registro.get("registro")
            if tipo == "encabezado" and encabezado is None:
                encabezado = registro
            elif tipo == "lectura":
                lecturas.append(registro)
            elif tipo == "cierre":
                cierre = registro
        if encabezado is None or not encabezado.get("uuid"):
            return None
        return {"encabezado": encabezado, "lecturas": lecturas, "cierre": cierre}

    def archivar(self, ruta: Path) -> None:
        destino_dir = self.directorio / "importados"
        destino_dir.mkdir(parents=True, exist_ok=True)
        os.replace(ruta, destino_dir / Path(ruta).name)


def reimportar(respaldo: RespaldoCiclos, db, motivo_interrumpido: str,
               excluir: set[str] | None = None) -> dict:
    """Arranque con base disponible (§7.4): reimporta cada respaldo cuyo uuid
    no esté en la base; si está pero quedó incompleto (la base falló a mitad de
    ciclo), lo completa (SAF-02 de T8); luego lo archiva. Un respaldo sin
    cierre se importa como INTERRUMPIDO. Un error deja el archivo en su sitio (se
    reintenta en el próximo arranque). `excluir`: uuids que no se tocan."""
    resultado = {"importados": [], "completados": [], "ya_registrados": [], "errores": []}
    excluir = excluir or set()
    for ruta in respaldo.pendientes():
        datos = respaldo.leer(ruta)
        if datos is None:
            resultado["errores"].append(ruta.name)
            continue
        uuid_ciclo = datos["encabezado"]["uuid"]
        if uuid_ciclo in excluir:
            continue
        try:
            accion = db.importar_ciclo_respaldo(
                datos["encabezado"], datos["lecturas"], datos["cierre"], motivo_interrumpido)
            respaldo.archivar(ruta)
        except Exception:
            logger.exception("RespaldoCiclos: no se pudo reimportar %s", ruta.name)
            resultado["errores"].append(ruta.name)
            continue
        clave = {"importado": "importados", "completado": "completados"}.get(accion, "ya_registrados")
        resultado.setdefault(clave, []).append(uuid_ciclo)
    return resultado

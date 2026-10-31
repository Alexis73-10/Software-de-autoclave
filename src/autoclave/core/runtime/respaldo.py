# core/runtime/respaldo.py
#
# Respaldo y restauración por USB (O2h, tanda 6; planeacion_opciones.md v4
# §3.5 y R-04). Técnico e ingeniero, solo fuera de ciclo (lo impone el backend).
#
# Un respaldo es un ZIP en <USB>/Especifika_respaldos/ con:
#   manifiesto.json   formato, versión de software, número de serie y modelo
#                     del equipo, fecha, usuario, partes incluidas y el SHA-256
#                     de cada archivo; más `hash` = SHA-256 del manifiesto sin
#                     ese campo (detecta un manifiesto alterado o truncado).
#   perfil.json       identificación del equipo (serie, modelo) — referencia.
#   calibracion.yaml  calibración de sensores vigente.
#   parametros.json   parámetros del equipo (system_params) vigentes.
#   programas/*.json  programas de usuario (cycles/user).
#   usuarios.json     usuario, nombre, rol y activo — SIN hashes de contraseña.
#   historial.db      copia de la base (opcional; nunca se restaura).
#
# Restaurar valida el manifiesto (hash y hashes de archivo), el formato, la
# versión mayor del software y el NÚMERO DE SERIE: un respaldo de OTRO equipo
# se rechaza siempre (la calibración y el perfil son del equipo). Aplica solo
# calibración, parámetros y programas (DECISIÓN SIN CONFIRMAR: el perfil se
# cambia reinstalando; los usuarios y el historial no se tocan, por
# trazabilidad). Los programas tampoco (SAF-02 de O2h: falta un validador
# común con el editor). La presión atmosférica de referencia no se restaura
# (solo la escribe O2f). La calibración se valida canal por canal y se recarga
# sin reiniciar; los parámetros se aplican sin reiniciar.
# El hash detecta daño o alteración casual, pero NO autentica (no hay firma).
# Nunca toca salidas ni el ControlLoop.

import hashlib
import io
import json
import re
import zipfile
from datetime import datetime
from pathlib import Path

FORMATO = 1
CARPETA = "Especifika_respaldos"
PARTES = ("perfil_calibracion", "parametros_programas", "usuarios", "historial")
MAX_ZIP_BYTES = 200 * 1024 * 1024
MAX_ARCHIVO_BYTES = 150 * 1024 * 1024
MAX_ENTRADAS = 500
_NOMBRE_PROGRAMA = re.compile(r"^programas/[A-Za-z0-9_.-]{1,80}\.json$")
_NOMBRE_RESPALDO = re.compile(r"^respaldo_[A-Za-z0-9_.-]{1,120}\.zip$")


class ErrorRespaldo(Exception):
    def __init__(self, codigo: str, detalle: str = ""):
        super().__init__(codigo)
        self.codigo = codigo
        self.detalle = detalle


def sha256(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def _hash_manifiesto(m: dict) -> str:
    sin = {k: v for k, v in m.items() if k != "hash"}
    return sha256(json.dumps(sin, sort_keys=True, ensure_ascii=False).encode("utf-8"))


def version_mayor(v: str) -> str:
    return str(v or "").split(".")[0]


def nombre_archivo(serie: str, ahora: datetime) -> str:
    limpia = re.sub(r"[^A-Za-z0-9_.-]", "_", serie or "sin_serie")[:60]
    return f"respaldo_{limpia}_{ahora.strftime('%Y%m%d_%H%M%S')}.zip"


def crear(equipo: dict, partes: dict, contenido: dict, usuario: str, version_sw: str,
          ahora: datetime | None = None) -> bytes:
    """ZIP en memoria. `contenido`: {ruta_en_zip: bytes} ya armado por el
    llamador según `partes`."""
    ahora = ahora or datetime.now()
    archivos = {ruta: sha256(datos) for ruta, datos in sorted(contenido.items())}
    m = {"formato": FORMATO, "version_sw": version_sw, "serie": equipo.get("serie", ""),
         "modelo": equipo.get("modelo", ""), "creado_en": ahora.isoformat(timespec="seconds"),
         "creado_por": usuario, "partes": {p: bool(partes.get(p)) for p in PARTES},
         "archivos": archivos}
    m["hash"] = _hash_manifiesto(m)
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifiesto.json", json.dumps(m, ensure_ascii=False, indent=2))
        for ruta, datos in sorted(contenido.items()):
            z.writestr(ruta, datos)
    return mem.getvalue()


def leer(ruta: Path) -> tuple[dict, dict]:
    """(manifiesto, {ruta: bytes}) validando integridad. Lanza ErrorRespaldo."""
    ruta = Path(ruta)
    try:
        if ruta.stat().st_size > MAX_ZIP_BYTES:
            raise ErrorRespaldo("demasiado_grande")
        with zipfile.ZipFile(ruta) as z:
            nombres = z.namelist()
            if "manifiesto.json" not in nombres:
                raise ErrorRespaldo("sin_manifiesto")
            # SAF-06 de O2h: topes al número de entradas y al tamaño total
            if len(nombres) > MAX_ENTRADAS or z.getinfo("manifiesto.json").file_size > 1024 * 1024:
                raise ErrorRespaldo("demasiado_grande")
            if sum(i.file_size for i in z.infolist()) > MAX_ZIP_BYTES:
                raise ErrorRespaldo("demasiado_grande")
            m = json.loads(z.read("manifiesto.json").decode("utf-8"))
            if not isinstance(m, dict) or not isinstance(m.get("archivos"), dict):
                raise ErrorRespaldo("manifiesto_invalido")
            if m.get("hash") != _hash_manifiesto(m):
                raise ErrorRespaldo("manifiesto_alterado")
            datos = {}
            for nombre, esperado in m["archivos"].items():
                info = z.getinfo(nombre) if nombre in nombres else None
                if info is None:
                    raise ErrorRespaldo("archivo_faltante", nombre)
                if info.file_size > MAX_ARCHIVO_BYTES:
                    raise ErrorRespaldo("demasiado_grande", nombre)
                contenido = z.read(nombre)
                if sha256(contenido) != esperado:
                    raise ErrorRespaldo("hash_invalido", nombre)
                datos[nombre] = contenido
    except ErrorRespaldo:
        raise
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as e:
        raise ErrorRespaldo("ilegible", type(e).__name__)
    return m, datos


def validar_para_equipo(m: dict, equipo: dict, version_sw: str) -> str:
    """"" si se puede restaurar en este equipo; si no, el código del rechazo."""
    if m.get("formato") != FORMATO:
        return "formato"
    serie = equipo.get("serie") or ""
    if not serie or m.get("serie") != serie:
        return "otra_serie"
    if version_mayor(m.get("version_sw")) != version_mayor(version_sw):
        return "version"
    return ""


def resumen(ruta: Path, equipo: dict, version_sw: str) -> dict:
    """Fila de la lista de respaldos de la USB (Válido / Rechazado)."""
    fila = {"archivo": Path(ruta).name, "valido": False, "motivo": "", "serie": "",
            "fecha": "", "partes": {}}
    try:
        m, _ = leer(ruta)
    except ErrorRespaldo as e:
        fila["motivo"] = e.codigo
        return fila
    fila.update(serie=m.get("serie", ""), fecha=m.get("creado_en", ""),
                partes=m.get("partes", {}), version_sw=m.get("version_sw", ""))
    fila["motivo"] = validar_para_equipo(m, equipo, version_sw)
    fila["valido"] = fila["motivo"] == ""
    return fila


def ruta_respaldo_segura(unidad: str, archivo: str) -> Path:
    """Ruta dentro de <unidad>/Especifika_respaldos; rechaza traversal."""
    if not isinstance(archivo, str) or not _NOMBRE_RESPALDO.match(archivo):
        raise ErrorRespaldo("archivo_invalido")
    base = (Path(unidad) / CARPETA).resolve()
    ruta = (base / archivo).resolve()
    if ruta.parent != base:
        raise ErrorRespaldo("archivo_invalido")
    return ruta


def programas_del_respaldo(datos: dict) -> dict:
    """{nombre.json: dict} validando nombre y que sea JSON objeto."""
    salida = {}
    for ruta, contenido in datos.items():
        if not ruta.startswith("programas/"):
            continue
        if not _NOMBRE_PROGRAMA.match(ruta):
            raise ErrorRespaldo("programa_invalido", ruta)
        try:
            obj = json.loads(contenido.decode("utf-8"))
        except ValueError:
            raise ErrorRespaldo("programa_invalido", ruta)
        if not isinstance(obj, dict):
            raise ErrorRespaldo("programa_invalido", ruta)
        salida[ruta.split("/", 1)[1]] = obj
    return salida


def unidades_usb() -> list[dict]:
    """Unidades extraíbles montadas (psutil). Nunca lanza."""
    try:
        import psutil
        lista = []
        for p in psutil.disk_partitions(all=False):
            if "removable" not in (p.opts or "").lower():
                continue
            try:
                libre = psutil.disk_usage(p.mountpoint).free
            except OSError:
                continue
            lista.append({"ruta": p.mountpoint, "libre_bytes": libre})
        return lista
    except Exception:
        return []

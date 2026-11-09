import json
import logging
import sys
import os
import shutil
from datetime import datetime

logger = logging.getLogger(__name__)

# Carpetas que el programa también ESCRIBE (parámetros globales, ciclos de
# usuario, correo, enlace de E/S). En un build congelado de un solo archivo
# (onefile), _MEIPASS es una carpeta temporal que se borra al cerrar: lo que se
# guardara ahí se perdería. En ese caso se usa una copia junto al .exe, en
# <carpeta del exe>/programa/autoclave/..., sembrada desde el paquete.
_ESCRIBIBLES = ("autoclave/config", "autoclave/cycles")
# Siempre se refrescan desde el paquete: son de fábrica, el programa no las
# edita, y así un build nuevo trae sus valores
_SOLO_FABRICA = ("autoclave/cycles/factory",)
# D9-13.1 (tanda 9): archivos de configuración DE FÁBRICA que el programa no
# edita (el máximo físico y la asignación de fábrica de cada instancia; los
# defectos y límites de los parámetros del equipo, cuyos valores vigentes viven
# en la BD). Al actualizar, si el del paquete difiere del guardado, se respalda
# el guardado (con fecha, en programa/<CARPETA_RESPALDOS>/) y se reemplaza. Lo
# del sitio NUNCA entra aquí: calibration_modbus.yaml, correo.json,
# active_instances.yaml, cycles/user, cycles/defecto, ni nada fuera de
# programa/ (perfil, BD, data/asignacion_io.json).
_FABRICA_CON_RESPALDO = ("autoclave/config/instances/", "autoclave/config/global_params.json")
CARPETA_RESPALDOS = "respaldos_configuracion"
# D9-7 (tanda 9): la entrega ya no trae cycles/user; en la primera instalación
# (sin carpeta de usuario) los programas editables se siembran desde fábrica
_CICLOS = "autoclave/cycles"
_sembradas = set()


# INS-02 (tanda 17): el Setup instala en X:\Especifika\Autoclave\{programa,datos}
# (X = unidad elegida) y escribe esta clave, en la vista de 64 bits del registro.
# El Setup (autoclave.iss) y tools/estacion usan los mismos nombres.
CLAVE_REGISTRO = r"SOFTWARE\Especifika\Autoclave"
VALOR_RUTA_PROGRAMA = "RutaPrograma"
VALOR_RUTA_DATOS = "RutaDatos"
SUBCARPETA_PROGRAMA = "programa"
SUBCARPETA_DATOS = "datos"


def _leer_registro_instalacion():
    """(RutaPrograma, RutaDatos) de HKLM\\SOFTWARE\\Especifika\\Autoclave (vista
    de 64 bits), o None si no existe, falta un valor o no es Windows."""
    try:
        import winreg
    except ImportError:
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, CLAVE_REGISTRO, 0,
                            winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as clave:
            programa, _ = winreg.QueryValueEx(clave, VALOR_RUTA_PROGRAMA)
            datos, _ = winreg.QueryValueEx(clave, VALOR_RUTA_DATOS)
    except OSError:
        return None
    if not isinstance(programa, str) or not isinstance(datos, str) or not programa or not datos:
        return None
    return programa, datos


def _misma_carpeta(a: str, b: str) -> bool:
    return os.path.normcase(os.path.normpath(os.path.abspath(a))) == \
        os.path.normcase(os.path.normpath(os.path.abspath(b)))


def raiz_datos_exe() -> str:
    """Carpeta de datos escribibles de un build congelado (la usa también
    utils/paths.app_root). Orden (INS-02, tanda 17):
    1. `RutaDatos` del registro, si `RutaPrograma` es la carpeta del .exe en
       ejecución (instalación del Setup en X:\\Especifika\\Autoclave);
    2. instalado en Archivos de programa (solo lectura sin administrador):
       %ProgramData%\\Especifika\\Autoclave (disposición de la compilación I y anteriores);
    3. en cualquier otro lugar (copia portátil), la carpeta del .exe."""
    carpeta_exe = os.path.dirname(os.path.abspath(sys.executable))
    registro = _leer_registro_instalacion()
    if registro is not None and _misma_carpeta(registro[0], carpeta_exe):
        return os.path.normpath(registro[1])
    for variable in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(variable)
        if base and os.path.normcase(carpeta_exe).startswith(os.path.normcase(base) + os.sep):
            return os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"),
                                "Especifika", "Autoclave")
    return carpeta_exe


def _carpeta_persistente() -> str:
    return os.path.join(raiz_datos_exe(), "programa")


def _copiar(origen: str, destino: str) -> None:
    # copia a un temporal y renombra: varios procesos (backend y pantallas)
    # pueden sembrar a la vez
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    temporal = f"{destino}.{os.getpid()}.tmp"
    shutil.copy2(origen, temporal)
    os.replace(temporal, destino)


def _marca_tiempo() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H%M%S")


def _respaldar(destino: str, relativa: str, marca: str) -> str:
    """Copia `destino` a programa/<CARPETA_RESPALDOS>/<marca>/<relativa> y
    devuelve la ruta del respaldo. Lanza OSError si no se pudo."""
    respaldo = os.path.normpath(os.path.join(_carpeta_persistente(), CARPETA_RESPALDOS,
                                             marca, relativa))
    _copiar(destino, respaldo)
    return respaldo


def _iguales(a: str, b: str) -> bool:
    try:
        with open(a, "rb") as fa, open(b, "rb") as fb:
            return fa.read() == fb.read()
    except OSError:
        return False


def _refrescar_con_respaldo(origen: str, destino: str, relativa: str, marca: str) -> None:
    """D9-13.1: reemplaza un archivo de fábrica que cambió en el paquete, con
    respaldo previo. Sin respaldo no se reemplaza (queda el anterior)."""
    if _iguales(origen, destino):
        return
    try:
        respaldo = _respaldar(destino, relativa, marca)
    except OSError:
        logger.exception("No se pudo respaldar %s: no se reemplaza por el de fábrica", destino)
        return
    _copiar(origen, destino)
    logger.warning("Configuración de fábrica actualizada: %s (respaldo del anterior en %s)",
                   relativa, respaldo)


# PRI-05 (ciclo Prion): programas de fábrica que ya existían antes de la siembra
# de faltantes; se dan por «vistos» en un equipo sin marca (no se recrean si el
# hospital los borró).
_FABRICA_LEGADA = frozenset({"bowe_dick", "134_instrumental", "instrumental_121",
                             "liquidos", "textiles"})
MARCA_FABRICA_VISTOS = "fabrica_vistos.lst"   # en cycles/user; no es .json a propósito


def _datos_programa(ruta: str):
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def _escribir_marca_vistos(usuario: str, ids) -> None:
    ruta = os.path.join(usuario, MARCA_FABRICA_VISTOS)
    temporal = f"{ruta}.{os.getpid()}.tmp"
    with open(temporal, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(ids)) + "\n")
    os.replace(temporal, ruta)


def sembrar_faltantes_usuario(raiz_ciclos: str) -> list:
    """PRI-05: copia a <raiz>/user los programas de <raiz>/factory que el equipo
    aún no conocía (id fuera de la marca `fabrica_vistos.lst`; sin marca rigen
    los cinco de fábrica anteriores). No pisa un programa existente (mismo id,
    mismo número o mismo archivo), quita `nombre_clave` (como la siembra
    inicial) y recuerda lo visto para no recrear lo que el hospital borre.
    Idempotente. Nunca lanza: ante un error deja un aviso y reintenta en el
    próximo arranque. Devuelve los archivos sembrados."""
    sembrados = []
    try:
        fabrica = os.path.join(raiz_ciclos, "factory")
        usuario = os.path.join(raiz_ciclos, "user")
        if not os.path.isdir(fabrica) or not os.path.isdir(usuario):
            return sembrados
        marca = os.path.join(usuario, MARCA_FABRICA_VISTOS)
        if os.path.exists(marca):
            with open(marca, "r", encoding="utf-8") as f:
                vistos = {l.strip() for l in f if l.strip()}
        else:
            vistos = set(_FABRICA_LEGADA)
        ids_usuario, numeros_usuario = set(), set()
        for nombre in os.listdir(usuario):
            if nombre.endswith(".json"):
                try:
                    d = _datos_programa(os.path.join(usuario, nombre))
                    ids_usuario.add(d.get("cycle_id"))
                    numeros_usuario.add(d.get("cycle_number"))
                except Exception:
                    pass
        procesados = set()
        for nombre in sorted(os.listdir(fabrica)):
            if not nombre.endswith(".json"):
                continue
            try:
                datos = _datos_programa(os.path.join(fabrica, nombre))
                cid, numero = datos["cycle_id"], datos.get("cycle_number")
                if cid in vistos:
                    continue
                destino = os.path.join(usuario, nombre)
                if cid in ids_usuario or numero in numeros_usuario or os.path.exists(destino):
                    logger.warning("Programa de fábrica %s no se siembra: ya hay un programa de "
                                   "usuario con ese id, número o archivo", cid)
                    procesados.add(cid)
                    continue
                datos.pop("nombre_clave", None)
                temporal = f"{destino}.{os.getpid()}.tmp"
                try:
                    with open(temporal, "w", encoding="utf-8") as f:
                        json.dump(datos, f, ensure_ascii=False, indent=4)
                    os.replace(temporal, destino)
                finally:
                    if os.path.exists(temporal):
                        os.remove(temporal)
                procesados.add(cid)
                sembrados.append(nombre)
                logger.info("Programa de fábrica %s sembrado en %s", cid, usuario)
            except Exception:
                logger.warning("No se pudo sembrar el programa de fábrica %s", nombre, exc_info=True)
        if procesados:
            try:
                _escribir_marca_vistos(usuario, vistos | procesados)
            except OSError:
                logger.warning("No se pudo guardar la marca de programas de fábrica vistos",
                               exc_info=True)
    except Exception:
        logger.warning("Siembra de programas de fábrica faltantes omitida", exc_info=True)
    return sembrados


def _sembrar_usuario_desde_fabrica() -> None:
    """D9-7: primera instalación sin cycles/user. Copia cada programa de fábrica
    (sin `nombre_clave`, que es solo de fábrica: un nombre cambiado en el
    hospital se seguiría mostrando con el del catálogo). Se arma en una carpeta
    temporal y se renombra: varios procesos pueden arrancar a la vez y nunca
    queda una carpeta de usuario a medias."""
    raiz = os.path.join(_carpeta_persistente(), _CICLOS)
    usuario = os.path.join(raiz, "user")
    fabrica = os.path.join(raiz, "factory")
    if os.path.exists(usuario) or not os.path.isdir(fabrica):
        return
    temporal = f"{usuario}.{os.getpid()}.tmp"
    try:
        shutil.rmtree(temporal, ignore_errors=True)
        os.makedirs(temporal)
        for nombre in sorted(os.listdir(fabrica)):
            if not nombre.endswith(".json"):
                continue
            with open(os.path.join(fabrica, nombre), "r", encoding="utf-8") as f:
                datos = json.load(f)
            datos.pop("nombre_clave", None)
            with open(os.path.join(temporal, nombre), "w", encoding="utf-8") as f:
                json.dump(datos, f, ensure_ascii=False, indent=4)
        os.rename(temporal, usuario)
        try:
            _escribir_marca_vistos(usuario, [d["cycle_id"] for d in
                                             (_datos_programa(os.path.join(fabrica, n))
                                              for n in os.listdir(fabrica) if n.endswith(".json"))])
        except Exception:
            logger.warning("No se pudo guardar la marca de programas de fábrica vistos", exc_info=True)
        logger.info("Primera instalación: programas de usuario sembrados desde fábrica en %s", usuario)
    except (OSError, ValueError):
        # otro proceso ya la creó, o un programa de fábrica ilegible: el
        # cargador de ciclos lo reporta; sin carpeta de usuario rigen los de fábrica
        logger.exception("No se pudieron sembrar los programas de usuario desde fábrica")
        shutil.rmtree(temporal, ignore_errors=True)


def _sembrar(prefijo: str) -> None:
    if prefijo in _sembradas:
        return
    _sembradas.add(prefijo)
    origen_raiz = os.path.join(sys._MEIPASS, prefijo)
    destino_raiz = os.path.join(_carpeta_persistente(), prefijo)
    marca = _marca_tiempo()
    for carpeta, _, archivos in os.walk(origen_raiz):
        relativa = os.path.relpath(carpeta, origen_raiz)
        if "__pycache__" in relativa:
            continue
        for nombre in archivos:
            origen = os.path.join(carpeta, nombre)
            destino = os.path.normpath(os.path.join(destino_raiz, relativa, nombre))
            rel_paquete = os.path.normpath(os.path.join(prefijo, relativa, nombre)).replace("\\", "/")
            de_fabrica = any(f"{prefijo}/{relativa}".replace("\\", "/").startswith(f)
                             for f in _SOLO_FABRICA)
            con_respaldo = any(rel_paquete == f or (f.endswith("/") and rel_paquete.startswith(f))
                               for f in _FABRICA_CON_RESPALDO)
            try:
                if de_fabrica or not os.path.exists(destino):
                    _copiar(origen, destino)
                elif con_respaldo:
                    _refrescar_con_respaldo(origen, destino, rel_paquete, marca)
            except OSError:
                pass   # otro proceso lo está copiando; se usa el que quede
    if prefijo == _CICLOS:
        _sembrar_usuario_desde_fabrica()


def resource_path(relative_path: str) -> str:
    if hasattr(sys, "_MEIPASS"):
        # .exe
        normalizada = relative_path.replace("\\", "/")
        for prefijo in _ESCRIBIBLES:
            if normalizada == prefijo or normalizada.startswith(prefijo + "/"):
                _sembrar(prefijo)
                return os.path.join(_carpeta_persistente(), relative_path)
        base_path = sys._MEIPASS
    else:
        # desarrollo → raíz del proyecto
        base_path = os.path.abspath("src")

    return os.path.join(base_path, relative_path)

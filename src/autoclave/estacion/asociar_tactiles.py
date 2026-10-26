# autoclave/estacion/asociar_tactiles.py
#
# EST-06 (tanda 17): herramienta propia de asociación de pantallas táctiles,
# `Autoclave.exe --rol asociar-tactiles`. La usa 06_asociar_tactiles.ps1
# cuando Windows no trae MultiDigitizer.exe ("Configuración de Tablet PC"),
# y se puede ejecutar sola como administrador.
#
# Recorrido:
#   1. exige administrador (escribe en HKLM); si no, sale con SIN_ADMIN;
#   2. respaldo del estado previo de Digimon, si aún no existe, con el mismo
#      formato que el script (ver digimon.py), ANTES de escribir nada; si no
#      puede respaldar, no toca el registro;
#   3. en cada monitor, uno a la vez, una ventana negra a pantalla completa,
#      sin borde y siempre encima con "Toque esta pantalla / Touch this
#      screen"; el primer toque que llega por Raw Input (página HID 0x0D
#      digitalizador, uso 0x04 pantalla táctil, RIDEV_INPUTSINK) identifica el
#      digitalizador (RIDI_DEVICENAME); el monitor es el de esa ventana
#      (EnumDisplayDevicesW con EDD_GET_DEVICE_INTERFACE_NAME). Un
#      digitalizador ya asociado en esta pasada no cuenta para el siguiente
#      monitor. Tope de TOPE_POR_MONITOR_S por monitor (time.monotonic());
#      Enter salta la pantalla y Esc cancela todo (no escribe nada);
#   4. arma los valores (digimon.armar_valores, función pura) y los escribe
#      (solo crea o reemplaza; nunca borra);
#   5. avisa en pantalla y en el log que hay que REINICIAR el equipo
#      (Windows lee Digimon al iniciar sesión).
# Textos bilingües fijos (corre fuera de los catálogos i18n).
#
# Códigos de salida (06_asociar_tactiles.ps1 los anota en el log; el paso
# sigue sin fallar y el Setup cuenta las asociaciones):

import argparse
import getpass
import logging
import os
import sys
import time
from datetime import datetime
from types import SimpleNamespace

from autoclave.estacion import digimon

logger = logging.getLogger(__name__)

COMPLETO = 0          # todas las pantallas quedaron asociadas
SIN_ADMIN = 2         # no corre como administrador: no se escribió nada
INCOMPLETO = 3        # alguna pantalla sin asociar (tope, Enter) o cancelado con Esc
ERROR = 4             # error (respaldo, registro, ventanas): ver el log
SIN_MONITORES = 5     # no se encontró ningún monitor con ruta de interfaz

TOPE_POR_MONITOR_S = 120.0
TITULO_TOQUE = "Toque esta pantalla"
TEXTO_TOQUE = "Touch this screen\n\nEnter: saltar / skip · Esc: cancelar / cancel"
TITULO_FIN = "Listo / Done"
TEXTO_FIN = ("Reinicie el equipo para aplicar la asociación.\n"
             "Restart the computer to apply the association.")
SEGUNDOS_AVISO_FIN = 8.0


class Cancelado(Exception):
    """El operador pulsó Esc."""


class _Log:
    """Escribe en el log de la estación (mismo formato que _comun.ps1) y en
    el logger de Python."""

    def __init__(self, ruta=None):
        self.ruta = ruta

    def __call__(self, mensaje: str, nivel: str = "INFO") -> None:
        getattr(logger, {"WARN": "warning", "ERROR": "error"}.get(nivel, "info"))(mensaje)
        if not self.ruta:
            return
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.ruta)), exist_ok=True)
            try:
                usuario = getpass.getuser()
            except Exception:
                usuario = "?"
            linea = f"{datetime.now():%Y-%m-%d %H:%M:%S} [{nivel}] [{usuario}] [asociar-tactiles] {mensaje}\n"
            with open(self.ruta, "a", encoding="utf-8") as f:
                f.write(linea)
        except OSError:
            logger.exception("No se pudo escribir en %s", self.ruta)


def carpeta_estacion() -> str:
    """<datos>\\estacion: la carpeta de datos resuelta (utils/paths.app_root,
    que en el build congelado usa resources.raiz_datos_exe)."""
    from autoclave.utils.paths import app_root
    return os.path.join(str(app_root()), "estacion")


def ejecutar(*, es_admin, listar_monitores, pedir_toque, escritor, ruta_respaldo, log,
             tope_s: float = TOPE_POR_MONITOR_S, avisar_fin=None) -> int:
    """Recorrido completo con todas sus dependencias inyectadas (las pruebas
    usan dobles; main() usa las de Win32).

    listar_monitores() → [SimpleNamespace(rect, interfaz)];
    pedir_toque(monitor, excluidos, tope_s) → ruta HID del digitalizador o
    None (tope o Enter); lanza Cancelado con Esc.
    escritor: leer() / existe() / escribir(nombre, dato) (digimon.EscritorRegistro)."""
    log("== Inicio asociar-tactiles (herramienta propia) ==")
    if not es_admin():
        log("Se necesita ejecutar como administrador (escribe en HKLM). No se cambió nada.", "ERROR")
        return SIN_ADMIN
    monitores = [m for m in listar_monitores() if getattr(m, "interfaz", None)]
    log(f"Monitores con ruta de interfaz: {len(monitores)}.")
    if not monitores:
        log("No se encontró ningún monitor: no hay nada que asociar.", "WARN")
        return SIN_MONITORES

    try:
        if digimon.asegurar_respaldo(ruta_respaldo, escritor):
            log(f"Respaldo de Digimon creado en {ruta_respaldo}.")
        else:
            log(f"Respaldo de Digimon ya existe ({ruta_respaldo}): no se sobrescribe.")
    except Exception as e:
        log(f"No se pudo crear el respaldo de Digimon ({e}): no se toca el registro.", "ERROR")
        return ERROR

    pares, excluidos, saltados = [], set(), 0
    try:
        for i, monitor in enumerate(monitores, start=1):
            log(f"Pantalla {i}/{len(monitores)}: {monitor.interfaz}. Esperando un toque "
                f"(máximo {tope_s:.0f} s).")
            hid = pedir_toque(monitor, frozenset(excluidos), tope_s)
            if not hid:
                saltados += 1
                log(f"Pantalla {i}: sin toque (tope o Enter): queda sin asociar.", "WARN")
                continue
            log(f"Pantalla {i}: tocada con {hid}.")
            pares.append((hid, monitor.interfaz))
            excluidos.add(digimon.normalizar_ruta(hid).lower())
    except Cancelado:
        log("Cancelado con Esc: no se escribió ninguna asociación.", "WARN")
        return INCOMPLETO
    except Exception as e:
        log(f"Error al esperar los toques ({type(e).__name__}: {e}): no se escribió ninguna asociación.",
            "ERROR")
        return ERROR

    try:
        existentes = escritor.leer()
    except Exception as e:
        log(f"No se pudo leer Digimon ({e}).", "ERROR")
        return ERROR
    armado = digimon.armar_valores(pares, digimon.prefijo_observado(existentes))
    for rechazo in armado.rechazos:
        log(f"Descartado: {rechazo}", "WARN")
    for aviso in digimon.conflictos(armado.valores, existentes):
        log(f"Aviso: {aviso}", "WARN")

    escritos, errores = 0, 0
    for nombre, dato in armado.valores.items():
        try:
            escritor.escribir(nombre, dato)
            escritos += 1
            log(f"Asociación escrita: {nombre} = {dato}.")
        except Exception as e:
            errores += 1
            log(f"No se pudo escribir {nombre}: {e}", "ERROR")

    if escritos:
        log("Reinicie el equipo: Windows aplica la asociación de pantallas táctiles al iniciar sesión.",
            "WARN")
        if avisar_fin is not None:
            try:
                avisar_fin()
            except Exception:
                logger.exception("No se pudo mostrar el aviso final")
    log(f"== Fin asociar-tactiles: {escritos} asociaciones escritas de {len(monitores)} pantallas ==")
    if errores:
        return ERROR
    if escritos < len(monitores) or saltados or armado.rechazos:
        return INCOMPLETO
    return COMPLETO


# ── implementación Win32 ────────────────────────────────────────────────────

def _es_admin_win32() -> bool:
    try:
        from autoclave.estacion import _win32
        return bool(_win32.api().IsUserAnAdmin())
    except Exception:
        logger.exception("No se pudo comprobar si es administrador")
        return False


def _listar_monitores_win32() -> list:
    from autoclave.estacion import _win32
    a = _win32.api()
    salida = []
    for m in _win32.monitores(a):
        interfaces = _win32.interfaces_monitor(m.dispositivo, a)
        salida.append(SimpleNamespace(rect=m.rect, dispositivo=m.dispositivo,
                                      interfaz=interfaces[0] if interfaces else None))
        if len(interfaces) > 1:
            logger.warning("%s tiene %d monitores (clonado): se usa %s", m.dispositivo,
                           len(interfaces), interfaces[0])
    return salida


def _nombre_dispositivo(a, h_dispositivo):
    import ctypes
    from ctypes import wintypes
    from autoclave.estacion import _win32
    tam = wintypes.UINT(0)
    a.GetRawInputDeviceInfoW(h_dispositivo, _win32.RIDI_DEVICENAME, None, ctypes.byref(tam))
    if not tam.value:
        return None
    buf = ctypes.create_unicode_buffer(tam.value + 1)
    if a.GetRawInputDeviceInfoW(h_dispositivo, _win32.RIDI_DEVICENAME, buf, ctypes.byref(tam)) in (0, 0xFFFFFFFF):
        return None
    return buf.value


def _pedir_toque_win32(monitor, excluidos, tope_s, reloj=time.monotonic):
    """Ventana en `monitor` y espera el primer toque de un digitalizador que
    no esté en `excluidos`. Devuelve su ruta HID, None (tope/Enter) o lanza
    Cancelado (Esc)."""
    import ctypes
    from ctypes import wintypes
    from autoclave.estacion import _win32
    from autoclave.estacion._ventanas import VentanasTexto
    a = _win32.api()
    estado = {"hid": None, "accion": None}

    def al_mensaje(hwnd, msg, wparam, lparam):
        if msg == _win32.WM_INPUT and estado["hid"] is None:
            cab = _win32.RAWINPUTHEADER()
            tam = wintypes.UINT(ctypes.sizeof(cab))
            if a.GetRawInputData(lparam, _win32.RID_HEADER, ctypes.byref(cab), ctypes.byref(tam),
                                 ctypes.sizeof(_win32.RAWINPUTHEADER)) != 0xFFFFFFFF \
                    and cab.dwType == _win32.RIM_TYPEHID and cab.hDevice:
                nombre = _nombre_dispositivo(a, cab.hDevice)
                if nombre and digimon.normalizar_ruta(nombre).lower() not in excluidos:
                    estado["hid"] = nombre
            return None   # DefWindowProc limpia el búfer de Raw Input
        if msg in (_win32.WM_KEYDOWN, _win32.WM_SYSKEYDOWN):
            if wparam == _win32.VK_ESCAPE:
                estado["accion"] = "cancelar"
                return 0
            if wparam == _win32.VK_RETURN:
                estado["accion"] = "saltar"
                return 0
        return None

    ventanas = VentanasTexto(TITULO_TOQUE, TEXTO_TOQUE, activable=True, al_mensaje=al_mensaje, api=a)
    registrado = False
    try:
        ventanas.crear([monitor.rect])
        disp = _win32.RAWINPUTDEVICE(_win32.HID_USAGE_PAGE_DIGITIZER, _win32.HID_USAGE_DIGITIZER_TOUCH_SCREEN,
                                     _win32.RIDEV_INPUTSINK, ventanas.hwnds[0])
        if not a.RegisterRawInputDevices(ctypes.byref(disp), 1, ctypes.sizeof(disp)):
            raise OSError(f"RegisterRawInputDevices falló (error {ctypes.get_last_error()})")
        registrado = True
        limite = reloj() + float(tope_s)
        while estado["hid"] is None and estado["accion"] is None:
            restante = limite - reloj()
            if restante <= 0:
                return None
            if not ventanas.esperar(int(min(0.2, restante) * 1000)):
                return None
        if estado["accion"] == "cancelar":
            raise Cancelado()
        return estado["hid"]
    finally:
        if registrado:
            quitar = _win32.RAWINPUTDEVICE(_win32.HID_USAGE_PAGE_DIGITIZER,
                                           _win32.HID_USAGE_DIGITIZER_TOUCH_SCREEN, _win32.RIDEV_REMOVE, None)
            try:
                a.RegisterRawInputDevices(ctypes.byref(quitar), 1, ctypes.sizeof(quitar))
            except Exception:
                pass
        ventanas.destruir()


def _avisar_fin_win32(monitores, segundos=SEGUNDOS_AVISO_FIN, reloj=time.monotonic):
    """Aviso de reinicio en todas las pantallas durante unos segundos (no es
    modal: el Setup nunca queda esperando un clic)."""
    from autoclave.estacion._ventanas import VentanasTexto
    ventanas = VentanasTexto(TITULO_FIN, TEXTO_FIN, activable=True)
    try:
        ventanas.crear([m.rect for m in monitores])
        limite = reloj() + segundos
        while reloj() < limite and ventanas.esperar(200):
            pass
    finally:
        ventanas.destruir()


def _parse_args(argv):
    p = argparse.ArgumentParser(prog="Autoclave.exe --rol asociar-tactiles")
    p.add_argument("--respaldo", default=None,
                   help="ruta de respaldo_06_asociar_tactiles.json (por defecto <datos>\\estacion)")
    p.add_argument("--log", default=None, help="log de la estación (por defecto <datos>\\estacion\\estacion.log)")
    p.add_argument("--tope-s", type=float, default=TOPE_POR_MONITOR_S)
    return p.parse_args(argv)


def main(argv=None) -> int:
    """Punto de entrada del rol. Nunca lanza: cualquier error es ERROR."""
    try:
        args = _parse_args(list(argv or []))
    except SystemExit:
        return ERROR
    log = _Log(None)
    try:
        estacion = carpeta_estacion() if (args.respaldo is None or args.log is None) else None
        ruta_respaldo = args.respaldo or os.path.join(estacion, digimon.NOMBRE_RESPALDO)
        log = _Log(args.log or os.path.join(estacion, "estacion.log"))
        if sys.platform != "win32":
            log("La asociación de pantallas táctiles solo existe en Windows.", "ERROR")
            return ERROR
        if not _es_admin_win32():
            return ejecutar(es_admin=lambda: False, listar_monitores=list, pedir_toque=None,
                            escritor=None, ruta_respaldo=ruta_respaldo, log=log)
        monitores = _listar_monitores_win32()
        return ejecutar(es_admin=lambda: True, listar_monitores=lambda: monitores,
                        pedir_toque=_pedir_toque_win32, escritor=digimon.EscritorRegistro(),
                        ruta_respaldo=ruta_respaldo, log=log, tope_s=args.tope_s,
                        avisar_fin=lambda: _avisar_fin_win32(monitores))
    except Exception as e:
        logger.exception("asociar-tactiles falló")
        log(f"Error inesperado: {type(e).__name__}: {e}", "ERROR")
        return ERROR

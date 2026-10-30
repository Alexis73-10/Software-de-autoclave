# autoclave/backend/rutas/respaldo.py
#
# Respaldo y restauración (/backup).
# ORG-12 (tanda 15): movido sin cambios desde backend/server.py; se registra
# en server.py con app.include_router.

import sqlite3
import json
import os
import threading
from pathlib import Path
from datetime import datetime
from fastapi import Depends
from pydantic import BaseModel, StrictBool
from autoclave.backend.autenticacion import Sesion
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.core.managers.catalogo_parametros import evaluar_desviacion_acumulada
from autoclave.config import load_config
from autoclave.state_machine.machine.enum_global import GlobalState
from autoclave.auth.roles import ROL_INGENIERO, ROL_TECNICO
from fastapi import APIRouter

from autoclave.backend.dependencias import (CALIBRATION_PATH, DISTINTO_DE_CICLO, RechazoApi,
    _auditar, _lock_archivos, _rechazar, context, guard_estado, requiere_rol)
from autoclave.backend.rutas._comun import _meta_equipo, _reasignacion

router = APIRouter()


# ── Respaldo y restauración por USB (O2h, tanda 6) ──────────────────────────
# Técnico e ingeniero, solo fuera de CICLO (409, también el ingeniero). Ver
# core/runtime/respaldo.py: manifiesto con hash, sin hashes de contraseña, y un
# respaldo de OTRO número de serie se rechaza siempre. Restaurar pide
# `confirmar: true` y no toca usuarios, historial, perfil ni la atmosférica.

class _ExportarBody(BaseModel):
    unidad: str
    perfil_calibracion: StrictBool = True
    parametros_programas: StrictBool = True
    usuarios: StrictBool = True
    historial: StrictBool = False


class _RestaurarBody(BaseModel):
    unidad: str
    archivo: str
    confirmar: StrictBool = False


_lock_respaldo = threading.Lock()


def _fabrica(cfg) -> dict:
    return cfg.calibration.factory.model_dump()


def _misma_fabrica(cfg_resp) -> bool:
    """Tanda 19 (MOD-04; revisión R, V19-s2-02): True si TODA la sección
    `calibration.factory` del respaldo (temperatura y presión, todos los campos
    de cada canal) es igual a la del archivo de calibración activo, es decir,
    si el respaldo es del mismo enlace de E/S y de la misma fábrica. False si
    difiere en cualquier campo o si el activo no se puede leer (falla cerrada).
    Desde la tanda 20 (T20-03) el enlace es único (Modbus): esto rechaza los
    respaldos de equipos con el enlace serial retirado (cuentas del ADC) y
    también un respaldo con otra fábrica del mismo enlace: falla cerrada; la
    fábrica no se restaura por respaldo."""
    try:
        activa = load_config(CALIBRATION_PATH)
    except Exception:
        return False
    return _fabrica(cfg_resp) == _fabrica(activa)


def _unidades_usb() -> list[dict]:
    from autoclave.core.runtime import respaldo as rp
    return rp.unidades_usb()


def _version_sw() -> str:
    # VER-03/VER-05: fuente única, con el commit de la compilación
    from autoclave._version import version_completa
    return version_completa()


def _unidad_detectada(unidad: str, entidad: str, sesion) -> str:
    rutas = {u["ruta"] for u in _unidades_usb()}
    if unidad not in rutas:
        raise RechazoApi(404, "usb_no_detectada", "Unidad USB no detectada")
    return unidad


def _carpeta_programas_usuario() -> Path:
    return Path(context.cycle_manager.carpeta("cycles/user"))


def _usuarios_sin_hash() -> list[dict]:
    db = context.db
    with getattr(db, "_lock", threading.Lock()):
        filas = db._conn.execute("SELECT usuario, nombre, rol, activo FROM usuarios").fetchall()
    return [{"usuario": f[0], "nombre": f[1], "rol": f[2], "activo": bool(f[3])} for f in filas]


def _copia_bd() -> bytes:
    import tempfile
    db = context.db
    with tempfile.TemporaryDirectory() as tmp:
        destino = Path(tmp) / "historial.db"
        dst = sqlite3.connect(destino)
        try:
            with getattr(db, "_lock", threading.Lock()):
                db._conn.backup(dst)
        finally:
            dst.close()
        return destino.read_bytes()


@router.get("/backup/usb")
def get_backup_usb(sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    from autoclave.core.runtime import respaldo as rp
    equipo, version = _meta_equipo(), _version_sw()
    unidades = []
    for u in _unidades_usb():
        carpeta = Path(u["ruta"]) / rp.CARPETA
        respaldos = []
        try:
            archivos = sorted(carpeta.glob("respaldo_*.zip"), reverse=True)[:50]
        except OSError:
            archivos = []
        for a in archivos:
            respaldos.append(rp.resumen(a, equipo, version))
        unidades.append({**u, "respaldos": respaldos})
    return {"unidades": unidades, "serie": equipo["serie"], "version_sw": version}


@router.post("/backup/export")
def post_backup_export(body: _ExportarBody,
                       sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    from autoclave.core.runtime import respaldo as rp
    from autoclave.utils.archivos import escribir_texto_atomico  # noqa: F401
    entidad = "/backup/export"
    with guard_estado(DISTINTO_DE_CICLO, entidad, sesion):
        pass
    unidad = _unidad_detectada(body.unidad, entidad, sesion)
    partes = body.model_dump(exclude={"unidad"})
    if not any(partes.values()):
        raise RechazoApi(422, "sin_partes", "Elija qué exportar")
    equipo = _meta_equipo()
    contenido = {"perfil.json": json.dumps(equipo, ensure_ascii=False).encode("utf-8")}
    if body.perfil_calibracion:
        with _lock_archivos:                         # SAF-05 de O2h
            contenido["calibracion.yaml"] = Path(CALIBRATION_PATH).read_bytes()
        # R8 (D8-5.12): la asignación de E/S vigente, si difiere de fábrica
        asignacion = _reasignacion.contenido_respaldo()
        if asignacion is not None:
            contenido[_reasignacion.RUTA_EN_RESPALDO] = asignacion
    if body.parametros_programas:
        params = {p["clave"]: p["valor"] for p in context.config_manager.describir()}
        contenido["parametros.json"] = json.dumps(params, ensure_ascii=False).encode("utf-8")
        for f in sorted(_carpeta_programas_usuario().glob("*.json")):
            contenido[f"programas/{f.name}"] = f.read_bytes()
    if body.usuarios:
        contenido["usuarios.json"] = json.dumps(_usuarios_sin_hash(), ensure_ascii=False).encode("utf-8")
    if body.historial:
        contenido["historial.db"] = _copia_bd()
    with _lock_respaldo:
        zip_bytes = rp.crear(equipo, partes, contenido, sesion.usuario, _version_sw())
        carpeta = Path(unidad) / rp.CARPETA
        nombre = rp.nombre_archivo(equipo["serie"], datetime.now())
        try:
            carpeta.mkdir(parents=True, exist_ok=True)
            temporal = carpeta / (nombre + ".tmp")
            temporal.write_bytes(zip_bytes)
            os.replace(temporal, carpeta / nombre)
        except OSError:
            _rechazar(503, "usb_no_escribible", "No se pudo escribir en la USB", entidad, sesion)
    _auditar("respaldo_exportado", sesion, entidad=entidad,
             detalle={"archivo": nombre, "partes": partes, "bytes": len(zip_bytes)})
    return {"ok": True, "archivo": nombre, "bytes": len(zip_bytes)}


@router.post("/backup/restore")
def post_backup_restore(body: _RestaurarBody,
                        sesion: Sesion = Depends(requiere_rol(ROL_TECNICO, ROL_INGENIERO))):
    from autoclave.core.managers.config_manager import ErrorParametro
    from autoclave.core.runtime import respaldo as rp
    from autoclave.utils.archivos import escribir_texto_atomico
    entidad = "/backup/restore"
    with guard_estado(DISTINTO_DE_CICLO, entidad, sesion):
        pass
    unidad = _unidad_detectada(body.unidad, entidad, sesion)
    try:
        ruta = rp.ruta_respaldo_segura(unidad, body.archivo)
        m, datos = rp.leer(ruta)
    except rp.ErrorRespaldo as e:
        _auditar("respaldo_rechazado", sesion, entidad=entidad,
                 detalle={"archivo": body.archivo, "motivo": e.codigo})
        raise RechazoApi(422, e.codigo, "Respaldo inválido")
    motivo = rp.validar_para_equipo(m, _meta_equipo(), _version_sw())
    if motivo:
        _auditar("respaldo_rechazado", sesion, entidad=entidad,
                 detalle={"archivo": body.archivo, "motivo": motivo, "serie_respaldo": m.get("serie")})
        raise RechazoApi(409, motivo, "El respaldo no corresponde a este equipo",
                         extra={"serie_respaldo": m.get("serie", "")})
    if not body.confirmar:
        raise RechazoApi(428, "confirmacion_requerida", "Confirme la restauración",
                         extra={"partes": m.get("partes", {})})
    # validar todo ANTES de escribir nada. SAF-02 de O2h: los programas NO se
    # restauran (no hay aún un validador común con el editor de parámetros);
    # quedan en el respaldo como referencia.
    params = {}
    if "parametros.json" in datos:
        try:
            params = json.loads(datos["parametros.json"].decode("utf-8"))
        except ValueError:
            raise RechazoApi(422, "parametros_invalidos", "Respaldo inválido")
        if not isinstance(params, dict):
            raise RechazoApi(422, "parametros_invalidos", "Respaldo inválido")
    calib = datos.get("calibracion.yaml")
    if calib is not None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            prueba = Path(tmp) / "calibration.yaml"
            prueba.write_bytes(calib)
            try:
                cfg_resp = load_config(prueba)
            except Exception:
                raise RechazoApi(422, "calibracion_invalida", "Respaldo inválido")
        # Tanda 19 (MOD-04): una calibración de otro enlace de E/S (el serial
        # retirado en la tanda 20, T20-03: cuentas del ADC; Modbus: µA y
        # décimas de °C) pisaría la escala de fábrica y las lecturas saldrían
        # mal. Revisión R (V19-s2-02): se compara TODA la sección de fábrica
        # (temperatura y presión) con la del archivo activo; cualquier
        # diferencia rechaza. Fail-closed: si el activo no se puede leer,
        # también. Rechaza además un respaldo con otra fábrica del mismo
        # enlace (falla cerrada).
        if not _misma_fabrica(cfg_resp):
            _auditar("respaldo_rechazado", sesion, entidad=entidad,
                     detalle={"archivo": body.archivo, "motivo": "calibracion_otro_enlace"})
            raise RechazoApi(422, "calibracion_otro_enlace",
                             "La calibración del respaldo es de otro enlace de E/S o de "
                             "otra calibración de fábrica (temperatura o presión distinta "
                             "de la activa); no se restaura")
        # SAF-01 de O2h: misma plausibilidad que la calibración manual, canal
        # por canal; lo dudoso (aviso) también se rechaza: fail-closed
        for tipo, mapa, lista in (("temperature", EstadoAutoclave.map_temp,
                                   cfg_resp.calibration.user.temperature),
                                  ("pressure", EstadoAutoclave.map_pres,
                                   cfg_resp.calibration.user.pressure)):
            for sensor, i in mapa.items():
                if i >= len(lista):
                    raise RechazoApi(422, "calibracion_invalida", "Respaldo inválido")
                c = lista[i]
                nivel, motivo_c = (("aviso", "polinomio") if c.poly else
                                   evaluar_desviacion_acumulada(tipo, float(c.gain),
                                                                float(c.offset), sensor))
                if nivel is not None:
                    _auditar("respaldo_rechazado", sesion, entidad=entidad,
                             detalle={"archivo": body.archivo, "motivo": "calibracion_implausible",
                                      "sensor": sensor, "detalle": motivo_c})
                    raise RechazoApi(422, "calibracion_implausible",
                                     f"Calibración no plausible en {sensor}: {motivo_c}")
    # R8 (D8-5.12): la asignación de E/S se valida antes de escribir nada; solo
    # el ingeniero la restaura y rige al reiniciar el control
    asignacion_io = datos.get(_reasignacion.RUTA_EN_RESPALDO)
    if asignacion_io is not None and sesion.rol == ROL_INGENIERO:
        from autoclave.core.runtime import asignacion_io as _aio
        try:
            _reasignacion.validar_respaldo(asignacion_io)
        except _aio.ErrorAsignacion as e:
            _auditar("respaldo_rechazado", sesion, entidad=entidad,
                     detalle={"archivo": body.archivo, "motivo": "asignacion_io_invalida",
                              "errores": e.errores})
            raise RechazoApi(422, "asignacion_io_invalida", "Respaldo inválido")
    aplicado = {"calibracion": False, "parametros": [], "parametros_omitidos": [], "programas": []}
    with _lock_respaldo:
      try:
        if calib is not None:
            with _lock_archivos:
                with context.control_loop.bloqueo_maquina():     # SAF-03: de nuevo, justo antes
                    en_ciclo = context.estado.get_machine_state() == GlobalState.CICLO
                if en_ciclo:
                    _rechazar(409, "estado_no_permitido", "Hay un ciclo en curso", entidad, sesion)
                escribir_texto_atomico(CALIBRATION_PATH, calib.decode("utf-8"))
                context.units.reload_calibration(CALIBRATION_PATH)   # SAF-04: sin reiniciar
            aplicado["calibracion"] = True
        cm = context.config_manager
        for clave, valor in params.items():
            try:
                p = cm.describir(clave)
            except ErrorParametro:
                aplicado["parametros_omitidos"].append(clave)
                continue
            if p["solo_lectura"] or p["valor"] == valor:
                if p["solo_lectura"]:
                    aplicado["parametros_omitidos"].append(clave)
                continue
            with cm.lock_cambios:
                try:
                    anterior, nuevo = cm.fijar(clave, valor, sesion.usuario, aplicar=False)
                except ErrorParametro:
                    aplicado["parametros_omitidos"].append(clave)
                    continue
                try:
                    with guard_estado(DISTINTO_DE_CICLO, entidad, sesion):
                        cm.aplicar_valor(clave, nuevo, sesion.usuario)
                except RechazoApi:
                    cm.revertir_bd(clave, anterior)
                    raise
            aplicado["parametros"].append(clave)
        if asignacion_io is not None:
            aplicado.update(_reasignacion.restaurar_respaldo(asignacion_io, sesion, entidad))
      finally:
        # SAF-03: se audita siempre lo que sí se aplicó, también si falla a medias
        _auditar("respaldo_restaurado", sesion, entidad=entidad,
                 detalle={"archivo": body.archivo, "creado_en": m.get("creado_en"), **aplicado})
    return {"ok": True, **aplicado,
            "reinicio_requerido": aplicado.get("asignacion_io") is True}

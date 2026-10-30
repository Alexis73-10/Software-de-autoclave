# tests/test_r8_reasignacion_api.py
#
# R8 (tanda 8, D8-5.12): API de la reasignación de E/S. Permisos (solo el
# ingeniero), fuera de ciclo, conflictos y puertos inexistentes rechazados en
# el backend, doble confirmación, confirmación reforzada, reautenticación,
# persistencia en data/, bitácora, reinicio y restauración de fábrica; y su
# paso por el respaldo (O2h).
#
# Tanda 19 (decisión 4 de Cristian, MOD-05): el buzzer ocupa DO 25. Las pruebas
# que usaban DO 25 como puerto libre (vapor_camara, y descompresion_lenta para
# el conflicto con vapor_camara) usan ahora DO 27 (DO 26 ya lo usan otras
# pruebas de este archivo); la intención y las expectativas no cambian.

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autoclave.core.runtime import asignacion_io as aio
from autoclave.state_machine.machine.enum_global import GlobalState
from tests.helpers.backend_doble import modulo_backend, parchear_en_backend, fuente_backend

CLAVE = "Ingeniero-2026"


@pytest.fixture(autouse=True)
def _mapas_de_fabrica():
    aio.restablecer_memoria_fabrica_codigo()
    yield
    aio.restablecer_memoria_fabrica_codigo()


@pytest.fixture
def api(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from autoclave.backend import reinicio
    from autoclave.services.domain.logging.db_manager import DbManager
    from tests.helpers.backend_doble import cabecera, cargar_servidor
    ctx = MagicMock()
    ctx.db = DbManager(db_path=tmp_path / "t.db")
    ctx.sin_base_de_datos = False
    srv, _ = cargar_servidor(ctx)
    ctx.db.crear_usuario("Inés", "ines", modulo_backend("rutas.usuarios").hash_password(CLAVE), "ingeniero")
    ctx.db.crear_usuario("Tomás", "tomas", modulo_backend("rutas.usuarios").hash_password(CLAVE), "tecnico")
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    ctx.control_loop.test_mode_active = False
    ctx.control_loop.apagando = False
    ctx.control_loop.estado_seguro.activo = False
    # ESS-07: sin paro, cámara segura (fría y a atm) con datos vigentes
    ctx.estado.get_flag.return_value = False
    ctx.estado.sensores_pres = {"pres_camara": 101.3}
    ctx.estado.sensores_temp = {"temp_camara": 30.0}
    ctx.config_manager = {"presion_admosferica": 101.3, "rango_presion_atm": 5.0,
                          "temp_max_apertura": 80.0}
    ctx.programas_para_seguridad.return_value = []   # como el real sin programa
    ctx.temp_max_tras_ciclo.return_value = None
    ctx.profile = None
    ctx.control_loop.presion_vigente = True
    ctx.archivo_asignacion = aio.ArchivoAsignacion(tmp_path / "data" / "asignacion_io.json")
    ctx.asignacion_fabrica = aio.fabrica_codigo()
    ctx.motivo_asignacion = ""
    ctx.verificacion_asignacion = {"estado": "sin_cambios", "funciones": {}}
    ctx.asignacion_pendiente = []
    ctx.asignacion_modificada_en = ""
    pedidos = []
    reinicio.registrar(lambda: pedidos.append("detenido"))
    monkeypatch.setattr(reinicio, "solicitar", lambda motivo, **k: pedidos.append(motivo) or True)
    cliente = TestClient(srv.app)
    yield cliente, srv, ctx, (lambda rol="ingeniero", usuario="ines": cabecera(srv, rol, usuario)), pedidos
    reinicio.registrar(None)
    ctx.db.close()


def _auditoria(ctx, evento=None):
    filas, _ = ctx.db.consultar_auditoria(evento=evento, limite=100)
    return filas


def _aplicar(cliente, cab, cambios, **extra):
    cuerpo = {"cambios": cambios, "clave": CLAVE, "confirmar": True, **extra}
    return cliente.post("/io/assignment", json=cuerpo, headers=cab)


# ── permisos ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("rol", ["tecnico", "admin"])
def test_solo_el_ingeniero(api, rol):
    cliente, _srv, ctx, cab, pedidos = api
    h = cab(rol, "tomas")
    assert cliente.get("/io/assignment", headers=h).status_code == 403
    r = _aplicar(cliente, h, {"vapor_camara": 27})
    assert r.status_code == 403 and r.json()["codigo"] == "rol_sin_permiso"
    r = cliente.post("/io/assignment/factory", json={"clave": CLAVE, "confirmar": True}, headers=h)
    assert r.status_code == 403
    assert not ctx.archivo_asignacion.existe() and pedidos == []


def test_sin_sesion_401(api):
    cliente = api[0]
    assert cliente.get("/io/assignment").status_code == 401


# ── estado (fuera de ciclo) ─────────────────────────────────────────────────

def test_rechazado_en_ciclo(api):
    cliente, _srv, ctx, cab, pedidos = api
    ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    r = _aplicar(cliente, cab(), {"vapor_camara": 27})
    assert r.status_code == 409 and r.json()["motivo"] == "ciclo"
    assert not ctx.archivo_asignacion.existe() and pedidos == []
    assert cliente.get("/io/assignment", headers=cab()).json()["editable"] is False


def _estado_seguro_actuando(ctx, liquido=False, sellado=False, confirmar=False):
    es = ctx.control_loop.estado_seguro
    es.activo = True
    es.requiere_confirmacion = confirmar
    es._protocolo.sellado = sellado
    es._protocolo.es_liquido.return_value = liquido


def test_permitido_en_falla_y_con_estado_seguro_actuando(api, monkeypatch):
    """Cambio urgente 28-oct: en FALLA y con el protocolo de estado seguro
    actuando sobre una carga sólida se puede reasignar (sensor de presión de
    cámara dañado)."""
    cliente, srv, ctx, cab, pedidos = api
    ctx.estado.get_machine_state.return_value = GlobalState.FALLA
    _estado_seguro_actuando(ctx)
    assert cliente.get("/io/assignment", headers=cab()).json()["editable"] is True
    r = _aplicar(cliente, cab(), {"vapor_camara": 27})
    assert r.status_code == 200, r.text
    assert ctx.archivo_asignacion.existe() and pedidos


# ══ ESS-07 / tanda 24 ═══════════════════════════════════════════════════
# Las pruebas de ESS-07 (SAF-01, SAF-03, H1) se retiraron con RSB-01 (tanda
# 24): la reasignación ya no se bloquea por sensores, paro ni estado seguro.
# El comportamiento nuevo está en tests/test_ess07_reasignacion_reinicio.py.


def test_rechazado_en_modo_prueba(api):
    cliente, _srv, ctx, cab, pedidos = api
    ctx.control_loop.test_mode_active = True
    r = _aplicar(cliente, cab(), {"vapor_camara": 27})
    assert r.status_code == 409 and r.json()["motivo"] == "modo_prueba"


def test_ciclo_iniciado_entre_la_validacion_y_el_guardado_deshace_la_escritura(api):
    """Re-comprobación bajo el lock tras escribir: si ya no se puede, el
    archivo vuelve a como estaba y no se reinicia ni se detiene el lazo."""
    cliente, srv, ctx, cab, pedidos = api
    estados = iter([GlobalState.PREPARADO] + [GlobalState.CICLO] * 10)
    ctx.estado.get_machine_state.side_effect = lambda: next(estados)
    r = _aplicar(cliente, cab(), {"vapor_camara": 27})
    assert r.status_code == 409
    assert not ctx.archivo_asignacion.existe()
    ctx.control_loop.iniciar_apagado.assert_not_called()
    assert pedidos == []


# ── conflictos y puertos inexistentes (backend) ────────────────────────────

@pytest.mark.parametrize("cambios,codigo", [
    ({"vapor_camara": 3}, "conflicto"),
    ({"paro_emergencia": 1}, "conflicto"),
    ({"vapor_camara": 40}, "puerto_inexistente"),
    ({"puerta_1_cerrada": 52}, "puerto_inexistente"),
    ({"pres_camara": 17}, "puerto_inexistente"),     # tanda 23: AI 01-16
    ({"pres_camara": 2}, "conflicto"),               # AI 02 es pres_chaqueta
    ({"funcion_falsa": 25}, "funcion_desconocida"),
])
def test_conflictos_rechazados_en_el_backend(api, cambios, codigo):
    cliente, _srv, ctx, cab, pedidos = api
    r = _aplicar(cliente, cab(), cambios)
    assert r.status_code == 422 and r.json()["codigo"] == codigo
    assert not ctx.archivo_asignacion.existe() and pedidos == []


def test_conflicto_con_la_asignacion_ya_guardada(api):
    """El conflicto se evalúa contra la vigente, no contra la de fábrica."""
    cliente, _srv, ctx, cab, _p = api
    ctx.archivo_asignacion.guardar({"vapor_camara": 27}, "ines", [])
    r = _aplicar(cliente, cab(), {"descompresion_lenta": 27})
    assert r.status_code == 422 and r.json()["errores"][0]["ocupado_por"] == "vapor_camara"


def test_sin_cambios(api):
    cliente, _srv, _ctx, cab, _p = api
    assert _aplicar(cliente, cab(), {"vapor_camara": 4}).json()["codigo"] == "sin_cambios"
    assert _aplicar(cliente, cab(), {}).json()["codigo"] == "sin_cambios"


# ── confirmaciones y reautenticación ───────────────────────────────────────

def test_doble_confirmacion_con_alerta_de_criticidad(api):
    cliente, _srv, ctx, cab, _p = api
    r = cliente.post("/io/assignment", json={"cambios": {"vapor_camara": 27, "DO:agua_bomba": 26},
                                             "clave": CLAVE}, headers=cab())
    assert r.status_code == 428 and r.json()["codigo"] == "confirmacion_requerida"
    assert r.json()["criticas"] == ["vapor_camara"]
    assert not ctx.archivo_asignacion.existe()


def test_reforzada_exige_escribir_el_nombre(api):
    # T20-03 / MOD-05: DI 16 (antes DI 30; con los módulos M31-U solo hay DI 01-16)
    cliente, _srv, ctx, cab, pedidos = api
    r = _aplicar(cliente, cab(), {"paro_emergencia": 16})
    assert r.status_code == 428 and r.json()["codigo"] == "confirmacion_reforzada"
    assert r.json()["funciones"] == ["paro_emergencia"]
    r = _aplicar(cliente, cab(), {"paro_emergencia": 16}, nombres={"paro_emergencia": "paro"})
    assert r.status_code == 422 and r.json()["codigo"] == "nombre_no_coincide"
    assert not ctx.archivo_asignacion.existe()
    r = _aplicar(cliente, cab(), {"paro_emergencia": 16},
                 nombres={"paro_emergencia": "  PARO  de emergencia "})
    assert r.status_code == 200, r.text
    assert pedidos


@pytest.mark.parametrize("escrito", ["Puerta 1 cerrada", "Door 1 closed"])
def test_reforzada_acepta_el_nombre_en_espanol_o_ingles(api, escrito):
    from autoclave import i18n
    if i18n.t("io.di.puerta_1_cerrada", "en") != "Door 1 closed" and escrito != "Puerta 1 cerrada":
        escrito = i18n.t("io.di.puerta_1_cerrada", "en")
    cliente, _srv, _ctx, cab, _p = api
    # T20-03 / MOD-05: DI 15 (antes DI 20)
    r = _aplicar(cliente, cab(), {"puerta_1_cerrada": 15}, nombres={"puerta_1_cerrada": escrito})
    assert r.status_code == 200, r.text


def test_reautenticacion(api):
    cliente, _srv, ctx, cab, pedidos = api
    r = _aplicar(cliente, cab(), {"vapor_camara": 27}, clave="mala")
    assert r.status_code == 403 and r.json()["codigo"] == "reautenticacion_fallida"
    r = _aplicar(cliente, cab(), {"vapor_camara": 27}, clave="")
    assert r.status_code == 403 and r.json()["codigo"] == "reautenticacion_requerida"
    assert not ctx.archivo_asignacion.existe() and pedidos == []


def test_reautenticacion_fallida_suma_al_bloqueo(api):
    cliente, _srv, ctx, cab, _p = api
    h = cab()
    codigos = [_aplicar(cliente, h, {"vapor_camara": 27}, clave="mala").status_code for _ in range(5)]
    assert codigos[-1] == 429
    # el token quedó invalidado
    assert cliente.get("/io/assignment", headers=h).status_code == 401


# ── aplicar: persistencia, bitácora y reinicio ─────────────────────────────

def test_aplicar_guarda_en_data_audita_y_reinicia(api):
    cliente, _srv, ctx, cab, pedidos = api
    r = _aplicar(cliente, cab(), {"vapor_camara": 27, "pres_camara": 13})
    assert r.status_code == 200, r.text
    assert r.json()["reinicio"] is True
    datos = json.loads(ctx.archivo_asignacion.ruta.read_text(encoding="utf-8"))
    assert datos["cambios"] == {"pres_camara": 13, "vapor_camara": 27}
    assert datos["verificacion_pendiente"] == ["pres_camara", "vapor_camara"]
    assert datos["modificado_por"] == "ines"
    ctx.control_loop.iniciar_apagado.assert_called_once()
    assert len(pedidos) == 1
    filas = {f["entidad"]: f for f in _auditoria(ctx, "reasignacion_io")}
    assert filas["vapor_camara"]["valor_anterior"] == "DO 04"
    assert filas["vapor_camara"]["valor_nuevo"] == "DO 27"
    assert filas["vapor_camara"]["usuario"] == "ines"
    assert filas["pres_camara"]["valor_nuevo"] == "AI 13"
    assert _auditoria(ctx, "reinicio_control")
    # la memoria no cambia en caliente: rige al reiniciar
    assert aio.en_memoria() == aio.fabrica_codigo()
    g = cliente.get("/io/assignment", headers=cab()).json()
    assert g["reinicio_pendiente"] is True and g["cambios_guardados"] == {"pres_camara": 13, "vapor_camara": 27}


def test_intercambio_de_puertos(api):
    cliente, _srv, ctx, cab, _p = api
    r = _aplicar(cliente, cab(), {"vapor_camara": 3, "vapor_chaqueta": 4})
    assert r.status_code == 200, r.text
    assert aio.ArchivoAsignacion(ctx.archivo_asignacion.ruta).leer()["cambios"] == {
        "vapor_camara": 3, "vapor_chaqueta": 4}


def test_sin_mecanismo_de_reinicio_guarda_y_no_detiene_el_lazo(api, monkeypatch):
    from autoclave.backend import reinicio
    cliente, _srv, ctx, cab, _p = api
    reinicio.registrar(None)
    r = _aplicar(cliente, cab(), {"vapor_camara": 27})
    assert r.status_code == 200 and r.json()["reinicio"] is False
    assert ctx.archivo_asignacion.existe()
    ctx.control_loop.iniciar_apagado.assert_not_called()


def test_get_tabla(api):
    cliente, _srv, ctx, cab, _p = api
    d = cliente.get("/io/assignment", headers=cab()).json()
    filas = {f["funcion"]: f for f in d["filas"]}
    assert filas["vapor_camara"]["id_actual"] == "DO 04" and filas["vapor_camara"]["tipo"] == "DO"
    assert filas["vapor_camara"]["critica"] is True and filas["vapor_camara"]["reforzada"] is False
    assert filas["paro_emergencia"]["reforzada"] is True
    assert filas["pres_camara"]["id_actual"] == "AI 01" and filas["pres_camara"]["temperatura"] is False
    assert filas["temp_referencia"]["tipo"] == "AI" and filas["temp_referencia"]["temperatura"] is True
    # T20-03 / MOD-05: último DI 16 (antes 48, rango del enlace serial)
    assert d["puertos"]["DO"] == list(range(1, 33)) and d["puertos"]["DI"][-1] == 16
    assert d["ocupados"]["DO"]["2"] == "vapor_caldera"     # no habilitada, pero ocupa
    assert d["editable"] is True and d["reinicio_pendiente"] is False


def test_nombre_en_dos_tipos_da_dos_filas_y_se_reasigna_solo_el_de_su_tipo(api):
    """agua_bomba es DI 09 (retorno) y DO 18 (mando): cada una con su fila y su
    clave con el tipo delante; reasignar la DI no toca la DO."""
    # T20-03 / MOD-05: DI 16 (antes DI 30; con los módulos M31-U solo hay DI 01-16)
    cliente, _srv, ctx, cab, _p = api
    d = cliente.get("/io/assignment", headers=cab()).json()
    filas = {f["funcion"]: f for f in d["filas"]}
    assert filas["DI:agua_bomba"]["id_actual"] == "DI 09" and filas["DO:agua_bomba"]["id_actual"] == "DO 18"
    assert d["ocupados"]["DI"]["9"] == "DI:agua_bomba"
    assert _aplicar(cliente, cab(), {"agua_bomba": 16}).status_code == 422      # ambiguo
    r = _aplicar(cliente, cab(), {"DI:agua_bomba": 16})
    assert r.status_code == 200, r.text
    nueva, _ = aio.vigente(aio.fabrica_codigo(), ctx.archivo_asignacion)
    assert nueva["DI"]["agua_bomba"] == 16 and nueva["DO"]["agua_bomba"] == 18
    fila = next(f for f in _auditoria(ctx, "reasignacion_io") if f["entidad"] == "DI:agua_bomba")
    assert (fila["valor_anterior"], fila["valor_nuevo"]) == ("DI 09", "DI 16")


# ── restaurar fábrica ──────────────────────────────────────────────────────

def test_restaurar_fabrica(api):
    cliente, _srv, ctx, cab, pedidos = api
    ctx.archivo_asignacion.guardar({"vapor_camara": 27}, "ines", [])
    aio.aplicar_en_memoria(aio.combinar(aio.fabrica_codigo(), {"vapor_camara": 27}))
    r = cliente.post("/io/assignment/factory", json={"clave": CLAVE}, headers=cab())
    assert r.status_code == 428
    r = cliente.post("/io/assignment/factory", json={"clave": CLAVE, "confirmar": True}, headers=cab())
    assert r.status_code == 200, r.text
    datos = aio.ArchivoAsignacion(ctx.archivo_asignacion.ruta).leer()
    assert datos["cambios"] == {} and datos["verificacion_pendiente"] == ["vapor_camara"]
    [fila] = _auditoria(ctx, "reasignacion_io_fabrica")
    assert fila["valor_anterior"] == "DO 27" and fila["valor_nuevo"] == "DO 04"
    assert pedidos


def test_restaurar_fabrica_con_el_archivo_danado(api):
    """Camino de salida del bloqueo: el archivo dañado se reescribe."""
    cliente, _srv, ctx, cab, _p = api
    ctx.archivo_asignacion.ruta.parent.mkdir(parents=True, exist_ok=True)
    ctx.archivo_asignacion.ruta.write_text("{dañado", encoding="utf-8")
    assert cliente.get("/io/assignment", headers=cab()).json()["error_archivo"] == "archivo_ilegible"
    r = cliente.post("/io/assignment/factory", json={"clave": CLAVE, "confirmar": True}, headers=cab())
    assert r.status_code == 200, r.text
    assert aio.ArchivoAsignacion(ctx.archivo_asignacion.ruta).leer()["cambios"] == {}


def test_restaurar_fabrica_sin_nada_que_restaurar(api):
    cliente, _srv, _ctx, cab, _p = api
    r = cliente.post("/io/assignment/factory", json={"clave": CLAVE, "confirmar": True}, headers=cab())
    assert r.status_code == 422 and r.json()["codigo"] == "sin_cambios"


# ── respaldo (O2h) ─────────────────────────────────────────────────────────

@pytest.fixture
def respaldo(api, tmp_path, monkeypatch):
    from autoclave.core.managers.config_manager import ConfigManager
    from autoclave.utils.paths import calibration_path
    cliente, srv, ctx, cab, pedidos = api
    c = ConfigManager(); c.load_config(); c.vincular_bd(ctx.db)
    ctx.config_manager = c
    perfil = MagicMock(); perfil.serial_number = "ACV-2026-001"; perfil.model_id = "M-1"
    ctx.profile = perfil
    programas = tmp_path / "user"; programas.mkdir()
    ctx.cycle_manager.carpeta.return_value = str(programas)
    usb = tmp_path / "usb"; usb.mkdir()
    calib = tmp_path / "calibration.yaml"
    calib.write_bytes(Path(calibration_path()).read_bytes())
    parchear_en_backend(monkeypatch, "CALIBRATION_PATH", calib)
    monkeypatch.setattr(modulo_backend("rutas.respaldo"), "_unidades_usb", lambda: [{"ruta": str(usb), "libre_bytes": 8e9}])
    monkeypatch.setattr(modulo_backend("rutas.respaldo"), "_version_sw", lambda: "1.2.0")
    return cliente, srv, ctx, cab, usb


def _exportar(cliente, cab, usb):
    r = cliente.post("/backup/export", json={"unidad": str(usb), "usuarios": False}, headers=cab)
    assert r.status_code == 200, r.text
    return r.json()["archivo"]


def test_respaldo_incluye_y_restaura_la_asignacion(respaldo):
    cliente, _srv, ctx, cab, usb = respaldo
    ctx.archivo_asignacion.guardar({"vapor_camara": 27}, "ines", [])
    archivo = _exportar(cliente, cab(), usb)
    from autoclave.core.runtime import respaldo as rp
    _m, datos = rp.leer(usb / rp.CARPETA / archivo)
    assert json.loads(datos["asignacion_io.json"])["cambios"] == {"vapor_camara": 27}
    ctx.archivo_asignacion.ruta.unlink()
    r = cliente.post("/backup/restore", json={"unidad": str(usb), "archivo": archivo, "confirmar": True},
                     headers=cab())
    assert r.status_code == 200, r.text
    assert r.json()["asignacion_io"] is True and r.json()["reinicio_requerido"] is True
    assert aio.ArchivoAsignacion(ctx.archivo_asignacion.ruta).leer()["cambios"] == {"vapor_camara": 27}
    assert any(f["entidad"] == "vapor_camara" for f in _auditoria(ctx, "reasignacion_io"))


def test_respaldo_restaurado_por_tecnico_no_toca_la_asignacion(respaldo):
    cliente, _srv, ctx, cab, usb = respaldo
    ctx.archivo_asignacion.guardar({"vapor_camara": 27}, "ines", [])
    archivo = _exportar(cliente, cab(), usb)
    ctx.archivo_asignacion.ruta.unlink()
    r = cliente.post("/backup/restore", json={"unidad": str(usb), "archivo": archivo, "confirmar": True},
                     headers=cab("tecnico", "tomas"))
    assert r.status_code == 200, r.text
    assert r.json()["asignacion_io_omitida"] == "rol" and r.json()["reinicio_requerido"] is False
    assert not ctx.archivo_asignacion.existe()


def test_respaldo_con_asignacion_invalida_se_rechaza_sin_escribir(respaldo):
    from autoclave.core.runtime import respaldo as rp
    cliente, _srv, ctx, cab, usb = respaldo
    contenido = {"perfil.json": b"{}", "asignacion_io.json":
                 json.dumps({"formato": 1, "cambios": {"vapor_camara": 3}}).encode()}
    datos = rp.crear({"serie": "ACV-2026-001", "modelo": "M-1"}, {"perfil_calibracion": True},
                     contenido, "ines", "1.2.0")
    carpeta = usb / rp.CARPETA; carpeta.mkdir()
    (carpeta / "respaldo_ACV-2026-001_x.zip").write_bytes(datos)
    r = cliente.post("/backup/restore", json={"unidad": str(usb), "archivo": "respaldo_ACV-2026-001_x.zip",
                                              "confirmar": True}, headers=cab())
    assert r.status_code == 422 and r.json()["codigo"] == "asignacion_io_invalida"
    assert not ctx.archivo_asignacion.existe()


# ── revisión R8: SEN-01, verificación por el ingeniero, escritura ──────────

def test_puerto_analogico_sin_calibracion_se_rechaza(api, monkeypatch):
    """SEN-01: una calibración con 7 entradas de presión de usuario: AI 08
    no tiene calibración y no se puede asignar (tanda 23: AI 01-16)."""
    from autoclave.backend import server_reasignacion as sr
    cliente, _srv, ctx, cab, _p = api
    monkeypatch.setattr(sr, "_largos_calibracion", lambda: {"temperatura": 8, "presion": 7})
    r = _aplicar(cliente, cab(), {"pres_camara": 8})
    assert r.status_code == 422 and r.json()["codigo"] == "puerto_sin_calibracion"
    assert not ctx.archivo_asignacion.existe()
    assert _aplicar(cliente, cab(), {"pres_camara": 7}).status_code == 200


def test_calibracion_real_cubre_los_puertos_ofrecidos_o_se_rechazan(api):
    """Con la calibración del repositorio, cada puerto analógico de presión o
    tiene calibración o la validación lo rechaza (nunca se lee sin corregir)."""
    from autoclave.backend import server_reasignacion as sr
    largos = sr._largos_calibracion()
    assert largos["temperatura"] > 0 and largos["presion"] > 0
    f = aio.fabrica_codigo()
    for puerto in aio.puertos()["AI_PRES"]:
        nueva = aio.combinar(f, {"pres_camara": puerto})
        errores = aio.puertos_sin_calibracion(nueva, largos)
        con_cal = puerto - 1 < largos["presion"]          # tanda 23: AI 01-16
        assert (not any(e["funcion"] == "pres_camara" for e in errores)) == con_cal


def _pendiente(ctx, funciones, cambios):
    ctx.archivo_asignacion.guardar(cambios, "ines", funciones)
    aio.aplicar_en_memoria(aio.combinar(aio.fabrica_codigo(), cambios))
    ctx.asignacion_pendiente = list(funciones)
    ctx.asignacion_modificada_en = "2000-01-01T00:00:00"
    ctx.asignacion_di_cambio = set()
    ctx.asignacion_evidencia = {}


def _verificar(cliente, cab, funcion, **extra):
    return cliente.post("/io/assignment/verify", json={"funcion": funcion, "clave": CLAVE, **extra},
                        headers=cab)


def test_verificar_salida_exige_accionarla_en_modo_prueba_despues_de_reasignar(api):
    cliente, _srv, ctx, cab, _p = api
    _pendiente(ctx, ["vapor_camara"], {"vapor_camara": 27})
    r = _verificar(cliente, cab(), "vapor_camara")
    assert r.status_code == 409 and r.json()["codigo"] == "sin_prueba_de_salida"
    g = cliente.get("/io/assignment", headers=cab()).json()
    assert g["pendientes"] == ["vapor_camara"]
    assert g["verificacion"]["funciones"]["vapor_camara"]["falta"] == "sin_prueba_de_salida"
    # una prueba registrada en la bitácora (p. ej. de antes del reinicio) no cuenta
    ctx.db.registrar_auditoria("salida_prueba", usuario="ines", entidad="vapor_camara", valor_nuevo=True)
    assert _verificar(cliente, cab(), "vapor_camara").status_code == 409
    from autoclave.backend import server_reasignacion as sr
    sr.evidencia_do("vapor_camara")          # gancho de /io/test/output en este arranque
    r = _verificar(cliente, cab(), "vapor_camara")
    assert r.status_code == 200, r.text
    assert ctx.asignacion_pendiente == [] and r.json()["pendientes"] == []
    assert aio.ArchivoAsignacion(ctx.archivo_asignacion.ruta).leer()["verificacion_pendiente"] == []
    fila = _auditoria(ctx, "reasignacion_io_verificada")[0]
    assert fila["usuario"] == "ines" and fila["valor_nuevo"] == "DO 27"
    assert fila["detalle"]["metodo"] == "ingeniero"
    ctx.alarma_asignacion_sin_verificar.assert_called()


def test_evidencia_de_una_funcion_no_pendiente_no_se_guarda(api):
    from autoclave.backend import server_reasignacion as sr
    cliente, _srv, ctx, cab, _p = api
    _pendiente(ctx, ["vapor_camara"], {"vapor_camara": 27})
    sr.evidencia_do("bomba_vacio")
    assert ctx.asignacion_evidencia == {}
    sr.evidencia_do("vapor_camara")
    assert ctx.asignacion_evidencia == {"vapor_camara": 27}


def test_verificar_rechazado_con_una_asignacion_guardada_que_aun_no_rige(api):
    """TMG-10/SAF-03 de la re-revisión: verificar no puede quitar la marca de
    lo que regirá en el próximo arranque."""
    from autoclave.backend import server_reasignacion as sr
    cliente, _srv, ctx, cab, _p = api
    _pendiente(ctx, ["vapor_camara"], {"vapor_camara": 27})
    sr.evidencia_do("vapor_camara")
    ctx.archivo_asignacion.guardar({"vapor_camara": 26}, "ines", ["vapor_camara"])
    r = _verificar(cliente, cab(), "vapor_camara")
    assert r.status_code == 409 and r.json()["codigo"] == "reinicio_pendiente"
    assert aio.ArchivoAsignacion(ctx.archivo_asignacion.ruta).leer()["verificacion_pendiente"] == ["vapor_camara"]


def test_ganchos_en_server():
    """El modo prueba registra la evidencia de las salidas; restaurar «último»
    se filtra por puerto. Tanda 24 (RSB-07): los ganchos de calibración de las
    analógicas se retiraron."""
    from autoclave.backend import server_reasignacion as sr
    texto = fuente_backend()
    assert "_reasignacion.evidencia_do(clave)" in texto
    assert "_reasignacion.ultimo_es_del_puerto_vigente(tipo, sensor, filas[0])" in texto
    assert "evidencia_ai" not in texto
    for gancho in ("evidencia_ai", "anular_evidencia_ai", "anular_evidencias_ai"):
        assert not hasattr(sr, gancho)


def test_ultimo_registro_de_calibracion_por_puerto(api):
    from autoclave.backend import server_reasignacion as sr
    _cliente, _srv, ctx, _cab, _p = api
    assert sr.ultimo_es_del_puerto_vigente("pressure", "pres_camara", {"detalle": {"puerto": 9}})
    assert sr.ultimo_es_del_puerto_vigente("pressure", "pres_camara", {"detalle": None})
    aio.aplicar_en_memoria(aio.combinar(aio.fabrica_codigo(), {"pres_camara": 13}))
    assert not sr.ultimo_es_del_puerto_vigente("pressure", "pres_camara", {"detalle": {"puerto": 9}})
    assert not sr.ultimo_es_del_puerto_vigente("pressure", "pres_camara", {"detalle": {}})
    # tanda 23 (AIN-05): un registro sin "formato" es de la numeración vieja
    # (AI 13 de entonces = AI 05); con "formato" 2, la nueva
    assert not sr.ultimo_es_del_puerto_vigente("pressure", "pres_camara", {"detalle": {"puerto": 13}})
    assert sr.ultimo_es_del_puerto_vigente("pressure", "pres_camara",
                                           {"detalle": {"puerto": 13, "formato": 2}})


def test_verificar_entrada_de_seguridad_exige_nombre_y_cambio_observado(api):
    cliente, _srv, ctx, cab, _p = api
    libre = next(p for p in aio.puertos()["DI"] if p not in aio.fabrica_codigo()["DI"].values())
    _pendiente(ctx, ["paro_emergencia"], {"paro_emergencia": libre})
    r = _verificar(cliente, cab(), "paro_emergencia")
    assert r.status_code == 428 and r.json()["codigo"] == "confirmacion_reforzada"
    r = _verificar(cliente, cab(), "paro_emergencia", nombre="Paro de emergencia")
    assert r.status_code == 409 and r.json()["codigo"] == "sin_cambio_observado"
    ctx.asignacion_di_cambio = {"paro_emergencia"}
    r = _verificar(cliente, cab(), "paro_emergencia", nombre="Paro de emergencia")
    assert r.status_code == 200, r.text


@pytest.mark.req("RSB-07")
def test_verificar_analogica_con_lectura_valida_sin_calibrar(api):
    """Tanda 24 (RSB-07): basta la lectura válida en el puerto nuevo; ya no se
    exige calibrar de nuevo (nunca calibracion_requerida). La auditoría guarda
    el método «lectura» y el valor leído."""
    cliente, _srv, ctx, cab, _p = api
    _pendiente(ctx, ["pres_camara"], {"pres_camara": 13})
    pres = [0.0] * 16
    ctx.units.get_all.return_value = {"connected": True, "pressure": pres, "temperature": [20.0] * 8}
    r = _verificar(cliente, cab(), "pres_camara")
    assert r.status_code == 409 and r.json()["codigo"] == "sin_lectura"
    g = cliente.get("/io/assignment", headers=cab()).json()
    assert g["verificacion"]["funciones"]["pres_camara"]["falta"] == "sin_lectura"
    assert g["verificacion"]["funciones"]["pres_camara"]["lectura"] is None
    pres[12] = 101.0                 # AI 13 (tanda 23)
    g = cliente.get("/io/assignment", headers=cab()).json()
    assert g["verificacion"]["funciones"]["pres_camara"] == {
        "estado": "pendiente", "falta": "", "lectura": 101.0}
    r = _verificar(cliente, cab(), "pres_camara")
    assert r.status_code == 200, r.text
    assert ctx.asignacion_pendiente == []
    fila = _auditoria(ctx, "reasignacion_io_verificada")[0]
    assert fila["valor_nuevo"] == "AI 13"
    assert fila["detalle"]["metodo"] == "lectura" and fila["detalle"]["lectura"] == 101.0
    assert fila["detalle"]["unidad"] == "kPa"


@pytest.mark.req("RSB-07")
def test_verificar_temperatura_con_lectura_valida_sin_calibrar(api):
    cliente, _srv, ctx, cab, _p = api
    _pendiente(ctx, ["temp_camara"], {"temp_camara": 4})
    temp = [None] * 6
    ctx.units.get_all.return_value = {"connected": True, "pressure": [101.0] * 16, "temperature": temp}
    assert _verificar(cliente, cab(), "temp_camara").json()["codigo"] == "sin_lectura"
    temp[3] = 25.5                   # RTD 04
    r = _verificar(cliente, cab(), "temp_camara")
    assert r.status_code == 200, r.text
    fila = _auditoria(ctx, "reasignacion_io_verificada")[0]
    assert fila["detalle"]["lectura"] == 25.5 and fila["detalle"]["unidad"] == "°C"


@pytest.mark.req("RSB-07")
@pytest.mark.parametrize("funcion,puerto,clave,valor", [
    ("temp_camara", 4, "temperature", 0.0),       # 0,0 °C = sin señal
    ("temp_camara", 4, "temperature", 250.0),     # fuera de 0-200 °C
    ("pres_camara", 13, "pressure", 500.0),       # fuera de -10-450 kPa
])
def test_verificar_analogica_fuera_del_rango_publicado_es_sin_lectura(api, funcion, puerto, clave, valor):
    """Revisión R de la tanda 24 (SAF-02): la lectura que cuenta es la que el
    control publicaría (P7 de la tanda 16)."""
    cliente, _srv, ctx, cab, _p = api
    _pendiente(ctx, [funcion], {funcion: puerto})
    datos = {"connected": True, "pressure": [101.0] * 16, "temperature": [25.0] * 6}
    datos[clave][puerto - 1] = valor
    ctx.units.get_all.return_value = datos
    r = _verificar(cliente, cab(), funcion)
    assert r.status_code == 409 and r.json()["codigo"] == "sin_lectura"
    assert ctx.asignacion_pendiente == [funcion]


@pytest.mark.req("RSB-07")
def test_verificar_analogica_sin_calibracion_en_el_puerto_rechazada(api, monkeypatch):
    """La calibración vigente del puerto sigue haciendo falta (la nominal
    cuenta); sin ella, puerto_sin_calibracion, aunque haya lectura."""
    cliente, srv, ctx, cab, _p = api
    _pendiente(ctx, ["pres_camara"], {"pres_camara": 13})
    ctx.units.get_all.return_value = {"connected": True, "pressure": [101.0] * 16,
                                      "temperature": [20.0] * 6}
    sr = modulo_backend("server_reasignacion")
    monkeypatch.setattr(sr, "_largos_calibracion", lambda: {"temperatura": 6, "presion": 8})
    r = _verificar(cliente, cab(), "pres_camara")
    assert r.status_code == 409 and r.json()["codigo"] == "puerto_sin_calibracion"
    assert ctx.asignacion_pendiente == ["pres_camara"]


def test_verificar_nunca_devuelve_calibracion_requerida():
    texto = (Path(__file__).resolve().parents[1] / "src/autoclave/backend/server_reasignacion.py"
             ).read_text(encoding="utf-8")
    assert '"calibracion_requerida"' not in texto


def test_verificar_rechazos(api):
    cliente, _srv, ctx, cab, _p = api
    from autoclave.backend import server_reasignacion as sr
    _pendiente(ctx, ["vapor_camara"], {"vapor_camara": 27})
    sr.evidencia_do("vapor_camara")
    assert _verificar(cliente, cab(), "bomba_vacio").json()["codigo"] == "no_pendiente"
    assert _verificar(cliente, cab("tecnico", "tomas"), "vapor_camara").status_code == 403
    r = cliente.post("/io/assignment/verify", json={"funcion": "vapor_camara", "clave": "mala"},
                     headers=cab())
    assert r.status_code == 403
    ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    assert _verificar(cliente, cab(), "vapor_camara").status_code == 409
    assert ctx.asignacion_pendiente == ["vapor_camara"]


def test_lo_pendiente_no_se_pierde_con_otra_reasignacion(api):
    """SAF-03: lo que seguía sin verificar sigue pendiente tras otra reasignación."""
    cliente, _srv, ctx, cab, _p = api
    libre = next(p for p in aio.puertos()["DI"] if p not in aio.fabrica_codigo()["DI"].values())
    _pendiente(ctx, ["paro_emergencia"], {"paro_emergencia": libre})
    r = _aplicar(cliente, cab(), {"vapor_camara": 27})
    assert r.status_code == 200, r.text
    assert aio.ArchivoAsignacion(ctx.archivo_asignacion.ruta).leer()["verificacion_pendiente"] == \
        ["paro_emergencia", "vapor_camara"]


def test_rechazado_con_un_reinicio_en_curso(api, monkeypatch):
    from autoclave.backend import reinicio
    cliente, _srv, ctx, cab, _p = api
    monkeypatch.setattr(reinicio, "solicitado", lambda: True)
    r = _aplicar(cliente, cab(), {"vapor_camara": 27})
    assert r.status_code == 409 and r.json()["codigo"] == "reinicio_en_curso"
    assert not ctx.archivo_asignacion.existe()


def test_restaurar_fabrica_con_bytes_no_utf8(api):
    """TMG-05: un archivo dañado con bytes que no son UTF-8 no impide la salida."""
    cliente, _srv, ctx, cab, _p = api
    ctx.archivo_asignacion.ruta.parent.mkdir(parents=True, exist_ok=True)
    ctx.archivo_asignacion.ruta.write_bytes(b"\xff\xfe\x00da\xf1ado")
    r = cliente.post("/io/assignment/factory", json={"clave": CLAVE, "confirmar": True}, headers=cab())
    assert r.status_code == 200, r.text


def test_deshacer_ante_cualquier_error_deja_el_archivo_como_estaba(api, monkeypatch):
    """TMG-07: un error inesperado al volver a comprobar el estado deshace."""
    cliente, srv, ctx, cab, _p = api
    ctx.archivo_asignacion.ruta.parent.mkdir(parents=True, exist_ok=True)
    ctx.archivo_asignacion.ruta.write_bytes(b"\xff previo")
    llamadas = []

    def falla(diferencias=None):
        llamadas.append(1)
        if len(llamadas) > 1:
            raise RuntimeError("inesperado")
        return "", ""
    monkeypatch.setattr(modulo_backend("server_reasignacion"), "_motivo_bloqueo", falla)
    with pytest.raises(RuntimeError):
        cliente.post("/io/assignment/factory", json={"clave": CLAVE, "confirmar": True}, headers=cab())
    assert ctx.archivo_asignacion.ruta.read_bytes() == b"\xff previo"


def test_get_lista_todas_las_funciones(api):
    """SEN-06: las que el equipo no usa también ocupan su puerto y se pueden mover."""
    cliente, _srv, ctx, cab, _p = api
    filas = cliente.get("/io/assignment", headers=cab()).json()["filas"]
    assert {f["funcion"] for f in filas} == set(aio.funciones())
    assert all(isinstance(f["habilitada"], bool) for f in filas)


def test_restaurar_calibracion_guarda_el_puerto(api):
    """3.ª vuelta R8 (sensores): el registro de la restauración lleva el
    puerto. Tanda 24 (RSB-07): restaurar ya no anula evidencia de analógicas
    (no la hay: se verifican por lectura)."""
    texto = fuente_backend()
    assert "anular_evidencia_ai" not in texto and "anular_evidencias_ai" not in texto
    assert '"accion": f"restaurar_{destino}",\n                   "puerto":' in texto


def test_verificar_relee_la_evidencia_bajo_los_locks():
    """RSB-07 conserva la relectura bajo _lock_escritura y _lock_archivos."""
    raiz = Path(__file__).resolve().parents[1] / "src/autoclave/backend"
    assert "with _lock_escritura, srv._lock_archivos:" in (raiz / "server_reasignacion.py").read_text(encoding="utf-8")

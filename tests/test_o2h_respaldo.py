# tests/test_o2h_respaldo.py
#
# O2h (tanda 6): respaldo y restauración por USB. Sin USB real: carpeta
# temporal como "unidad" y dobles del contexto.

import json
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autoclave.core.runtime import respaldo as rp
from tests.backend_doble import modulo_backend, parchear_en_backend

EQUIPO = {"serie": "ACV-2026-001", "modelo": "M-1"}


def _zip(tmp_path, equipo=EQUIPO, contenido=None, version="1.2.0"):
    contenido = contenido or {"parametros.json": b'{"timeout_puerta": 90}'}
    datos = rp.crear(equipo, {"parametros_programas": True}, contenido, "tec", version)
    carpeta = tmp_path / rp.CARPETA
    carpeta.mkdir(exist_ok=True)
    ruta = carpeta / rp.nombre_archivo(equipo["serie"], __import__("datetime").datetime(2026, 10, 21))
    ruta.write_bytes(datos)
    return ruta


def test_crear_y_leer_con_hashes(tmp_path):
    ruta = _zip(tmp_path)
    m, datos = rp.leer(ruta)
    assert m["serie"] == "ACV-2026-001" and m["formato"] == rp.FORMATO
    assert m["archivos"]["parametros.json"] == rp.sha256(datos["parametros.json"])
    assert rp.validar_para_equipo(m, EQUIPO, "1.9.9") == ""


def test_otra_serie_y_version(tmp_path):
    m, _ = rp.leer(_zip(tmp_path, equipo={"serie": "OTRO-9", "modelo": "M-1"}))
    assert rp.validar_para_equipo(m, EQUIPO, "1.2.0") == "otra_serie"
    assert rp.validar_para_equipo(m, {"serie": ""}, "1.2.0") == "otra_serie"
    m, _ = rp.leer(_zip(tmp_path))
    assert rp.validar_para_equipo(m, EQUIPO, "2.0.0") == "version"


def _reescribir(ruta, cambiar):
    with zipfile.ZipFile(ruta) as z:
        archivos = {n: z.read(n) for n in z.namelist()}
    cambiar(archivos)
    with zipfile.ZipFile(ruta, "w") as z:
        for n, d in archivos.items():
            z.writestr(n, d)


@pytest.mark.parametrize("alteracion,codigo", [
    (lambda a: a.__setitem__("parametros.json", b'{"timeout_puerta": 5}'), "hash_invalido"),
    (lambda a: a.pop("parametros.json"), "archivo_faltante"),
    (lambda a: a.__setitem__("manifiesto.json", a["manifiesto.json"].replace(b"ACV-2026-001", b"OTRO")),
     "manifiesto_alterado"),
    (lambda a: a.pop("manifiesto.json"), "sin_manifiesto"),
])
def test_integridad(tmp_path, alteracion, codigo):
    ruta = _zip(tmp_path)
    _reescribir(ruta, alteracion)
    with pytest.raises(rp.ErrorRespaldo) as e:
        rp.leer(ruta)
    assert e.value.codigo == codigo


def test_ilegible(tmp_path):
    p = tmp_path / "x.zip"
    p.write_bytes(b"no es zip")
    with pytest.raises(rp.ErrorRespaldo) as e:
        rp.leer(p)
    assert e.value.codigo == "ilegible"


@pytest.mark.parametrize("nombre", ["../x.zip", "respaldo_a/../../b.zip", "otro.zip", "respaldo_\\..\\x.zip"])
def test_ruta_segura(tmp_path, nombre):
    with pytest.raises(rp.ErrorRespaldo):
        rp.ruta_respaldo_segura(str(tmp_path), nombre)


def test_programas_invalidos():
    with pytest.raises(rp.ErrorRespaldo):
        rp.programas_del_respaldo({"programas/../x.json": b"{}"})
    with pytest.raises(rp.ErrorRespaldo):
        rp.programas_del_respaldo({"programas/a.json": b"[1]"})
    assert rp.programas_del_respaldo({"programas/a.json": b'{"id": 1}'}) == {"a.json": {"id": 1}}


# ── API ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def api(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from autoclave.core.managers.config_manager import ConfigManager
    from autoclave.services.domain.logging.db_manager import DbManager
    from autoclave.state_machine.machine.enum_global import GlobalState
    from tests.backend_doble import cabecera, cargar_servidor
    ctx = MagicMock()
    ctx.db = DbManager(db_path=tmp_path / "t.db")
    ctx.db.crear_usuario("Ana", "ana", "HASH-SECRETO-xyz", "tecnico") if hasattr(ctx.db, "crear_usuario") else None
    c = ConfigManager(); c.load_config(); c.vincular_bd(ctx.db)
    ctx.config_manager = c
    ctx.sin_base_de_datos = False
    perfil = MagicMock(); perfil.serial_number = EQUIPO["serie"]; perfil.model_id = EQUIPO["modelo"]
    ctx.profile = perfil
    programas = tmp_path / "user"; programas.mkdir()
    (programas / "instrumental_134.json").write_text('{"id": 2, "nombre": "I134"}', encoding="utf-8")
    ctx.cycle_manager.carpeta.return_value = str(programas)
    usb = tmp_path / "usb"; usb.mkdir()
    calib = tmp_path / "calibration.yaml"
    from autoclave.utils.paths import calibration_path
    calib.write_bytes(Path(calibration_path()).read_bytes())
    srv, _ = cargar_servidor(ctx)
    parchear_en_backend(monkeypatch, "CALIBRATION_PATH", calib)
    monkeypatch.setattr(modulo_backend("rutas.respaldo"), "_unidades_usb", lambda: [{"ruta": str(usb), "libre_bytes": 8e9}])
    monkeypatch.setattr(modulo_backend("rutas.respaldo"), "_version_sw", lambda: "1.2.0")
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    yield TestClient(srv.app), srv, ctx, cabecera, usb, programas, calib
    ctx.db.close()


ROLES = ["operador", "admin", "tecnico", "ingeniero"]


@pytest.mark.parametrize("rol", ROLES)
def test_matriz(api, rol):
    client, srv, ctx, cab, usb, *_ = api
    h = cab(srv, rol)
    esperado = 200 if rol in ("tecnico", "ingeniero") else 403
    assert client.get("/backup/usb", headers=h).status_code == esperado
    r = client.post("/backup/export", json={"unidad": str(usb)}, headers=h)
    assert r.status_code == esperado
    r = client.post("/backup/restore", json={"unidad": str(usb), "archivo": "respaldo_x.zip",
                                            "confirmar": True}, headers=h)
    assert r.status_code == (403 if esperado == 403 else 422)


def test_sin_token(api):
    client, *_ = api
    assert client.get("/backup/usb").status_code == 401
    assert client.post("/backup/export", json={"unidad": "x"}).status_code == 401


def test_exportar_y_restaurar_ida_y_vuelta(api):
    client, srv, ctx, cab, usb, programas, calib = api
    h = cab(srv, "tecnico")
    ctx.config_manager.fijar("timeout_puerta", 90)
    r = client.post("/backup/export", json={"unidad": str(usb), "historial": True}, headers=h)
    assert r.status_code == 200
    archivo = r.json()["archivo"]
    m, datos = rp.leer(usb / rp.CARPETA / archivo)
    assert m["serie"] == EQUIPO["serie"] and "historial.db" in datos
    assert "HASH-SECRETO" not in json.dumps({k: v.decode("latin-1") for k, v in datos.items()
                                             if k != "historial.db"})
    usuarios = json.loads(datos.get("usuarios.json", b"[]"))
    assert all(set(u) == {"usuario", "nombre", "rol", "activo"} for u in usuarios)
    lista = client.get("/backup/usb", headers=h).json()["unidades"][0]["respaldos"]
    assert lista[0]["valido"] is True
    # cambios locales que la restauración debe deshacer
    ctx.config_manager.fijar("timeout_puerta", 120)
    (programas / "instrumental_134.json").write_text('{"id": 2, "nombre": "CAMBIADO"}', encoding="utf-8")
    calib.write_text(calib.read_text(encoding="utf-8") + "\n# cambio\n", encoding="utf-8")
    sin = client.post("/backup/restore", json={"unidad": str(usb), "archivo": archivo}, headers=h)
    assert sin.status_code == 428 and ctx.config_manager.get("timeout_puerta") == 120
    r = client.post("/backup/restore", json={"unidad": str(usb), "archivo": archivo,
                                            "confirmar": True}, headers=h)
    assert r.status_code == 200, r.text
    d = r.json()
    assert ctx.config_manager.get("timeout_puerta") == 90 and "timeout_puerta" in d["parametros"]
    assert "presion_atmosferica" in d["parametros_omitidos"]
    # SAF-02 de O2h: los programas no se restauran (solo se exportan)
    assert json.loads((programas / "instrumental_134.json").read_text(encoding="utf-8"))["nombre"] == "CAMBIADO"
    assert d["programas"] == [] and "programas/instrumental_134.json" in datos
    assert "# cambio" not in calib.read_text(encoding="utf-8") and d["reinicio_requerido"] is False
    ctx.units.reload_calibration.assert_called()
    assert ctx.db.get_auditoria(evento="respaldo_exportado")
    assert ctx.db.get_auditoria(evento="respaldo_restaurado")


def test_restaurar_otra_serie_se_rechaza(api, tmp_path):
    client, srv, ctx, cab, usb, programas, calib = api
    ruta = _zip(usb, equipo={"serie": "OTRO-EQUIPO", "modelo": "M-1"},
                contenido={"parametros.json": b'{"timeout_puerta": 200}'})
    h = cab(srv, "ingeniero")
    fila = client.get("/backup/usb", headers=h).json()["unidades"][0]["respaldos"][0]
    assert fila["valido"] is False and fila["motivo"] == "otra_serie"
    r = client.post("/backup/restore", json={"unidad": str(usb), "archivo": ruta.name,
                                            "confirmar": True}, headers=h)
    assert r.status_code == 409 and r.json()["codigo"] == "otra_serie"
    assert ctx.config_manager.get("timeout_puerta") == 60
    assert ctx.db.get_auditoria(evento="respaldo_rechazado")


def test_calibracion_implausible_se_rechaza(api):
    """SAF-01 de O2h: misma plausibilidad que la calibración manual."""
    client, srv, ctx, cab, usb, programas, calib = api
    import re
    texto = calib.read_text(encoding="utf-8")
    user = texto.index("user:")
    malo = texto[:user] + re.sub(r"offset: [-0-9.]+", "offset: 40.0", texto[user:], count=1)
    ruta = _zip(usb, contenido={"calibracion.yaml": malo.encode("utf-8")})
    antes = calib.read_text(encoding="utf-8")
    r = client.post("/backup/restore", json={"unidad": str(usb), "archivo": ruta.name,
                                            "confirmar": True}, headers=cab(srv, "ingeniero"))
    assert r.status_code == 422 and r.json()["codigo"] == "calibracion_implausible"
    assert calib.read_text(encoding="utf-8") == antes


def test_restaurar_alterado_no_aplica_nada(api):
    client, srv, ctx, cab, usb, programas, calib = api
    ruta = _zip(usb, contenido={"parametros.json": b'{"timeout_puerta": 90}'})
    _reescribir(ruta, lambda a: a.__setitem__("parametros.json", b'{"timeout_puerta": 300}'))
    r = client.post("/backup/restore", json={"unidad": str(usb), "archivo": ruta.name,
                                            "confirmar": True}, headers=cab(srv, "tecnico"))
    assert r.status_code == 422 and r.json()["codigo"] == "hash_invalido"
    assert ctx.config_manager.get("timeout_puerta") == 60


@pytest.mark.parametrize("ruta", ["/backup/export", "/backup/restore"])
def test_409_en_ciclo(api, ruta):
    from autoclave.state_machine.machine.enum_global import GlobalState
    client, srv, ctx, cab, usb, *_ = api
    ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    r = client.post(ruta, json={"unidad": str(usb), "archivo": "respaldo_a.zip", "confirmar": True},
                    headers=cab(srv, "ingeniero"))
    assert r.status_code == 409


def test_usb_no_detectada_y_traversal(api, tmp_path):
    client, srv, ctx, cab, usb, *_ = api
    h = cab(srv, "tecnico")
    assert client.post("/backup/export", json={"unidad": str(tmp_path)}, headers=h).status_code == 404
    r = client.post("/backup/restore", json={"unidad": str(usb), "archivo": "../t.db",
                                            "confirmar": True}, headers=h)
    assert r.status_code == 422


# ── UI ──────────────────────────────────────────────────────────────────────

USB = {"unidades": [{"ruta": "E:\\", "libre_bytes": 15.2e9, "respaldos": [
    {"archivo": "respaldo_ACV-2026-001_20261020_180000.zip", "valido": True, "motivo": "",
     "serie": "ACV-2026-001", "fecha": "2026-10-20T18:00:00", "partes": {}},
    {"archivo": "respaldo_ACV-2026-007_20261001_090000.zip", "valido": False, "motivo": "otra_serie",
     "serie": "ACV-2026-007", "fecha": "2026-10-01T09:00:00", "partes": {}}]}],
       "serie": "ACV-2026-001", "version_sw": "1.2.0"}
RUTAS = {"GET /backup/usb": [200, USB],
         "POST /backup/export": [200, {"ok": True, "archivo": "respaldo_x.zip"}],
         "POST /backup/restore": [200, {"ok": True, "reinicio_requerido": True}]}

PASOS = r'''
raiz.setProperty("seccionActiva", "respaldo"); esperar(400)
p = buscar("opcionesRespaldo")
ctrl = p.findChild(QObject, "respaldoController")
salida["usb"] = ctrl.property("unidad")
salida["restaurar_antes"] = buscar("botonRestaurar", p).property("habilitado")
ctrl.seleccionar("respaldo_ACV-2026-007_20261001_090000.zip"); esperar()
salida["sel_rechazado"] = ctrl.property("seleccion")
ctrl.seleccionar("respaldo_ACV-2026-001_20261020_180000.zip"); esperar()
salida["restaurar_hab"] = buscar("botonRestaurar", p).property("habilitado")
capturar("O2h_1_respaldo.png")
buscar("dialogoRestaurar", p).abrir(); esperar()
capturar("O2h_2_confirmar.png")
buscar("dialogoRestaurar", p).cerrar()
ctrl.fijarParte("historial", True)
salida["exportar"] = ctrl.exportar(); esperar()
salida["restaurar"] = ctrl.restaurar(); esperar()
salida["msg"] = ctrl.property("mensaje")
capturar("O2h_3_restaurado.png")
'''


def test_pantalla_respaldo():
    pytest.importorskip("PySide6")
    from tests.opciones_qml_banco import correr, quieren_capturas
    d = correr("tecnico", PASOS, RUTAS, capturas=quieren_capturas())
    assert d["avisos"] == []
    assert d["usb"] == "E:\\" and d["restaurar_antes"] is False
    assert d["sel_rechazado"] == "" and d["restaurar_hab"] is True
    assert d["exportar"] is True and d["restaurar"] is True
    assert d["msg"] == "respaldo.restaurado_reinicio"
    exp = next(e for e in d["enviados"] if e[1] == "/backup/export")
    assert exp[2]["historial"] is True and exp[2]["unidad"] == "E:\\"
    res = next(e for e in d["enviados"] if e[1] == "/backup/restore")
    assert res[2]["confirmar"] is True and res[2]["archivo"].startswith("respaldo_ACV-2026-001")


def test_seccion_respaldo_por_rol():
    from autoclave.ui_qml.domain.permisos_opciones import puede_ver
    assert [puede_ver("respaldo", r) for r in ("operador", "admin", "tecnico", "ingeniero")] == \
        [False, False, True, True]

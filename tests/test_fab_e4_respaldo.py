# tests/test_fab_e4_respaldo.py
#
# Modo fábrica, Etapa 4 (DF-08, R-06): el manifiesto de los respaldos lleva
# `tipo`; sin `tipo` es «respaldo» (compatibilidad) y cualquier otro tipo se
# rechaza al restaurar con 422 `paquete_no_restaurable`. La lista de
# respaldos de la USB no mira Especifika_liberaciones.

import json
import zipfile
from datetime import datetime

from autoclave.core.runtime import paquete_liberacion as pl
from autoclave.core.runtime import respaldo as rp
from tests.test_o2h_respaldo import EQUIPO, api  # noqa: F401  (fixture)


def _zip_con_manifiesto(usb, cambiar_manifiesto, nombre=None, version="1.2.0"):
    """Respaldo válido de EQUIPO cuyo manifiesto se modifica y se vuelve a
    sellar con su hash (para simular uno anterior o de otro tipo)."""
    datos = rp.crear(EQUIPO, {"parametros_programas": True},
                     {"parametros.json": b'{"timeout_puerta": 90}'}, "tec", version)
    import io
    with zipfile.ZipFile(io.BytesIO(datos)) as z:
        archivos = {n: z.read(n) for n in z.namelist()}
    m = json.loads(archivos["manifiesto.json"])
    cambiar_manifiesto(m)
    m["hash"] = rp.hash_manifiesto(m)
    archivos["manifiesto.json"] = json.dumps(m).encode("utf-8")
    carpeta = usb / rp.CARPETA
    carpeta.mkdir(exist_ok=True)
    ruta = carpeta / (nombre or rp.nombre_archivo(EQUIPO["serie"], datetime(2026, 10, 21)))
    with zipfile.ZipFile(ruta, "w") as z:
        for n, d in archivos.items():
            z.writestr(n, d)
    return ruta


def test_respaldo_nuevo_lleva_tipo(tmp_path):
    ruta = tmp_path / "r.zip"
    ruta.write_bytes(rp.crear(EQUIPO, {}, {"a.json": b"{}"}, "u", "1.0.0"))
    m, _ = rp.leer(ruta)
    assert m["tipo"] == "respaldo" and rp.tipo_manifiesto(m) == "respaldo"
    assert rp.validar_para_equipo(m, EQUIPO, "1.0.0") == ""


def test_manifiesto_sin_tipo_es_respaldo():
    assert rp.tipo_manifiesto({"formato": 1}) == "respaldo"
    m = {"formato": 1, "serie": EQUIPO["serie"], "version_sw": "1.2.0"}
    assert rp.validar_para_equipo(m, EQUIPO, "1.2.0") == ""


def test_tipo_distinto_no_restaurable():
    for tipo in ("liberacion", "otro", ""):
        m = {"tipo": tipo, "formato": 1, "serie": EQUIPO["serie"], "version_sw": "1.2.0"}
        assert rp.validar_para_equipo(m, EQUIPO, "1.2.0") == "paquete_no_restaurable"


def test_restaurar_sin_tipo_acepta(api):
    client, srv, ctx, cab, usb, programas, calib = api
    ruta = _zip_con_manifiesto(usb, lambda m: m.pop("tipo"))
    h = cab(srv, "ingeniero")
    fila = client.get("/backup/usb", headers=h).json()["unidades"][0]["respaldos"][0]
    assert fila["valido"] is True
    r = client.post("/backup/restore", json={"unidad": str(usb), "archivo": ruta.name,
                                            "confirmar": True}, headers=h)
    assert r.status_code == 200, r.text
    assert ctx.config_manager.get("timeout_puerta") == 90


def test_restaurar_tipo_liberacion_422(api):
    client, srv, ctx, cab, usb, programas, calib = api
    ruta = _zip_con_manifiesto(usb, lambda m: m.__setitem__("tipo", "liberacion"))
    h = cab(srv, "ingeniero")
    fila = client.get("/backup/usb", headers=h).json()["unidades"][0]["respaldos"][0]
    assert fila["valido"] is False and fila["motivo"] == "paquete_no_restaurable"
    for confirmar in (False, True):
        r = client.post("/backup/restore", json={"unidad": str(usb), "archivo": ruta.name,
                                                "confirmar": confirmar}, headers=h)
        assert r.status_code == 422 and r.json()["codigo"] == "paquete_no_restaurable"
    assert ctx.config_manager.get("timeout_puerta") == 60
    filas = ctx.db.get_auditoria(evento="respaldo_rechazado")
    assert filas and "paquete_no_restaurable" in json.dumps(filas[0], default=str)


def test_paquete_de_liberacion_renombrado_se_rechaza(api, tmp_path):
    """Un ZIP de liberación copiado a Especifika_respaldos con nombre de
    respaldo tampoco se restaura (su manifiesto no es «respaldo»)."""
    client, srv, ctx, cab, usb, programas, calib = api
    otra = tmp_path / "otra_usb"; otra.mkdir()
    fuentes = pl.FuentesPaquete(copiar_base=pl.copiar_base_desde(ctx.db), equipo=dict(EQUIPO),
                                version_sw="1.2.0", parametros={"timeout_puerta": 90},
                                mapas_sensores={})
    r = pl.generar_paquete_liberacion(fuentes, otra, "ing", datetime(2026, 11, 22, 10, 0))
    carpeta = usb / rp.CARPETA; carpeta.mkdir(exist_ok=True)
    nombre = "respaldo_ACV-2026-001_20261122_100000.zip"
    (carpeta / nombre).write_bytes(r.ruta.read_bytes())
    h = cab(srv, "ingeniero")
    resp = client.post("/backup/restore", json={"unidad": str(usb), "archivo": nombre,
                                               "confirmar": True}, headers=h)
    assert resp.status_code == 422 and resp.json()["codigo"] == "paquete_no_restaurable"
    assert ctx.config_manager.get("timeout_puerta") == 60


def test_lista_usb_no_muestra_liberaciones(api, tmp_path):
    client, srv, ctx, cab, usb, programas, calib = api
    fuentes = pl.FuentesPaquete(copiar_base=pl.copiar_base_desde(ctx.db), equipo=dict(EQUIPO),
                                version_sw="1.2.0", parametros={}, mapas_sensores={})
    pl.generar_paquete_liberacion(fuentes, usb, "ing", datetime(2026, 11, 22, 10, 0))
    # aunque alguien deje en la carpeta de liberaciones un archivo con nombre de respaldo
    (usb / pl.CARPETA / "respaldo_x_20261122_100000.zip").write_bytes(b"x")
    h = cab(srv, "ingeniero")
    unidad = client.get("/backup/usb", headers=h).json()["unidades"][0]
    assert unidad["respaldos"] == []
    r = client.post("/backup/restore", json={"unidad": str(usb), "archivo":
                                            f"../{pl.CARPETA}/respaldo_x_20261122_100000.zip",
                                            "confirmar": True}, headers=h)
    assert r.status_code == 422 and r.json()["codigo"] == "archivo_invalido"


def test_texto_es_en_del_codigo():
    import json as _json
    from pathlib import Path
    from autoclave.ui_qml import sesion_backend
    raiz = Path(sesion_backend.__file__).resolve().parents[1] / "i18n"
    fuente = Path(sesion_backend.__file__).read_text(encoding="utf-8")
    assert '"paquete_no_restaurable": "respaldo.err_paquete_no_restaurable"' in fuente
    for idioma in ("es", "en"):
        textos = _json.loads((raiz / f"{idioma}.json").read_text(encoding="utf-8"))
        assert textos["respaldo"]["err_paquete_no_restaurable"]

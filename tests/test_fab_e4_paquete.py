# tests/test_fab_e4_paquete.py
#
# Modo fábrica, Etapa 4: paquete de liberación (D-04, FAB-02, §7; P-07, P-09;
# DF-08, PA-03). Carpetas temporales como «USB» y una base de prueba con
# ciclos, usuarios con hash, alarmas y bitácora. No escribe en data/ ni en
# src/autoclave/cycles.

import csv
import io
import json
import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path

import pytest

from autoclave.core.runtime import paquete_liberacion as pl
from autoclave.core.runtime import respaldo as rp

AHORA = datetime(2026, 11, 22, 15, 4, 5)
HASH = "pbkdf2$600000$abcdef$HASH-SECRETO-QUE-NO-DEBE-SALIR"
CODIGO = "CODIGO-CREACION-SECRETO"
MAPAS = {"temperature": {"temp_camara": 0, "temp_ref": 1}, "pressure": {"pres_camara": 0}}


@pytest.fixture
def base(tmp_path):
    from autoclave.services.domain.logging.db_manager import DbManager
    db = DbManager(db_path=tmp_path / "datos" / "autoclave.db")
    db.crear_usuario("Ana Pérez", "ana", HASH, "ingeniero", codigo_creacion=CODIGO)
    db.crear_usuario("Luis", "luis", HASH + "2", "operador", codigo_creacion=CODIGO)
    for n, resultado in ((1, "COMPLETADO"), (2, "FALLO")):
        cid = db.crear_ciclo(n, "solido", "Instrumental 134", 134.0, 4.0, "M-1", "SN260001",
                             "1.0.0-alpha.30", operador="ana", numero_programa=2)
        for i in range(30):
            db.insertar_lectura_grafica(cid, i * 10.0, "CALENTAMIENTO" if i < 15 else "ESTERILIZACION",
                                        100 + i, 99 + i, 150 + i * 3)
            if i % 10 == 0:
                db.insertar_lectura(cid, f"00:0{i // 10}:00", "2026-11-20T10:00:00", "H",
                                    100 + i, 150 + i, para_imprimir=True)
        if resultado == "FALLO":
            db.insertar_alarma("CIC-04", "alta", "Presión baja", "operacion", "desc", "{}",
                               "2026-11-20T10:30:00", None, cid)
            db.cerrar_ciclo(cid, resultado, motivo_fallo="presión baja", codigo_fallo="CIC-04")
        else:
            db.cerrar_ciclo(cid, resultado)
    for i in range(5):
        db.registrar_auditoria("respaldo_exportado", usuario="ana", rol="ingeniero",
                               entidad=f"/x/{i}", detalle={"i": i, "texto": "año; «coma», sí"})
    yield db
    db.close()


@pytest.fixture
def fuentes(tmp_path, base):
    from autoclave.utils.paths import calibration_path
    raiz = tmp_path / "datos"
    calib = raiz / "calibration_modbus.yaml"
    calib.write_bytes(Path(calibration_path()).read_bytes())
    programas = raiz / "cycles_user"
    programas.mkdir()
    (programas / "instrumental_134.json").write_text(json.dumps(
        {"cycle_id": "instrumental_134", "cycle_number": 2, "display_name": "Instrumental 134",
         "parameters": {"esterilizacion": {"temperatura_esterilizacion": 134}}}), encoding="utf-8")
    (programas / "programa_11.json").write_text(json.dumps(
        {"cycle_id": "p11", "cycle_number": 11, "display_name": "Usuario",
         "parameters": {}}), encoding="utf-8")
    (programas / "fabrica_vistos.lst").write_text("instrumental_134\n", encoding="utf-8")
    (programas / "fabrica_borrados.lst").write_text("bowie_dick\n", encoding="utf-8")
    (programas / "nota.txt").write_text("no va", encoding="utf-8")
    asign = raiz / "asignacion_io.json"
    asign.write_text('{"formato": 2, "cambios": {}}', encoding="utf-8")
    rc = raiz / "respaldo_ciclos"
    (rc / "importados").mkdir(parents=True)
    (rc / "aaaa-1111.jsonl").write_text('{"tipo": "encabezado"}\n', encoding="utf-8")
    (rc / "importados" / "bbbb-2222.jsonl").write_text('{"tipo": "cierre"}\n', encoding="utf-8")
    data = raiz / "data"; data.mkdir()
    (data / "backend.log").write_text("arranque\n", encoding="utf-8")
    (data / "lanzador.log").write_text("lanzador\n", encoding="utf-8")
    (data / "tema.json").write_text("{}", encoding="utf-8")
    logs = raiz / "logs"; logs.mkdir()
    (logs / "autoclave.log").write_text("log\n", encoding="utf-8")
    return pl.FuentesPaquete(
        copiar_base=pl.copiar_base_desde(base),
        equipo={"serie": "SN260001", "modelo": "M-1", "tipo_instalacion": "fabricacion"},
        version_sw="1.0.0-alpha.30 (abc1234)",
        parametros=[{"clave": "timeout_puerta", "valor": 90, "unidad": "s"},
                    {"clave": "presion_atmosferica", "valor": 74.6, "unidad": "kPa"}],
        ruta_calibracion=calib, carpeta_programas=programas, ruta_asignacion_io=asign,
        carpeta_respaldo_ciclos=rc, carpetas_logs={"data": data, "logs": logs},
        mapas_sensores=MAPAS, contadores={"Contador de ciclos": 2})


@pytest.fixture
def usb(tmp_path):
    u = tmp_path / "usb"
    u.mkdir()
    return u


def _contenido(ruta):
    with zipfile.ZipFile(ruta) as z:
        return {n: z.read(n) for n in z.namelist()}


def _generar(fuentes, usb):
    return pl.generar_paquete_liberacion(fuentes, usb, "ana", AHORA)


# ── contenido ───────────────────────────────────────────────────────────
def test_contenido_completo(fuentes, usb):
    r = _generar(fuentes, usb)
    assert r.ruta == usb / pl.CARPETA / "liberacion_SN260001_20261122-1504.zip"
    assert r.ruta.is_file() and r.tamano == r.ruta.stat().st_size
    nombres = set(_contenido(r.ruta))
    esperados = {"manifiesto.json", "informe_liberacion.pdf", "historial.db", "bitacora.csv",
                 "calibracion.yaml", "parametros.json", "programas/instrumental_134.json",
                 "programas/programa_11.json", "programas/fabrica_vistos.lst",
                 "programas/fabrica_borrados.lst", "asignacion_io.json",
                 "respaldo_ciclos/aaaa-1111.jsonl", "respaldo_ciclos/importados/bbbb-2222.jsonl",
                 "logs/data/backend.log", "logs/data/lanzador.log", "logs/logs/autoclave.log"}
    assert esperados <= nombres
    assert "programas/nota.txt" not in nombres and "logs/data/tema.json" not in nombres
    pdfs = sorted(n for n in nombres if n.startswith("ciclos/"))
    assert len(pdfs) == 2 and all(n.endswith(".pdf") for n in pdfs)
    datos = _contenido(r.ruta)
    assert all(datos[n].startswith(b"%PDF-1.4") for n in pdfs + ["informe_liberacion.pdf"])
    assert json.loads(datos["parametros.json"]) == {"timeout_puerta": 90, "presion_atmosferica": 74.6}
    assert r.ausentes == ()
    # nada temporal en la USB
    assert [p.name for p in (usb / pl.CARPETA).iterdir()] == [r.ruta.name]
    assert [p.name for p in usb.iterdir()] == [pl.CARPETA]


def test_manifiesto_tipo_liberacion_y_hashes(fuentes, usb):
    r = _generar(fuentes, usb)
    datos = _contenido(r.ruta)
    m = json.loads(datos["manifiesto.json"])
    assert m["tipo"] == "liberacion" and m["formato"] == pl.FORMATO
    assert m["serie"] == "SN260001" and m["creado_por"] == "ana"
    assert m["version_sw"] == "1.0.0-alpha.30 (abc1234)"
    assert m["creado_en"] == "2026-11-22T15:04:05"
    assert m["hash"] == rp.hash_manifiesto(m) == r.hash_manifiesto
    assert set(m["archivos"]) == set(datos) - {"manifiesto.json"}
    for nombre, h in m["archivos"].items():
        assert rp.sha256(datos[nombre]) == h
    assert pl.verificar_paquete(r.ruta) == r.hash_global == rp.sha256(r.ruta.read_bytes())


def test_informe_tiene_las_secciones_y_firmas(fuentes, usb):
    import zlib, re
    r = _generar(fuentes, usb)
    pdf = _contenido(r.ruta)["informe_liberacion.pdf"]
    texto = b"".join(zlib.decompress(s) for s in
                     re.findall(rb"stream\n(.*?)\nendstream", pdf, re.S)).decode("cp1252")
    for parte in ("SN260001", "M-1", "1.0.0-alpha.30", "Ana Pérez", "temp_camara", "pres_camara",
                  "timeout_puerta", "Programa 2", "temperatura_esterilizacion", "COMPLETADO",
                  "FALLO", "CIC-04", "Contador de ciclos", "Ingeniero que libera", "Aprobó",
                  "Firma", "Nombre", "Fecha"):
        assert parte in texto, parte


def test_informe_automatizacion_lleva_originales(fuentes, usb):
    import zlib, re
    fuentes.equipo = {"serie": "SN260002", "modelo": "M-1", "tipo_instalacion": "automatizacion",
                      "serial_original": "XYZ-999", "modelo_original": "Tuttnauer 3870"}
    r = _generar(fuentes, usb)
    datos = _contenido(r.ruta)
    m = json.loads(datos["manifiesto.json"])
    assert m["serial_original"] == "XYZ-999" and m["modelo_original"] == "Tuttnauer 3870"
    texto = b"".join(zlib.decompress(s) for s in re.findall(
        rb"stream\n(.*?)\nendstream", datos["informe_liberacion.pdf"], re.S)).decode("cp1252")
    assert "XYZ-999" in texto and "Tuttnauer 3870" in texto and "SN260002" in texto


def test_ciclo_pdf_con_grafica_y_ticket(fuentes, usb):
    import zlib, re
    r = _generar(fuentes, usb)
    datos = _contenido(r.ruta)
    nombre = next(n for n in sorted(datos) if n.startswith("ciclos/") and "000002" in n)
    texto = b"".join(zlib.decompress(s) for s in re.findall(
        rb"stream\n(.*?)\nendstream", datos[nombre], re.S)).decode("cp1252")
    assert "Presión cámara" in texto and "CIC-04" in texto and "Ticket" in texto
    assert texto.count(" l") > 20     # polilíneas de la gráfica


# ── P-09: base sin secretos ─────────────────────────────────────────────
def test_historial_sin_hash_ni_codigo(fuentes, usb, tmp_path, base):
    r = _generar(fuentes, usb)
    copia = tmp_path / "copia.db"
    copia.write_bytes(_contenido(r.ruta)["historial.db"])
    assert HASH.encode() not in copia.read_bytes() and CODIGO.encode() not in copia.read_bytes()
    conn = sqlite3.connect(copia)
    try:
        filas = conn.execute("SELECT usuario, nombre, rol, hash_pw, codigo_creacion FROM usuarios "
                             "ORDER BY id").fetchall()
        assert {f[0] for f in filas} >= {"ana", "luis", "Admin", "Ingeniero"}
        assert all(f[3] is None and f[4] is None for f in filas)
        assert conn.execute("SELECT COUNT(*) FROM ciclos").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM lecturas_grafica").fetchone()[0] == 60
        # los triggers de usuarios siguen en la copia (registro fiel)
        triggers = {f[0] for f in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='usuarios'")}
        assert "usuarios_sin_delete" in triggers
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    finally:
        conn.close()
    # la base viva conserva los hashes
    assert base._conn.execute("SELECT hash_pw FROM usuarios WHERE usuario='ana'").fetchone()[0] == HASH


# ── bitácora ────────────────────────────────────────────────────────────
def test_bitacora_csv_completa(fuentes, usb, base):
    r = _generar(fuentes, usb)
    crudo = _contenido(r.ruta)["bitacora.csv"]
    assert crudo.startswith(b"\xef\xbb\xbf")
    filas = list(csv.reader(io.StringIO(crudo.decode("utf-8-sig")), delimiter=";"))
    assert filas[0][:5] == ["id", "fecha", "usuario", "rol", "evento"]
    total = base._conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    assert total >= 5 and len(filas) - 1 == total
    exportados = [f for f in filas[1:] if f[4] == "respaldo_exportado"]
    assert len(exportados) == 5 and all(f[2] == "ana" for f in exportados)
    assert "año; «coma», sí" in exportados[0][8]


# ── verificación ────────────────────────────────────────────────────────
def _reescribir(ruta, cambiar):
    datos = _contenido(ruta)
    cambiar(datos)
    with zipfile.ZipFile(ruta, "w") as z:
        for n, d in datos.items():
            z.writestr(n, d)


@pytest.mark.parametrize("cambio,codigo", [
    (lambda d: d.__setitem__("parametros.json", d["parametros.json"][:-1] + b"X"), "hash_invalido"),
    (lambda d: d.pop("bitacora.csv"), "archivo_faltante"),
    (lambda d: d.__setitem__("extra.txt", b"x"), "archivo_no_declarado"),
    (lambda d: d.__setitem__("manifiesto.json",
                             d["manifiesto.json"].replace(b"SN260001", b"SN269999")),
     "manifiesto_alterado"),
    (lambda d: d.pop("manifiesto.json"), "sin_manifiesto"),
])
def test_verificar_detecta_alteraciones(fuentes, usb, cambio, codigo):
    r = _generar(fuentes, usb)
    _reescribir(r.ruta, cambio)
    with pytest.raises(pl.ErrorPaquete) as e:
        pl.verificar_paquete(r.ruta)
    assert e.value.codigo == codigo


def test_un_byte_alterado_en_el_zip_falla(fuentes, usb):
    r = _generar(fuentes, usb)
    crudo = bytearray(r.ruta.read_bytes())
    i = crudo.index(b"historial.db") + 200          # dentro de los datos comprimidos
    crudo[i] ^= 0xFF
    r.ruta.write_bytes(bytes(crudo))
    with pytest.raises(pl.ErrorPaquete) as e:
        pl.verificar_paquete(r.ruta)
    assert e.value.codigo in ("ilegible", "hash_invalido")


def test_respaldo_no_verifica_como_liberacion(tmp_path):
    ruta = tmp_path / "r.zip"
    ruta.write_bytes(rp.crear({"serie": "S"}, {}, {"a.json": b"{}"}, "u", "1.0.0"))
    with pytest.raises(pl.ErrorPaquete) as e:
        pl.verificar_paquete(ruta)
    assert e.value.codigo == "tipo_invalido"


# ── P-07: USB ───────────────────────────────────────────────────────────
def test_comprobar_usb_ok_no_deja_nada(usb):
    libre = pl.comprobar_usb_para_liberacion(usb, 1000)
    assert libre > 0 and list(usb.iterdir()) == []


def test_usb_ausente(tmp_path, fuentes):
    for carpeta in (None, "", tmp_path / "no_existe"):
        with pytest.raises(pl.ErrorPaquete) as e:
            pl.comprobar_usb_para_liberacion(carpeta, 1)
        assert e.value.codigo == "usb_ausente"
    with pytest.raises(pl.ErrorPaquete) as e:
        pl.generar_paquete_liberacion(fuentes, tmp_path / "no_existe", "ana", AHORA)
    assert e.value.codigo == "usb_ausente"


def test_usb_sin_espacio_no_escribe_nada(fuentes, usb, monkeypatch):
    monkeypatch.setattr(pl, "_espacio_libre", lambda carpeta: 5 * 1024 * 1024)
    with pytest.raises(pl.ErrorPaquete) as e:
        _generar(fuentes, usb)
    assert e.value.codigo == "usb_sin_espacio"
    assert list(usb.iterdir()) == []


def test_espacio_requerido_con_margen(usb, monkeypatch):
    assert pl.espacio_requerido(100 * 1024 * 1024) == 150 * 1024 * 1024 + pl.MARGEN_ESPACIO_BYTES
    monkeypatch.setattr(pl, "_espacio_libre", lambda c: pl.espacio_requerido(10_000) - 1)
    with pytest.raises(pl.ErrorPaquete) as e:
        pl.comprobar_usb_para_liberacion(usb, 10_000)
    assert e.value.codigo == "usb_sin_espacio"
    monkeypatch.setattr(pl, "_espacio_libre", lambda c: pl.espacio_requerido(10_000))
    assert pl.comprobar_usb_para_liberacion(usb, 10_000) == pl.espacio_requerido(10_000)


def test_usb_no_escribible_no_escribe_nada(fuentes, usb, monkeypatch):
    def falla(carpeta):
        raise PermissionError("protegida contra escritura")
    monkeypatch.setattr(pl, "_probar_escritura", falla)
    with pytest.raises(pl.ErrorPaquete) as e:
        _generar(fuentes, usb)
    assert e.value.codigo == "usb_no_escribible"
    assert list(usb.iterdir()) == []


def test_fallo_al_escribir_el_zip_borra_lo_parcial(fuentes, usb, monkeypatch):
    original = pl._escribir_zip

    def a_medias(destino, m, archivos):
        original(destino, m, archivos[:1])
        raise OSError("USB retirada")
    monkeypatch.setattr(pl, "_escribir_zip", a_medias)
    with pytest.raises(pl.ErrorPaquete) as e:
        _generar(fuentes, usb)
    assert e.value.codigo == "usb_no_escribible"
    assert list(usb.iterdir()) == []


def test_verificacion_fallida_borra_el_zip(fuentes, usb, monkeypatch):
    def mala(ruta):
        raise pl.ErrorPaquete("hash_invalido", "x")
    monkeypatch.setattr(pl, "verificar_paquete", mala)
    with pytest.raises(pl.ErrorPaquete) as e:
        _generar(fuentes, usb)
    assert e.value.codigo == "hash_invalido"
    assert list(usb.iterdir()) == []


def test_carpeta_existente_se_conserva_y_no_pisa(fuentes, usb):
    r1 = _generar(fuentes, usb)
    r2 = _generar(fuentes, usb)
    assert r1.ruta != r2.ruta and r1.ruta.is_file() and r2.ruta.is_file()
    assert r2.ruta.name == "liberacion_SN260001_20261122-1504_2.zip"


# ── ausentes y base ─────────────────────────────────────────────────────
def test_ausentes_en_el_manifiesto(fuentes, usb, tmp_path):
    fuentes.ruta_asignacion_io = tmp_path / "no.json"
    fuentes.carpeta_respaldo_ciclos = None
    fuentes.carpetas_logs = {"data": fuentes.carpetas_logs["data"], "logs": tmp_path / "nada"}
    r = _generar(fuentes, usb)
    m = json.loads(_contenido(r.ruta)["manifiesto.json"])
    rutas = {a["ruta"] for a in m["ausentes"]}
    assert rutas == {"asignacion_io.json", "respaldo_ciclos/", "logs/logs/"}
    assert {a["ruta"] for a in r.ausentes} == rutas
    pl.verificar_paquete(r.ruta)


def test_sin_base_se_aborta(fuentes, usb):
    def falla(destino):
        raise sqlite3.OperationalError("sin base")
    fuentes.copiar_base = falla
    with pytest.raises(pl.ErrorPaquete) as e:
        _generar(fuentes, usb)
    assert e.value.codigo == "sin_base"
    assert list(usb.iterdir()) == []


def test_nombre_paquete():
    assert pl.nombre_paquete("SN26/00 1", AHORA) == "liberacion_SN26_00_1_20261122-1504.zip"

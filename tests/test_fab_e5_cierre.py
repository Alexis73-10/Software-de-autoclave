# tests/test_fab_e5_cierre.py
#
# Modo fábrica, Etapa 5: cierre de fabricación en dos tiempos (DF-05; FAB-02,
# FAB-05, FAB-07, FAB-10; D-09..D-12; DF-09, DF-10; PA-06 = D-11, PA-08,
# PA-09). Pruebas de aceptación P-04, P-07, P-08, P-10 y P-12.
#
# Todo en carpetas temporales: un «equipo» completo (datos/, cycles/, logs/)
# con una base con ciclos, alarmas, bitácora, operadores, usuarios extra,
# catálogo de carga y mantenimientos. Nunca escribe en data/ ni en
# src/autoclave/cycles del repositorio.

import json
import shutil
import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path

import pytest

from autoclave.core.runtime import cierre_fabrica as cf
from autoclave.core.runtime import fabrica_equipo as fe
from autoclave.core.runtime import paquete_liberacion as pl
from autoclave.core.managers.cycle_manager import CycleManager
from autoclave.services.domain.logging.db_manager import DbManager

pytestmark = pytest.mark.req("DF-05", "FAB-02", "FAB-05", "FAB-07", "FAB-10", "D-09",
                             "D-10", "D-11", "D-12")

RAIZ = Path(__file__).resolve().parents[1]
CICLOS = RAIZ / "src" / "autoclave" / "cycles"
AHORA = datetime(2026, 11, 22, 16, 30, 0)
CADENA = "LOTE-PRUEBA-P10-QX7Z9"          # P-10: solo existe en los datos de prueba
MAPAS = {"temperature": {"temp_camara": 0}, "pressure": {"pres_camara": 0}}
HASH = "pbkdf2$600000$abcdef$HASH-DE-PRUEBA"


class _Config:
    def describir(self):
        return [{"clave": "timeout_puerta", "valor": 90, "unidad": "s"},
                {"clave": "presion_atmosferica", "valor": 74.6, "unidad": "kPa"}]


def _sembrar_base(db: DbManager) -> None:
    db.registrar_auditoria("equipo_instalado", usuario="sistema", entidad="SN260001",
                           detalle={"serie": "SN260001", "modelo": "M-1", "zona": "SA Pacific"})
    db.crear_usuario("Ana Pérez", "ana", HASH, "ingeniero")
    db.crear_usuario("Luis " + CADENA, "luis", HASH + "2", "operador")
    db.crear_operador("Operadora " + CADENA, creado_por="ana")
    db.alta_catalogo_carga("COD-1", "Caja " + CADENA, "ana")
    db.registrar_mantenimiento("2026-11-20", "ana", "preventivo", "obs " + CADENA, 2)
    db.guardar_parametro_sistema("timeout_puerta", 90, 60, 10, 600, usuario="ana",
                                 fecha="2026-11-20T10:00:00")
    for n, resultado in ((1, "COMPLETADO"), (2, "FALLO")):
        cid = db.crear_ciclo(n, "solido", "Instrumental 134", 134.0, 4.0, "M-1", "SN260001",
                             "1.0.0-alpha.30", operador=CADENA, numero_programa=2)
        for i in range(12):
            db.insertar_lectura_grafica(cid, i * 10.0, "ESTERILIZACION", 120 + i, 119 + i, 200)
            db.insertar_lectura(cid, f"00:00:{i:02d}", "2026-11-20T10:00:00", "E", 120, 200,
                                para_imprimir=True)
        if resultado == "FALLO":
            db.insertar_alarma("CIC-04", "alta", "Presión baja", "operacion", "desc " + CADENA,
                               "{}", "2026-11-20T10:30:00", None, cid)
            db.cerrar_ciclo(cid, resultado, motivo_fallo="presión " + CADENA, codigo_fallo="CIC-04")
        else:
            db.cerrar_ciclo(cid, resultado)
    db.registrar_auditoria("respaldo_exportado", usuario="ana", rol="ingeniero",
                           entidad="/backup", detalle={"lote": CADENA})


class Equipo:
    """Un equipo en FÁBRICA con datos de prueba en carpetas temporales."""

    def __init__(self, tmp: Path):
        self.tmp = tmp
        self.datos = tmp / "datos"
        self.data = self.datos / "data"
        self.data.mkdir(parents=True)
        self.ciclos = tmp / "cycles"
        shutil.copytree(CICLOS / "factory", self.ciclos / "factory")
        (self.ciclos / "user").mkdir()
        for f in (CICLOS / "user").glob("*.json"):
            shutil.copy2(f, self.ciclos / "user" / f.name)
        (self.ciclos / "user" / "fabrica_vistos.lst").write_text("bowe_dick\n", encoding="utf-8")
        (self.ciclos / "user" / "instrumental_134.json.bak").write_text(CADENA, encoding="utf-8")
        (self.ciclos / "user" / "numeros_usados.json").write_text("[3, 7, 11, 12]",
                                                                    encoding="utf-8")
        (self.ciclos / "defecto").mkdir()
        (self.ciclos / "defecto" / "viejo_borrado.json").write_text(
            json.dumps({"cycle_id": "viejo", "cycle_number": 9, "parameters": {}}), encoding="utf-8")
        (self.ciclos / "defecto" / "nota.txt").write_text("se conserva", encoding="utf-8")
        self.logs = self.datos / "logs"
        self.logs.mkdir()
        self.usb = tmp / "usb"
        self.usb.mkdir()
        self.calib = self.data / "calibration_modbus.yaml"
        from autoclave.utils.paths import calibration_path
        self.calib.write_bytes(Path(calibration_path()).read_bytes())
        self.rutas = cf.RutasCierre(carpeta_datos=self.data, carpeta_ciclos=self.ciclos,
                                    carpeta_logs=self.logs,
                                    ruta_registro_perfil=self.datos / "installation_profile_cambios.log")
        self.db = DbManager(self.rutas.base)
        _sembrar_base(self.db)
        # archivos de data/ que el cierre borra o reinicia
        rc = self.data / "respaldo_ciclos"
        (rc / "importados").mkdir(parents=True)
        (rc / "aaaa-1111.jsonl").write_text(json.dumps({"lote": CADENA}) + "\n", encoding="utf-8")
        (rc / "importados" / "bbbb-2222.jsonl").write_text(CADENA + "\n", encoding="utf-8")
        for nombre in ("backend.log", "lanzador.log", "ui_puerta1.log"):
            (self.data / nombre).write_text(f"{nombre} {CADENA}\n", encoding="utf-8")
        (self.logs / "autoclave.log").write_text(CADENA + "\n", encoding="utf-8")
        (self.logs / "autoclave.log.1").write_text(CADENA + "\n", encoding="utf-8")
        (self.datos / "installation_profile_cambios.log").write_text(CADENA, encoding="utf-8")
        (self.data / "login_recordado.json").write_text(json.dumps({"usuario": "luis"}),
                                                        encoding="utf-8")
        (self.data / "last_shutdown.json").write_text('{"t": 1}', encoding="utf-8")
        (self.data / "autoclave.db.corrupta-20261101-101010").write_text(CADENA, encoding="utf-8")
        (self.data / "asignacion_io.json").write_text('{"formato": 2, "cambios": {}}',
                                                      encoding="utf-8")
        (self.data / "asignacion_io.json.bak").write_text(CADENA, encoding="utf-8")
        (self.data / "asignacion_io.json.formato1.bak").write_text("{}", encoding="utf-8")
        (self.data / "ciclo_contador.json").write_text('{"ultimo": 2}', encoding="utf-8")
        (self.data / "mantenimiento_base.json").write_text('{"ciclos_instalacion": 79}',
                                                          encoding="utf-8")
        (self.data / "mantenimiento.json").write_text('{"intervalo_dias": 180}', encoding="utf-8")
        for nombre in ("tema.json", "idioma.json", "unidades.json", "impresora.json",
                       "correo_equipo.json"):
            (self.data / nombre).write_text('{"conservar": true}', encoding="utf-8")
        (self.datos / "installation_profile.json").write_text('{"perfil": 1}', encoding="utf-8")
        (self.datos / "estacion").mkdir()
        (self.datos / "estacion" / "respaldo_07.json").write_text("{}", encoding="utf-8")
        self.cm = CycleManager()
        self.cm.raiz = str(tmp)
        self.cm.load_all_cycles()

    def fuentes(self) -> pl.FuentesPaquete:
        return pl.FuentesPaquete(
            copiar_base=pl.copiar_base_desde(self.db),
            equipo={"serie": "SN260001", "modelo": "M-1", "tipo_instalacion": "fabricacion"},
            version_sw="1.0.0-alpha.31", parametros=_Config().describir(),
            ruta_calibracion=self.calib, carpeta_programas=self.ciclos / "user",
            ruta_asignacion_io=self.data / "asignacion_io.json",
            carpeta_respaldo_ciclos=self.data / "respaldo_ciclos",
            carpetas_logs={"data": self.data, "logs": self.logs}, mapas_sensores=MAPAS)

    def fase1(self, **kw) -> cf.ResultadoFase1:
        return cf.ejecutar_fase1(
            fuentes=self.fuentes(), carpeta_usb=self.usb, usuario="ana", rol="ingeniero",
            rutas=self.rutas, config_manager=_Config(), cycle_manager=self.cm,
            leer_base_vieja=self.db.datos_para_cierre_fabrica, serie="SN260001", ahora=AHORA,
            mapas=MAPAS, origen_calibracion=self.calib, **kw)

    def cerrar_base(self):
        self.db.close()


@pytest.fixture
def equipo(tmp_path):
    e = Equipo(tmp_path)
    yield e
    try:
        e.db.close()
    except Exception:
        pass


def _filas(ruta: Path, sql: str):
    conn = sqlite3.connect(str(ruta))
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def _conteo(ruta: Path, tabla: str) -> int:
    return _filas(ruta, f"SELECT COUNT(*) FROM {tabla}")[0][0]


def _cierre_completo(e: Equipo) -> cf.ResultadoFase1:
    r = e.fase1()
    cf.escribir_marca(e.rutas, r, "ana")
    e.cerrar_base()                     # el reinicio cierra la base
    return r


# ── fase 1 ────────────────────────────────────────────────────────────────
def test_fase1_paquete_temporales_y_base_nueva(equipo):
    r = equipo.fase1()
    # paquete en la USB, verificado, con la base completa de las pruebas
    assert r.ruta_paquete.parent == equipo.usb / pl.CARPETA and r.ruta_paquete.is_file()
    assert pl.verificar_paquete(r.ruta_paquete) == r.hash_paquete
    with zipfile.ZipFile(r.ruta_paquete) as z:
        assert "historial.db" in z.namelist()
    # temporales: los vigentes no se tocan
    assert equipo.rutas.temporal(fe.NOMBRE_PARAMETROS).is_file()
    assert equipo.rutas.temporal(fe.NOMBRE_CALIBRACION).is_file()
    assert not equipo.rutas.final(fe.NOMBRE_PARAMETROS).exists()
    assert (equipo.ciclos / "defecto" / "viejo_borrado.json").exists()
    nuevo = equipo.rutas.defecto_nuevo
    assert (nuevo / "nota.txt").exists() and not (nuevo / "viejo_borrado.json").exists()
    assert (nuevo / "134_instrumental.json").exists()
    # base nueva: un solo archivo, solo semillas y lo de la sección 8
    nueva = equipo.rutas.base_nueva
    assert nueva.is_file() and not Path(str(nueva) + "-wal").exists()
    assert _filas(nueva, "SELECT usuario, debe_cambiar_clave, cuenta_sistema FROM usuarios "
                         "ORDER BY usuario") == [("Admin", 1, 1), ("Ingeniero", 1, 1)]
    for tabla in ("ciclos", "lecturas", "lecturas_grafica", "alarmas_historial", "mantenimientos",
                  "operadores", "catalogo_carga", "ciclo_carga", "cycle_params_audit",
                  "sensor_calibration_audit"):
        assert _conteo(nueva, tabla) == 0, tabla
    assert _filas(nueva, "SELECT clave, valor, defecto, usuario, fecha FROM system_params") == [
        ("timeout_puerta", "90", "90", "", None)]
    assert _filas(nueva, "SELECT estado, fecha_liberacion, hash_paquete FROM estado_fabrica") == [
        ("ENTREGADO", AHORA.isoformat(timespec="seconds"), r.hash_paquete)]
    bit = _filas(nueva, "SELECT evento, usuario, rol, detalle, ts FROM audit_log ORDER BY id")
    assert [b[0] for b in bit] == ["equipo_instalado", "equipo_liberado_fabrica"]
    original = equipo.db.get_auditoria(evento="equipo_instalado")[0]
    assert bit[0][4] == original["ts"]
    assert json.loads(bit[0][3]) == {"serie": "SN260001", "modelo": "M-1", "zona": "SA Pacific"}
    assert bit[1][1:3] == ("ana", "ingeniero")
    detalle = json.loads(bit[1][3])
    assert detalle == {"fecha": AHORA.isoformat(timespec="seconds"), "serie": "SN260001",
                       "paquete": r.nombre_paquete}
    assert r.hash_paquete not in bit[1][3]          # D-12: sin el hash
    # triggers vigentes en la base nueva (FAB-07)
    triggers = {t[0] for t in _filas(nueva, "SELECT name FROM sqlite_master WHERE type='trigger'")}
    assert {"audit_log_sin_delete", "usuarios_sin_delete", "estado_fabrica_entregado_inmutable",
            "operadores_sin_delete", "catalogo_carga_sin_delete"} <= triggers
    # la base vieja sigue intacta y en FÁBRICA... (no hay fila: la prueba no entró)
    assert _conteo(equipo.rutas.base, "ciclos") == 2


def test_base_nueva_entregada_es_inmutable(equipo):
    equipo.fase1()
    conn = sqlite3.connect(str(equipo.rutas.base_nueva))
    try:
        with pytest.raises(sqlite3.DatabaseError):
            conn.execute("UPDATE estado_fabrica SET estado = 'FABRICA'")
        with pytest.raises(sqlite3.DatabaseError):
            conn.execute("DELETE FROM audit_log")
    finally:
        conn.close()


def test_preparar_base_entregada_rechaza_una_base_usada(equipo):
    with pytest.raises(RuntimeError):
        equipo.db.preparar_base_entregada(
            parametros=[], equipo_instalado=None, usuario="a", rol="ingeniero",
            detalle_liberacion={}, fecha_liberacion="x", hash_paquete="h")


@pytest.mark.req("P-07")
@pytest.mark.parametrize("caso", ["sin_usb", "no_escribible", "sin_espacio"])
def test_p07_usb_rechazada_y_nada_cambia(equipo, monkeypatch, caso):
    usb = equipo.usb
    if caso == "sin_usb":
        usb = equipo.tmp / "no_existe"
    elif caso == "no_escribible":
        monkeypatch.setattr(pl, "_probar_escritura",
                            lambda c: (_ for _ in ()).throw(PermissionError("protegida")))
    else:
        monkeypatch.setattr(pl, "_espacio_libre", lambda c: 1024)
    antes = sorted(p.relative_to(equipo.tmp) for p in equipo.tmp.rglob("*"))
    with pytest.raises(pl.ErrorPaquete) as e:
        cf.ejecutar_fase1(
            fuentes=equipo.fuentes(), carpeta_usb=usb, usuario="ana", rol="ingeniero",
            rutas=equipo.rutas, config_manager=_Config(), cycle_manager=equipo.cm,
            leer_base_vieja=equipo.db.datos_para_cierre_fabrica, serie="SN260001", ahora=AHORA,
            mapas=MAPAS, origen_calibracion=equipo.calib)
    assert e.value.codigo == {"sin_usb": "usb_ausente", "no_escribible": "usb_no_escribible",
                              "sin_espacio": "usb_sin_espacio"}[caso]
    despues = sorted(p.relative_to(equipo.tmp) for p in equipo.tmp.rglob("*"))
    assert despues == antes


# ── P-08: corte antes del punto de no retorno ─────────────────────────────
@pytest.mark.req("P-08", "FAB-05")
@pytest.mark.parametrize("corte", ["consolidar", "base_nueva", "antes_de_la_marca"])
def test_p08_corte_antes_de_la_marca_equipo_intacto(equipo, monkeypatch, corte):
    def falla(*_a, **_k):
        raise OSError("corte de energía simulado")
    if corte == "consolidar":
        monkeypatch.setattr(fe, "consolidar_defectos_programas", falla)
        with pytest.raises(OSError):
            equipo.fase1()
    elif corte == "base_nueva":
        monkeypatch.setattr(cf, "_crear_tablas_auditoria", falla)
        with pytest.raises(OSError):
            equipo.fase1()
        # la fase 1 borra sus temporales al fallar
        assert not equipo.rutas.base_nueva.exists()
    else:
        equipo.fase1()                  # todo listo, pero el corte llega antes de la marca
    equipo.cerrar_base()
    salida = cf.completar_cierre_si_pendiente(equipo.rutas)
    assert salida["marca"] is False
    # temporales borrados al arrancar; nada de lo vigente cambió
    assert not equipo.rutas.base_nueva.exists()
    assert not list(equipo.data.glob("*" + cf.SUFIJO_NUEVO))
    assert not equipo.rutas.defecto_nuevo.exists()
    assert not equipo.rutas.final(fe.NOMBRE_PARAMETROS).exists()
    assert (equipo.ciclos / "defecto" / "viejo_borrado.json").exists()
    assert _conteo(equipo.rutas.base, "ciclos") == 2
    assert (equipo.data / "respaldo_ciclos" / "aaaa-1111.jsonl").exists()
    assert json.loads((equipo.data / "ciclo_contador.json").read_text()) == {"ultimo": 2}
    # y el cierre se puede repetir completo
    monkeypatch.undo()
    equipo.db = DbManager(equipo.rutas.base)
    _cierre_completo(equipo)
    assert cf.completar_cierre_si_pendiente(equipo.rutas)["completado"] is True


# ── fase 2 y P-04 ─────────────────────────────────────────────────────────
def _comprobar_entregado(e: Equipo, r: cf.ResultadoFase1) -> None:
    base = e.rutas.base
    assert base.is_file()
    for s in cf.SIDECARS_BASE:
        assert not Path(str(base) + s).exists() or s == "-shm"
    assert not e.rutas.marca.exists() and not e.rutas.base_nueva.exists()
    assert not list(e.data.glob("autoclave.db.vieja*"))
    # P-04: solo lo de la sección 8
    db = DbManager(base)
    try:
        assert db.estado_fabrica() == "ENTREGADO"
        filas = db.get_auditoria(limite=50)
        assert sorted(f["evento"] for f in filas) == ["equipo_instalado", "equipo_liberado_fabrica"]
        assert sorted(u["usuario"] for u in db.listar_usuarios()) == ["Admin", "Ingeniero"]
    finally:
        db.close()
    for tabla in ("ciclos", "lecturas", "alarmas_historial", "mantenimientos", "operadores",
                  "catalogo_carga"):
        assert _conteo(base, tabla) == 0, tabla
    assert _filas(base, "SELECT hash_paquete FROM estado_fabrica") == [(r.hash_paquete,)]
    rc = e.data / "respaldo_ciclos"
    assert not rc.exists() or not any(rc.rglob("*"))
    assert not (e.data / "respaldo_ciclos.fab_borrar").exists()
    # contadores (D-10, DF-09, DF-10)
    assert json.loads((e.data / "ciclo_contador.json").read_text()) == {"ultimo": 0}
    assert json.loads((e.data / "mantenimiento_base.json").read_text()) == {"ciclos_instalacion": 0}
    assert json.loads((e.ciclos / "user" / "numeros_usados.json").read_text()) == [11, 12]
    # base de fábrica del equipo en su sitio
    assert e.rutas.final(fe.NOMBRE_PARAMETROS).is_file()
    assert json.loads(e.rutas.final(fe.NOMBRE_PARAMETROS).read_text())["timeout_puerta"] == 90
    assert e.rutas.final(fe.NOMBRE_CALIBRACION).is_file()
    assert (e.ciclos / "defecto" / "134_instrumental.json").exists()
    assert not (e.ciclos / "defecto" / "viejo_borrado.json").exists()
    assert (e.ciclos / "defecto" / "nota.txt").exists()
    assert not e.rutas.defecto_nuevo.exists() and not e.rutas.defecto_viejo.exists()
    # registros borrados
    for nombre in ("backend.log", "lanzador.log", "ui_puerta1.log", "login_recordado.json",
                   "last_shutdown.json", "autoclave.db.corrupta-20261101-101010",
                   "asignacion_io.json.bak"):
        assert not (e.data / nombre).exists(), nombre
    assert not list(e.logs.glob("*.log*"))
    assert not (e.datos / "installation_profile_cambios.log").exists()
    assert not list((e.ciclos / "user").glob("*.bak"))
    # se conserva
    for nombre in ("asignacion_io.json", "asignacion_io.json.formato1.bak", "mantenimiento.json",
                   "tema.json", "idioma.json", "unidades.json", "impresora.json",
                   "correo_equipo.json", "calibration_modbus.yaml"):
        assert (e.data / nombre).exists(), nombre
    assert (e.datos / "installation_profile.json").exists()
    assert (e.datos / "estacion" / "respaldo_07.json").exists()
    assert (e.ciclos / "user" / "fabrica_vistos.lst").exists()
    assert (e.ciclos / "user" / "instrumental_134.json").exists()
    assert not (e.data / "BD_BLOQUEADA").exists()


@pytest.mark.req("P-04", "PA-08", "PA-09", "DF-09", "DF-10")
def test_p04_cierre_completo_y_dos_reinicios(equipo):
    r = _cierre_completo(equipo)
    assert equipo.rutas.marca.exists()
    marca = json.loads(equipo.rutas.marca.read_text(encoding="utf-8"))
    assert marca["pasos_pendientes"] == list(cf.PASOS) and marca["hash_paquete"] == r.hash_paquete
    salida = cf.completar_cierre_si_pendiente(equipo.rutas)
    assert salida["completado"] is True and salida["hechos"] == list(cf.PASOS)
    _comprobar_entregado(equipo, r)
    # segundo reinicio: nada que hacer, nada cambia (idempotente)
    salida = cf.completar_cierre_si_pendiente(equipo.rutas)
    assert salida["marca"] is False and salida["restos"] == []
    _comprobar_entregado(equipo, r)


@pytest.mark.req("P-10")
def test_p10_ninguna_cadena_de_prueba_en_los_datos(equipo):
    for raiz in (equipo.datos, equipo.ciclos):
        assert any(CADENA.encode() in p.read_bytes() for p in raiz.rglob("*") if p.is_file()) \
            or raiz == equipo.ciclos
    _cierre_completo(equipo)
    cf.completar_cierre_si_pendiente(equipo.rutas)
    culpables = [str(p) for raiz in (equipo.datos, equipo.ciclos) for p in raiz.rglob("*")
                 if p.is_file() and (CADENA.encode() in p.read_bytes()
                                     or CADENA.encode("utf-16-le") in p.read_bytes())]
    assert culpables == []


# ── P-08: corte después del punto de no retorno ───────────────────────────
@pytest.mark.req("P-08", "FAB-05")
@pytest.mark.parametrize("paso", cf.PASOS)
def test_p08_corte_en_cada_paso_de_la_fase2_y_reanudacion(equipo, monkeypatch, paso):
    r = _cierre_completo(equipo)
    original = cf._FUNCIONES[paso]

    def corte(rutas, fallos):
        raise OSError("corte simulado")
    monkeypatch.setitem(cf._FUNCIONES, paso, corte)
    salida = cf.completar_cierre_si_pendiente(equipo.rutas)
    if paso in cf.PASOS_CRITICOS:
        assert salida["completado"] is False and paso in salida["pendientes"]
        assert equipo.rutas.marca.exists()
        # la base queda bloqueada: el backend no abre ni reimporta nada
        bloqueo = equipo.data / "BD_BLOQUEADA"
        assert bloqueo.read_text(encoding="utf-8").startswith(cf.PREFIJO_BLOQUEO)
        hechos = json.loads(equipo.rutas.marca.read_text(encoding="utf-8"))["pasos_hechos"]
        assert hechos == list(cf.PASOS[:cf.PASOS.index(paso)])
        monkeypatch.setitem(cf._FUNCIONES, paso, original)
        salida = cf.completar_cierre_si_pendiente(equipo.rutas)
    # mejor esfuerzo: se da por hecho con aviso y el cierre termina
    assert salida["completado"] is True
    if paso in ("registros", "base_vieja"):
        # lo que quedó lo borra la limpieza de restos o queda como aviso
        monkeypatch.setitem(cf._FUNCIONES, paso, original)
        original(equipo.rutas, [])
    _comprobar_entregado(equipo, r)


@pytest.mark.req("P-08")
def test_p08_corte_a_mitad_del_reemplazo_de_la_base(equipo):
    r = _cierre_completo(equipo)
    base = equipo.rutas.base
    # corte justo después de apartar la base vieja, antes de poner la nueva
    base.rename(base.with_name(base.name + cf.SUFIJO_BASE_VIEJA))
    cf.completar_cierre_si_pendiente(equipo.rutas)
    _comprobar_entregado(equipo, r)


@pytest.mark.req("P-08")
def test_p08_marca_ilegible_completa_igual(equipo):
    r = _cierre_completo(equipo)
    equipo.rutas.marca.write_text("{roto", encoding="utf-8")
    assert cf.completar_cierre_si_pendiente(equipo.rutas)["completado"] is True
    _comprobar_entregado(equipo, r)


def test_un_wal_viejo_no_queda_junto_a_la_base_nueva(equipo):
    r = _cierre_completo(equipo)
    wal = Path(str(equipo.rutas.base) + "-wal")
    wal.write_bytes(b"WAL de prueba " + CADENA.encode())
    cf.completar_cierre_si_pendiente(equipo.rutas)
    assert not wal.exists()
    _comprobar_entregado(equipo, r)


def test_bd_bloqueada_ajena_no_se_retira(equipo):
    _cierre_completo(equipo)
    bloqueo = equipo.data / "BD_BLOQUEADA"
    bloqueo.write_text("Base de datos corrupta apartada", encoding="utf-8")
    cf.completar_cierre_si_pendiente(equipo.rutas)
    assert bloqueo.exists()


def test_log_abierto_se_vacia(equipo, monkeypatch):
    _cierre_completo(equipo)
    log = equipo.data / "backend.log"
    real = Path.unlink

    def unlink(self, *a, **k):
        if self == log:
            raise PermissionError("en uso")
        return real(self, *a, **k)
    monkeypatch.setattr(Path, "unlink", unlink)
    assert cf.completar_cierre_si_pendiente(equipo.rutas)["completado"] is True
    assert log.exists() and log.stat().st_size == 0


def test_marca_exige_temporales_completos(equipo):
    r = equipo.fase1()
    equipo.rutas.temporal(fe.NOMBRE_CALIBRACION).unlink()
    with pytest.raises(cf.ErrorCierre) as e:
        cf.escribir_marca(equipo.rutas, r, "ana")
    assert e.value.codigo == "temporales_incompletos"
    assert not equipo.rutas.marca.exists()


def test_resumen_cuenta_lo_que_se_borra(equipo):
    datos = cf.resumen(equipo.db)
    assert datos["conteos"]["ciclos"] == 2 and datos["conteos"]["operadores"] == 1
    assert datos["conteos"]["usuarios_prueba"] == 2 and datos["conteos"]["catalogo_carga"] == 1
    assert datos["conteos"]["mantenimientos"] == 1 and datos["conteos"]["alarmas"] == 1
    assert "respaldo_ciclos" in datos["se_borra"] and "equipo_instalado" in datos["queda"]


def test_completar_nunca_lanza(tmp_path):
    rutas = cf.RutasCierre(carpeta_datos=tmp_path / "no", carpeta_ciclos=tmp_path / "no")
    assert cf.completar_cierre_si_pendiente(rutas)["marca"] is False


@pytest.mark.req("P-12")
def test_p12_el_cierre_no_quita_triggers_ni_borra_filas():
    for rel in ("core/runtime/cierre_fabrica.py", "backend/rutas/fabrica.py"):
        texto = (RAIZ / "src" / "autoclave" / rel).read_text(encoding="utf-8").upper()
        assert "DROP TRIGGER" not in texto and "DELETE FROM" not in texto, rel
    for ruta in (RAIZ / "src").rglob("*.py"):
        assert "DROP TRIGGER" not in ruta.read_text(encoding="utf-8").upper(), ruta


def test_main_llama_a_la_fase2_antes_del_servidor():
    import ast
    arbol = ast.parse((RAIZ / "src" / "autoclave" / "backend" / "main.py").read_text("utf-8"))
    main = next(n for n in arbol.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    orden = []
    for nodo in ast.walk(main):
        if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name):
            orden.append((nodo.lineno, nodo.func.id))
        if isinstance(nodo, ast.ImportFrom) and nodo.module == "autoclave.backend" \
                and any(a.name == "server" for a in nodo.names):
            orden.append((nodo.lineno, "import server"))
    nombres = [n for _, n in sorted(orden)]
    assert nombres.index("completar_cierre_fabrica") < nombres.index("import server")


def test_main_completar_no_lanza():
    from autoclave.backend import main as m
    assert m.completar_cierre_fabrica(lambda: {"ok": 1}) == {"ok": 1}

    def falla():
        raise RuntimeError("x")
    assert m.completar_cierre_fabrica(falla) is None

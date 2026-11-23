# tests/test_fab_s_cierre.py
#
# Correcciones de la revisión de seguridad del modo fábrica
# (docs/informes/modo_fabrica/S_revision_seguridad.md): SAF-01 (la fase 2 no
# destruye nada sin validar), SAF-02 (cierre incompleto = arranque detenido,
# respaldos posteriores conservados, contador que nunca baja), SAF-03 (marca
# que no se actualiza o no se borra) y SAF-06 (restos solo en ENTREGADO).
#
# Todo en carpetas temporales con el «equipo» de test_fab_e5_cierre.

import json
import os
import shutil
import sqlite3
from pathlib import Path

import pytest

from autoclave.core.runtime import cierre_fabrica as cf
from autoclave.services.domain.logging.db_manager import DbManager
from tests.test_fab_e5_cierre import Equipo, _cierre_completo, _comprobar_entregado, _conteo

pytestmark = pytest.mark.req("SAF-01", "SAF-02", "SAF-03", "SAF-06")


@pytest.fixture
def equipo(tmp_path):
    e = Equipo(tmp_path)
    yield e
    try:
        e.db.close()
    except Exception:
        pass


def _rechazadas(e: Equipo) -> list[Path]:
    return sorted(e.data.glob(cf.NOMBRE_MARCA + cf.SUFIJO_RECHAZADA + "*"))


def _intacto_entregado_con_ciclos(e: Equipo) -> None:
    """Nada destructivo pasó: ciclos, respaldos, contador y logs siguen."""
    assert _conteo(e.rutas.base, "ciclos") == 2
    assert (e.data / "respaldo_ciclos" / "aaaa-1111.jsonl").exists()
    assert (e.data / "respaldo_ciclos" / "importados" / "bbbb-2222.jsonl").exists()
    assert json.loads((e.data / "ciclo_contador.json").read_text()) == {"ultimo": 2}
    assert json.loads((e.data / "mantenimiento_base.json").read_text()) == {"ciclos_instalacion": 79}
    assert (e.data / "backend.log").exists()
    assert (e.data / "autoclave.db.corrupta-20261101-101010").exists()


def _equipo_entregado_en_campo(e: Equipo) -> None:
    """Un equipo ENTREGADO con ciclos reales: base sin fila FÁBRICA."""
    e.db.close()
    e.rutas.base.unlink()
    for s in cf.SIDECARS_BASE:
        Path(str(e.rutas.base) + s).unlink(missing_ok=True)
    db = DbManager(e.rutas.base)
    try:
        db.registrar_auditoria("equipo_instalado", usuario="sistema", entidad="SN260001")
        for n in (1, 2):
            cid = db.crear_ciclo(n, "solido", "Instrumental 134", 134.0, 4.0, "M-1", "SN260001", "x")
            db.cerrar_ciclo(cid, "COMPLETADO")
        assert db.estado_fabrica() == "ENTREGADO"
    finally:
        db.close()


# ── SAF-01 ───────────────────────────────────────────────────────────────
@pytest.mark.parametrize("contenido", ["", "{}", "[]", '{"formato": 1}',
                                       '{"formato": 1, "hash_paquete": "x", "fecha": "2026-11-22"}'])
def test_saf01_marca_plantada_en_entregado_no_borra_nada(equipo, contenido):
    _equipo_entregado_en_campo(equipo)
    equipo.rutas.marca.write_text(contenido, encoding="utf-8")
    salida = cf.completar_cierre_si_pendiente(equipo.rutas)
    assert salida["completado"] is False and salida["bloquear"] is False
    assert salida["rechazada"] and salida["motivo"]
    assert not equipo.rutas.marca.exists() and len(_rechazadas(equipo)) == 1
    assert cf.cierre_incompleto(equipo.rutas) is False
    _intacto_entregado_con_ciclos(equipo)


def test_saf01_marca_rechazada_no_sobrescribe_una_anterior(equipo):
    _equipo_entregado_en_campo(equipo)
    for _ in range(2):
        equipo.rutas.marca.write_text("{}", encoding="utf-8")
        cf.completar_cierre_si_pendiente(equipo.rutas)
    assert len(_rechazadas(equipo)) == 2


def test_saf01_marca_legitima_copiada_a_un_equipo_entregado_con_ciclos(equipo):
    # una marca de verdad (hash y fecha válidos) con «base» ya hecho, en un
    # equipo que ya operó: la base tiene ciclos → rechazada
    r = _cierre_completo(equipo)
    assert cf.completar_cierre_si_pendiente(equipo.rutas)["completado"] is True
    db = DbManager(equipo.rutas.base)
    try:
        cid = db.crear_ciclo(1, "solido", "Instrumental 134", 134.0, 4.0, "M-1", "SN260001", "x")
        db.cerrar_ciclo(cid, "COMPLETADO")
    finally:
        db.close()
    rc = equipo.data / "respaldo_ciclos"
    rc.mkdir(exist_ok=True)
    (rc / "real.jsonl").write_text("{}", encoding="utf-8")
    (equipo.data / "ciclo_contador.json").write_text('{"ultimo": 1}', encoding="utf-8")
    marca = {"formato": 1, "fecha": r.fecha_liberacion, "usuario": "ana",
             "hash_paquete": r.hash_paquete, "ruta_paquete": "x",
             "pasos_hechos": ["archivos_fabrica", "defectos", "base"],
             "pasos_pendientes": ["respaldo_ciclos", "contadores", "registros", "base_vieja"]}
    equipo.rutas.marca.write_text(json.dumps(marca), encoding="utf-8")
    salida = cf.completar_cierre_si_pendiente(equipo.rutas)
    assert salida["rechazada"] and "ciclos" in salida["motivo"]
    assert (rc / "real.jsonl").exists()
    assert json.loads((equipo.data / "ciclo_contador.json").read_text()) == {"ultimo": 1}


def test_saf01_bitacora_posterior_a_la_liberacion_rechaza(equipo):
    r = _cierre_completo(equipo)
    assert cf.completar_cierre_si_pendiente(equipo.rutas)["completado"] is True
    db = DbManager(equipo.rutas.base)
    try:
        db.registrar_auditoria("login", usuario="ana", entidad="x")
    finally:
        db.close()
    marca = {"formato": 1, "fecha": r.fecha_liberacion, "hash_paquete": r.hash_paquete,
             "pasos_hechos": ["archivos_fabrica", "defectos", "base"]}
    equipo.rutas.marca.write_text(json.dumps(marca), encoding="utf-8")
    salida = cf.completar_cierre_si_pendiente(equipo.rutas)
    assert salida["rechazada"] and "bitácora" in salida["motivo"]


def test_saf01_nueva_fabricada_en_fabrica_se_rechaza(equipo):
    r = _cierre_completo(equipo)
    nueva = equipo.rutas.base_nueva
    nueva.unlink()
    # una «.nueva» que es una copia de una base en FÁBRICA (con sus ciclos)
    shutil.copy2(equipo.rutas.base, nueva)
    salida = cf.completar_cierre_si_pendiente(equipo.rutas)
    assert salida["rechazada"] and not salida["completado"]
    assert DbManager(equipo.rutas.base).estado_fabrica() == "FABRICA"
    assert _conteo(equipo.rutas.base, "ciclos") == 2
    assert (equipo.data / "respaldo_ciclos" / "aaaa-1111.jsonl").exists()
    assert len(_rechazadas(equipo)) == 1 and r.hash_paquete


def test_saf01_hash_distinto_se_rechaza(equipo):
    _cierre_completo(equipo)
    datos = json.loads(equipo.rutas.marca.read_text(encoding="utf-8"))
    datos["hash_paquete"] = "0" * 64
    equipo.rutas.marca.write_text(json.dumps(datos), encoding="utf-8")
    salida = cf.completar_cierre_si_pendiente(equipo.rutas)
    assert salida["rechazada"] and not salida["completado"]
    assert _conteo(equipo.rutas.base, "ciclos") == 2
    assert equipo.rutas.base_nueva.exists()        # la fase 2 no tocó nada


def test_saf01_fecha_distinta_se_rechaza(equipo):
    _cierre_completo(equipo)
    datos = json.loads(equipo.rutas.marca.read_text(encoding="utf-8"))
    datos["fecha"] = "2026-01-01T00:00:00"
    equipo.rutas.marca.write_text(json.dumps(datos), encoding="utf-8")
    assert cf.completar_cierre_si_pendiente(equipo.rutas)["rechazada"]
    assert _conteo(equipo.rutas.base, "ciclos") == 2


def test_saf01_vigente_entregado_con_nueva_valida_se_rechaza(equipo):
    # la .nueva es legítima pero la base vigente no está en FÁBRICA
    _cierre_completo(equipo)
    vigente = equipo.rutas.base
    conn = sqlite3.connect(str(vigente))
    try:
        conn.execute("UPDATE estado_fabrica SET estado = 'ENTREGADO' WHERE id = 1")
        conn.commit()
    finally:
        conn.close()
    assert cf.completar_cierre_si_pendiente(equipo.rutas)["rechazada"]
    assert _conteo(vigente, "ciclos") == 2


def test_saf01_cierre_legitimo_sigue_funcionando(equipo):
    r = _cierre_completo(equipo)
    salida = cf.completar_cierre_si_pendiente(equipo.rutas)
    assert salida["completado"] is True and salida["rechazada"] is None
    assert cf.cierre_incompleto(equipo.rutas) is False
    _comprobar_entregado(equipo, r)


def test_saf01_base_no_verificable_bloquea_sin_borrar(equipo, monkeypatch):
    _cierre_completo(equipo)

    def falla(_ruta):
        raise sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(cf, "_abrir_solo_lectura", falla)
    salida = cf.completar_cierre_si_pendiente(equipo.rutas)
    assert salida["bloquear"] is True and not salida["rechazada"]
    assert equipo.rutas.marca.exists() and cf.cierre_incompleto(equipo.rutas) is True
    assert equipo.rutas.base_nueva.exists() and _conteo(equipo.rutas.base, "ciclos") == 2
    monkeypatch.undo()
    assert cf.completar_cierre_si_pendiente(equipo.rutas)["completado"] is True


def test_saf01_validar_no_crea_la_base_vigente(equipo):
    r = _cierre_completo(equipo)
    datos = json.loads(equipo.rutas.marca.read_text(encoding="utf-8"))
    equipo.rutas.base.unlink()
    for s in cf.SIDECARS_BASE:
        Path(str(equipo.rutas.base) + s).unlink(missing_ok=True)
    equipo.rutas.base_nueva.unlink()
    equipo.rutas.marca.write_text(json.dumps(datos), encoding="utf-8")
    assert cf.completar_cierre_si_pendiente(equipo.rutas)["rechazada"]
    assert not equipo.rutas.base.exists() and r.hash_paquete == datos["hash_paquete"]


# ── SAF-02 ───────────────────────────────────────────────────────────────
def test_saf02_cierre_incompleto_sin_fase2_en_el_proceso_es_la_marca(tmp_path):
    rutas = cf.RutasCierre(carpeta_datos=tmp_path, carpeta_ciclos=tmp_path / "c")
    assert cf.cierre_incompleto(rutas) is False
    rutas.marca.write_text("{}", encoding="utf-8")
    assert cf.cierre_incompleto(rutas) is True      # falla cerrada


def test_saf02_paso_critico_fallido_bloquea_sin_bd_bloqueada(equipo, monkeypatch):
    _cierre_completo(equipo)

    def corte(rutas, fallos):
        raise OSError("corte")
    monkeypatch.setitem(cf._FUNCIONES, "respaldo_ciclos", corte)
    salida = cf.completar_cierre_si_pendiente(equipo.rutas)
    assert salida["bloquear"] is True and cf.cierre_incompleto(equipo.rutas) is True
    assert not (equipo.data / "BD_BLOQUEADA").exists()


def test_saf02_etapa1_del_arranque_se_detiene(monkeypatch):
    from autoclave.backend import context as ctx
    from autoclave.backend.arranque import secuencia
    monkeypatch.setattr(cf, "cierre_incompleto", lambda rutas=None: True)
    with pytest.raises(secuencia.ErrorArranque) as e:
        ctx.BackendContext.verificar_instalacion(object.__new__(ctx.BackendContext))
    assert e.value.codigo == secuencia.ARR_CIERRE_FABRICA == "ARR_CIERRE_FABRICA"


def test_saf02_secuencia_no_construye_el_control(monkeypatch):
    from autoclave.backend.arranque import secuencia
    from autoclave.backend.arranque.registro import RegistroArranque

    class Ctx:
        construido = False

        def verificar_instalacion(self):
            raise secuencia.ErrorArranque(secuencia.ARR_CIERRE_FABRICA, "x")

        def construir_control(self, _f):
            Ctx.construido = True
    registro = RegistroArranque()
    secuencia.ejecutar_arranque(Ctx(), registro, al_cancelar_prueba=lambda: None,
                                al_operable=lambda: None, esperar_interfaz=False)
    assert Ctx.construido is False
    inst = registro.instantanea()
    assert inst["falloBloqueante"] is True
    assert any(e["codigo"] == "ARR_CIERRE_FABRICA" for e in inst["etapas"])


def test_saf02_respaldos_posteriores_a_la_marca_se_conservan(equipo):
    r = _cierre_completo(equipo)
    nuevo = equipo.data / "respaldo_ciclos" / "posterior.jsonl"
    nuevo.write_text("ciclo real\n", encoding="utf-8")       # mtime = ahora > AHORA
    viejo = equipo.data / "respaldo_ciclos" / "aaaa-1111.jsonl"
    assert cf.completar_cierre_si_pendiente(equipo.rutas)["completado"] is True
    assert nuevo.exists() and nuevo.read_text(encoding="utf-8") == "ciclo real\n"
    assert not viejo.exists()
    assert not (equipo.data / "respaldo_ciclos" / "importados" / "bbbb-2222.jsonl").exists()
    _ = r


def test_saf02_contadores_no_bajan_con_ciclos_en_la_base(equipo):
    equipo.cerrar_base()
    (equipo.data / "ciclo_contador.json").write_text('{"ultimo": 57}', encoding="utf-8")
    cf._paso_contadores(equipo.rutas, [])          # la base vigente tiene 2 ciclos
    assert json.loads((equipo.data / "ciclo_contador.json").read_text()) == {"ultimo": 57}
    assert json.loads((equipo.data / "mantenimiento_base.json").read_text()) == {"ciclos_instalacion": 79}
    # numeros_usados sí se ajusta
    assert json.loads((equipo.ciclos / "user" / "numeros_usados.json").read_text()) == [11, 12]


# ── SAF-03 ───────────────────────────────────────────────────────────────
def test_saf03_marca_no_actualizada_corta_la_fase2(equipo, monkeypatch):
    r = _cierre_completo(equipo)
    real = cf.escribir_texto_atomico
    llamadas = {"n": 0}

    def falla_en_marca(ruta, texto, *a, **k):
        if Path(ruta) == equipo.rutas.marca:
            llamadas["n"] += 1
            if llamadas["n"] == 3:       # tras el paso «base»
                raise OSError("disco")
        return real(ruta, texto, *a, **k)
    monkeypatch.setattr(cf, "escribir_texto_atomico", falla_en_marca)
    salida = cf.completar_cierre_si_pendiente(equipo.rutas)
    assert salida["bloquear"] is True and salida["completado"] is False
    assert salida["hechos"] == ["archivos_fabrica", "defectos"]
    # no siguió: los respaldos y el contador siguen
    assert (equipo.data / "respaldo_ciclos" / "aaaa-1111.jsonl").exists()
    assert json.loads((equipo.data / "ciclo_contador.json").read_text()) == {"ultimo": 2}
    # la marca dice «base» pendiente pero la base ya se reemplazó: el
    # siguiente arranque valida como base hecha y termina
    monkeypatch.undo()
    salida = cf.completar_cierre_si_pendiente(equipo.rutas)
    assert salida["completado"] is True, salida
    _comprobar_entregado(equipo, r)


def test_saf03_unlink_fallido_renombra_a_hecho(equipo, monkeypatch):
    r = _cierre_completo(equipo)
    real = Path.unlink

    def unlink(self, *a, **k):
        if self == equipo.rutas.marca:
            raise PermissionError("en uso")
        return real(self, *a, **k)
    monkeypatch.setattr(Path, "unlink", unlink)
    assert cf.completar_cierre_si_pendiente(equipo.rutas)["completado"] is True
    monkeypatch.undo()
    assert not equipo.rutas.marca.exists()
    assert (equipo.data / cf.NOMBRE_MARCA_HECHA).exists()
    _comprobar_entregado(equipo, r)


def test_saf03_unlink_y_renombre_fallidos_no_repiten_nada(equipo, monkeypatch):
    _cierre_completo(equipo)
    real_unlink, real_replace = Path.unlink, os.replace

    def unlink(self, *a, **k):
        if self == equipo.rutas.marca:
            raise PermissionError("en uso")
        return real_unlink(self, *a, **k)

    def replace(src, dst):
        if Path(src) == equipo.rutas.marca and Path(dst).name == cf.NOMBRE_MARCA_HECHA:
            raise PermissionError("en uso")
        return real_replace(src, dst)
    monkeypatch.setattr(Path, "unlink", unlink)
    monkeypatch.setattr(cf.os, "replace", replace)
    assert cf.completar_cierre_si_pendiente(equipo.rutas)["completado"] is True
    monkeypatch.undo()
    assert equipo.rutas.marca.exists()
    # el equipo opera: ciclos y respaldos nuevos
    db = DbManager(equipo.rutas.base)
    try:
        cid = db.crear_ciclo(1, "solido", "Instrumental 134", 134.0, 4.0, "M-1", "SN260001", "x")
        db.cerrar_ciclo(cid, "COMPLETADO")
    finally:
        db.close()
    (equipo.data / "ciclo_contador.json").write_text('{"ultimo": 1}', encoding="utf-8")
    rc = equipo.data / "respaldo_ciclos"
    rc.mkdir(exist_ok=True)
    (rc / "real.jsonl").write_text("{}", encoding="utf-8")
    vieja = json.loads(equipo.rutas.marca.read_text(encoding="utf-8"))
    salida = cf.completar_cierre_si_pendiente(equipo.rutas)
    assert salida["completado"] is True and salida["hechos"] == list(cf.PASOS)
    assert (rc / "real.jsonl").exists() and _conteo(equipo.rutas.base, "ciclos") == 1
    assert json.loads((equipo.data / "ciclo_contador.json").read_text()) == {"ultimo": 1}
    # y si esa marca vieja dijera que quedan pasos, la validación la rechaza
    datos = dict(vieja, pasos_hechos=["archivos_fabrica", "defectos", "base"])
    equipo.rutas.marca.write_text(json.dumps(datos), encoding="utf-8")
    salida = cf.completar_cierre_si_pendiente(equipo.rutas)
    assert salida["rechazada"] and (rc / "real.jsonl").exists()


# ── SAF-06 ───────────────────────────────────────────────────────────────
def test_saf06_restos_no_se_tocan_en_fabrica(equipo):
    equipo.cerrar_base()
    vieja = equipo.data / "autoclave.db.vieja"
    vieja.write_bytes(b"datos de alguien")
    apartada = equipo.data / "respaldo_ciclos.fab_borrar"
    apartada.mkdir()
    (apartada / "x.jsonl").write_text("{}", encoding="utf-8")
    assert cf.completar_cierre_si_pendiente(equipo.rutas)["restos"] == []
    assert vieja.read_bytes() == b"datos de alguien" and (apartada / "x.jsonl").exists()


def test_saf06_restos_no_se_tocan_en_entregado_sin_fecha(equipo):
    _equipo_entregado_en_campo(equipo)
    vieja = equipo.data / "autoclave.db.vieja"
    vieja.write_bytes(b"x")
    cf.completar_cierre_si_pendiente(equipo.rutas)
    assert vieja.exists()


def test_saf06_restos_se_borran_tras_un_cierre(equipo):
    _cierre_completo(equipo)
    assert cf.completar_cierre_si_pendiente(equipo.rutas)["completado"] is True
    vieja = equipo.data / "autoclave.db.vieja"
    vieja.write_bytes(b"x")
    assert "autoclave.db.vieja" in cf.completar_cierre_si_pendiente(equipo.rutas)["restos"]
    assert not vieja.exists()


def test_saf06_temporales_de_fase1_se_borran_siempre(equipo):
    equipo.cerrar_base()
    tmp = equipo.data / ("parametros_fabrica_equipo.json" + cf.SUFIJO_NUEVO)
    tmp.write_text("{}", encoding="utf-8")
    cf.completar_cierre_si_pendiente(equipo.rutas)
    assert not tmp.exists()

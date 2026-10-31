"""Instalación por automatización: puente del asistente (docs/informes/automatizacion/diseno.md §4).

Cubre construir_perfil / validarCodigo / instalar con el verificador real de
`installation/activacion_v2` y códigos v2 armados con `tests/helpers/codigo_doble`
(K_t de prueba, siempre aislada con `configurar_transporte`), y los dobles
`codigo_doble.acepta/rechaza` para las ramas del puente."""

import json
import sys
from pathlib import Path
from datetime import date, datetime

import pytest

from autoclave import i18n
from autoclave.installation import activacion_v2 as v2
from autoclave.installation import storage
from autoclave.installation.profile import ProfileValidationError
from autoclave.services.domain.logging.db_manager import DbManager
from tests.helpers import codigo_doble
from tests.helpers.codigo_doble import K_T_PRUEBA, construir_codigo_v2

pytest.importorskip("PySide6")
from autoclave.ui_qml.bridge import puente_instalacion as pi

AHORA = datetime(2026, 10, 22, 8, 0, 0)
HOY = AHORA.date()
SERIE = "SN260001"
K_E = bytes(range(16))
ORIG = ("sn-123 456", "  Autoclave   Marca X 50L ")        # en bruto
ORIG_N = ("SN-123456", "AUTOCLAVE MARCA X 50L")             # normalizados (los firmados)
CLAVES = {"clave_admin": "admin-nueva-1", "confirmacion_admin": "admin-nueva-1",
          "clave_ingeniero": "inge-nueva-1", "confirmacion_ingeniero": "inge-nueva-1"}


@pytest.fixture(autouse=True)
def transporte():
    v2.configurar_transporte(K_T_PRUEBA)
    yield
    v2.configurar_transporte(None)


@pytest.fixture
def perfil_tmp(monkeypatch, tmp_path):
    ruta = tmp_path / "installation_profile.json"
    monkeypatch.setattr(storage, "INSTALLATION_FILE", ruta)
    return ruta


def _datos(**cambios):
    d = {
        "serial_number": SERIE, "equipment_class": "piso_lab",
        "door_count": 2, "door_type": "advanced", "door_id": 2, "cooling_level": 2,
        "vapor_source": "generator", "capacidad_litros": 45, "tipo_carga": "V",
        "supply_inputs": {}, "temperature_probes": {},
    }
    d.update(cambios)
    return d


def _auto(**cambios):
    base = {"tipo_instalacion": "automatizacion", "serial_original": ORIG[0],
            "modelo_original": ORIG[1]}
    base.update(cambios)
    return _datos(**base)


def _codigo(originales=None, orig=None, serial=SERIE, agrupar=False, ventana=HOY):
    return construir_codigo_v2(serial, K_E, permanente=True, ventana=ventana, P=0, G=0, orig=orig,
                               emerg=0, originales=originales, agrupar=agrupar)


def _msg(clave):
    return i18n.t(clave)


def _v1_valido(s, c, modo, *a, hoy=None, **k):
    """Verificador real con un v1 que siempre pasa (el v1 real no es de este conjunto)."""
    return v2.verificar_codigo_instalacion(s, c, modo, *a, hoy=hoy, validar_v1=lambda *_: True)


@pytest.fixture
def puente(perfil_tmp):
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    return pi.PuenteInstalacion(abrir_bd=lambda: DbManager(perfil_tmp.parent / "autoclave.db"),
                                es_semilla=lambda c: False)


# --- fabricación ------------------------------------------------------------------------------------

def test_fabricacion_con_v1_como_hoy():
    p = pi.construir_perfil(_datos(serial_number="ab-123"), "ABCDEFGHIJKL", AHORA,
                            verificar_codigo=_v1_valido)
    assert p.tipo_instalacion == "fabricacion" and p.sello_identidad is None
    assert p.serial_original is None and p.modelo_original is None
    assert p.machine_id == "ACV-2026-AB-123"


def test_fabricacion_con_v2_ins():
    p = pi.construir_perfil(_datos(), _codigo(), AHORA)
    assert p.serial_number == SERIE and p.machine_id == f"ACV-2026-{SERIE}"
    assert p.tipo_instalacion == "fabricacion" and p.sello_identidad is None


def test_fabricacion_ignora_los_originales_que_mande_la_pantalla(perfil_tmp):
    p = pi.construir_perfil(_datos(serial_original="X1", modelo_original="Y1"), _codigo(), AHORA)
    assert p.serial_original is None and p.modelo_original is None and p.sello_identidad is None
    pi.escribir_perfil(p)
    guardado = json.loads(perfil_tmp.read_text(encoding="utf-8"))
    for campo in ("tipo_instalacion", "serial_original", "modelo_original", "sello_identidad"):
        assert campo not in guardado


def test_fabricacion_rechaza_un_codigo_de_automatizacion():
    with pytest.raises(ValueError) as e:
        pi.construir_perfil(_datos(), _codigo(originales=ORIG), AHORA)
    assert str(e.value) == _msg("instalacion.error_codigo")


def test_tipo_instalacion_desconocido_es_fabricacion():
    p = pi.construir_perfil(_datos(tipo_instalacion="otra"), _codigo(), AHORA)
    assert p.tipo_instalacion == "fabricacion"


# --- automatización ---------------------------------------------------------------------------------

def test_automatizacion_de_punta_a_punta(perfil_tmp):
    p = pi.construir_perfil(_auto(), _codigo(originales=ORIG), AHORA)
    assert p.tipo_instalacion == "automatizacion"
    assert (p.serial_original, p.modelo_original) == ORIG_N
    assert p.serial_number == SERIE and p.machine_id == f"ACV-2026-{SERIE}"
    assert p.model_id == "SPK-SAT 45V2-LAB"                       # el modelo sigue calculándose
    assert p.sello_identidad == v2.sellar_identidad("automatizacion", SERIE, *ORIG_N, k_t=K_T_PRUEBA)
    pi.escribir_perfil(p)
    cargado = storage.load()                                       # verifica el sello
    assert cargado.tipo_instalacion == "automatizacion"
    assert (cargado.serial_original, cargado.modelo_original) == ORIG_N
    assert cargado.sello_identidad == p.sello_identidad


def test_automatizacion_con_reia_y_codigo_agrupado():
    codigo = _codigo(originales=ORIG, orig=date(2026, 10, 1), agrupar=True)
    assert codigo.count("-") == 11
    p = pi.construir_perfil(_auto(), codigo, AHORA)
    assert p.tipo_instalacion == "automatizacion"


def test_el_perfil_de_automatizacion_editado_no_carga(perfil_tmp):
    pi.escribir_perfil(pi.construir_perfil(_auto(), _codigo(originales=ORIG), AHORA))
    data = json.loads(perfil_tmp.read_text(encoding="utf-8"))
    data["modelo_original"] = "OTRO MODELO"
    perfil_tmp.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ProfileValidationError):
        storage.load()


def test_automatizacion_rechaza_v1():
    with pytest.raises(ValueError) as e:
        pi.construir_perfil(_auto(), "ABCDEFGHIJKL", AHORA, verificar_codigo=_v1_valido)
    assert str(e.value) == _msg("instalacion.error_codigo_v1_automatizacion")


def test_automatizacion_rechaza_un_codigo_de_fabricacion():
    with pytest.raises(ValueError) as e:
        pi.construir_perfil(_auto(), _codigo(), AHORA)
    assert str(e.value) == _msg("instalacion.error_codigo_automatizacion")


def test_automatizacion_con_otros_originales_da_el_mensaje_generico():
    codigo = _codigo(originales=ORIG)
    with pytest.raises(ValueError) as e:
        pi.construir_perfil(_auto(modelo_original="MODELO DISTINTO"), codigo, AHORA)
    assert str(e.value) == _msg("instalacion.error_codigo_automatizacion")
    with pytest.raises(ValueError) as e:
        pi.construir_perfil(_auto(serial_number="SN260002"), codigo, AHORA)
    assert str(e.value) == _msg("instalacion.error_codigo_automatizacion")


@pytest.mark.parametrize("cambios, clave", [
    ({"serial_original": ""}, "instalacion.error_serie_original"),
    ({"serial_original": "A|B"}, "instalacion.error_serie_original"),
    ({"serial_original": "A" * 41}, "instalacion.error_serie_original"),
    ({"serial_original": None}, "instalacion.error_serie_original"),
    ({"modelo_original": "   "}, "instalacion.error_modelo_original"),
    ({"modelo_original": "M|1"}, "instalacion.error_modelo_original"),
    ({"modelo_original": "ñ"}, "instalacion.error_modelo_original"),
    ({"modelo_original": "M" * 81}, "instalacion.error_modelo_original"),
])
def test_originales_invalidos(cambios, clave):
    with pytest.raises(ValueError) as e:
        pi.construir_perfil(_auto(**cambios), _codigo(originales=ORIG), AHORA)
    assert str(e.value) == _msg(clave)


def test_serial_especifika_con_otro_formato_en_v2():
    with pytest.raises(ValueError) as e:
        pi.construir_perfil(_auto(serial_number="AB-123"), _codigo(originales=ORIG), AHORA)
    assert str(e.value) == _msg("instalacion.error_serial_v2")


def test_sin_transporte_usa_el_error_generico_y_deja_log(caplog):
    v2.configurar_transporte(b"")
    caplog.set_level("ERROR")
    with pytest.raises(ValueError) as e:
        pi.construir_perfil(_auto(), _codigo(originales=ORIG), AHORA)
    assert str(e.value) == _msg("instalacion.error_codigo")
    assert any("transporte" in r.getMessage() for r in caplog.records if r.levelname == "ERROR")


def test_el_verificador_recibe_la_fecha_de_ahora_y_los_originales():
    doble = codigo_doble.acepta(codigo_doble.Modo.AUTOMATIZACION, ORIG_N)
    pi.construir_perfil(_auto(), "X", AHORA, verificar_codigo=doble, sellar=lambda *a: "a" * 64)
    ll = doble.llamadas[0]
    assert ll["modo"] is v2.Modo.AUTOMATIZACION
    assert (ll["serie_original"], ll["modelo_original"]) == ORIG


def test_automatizacion_con_doble_usa_los_originales_del_resultado():
    doble = codigo_doble.acepta(codigo_doble.Modo.AUTOMATIZACION, ORIG_N)
    p = pi.construir_perfil(_auto(), "X", AHORA, verificar_codigo=doble,
                            sellar=lambda tipo, serial, s, m: f"{tipo}|{serial}|{s}|{m}".ljust(64, "0")[:64])
    assert (p.serial_original, p.modelo_original) == ORIG_N


def test_el_doble_que_rechaza_da_el_mensaje_segun_el_modo():
    with pytest.raises(ValueError) as e:
        pi.construir_perfil(_auto(), "X", AHORA, verificar_codigo=codigo_doble.rechaza("etiqueta"))
    assert str(e.value) == _msg("instalacion.error_codigo_automatizacion")
    with pytest.raises(ValueError) as e:
        pi.construir_perfil(_datos(), "X", AHORA, verificar_codigo=codigo_doble.rechaza("etiqueta"))
    assert str(e.value) == _msg("instalacion.error_codigo")


# --- slots ------------------------------------------------------------------------------------------

def test_slot_validar_codigo_devuelve_vacio_o_clave(puente):
    ok = _codigo(originales=ORIG, ventana=date.today())
    assert puente.validarCodigo(SERIE, ok, "automatizacion", *ORIG) == ""
    assert puente.validarCodigo(SERIE.lower(), ok, "automatizacion", *ORIG) == ""
    assert puente.validarCodigo(SERIE, ok, "automatizacion", ORIG[0], "otro") == \
        "instalacion.error_codigo_automatizacion"
    assert puente.validarCodigo(SERIE, ok, "automatizacion", "", ORIG[1]) == \
        "instalacion.error_serie_original"
    assert puente.validarCodigo(SERIE, ok, "automatizacion", ORIG[0], "") == \
        "instalacion.error_modelo_original"
    assert puente.validarCodigo("AB-1", ok, "automatizacion", *ORIG) == "instalacion.error_serial_v2"
    assert puente.validarCodigo(SERIE, "ABCDEFGHIJKL", "automatizacion", *ORIG) == \
        "instalacion.error_codigo_v1_automatizacion"
    # fabricación: el código de automatización no vale, el de fabricación sí
    assert puente.validarCodigo(SERIE, ok, "fabricacion", "", "") == "instalacion.error_codigo"
    assert puente.validarCodigo(SERIE, _codigo(ventana=date.today()), "fabricacion", "", "") == ""
    assert puente.validarCodigo(SERIE, _codigo(ventana=date.today()), "automatizacion", *ORIG) == \
        "instalacion.error_codigo_automatizacion"


def test_slot_validar_original(puente):
    assert puente.validarOriginal("serie", " ab 12 ") == ""
    assert puente.validarOriginal("serie", "A|B") == "instalacion.error_serie_original"
    assert puente.validarOriginal("modelo", "Marca  X") == ""
    assert puente.validarOriginal("modelo", "M" * 81) == "instalacion.error_modelo_original"


def test_instalar_en_automatizacion_revalida_y_registra(perfil_tmp, puente):
    ok = _codigo(originales=ORIG, ventana=date.today())
    # sin haber validado el código en el slot, instalar() no pasa
    r = puente.instalar(_auto(contrasenas=CLAVES))
    assert r["ok"] is False and not perfil_tmp.exists()
    assert puente.validarCodigo(SERIE, ok, "automatizacion", *ORIG) == ""
    # el código vale para otros originales: instalar() lo rechaza aunque el slot ya lo aceptó
    r = puente.instalar(_auto(modelo_original="OTRO", contrasenas=CLAVES))
    assert r == {"ok": False, "error": _msg("instalacion.error_codigo_automatizacion")}
    assert not perfil_tmp.exists()
    r = puente.instalar(_auto(contrasenas=CLAVES))
    assert r == {"ok": True, "error": ""}
    assert storage.load().tipo_instalacion == "automatizacion"
    db = DbManager(perfil_tmp.parent / "autoclave.db")
    try:
        filas = db.get_auditoria(evento="equipo_instalado", limite=10)
    finally:
        db.close()
    assert len(filas) == 1
    detalle = filas[0]["detalle"]
    assert detalle["tipo_instalacion"] == "automatizacion"
    assert (detalle["serie_original"], detalle["modelo_original"]) == ORIG_N
    assert detalle["serie"] == SERIE


def test_instalar_en_fabricacion_no_agrega_claves_de_automatizacion(perfil_tmp, puente):
    assert puente.validarCodigo(SERIE, _codigo(ventana=date.today()), "fabricacion", "", "") == ""
    assert puente.instalar(_datos(contrasenas=CLAVES)) == {"ok": True, "error": ""}
    db = DbManager(perfil_tmp.parent / "autoclave.db")
    try:
        detalle = db.get_auditoria(evento="equipo_instalado", limite=10)[0]["detalle"]
    finally:
        db.close()
    assert set(detalle) == {"serie", "modelo", "version", "zona_horaria"}


def test_claves_i18n_del_asistente_en_es_y_en():
    claves = ("automatizado", "serie_original", "modelo_original", "error_codigo_automatizacion",
              "error_codigo_v1_automatizacion", "error_serie_original", "error_modelo_original",
              "error_serial_v2")
    ruta = Path(i18n.__file__).parent
    for idioma in ("es", "en"):
        d = json.loads((ruta / f"{idioma}.json").read_text(encoding="utf-8"))
        for c in claves:
            assert d["instalacion"][c].strip()
        assert d["equipo"]["serial_especifika"].strip()

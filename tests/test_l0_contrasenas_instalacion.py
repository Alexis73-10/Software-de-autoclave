"""LIC-02 (licencia L0): el asistente de instalación obliga a fijar las
contraseñas de Admin e Ingeniero (reglas del backend, distintas de las semilla
y entre sí), las guarda antes del perfil (hash, debe_cambiar_clave=0,
auditoría) y no termina si el guardado falla. En un equipo ya instalado que
conserve una contraseña semilla, aviso no bloqueante SIS-07 solo para técnico
e ingeniero."""

import json
import sys
from pathlib import Path

import pytest

from autoclave.backend.contrasenas import verificar_password
from autoclave.installation import storage
from autoclave.services.domain.logging import db_manager as dbm
from autoclave.services.domain.logging.db_manager import DbManager
from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.alarms.catalogo import CATALOGO, CONTRASENA_SEMILLA, ROLES_VISIBLES
from autoclave.ui_qml.bridge import puente_instalacion as pi

RAIZ = Path(__file__).resolve().parents[1]
# Las contraseñas semilla son públicas (ya están en otras pruebas); aquí solo
# sirven para comprobar que se rechazan. El código fuente ya no las dice.
SEMILLA_ADMIN, SEMILLA_INGENIERO = "admin1234", "ingeniero1234"
VALIDAS = {"clave_admin": "admin-nueva-1", "confirmacion_admin": "admin-nueva-1",
           "clave_ingeniero": "inge-nueva-1", "confirmacion_ingeniero": "inge-nueva-1"}


def _sin_semilla(_clave):
    return False


def _datos(**cambios):
    d = {"serial_number": "ab-123", "equipment_class": "piso_lab",
         "door_count": 2, "door_type": "advanced", "door_id": 2, "cooling_level": 2,
         "vapor_source": "generator", "supply_inputs": {}, "temperature_probes": {},
         "capacidad_litros": 45, "tipo_carga": "V"}
    d.update(cambios)
    return d


@pytest.fixture
def entorno(monkeypatch, tmp_path):
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    monkeypatch.setattr(storage, "INSTALLATION_FILE", tmp_path / "installation_profile.json")
    return tmp_path


def _puente(tmp_path, **kw):
    kw.setdefault("abrir_bd", lambda: DbManager(tmp_path / "autoclave.db"))
    kw.setdefault("es_semilla", _sin_semilla)
    p = pi.PuenteInstalacion(validar_codigo=lambda s, c: True, **kw)
    assert p.validarCodigo("ab-123", "X") is True
    return p


def _cuenta(db_path, usuario):
    db = DbManager(db_path)
    try:
        return db.get_usuario_by_username(usuario), db.get_auditoria(evento="contrasena_fijada_instalacion")
    finally:
        db.close()


# ── reglas ───────────────────────────────────────────────────────────────────

def test_validas_sin_errores():
    assert pi.errores_contrasenas(VALIDAS, es_semilla=_sin_semilla) == {}


@pytest.mark.parametrize("cambios, esperado", [
    ({"clave_admin": "", "confirmacion_admin": ""}, {"clave_admin": "obligatorio",
                                                     "confirmacion_admin": "obligatorio"}),
    ({"clave_ingeniero": "corta", "confirmacion_ingeniero": "corta"}, {"clave_ingeniero": "corta"}),
    ({"clave_admin": "x" * 65, "confirmacion_admin": "x" * 65}, {"clave_admin": "larga"}),
    ({"confirmacion_admin": "otra-cosa-1"}, {"confirmacion_admin": "no_coinciden"}),
    ({"confirmacion_ingeniero": ""}, {"confirmacion_ingeniero": "obligatorio"}),
    ({"clave_ingeniero": "admin-nueva-1", "confirmacion_ingeniero": "admin-nueva-1"},
     {"clave_ingeniero": "iguales"}),
])
def test_reglas(cambios, esperado):
    assert pi.errores_contrasenas({**VALIDAS, **cambios}, es_semilla=_sin_semilla) == esperado


def test_rechaza_las_semillas_de_cualquiera_de_las_dos_cuentas():
    # verificación real contra los hashes semilla (PBKDF2)
    assert dbm.es_clave_semilla(SEMILLA_ADMIN) is True
    assert dbm.es_clave_semilla(SEMILLA_INGENIERO) is True
    assert dbm.es_clave_semilla("admin-nueva-1") is False
    claves = {"clave_admin": SEMILLA_INGENIERO, "confirmacion_admin": SEMILLA_INGENIERO,
              "clave_ingeniero": SEMILLA_ADMIN, "confirmacion_ingeniero": SEMILLA_ADMIN}
    assert pi.errores_contrasenas(claves) == {"clave_admin": "semilla", "clave_ingeniero": "semilla"}


def test_slot_devuelve_errores_para_la_pantalla(entorno):
    p = _puente(entorno, es_semilla=lambda c: c == "semilla-x1")
    r = p.validarContrasenas("semilla-x1", "semilla-x1", "corta", "otra")
    assert r["clave_admin"] == {"clave": "validacion.semilla", "valores": {}}
    assert r["clave_ingeniero"] == {"clave": "validacion.corta", "valores": {"min": 8}}
    assert r["confirmacion_ingeniero"]["clave"] == "validacion.no_coinciden"
    assert p.validarContrasenas(*[VALIDAS[c] for c in pi.CAMPOS_CONTRASENAS]) == {}


def test_textos_es_en():
    from autoclave import i18n
    for idioma in ("es", "en"):
        for clave in ("validacion.semilla", "validacion.iguales", "instalacion.paso_contrasenas",
                      "instalacion.contrasenas_titulo", "instalacion.clave_admin",
                      "instalacion.confirmacion_admin", "instalacion.clave_ingeniero",
                      "instalacion.confirmacion_ingeniero", "instalacion.error_contrasenas",
                      "bitacora.ev.contrasena_fijada_instalacion",
                      "bitacora.tipo.contrasena_fijada_instalacion"):
            assert i18n.t(clave, idioma) != clave, (idioma, clave)


# ── instalar ─────────────────────────────────────────────────────────────────

def test_no_termina_sin_las_contrasenas(entorno):
    p = _puente(entorno)
    for claves in (None, {}, {**VALIDAS, "confirmacion_ingeniero": "x"}):
        datos = _datos() if claves is None else _datos(contrasenas=claves)
        r = p.instalar(datos)
        assert r["ok"] is False
        assert not storage.INSTALLATION_FILE.exists()
    fila, auditoria = _cuenta(entorno / "autoclave.db", "Admin")
    assert fila["debe_cambiar_clave"] == 1 and auditoria == []


def test_guarda_hash_apaga_debe_cambiar_y_audita(entorno):
    p = _puente(entorno)
    assert p.instalar(_datos(contrasenas=VALIDAS)) == {"ok": True, "error": ""}
    assert storage.INSTALLATION_FILE.exists()
    for usuario, clave in (("Admin", "admin-nueva-1"), ("Ingeniero", "inge-nueva-1")):
        fila, auditoria = _cuenta(entorno / "autoclave.db", usuario)
        assert verificar_password(clave, fila["hash_pw"])
        assert fila["debe_cambiar_clave"] == 0
    assert sorted(a["entidad"] for a in auditoria) == ["Admin", "Ingeniero"]
    texto = json.dumps(auditoria, ensure_ascii=False)
    assert "admin-nueva-1" not in texto and "inge-nueva-1" not in texto


def test_si_el_guardado_falla_no_termina(entorno):
    def falla():
        raise OSError("disco lleno")
    p = _puente(entorno, abrir_bd=falla)
    r = p.instalar(_datos(contrasenas=VALIDAS))
    assert r["ok"] is False and "disco lleno" in r["error"]
    assert not storage.INSTALLATION_FILE.exists()


def test_fijar_es_todo_o_nada(tmp_path):
    db = DbManager(tmp_path / "autoclave.db")
    antes = db.get_usuario_by_username("Admin")["hash_pw"]
    with pytest.raises(RuntimeError):
        db.fijar_claves_instalacion({"admin": "pbkdf2$1000$00$00", "rol_inexistente": "x"})
    fila = db.get_usuario_by_username("Admin")
    assert fila["hash_pw"] == antes and fila["debe_cambiar_clave"] == 1
    assert db.get_auditoria(evento="contrasena_fijada_instalacion") == []
    db.close()


def test_reinstalacion_tambien_exige_y_fija(entorno):
    db = DbManager(entorno / "autoclave.db")
    from autoclave.backend.contrasenas import hash_password
    db.actualizar_password("Admin", hash_password("ya-cambiada-1", iteraciones=1000))
    db.close()
    p = _puente(entorno)
    assert p.instalar(_datos())["ok"] is False
    assert p.instalar(_datos(contrasenas=VALIDAS))["ok"] is True
    fila, _ = _cuenta(entorno / "autoclave.db", "Admin")
    assert verificar_password("admin-nueva-1", fila["hash_pw"])


def test_el_paso_esta_en_el_asistente_antes_del_resumen():
    qml = (RAIZ / "src/autoclave/ui_qml/qml/Pantallas/Instalacion.qml").read_text(encoding="utf-8")
    assert 'p.push("vapor", "datos", "contrasenas", "resumen")' in qml
    assert 'paso === "contrasenas"' in qml and "puente.validarContrasenas(" in qml
    assert "contrasenas: { clave_admin:" in qml


def test_db_manager_no_dice_las_semillas_en_claro():
    fuente = (RAIZ / "src/autoclave/services/domain/logging/db_manager.py").read_text(encoding="utf-8")
    assert SEMILLA_ADMIN not in fuente and SEMILLA_INGENIERO not in fuente


# ── SIS-07 en equipos ya instalados ──────────────────────────────────────────

class _Ctx:
    def __init__(self, db):
        self.db = db
        self.alarm_manager = AlarmManager()


def _activas(am):
    return [i for i in am.activas() if i.codigo == CONTRASENA_SEMILLA]


def test_sis07_con_semilla_y_se_despeja_al_cambiar(tmp_path):
    from autoclave.backend.context import BackendContext
    from autoclave.backend.contrasenas import hash_password
    db = DbManager(tmp_path / "autoclave.db")
    ctx = _Ctx(db)
    assert db.cuentas_con_clave_semilla() == ["Admin", "Ingeniero"]
    BackendContext.revisar_contrasenas_semilla(ctx)
    activas = _activas(ctx.alarm_manager)
    assert len(activas) == 1 and "Admin, Ingeniero" in activas[0].descripcion
    db.actualizar_password("Admin", hash_password("nueva-admin-1", iteraciones=1000))
    BackendContext.revisar_contrasenas_semilla(ctx)
    assert "Ingeniero" in _activas(ctx.alarm_manager)[0].descripcion
    db.actualizar_password("Ingeniero", hash_password("nueva-inge-1", iteraciones=1000))
    BackendContext.revisar_contrasenas_semilla(ctx)
    assert _activas(ctx.alarm_manager) == []
    db.close()


def test_sis07_sin_aviso_tras_la_instalacion(tmp_path):
    from autoclave.backend.context import BackendContext
    db = DbManager(tmp_path / "autoclave.db")
    db.fijar_claves_instalacion({"admin": "pbkdf2$1000$00$00", "ingeniero": "pbkdf2$1000$01$01"})
    ctx = _Ctx(db)
    BackendContext.revisar_contrasenas_semilla(ctx)
    assert _activas(ctx.alarm_manager) == []
    db.close()


def test_sis07_nunca_lanza_sin_base():
    from autoclave.backend.context import BackendContext
    from autoclave.backend.arranque.sin_bd import BdNoDisponible
    ctx = _Ctx(BdNoDisponible())
    BackendContext.revisar_contrasenas_semilla(ctx)
    assert _activas(ctx.alarm_manager) == []


def test_sis07_no_bloqueante_y_solo_tecnico_e_ingeniero():
    d = CATALOGO[CONTRASENA_SEMILLA]
    assert d.bloquea_inicio is False and d.nivel.name == "AVISO"
    assert ROLES_VISIBLES[CONTRASENA_SEMILLA] == {"tecnico", "ingeniero"}
    from autoclave import i18n
    for idioma in ("es", "en"):
        assert i18n.t("alarmas.SIS-07.titulo", idioma) != "alarmas.SIS-07.titulo"


def test_dto_lleva_los_roles_visibles():
    from autoclave.backend import server
    am = AlarmManager()
    inst = am.activar(CONTRASENA_SEMILLA, cuentas="Admin")
    assert server._alarma_dto(inst)["roles_visibles"] == ["ingeniero", "tecnico"]


@pytest.mark.parametrize("rol, visible", [
    (None, False), ("operador", False), ("admin", False), ("tecnico", True), ("ingeniero", True)])
def test_bandeja_y_campana_filtran_por_rol(rol, visible):
    from autoclave.ui_qml.bridge.ui_bridge import visibles_para_rol
    alarmas = [{"id": "SIS-07", "roles_visibles": ["ingeniero", "tecnico"]},
               {"id": "SUM-01", "roles_visibles": []}, {"id": "PRE-01"}]
    ids = [a["id"] for a in visibles_para_rol(alarmas, rol)]
    assert ids == (["SIS-07", "SUM-01", "PRE-01"] if visible else ["SUM-01", "PRE-01"])

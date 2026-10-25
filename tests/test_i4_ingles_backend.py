"""I4 (tanda 6): inglés del backend y de las salidas.

Motivos de puerta con código + parámetros, motivo_fallo con parámetros en la
BD, nombre_clave de los ciclos de fábrica, etiquetas de roles y enums,
textos que Python entrega a QML, PDF con unidades, tickets de resumen,
arranque y conectividad en es/en y cp437 (I18N-18)."""

import json
import re
import string
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autoclave import i18n
from autoclave.core.runtime import alarmas_i18n, camara_segura, motivos
from autoclave.core.runtime.motivos import Motivo
from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.alarms.catalogo import CATALOGO

RAIZ = Path(__file__).resolve().parents[1]
SRC = RAIZ / "src" / "autoclave"


def _cat(lang):
    return json.loads((SRC / f"i18n/{lang}.json").read_text(encoding="utf-8"))


def _campos(texto):
    return {c for _, c, _, _ in string.Formatter().parse(texto) if c}


# ── Alarmas: cada código se dispara y tiene texto en es y en ──────────────

def _valores(d):
    ejemplo = {"pres": 210.0, "minimo": 100.0, "maximo": 200.0, "objetivo": 150.0, "rango": 10.0,
               "temp": 90.5, "minutos": 12.0, "segundos": 5.0,
               # E12 (tanda 12): CIC-12/CIC-13 (saturación, K y °C con decimales)
               "tsat": 137.0, "dt": 2.5}
    return {c: ejemplo.get(c, "X") for c in d.campos()}


@pytest.mark.parametrize("codigo", sorted(CATALOGO))
def test_cada_alarma_se_dispara_y_tiene_texto_es_en(codigo):
    am = AlarmManager()
    d = CATALOGO[codigo]
    inst = am.activar(codigo, "prueba", **_valores(d))
    assert inst.codigo == codigo
    textos = alarmas_i18n.por_idioma(d, _valores(d))
    for idioma in ("es", "en"):
        for campo in ("titulo", "descripcion", "accion"):
            assert textos[idioma][campo].strip(), (codigo, idioma, campo)
            assert "{" not in textos[idioma][campo], (codigo, idioma, campo)


# ── Motivos de puerta ─────────────────────────────────────────────────────

@pytest.mark.parametrize("codigo", motivos.CODIGOS + ("error_comunicacion",))
def test_cada_motivo_de_puerta_tiene_texto_es_en_con_mismos_campos(codigo):
    es, en = _cat("es")["puerta"].get(codigo), _cat("en")["puerta"].get(codigo)
    assert isinstance(es, str) and es.strip() and isinstance(en, str) and en.strip(), codigo
    assert _campos(es) == _campos(en), codigo


def test_los_codigos_usados_en_el_codigo_estan_declarados():
    usados = set()
    for ruta in (SRC / "services/domain/puertas/ser_puertas.py", SRC / "core/runtime/camara_segura.py",
                 SRC / "devices/puertas/advanced_door.py", SRC / "backend/server.py"):
        usados |= set(re.findall(r'Motivo\(\s*"([a-z_]+)"', ruta.read_text(encoding="utf-8")))
    assert usados and usados <= set(motivos.CODIGOS)
    assert set(motivos.CODIGOS) <= usados


def test_motivo_es_el_mismo_texto_en_espanol():
    m = Motivo("camara_presurizada", "Cámara presurizada (250 kPa)", pres=250.0)
    assert m == "Cámara presurizada (250 kPa)" and isinstance(m, str)
    assert f"x {m}" == "x Cámara presurizada (250 kPa)"
    assert motivos.texto(m, "en") == "Chamber pressurized (250.0 kPa)"
    assert motivos.texto("texto libre", "en") == "texto libre"


class _Estado:
    def __init__(self, pres=75.0, temp=40.0):
        self.sensores_pres = {"pres_camara": pres}
        self.sensores_temp = {"temp_camara": temp}


CONFIG = {"presion_admosferica": 75.0, "rango_presion_atm": 5.0, "temp_max_apertura": 80.0}


@pytest.mark.parametrize("estado,vigentes,config,codigo", [
    (_Estado(), False, CONFIG, "sin_datos_vigentes"),
    (_Estado(), True, {}, "falta_config"),
    (_Estado(pres=None), True, CONFIG, "sin_presion_camara"),
    (_Estado(temp=None), True, CONFIG, "sin_temp_camara"),
    (_Estado(pres=200.0), True, CONFIG, "sobrepresion"),
    (_Estado(pres=20.0), True, CONFIG, "vacio"),
    (_Estado(temp=95.0), True, CONFIG, "temp_alta"),
])
def test_camara_segura_dispara_cada_motivo_con_codigo(estado, vigentes, config, codigo):
    segura, motivo = camara_segura.evaluar(estado, config, None, datos_vigentes=vigentes)
    assert segura is False and motivos.codigo_de(motivo) == codigo
    textos = motivos.por_idioma(motivo, "F", "psi", 75.0)
    assert textos["es"].strip() and textos["en"].strip() and "{" not in textos["en"]


def test_motivo_en_unidades_vigentes():
    _, m = camara_segura.evaluar(_Estado(temp=95.0), CONFIG, None)
    assert motivos.texto(m, "en", "F") == "Temperature too high (203.0 °F)"
    _, m = camara_segura.evaluar(_Estado(pres=200.0), CONFIG, None)
    assert motivos.texto(m, "en", "C", "psi", 75.0) == "Chamber overpressure (18.1 psig)"
    # sin P_atm en psi: nunca un número inventado
    assert motivos.texto(m, "en", "C", "psi", None) == "Chamber overpressure (—)"


def test_servicio_puertas_dispara_motivos_con_codigo():
    from tests.test_servicio_puertas import CONFIG as CFG, Estado, _avanzada
    from autoclave.devices.puertas.enum_doors import DoorState
    from autoclave.services.domain.puertas.ser_puertas import ServicioPuertas
    est = Estado()
    p1 = _avanzada("Puerta 1", est, di={"bloqueo": "bloqueo_1"})
    p2 = _avanzada("Puerta 2", est)
    est.puertas = {"Puerta 1": DoorState.CERRADO, "Puerta 2": DoorState.ABIERTO}
    s = ServicioPuertas([p1, p2], est, MagicMock(), dict(CFG))
    vistos = {}
    vistos["desconocida"] = s.request_open("Puerta 9")[1]
    vistos["otra_puerta_abierta"] = s.request_open("Puerta 1")[1]
    vistos["ya_cerrada"] = s.request_close("Puerta 1")[1]
    est.puertas["Puerta 2"] = DoorState.CERRADO
    est.sensores_di["bloqueo_1"] = True
    vistos["bloqueada"] = s.request_open("Puerta 1")[1]
    est.flags["PARO_EMERGENCIA"] = True
    vistos["paro"] = s.request_open("Puerta 1")[1]
    est.flags["PARO_EMERGENCIA"] = False
    est.puertas["Puerta 1"] = DoorState.ABIERTO
    est.sensores_pres["pres_camara"] = 300.0
    vistos["camara_presurizada"] = s.request_close("Puerta 1")[1]
    for codigo, m in vistos.items():
        assert motivos.codigo_de(m) == codigo, (codigo, m)
        assert motivos.por_idioma(m)["en"] != "", codigo


def test_comando_de_puerta_usa_el_texto_del_idioma_vigente():
    import requests
    from autoclave.services.domain.puertas.door_command_service import DoorCommandService
    resp = MagicMock()
    resp.json.return_value = {"detail": "Puerta bloqueada mecánicamente", "codigo": "puerta_rechazada",
                              "motivo_textos": {"es": "Puerta bloqueada mecánicamente",
                                                "en": "Door mechanically locked"}}
    backend = MagicMock()
    backend.post.side_effect = requests.exceptions.HTTPError(response=resp)
    antes = i18n.idioma()
    try:
        i18n.fijar_idioma("en")
        assert DoorCommandService(backend, 1).open("Puerta 1") == (False, "Door mechanically locked")
    finally:
        i18n.fijar_idioma(antes)


# ── motivo_fallo con parámetros en la BD ──────────────────────────────────

def test_cerrar_ciclo_guarda_los_parametros_y_se_presentan_en_ingles(tmp_path):
    from autoclave.services.domain.logging.db_manager import DbManager
    db = DbManager(db_path=tmp_path / "t.db")
    columnas = {f[1] for f in db._conn.execute("PRAGMA table_info(ciclos)")}
    assert "valores_fallo" in columnas
    cid = db._conn.execute("INSERT INTO ciclos (numero_ciclo, fecha_inicio) VALUES (1, '2026-10-21T10:00:00')").lastrowid
    codigo = next(c for c, d in CATALOGO.items() if "temp" in d.campos())
    valores = {c: 133.8 for c in CATALOGO[codigo].campos()}
    db.cerrar_ciclo(cid, "FALLO", "texto es", codigo, valores_fallo=valores)
    fila = db._conn.execute("SELECT motivo_fallo, codigo_fallo, valores_fallo FROM ciclos WHERE id=?",
                            (cid,)).fetchone()
    assert fila[0] == "texto es" and fila[1] == codigo and json.loads(fila[2]) == valores
    en = alarmas_i18n.motivo_fallo(fila[1], fila[2], fila[0], "en")
    assert en.startswith(f"{codigo} · ") and "133.8" in en
    assert en != alarmas_i18n.motivo_fallo(fila[1], fila[2], fila[0], "es")
    assert alarmas_i18n.motivo_fallo(fila[1], fila[2], fila[0], "es").startswith(codigo)


def test_sin_parametros_y_ciclos_antiguos():
    assert alarmas_i18n.motivo_fallo("", "", "Motivo viejo", "en") == "Motivo viejo"
    assert alarmas_i18n.motivo_fallo(None, None, None, "en") is None
    codigo = sorted(CATALOGO)[0]
    assert alarmas_i18n.motivo_fallo(codigo, "", "guardado", "es") == "guardado"
    assert alarmas_i18n.motivo_fallo(codigo, "{roto", "guardado", "en") == "guardado"


def test_migracion_v7_sobre_base_v6(tmp_path):
    import sqlite3
    from autoclave.services.domain.logging import db_manager
    from autoclave.services.domain.logging.db_manager import DbManager
    DbManager(db_path=tmp_path / "t.db")._conn.close()
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("PRAGMA user_version = 6")
    conn.commit()
    conn.close()
    db = DbManager(db_path=tmp_path / "t.db")
    assert db.get_version_esquema() == db_manager.ESQUEMA_VERSION == 11   # v11: U11 (cuentas del sistema)


def test_registrar_fallo_deja_los_valores_en_el_estado():
    from autoclave.state_machine.states.ciclo import CicloState
    estado = MagicMock()
    inst = MagicMock(codigo="CIC-01", titulo="t", descripcion="d")
    obj = CicloState.__new__(CicloState)
    obj.estado = estado
    obj.alarm_manager = MagicMock()
    obj.alarm_manager.activar.return_value = inst
    obj._registrar_fallo("CIC-01", "x", temp=float("nan"), pres=210.0)
    assert estado.valores_fallo == {"temp": None, "pres": 210.0}


# ── nombre_clave, roles y enums ───────────────────────────────────────────

def test_ciclos_de_fabrica_tienen_nombre_clave_con_texto_es_en():
    for ruta in (SRC / "cycles/factory").glob("*.json"):
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        clave = datos.get("nombre_clave")
        assert clave == f"ciclos_fabrica.{datos['cycle_id']}.nombre", ruta.name
        for lang in ("es", "en"):
            assert i18n.existe(clave, lang)


def test_nombres_de_resuelve_por_cycle_id_si_no_se_renombro():
    from autoclave.core.managers.cycle_manager import Cycle, CycleManager
    cm = CycleManager.__new__(CycleManager)
    fab = Cycle("liquidos", "Líquidos", {}, 4)
    fab.nombre_clave = "ciclos_fabrica.liquidos.nombre"
    cm.fabrica = {4: fab}
    usuario = Cycle("liquidos", "Líquidos", {}, 4)
    assert cm.nombres_de(usuario) == {"es": "Líquidos", "en": "Liquids"}
    renombrado = Cycle("liquidos", "Mis líquidos", {}, 4)
    assert cm.nombres_de(renombrado) == {"es": "Mis líquidos", "en": "Mis líquidos"}


def test_etiqueta_de_rol_por_catalogo():
    from autoclave.auth.roles import ROLES, etiqueta_rol
    for valor, _ in ROLES:
        assert i18n.existe(f"roles.{valor}", "en")
    assert etiqueta_rol("tecnico", idioma="en") == "Technician"
    assert etiqueta_rol("tecnico", idioma="es") == "Técnico"
    assert etiqueta_rol("desconocido", idioma="en") == "desconocido"


def test_enums_del_panel_de_informacion_tienen_etiqueta():
    from autoclave.devices.puertas.door_type import DoorType
    from autoclave.installation.equipment import EquipmentClass
    from autoclave.ui_qml.bridge.info_equipo import _fila_enum
    for enum, prefijo, clave in ((EquipmentClass, "clase_", "clase"), (DoorType, "tipo_puerta_", "tipo_puerta")):
        for v in enum:
            fila = _fila_enum(clave, prefijo, v)
            assert fila["valor"] == v.value and fila["valorClave"] == f"{prefijo}{v.value}"
            for lang in ("es", "en"):
                assert i18n.existe(f"equipo.{fila['valorClave']}", lang)
    assert "valorClave" not in _fila_enum("clase", "clase_", None)


def test_rotulo_de_periodo_en_ingles():
    from autoclave.ui_qml.domain.resumen_sistema import rotulo_periodo
    d = date(2026, 10, 6)
    assert rotulo_periodo("dia", d, "es") == "Martes 6 oct 2026"
    assert rotulo_periodo("dia", d, "en") == "Tuesday 6 Oct 2026"
    assert rotulo_periodo("mes", d, "en") == "October 2026"


# ── PDF con unidades ──────────────────────────────────────────────────────

def test_grafica_y_consigna_del_pdf_en_unidades():
    from autoclave.ui_qml.exportacion import unidades_pdf as up
    datos = {"t_min": [0, 1], "temp_camara": [100.0, None], "temp_ref": [], "pres_camara": [75.0, 175.0]}
    assert up.grafica(datos, "C", "kPa", None) is datos
    g = up.grafica(datos, "F", "psi", 75.0)
    assert g["temp_camara"] == [212.0, None]
    assert g["pres_camara"][0] == 0.0 and abs(g["pres_camara"][1] - 100 / 6.894757) < 1e-9
    assert up.grafica(datos, "C", "psi", None)["pres_camara"] == [None, None]
    assert up.grafica(datos, "C", "bar", None)["pres_camara"] == [0.75, 1.75]
    c = {"temp": 134.0, "pres": 304.0, "desde_min": 1, "hasta_min": 2}
    assert up.consigna(c, "C", "psi", None) is None
    assert up.consigna(c, "F", "kPa", None)["temp"] == pytest.approx(273.2)
    assert up.textos_ejes({"eje_temp": "°C"}, "F", "psi") == {"eje_temp": "°F", "eje_pres": "psig"}
    assert up.rotulo_unidades("C", "kPa") == "°C, kPa abs"
    assert up.rotulo_unidades("F", "psi") == "°F, psig"


def test_datos_del_pdf_llevan_unidades_y_motivo_en_el_idioma_vigente():
    from autoclave.services.domain.logging.ticket_formatter import Presentacion
    from autoclave.ui_qml.bridge.acciones_ciclos import AccionesCiclos
    codigo = sorted(CATALOGO)[0]
    ciclo = {"id": 1, "numero_ciclo": 7, "fecha_inicio": "2026-10-21T10:00:00",
             "fecha_fin": "2026-10-21T11:00:00", "nombre_ciclo": "X", "resultado": "FALLO",
             "codigo_fallo": codigo, "motivo_fallo": "es", "valores_fallo": "",
             "modelo": "M", "serie": "S"}
    antes = i18n.idioma()
    try:
        i18n.fijar_idioma("en")
        datos = AccionesCiclos._datos_pdf(MagicMock(_campo_motivo=AccionesCiclos._campo_motivo),
                                          ciclo, Presentacion("en", "F", "psi", 75.0))
    finally:
        i18n.fijar_idioma(antes)
    campos = dict(datos["campos"])
    assert campos["Units"] == "°F, psig"
    assert campos["Reason"].startswith(codigo)


# ── Tickets: arranque (I18N-18), conectividad y resumen; cp437 ────────────

def _perfil():
    from autoclave.installation.equipment import EquipmentClass
    p = MagicMock()
    p.model_id, p.serial_number, p.equipment_class = "MESA_B", "S-1", EquipmentClass.MESA_B
    return p


def test_ticket_de_arranque_decide_por_codigo_no_por_texto():
    from autoclave.devices.printer.startup_ticket import FALLO, OK, SIN_DATOS, format_startup_ticket
    t = datetime(2026, 10, 21, 8, 0, 0)
    ok = format_startup_ticket(_perfil(), "1", None, t, [("backend", OK), ("tarjeta", OK)], idioma="en")
    assert "System ready" in ok and "Control board:" in ok and "First power-on" in ok
    mal = format_startup_ticket(_perfil(), "1", t, t, [("backend", OK), ("tarjeta", SIN_DATOS)],
                                idioma="en")
    assert "STARTUP FAILURE" in mal and "No data" in mal
    es = format_startup_ticket(_perfil(), "1", t, t, [("backend", FALLO), ("tarjeta", OK)], idioma="es")
    assert "FALLO EN ARRANQUE" in es and "Tarjeta:" in es
    # legado: los textos antiguos siguen funcionando; uno desconocido es fallo
    assert "Sistema listo" in format_startup_ticket(_perfil(), "1", t, t, [("Backend", "OK")], idioma="es")
    assert "FALLO EN ARRANQUE" in format_startup_ticket(_perfil(), "1", t, t, [("X", "raro")], idioma="es")


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_tickets_en_cp437(idioma):
    from autoclave.devices.printer.connectivity_ticket import format_connectivity_ticket
    from autoclave.devices.printer.startup_ticket import FALLO, OK, format_startup_ticket
    from autoclave.services.domain.reportes.resumen_periodo import format_ticket_resumen
    t = datetime(2026, 10, 21, 8, 0, 0)
    textos = [format_startup_ticket(_perfil(), "1", t, t, [("backend", OK), ("tarjeta", FALLO)],
                                    idioma=idioma)]
    textos += [format_connectivity_ticket(s, ok, t, idioma=idioma)
               for s in ("TARJETA", "BACKEND") for ok in (True, False)]
    resumen = {"totales": {"total": 2, "completados": 1, "fallos": 1, "cancelados": 0, "sin_cierre": 0},
               "por_programa": [{"programa_numero": 1, "programa_nombre": "Bowe & Dick", "total": 2,
                                 "completados": 1, "fallos": 1, "cancelados": 0, "sin_cierre": 0}],
               "causas_fallo": [{"causa": "FALLO", "cantidad": 1}]}
    textos.append(format_ticket_resumen(resumen, "2026-10-01", "2026-10-31", "S-1", "M", ahora=t,
                                        idioma=idioma))
    for texto in textos:
        texto.encode("cp437")
        assert all(len(l) <= 48 for l in texto.split("\n"))
    if idioma == "en":
        assert "BOARD: DISCONNECTED" in textos[2] or "BOARD: DISCONNECTED" in "".join(textos)
        assert "CYCLE SUMMARY" in textos[-1] and "Completed: 1 (50%)" in textos[-1]
    else:
        assert "RESUMEN DE CICLOS" in textos[-1] and "TARJETA: DESCONECTADA" in "".join(textos)


def test_resumen_conserva_24_columnas():
    from autoclave.services.domain.reportes.resumen_periodo import format_ticket_resumen
    resumen = {"totales": {"total": 0, "completados": 0, "fallos": 0, "cancelados": 0, "sin_cierre": 0},
               "por_programa": [], "causas_fallo": []}
    for idioma in ("es", "en"):
        texto = format_ticket_resumen(resumen, "2026-10-01", "2026-10-31", "S", "M",
                                      ahora=datetime(2026, 10, 21), idioma=idioma)
        assert all(len(l) <= 24 for l in texto.split("\n")), idioma

"""T29-07 (tanda 29): con F0 activo, el encabezado del ticket dice «F0 activo ·
objetivo {F0_objetivo} min» (al final ya va «F0 total»), en vivo, en la
reimpresión y en el PDF y el correo (que embeben format_ticket). Sin F0 activo
el ticket queda idéntico al anterior."""

import json

from autoclave import i18n
from autoclave.installation.equipment import EquipmentClass
from autoclave.services.domain.logging import ticket_formatter as tf
from autoclave.state_machine.machine.enum_global import GlobalState
from tests.test_cycle_logger_printer import (FakeCycle, FakeCycleManager, FakePrinter,
                                             _build_logger)

ES = tf.Presentacion(idioma="es")
EN = tf.Presentacion(idioma="en")


def _ciclo(**extra):
    base = {
        "numero_ciclo": 12, "serie": "SN260001", "modelo": "SPK-SAT 2000H2-LAB",
        "version_sw": "1.0.0", "nombre_ciclo": "Líquidos", "tipo_ciclo": "liquidos",
        "temp_esterilizacion": 121, "tiempo_esterilizacion": 15,
        "fecha_inicio": "2026-11-06T10:00:00", "fecha_fin": "2026-11-06T11:00:00",
        "resultado": "COMPLETADO",
    }
    base.update(extra)
    return base


def _programa_json(objetivo):
    return json.dumps({"cycle_id": "liquidos", "parameters": {
        "globals": {"F0": {"value": True}, "F0_objetivo": {"value": objetivo}}}})


# ── i18n ────────────────────────────────────────────────────────────────

def test_claves_es_en():
    assert i18n.t("ticket_ciclo.f0_activo", "es", objetivo=12) == "F0 activo · objetivo 12 min"
    assert i18n.t("ticket_ciclo.f0_activo", "en", objetivo=12) == "F0 active · target 12 min"


# ── encabezado ──────────────────────────────────────────────────────────

def test_encabezado_sin_f0_identico():
    meta = _ciclo()
    assert tf.format_header(meta, ES) == tf.format_header({**meta, "f0_activo": False}, ES)
    assert "F0" not in tf.format_header(meta, ES)


def test_encabezado_con_f0_activo():
    texto = tf.format_header({**_ciclo(), "f0_activo": True, "f0_objetivo": 12.0}, ES)
    assert "F0 activo · objetivo 12 min" in texto
    texto = tf.format_header({**_ciclo(), "f0_activo": True, "f0_objetivo": 12.5}, EN)
    assert "F0 active · target 12.5 min" in texto


def test_encabezado_con_f0_y_objetivo_ilegible():
    texto = tf.format_header({**_ciclo(), "f0_activo": True, "f0_objetivo": None}, ES)
    assert "F0 activo · objetivo --- min" in texto


# ── reimpresión (también el PDF y el correo: format_ticket) ─────────────

def test_reimpresion_sin_f0_identica():
    sin = tf.format_ticket(_ciclo(), [], ES)
    con_json_sin_f0 = tf.format_ticket(_ciclo(programa_json=_programa_json(12), f0_final=None), [], ES)
    assert sin == con_json_sin_f0
    assert "F0" not in sin


def test_reimpresion_con_f0():
    texto = tf.format_ticket(_ciclo(programa_json=_programa_json(18), f0_final=20.4), [], ES)
    assert "F0 activo · objetivo 18 min" in texto
    assert "F0 total: 20.4 min" in texto
    # el objetivo en el encabezado, el total en el pie
    assert texto.index("F0 activo") < texto.index("F0 total")


def test_reimpresion_con_f0_sin_instantanea():
    texto = tf.format_ticket(_ciclo(f0_final=20.4), [], ES)
    assert "F0 activo · objetivo --- min" in texto


def test_objetivo_de_programa():
    assert tf.f0_objetivo_de_programa(_programa_json(12)) == 12.0
    assert tf.f0_objetivo_de_programa(json.loads(_programa_json(7))) == 7.0
    assert tf.f0_objetivo_de_programa("no json") is None
    assert tf.f0_objetivo_de_programa(None) is None


# ── ticket en vivo (CycleLogger) ───────────────────────────────────────

class _CicloF0(FakeCycle):
    def get_param(self, *keys, default=None):
        if keys == ("globals", "F0_objetivo"):
            return 12
        return super().get_param(*keys, default=default)


class _GestorF0(FakeCycleManager):
    def get_selected_cycle(self):
        return _CicloF0(f0_activo=self.f0_activo)


def _ticket_en_vivo(f0_activo, clase=EquipmentClass.PISO_LAB):
    printer = FakePrinter()
    cl = _build_logger(printer, cycle_manager=_GestorF0(f0_activo=f0_activo))
    cl.profile.equipment_class = clase
    cl.estado.f0_acumulado = 15.3
    cl.update()                                  # encabezado
    cl.update()                                  # fila
    cl.estado.machine_state = GlobalState.PREPARADO
    cl.update()                                  # pie
    return printer.calls


def test_en_vivo_con_f0_encabezado_y_pie():
    llamadas = _ticket_en_vivo(True)
    assert "F0 activo · objetivo 12 min" in llamadas[0]
    assert "F0 total: 15.3 min" in llamadas[3]


def test_en_vivo_sin_f0_encabezado_sin_linea():
    assert all("F0" not in t for t in _ticket_en_vivo(False))


def test_en_vivo_f0_en_equipo_no_lab_sin_linea():
    assert all("F0" not in t for t in _ticket_en_vivo(True, EquipmentClass.PISO))

"""X9 (tanda 9), D9-13.4: con la interfaz en inglés, el ticket, la
reimpresión y los motivos de fallo de las fases salen en el idioma vigente
(catálogo es/en, claves + parámetros, D-25)."""

import json
import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autoclave import i18n
from autoclave.core.runtime import alarmas_i18n, motivos_fase
from autoclave.services.domain.logging import ticket_formatter as tf
from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.cycle_phases.base_fase import FaseResult
from autoclave.state_machine.states.ciclo import CicloState

RAIZ = Path(__file__).resolve().parents[1]
ES = tf.Presentacion("es", "C", "kPa")
EN = tf.Presentacion("en", "C", "kPa")
EN_F = tf.Presentacion("en", "F", "psi", 101.3)
_ESPANOL = re.compile(r"[áéíóúñÁÉÍÓÚÑ¿¡]|\b(de|del|la|el|sin|tiempo|presión|temperatura|"
                      r"vacío|secado|modo|fallo|puerta|ciclo)\b", re.IGNORECASE)


def _catalogo(lang):
    return json.loads((RAIZ / "src" / "autoclave" / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))


# ── Catálogo ────────────────────────────────────────────────────────────────

def test_todo_motivo_de_fase_tiene_texto_es_en_con_los_mismos_campos():
    es, en = _catalogo("es")["motivos_fase"], _catalogo("en")["motivos_fase"]
    for codigo in motivos_fase.CODIGOS:
        assert es[codigo] and en[codigo], codigo
        assert set(re.findall(r"\{(\w+)\}", es[codigo])) == set(re.findall(r"\{(\w+)\}", en[codigo]))
    assert set(es["etapa"]) == set(en["etapa"])


def test_rotulos_del_ticket_es_en_con_las_mismas_claves():
    es, en = _catalogo("es")["ticket_ciclo"], _catalogo("en")["ticket_ciclo"]

    def claves(d, p=""):
        return {p + k if not isinstance(v, dict) else x for k, v in d.items()
                for x in (claves(v, p + k + ".") if isinstance(v, dict) else [p + k])}
    assert claves(es) == claves(en)


def test_ticket_en_cp437():
    """El ticket térmico se imprime en cp437."""
    for lang in ("es", "en"):
        for k, v in _catalogo(lang)["ticket_ciclo"].items():
            for texto in (v.values() if isinstance(v, dict) else [v]):
                texto.encode("cp437")


# ── Motivos de fallo de las fases ──────────────────────────────────────────

def test_motivo_es_texto_en_espanol_con_codigo_y_valores():
    m = motivos_fase.motivo("est_temp_alta", temp=140.04, temp_limite=137.0)
    assert isinstance(m, str) and m.startswith("Temperatura alta:")
    assert "140.0 °C" in m and "137.0 °C" in m
    assert m.codigo == "est_temp_alta" and m.valores["temp"] == 140.04


def test_motivo_en_ingles_y_otras_unidades_desde_los_valores_de_la_alarma():
    m = motivos_fase.motivo("est_pres_baja", pres=300.0, pres_limite=302.0)
    valores = motivos_fase.a_valores(m)
    en = motivos_fase.texto_desde_valores(valores, "en")
    assert en.startswith("Low pressure:") and "300.0 kPa" in en
    en_psi = motivos_fase.texto_desde_valores(valores, "en", "F", "psi", 101.3)
    assert "kPa" not in en_psi and "psi" in en_psi


def test_motivo_de_descompresion_con_etapa_y_sin_lectura():
    m = motivos_fase.motivo("desc_tiempo_limite", clave_etapa="motivos_fase.etapa.enfriamiento",
                            modo=4, temp=None, pres=250.0)
    assert "Tiempo límite de enfriamiento del modo 4" in m
    en = motivos_fase.texto_desde_valores(motivos_fase.a_valores(m), "en")
    assert en.startswith("Cooling time limit in mode 4") and "T=—" in en
    assert not _ESPANOL.search(en), en


@pytest.mark.parametrize("codigo,valores", [
    ("cal_tiempo_limite", {"minutos": "60"}),
    ("cal_tiempo_limite_sostenimiento", {"minutos": "60", "segundos": "12"}),
    ("cal_no_sostuvo", {"minutos": "5"}),
    ("est_comunicacion", {"segundos": "40", "maximo": "30"}),
    ("est_temp_baja", {"temp": 133.8, "temp_limite": 133.9}),
    ("est_timeout_f0", {"minutos": "7", "f0": "3.10", "f0_objetivo": "12.0"}),
    ("sec_vacio_perdido", {"modo": 1, "pres": 95.0, "pres_umbral": 90.0}),
    ("sec_sin_vacio", {"modo": 2, "pres_umbral": 90.0}),
    ("sec_termino_sin_vacio", {"modo": 1}),
    ("sec_modo3_vacio_bajo", {}),
    ("sec_modo3_aire_alto", {}),
])
def test_cada_motivo_en_ingles_sin_espanol(codigo, valores):
    m = motivos_fase.motivo(codigo, **valores)
    en = motivos_fase.texto_desde_valores(motivos_fase.a_valores(m), "en")
    assert en and "{" not in en and not _ESPANOL.search(en), en
    assert "{" not in m


def _ciclo():
    estado = MagicMock()
    estado.sensores_temp = {"temp_camara": 100.0}
    estado.sensores_pres = {"pres_camara": 200.0, "pres_chaqueta": 300.0,
                            "pres_empaque_1": 300.0, "pres_empaque_2": 300.0}
    estado.sensores_di = {"puerta_1_cerrada": 1, "puerta_2_cerrada": 1, "vapor_suministro": 1}
    estado.get_flag.side_effect = lambda f: False
    cycle = MagicMock(); cycle.get_param.return_value = None
    cycle.copia.return_value = cycle
    config = MagicMock(); config.get.return_value = None
    am = AlarmManager()
    ciclo = CicloState(estado, MagicMock(), cycle, config, am)
    ciclo.reset()
    ciclo._protocolo = MagicMock()
    return ciclo, estado, am


def test_la_alarma_y_el_historial_muestran_el_motivo_en_el_idioma_vigente():
    ciclo, estado, am = _ciclo()

    def falla():
        estado.motivo_fallo = motivos_fase.motivo("est_temp_alta", temp=140.0, temp_limite=137.0)
        return FaseResult.FALLO
    ciclo._fases[0].update = falla
    ciclo.run()
    [inst] = am.activas()
    # el texto en español (log, base) no cambia de forma
    assert "Temperatura alta: 140.0 °C > 137.0 °C" in estado.motivo_fallo
    textos = alarmas_i18n.por_idioma(inst.definicion, inst.valores)
    assert textos["en"]["descripcion"].startswith("High temperature: 140.0 °C")
    assert textos["es"]["descripcion"].startswith("Temperatura alta: 140.0 °C")
    # Historial / PDF / reimpresión: desde ciclos.valores_fallo (JSON)
    guardado = json.dumps(estado.valores_fallo)
    en = alarmas_i18n.motivo_fallo(estado.codigo_fallo, guardado, str(estado.motivo_fallo), "en")
    assert en.startswith("CIC-01 · Preheating failure: High temperature") and not _ESPANOL.search(
        en.split(":", 1)[1]), en


def test_motivo_de_texto_libre_sigue_igual():
    """Un motivo sin clave (ciclos anteriores, otras rutas) no cambia."""
    ciclo, estado, am = _ciclo()

    def falla():
        estado.motivo_fallo = "Motivo antiguo"
        return FaseResult.FALLO
    ciclo._fases[0].update = falla
    ciclo.run()
    assert "motivo_codigo" not in am.activas()[0].valores
    assert estado.motivo_fallo.endswith("Motivo antiguo")


def test_las_fases_usan_motivos_con_clave():
    """Ningún _fallo de las fases arma el motivo con texto suelto."""
    base = RAIZ / "src" / "autoclave" / "state_machine" / "cycle_phases"
    for nombre in ("calentamiento.py", "esterilizacion.py", "secado.py", "descompresion.py"):
        fuente = (base / nombre).read_text(encoding="utf-8")
        assert not re.search(r'_fallo\(\s*f?"', fuente), nombre
        assert not re.search(r'motivo_fallo\s*=\s*\(?\s*f?"', fuente), nombre


# ── Ticket ─────────────────────────────────────────────────────────────────

_CICLO = {"numero_ciclo": 12, "serie": "S1", "modelo": "M", "version_sw": "1.0",
          "nombre_ciclo": "134 Instrumental", "tipo_ciclo": "instrumental_134",
          "temp_esterilizacion": 134.0, "tiempo_esterilizacion": 4,
          "fecha_inicio": "2026-10-23T10:00:00", "fecha_fin": "2026-10-23T11:00:00",
          "resultado": "FALLO_ESTERILIZACION", "codigo_fallo": "CIC-04",
          "motivo_fallo": "CIC-04 · Fallo en esterilización: Temperatura alta",
          "f0_final": 12.3, "operador": "Ana",
          "avisos_ticket": json.dumps({"sin_datos_s": None, "avisos": [
              {"clave": "ticket_ciclo.aviso_uniformidad", "sensor": "Sonda 2", "temp": 131.2},
              "Aviso antiguo"]})}


def test_reimpresion_en_ingles():
    texto = tf.format_ticket(_CICLO, [], EN)
    assert "Status: FAILED (STERILIZATION)" in texto
    assert "Reason: CIC-04 - Sterilization failure" in texto
    assert "Warning: Thermal uniformity out of range: Sonda 2 131.2 C" in texto
    assert "Warning: Aviso antiguo" in texto
    assert "*** LOAD NOT STERILE ***" in texto and "F0 total: 12.3 min" in texto
    assert "Cycle No.: 000012" in texto and "Steril. temp.: 134.0 C" in texto
    texto.encode("cp437")


def test_reimpresion_en_espanol_igual_que_antes():
    texto = tf.format_ticket(_CICLO, [], ES)
    assert "Estado: FALLO_ESTERILIZACION" in texto
    assert "Motivo: CIC-04 - Fallo en esterilización" in texto
    assert "Aviso: Uniformidad termica fuera de rango: Sonda 2 131.2 C" in texto
    assert "Ciclo No.: 000012" in texto and "Temp. Ester.: 134.0 C" in texto
    assert "SoftW.: 1.0" in texto and "*** CARGA NO ESTÉRIL ***" in texto


def test_aviso_en_fahrenheit():
    assert tf.aviso_ticket({"clave": "ticket_ciclo.aviso_uniformidad", "sensor": "S",
                            "temp": 100.0}, EN_F).endswith("S 212.0 F")


@pytest.mark.parametrize("resultado,esperado", [
    ("COMPLETADO", "COMPLETED"), ("CANCELADO", "CANCELLED"),
    ("FALLO_PRE_VACIO", "FAILED (PREVACUUM)"), ("FALLO_IO", "FAILED (I/O)"),
    ("FALLO_PUERTA_2_EMPAQUE", "FAILED (DOOR 2 GASKET)"),
    ("FALLO_PUERTA_1_EMPAQUE_SIN_LECTURA", "FAILED (DOOR 1 GASKET NO READING)"),
    ("SENSOR_AUSENTE", "SENSOR MISSING"), ("FALLO_DESCONOCIDA", "FAILED_DESCONOCIDA"),
])
def test_resultado_en_ingles(resultado, esperado):
    assert tf.resultado_ticket(resultado, EN) == esperado
    assert tf.resultado_ticket(resultado, ES) == resultado


def test_nombre_de_programa_de_fabrica_en_el_idioma_del_ticket():
    clave = "ciclos_fabrica.134_instrumental.nombre"
    tf.fijar_resolutor_nombre(lambda cid, nombre: clave if cid == "instrumental_134" else None)
    try:
        en = tf.format_header(dict(_CICLO), EN)
        assert i18n.t(clave, "en") in en.split("\n")
        es = tf.format_header(dict(_CICLO, tipo_ciclo="propio", nombre_ciclo="Mi programa"), EN)
        assert "Mi programa" in es.split("\n")
    finally:
        tf.fijar_resolutor_nombre(None)

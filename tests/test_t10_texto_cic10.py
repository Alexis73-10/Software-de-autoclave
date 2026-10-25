"""T10 (tanda 10, D10-3): textos de CIC-10 según la causa.

Con la causa «sin presión de cámara» (D9-1.4) el motivo y la acción dicen que
sin el sensor de presión de cámara no se puede llevar la cámara a estado
seguro y piden revisar la conexión del sensor o llamar a servicio técnico; no
mencionan la sonda Principal. Con la causa de sonda Principal el texto no
cambia. Solo textos: la lógica del protocolo no se toca."""

import ast
import json
from pathlib import Path

import pytest

from autoclave.core.runtime import alarmas_i18n
from autoclave.state_machine.alarms.catalogo import CATALOGO, CIC_10
from tests.helpers.backend_doble import modulo_backend

SRC = Path(__file__).resolve().parents[1] / "src" / "autoclave"
CATALOGOS = {l: json.loads((SRC / "i18n" / f"{l}.json").read_text(encoding="utf-8"))
             for l in ("es", "en")}

# Textos de la acción de CIC-10 antes de la tanda 10 (causa sonda Principal):
# deben quedar idénticos.
ACCION_PRINCIPAL = {
    "es": ("No abra la puerta. Revise la sonda Principal o asigne otra sonda como Principal en "
           "OPCIONES › Parámetros del ciclo › Sensores (técnico o ingeniero). Si no se resuelve, "
           "llame a servicio técnico."),
    "en": ("Do not open the door. Check the Main probe or assign another probe as Main in "
           "OPTIONS › Cycle parameters › Sensors (technician or engineer). If it is not resolved, "
           "call technical service."),
}
MOTIVO_PRINCIPAL = "Sensor Principal sin lectura: el estado seguro no puede confirmar la temperatura"
# Motivo con que la tanda 9 registraba la presión perdida (registros viejos)
MOTIVO_PRESION_T9 = ("Sensor de presión de cámara sin lectura: el estado seguro no puede "
                     "confirmar la presión. Llame a servicio técnico")


def _motivo_presion() -> str:
    """El motivo literal que arma ProtocoloFallo.bloqueado_motivo con la
    presión de cámara sin lectura."""
    ruta = SRC / "state_machine" / "cycle_phases" / "protocolo_fallo.py"
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    funcion = next(n for n in ast.walk(arbol)
                   if isinstance(n, ast.FunctionDef) and n.name == "bloqueado_motivo")
    motivos = [n.value.value for n in ast.walk(funcion)
               if isinstance(n, ast.Return) and isinstance(n.value, ast.Constant)
               and isinstance(n.value.value, str) and "presión de cámara" in n.value.value]
    assert len(motivos) == 1, motivos
    return motivos[0]


def _sin_principal(texto: str):
    bajo = texto.lower()
    assert "principal" not in bajo and "main probe" not in bajo and "main " not in bajo, texto
    assert "sonda" not in bajo and "probe" not in bajo, texto


def _dice_presion_y_estado_seguro(texto: str, idioma: str):
    bajo = texto.lower()
    if idioma == "es":
        assert "sensor de presión de cámara" in bajo, texto
        assert "no se puede llevar la cámara a estado seguro" in bajo, texto
        assert "conexión" in bajo and "servicio técnico" in bajo, texto
    else:
        assert "chamber pressure sensor" in bajo, texto
        assert "safe state" in bajo and "cannot" in bajo, texto
        assert "connection" in bajo and "technical service" in bajo, texto


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_sin_presion_la_accion_no_menciona_la_sonda_principal(idioma):
    t = alarmas_i18n.textos(CATALOGO[CIC_10], {"motivo": _motivo_presion()}, idioma)
    _sin_principal(t["accion"])
    _dice_presion_y_estado_seguro(t["accion"], idioma)
    assert t["accion"].startswith("No abra la puerta." if idioma == "es" else "Do not open the door.")


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_sin_presion_el_motivo_dice_que_no_se_puede_llevar_a_estado_seguro(idioma):
    t = alarmas_i18n.textos(CATALOGO[CIC_10], {"motivo": _motivo_presion()}, idioma)
    _sin_principal(t["descripcion"])
    _dice_presion_y_estado_seguro(t["descripcion"], idioma)
    clave = alarmas_i18n.clave_motivo_bloqueo(_motivo_presion())
    assert clave == "estado_seguro_motivos.sin_presion_camara"
    _dice_presion_y_estado_seguro(CATALOGOS[idioma]["estado_seguro_motivos"]["sin_presion_camara"],
                                  idioma)


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_registro_viejo_sin_presion_tambien_usa_la_accion_nueva(idioma):
    t = alarmas_i18n.textos(CATALOGO[CIC_10], {"motivo": MOTIVO_PRESION_T9}, idioma)
    _sin_principal(t["accion"])
    _dice_presion_y_estado_seguro(t["accion"], idioma)


@pytest.mark.parametrize("idioma", ["es", "en"])
@pytest.mark.parametrize("motivo", [
    MOTIVO_PRINCIPAL,
    "Sensor Principal sin lectura: no se puede confirmar el enfriamiento",
    "Sensor Principal sin lectura con carga líquida: cámara sellada hasta que las sondas "
    "confirmen la temperatura o venza la espera",
    "Sensor Principal sin lectura",
])
def test_con_sonda_principal_la_accion_no_cambia(idioma, motivo):
    t = alarmas_i18n.textos(CATALOGO[CIC_10], {"motivo": motivo}, idioma)
    assert t["accion"] == ACCION_PRINCIPAL[idioma]
    assert CATALOGO[CIC_10].accion == ACCION_PRINCIPAL["es"]
    assert CATALOGOS[idioma]["alarmas"]["CIC-10"]["accion"] == ACCION_PRINCIPAL[idioma]


def test_la_accion_variante_existe_en_ambos_idiomas_y_el_catalogo_trae_el_espanol():
    from autoclave.state_machine.alarms.catalogo import CIC_10_ACCION_SIN_PRESION
    assert CATALOGOS["es"]["alarmas"]["CIC-10"]["accion_sin_presion"] == CIC_10_ACCION_SIN_PRESION
    assert CATALOGOS["en"]["alarmas"]["CIC-10"]["accion_sin_presion"].strip()
    assert alarmas_i18n.accion(CATALOGO[CIC_10], {"motivo": _motivo_presion()}) \
        == CIC_10_ACCION_SIN_PRESION
    assert alarmas_i18n.accion(CATALOGO[CIC_10], {"motivo": MOTIVO_PRINCIPAL}) \
        == ACCION_PRINCIPAL["es"]
    # otra alarma: la acción del catálogo tal cual
    assert alarmas_i18n.accion(CATALOGO["SEN-06"], {}) == CATALOGO["SEN-06"].accion


# ── lo que llega a /status, a la tarjeta de Preciclo y a la campana ───────────

def _dto(motivo):
    from autoclave.backend import server
    from autoclave.state_machine.alarms.alarm_manager import AlarmManager
    am = AlarmManager()
    am.activar(CIC_10, motivo=motivo)
    return modulo_backend("rutas.sistema")._alarma_dto(am.activas()[0])


def test_status_sin_presion_lleva_la_accion_y_el_motivo_nuevos():
    dto = _dto(_motivo_presion())
    _sin_principal(dto["accion"])
    _dice_presion_y_estado_seguro(dto["accion"], "es")
    for idioma in ("es", "en"):
        _sin_principal(dto["textos"][idioma]["accion"])
        _sin_principal(dto["textos"][idioma]["descripcion"])
        _dice_presion_y_estado_seguro(dto["textos"][idioma]["descripcion"], idioma)
    _sin_principal(dto["description"])
    _dice_presion_y_estado_seguro(dto["description"], "es")


def test_status_con_sonda_principal_conserva_la_accion():
    dto = _dto(MOTIVO_PRINCIPAL)
    assert dto["accion"] == ACCION_PRINCIPAL["es"]
    assert dto["textos"]["en"]["accion"] == ACCION_PRINCIPAL["en"]
    assert dto["description"] == MOTIVO_PRINCIPAL + ". La cámara sigue sin considerarse segura."


def test_tarjeta_de_preciclo_y_campana_reciben_el_motivo_nuevo():
    """La tarjeta de alarmas de Preciclo y la campana (PanelNotificaciones ›
    FilaAlarma) muestran el rol `description` de AlarmListModel; el aviso de
    la campana (SeccionEstadoSeguro) muestra el motivo por su clave y, sin
    sonda Principal, no añade la acción de asignar sonda ni su botón."""
    pytest.importorskip("PySide6")
    from autoclave.ui_qml.bridge.ui_bridge import UiBridge, _normalizar_alarmas
    fila = _normalizar_alarmas([_dto(_motivo_presion())])[0]
    _sin_principal(fila["description"])
    _dice_presion_y_estado_seguro(fila["description"], "es")
    d = UiBridge._seguridad_de({"estado_seguro": {"activo": True,
                                                  "bloqueado_motivo": _motivo_presion()}})
    assert d["es_bloqueado_clave"] == "estado_seguro_motivos.sin_presion_camara"
    assert d["es_bloqueado_sonda"] is False
    d = UiBridge._seguridad_de({"estado_seguro": {"activo": True,
                                                  "bloqueado_motivo": MOTIVO_PRINCIPAL}})
    assert d["es_bloqueado_sonda"] is True

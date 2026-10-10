# T-17 (planeacion_backend_autenticacion.md §5.8): el ciclo en curso trabaja
# con una copia profunda del programa tomada al entrar en CICLO, y un cambio
# del ingeniero en CICLO solo llega a esa copia si la fase del parámetro aún
# no ha iniciado. Programa real (perfil JSON de usuario) y CicloState real;
# el resto de dependencias son dobles.

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from autoclave.core.managers.cycle_manager import Cycle
from autoclave.state_machine.machine.enum_global import GlobalState
from autoclave.state_machine.states.ciclo import CicloResultado, CicloState

_PERFIL = (Path(__file__).resolve().parents[1]
           / "src/autoclave/cycles/user/instrumental_134.json")


def _programa() -> Cycle:
    data = json.loads(_PERFIL.read_text(encoding="utf-8"))
    return Cycle(data["cycle_id"], data["cycle_id"], data["parameters"])


def _parametro(programa: Cycle, seccion: str):
    """Primer parámetro editable de la sección y un valor nuevo válido."""
    for nombre, hoja in programa.parameters[seccion].items():
        if not isinstance(hoja, dict) or "value" not in hoja:
            continue
        if hoja.get("type") == "bool":
            return [nombre], not hoja["value"]
        for candidato in (hoja.get("min"), hoja.get("max")):
            if candidato is not None and candidato != hoja["value"]:
                return [nombre], candidato
    raise AssertionError(f"sin parámetro editable en {seccion}")


def _valor(programa: Cycle, seccion: str, path: list[str]):
    return programa.parameters[seccion][path[0]]["value"]


def _ciclo(fase_idx=0):
    programa = _programa()
    estado = MagicMock()
    estado.get_flag.return_value = False
    ciclo = CicloState(estado, MagicMock(), programa, MagicMock(), MagicMock())
    ciclo.reset()
    ciclo._fase_idx = fase_idx
    return ciclo, programa


def _editar(ciclo, programa, seccion):
    """Como el endpoint: guarda en el almacenado y luego decide la copia."""
    path, nuevo = _parametro(programa, seccion)
    nuevo = programa.set_param(seccion, path, nuevo)
    return path, nuevo, ciclo.aplicar_si_fase_pendiente(seccion, path, nuevo)


# ── Copia al entrar en CICLO ──────────────────────────────────────────────────

def test_al_entrar_en_ciclo_todo_lee_la_copia():
    ciclo, programa = _ciclo()
    copia = ciclo.programa_en_curso
    assert copia is not programa and copia.parameters is not programa.parameters
    assert ciclo.cycle is copia and ciclo._protocolo.cycle is copia
    assert all(f.cycle is copia for f in ciclo._fases)


def test_editar_el_almacenado_no_cambia_una_fase_iniciada():
    """Criterio 11c: dentro de una fase iniciada ningún valor cambia."""
    ciclo, programa = _ciclo(fase_idx=2)                  # CALENTAMIENTO en curso
    antes = json.dumps(ciclo.programa_en_curso.parameters["calentamiento"], sort_keys=True)
    path, nuevo, aplico = _editar(ciclo, programa, "calentamiento")
    assert aplico is False
    assert _valor(programa, "calentamiento", path) == nuevo
    assert json.dumps(ciclo.programa_en_curso.parameters["calentamiento"], sort_keys=True) == antes


def test_el_siguiente_ciclo_toma_el_cambio():
    ciclo, programa = _ciclo(fase_idx=2)
    path, nuevo, _ = _editar(ciclo, programa, "calentamiento")
    ciclo.reset()
    assert _valor(ciclo.programa_en_curso, "calentamiento", path) == nuevo


# ── Regla de fases pendientes ─────────────────────────────────────────────────

@pytest.mark.parametrize("seccion", ["esterilizacion", "descompresion", "secado"])
def test_fase_pendiente_aplica_al_ciclo_en_curso(seccion):
    ciclo, programa = _ciclo(fase_idx=2)                  # CALENTAMIENTO en curso
    path, nuevo, aplico = _editar(ciclo, programa, seccion)
    assert aplico is True
    assert _valor(ciclo.programa_en_curso, seccion, path) == nuevo


@pytest.mark.parametrize("seccion", ["precalentamiento", "prevacio",        # terminadas
                                     "calentamiento", "estabilizacion"])   # en curso
def test_fase_iniciada_o_terminada_rige_desde_el_siguiente(seccion):
    ciclo, programa = _ciclo(fase_idx=2)
    path, _, aplico = _editar(ciclo, programa, seccion)
    assert aplico is False
    assert _valor(ciclo.programa_en_curso, seccion, path) != _valor(programa, seccion, path)


@pytest.mark.parametrize("seccion", ["globals", "finalizacion"])
def test_secciones_globales_rigen_desde_el_siguiente(seccion):
    """Fase "Global": un cambio en finalizacion no afecta a la apertura
    automática del ciclo en curso."""
    ciclo, programa = _ciclo(fase_idx=0)
    path, _, aplico = _editar(ciclo, programa, seccion)
    assert aplico is False
    assert _valor(ciclo.programa_en_curso, seccion, path) != _valor(programa, seccion, path)


def test_la_primera_fase_cuenta_como_iniciada_al_entrar():
    ciclo, programa = _ciclo(fase_idx=0)
    _, _, aplico = _editar(ciclo, programa, "precalentamiento")
    assert aplico is False


@pytest.mark.parametrize("resultado", [CicloResultado.COMPLETADO, CicloResultado.FALLO,
                                       CicloResultado.CANCELADO])
def test_ciclo_terminado_no_recibe_cambios(resultado):
    """Esperando confirmación (o en el protocolo de fallo) ya no hay fases
    pendientes: el protocolo de fallo lee descompresion de la copia."""
    ciclo, programa = _ciclo(fase_idx=1)
    ciclo._resultado_pendiente = resultado
    _, _, aplico = _editar(ciclo, programa, "descompresion")
    assert aplico is False


def test_sin_copia_no_aplica():
    programa = _programa()
    ciclo = CicloState(MagicMock(), MagicMock(), programa, MagicMock(), MagicMock())
    path, nuevo = _parametro(programa, "secado")
    assert ciclo.aplicar_si_fase_pendiente("secado", path, nuevo) is False


def test_ruta_inexistente_no_aplica_ni_rompe():
    ciclo, _ = _ciclo(fase_idx=0)
    assert ciclo.aplicar_si_fase_pendiente("secado", ["no_existe"], 1) is False


# ── ControlLoop y registro del ciclo ──────────────────────────────────────────

def _loop(estado_maquina):
    from autoclave.services.domain.loop.control_loop import ControlLoop
    estado = MagicMock()
    estado.get_machine_state.return_value = estado_maquina
    cycle_manager = MagicMock()
    cycle_manager.get_selected_cycle.return_value = _programa()
    logger_ciclo = MagicMock()
    with patch("autoclave.services.domain.loop.control_loop.StateMachine"):
        loop = ControlLoop(units=MagicMock(), door_service=MagicMock(), doors=[],
                           estado=estado, link=MagicMock(), set_do=MagicMock(),
                           alarm_manager=MagicMock(), cycle_manager=cycle_manager,
                           config_manager=MagicMock(), cycle_logger=logger_ciclo)
    return loop, logger_ciclo


def test_control_loop_solo_aplica_en_ciclo():
    loop, _ = _loop(GlobalState.PREPARADO)
    assert loop.aplicar_a_ciclo_en_curso("secado", ["x"], 1) is False
    loop.state_machine.ciclo.aplicar_si_fase_pendiente.assert_not_called()

    loop, _ = _loop(GlobalState.CICLO)
    loop.state_machine.ciclo.aplicar_si_fase_pendiente.return_value = True
    assert loop.aplicar_a_ciclo_en_curso("secado", ["x"], 1) is True


def test_programa_en_ejecucion_es_la_copia_o_el_seleccionado():
    loop, logger_ciclo = _loop(GlobalState.CICLO)
    loop.state_machine.ciclo.programa_en_curso = None
    assert loop.programa_en_ejecucion() is loop.cycle
    copia = loop.cycle.copia()
    loop.state_machine.ciclo.programa_en_curso = copia
    assert loop.programa_en_ejecucion() is copia
    # el registro del ciclo (ticket, F0 del pie) lee el mismo programa
    assert logger_ciclo.programa_en_ejecucion() is copia


def test_registro_del_ciclo_usa_el_programa_en_ejecucion():
    from autoclave.services.domain.logging.cycle_logger import CycleLogger
    seleccionado, copia = _programa(), _programa()
    cycle_manager = MagicMock()
    cycle_manager.get_selected_cycle.return_value = seleccionado
    registro = CycleLogger(MagicMock(), MagicMock(), MagicMock(), MagicMock(), cycle_manager)
    assert registro._programa() is seleccionado
    registro.programa_en_ejecucion = lambda: copia
    assert registro._programa() is copia


# ── Revisión de seguridad y temporización de T-17 ─────────────────────────────

class _Estado:
    def __init__(self):
        self.maquina = GlobalState.PREPARADO
        self.flags = {"START_CICLO": True}
        self.sensores_temp, self.sensores_pres, self.sensores_di = {}, {}, {}
        self.fase_ciclo = ""
        self.estado_maquina = {}
        self.Alarmas_activas = {}

    def get_machine_state(self):
        return self.maquina

    def set_machine_state(self, valor):
        self.maquina = valor

    def get_flag(self, nombre):
        return self.flags.get(nombre, False)

    def set_flag(self, nombre, valor):
        self.flags[nombre] = valor


def test_la_copia_se_toma_en_el_mismo_tick_que_entra_en_ciclo():
    """SAF-01/TMG-02: el registro del ciclo corre en ese mismo tick y leía la
    copia del ciclo anterior (cabecera del ticket con valores viejos)."""
    from autoclave.state_machine import state_machine as sm_mod
    programa = _programa()
    estado = _Estado()
    with patch.object(sm_mod, "preparado_state") as preparado, \
         patch.object(sm_mod, "preparacion_state"):
        preparado.return_value.run.return_value = True
        sm = sm_mod.StateMachine(MagicMock(), estado, MagicMock(), programa, MagicMock())
        sm.prev_state = GlobalState.PREPARADO
        copia_anterior = programa.copia()
        sm.ciclo.programa_en_curso = copia_anterior          # ciclo anterior
        path, nuevo = _parametro(programa, "esterilizacion")
        programa.set_param("esterilizacion", path, nuevo)    # edición en PREPARADO
        sm.update()
    assert estado.maquina == GlobalState.CICLO
    copia = sm.ciclo.programa_en_curso
    assert copia is not copia_anterior
    assert _valor(copia, "esterilizacion", path) == nuevo
    reset = MagicMock(wraps=sm.ciclo.reset)
    sm.ciclo.reset = reset
    with patch.object(sm.ciclo, "run", return_value="EN_CURSO"):
        sm.update()                                           # tick siguiente
    reset.assert_not_called()                                 # sin segunda entrada


def test_descompresion_lee_el_modo_al_iniciar_la_fase():
    """TMG-01: el modo se fijaba al iniciar el ciclo; un cambio con la fase
    pendiente se informaba como aplicado y la fase corría con el viejo."""
    ciclo, programa = _ciclo(fase_idx=3)                      # ESTERILIZACION en curso
    fase = next(f for f in ciclo._fases if f.name == "DESCOMPRESION")
    actual = programa.get_param("descompresion", "modo")
    nuevo = 1 if actual != 1 else 2
    programa.set_param("descompresion", ["modo"], nuevo)
    assert ciclo.aplicar_si_fase_pendiente("descompresion", ["modo"], nuevo) is True
    fase.update()
    assert fase._modo == nuevo


# ── Parámetros vinculados (SAF-02, decisión de Cristian) ──────────────────────

@pytest.mark.parametrize("seccion,nombre", [("calentamiento", "temperatura_calentamiento"),
                                            ("esterilizacion", "temperatura_esterilizacion")])
def test_temperaturas_de_calentamiento_y_esterilizacion_se_ajustan_juntas(seccion, nombre):
    programa = _programa()
    assert programa.set_param(seccion, [nombre], 121.0) == 121.0
    assert programa.get_param("calentamiento", "temperatura_calentamiento") == 121.0
    assert programa.get_param("esterilizacion", "temperatura_esterilizacion") == 121.0


def test_vinculado_fuera_de_rango_no_cambia_ninguno():
    programa = _programa()
    hoja = programa.parameters["esterilizacion"]["temperatura_esterilizacion"]
    hoja["max"] = 130                                 # la pareja admite menos
    with pytest.raises(ValueError):
        programa.set_param("calentamiento", ["temperatura_calentamiento"], 132.0)
    assert programa.get_param("calentamiento", "temperatura_calentamiento") == 134.0
    assert programa.get_param("esterilizacion", "temperatura_esterilizacion") == 134.0


def test_vinculado_con_una_fase_iniciada_rige_desde_el_siguiente():
    """CALENTAMIENTO en curso: la temperatura de esterilización (pendiente)
    no puede cambiar sola, quedarían distintas en el ciclo en curso."""
    ciclo, programa = _ciclo(fase_idx=2)
    programa.set_param("esterilizacion", ["temperatura_esterilizacion"], 121.0)
    assert ciclo.aplicar_si_fase_pendiente(
        "esterilizacion", ["temperatura_esterilizacion"], 121.0) is False
    copia = ciclo.programa_en_curso
    assert copia.get_param("calentamiento", "temperatura_calentamiento") == 134.0
    assert copia.get_param("esterilizacion", "temperatura_esterilizacion") == 134.0


def test_vinculado_con_ambas_fases_pendientes_aplica_a_las_dos():
    ciclo, programa = _ciclo(fase_idx=1)              # PRE_VACIO en curso
    programa.set_param("calentamiento", ["temperatura_calentamiento"], 121.0)
    assert ciclo.aplicar_si_fase_pendiente(
        "calentamiento", ["temperatura_calentamiento"], 121.0) is True
    copia = ciclo.programa_en_curso
    assert copia.get_param("calentamiento", "temperatura_calentamiento") == 121.0
    assert copia.get_param("esterilizacion", "temperatura_esterilizacion") == 121.0

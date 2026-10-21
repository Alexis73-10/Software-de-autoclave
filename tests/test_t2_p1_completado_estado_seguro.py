"""T2 / P-1 (tanda 6): el reconocimiento de un ciclo COMPLETADO con la cámara
NO segura entra al protocolo de estado seguro, igual que tras un fallo o una
cancelación. Con la cámara segura, PREPARADO directo (sin protocolo)."""

from unittest.mock import MagicMock

from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.state_machine.machine.enum_global import GlobalState
from autoclave.state_machine.state_machine import StateMachine

_CFG = {"presion_admosferica": 101.3, "rango_presion_atm": 10.0, "temp_max_apertura": 80.0}


class _Config(dict):
    def get(self, k, d=None):
        return super().get(k, d)


def _sm(pres, temp, temp_max_ciclo=None):
    estado = EstadoAutoclave()
    estado.sensores_pres["pres_camara"] = pres
    estado.sensores_temp["temp_camara"] = temp
    es = MagicMock()
    es.activo = False
    cycle = MagicMock()
    cycle.copia.return_value = cycle
    cycle.sensores = None
    cycle.get_param.side_effect = lambda *a, default=None, **k: (
        temp_max_ciclo if a[:2] == ("finalizacion", "temp_max_apertura") else default)
    sm = StateMachine(io=MagicMock(), estado=estado, set_do=MagicMock(), cycle=cycle,
                      config=_Config(_CFG), estado_seguro=es)
    estado.set_machine_state(GlobalState.CICLO)
    sm.prev_state = GlobalState.CICLO
    sm.ciclo.run = MagicMock(return_value="COMPLETADO")
    sm.ciclo._protocolo = MagicMock()
    return sm, estado, es


def test_completado_con_camara_caliente_inicia_estado_seguro():
    sm, estado, es = _sm(pres=101.3, temp=110.0)
    sm.update()
    assert estado.get_machine_state() == GlobalState.PREPARADO
    sm.ciclo._protocolo.ejecutar.assert_called_once_with(abrir_valvulas=True)
    es.iniciar.assert_called_once_with(sm.ciclo._protocolo)


def test_completado_con_camara_presurizada_inicia_estado_seguro():
    sm, estado, es = _sm(pres=180.0, temp=60.0)
    sm.update()
    es.iniciar.assert_called_once()


def test_completado_con_camara_segura_no_inicia_protocolo():
    sm, estado, es = _sm(pres=101.3, temp=60.0)
    sm.update()
    assert estado.get_machine_state() == GlobalState.PREPARADO
    sm.ciclo._protocolo.ejecutar.assert_not_called()
    es.iniciar.assert_not_called()


def test_completado_sin_lectura_cuenta_como_no_segura():
    sm, estado, es = _sm(pres=None, temp=60.0)
    sm.update()
    es.iniciar.assert_called_once()


def test_completado_sin_datos_vigentes_cuenta_como_no_segura():
    sm, estado, es = _sm(pres=101.3, temp=60.0)
    sm.update(datos_vigentes=False)
    es.iniciar.assert_called_once()


def test_rige_el_temp_max_apertura_del_ciclo_si_es_menor():
    # global 80 °C, del ciclo 70 °C: con 75 °C no es segura
    sm, estado, es = _sm(pres=101.3, temp=75.0, temp_max_ciclo=70.0)
    sm.update()
    es.iniciar.assert_called_once()


def test_error_al_evaluar_cuenta_como_no_segura():
    sm, estado, es = _sm(pres=101.3, temp=60.0)
    sm.programas_seguridad = MagicMock(side_effect=RuntimeError("x"))
    sm.update()
    es.iniciar.assert_called_once()


def test_sin_datos_vigentes_no_abre_valvulas():
    # TMG-07 / SAF-04 de la revisión de T2
    sm, estado, es = _sm(pres=101.3, temp=110.0)
    sm.update(datos_vigentes=False)
    sm.ciclo._protocolo.ejecutar.assert_called_once_with(abrir_valvulas=False)

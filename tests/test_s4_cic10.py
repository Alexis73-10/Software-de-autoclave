"""S4 (tanda 3): cambio de rol del Principal con la cámara no segura tras un
ciclo. Hotfix ES (6-nov): el protocolo de estado seguro (y su CIC-10) se
retiró; la reasignación sigue rigiendo la copia del programa del último
ciclo, que cuenta para "NO ABRIR" hasta la cámara segura, con las mismas
salvaguardas (SAF-01/SAF-02)."""

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

from autoclave.core.runtime import camara_segura
from autoclave.state_machine.estado_seguro import ConfirmacionParo
from autoclave.state_machine.machine.enum_global import GlobalState
from autoclave.services.domain.loop.control_loop import ControlLoop

_CFG = {"presion_admosferica": 101.3, "rango_presion_atm": 10.0, "temp_max_apertura": 80.0}
_PARAMS = {("descompresion", "modo"): 4, ("descompresion", "modo_4", "timeout"): 60,
           ("descompresion", "modo_4", "temperatura_enfriamiento"): 80.0,
           ("globals", "tipo_carga"): "liquido",
           ("finalizacion", "temp_max_apertura"): 80.0}


class _Config(dict):
    def get(self, k, d=None):
        return super().get(k, d)


class _Programa:
    id = "usr_liq"

    def __init__(self, principal):
        self.sensores = {"temp_camara": "no_en_uso", "temp_2_camara": "no_en_uso",
                         "temp_ref": "no_en_uso", principal: "principal"}

    def get_param(self, *ruta, default=None):
        return _PARAMS.get(ruta, default)


def _estado():
    flags = {}
    return SimpleNamespace(
        sensores_pres={"pres_camara": 200.0},
        sensores_temp={"temp_camara": None, "temp_2_camara": 70.0, "temp_ref": None},
        get_flag=lambda f: flags.get(f, False))


def _montar():
    estado = _estado()
    programa = _Programa("temp_camara")
    es = ConfirmacionParo(estado)
    cl = ControlLoop.__new__(ControlLoop)
    cl._sm_lock = threading.RLock()
    cl.estado = SimpleNamespace(get_machine_state=lambda: GlobalState.FALLA,
                                sensores_temp=estado.sensores_temp)
    cl.estado_seguro = es
    cl.cycle = None
    cl._programa_ultimo_ciclo = programa
    cl._recuperacion_pendiente = None
    return estado, programa, es, cl


def _segura(cl, estado):
    return camara_segura.evaluar(estado, _Config(_CFG), [cl._programa_ultimo_ciclo])[0]


def test_principal_sin_lectura_mantiene_no_abrir():
    estado, programa, es, cl = _montar()
    estado.sensores_pres["pres_camara"] = 101.3
    assert _segura(cl, estado) is False


def test_cambiar_el_principal_rige_la_copia_del_ultimo_ciclo():
    estado, programa, es, cl = _montar()
    estado.sensores_pres["pres_camara"] = 101.3
    nueva = {"temp_camara": "no_en_uso", "temp_2_camara": "principal", "temp_ref": "no_en_uso"}
    assert cl.aplicar_roles_sensores("usr_liq", nueva) == (True, "aplicado")
    assert _segura(cl, estado) is True            # ya mira temp_2_camara (70 °C)
    # SAF-02: la instantánea del ciclo terminado NO se muta; se usa una copia
    assert programa.sensores["temp_camara"] == "principal"
    assert cl._programa_ultimo_ciclo is not programa
    assert cl._programa_ultimo_ciclo.sensores["temp_2_camara"] == "principal"


def test_nuevo_principal_mas_frio_que_otra_sonda_no_libera():
    """SAF-01: una sonda fría no puede liberar NO ABRIR con la carga caliente."""
    estado, programa, es, cl = _montar()
    estado.sensores_temp["temp_ref"] = 125.0       # otra sonda con lectura: caliente
    estado.sensores_temp["temp_2_camara"] = 70.0
    nueva = {"temp_camara": "no_en_uso", "temp_2_camara": "principal", "temp_ref": "no_en_uso"}
    aplicado, motivo = cl.aplicar_roles_sensores("usr_liq", nueva)
    assert aplicado is False and motivo == "principal_mas_frio_que_otra_sonda"
    assert cl._programa_ultimo_ciclo is programa


def test_nuevo_principal_sin_lectura_no_libera():
    estado, programa, es, cl = _montar()
    estado.sensores_temp["temp_2_camara"] = None
    aplicado, motivo = cl.aplicar_roles_sensores("usr_liq", {
        "temp_camara": "no_en_uso", "temp_2_camara": "principal", "temp_ref": "no_en_uso"})
    assert (aplicado, motivo) == (False, "principal_sin_lectura")


def test_el_nuevo_principal_tambien_decide_la_camara_segura():
    """El Principal nuevo caliente mantiene NO ABRIR: no se libera a ciegas."""
    estado, programa, es, cl = _montar()
    estado.sensores_temp["temp_2_camara"] = 130.0
    estado.sensores_pres["pres_camara"] = 101.3
    assert cl.aplicar_roles_sensores("usr_liq", {"temp_camara": "no_en_uso",
                                                 "temp_2_camara": "principal",
                                                 "temp_ref": "no_en_uso"})[0] is True
    assert _segura(cl, estado) is False            # 130 °C: sigue sin ser segura


def test_no_toca_la_instantanea_durante_un_ciclo():
    estado, programa, es, cl = _montar()
    cl.estado = SimpleNamespace(get_machine_state=lambda: GlobalState.CICLO,
                                sensores_temp=estado.sensores_temp)
    cl.aplicar_roles_sensores("usr_liq", {"temp_camara": "no_en_uso",
                                          "temp_2_camara": "principal", "temp_ref": "no_en_uso"})
    assert programa.sensores["temp_camara"] == "principal"


def test_otro_programa_no_se_modifica():
    estado, programa, es, cl = _montar()
    cl.aplicar_roles_sensores("otro", {"temp_camara": "no_en_uso",
                                       "temp_2_camara": "principal", "temp_ref": "no_en_uso"})
    assert programa.sensores["temp_camara"] == "principal"


def test_el_catalogo_indica_que_hacer():
    from autoclave.state_machine.alarms.catalogo import CATALOGO, CIC_10
    accion = CATALOGO[CIC_10].accion
    assert "sonda Principal" in accion and "Parámetros del ciclo" in accion


def test_el_puente_expone_el_motivo_y_el_comando_abre_opciones():
    import os, sys
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    from autoclave.ui_qml.bridge.comandos_sistema import ComandosSistema
    from autoclave.ui_qml.bridge.ui_bridge import UiBridge
    d = UiBridge._seguridad_de({"estado_seguro": {"activo": True,
                                                  "bloqueado_motivo": "Sensor Principal sin lectura"}})
    assert d["es_bloqueado"] == "Sensor Principal sin lectura"
    assert UiBridge._seguridad_de({})["es_bloqueado"] == ""
    puente = MagicMock()
    c = ComandosSistema(puente, MagicMock(), 1)
    abiertos = []
    c.asignarSondaSolicitada.connect(lambda: abiertos.append(1))
    c.asignarSondaPrincipal()
    assert abiertos == [1]

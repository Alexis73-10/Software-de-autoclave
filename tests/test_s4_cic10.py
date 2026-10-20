"""S4 (tanda 3): CIC-10 — estado seguro detenido por el Principal sin lectura.
Un cambio de rol del Principal debe liberarlo (con una lectura válida) y la
UI debe indicar qué hacer."""

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

from autoclave.state_machine.cycle_phases.protocolo_fallo import ProtocoloFallo
from autoclave.state_machine.estado_seguro import ProtocoloEstadoSeguro
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
    set_do = MagicMock()
    prot = ProtocoloFallo(estado, set_do, programa, _Config(_CFG))
    prot.ejecutar()
    es = ProtocoloEstadoSeguro(estado, _Config(_CFG), programas_seguridad=lambda: [programa])
    es.iniciar(prot)
    cl = ControlLoop.__new__(ControlLoop)
    cl._sm_lock = threading.RLock()
    cl.estado = SimpleNamespace(get_machine_state=lambda: GlobalState.FALLA,
                                sensores_temp=estado.sensores_temp)
    cl.estado_seguro = es
    cl.cycle = None
    cl._programa_ultimo_ciclo = programa
    cl._recuperacion_pendiente = None
    return estado, programa, es, cl


def test_principal_sin_lectura_detiene_el_estado_seguro():
    estado, programa, es, cl = _montar()
    es.update()
    assert es.bloqueado_motivo and "Principal sin lectura" in es.bloqueado_motivo


def test_cambiar_el_principal_libera_el_estado_seguro_detenido():
    estado, programa, es, cl = _montar()
    es.update()
    assert es.bloqueado_motivo is not None
    nueva = {"temp_camara": "no_en_uso", "temp_2_camara": "principal", "temp_ref": "no_en_uso"}
    assert cl.aplicar_roles_sensores("usr_liq", nueva) == (True, "aplicado")
    es.update()
    assert es.bloqueado_motivo is None            # ya mira temp_2_camara (70 °C)
    # SAF-02: la instantánea del ciclo terminado NO se muta; el protocolo usa una copia
    assert programa.sensores["temp_camara"] == "principal"
    assert es.programa is not programa and es.programa.sensores["temp_2_camara"] == "principal"


def test_nuevo_principal_mas_frio_que_otra_sonda_no_libera():
    """SAF-01: una sonda fría no puede liberar el estado seguro con la carga caliente."""
    estado, programa, es, cl = _montar()
    estado.sensores_temp["temp_ref"] = 125.0       # otra sonda con lectura: caliente
    estado.sensores_temp["temp_2_camara"] = 70.0
    nueva = {"temp_camara": "no_en_uso", "temp_2_camara": "principal", "temp_ref": "no_en_uso"}
    aplicado, motivo = cl.aplicar_roles_sensores("usr_liq", nueva)
    assert aplicado is False and motivo == "principal_mas_frio_que_otra_sonda"
    es.update()
    assert es.programa is programa and es.bloqueado_motivo is not None   # sigue detenido


def test_nuevo_principal_sin_lectura_no_libera():
    estado, programa, es, cl = _montar()
    estado.sensores_temp["temp_2_camara"] = None
    aplicado, motivo = cl.aplicar_roles_sensores("usr_liq", {
        "temp_camara": "no_en_uso", "temp_2_camara": "principal", "temp_ref": "no_en_uso"})
    assert (aplicado, motivo) == (False, "principal_sin_lectura")


def test_el_nuevo_principal_tambien_decide_la_camara_segura():
    """El Principal nuevo caliente mantiene el estado seguro: no se libera a ciegas."""
    estado, programa, es, cl = _montar()
    estado.sensores_temp["temp_2_camara"] = 130.0
    estado.sensores_pres["pres_camara"] = 101.3
    assert cl.aplicar_roles_sensores("usr_liq", {"temp_camara": "no_en_uso",
                                                 "temp_2_camara": "principal",
                                                 "temp_ref": "no_en_uso"})[0] is True
    for _ in range(5):
        es.update()
    assert es.activo                               # 130 °C: sigue sin ser segura


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


def test_el_status_expone_el_motivo_del_bloqueo():
    from tests.backend_doble import cargar_servidor
    ctx = MagicMock()
    estado, programa, es, cl = _montar()
    es.update()
    ctx.control_loop.estado_seguro = es
    srv, _ = cargar_servidor(ctx)
    d = srv._estado_seguro_status()
    assert d["activo"] is True and "Principal sin lectura" in d["bloqueado_motivo"]


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

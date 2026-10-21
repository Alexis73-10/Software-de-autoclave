# Etapa 2 de planeacion_backend_autenticacion.md: endpoints de puertas (T-13,
# T-18, §5.3) y de fallas (T-16, §5.9), más FallaState con el paro activo, y
# las comprobaciones de backend de T-19 (temp_chaqueta fuera de /status y de
# la calibración, sin correr índices). Backend con contexto simulado.

import threading
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from autoclave.devices.puertas.enum_doors import DoorState
from autoclave.devices.puertas.simple_door import SimpleDoor
from autoclave.services.domain.puertas.ser_puertas import ServicioPuertas
from autoclave.state_machine.machine.enum_global import GlobalState
from autoclave.state_machine.states.falla import FallaState
from tests.backend_doble import cargar_servidor
from tests.test_servicio_puertas import CONFIG, Estado, _avanzada


class Flags:
    def __init__(self):
        self.valores = {}

    def get_flag(self, nombre):
        return self.valores.get(nombre, False)

    def set_flag(self, nombre, valor):
        self.valores[nombre] = valor


@pytest.fixture
def entorno(tmp_path):
    from autoclave.services.domain.logging.db_manager import DbManager
    est = Estado()
    flags = est   # una sola fuente de banderas para la máquina y las puertas
    p1 = _avanzada("Puerta 1", est, di={"bloqueo": "bloqueo_1"})
    p2 = SimpleDoor("Puerta 2", {"cerrada": "puerta_2_cerrada"}, est)
    est.puertas = {"Puerta 1": DoorState.CERRADO, "Puerta 2": DoorState.CERRADO}
    ctx = MagicMock()
    ctx.db = DbManager(db_path=tmp_path / "t.db")
    ctx.servicio_puertas = ServicioPuertas([p1, p2], est, MagicMock(), dict(CONFIG))
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    ctx.estado.get_flag.side_effect = flags.get_flag
    ctx.estado.set_flag.side_effect = flags.set_flag
    ctx.estado.fase_ciclo = ""
    ctx.control_loop.bloqueo_maquina.return_value = threading.Lock()
    ctx.control_loop.bloqueo_configuracion = None
    ctx.control_loop.test_mode_active = False
    ctx.control_loop.desconectado = False
    srv, _ = cargar_servidor(ctx)
    return TestClient(srv.app), ctx, est, flags


def _abrir(cliente, puerta="Puerta 1"):
    # S3e (tanda 2): cada pantalla opera su puerta; source_door = el número de la puerta
    return cliente.post(f"/doors/{puerta}/open", json={"source_door": int(puerta[-1])})


def _eventos(ctx, evento):
    return ctx.db.get_auditoria(evento=evento, limite=100)


# ── Puertas ───────────────────────────────────────────────────────────────────

def test_apertura_permitida_con_resultado_real(entorno):
    cliente, _, est, _ = entorno
    r = _abrir(cliente)
    assert r.status_code == 200
    assert r.json()["sin_actuador"] is False
    assert est.puertas["Puerta 1"] == DoorState.ABRIENDO


@pytest.mark.parametrize("estado", [GlobalState.CICLO])   # P-8 (tanda 6)
def test_puertas_bloqueadas_en_ciclo_hibernacion_y_emergencia(entorno, estado):
    cliente, ctx, est, _ = entorno
    ctx.estado.get_machine_state.return_value = estado
    est.puertas["Puerta 1"] = DoorState.ABIERTO
    for r in (_abrir(cliente), cliente.post("/doors/Puerta 1/close", json={})):
        assert r.status_code == 409
        assert r.json()["codigo"] == "estado_no_permitido"
    assert est.puertas["Puerta 1"] == DoorState.ABIERTO
    assert _eventos(ctx, "rechazo_409")


@pytest.mark.parametrize("estado", [GlobalState.PREPARACION, GlobalState.PREPARADO,
                                    GlobalState.FALLA])
def test_puertas_permitidas_en_preparacion_preparado_y_falla(entorno, estado):
    cliente, ctx, _, _ = entorno
    ctx.estado.get_machine_state.return_value = estado
    assert _abrir(cliente).status_code == 200


def test_sensor_ausente_rechaza_con_409_y_motivo(entorno):
    cliente, ctx, est, _ = entorno
    est.sensores_pres["pres_camara"] = None
    r = _abrir(cliente)
    assert r.status_code == 409
    assert r.json() == {"detail": "Sin lectura válida de presión de cámara",
                        "codigo": "puerta_rechazada"}
    assert est.puertas["Puerta 1"] == DoorState.CERRADO


def test_bloqueo_mecanico_responde_409_con_motivo(entorno):
    cliente, _, est, _ = entorno
    est.sensores_di["bloqueo_1"] = True
    r = _abrir(cliente)
    assert r.status_code == 409 and r.json()["detail"] == "Puerta bloqueada mecánicamente"


def test_puerta_sin_actuador_lo_indica(entorno):
    cliente, _, est, _ = entorno
    est.puertas["Puerta 1"] = DoorState.CERRADO
    r = _abrir(cliente, "Puerta 2")
    assert r.status_code == 200 and r.json()["sin_actuador"] is True


def test_puerta_desconocida_404(entorno):
    cliente, _, _, _ = entorno
    assert _abrir(cliente, "Puerta 9").status_code == 404


def test_cierre_con_estado_desconocido_409(entorno):
    cliente, _, est, _ = entorno
    est.puertas["Puerta 1"] = DoorState.DESCONOCIDO
    r = cliente.post("/doors/Puerta 1/close", json={})
    assert r.status_code == 409 and "desconocido" in r.json()["detail"]


# ── Fallas (T-16) ─────────────────────────────────────────────────────────────

def test_fault_reset_en_falla_guarda_reset_y_audita(entorno):
    cliente, ctx, _, flags = entorno
    ctx.estado.get_machine_state.return_value = GlobalState.FALLA
    assert cliente.post("/fault/reset").status_code == 200
    assert flags.get_flag("RESET_FALLA") is True
    assert _eventos(ctx, "falla_reconocida")


def test_fault_reset_fuera_de_falla_409(entorno):
    cliente, _, _, flags = entorno
    r = cliente.post("/fault/reset")
    assert r.status_code == 409 and r.json()["codigo"] == "estado_no_permitido"
    assert not flags.get_flag("RESET_FALLA")


def test_fault_reset_con_paro_activo_409_sin_guardar(entorno):
    cliente, ctx, _, flags = entorno
    ctx.estado.get_machine_state.return_value = GlobalState.FALLA
    flags.set_flag("PARO_EMERGENCIA", True)
    r = cliente.post("/fault/reset")
    assert r.status_code == 409 and r.json()["codigo"] == "paro_emergencia"
    assert not flags.get_flag("RESET_FALLA")


@pytest.mark.parametrize("fase,reset", [
    ("SENSOR_AUSENTE", True),            # OPC-22: antes no se reconocía
    ("FALLO_PRES_BAJA", True),
    ("EMERGENCIA", True),
    ("COMPLETADO", False),
    ("CANCELADO", False),
])
def test_acknowledge_reconoce_todo_resultado_fallo(entorno, fase, reset):
    cliente, ctx, _, flags = entorno
    ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    ctx.estado.fase_ciclo = fase
    assert cliente.post("/cycle/acknowledge").status_code == 200
    assert flags.get_flag("CICLO_CONFIRMADO") is True
    assert flags.get_flag("RESET_FALLA") is reset
    assert bool(_eventos(ctx, "falla_reconocida")) is reset


def test_acknowledge_con_paro_activo_409_sin_guardar(entorno):
    cliente, ctx, _, flags = entorno
    ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    ctx.estado.fase_ciclo = "EMERGENCIA"
    flags.set_flag("PARO_EMERGENCIA", True)
    r = cliente.post("/cycle/acknowledge")
    assert r.status_code == 409 and r.json()["codigo"] == "paro_emergencia"
    assert not flags.get_flag("CICLO_CONFIRMADO") and not flags.get_flag("RESET_FALLA")


def test_acknowledge_fuera_de_ciclo_409(entorno):
    cliente, _, _, _ = entorno
    assert cliente.post("/cycle/acknowledge").status_code == 409


def test_falla_descarta_el_reset_pedido_con_el_paro_activo():
    """OPC-23: soltar el paro no hace avanzar la máquina sin un nuevo reconocimiento."""
    flags = Flags()
    falla = FallaState(flags, MagicMock(), MagicMock())
    flags.set_flag("PARO_EMERGENCIA", True)
    flags.set_flag("RESET_FALLA", True)
    assert falla.run() is False
    assert flags.get_flag("RESET_FALLA") is False
    flags.set_flag("PARO_EMERGENCIA", False)      # se suelta el paro
    assert falla.run() is False                   # sigue en FALLA
    flags.set_flag("RESET_FALLA", True)           # nuevo reconocimiento
    assert falla.run() is True


# ── T-19 en el backend (SEN-02) ───────────────────────────────────────────────

def test_status_sin_temperatura_de_chaqueta(entorno):
    from autoclave.core.runtime.status import EstadoAutoclave
    cliente, ctx, _, _ = entorno
    estado = EstadoAutoclave()
    estado.update({"temperature": [121.0, 120.5, 119.0, 99.9, 60.0, 40.0]})
    ctx.estado = estado
    temperatura = cliente.get("/status").json()["sensors"]["temperature"]
    assert "chaqueta" not in temperatura
    # temp_drenaje ocupa la posición 4 (temp_drenaje_cam ya no existe, 2026-10-12)
    assert "drenaje_camara" not in temperatura and temperatura["drenaje"] == 60.0


def test_calibracion_por_nombre_sin_chaqueta_y_sin_correr_indices(entorno):
    _, _, _, _ = entorno
    from autoclave.backend import server
    assert server._resolve_sensor_index("temperature", "temp_drenaje") == 4
    with pytest.raises(Exception) as e:
        server._resolve_sensor_index("temperature", "temp_chaqueta")
    assert getattr(e.value, "status_code", None) == 404


# ── Revisión de seguridad y temporización de la etapa 2 ───────────────────────

@pytest.mark.parametrize("atributo,codigo", [("test_mode_active", "modo_prueba_activo"),
                                             ("desconectado", "sin_conexion_tarjeta")])
def test_puertas_rechazadas_en_modo_prueba_o_sin_tarjeta(entorno, atributo, codigo):
    """SAF-04: la orden quedaría pendiente y se ejecutaría sin revalidar."""
    cliente, ctx, est, _ = entorno
    setattr(ctx.control_loop, atributo, True)
    r = _abrir(cliente)
    assert r.status_code == 409 and r.json()["codigo"] == codigo
    assert est.puertas["Puerta 1"] == DoorState.CERRADO


def test_puertas_rechazadas_con_paro_de_emergencia(entorno):
    cliente, _, est, flags = entorno
    flags.set_flag("PARO_EMERGENCIA", True)
    r = _abrir(cliente)
    assert r.status_code == 409 and r.json()["detail"] == "Paro de emergencia activado"
    assert est.puertas["Puerta 1"] == DoorState.CERRADO


def test_acknowledge_a_mitad_de_ciclo_409_sin_guardar(entorno):
    """TMG-03/SAF-07: antes quedaba guardado y la máquina salía al terminar."""
    cliente, ctx, _, flags = entorno
    ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    ctx.estado.fase_ciclo = "ESTERILIZACION"
    r = cliente.post("/cycle/acknowledge")
    assert r.status_code == 409 and r.json()["codigo"] == "sin_resultado"
    assert not flags.get_flag("CICLO_CONFIRMADO")


def test_fault_reset_en_modo_prueba_409(entorno):
    """TMG-07: el reconocimiento se aplicaría al salir del modo prueba."""
    cliente, ctx, _, flags = entorno
    ctx.estado.get_machine_state.return_value = GlobalState.FALLA
    ctx.control_loop.test_mode_active = True
    r = cliente.post("/fault/reset")
    assert r.status_code == 409 and r.json()["codigo"] == "modo_prueba_activo"
    assert not flags.get_flag("RESET_FALLA")

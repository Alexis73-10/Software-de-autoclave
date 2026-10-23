"""S9 (tanda 9) — correcciones de la revisión ★ pasada 3
(R3-A1, R3-M1 y el Medio (b) de la configuración atmosférica).

- R3-A1: ejecutar() con la trama AI vencida deja la decisión inicial
  PENDIENTE, con todo cerrado; la toma el primer update() con la AI vigente
  (_presurizado_al_disparo, timeout de escalada, paso del modo, vacío).
- R3-M1: el NO ABRIR de /status usa presion_vigente (DI + AI).
- (b): sin presión atmosférica de referencia configurada no se abre el aire
  atmosférico.
"""

from unittest.mock import MagicMock

from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.state_machine.cycle_phases.protocolo_fallo import ProtocoloFallo
from tests.test_s9_estado_seguro_arranque import _CFG, _Config, _abiertas, _programa


def _protocolo(pres=250.0, temp=120.0, modo=2, tipo="solido", ai=(False, None), cfg=None):
    estado = EstadoAutoclave()
    estado.sensores_pres["pres_camara"] = pres
    estado.sensores_temp["temp_camara"] = temp
    set_do = MagicMock()
    set_do.reset_all_outputs.return_value = True
    prot = ProtocoloFallo(estado, set_do, _programa(modo=modo, tipo=tipo),
                          _Config(_CFG if cfg is None else cfg))
    lectura = {"v": ai}
    prot.lectura_ai = lambda: lectura["v"]
    return prot, estado, set_do, lectura


def _llamadas(set_do):
    return [c[0] for c in set_do.method_calls]


# ── R3-A1 ──────────────────────────────────────────────────────────────────

def test_cancelacion_con_ai_vencida_liquido_modo4_presurizado_contrapresion_al_volver():
    """Cancelación con la AI vencida, carga líquida modo 4 y cámara
    presurizada: nada se abre mientras tanto; al volver la AI, contrapresión
    (aire comprimido) y la lenta cerrada."""
    prot, estado, set_do, lectura = _protocolo(pres=250.0, temp=120.0, modo=4, tipo="liquido")
    prot.ejecutar()
    assert not _abiertas(set_do)
    for _ in range(3):
        prot.update()
    assert not _abiertas(set_do)
    lectura["v"] = (True, None)
    estado.sensores_pres["pres_camara"] = 150.0          # bajo la contrapresión de 200
    prot.update()
    prot.update()
    assert prot._presurizado_al_disparo is True
    abiertas = _abiertas(set_do)
    assert "aire_comprimido_camara_on" in abiertas
    assert "descompresion_lenta_on" not in abiertas


def test_solido_con_ai_vencida_al_disparo_arma_el_timeout_al_volver():
    prot, estado, set_do, lectura = _protocolo(pres=250.0, modo=2)
    prot.ejecutar()
    assert prot._t_timeout_descompresion is None
    lectura["v"] = (True, None)
    prot.update()
    assert prot._presurizado_al_disparo is True
    assert prot._t_timeout_descompresion is not None
    assert "descompresion_lenta_on" in _abiertas(set_do)


def test_paro_con_ai_vencida_marca_presurizado_y_reanudar_arma_el_timeout():
    """abrir_valvulas=False (paro): al volver la AI se marca presurizado; si
    ya se reanudó, el timeout se arma entonces."""
    prot, estado, set_do, lectura = _protocolo(pres=250.0, modo=2)
    prot.ejecutar(abrir_valvulas=False)
    prot.reanudar()
    lectura["v"] = (True, None)
    prot.update()
    assert prot._presurizado_al_disparo is True
    assert prot._t_timeout_descompresion is not None


def test_decision_pendiente_en_vacio_cuenta_el_vacio_al_volver():
    prot, estado, set_do, lectura = _protocolo(pres=20.0, temp=30.0)
    prot.ejecutar()
    lectura["v"] = (True, None)
    prot.update()
    assert "aire_admosferico_camara_on" not in _abiertas(set_do)
    prot.update(); prot.update()
    assert "aire_admosferico_camara_on" in _abiertas(set_do)


def test_ejecutar_con_ai_vigente_sin_cambio():
    prot, estado, set_do, _ = _protocolo(pres=250.0, modo=2, ai=(True, None))
    prot.ejecutar()
    assert prot._presurizado_al_disparo is True
    assert prot._t_timeout_descompresion is not None
    assert "descompresion_lenta_on" in _abiertas(set_do)


# ── (b) sin referencia atmosférica configurada ─────────────────────────────

def test_sin_referencia_atmosferica_no_abre_el_aire():
    prot, estado, set_do, _ = _protocolo(pres=75.0, temp=30.0, ai=(True, None),
                                         cfg={"temp_max_apertura": 80.0})
    prot.ejecutar(abrir_valvulas=False, solo_lenta=True)
    for _ in range(5):
        prot.update()
    assert "aire_admosferico_camara_on" not in _abiertas(set_do)


def test_con_referencia_atmosferica_si_abre_el_aire_en_vacio():
    prot, estado, set_do, _ = _protocolo(pres=20.0, temp=30.0, ai=(True, None))
    prot.ejecutar(abrir_valvulas=False, solo_lenta=True)
    for _ in range(3):
        prot.update()
    assert "aire_admosferico_camara_on" in _abiertas(set_do)


# ── R3-M1: NO ABRIR de /status con la presión vigente ──────────────────────

def test_status_no_abrir_usa_presion_vigente():
    from tests.backend_doble import cargar_servidor
    ctx = MagicMock()
    estado = EstadoAutoclave()
    estado.sensores_pres["pres_camara"] = 101.3
    estado.sensores_temp["temp_camara"] = 30.0
    ctx.config_manager = _Config(_CFG)
    ctx.programas_para_seguridad.return_value = []
    ctx.temp_max_tras_ciclo.return_value = None
    ctx.profile = None
    ctx.control_loop.datos_vigentes = True
    ctx.control_loop.presion_vigente = False          # AI vencida
    srv, _ = cargar_servidor(ctx)
    assert srv._camara_segura_status(estado)["no_abrir"] is True
    ctx.control_loop.presion_vigente = True
    assert srv._camara_segura_status(estado)["no_abrir"] is False

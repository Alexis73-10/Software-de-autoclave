"""Tanda 28 (A13, Cristian 5-nov): secado corto tras un ciclo fallido.

Con carga sólida, equipo con bomba de vacío y programa con secado, cuando el
protocolo de fallo lleva la cámara a la banda atmosférica, antes de que el
estado seguro cuente sus 3 lecturas seguras:
  (a) SECADO: bomba + vacío, todo vapor y escapes cerrados, secado_tras_fallo_s;
  (b) RUPTURA: bomba y vacío apagados (escalonado) y aire atmosférico hasta la
      banda atmosférica, con tiempo límite.
No corre (y queda anotado) con carga líquida, sin bomba, con el sistema de
vacío en falla, con el parámetro en 0...; un paro, una puerta abierta o el
modo prueba lo cortan y no se reanuda solo.

Piezas reales: ProtocoloFallo; salidas en un doble que guarda el último valor
ordenado.

Unión con el hotfix ES (6-nov, D4/D6): sin ProtocoloEstadoSeguro. El secado
corre en el ProtocoloFallo de CicloState mientras espera la confirmación:
`_Equipo.tick` hace lo mismo que el paso 0 de CicloState con el resultado
pendiente (paro → apagar_por_paro + cortar_secado("paro"); si no,
protocolo.update()) y registra los eventos con el ControlLoop real
(`_seguir_secado_tras_fallo`). Se retiraron las aserciones del estado seguro
(activo, 3 lecturas, motivo pendiente): NO ABRIR lo dice camara_segura (M4).
"""

import time
from datetime import datetime

import pytest

from autoclave.core.managers.cycle_manager import Cycle
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.installation import profile as perfil_mod
from autoclave.installation.equipment import EquipmentClass
from autoclave.installation.profile import DoorType, InstallationProfile, Role, vacio_instalado
from autoclave.state_machine.cycle_phases import protocolo_fallo as pf
from autoclave.state_machine.cycle_phases.protocolo_fallo import ProtocoloFallo
from types import SimpleNamespace

from autoclave.core.runtime import camara_segura
from autoclave.services.domain.loop.control_loop import ControlLoop

ATM, RANGO = 101.3, 5.0
VACIO = ("bomba_vacio", "vacio_camara")
VAPOR_Y_ESCAPES = ("vapor_camara", "vapor_chaqueta", "descompresion_rapida",
                   "descompresion_lenta", "descompresion_chaqueta", "aire_comprimido_camara")


class _Config(dict):
    def get(self, k, d=None):
        return super().get(k, d)


class _Salidas:
    """Doble de SetOutput: `estado[salida]` = última orden; `historial` =
    lista de (salida, valor) en orden."""

    def __init__(self):
        self.estado = {}
        self.historial = []

    def __getattr__(self, nombre):
        if nombre.endswith("_on") or nombre.endswith("_off"):
            salida, valor = nombre.rsplit("_", 1)
            salida = "aire_atmosferico_camara" if salida == "aire_admosferico_camara" else salida

            def orden():
                self.estado[salida] = (valor == "on")
                self.historial.append((salida, valor == "on"))
            return orden
        raise AttributeError(nombre)

    def reset_all_outputs(self):
        for k in list(self.estado):
            self.estado[k] = False
        self.historial.append(("ALL_OFF", False))
        return True

    def apagar_por_paro(self):
        return self.reset_all_outputs()

    def buzer_fallo(self):
        pass

    def on(self, salida):
        return self.estado.get(salida) is True


class _Alarmas:
    def __init__(self):
        self.codigos = []

    def activas(self):
        return [type("I", (), {"codigo": c})() for c in self.codigos]

    def activar(self, *a, **k):
        pass

    def resolver(self, *a, **k):
        pass


def _perfil(puertas=2):
    return InstallationProfile(
        machine_id="TEST-001", model_id="MX-TEST", serial_number="ACV-TEST",
        equipment_class=EquipmentClass.PISO, door_count=puertas, door_type=DoorType.ADVANCED,
        cooling_level=0, door_id=1, role=Role.OPERATOR_FRONT,
        created_at=datetime(2026, 1, 1), locked=False,
    )


def _programa(tipo="solido", secado_modo=1, tiempo_secado=2.0):
    prog = Cycle("p", "p", {
        "globals": {"tipo_carga": {"value": tipo}},
        "descompresion": {"modo": {"value": 1}},
        "secado": {"modo": {"value": secado_modo}, "tiempo_secado": {"value": tiempo_secado}},
        "finalizacion": {"temp_max_apertura": {"value": 80.0}},
    }, number=1)
    prog.sensores = {"temp_camara": "principal", "temp_2_camara": "no_en_uso",
                     "temp_ref": "no_en_uso"}
    return prog


class _Equipo:
    def __init__(self, monkeypatch, tipo="solido", con_bomba=True, segundos=60,
                 secado_modo=1, puertas=2):
        self.reloj = [1000.0]
        monkeypatch.setattr(time, "monotonic", lambda: self.reloj[0])
        monkeypatch.setattr(perfil_mod, "vacio_instalado", lambda profile: con_bomba)
        self.estado = EstadoAutoclave()
        self.estado.set_flag("PARO_EMERGENCIA", False)
        self.estado.sensores_pres["pres_camara"] = ATM
        self.estado.sensores_temp["temp_camara"] = 70.0
        for n in range(1, puertas + 1):
            self.estado.sensores_di[f"puerta_{n}_cerrada"] = 1
        self.estado.sensores_di["agua_bomba"] = 1       # agua de sello presente
        self.config = _Config({"presion_admosferica": ATM, "rango_presion_atm": RANGO,
                               "temp_max_apertura": 80.0, "secado_tras_fallo_s": segundos})
        self.salidas = _Salidas()
        self.alarmas = _Alarmas()
        self.programa = _programa(tipo, secado_modo)
        self.protocolo = ProtocoloFallo(self.estado, self.salidas, self.programa, self.config)
        self.protocolo.profile = _perfil(puertas)
        self.protocolo.alarm_manager = self.alarmas
        self.eventos = []
        # ControlLoop._seguir_secado_tras_fallo (real) sobre un doble mínimo
        self._registro = SimpleNamespace(
            state_machine=SimpleNamespace(ciclo=SimpleNamespace(_protocolo=self.protocolo)),
            _secado_visto=None,
            _evento_seguridad=lambda ev, det: self.eventos.append((ev, det)))

    def disparar(self, origen="fallo", **kw):
        self.protocolo.ejecutar(**kw)

    def tick(self, dt=0.25):
        """Un tick de CicloState con el resultado FALLO/CANCELADO pendiente."""
        if self.estado.get_flag("PARO_EMERGENCIA"):
            self.salidas.apagar_por_paro()
            self.protocolo.cortar_secado("paro")
        else:
            self.protocolo.update()
        ControlLoop._seguir_secado_tras_fallo(self._registro)
        self.reloj[0] += dt

    def salir_de_ciclo(self):
        """Confirmación: StateMachine._finalizar_protocolo_ciclo."""
        self.protocolo.finalizar()
        ControlLoop._seguir_secado_tras_fallo(self._registro)

    def no_abrir(self):
        return camara_segura.evaluar(self.estado, self.config, [self.programa])[0] is False

    def motivo_no_abrir(self):
        return getattr(camara_segura.evaluar(self.estado, self.config, [self.programa])[1],
                       "codigo", None)

    def pres(self, valor):
        self.estado.sensores_pres["pres_camara"] = valor

    def resultado(self):
        return self.protocolo.secado_resultado


# ── recorrido completo ─────────────────────────────────────────────────────

@pytest.mark.parametrize("origen", ["fallo", "cancelado"])
def test_fallo_solido_vacio_60s_ruptura_y_estado_seguro_despues(monkeypatch, origen):
    e = _Equipo(monkeypatch)
    e.disparar(origen=origen)
    assert e.resultado()["estado"] == "pendiente"
    e.tick()                                         # llega a la banda: empieza el secado
    assert e.protocolo.secando
    assert all(e.salidas.on(s) for s in VACIO)
    assert not any(e.salidas.on(s) for s in VAPOR_Y_ESCAPES + ("aire_atmosferico_camara",))
    assert e.motivo_no_abrir() == "secando_vapor_residual"
    e.pres(20.0)                                     # el vacío baja la presión
    t0 = e.reloj[0]
    while e.reloj[0] - t0 < 59.5:
        e.tick()
        assert e.no_abrir() and e.protocolo.secando
        assert all(e.salidas.on(s) for s in VACIO)
        assert not e.salidas.on("aire_atmosferico_camara")
    while e.protocolo._secado_fase == "secado":
        e.tick()
    # apagado escalonado: primero la bomba, luego el vacío
    assert not e.salidas.on("bomba_vacio") and e.salidas.on("vacio_camara")
    e.tick(dt=0.2)
    e.tick()
    assert not any(e.salidas.on(s) for s in VACIO)
    assert e.protocolo._secado_fase == "ruptura" and e.salidas.on("aire_atmosferico_camara")
    for _ in range(10):                              # sin llegar a la banda, sigue
        e.tick()
        assert e.no_abrir() and e.protocolo.secando
    e.pres(ATM)                                      # ruptura completa
    e.tick()
    assert not e.protocolo.secando and not e.salidas.on("aire_atmosferico_camara")
    assert e.resultado() == {"estado": "hecho", "motivo": None, "segundos": 60}
    assert not e.no_abrir()                          # recién ahora la cámara es segura
    eventos = [ev for ev, _ in e.eventos]
    assert eventos.index("estado_seguro_secado_iniciado") < eventos.index(
        "estado_seguro_secado_terminado")
    e.salir_de_ciclo()                               # D6: el resultado final no cambia
    assert e.resultado()["estado"] == "hecho"
    # nunca vapor ni escapes abiertos durante el secado tras fallo
    assert not any(e.salidas.on(s) for s in VAPOR_Y_ESCAPES)


def test_no_abrir_hasta_terminar_la_ruptura(monkeypatch):
    """Aunque la cámara parezca segura (presión en banda, temperatura baja)
    durante el secado y la ruptura, NO ABRIR sigue (M4)."""
    e = _Equipo(monkeypatch, segundos=5)
    e.config["secado_tras_fallo_vacio_s"] = 2        # A13-M3: vacío sostenido 2 s
    e.disparar()
    e.tick()
    e.pres(ATM - RANGO - 1.0)                        # vacío apenas bajo la banda
    ticks = 0
    while e.protocolo.secando:                       # secado, apagado y ruptura
        assert e.motivo_no_abrir() == "secando_vapor_residual"
        if e.protocolo._secado_fase == "ruptura":
            e.pres(ATM)                              # la ruptura vuelve a la banda
        e.tick()
        ticks += 1
        assert ticks < 100
    assert ticks >= 5 / 0.25                         # duró al menos los 5 s
    # ruptura con la presión ya en la banda: terminó; recién ahora es segura
    assert e.resultado()["estado"] == "hecho" and not e.no_abrir()


def test_ruptura_que_no_llega_a_la_banda_sigue_con_aviso(monkeypatch):
    e = _Equipo(monkeypatch, segundos=1)
    e.disparar()
    e.tick()
    e.pres(20.0)
    for _ in range(int((pf._RUPTURA_LIMITE_S + 5) / 0.25)):
        e.tick()
        if not e.protocolo.secando:
            break
    assert e.resultado()["estado"] == "sin_ruptura"
    assert e.no_abrir()                              # protocolo normal: cámara en vacío


# ── cuándo no corre ────────────────────────────────────────────────────────

def _nunca_vacio(e, ticks=20):
    for _ in range(ticks):
        e.tick()
        assert not any(e.salidas.on(s) for s in VACIO)
        assert not e.protocolo.secando


def test_carga_liquida_no_corre(monkeypatch):
    e = _Equipo(monkeypatch, tipo="liquido")
    e.disparar()
    _nunca_vacio(e)
    assert e.resultado()["estado"] == "omitido" and e.resultado()["motivo"] == "carga_liquida"


def test_tipo_de_carga_ilegible_es_liquida(monkeypatch):
    e = _Equipo(monkeypatch, tipo="SOLIDO")
    e.disparar()
    _nunca_vacio(e)
    assert e.resultado()["motivo"] == "carga_liquida"


def test_sin_bomba_en_el_perfil_no_corre(monkeypatch):
    e = _Equipo(monkeypatch, con_bomba=False)
    e.disparar()
    _nunca_vacio(e)
    assert e.resultado()["motivo"] == "sin_bomba"


def test_programa_sin_secado_no_corre(monkeypatch):
    e = _Equipo(monkeypatch, secado_modo=0)
    e.disparar()
    _nunca_vacio(e)
    assert e.resultado()["motivo"] == "sin_secado_programa"


@pytest.mark.parametrize("codigo", ["CIC-02", "CIC-06"])
def test_fallo_del_sistema_de_vacio_no_corre(monkeypatch, codigo):
    e = _Equipo(monkeypatch)
    e.estado.codigo_fallo = codigo
    e.disparar()
    _nunca_vacio(e)
    assert e.resultado()["motivo"] == "fallo_vacio"


@pytest.mark.parametrize("forma", ["alarma", "di"])
def test_sin_agua_de_la_bomba_no_corre(monkeypatch, forma):
    e = _Equipo(monkeypatch)
    if forma == "alarma":
        e.alarmas.codigos = ["SUM-03"]
    else:
        e.estado.sensores_di["agua_bomba"] = 0
    e.disparar()
    _nunca_vacio(e)
    assert e.resultado()["motivo"] == "fallo_vacio"


def test_parametro_en_cero_lo_desactiva(monkeypatch):
    e = _Equipo(monkeypatch, segundos=0)
    e.disparar()
    _nunca_vacio(e)
    assert e.resultado()["motivo"] == "desactivado"


def test_completado_no_hace_secado(monkeypatch):
    e = _Equipo(monkeypatch)
    e.disparar(origen="completado", secado_tras_fallo=False)
    _nunca_vacio(e)
    assert e.resultado()["motivo"] == "no_aplica"


def test_puerta_no_confirmada_al_llegar_no_corre(monkeypatch):
    e = _Equipo(monkeypatch)
    e.estado.sensores_di["puerta_2_cerrada"] = None
    e.disparar()
    _nunca_vacio(e)
    assert e.resultado()["motivo"] == "puerta_abierta"


def test_principal_sin_lectura_al_llegar_no_corre(monkeypatch):
    e = _Equipo(monkeypatch)
    e.estado.sensores_temp["temp_camara"] = None
    e.disparar()
    _nunca_vacio(e, ticks=2)
    assert e.resultado()["motivo"] == "sin_principal"


# ── cortes durante el secado ───────────────────────────────────────────────

def _en_secado(monkeypatch, **kw):
    e = _Equipo(monkeypatch, **kw)
    e.disparar()
    e.tick()
    e.pres(30.0)
    for _ in range(8):
        e.tick()
    assert e.protocolo.secando and all(e.salidas.on(s) for s in VACIO)
    return e


def test_paro_durante_el_secado_lo_corta_y_no_se_reanuda(monkeypatch):
    e = _en_secado(monkeypatch)
    e.estado.set_flag("PARO_EMERGENCIA", True)
    e.tick()
    assert not any(e.salidas.on(s) for s in VACIO)
    assert e.resultado()["estado"] == "cortado" and e.resultado()["motivo"] == "paro"
    e.estado.set_flag("PARO_EMERGENCIA", False)      # liberado (sin PARO_REAL: sin confirmación)
    n = len(e.salidas.historial)
    for _ in range(40):
        e.tick()
    assert ("bomba_vacio", True) not in e.salidas.historial[n:]
    assert ("vacio_camara", True) not in e.salidas.historial[n:]
    assert not e.protocolo.secando


def test_paro_visto_por_el_propio_protocolo_tambien_corta(monkeypatch):
    """Defensa: aunque quien lo llame no corte antes, el protocolo mira el paro."""
    e = _en_secado(monkeypatch)
    e.estado.set_flag("PARO_EMERGENCIA", True)
    e.protocolo.update()
    assert not any(e.salidas.on(s) for s in VACIO)
    assert e.resultado()["motivo"] == "paro"


def test_puerta_que_se_abre_lo_corta(monkeypatch):
    e = _en_secado(monkeypatch)
    e.estado.sensores_di["puerta_1_cerrada"] = 0
    e.tick()
    assert not any(e.salidas.on(s) for s in VACIO)
    assert e.resultado()["motivo"] == "puerta_abierta"


def test_falla_del_agua_de_la_bomba_lo_corta(monkeypatch):
    e = _en_secado(monkeypatch)
    e.alarmas.codigos = ["SUM-03"]
    e.tick()
    assert not any(e.salidas.on(s) for s in VACIO)
    assert e.resultado()["motivo"] == "fallo_vacio"


# Unión hotfix ES: se retiraron test_modo_prueba_lo_corta y
# test_datos_no_vigentes_lo_cortan (los cortaba el protocolo de estado seguro;
# en CICLO no se entra al modo prueba y la trama AI vencida la cubre
# test_b4_ai_vencida_vista_por_el_protocolo_corta_el_secado de A13r).


def test_presion_sin_lectura_lo_corta(monkeypatch):
    e = _en_secado(monkeypatch)
    e.pres(None)
    e.tick()
    assert not any(e.salidas.on(s) for s in VACIO)
    assert e.resultado()["motivo"] == "sin_presion"


def test_un_parametro_cambiado_en_vuelo_rige_al_empezar(monkeypatch):
    e = _Equipo(monkeypatch, segundos=60)
    e.disparar()
    e.config["secado_tras_fallo_s"] = 2
    e.tick()
    assert abs((e.protocolo._secado_t_fin - e.protocolo._secado_t0) - 2) < 1e-6


def test_parametro_invalido_usa_el_defecto(monkeypatch):
    e = _Equipo(monkeypatch, segundos=999)
    assert e.protocolo._segundos_secado() == pf.SECADO_DEFECTO_S


# ── perfil ─────────────────────────────────────────────────────────────────

def test_vacio_instalado_exige_capacidad_y_las_dos_salidas():
    io_ok = {"DO": ["bomba_vacio", "vacio_camara"], "AI": [], "DI": []}
    assert vacio_instalado(_perfil(), io_ok) is True
    assert vacio_instalado(_perfil(), {"DO": ["bomba_vacio"]}) is False
    assert vacio_instalado(None, io_ok) is False
    sin_vacio = _perfil(puertas=1)
    sin_vacio.equipment_class = EquipmentClass.MESA_SIMPLE if hasattr(
        EquipmentClass, "MESA_SIMPLE") else list(EquipmentClass)[0]
    from autoclave.installation.equipment import get_capabilities
    if not get_capabilities(sin_vacio.equipment_class).has_vacuum:
        assert vacio_instalado(sin_vacio, io_ok) is False


# ── ticket, historial y pantalla ───────────────────────────────────────────

def _p(idioma="es"):
    from autoclave.services.domain.logging.ticket_formatter import Presentacion
    return Presentacion(idioma=idioma)


@pytest.mark.parametrize("resultado, es, en", [
    ({"estado": "hecho", "segundos": 60, "motivo": None},
     "Secado tras fallo: 60 s", "Drying after failure: 60 s"),
    ({"estado": "omitido", "segundos": None, "motivo": "carga_liquida"},
     "Secado tras fallo: omitido (carga líquida)", "Drying after failure: skipped (liquid load)"),
    ({"estado": "cortado", "segundos": 12, "motivo": "paro"},
     "Secado tras fallo: cortado a los 12 s (paro de emergencia)",
     "Drying after failure: stopped after 12 s (emergency stop)"),
])
def test_linea_del_ticket(resultado, es, en):
    from autoclave.services.domain.logging import ticket_formatter as tf
    aviso = tf.aviso_secado_tras_fallo(resultado)
    assert es in tf.format_footer("FALLO_CALENTAMIENTO", "2026-11-05T10:00:00",
                                  avisos=[aviso], p=_p("es"))
    assert en in tf.format_footer("FALLO_CALENTAMIENTO", "2026-11-05T10:00:00",
                                  avisos=[aviso], p=_p("en"))


def test_aviso_ilegible_no_va_al_ticket():
    from autoclave.services.domain.logging import ticket_formatter as tf
    assert tf.aviso_secado_tras_fallo(None) is None
    assert tf.aviso_secado_tras_fallo({"estado": "otro"}) is None


def test_el_resultado_conocido_despues_del_cierre_se_guarda_en_la_base():
    from autoclave.services.domain.logging import ticket_formatter as tf
    from autoclave.services.domain.logging.cycle_logger import CycleLogger, _RegistroBD

    class _Db:
        def __init__(self):
            self.escrito = None

        def actualizar_avisos_ticket(self, ciclo_id, datos):
            self.escrito = (ciclo_id, datos)

    logger = CycleLogger.__new__(CycleLogger)
    logger.estado = EstadoAutoclave()
    logger.db = _Db()
    logger._ejecutar_bd = lambda tarea: tarea()
    reg = _RegistroBD()
    reg.id = 7
    pendiente = tf.aviso_secado_tras_fallo({"estado": "pendiente"})
    logger._secado_pendiente = (reg, {"sin_datos_s": None, "avisos": ["otro", pendiente]})
    logger.estado.secado_tras_fallo = {"estado": "pendiente", "motivo": None, "segundos": None}
    logger._seguir_secado_tras_fallo()
    assert logger.db.escrito is None and logger._secado_pendiente is not None
    logger.estado.secado_tras_fallo = {"estado": "hecho", "motivo": None, "segundos": 60}
    logger._seguir_secado_tras_fallo()
    ciclo_id, datos = logger.db.escrito
    assert ciclo_id == 7 and datos["avisos"][0] == "otro"
    assert datos["avisos"][1]["estado"] == "hecho" and datos["avisos"][1]["segundos"] == 60
    assert logger._secado_pendiente is None


def test_db_actualiza_avisos_ticket(tmp_path):
    from autoclave.services.domain.logging.db_manager import DbManager
    from autoclave.services.domain.logging.ticket_formatter import leer_avisos_ticket
    db = DbManager(tmp_path / "a13.db")
    cid = db.crear_ciclo(1, "p", "p", 134, 3.5, "M", "S", "1")
    db.cerrar_ciclo(cid, "FALLO_CALENTAMIENTO", avisos_ticket={"avisos": ["x"]})
    db.actualizar_avisos_ticket(cid, {"sin_datos_s": None, "avisos": ["x", {"clave": "k"}]})
    fila = db.get_ciclo(cid) if hasattr(db, "get_ciclo") else None
    if fila is None:
        fila = dict(db._conn.execute("SELECT avisos_ticket FROM ciclos WHERE id=?",
                                     (cid,)).fetchone())
    assert leer_avisos_ticket(fila["avisos_ticket"])[1] == ["x", {"clave": "k"}]

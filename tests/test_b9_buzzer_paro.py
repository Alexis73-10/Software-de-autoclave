"""B9 (tanda 9, D9-9): buzzer y paro de emergencia.

Evidencia de banco (Cristian): con el paro activo, cada vez que el buzzer
reinicia su patrón se encienden un instante las salidas que estaban activas al
pulsar el paro.

Banco simulado: SerialLink real (con el doble de puerto de tests/serial_doble)
conectado a un doble del firmware V3 que reproduce el .ino línea a línea en lo
que importa aquí (registro sombra estadoOut1/estadoOut2, SET DOn, ALL_OFF,
publicación de DO cada 500 ms), SetOutput real, BuzzerPlayer real y los
estados reales; el tick reproduce el orden de ControlLoop._tick (puertas →
máquina de estados → buzzer) con el intervalo de producción (0,5 s). Se
registran todas las órdenes SET/ALL_OFF que salen al puerto y el estado de los
pines de la tarjeta después de cada orden.

Con B9_ESCRIBIR_REGISTRO=1 escribe el registro en
docs/informes/tanda9/B9_registro_ordenes.md."""

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.devices.io import set_io
from autoclave.devices.io.set_io import SetOutput
from autoclave.devices.puertas.advanced_door import AdvancedDoor, DoorState
from autoclave.devices.buzer import buzer as buzer_mod
from autoclave.protocols import serial_link as sl_mod
from autoclave.protocols.serial_link import SerialLink
from autoclave.protocols.serial_link_config import SerialLinkConfig
from autoclave.state_machine.states.preparacion import preparacion_state
from autoclave.state_machine.states.preparado import preparado_state
from autoclave.state_machine.states.falla import FallaState
from tests.serial_doble import PuertoDoble, linea

TICK = 0.5          # ControlLoop.interval de producción
BUZZER = EstadoAutoclave.map_do["buzer_alarma"] + 1


class FirmwareV3:
    """Doble del firmware Comunicacion_esclava_ESP32_V3.ino (registro sombra,
    procesarSet, apagarTodo, publicarEstados). Pines activos en bajo como en
    la tarjeta: aquí se guarda directamente 1 = salida encendida."""

    def __init__(self, link, reloj, registro):
        self.link = link
        self.reloj = reloj
        self.registro = registro
        self.sombra = [False] * 32      # estadoOut1/estadoOut2 (True = ON)
        self.pines = [False] * 32       # lo que escribió el último write16
        self.sincronizado = True
        self.encendidos_no_buzzer = []  # (t, canal, orden) tras el paro

    def _write16(self, expansor):
        base = 0 if expansor == 1 else 16
        for i in range(16):
            self.pines[base + i] = self.sombra[base + i]

    def recibir(self, payload):
        t = self.reloj[0]
        responder = [linea("ACK")]
        if payload == "ALL_OFF":
            self.sombra = [False] * 32
            self._write16(1)
            self._write16(2)
            self.sincronizado = True
            responder.append(linea("OK ALL_OFF"))
        elif payload.startswith("SET DO"):
            n, est = payload[6:].split(" ")
            n = int(n)
            on = est == "ON"
            if self.sincronizado:
                self.sombra[n - 1] = on
                self._write16(1 if n <= 16 else 2)
                responder.append(linea(f"OK DO{n} {est}"))
        encendidos = [c + 1 for c, v in enumerate(self.pines) if v]
        self.registro.append((t, payload, encendidos))
        # La respuesta llega por el lector; aquí, en línea (sin hilo)
        for r in responder:
            self.link._alimentar(r)

    def publicar_do(self):
        bits = "".join("1" if v else "0" for v in self.sombra)
        self.link._alimentar(linea("DO:" + bits))


def _armar(monkeypatch):
    reloj = [1000.0]
    for mod in (set_io, sl_mod, buzzer_mod_time()):
        monkeypatch.setattr(mod.time, "monotonic", lambda: reloj[0])
    estado = EstadoAutoclave()
    for di in estado.sensores_di:
        estado.sensores_di[di] = 1
    link = SerialLink(config=SerialLinkConfig())
    link._rx_buf = bytearray()
    puerto = PuertoDoble()
    link.serial = puerto
    link.data["port_open"] = True
    link._handshake_ok = True
    registro = []
    fw = FirmwareV3(link, reloj, registro)
    puerto.al_escribir = fw.recibir
    set_do = SetOutput(link, estado, profile=None)
    return dict(reloj=reloj, estado=estado, link=link, fw=fw, registro=registro,
                set_do=set_do)


def buzzer_mod_time():
    return buzer_mod


def _do_reportado(a):
    """Units: el DO de la trama pasa a estado.salidas_do."""
    do = a["link"].get_state()["do"]
    for nombre, i in EstadoAutoclave.map_do.items():
        a["estado"].salidas_do[nombre] = do[i]


def _puerta(a):
    estado = a["estado"]
    estado.update_door_state("Puerta 1", DoorState.CERRADO)
    estado.sensores_di["puerta_1_abierta"] = 0
    estado.sensores_di["puerta_1_cerrada"] = 1
    estado.sensores_pres["pres_empaque_1"] = 100.0     # bajo: re-presuriza
    return AdvancedDoor(
        name="Puerta 1",
        di={"abierta": "puerta_1_abierta", "cerrada": "puerta_1_cerrada"},
        do={"cerrar": EstadoAutoclave.map_do["cerrar_puerta_1"] + 1,
            "bloquear": EstadoAutoclave.map_do["bloqueo_puerta_1"] + 1},
        ai={"presion_empaque": "pres_empaque_1"},
        estado=estado, setdo=a["set_do"],
        config={"presion_empaque": 300, "timeout_puerta": 60, "vacio_empaque": 30,
                "presion_admosferica": 74.5, "rango_presion_atm": 20},
        alarm_manager=None)


_PREVIAS = ("vapor_chaqueta", "descompresion_lenta", "agua_intercambiador",
            "aire_comprimido_camara")


def _estado_maquina(nombre, a):
    am = MagicMock()
    if nombre == "PREPARACION":
        return preparacion_state(am, a["estado"], a["set_do"], MagicMock(), MagicMock())
    if nombre == "PREPARADO":
        return preparado_state(am, a["estado"], a["set_do"], MagicMock(), MagicMock())
    return FallaState(a["estado"], a["set_do"], am)


def _correr_paro(monkeypatch, nombre_estado, con_puerta=True, segundos=15.0,
                 corregido=True):
    a = _armar(monkeypatch)
    puerta = _puerta(a) if con_puerta else None
    # Antes del paro: salidas encendidas por el control
    for n in _PREVIAS:
        getattr(a["set_do"], f"{n}_on")()
    a["fw"].publicar_do()
    _do_reportado(a)
    estado_m = _estado_maquina(nombre_estado, a)
    # Se pulsa el paro
    a["estado"].set_flag("PARO_EMERGENCIA", True)
    a["estado"].set_flag("PARO_REAL", True)
    t_paro = a["reloj"][0]
    a["registro"].append((t_paro, "--- PARO PULSADO ---", []))
    proxima_do = t_paro + 0.5
    fin = t_paro + segundos
    primero = True
    while a["reloj"][0] < fin:
        # orden de ControlLoop._tick: paso 2 (flanco del paro, D9-9) →
        # puertas → máquina de estados → buzzer
        if primero and corregido:
            a["set_do"].apagar_por_paro(inmediato=True)
        primero = False
        if puerta is not None:
            puerta.update()
        estado_m.run()
        a["set_do"].buzer.update()
        a["reloj"][0] += TICK
        while a["reloj"][0] >= proxima_do:      # publicarEstados cada 500 ms
            a["fw"].publicar_do()
            _do_reportado(a)
            proxima_do += 0.5
    return a, t_paro


def _encendidos_tras_paro(a, t_paro):
    """(t, orden, canales no buzzer encendidos en los pines) después de la
    primera orden posterior al paro."""
    marca = next(i for i, r in enumerate(a["registro"]) if r[1].startswith("---"))
    tras = a["registro"][marca + 1:]
    malos = []
    for i, (t, orden, enc) in enumerate(tras):
        otros = [c for c in enc if c != BUZZER]
        if i > 0 and otros:          # la primera orden es el ALL_OFF del paro
            malos.append((round(t - t_paro, 2), orden, otros))
    return tras, malos


REGISTROS: dict[str, list] = {}


@pytest.mark.parametrize("nombre_estado", ["PREPARACION", "PREPARADO", "FALLA"])
@pytest.mark.parametrize("con_puerta", [True, False])
def test_con_el_paro_ninguna_salida_salvo_el_buzzer_se_enciende(
        monkeypatch, nombre_estado, con_puerta):
    a, t_paro = _correr_paro(monkeypatch, nombre_estado, con_puerta)
    tras, malos = _encendidos_tras_paro(a, t_paro)
    REGISTROS[f"{nombre_estado}, puerta avanzada={con_puerta}"] = [
        (round(t - t_paro, 2), o, e) for t, o, e in a["registro"]]
    # primera orden tras el paro: ALL_OFF, y uno solo en ese tick (TMG-01)
    assert tras[0][1] == "ALL_OFF", tras[:3]
    assert [o for t, o, _ in tras if t == t_paro].count("ALL_OFF") == 1, tras[:6]
    assert not malos, malos[:10]
    # el buzzer sí suena
    assert any(o == f"SET DO{BUZZER} ON" for _, o, _ in tras)
    # solo el buzzer recibe SET ... ON
    assert all(o == f"SET DO{BUZZER} ON" for _, o, _ in tras if o.endswith(" ON"))


@pytest.mark.parametrize("nombre_estado", ["PREPARACION", "PREPARADO", "FALLA"])
def test_evidencia_sin_correccion_solo_las_puertas_se_reencienden(monkeypatch, nombre_estado):
    """Causa confirmada (código anterior a D9-9): el firmware limpia la sombra
    con el ALL_OFF (hipótesis 1 descartada) y el enlace no reenvía estados
    previos (hipótesis 2 descartada): ninguna salida de control encendida
    antes del paro vuelve a encenderse. Las que se encienden son las de la
    puerta, que AdvancedDoor.update() re-afirma en cada tick (paso 3 de
    ControlLoop), en el mismo tick que el buzzer; el ALL_OFF espaciado
    (hipótesis 3) solo decide cuánto duran."""
    monkeypatch.setattr(SetOutput, "_paro_bloquea", lambda self, index: False)
    a, t_paro = _correr_paro(monkeypatch, nombre_estado, True, corregido=False)
    puerta = {_canal_n("cerrar_puerta_1"), _canal_n("bloqueo_puerta_1")}
    previas_control = {_canal_n(n) for n in _PREVIAS}
    marca = next(i for i, r in enumerate(a["registro"]) if r[1].startswith("---"))
    primer_all_off = next(i for i, r in enumerate(a["registro"])
                          if i > marca and r[1] == "ALL_OFF")
    encendidas = set()
    for _, _, enc in a["registro"][primer_all_off:]:
        encendidas |= {c for c in enc if c != BUZZER}
    assert encendidas == puerta, "sin la corrección solo se re-encienden las de la puerta"
    ordenes_on = {o for _, o, _ in a["registro"][marca + 1:] if o.endswith(" ON")}
    assert ordenes_on == {f"SET DO{c} ON" for c in puerta | {BUZZER}}
    assert not any(f"SET DO{c} ON" in ordenes_on for c in previas_control)
    # el firmware: tras cada ALL_OFF la sombra queda vacía
    for i, (_, o, enc) in enumerate(a["registro"]):
        if o == "ALL_OFF":
            assert enc == []


def _canal_n(nombre):
    return EstadoAutoclave.map_do[nombre] + 1


# ---------------------------------------------------------------------------
# Planta simulada (E1/T11), 4 programas de fábrica: paro en ciclo
# ---------------------------------------------------------------------------

from tests import test_e1_ensayo_simulador as e1                       # noqa: E402
from tests.test_e1_ensayo_simulador import PROGRAMAS, programas  # noqa: E402,F401
from autoclave.state_machine.states.ciclo import CicloResultado        # noqa: E402

ENSAYO: dict[tuple[int, str], dict] = {}


@pytest.mark.parametrize("numero", sorted(PROGRAMAS))
@pytest.mark.parametrize("fase", ["PRE_VACIO", "ESTERILIZACION"])
def test_ensayo_paro_en_ciclo_4_programas(programas, monkeypatch, tmp_path,  # noqa: F811
                                         numero, fase):
    a = e1._armar(programas[numero], monkeypatch, tmp_path)
    if fase == "PRE_VACIO" and numero == 4:
        fase_real = "CALENTAMIENTO"           # Líquidos no tiene PRE_VACIO
    else:
        fase_real = fase
    assert e1._hasta_fase(a, fase_real, extra_s=20) is None
    previas = sorted(n for n, v in a["estado"].salidas_do.items() if v)
    # registro de órdenes a la tarjeta desde el paro
    ordenes = []
    original = a["tarjeta"].set_output

    def registrar(canal, valor):
        ordenes.append((canal, bool(valor)))
        original(canal, valor)
    a["tarjeta"].set_output = registrar
    a["estado"].set_flag("PARO_EMERGENCIA", True)
    a["estado"].set_flag("PARO_REAL", True)
    a["estado"].sensores_di["paro_emergencia"] = 0
    resultado = None
    for _ in range(int(120 / e1.DT)):
        resultado = e1._tick(a)
        e1._avanzar(a)
    encendidas = sorted({c for c, v in ordenes if v and c != BUZZER})
    quedan = sorted(n for n, v in a["estado"].salidas_do.items() if v)
    # al soltar el paro el bloqueo de SetOutput desaparece
    a["estado"].set_flag("PARO_EMERGENCIA", False)
    a["estado"].set_flag("PARO_REAL", False)
    a["estado"].sensores_di["paro_emergencia"] = 1
    a["set_do"].descompresion_lenta_on()
    lenta_tras_soltar = a["tarjeta"].on("descompresion_lenta")
    a["set_do"].descompresion_lenta_off()
    r = {"fase": fase_real, "salidas_antes_del_paro": ", ".join(previas) or "ninguna",
         "resultado": resultado, "ordenes_ON_en_paro": encendidas or "ninguna",
         "salidas_encendidas_tras_120_s": ", ".join(quedan) or "ninguna",
         "orden_aceptada_tras_soltar": lenta_tras_soltar}
    ENSAYO[(numero, fase)] = r
    assert previas, r
    assert resultado == CicloResultado.ESPERANDO_CONFIRMACION, r
    assert not encendidas, r
    assert not quedan, r
    assert lenta_tras_soltar is True, r


def test_escribir_ensayo_b9():
    if os.environ.get("B9_ESCRIBIR_REGISTRO") != "1":
        pytest.skip("solo con B9_ESCRIBIR_REGISTRO=1")
    filas = ["| Programa | Celda | Resultado |", "|---|---|---|"]
    for (numero, fase), r in sorted(ENSAYO.items()):
        datos = "; ".join(f"{k}={v}" for k, v in r.items())
        filas.append(f"| {numero} {PROGRAMAS[numero]} | paro en {fase} | {datos} |")
    destino = Path("docs/informes/tanda9/B9_ensayo_tabla.md")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(filas) + "\n", encoding="utf-8")


def test_escribir_registro_b9():
    if os.environ.get("B9_ESCRIBIR_REGISTRO") != "1":
        pytest.skip("solo con B9_ESCRIBIR_REGISTRO=1")
    filas = ["# B9 — registro de órdenes durante el paro (planta simulada)", ""]
    for clave, reg in REGISTROS.items():
        filas += [f"## {clave}", "", "| t desde el paro (s) | orden | pines encendidos tras la orden |",
                  "|---|---|---|"]
        for t, o, e in reg:
            filas.append(f"| {t} | {o} | {', '.join(f'DO{c}' for c in e) or '—'} |")
        filas.append("")
    destino = Path("docs/informes/tanda9/B9_registro_ordenes.md")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(filas) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Corrección en el PC (D9-9)
# ---------------------------------------------------------------------------

class _IoRegistro:
    def __init__(self):
        self.ordenes = []
        self.all_off_ok = True

    def set_output(self, canal, valor):
        self.ordenes.append((canal, bool(valor)))
        return True

    def all_off(self, timeout=1.0):
        self.ordenes.append(("ALL_OFF", None))
        return self.all_off_ok


def _set_do(paro_real=False, paro=False, maquina=None):
    from autoclave.state_machine.machine.enum_global import GlobalState
    estado = EstadoAutoclave()
    estado.set_machine_state(maquina or GlobalState.PREPARACION)
    estado.set_flag("PARO_EMERGENCIA", paro or paro_real)
    estado.set_flag("PARO_REAL", paro_real)
    io = _IoRegistro()
    return SetOutput(io, estado, profile=None), io, estado


def _canal(nombre):
    return EstadoAutoclave.map_do[nombre] + 1


def test_con_paro_real_una_salida_no_se_enciende_y_se_reafirma_apagada():
    s, io, _ = _set_do(paro_real=True)
    s.vapor_camara_on()
    s.set_output(_canal("cerrar_puerta_1"), True)      # como las puertas
    assert io.ordenes == [(_canal("vapor_camara"), False),
                          (_canal("cerrar_puerta_1"), False)]


def test_con_paro_real_el_buzzer_si_conmuta():
    s, io, _ = _set_do(paro_real=True)
    s.buzer_on()
    s.buzer_off()
    assert io.ordenes == [(BUZZER, True), (BUZZER, False)]


def test_con_paro_las_ordenes_de_apagar_pasan_igual():
    s, io, _ = _set_do(paro_real=True)
    s.vapor_chaqueta_off()
    assert io.ordenes == [(_canal("vapor_chaqueta"), False)]


def test_sin_paro_no_cambia_nada():
    s, io, _ = _set_do()
    s.vapor_camara_on()
    assert io.ordenes == [(_canal("vapor_camara"), True)]


def test_sin_datos_fuera_de_ciclo_tambien_bloquea():
    # PARO_EMERGENCIA sin PARO_REAL (sin datos de la tarjeta): fuera de CICLO
    # los estados ya mandan ALL_OFF; ninguna salida se enciende entre medio
    s, io, _ = _set_do(paro=True)
    s.agua_intercambiador_on()
    assert io.ordenes == [(_canal("agua_intercambiador"), False)]


def test_sin_datos_en_ciclo_no_cambia_la_tolerancia_de_di():
    # En CICLO, la tolerancia de DI vencida (P-3) no se toca
    from autoclave.state_machine.machine.enum_global import GlobalState
    s, io, _ = _set_do(paro=True, maquina=GlobalState.CICLO)
    s.descompresion_lenta_on()
    assert io.ordenes == [(_canal("descompresion_lenta"), True)]


def test_sin_datos_en_ciclo_tras_el_aborto_bloquea(monkeypatch):
    # SAF-03 de la revisión: vencida la tolerancia, el ciclo aborta y llama a
    # apagar_por_paro en cada tick (estado global sigue en CICLO): mientras
    # lo pida, nada se enciende
    from autoclave.state_machine.machine.enum_global import GlobalState
    reloj = [100.0]
    monkeypatch.setattr(set_io.time, "monotonic", lambda: reloj[0])
    s, io, estado = _set_do(paro=True, maquina=GlobalState.CICLO)
    s.set_output(_canal("cerrar_puerta_1"), True)            # tolerancia: pasa
    assert io.ordenes[-1] == (_canal("cerrar_puerta_1"), True)
    for _ in range(6):                                       # abortado: 3 s de ticks
        s.apagar_por_paro()
        s.set_output(_canal("cerrar_puerta_1"), True)
        assert io.ordenes[-1] == (_canal("cerrar_puerta_1"), False)
        reloj[0] += 0.5
    # la máquina deja de pedirlo (paro nuevo en tolerancia): vuelve a pasar
    reloj[0] += 3.1
    s.set_output(_canal("cerrar_puerta_1"), True)
    assert io.ordenes[-1] == (_canal("cerrar_puerta_1"), True)


def test_sin_datos_en_ciclo_el_tick_del_aborto_ya_bloquea(monkeypatch):
    # TMG-02 de la re-revisión: el tick del aborto llama a reset_all_outputs
    # (protocolo), no a apagar_por_paro; ya cuenta como pedido
    from autoclave.state_machine.machine.enum_global import GlobalState
    reloj = [100.0]
    monkeypatch.setattr(set_io.time, "monotonic", lambda: reloj[0])
    s, io, estado = _set_do(paro=True, maquina=GlobalState.CICLO)
    s.reset_all_outputs()
    reloj[0] += 0.5
    s.set_output(_canal("bloqueo_puerta_1"), True)
    assert io.ordenes[-1] == (_canal("bloqueo_puerta_1"), False)
    # sin paro, reset_all_outputs no marca nada
    estado.set_flag("PARO_EMERGENCIA", False)
    s.set_output(_canal("bloqueo_puerta_1"), True)
    s.reset_all_outputs()
    estado.set_flag("PARO_EMERGENCIA", True)
    s.set_output(_canal("bloqueo_puerta_1"), True)
    assert io.ordenes[-1] == (_canal("bloqueo_puerta_1"), True)


def test_tras_all_off_confirmado_no_se_repite_por_un_do_viejo(monkeypatch):
    # SAF-04/TMG-01 de la revisión: en el tick del flanco, el DO publicado
    # antes del ALL_OFF inmediato no provoca un segundo ALL_OFF
    reloj = [100.0]
    monkeypatch.setattr(set_io.time, "monotonic", lambda: reloj[0])
    s, io, estado = _set_do(paro_real=True)
    estado.salidas_do["vapor_camara"] = 1          # DO viejo, previo al ALL_OFF
    assert s.apagar_por_paro(inmediato=True) is True
    assert s.apagar_por_paro() is None
    reloj[0] += 0.7                                # ya llegó un DO nuevo
    assert s.apagar_por_paro() is True             # y sigue mostrando una salida
    # sin ACK no hay gracia: se repite en el tick siguiente
    io.all_off_ok = False
    reloj[0] += 1.0
    assert s.apagar_por_paro() is False
    reloj[0] += 0.1
    assert s.apagar_por_paro() is False


def test_paro_real_en_ciclo_bloquea():
    from autoclave.state_machine.machine.enum_global import GlobalState
    s, io, _ = _set_do(paro_real=True, maquina=GlobalState.CICLO)
    s.descompresion_lenta_on()
    assert io.ordenes == [(_canal("descompresion_lenta"), False)]


def test_apagar_por_paro_inmediato_ignora_el_intervalo(monkeypatch):
    reloj = [100.0]
    monkeypatch.setattr(set_io.time, "monotonic", lambda: reloj[0])
    s, io, estado = _set_do(paro_real=True)
    for n in estado.salidas_do:
        estado.salidas_do[n] = 0
    assert s.apagar_por_paro() is True
    reloj[0] += 0.2
    assert s.apagar_por_paro() is None                # dentro del intervalo
    assert s.apagar_por_paro(inmediato=True) is True  # flanco del paro
    assert [o for o in io.ordenes if o[0] == "ALL_OFF"] == [("ALL_OFF", None)] * 2


def test_fuera_del_paro_el_buzzer_no_altera_otras_salidas(monkeypatch):
    a = _armar(monkeypatch)
    for n in _PREVIAS:
        getattr(a["set_do"], f"{n}_on")()
    previas = [c for c, v in enumerate(a["fw"].pines, 1) if v]
    a["set_do"].buzer.play(buzer_mod.BEEP_ALARMA, repeticiones=3)
    for _ in range(40):
        a["set_do"].buzer.update()
        a["reloj"][0] += 0.1
    marca = len(_PREVIAS)
    assert len(a["registro"]) > marca + 5
    for _, orden, enc in a["registro"][marca:]:
        assert orden.startswith(f"SET DO{BUZZER} "), orden
        assert [c for c in enc if c != BUZZER] == previas


def _loop_paro():
    from autoclave.services.domain.loop.control_loop import ControlLoop
    from unittest.mock import patch
    estado = EstadoAutoclave()
    cm = MagicMock()
    cm.get_selected_cycle.return_value = MagicMock()
    with patch("autoclave.services.domain.loop.control_loop.StateMachine"):
        loop = ControlLoop(units=MagicMock(), door_service=MagicMock(), doors=[],
                           estado=estado, link=MagicMock(), set_do=MagicMock(),
                           alarm_manager=MagicMock(), cycle_manager=cm,
                           config_manager=MagicMock(), profile=None)
    loop.units.get_all.return_value = {}
    estado.sensores_di["suministro_electrico"] = 1
    loop.link.is_connected.return_value = True
    loop.link.edad_ultima_di.return_value = 0.1
    loop._di_vista_en_conexion = True
    return loop, estado


def test_control_loop_all_off_inmediato_en_el_flanco_del_paro():
    loop, estado = _loop_paro()
    estado.sensores_di["paro_emergencia"] = 1       # NC: 1 = sin paro
    loop._tick()
    loop.set_do.apagar_por_paro.assert_not_called()
    estado.sensores_di["paro_emergencia"] = 0       # se pulsa
    loop._tick()
    loop.set_do.apagar_por_paro.assert_called_once_with(inmediato=True)
    loop._tick()                                    # sigue pulsado: no se repite
    loop.set_do.apagar_por_paro.assert_called_once_with(inmediato=True)
    estado.sensores_di["paro_emergencia"] = 1       # se suelta
    loop._tick()
    estado.sensores_di["paro_emergencia"] = 0       # se vuelve a pulsar
    loop._tick()
    assert loop.set_do.apagar_por_paro.call_count == 2


def test_control_loop_all_off_del_flanco_bajo_el_lock_de_la_maquina():
    # TMG-02 de la revisión: no se intercala con el ALL_OFF de entrar/salir
    # del modo prueba (bajo _sm_lock en el hilo del backend)
    loop, estado = _loop_paro()
    tomado = []
    loop.set_do.apagar_por_paro.side_effect = (
        lambda **_: tomado.append(loop._sm_lock._is_owned()))
    estado.sensores_di["paro_emergencia"] = 0
    loop._tick()
    assert tomado == [True]

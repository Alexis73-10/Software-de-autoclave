"""S3c y S3d (tanda 2; pendientes T8 SAF-03 y TMG-02/SAF-09).

S3c: una base de datos que falla en caliente (durante un ciclo) activa
OPERANDO_SIN_BD, como si el equipo hubiera arrancado sin base: alarma, el
siguiente ciclo pide confirmación y lleva la leyenda "SIN OPERADOR / SIN BD",
calibración/parámetros bloqueados. El ciclo en curso NO se detiene: sigue en el
respaldo JSONL y en el ticket.

S3d: el respaldo (con su fsync) sale del hilo del lazo: va por el mismo hilo
FIFO que la base (EscritorBD), así que se conserva "primero el respaldo, después
la base" (TMG-03 de T8). Si la cola está llena, el respaldo se escribe en línea:
nunca se descarta."""

import queue
import sqlite3
from unittest.mock import MagicMock

from autoclave.core.runtime.respaldo_ciclos import RespaldoCiclos
from autoclave.services.domain.logging.cycle_logger import CycleLogger
from tests.test_t8_modo_sin_bd import _Estado, _correr_ciclo


class _Diferido:
    """Ejecutor que guarda las tareas (como la cola de EscritorBD) para
    correrlas después, fuera del 'tick'."""

    def __init__(self, lleno=False):
        self.tareas = []
        self.lleno = lleno

    def __call__(self, tarea):
        if self.lleno:
            raise queue.Full
        self.tareas.append(tarea)

    def correr(self):
        while self.tareas:
            self.tareas.pop(0)()


def _logger(tmp_path, db, ejecutar=None, al_fallar_bd=None):
    from tests.test_t8_modo_sin_bd import _logger as base
    cl, estado, printer, respaldo = base(tmp_path, db, sin_bd=False)
    if ejecutar is not None:
        cl._ejecutar_bd = ejecutar
    cl.al_fallar_bd = al_fallar_bd
    return cl, estado, printer, respaldo


# ── S3d: respaldo fuera del tick, en orden con la base ──────────────────────

def test_el_respaldo_no_se_escribe_en_el_tick(tmp_path):
    db = MagicMock()
    db.crear_ciclo.return_value = 1
    diferido = _Diferido()
    cl, estado, _, respaldo = _logger(tmp_path, db, ejecutar=diferido)
    cl.update()                                  # inicio (tick)
    cl.update()                                  # primera lectura (tick)
    assert respaldo.pendientes() == []           # nada escrito todavía en el tick
    diferido.correr()                            # hilo de escritura
    datos = respaldo.leer(respaldo.pendientes()[0])
    assert datos["encabezado"] and datos["lecturas"]


def test_primero_el_respaldo_y_despues_la_base(tmp_path):
    orden = []
    db = MagicMock()
    db.crear_ciclo.side_effect = lambda **kw: orden.append("bd_crear") or 1
    db.insertar_lectura.side_effect = lambda **kw: orden.append("bd_lectura")
    diferido = _Diferido()
    cl, estado, _, respaldo = _logger(tmp_path, db, ejecutar=diferido)
    real = respaldo._anexar
    respaldo._anexar = lambda u, r: orden.append("respaldo_" + r["registro"]) or real(u, r)
    cl.update()
    cl.update()
    diferido.correr()
    assert orden.index("respaldo_encabezado") < orden.index("bd_crear")
    assert orden.index("respaldo_lectura") < orden.index("bd_lectura")


def test_con_la_cola_llena_el_respaldo_se_escribe_en_linea(tmp_path):
    db = MagicMock()
    cl, estado, _, respaldo = _logger(tmp_path, db, ejecutar=_Diferido(lleno=True))
    _correr_ciclo(cl, estado)
    datos = respaldo.leer(respaldo.pendientes()[0])
    assert datos["encabezado"] and datos["lecturas"] and datos["cierre"]


# ── S3c: la base que falla en caliente activa OPERANDO_SIN_BD ───────────────

def test_falla_de_la_base_en_caliente_avisa_una_vez_y_el_ciclo_sigue(tmp_path):
    avisos = []
    db = MagicMock()
    db.crear_ciclo.return_value = 5
    db.insertar_lectura.side_effect = sqlite3.OperationalError("disk I/O error")
    db.cerrar_ciclo.side_effect = sqlite3.OperationalError("disk I/O error")
    cl, estado, printer, respaldo = _logger(tmp_path, db, al_fallar_bd=avisos.append)
    _correr_ciclo(cl, estado)
    assert len(avisos) == 1 and "disk I/O error" in avisos[0]
    assert respaldo.leer(respaldo.pendientes()[0])["cierre"]["resultado"] == "COMPLETADO"


def test_cola_llena_tambien_avisa(tmp_path):
    avisos = []
    cl, estado, _, _ = _logger(tmp_path, MagicMock(), ejecutar=_Diferido(lleno=True),
                               al_fallar_bd=avisos.append)
    _correr_ciclo(cl, estado)
    assert len(avisos) == 1


def test_contexto_pasa_a_operar_sin_base():
    from autoclave.backend.context import BackendContext
    from autoclave.state_machine.alarms.catalogo import OPERANDO_SIN_BD
    import threading
    ctx = BackendContext.__new__(BackendContext)
    ctx._lock_sin_bd = threading.Lock()
    ctx.db = "db-real"
    ctx.calibration_audit = "audit-real"
    ctx.sin_base_de_datos = False
    ctx.alarm_manager = MagicMock()
    ctx.cycle_logger = MagicMock(sin_base_de_datos=False)
    ctx.bd_fallo_en_caliente("disk I/O error")
    ctx.bd_fallo_en_caliente("otra")             # idempotente
    assert ctx.sin_base_de_datos is True
    assert ctx.cycle_logger.sin_base_de_datos is True   # el siguiente ciclo: leyenda
    # los endpoints que usan context.db responden 503; la real se conserva
    from autoclave.backend.arranque.sin_bd import BdNoDisponible
    assert isinstance(ctx.db, BdNoDisponible) and ctx.db_real == "db-real"
    assert isinstance(ctx.calibration_audit, BdNoDisponible)
    ctx.alarm_manager.activar.assert_called_once()
    assert ctx.alarm_manager.activar.call_args.args[0] == OPERANDO_SIN_BD


def test_siguiente_ciclo_tras_la_falla_va_sin_registro(tmp_path):
    db = MagicMock()
    db.crear_ciclo.return_value = 5
    db.insertar_lectura.side_effect = sqlite3.OperationalError("disk I/O error")
    cl, estado, printer, respaldo = _logger(tmp_path, db,
                                            al_fallar_bd=lambda m: setattr(cl, "sin_base_de_datos", True))
    _correr_ciclo(cl, estado)
    db.reset_mock()
    printer.reset_mock()
    from autoclave.state_machine.machine.enum_global import GlobalState
    estado.maquina = GlobalState.PREPARADO     # el operador confirmó: vuelve a PREPARADO
    cl.update()
    estado.maquina = GlobalState.CICLO         # y arranca un ciclo nuevo
    estado.fase_ciclo = "CALENTAMIENTO"
    _correr_ciclo(cl, estado)
    db.crear_ciclo.assert_not_called()           # el segundo ya no toca la base
    impreso = "\n".join(c.args[0] for c in printer.enqueue.call_args_list)
    assert "SIN OPERADOR / SIN BD" in impreso


# ── Revisión de S3c/S3d ──────────────────────────────────────────────────────

def _con_contador(tmp_path, db, ejecutar_bd=None, ejecutar_respaldo=None):
    from autoclave.core.runtime.contador_ciclos import ContadorCiclos
    cl, estado, printer, respaldo = _logger(tmp_path, db, ejecutar=ejecutar_bd)
    cl.contador = ContadorCiclos(tmp_path / "contador.json")
    if ejecutar_respaldo is not None:
        cl._ejecutar_respaldo_propio = ejecutar_respaldo
    return cl, estado, respaldo


def test_la_marca_de_ciclo_se_limpia_despues_del_cierre_del_respaldo(tmp_path):
    """S3-01: un corte entre la limpieza y el cierre no puede dejar un ciclo
    terminado sin cierre y sin marca."""
    db = MagicMock()
    db.crear_ciclo.return_value = 1
    db.max_numero_ciclo.return_value = 0
    diferido = _Diferido()
    cl, estado, respaldo = _con_contador(tmp_path, db, ejecutar_respaldo=diferido)
    cl.update()
    cl.update()
    estado.fase_ciclo = "COMPLETADO"
    cl.update()                                       # cierre en el tick
    assert cl.contador.en_curso() is not None         # marca aún puesta
    diferido.correr()                                 # hilo del respaldo: cierre y luego limpia
    assert cl.contador.en_curso() is None
    assert respaldo.leer(respaldo.pendientes()[0])["cierre"]["resultado"] == "COMPLETADO"


def test_la_limpieza_diferida_no_borra_la_marca_del_ciclo_siguiente(tmp_path):
    from autoclave.state_machine.machine.enum_global import GlobalState
    db = MagicMock()
    db.crear_ciclo.return_value = 1
    db.max_numero_ciclo.return_value = 0
    diferido = _Diferido()
    cl, estado, _ = _con_contador(tmp_path, db, ejecutar_respaldo=diferido)
    _correr_ciclo(cl, estado)                          # termina el ciclo 1; limpieza en cola
    estado.maquina = GlobalState.PREPARADO
    cl.update()
    estado.maquina = GlobalState.CICLO
    estado.fase_ciclo = "CALENTAMIENTO"
    cl.update()                                        # inicia el ciclo 2: marca síncrona
    marca = cl.contador.en_curso()
    assert marca is not None and marca["numero"] == 2
    diferido.correr()                                  # llega la limpieza del ciclo 1
    assert cl.contador.en_curso() is not None and cl.contador.en_curso()["numero"] == 2


def test_el_respaldo_no_espera_a_una_base_atascada(tmp_path):
    db = MagicMock()
    db.crear_ciclo.return_value = 1
    cola_bd, cola_respaldo = _Diferido(), _Diferido()
    cl, estado, _, respaldo = _logger(tmp_path, db, ejecutar=cola_bd)
    cl._ejecutar_respaldo_propio = cola_respaldo
    cl.update()
    cl.update()
    cola_respaldo.correr()                             # solo el respaldo avanza
    assert respaldo.leer(respaldo.pendientes()[0])["lecturas"]
    db.insertar_lectura.assert_not_called()            # la base sigue atascada


def test_detener_vacia_las_colas_reales_antes_de_cerrar(tmp_path):
    import time
    from autoclave.services.domain.logging.cycle_logger import EscritorBD
    escritos = []
    bd = EscritorBD(nombre="bd-prueba")
    rsp = EscritorBD(maximo=0, nombre="rsp-prueba")
    cl = CycleLogger(MagicMock(), _Estado(), {}, MagicMock(), MagicMock(),
                     ejecutar_bd=bd, ejecutar_respaldo=rsp)
    bd(lambda: (time.sleep(0.2), escritos.append("bd")))
    rsp(lambda: (time.sleep(0.2), escritos.append("respaldo")))
    cl.detener(5.0)
    assert sorted(escritos) == ["bd", "respaldo"]      # nada quedó sin escribir


def test_sin_base_no_se_consulta_la_base_para_numerar(tmp_path):
    from autoclave.core.runtime.contador_ciclos import ContadorCiclos
    db = MagicMock()
    db.max_numero_ciclo.side_effect = AssertionError("no debe consultarse la base")
    cl, estado, _, _ = _logger(tmp_path, db)
    cl.contador = ContadorCiclos(tmp_path / "c.json")
    cl.sin_base_de_datos = True
    assert cl._numero_nuevo() == 1


def test_el_aviso_de_base_caida_es_unico_con_hilos_concurrentes(tmp_path):
    import threading
    avisos = []
    cl, _, _, _ = _logger(tmp_path, MagicMock(), al_fallar_bd=avisos.append)
    hilos = [threading.Thread(target=cl._avisar_bd_fallida, args=("x",)) for _ in range(20)]
    [h.start() for h in hilos]
    [h.join() for h in hilos]
    assert len(avisos) == 1

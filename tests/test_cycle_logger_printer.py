import time as time_module
from types import SimpleNamespace

from autoclave.services.domain.logging.cycle_logger import CycleLogger
from autoclave.state_machine.machine.enum_global import GlobalState


class FakeDb:
    def __init__(self):
        self._next_id = 1
        self.cerrados = []

    def siguiente_numero_ciclo(self):
        return 7

    def crear_ciclo(self, **kwargs):
        cid = self._next_id
        self._next_id += 1
        return cid

    def insertar_lectura(self, **kwargs):
        pass

    def cerrar_ciclo(self, ciclo_id, resultado, motivo_fallo=None):
        self.cerrados.append((ciclo_id, resultado, motivo_fallo))


class FakeCycle:
    id = "bowe_dick"
    name = "Bowie-Dick"

    def __init__(self, f0_activo=False):
        self.f0_activo = f0_activo

    def get_param(self, *keys, default=None):
        # Replica la semántica real de Cycle.get_param: recorre las claves
        # anidadas (sección → parámetro), no sólo la última.
        data = {
            "esterilizacion": {
                "temperatura_esterilizacion": 134,
                "tiempo_esterilizacion": 3.5,
            },
            "globals": {
                "F0": self.f0_activo,
            },
        }
        for key in keys:
            if not isinstance(data, dict):
                return default
            data = data.get(key)
            if data is None:
                return default
        return data


class FakeCycleManager:
    def __init__(self, f0_activo=False):
        self.f0_activo = f0_activo

    def get_selected_cycle(self):
        return FakeCycle(f0_activo=self.f0_activo)


class FakeConfig:
    def __init__(self, intervalo=99999):
        self.intervalo = intervalo

    def get(self, *keys, default=None):
        return self.intervalo


class FakeEstado:
    def __init__(self):
        self.machine_state = GlobalState.CICLO
        self.fase_ciclo = "PRECALENTAMIENTO"
        self.sub_estado_ciclo = ""
        self.motivo_fallo = ""
        self.sensores_temp = {"temp_camara": 25.0}
        self.sensores_pres = {"pres_camara": 74.5}
        self.f0_acumulado = 0.0

    def get_machine_state(self):
        return self.machine_state


class FakePrinter:
    def __init__(self):
        self.calls = []

    def enqueue(self, text):
        self.calls.append(text)


def _build_logger(printer, config=None, cycle_manager=None):
    return CycleLogger(
        db=FakeDb(),
        estado=FakeEstado(),
        config=config or FakeConfig(),
        profile=SimpleNamespace(serial_number="SN-001", model_id="MX-500"),
        cycle_manager=cycle_manager or FakeCycleManager(),
        printer=printer,
    )


def test_inicio_de_ciclo_encola_encabezado():
    printer = FakePrinter()
    cl = _build_logger(printer)

    cl.update()   # transición → CICLO: dispara _on_inicio

    assert len(printer.calls) == 1
    assert "Ciclo No.: 000007" in printer.calls[0]
    assert "Num serie: SN-001" in printer.calls[0]
    assert "Modelo: MX-500" in printer.calls[0]
    assert "Temp. Ester.: 134 C" in printer.calls[0]
    assert "Tiempo Ester.: 3.5 min" in printer.calls[0]


def test_cambio_de_fase_encola_una_fila():
    printer = FakePrinter()
    cl = _build_logger(printer)

    cl.update()   # header
    cl.update()   # cambio de fase None -> "PH" -> fila

    assert len(printer.calls) == 2
    assert printer.calls[1].startswith("PH ")


def test_sin_cambio_de_fase_ni_intervalo_no_encola_nada_nuevo():
    printer = FakePrinter()
    cl = _build_logger(printer)

    cl.update()   # header
    cl.update()   # fila por cambio de fase
    cl.update()   # misma fase, intervalo (99999s) no cumplido

    assert len(printer.calls) == 2


def test_cambio_de_sub_estado_encola_fila_sin_esperar_intervalo():
    printer = FakePrinter()
    cl = _build_logger(printer, config=FakeConfig(intervalo=99999))

    cl.update()   # header
    cl.update()   # fila por cambio de fase (None -> "PH")
    assert len(printer.calls) == 2

    cl.estado.sub_estado_ciclo = "VACIO_BAJO"
    cl.update()   # misma fase, pero cambió el paso interno -> fila igual
    assert len(printer.calls) == 3
    assert printer.calls[2].startswith("PH ")

    cl.estado.sub_estado_ciclo = "HOLD_BAJO"
    cl.update()   # otro cambio de paso interno -> otra fila
    assert len(printer.calls) == 4


def test_sin_cambio_de_sub_estado_no_encola_fila_extra():
    printer = FakePrinter()
    cl = _build_logger(printer, config=FakeConfig(intervalo=99999))

    cl.update()   # header
    cl.update()   # fila por cambio de fase
    cl.estado.sub_estado_ciclo = "VACIO_BAJO"
    cl.update()   # fila por cambio de sub-estado
    assert len(printer.calls) == 3

    cl.update()   # mismo sub-estado, sin cambio de fase, intervalo no cumplido
    assert len(printer.calls) == 3


def test_intervalo_cumplido_encola_fila_periodica(monkeypatch):
    printer = FakePrinter()
    cl = _build_logger(printer, config=FakeConfig(intervalo=1))
    cl.estado.fase_ciclo = "CALENTAMIENTO"   # código "H" -> usa intervalo_impresion

    tiempo_actual = [1000.0]
    monkeypatch.setattr(time_module, "time", lambda: tiempo_actual[0])

    cl.update()   # header
    cl.update()   # cambio de fase None -> "H" -> fila 1

    tiempo_actual[0] += 2.0   # supera el intervalo de 1s
    cl.update()   # misma fase, intervalo cumplido -> fila 2

    assert len(printer.calls) == 3


def test_fin_de_ciclo_encola_fila_final_y_pie():
    printer = FakePrinter()
    cl = _build_logger(printer)

    cl.update()   # header
    cl.update()   # fila por cambio de fase
    cl.estado.machine_state = GlobalState.PREPARADO
    cl.update()   # _on_fin: fila "E" + pie

    assert len(printer.calls) == 4
    assert "Estado:" in printer.calls[3]
    assert "Hora fin:" in printer.calls[3]
    assert "Temp. final:" in printer.calls[3]


def test_fin_de_ciclo_sin_f0_activo_no_incluye_f0_total_en_el_pie():
    printer = FakePrinter()
    cl = _build_logger(printer, cycle_manager=FakeCycleManager(f0_activo=False))
    cl.estado.f0_acumulado = 15.3

    cl.update()   # header
    cl.update()   # fila por cambio de fase
    cl.estado.machine_state = GlobalState.PREPARADO
    cl.update()   # _on_fin: fila "E" + pie

    assert "F0 total" not in printer.calls[3]


def test_fin_de_ciclo_con_f0_activo_incluye_f0_total_en_el_pie():
    printer = FakePrinter()
    cl = _build_logger(printer, cycle_manager=FakeCycleManager(f0_activo=True))
    cl.estado.f0_acumulado = 15.3

    cl.update()   # header
    cl.update()   # fila por cambio de fase
    cl.estado.machine_state = GlobalState.PREPARADO
    cl.update()   # _on_fin: fila "E" + pie

    assert "F0 total: 15.3 min" in printer.calls[3]


def test_sin_printer_no_falla():
    cl = _build_logger(printer=None)

    cl.update()
    cl.update()
    cl.estado.machine_state = GlobalState.PREPARADO
    cl.update()

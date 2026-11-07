"""T29-02 (tanda 29): inventario de alarmas y avisos que aparecen durante un
ciclo completo y hasta 5 min después, con la planta simulada de
tests/test_t11_programas_integracion.py y la StateMachine real.

No es una prueba automática (tests/banco). Uso, desde la raíz:

    python tests/banco/t29_inventario_avisos.py

Corre: programa 2 (Instrumental 134, sólido con prevacío y secado) y
programa 4 (Líquidos) con el enfriamiento forzado a modo 4. El drenaje sigue a
la cámara con retraso (más caliente con los escapes abiertos, más frío con
agua_intercambiador); las puertas, cerradas (DI vigentes). Imprime cada
activación (código, estado de la máquina, fase, minuto) y el resumen de las
que aparecieron en CICLO (las que irían a alarmas_ciclo / observaciones)."""

import sys
import time
from pathlib import Path
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

import test_t11_programas_integracion as t11  # noqa: E402
from autoclave.core.managers.config_manager import ConfigManager  # noqa: E402
from autoclave.core.managers.cycle_manager import CycleManager  # noqa: E402
from autoclave.core.runtime.status import EstadoAutoclave  # noqa: E402
from autoclave.devices.io.set_io import SetOutput  # noqa: E402
from autoclave.installation.equipment import EquipmentClass, get_capabilities  # noqa: E402
from autoclave.state_machine.alarms.alarm_manager import AlarmManager  # noqa: E402
from autoclave.state_machine.machine.enum_global import GlobalState  # noqa: E402
from autoclave.state_machine.state_machine import StateMachine  # noqa: E402

DT = t11.DT
DESPUES_S = 5 * 60


class _Registro(AlarmManager):
    def __init__(self, estado, reloj):
        super().__init__(estado)
        self._estado = estado
        self._reloj_inv = reloj
        self.eventos = []

    def activar(self, codigo, *a, **k):
        ya = any(i.codigo == codigo and i.origen == k.get("origen") for i in self.activas())
        if not ya:
            self.eventos.append((codigo, self._estado.get_machine_state().name,
                                 self._estado.fase_ciclo, (self._reloj_inv[0] - 1000.0) / 60))
        return super().activar(codigo, *a, **k)


def _drenaje(t_dren, planta, modulo_es):
    escape = modulo_es.on("descompresion_rapida") or modulo_es.on("descompresion_lenta")
    objetivo = planta.t if escape else 0.6 * planta.t
    if modulo_es.on("agua_intercambiador"):
        objetivo -= 30.0
    t_dren += (objetivo - t_dren) * DT / 30.0
    return max(t_dren, 25.0)


def correr(programa, etiqueta):
    reloj = [1000.0]
    with patch.object(time, "monotonic", lambda: reloj[0]):
        estado = EstadoAutoclave()
        for di in estado.sensores_di:
            estado.sensores_di[di] = 1
        estado.sensores_di["paro_emergencia"] = 1
        estado.sensores_di["agua_camara"] = 0
        modulo_es = t11._ModuloEs(estado)
        config = ConfigManager()
        config.load_config()
        t11.P_ATM = float(config.get("presion_admosferica") or 101.3)
        planta = t11._Planta(modulo_es)
        alarmas = _Registro(estado, reloj)
        set_do = SetOutput(modulo_es, estado, profile=None)
        sm = StateMachine(None, estado, set_do, programa, config,
                          cap=get_capabilities(EquipmentClass.PISO_LAB),
                          alarm_manager=alarmas, programas_seguridad=lambda: [programa])
        t_dren = 40.0
        planta.publicar(estado)
        estado.sensores_temp["temp_drenaje"] = t_dren
        estado.set_machine_state(GlobalState.CICLO)
        sm.on_state_entry(GlobalState.CICLO)
        sm.prev_state = GlobalState.CICLO
        fin = None
        for _ in range(int(4 * 3600 / DT)):
            planta.publicar(estado)
            estado.sensores_temp["temp_drenaje"] = t_dren
            if estado.get_machine_state() == GlobalState.CICLO and sm.ciclo._resultado_pendiente:
                estado.set_flag("CICLO_CONFIRMADO", True)
            sm.update(datos_vigentes=True)
            if fin is None and estado.get_machine_state() != GlobalState.CICLO:
                fin = reloj[0]
                resultado = estado.get_machine_state().name
            if fin is not None and reloj[0] - fin >= DESPUES_S:
                break
            planta.paso()
            t_dren = _drenaje(t_dren, planta, modulo_es)
            reloj[0] += DT
        print(f"\n=== {etiqueta}: fin de ciclo -> {resultado if fin else 'sin terminar'} "
              f"(min {((fin or reloj[0]) - 1000) / 60:.1f}) ===")
        for codigo, maquina, fase, minuto in alarmas.eventos:
            print(f"  {minuto:7.1f} min  {codigo:28s} {maquina:12s} {fase}")
        en_ciclo = sorted({c for c, m, _f, _t in alarmas.eventos if m == "CICLO"})
        print("  En CICLO (irían a alarmas_ciclo):", ", ".join(en_ciclo) or "ninguna")
        print("  Activas al final:", ", ".join(sorted(i.codigo for i in alarmas.activas())) or "ninguna")


def main():
    cm = CycleManager()
    cm._load_from_folder("cycles/factory", source="factory")
    por_numero = {c.number: c for c in cm.cycles.values() if c.number is not None}
    correr(por_numero[2], "Programa 2 (sólido, prevacío y secado)")
    liquido = por_numero[4].copia()
    liquido.set_param("descompresion", ["modo"], 4)
    correr(liquido, "Programa 4 (líquidos, modo 4)")


if __name__ == "__main__":
    main()

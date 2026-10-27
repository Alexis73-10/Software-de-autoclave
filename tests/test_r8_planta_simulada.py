"""R8 (tanda 8, D8-5.12): una función reasignada se lee y se acciona en su
puerto nuevo, con la planta simulada de T11/E1, en los 4 programas de fábrica.

La planta tiene su propio "cableado físico" (canal de tarjeta -> función),
calculado aparte de los mapas del software: simula que el técnico movió los
cables de vapor de cámara, presión de cámara, temperatura de cámara y paro de
emergencia a puertos libres porque los de fábrica se dañaron. El puerto viejo
queda muerto (la salida no mueve nada; la entrada lee 0). Con la asignación
aplicada en memoria el ciclo debe completarse sin tocar nunca el canal viejo;
sin ella (control negativo), el software lee y acciona los puertos muertos.

Con R8_ESCRIBIR_INFORME=1 escribe docs/informes/tanda8/R8_ensayo_tabla.md."""

import os
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autoclave.core.managers.config_manager import ConfigManager
from autoclave.core.runtime import asignacion_io as aio
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.devices.io.set_io import SetOutput
from autoclave.installation.equipment import EquipmentClass, get_capabilities
from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.machine.enum_global import GlobalState
from autoclave.state_machine.states.ciclo import CicloResultado, CicloState
from tests import test_t11_programas_integracion as t11
from tests.test_e1_ensayo_simulador import PROGRAMAS, programas  # noqa: F401
from tests.test_t11_programas_integracion import DT, _Planta

RESULTADOS: dict[int, dict] = {}


@pytest.fixture(autouse=True)
def _mapas_de_fabrica():
    aio.restablecer_memoria_fabrica_codigo()
    yield
    aio.restablecer_memoria_fabrica_codigo()


def _libre(asignacion: dict, tipo: str, rango) -> int:
    usados = set(asignacion[tipo].values())
    return next(p for p in rango if p not in usados)


def _cambios() -> dict:
    f = aio.fabrica_codigo()
    return {"vapor_camara": _libre(f, "DO", aio.puertos()["DO"]),
            "pres_camara": _libre(f, "AI", aio.puertos()["AI_PRES"]),
            "temp_camara": _libre(f, "AI", aio.puertos()["AI_TEMP"]),
            "paro_emergencia": _libre(f, "DI", aio.puertos()["DI"])}


class _TarjetaFisica:
    """Salidas por canal físico; el nombre de cada canal sale del cableado de
    la planta, no de EstadoAutoclave.map_do."""

    def __init__(self, estado, cableado: dict):
        self.estado = estado
        self.do: dict[int, bool] = {}
        self.encendidos: set[int] = set()
        self._canal = {aio.nombre_estado(f): p for f, p in cableado["DO"].items()}
        self._nombre = {p: n for n, p in self._canal.items()}

    def set_output(self, canal, valor):
        self.do[canal] = bool(valor)
        if valor:
            self.encendidos.add(canal)
        nombre = self._nombre.get(canal)
        if nombre:
            self.estado.salidas_do[nombre] = 1 if valor else 0

    def all_off(self):
        for canal in list(self.do):
            self.set_output(canal, False)
        return True

    def on(self, nombre):
        return self.do.get(self._canal[nombre], False)


class _PlantaFisica(_Planta):
    """Publica vectores crudos por canal físico y deja que EstadoAutoclave.update
    los reparta con los mapas del software (como hace el lazo con la tarjeta)."""

    def __init__(self, tarjeta, cableado: dict, puerto_muerto_di: int):
        super().__init__(tarjeta)
        self.cableado = cableado
        self.puerto_muerto_di = puerto_muerto_di

    def publicar(self, estado):
        t = self.t_sonda
        valores = {"temp_camara": t, "temp_2_camara": t, "temp_ref": t - 0.2, "temp_drenaje": 40.0,
                   "pres_camara": self.p, "pres_chaqueta": self.p_chaqueta,
                   "pres_empaque_1": 350.0, "pres_empaque_2": 350.0}
        temp, pres = [0.0] * 8, [0.0] * 8
        for funcion, puerto in self.cableado["AI"].items():
            v = valores.get(aio.nombre_estado(funcion), 0.0)
            if puerto in aio.puertos()["AI_TEMP"]:
                temp[puerto - 1] = v
            else:
                pres[puerto - 9] = v
        di = [1] * 56
        di[self.puerto_muerto_di - 1] = 0          # el cable ya no está en el puerto viejo
        estado.update({"temperature": temp, "pressure": pres, "raw_di": di})


def _armar(programa, monkeypatch, reasignar: bool):
    fabrica = aio.fabrica_codigo()
    cambios = _cambios()
    cableado = aio.combinar(fabrica, cambios)            # lo que hizo el técnico
    if reasignar:
        aio.aplicar_en_memoria(cableado)                 # lo que aplica R8 al arrancar
    reloj = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: reloj[0])
    estado = EstadoAutoclave()
    estado.set_machine_state(GlobalState.CICLO)
    tarjeta = _TarjetaFisica(estado, cableado)
    config = ConfigManager()
    config.load_config()
    t11.P_ATM = float(config.get("presion_admosferica") or 101.3)
    planta = _PlantaFisica(tarjeta, cableado, fabrica["DI"]["paro_emergencia"])
    set_do = SetOutput(tarjeta, estado, profile=None)
    ciclo = CicloState(estado, set_do, programa, config, AlarmManager(),
                       cap=get_capabilities(EquipmentClass.PISO_LAB))
    planta.publicar(estado)
    ciclo.reset()
    return dict(reloj=reloj, estado=estado, tarjeta=tarjeta, planta=planta, set_do=set_do,
                ciclo=ciclo, fabrica=fabrica, cambios=cambios)


@pytest.mark.parametrize("numero", sorted(PROGRAMAS))
def test_ciclo_completo_con_funciones_en_su_puerto_nuevo(programas, monkeypatch, numero):  # noqa: F811
    a = _armar(programas[numero], monkeypatch, reasignar=True)
    estado, planta = a["estado"], a["planta"]
    assert estado.sensores_di["paro_emergencia"] == 1            # lee el puerto nuevo
    assert estado.sensores_pres["pres_camara"] == pytest.approx(planta.p)
    assert estado.sensores_temp["temp_camara"] == pytest.approx(planta.t_sonda)
    p_max = 0.0
    resultado = None
    for _ in range(int(4 * 3600 / DT)):
        planta.publicar(estado)
        resultado = a["ciclo"].run()
        if resultado in (CicloResultado.ESPERANDO_CONFIRMACION, CicloResultado.FALLO):
            break
        planta.paso()
        a["reloj"][0] += DT
        p_max = max(p_max, planta.p)
    canal_viejo = a["fabrica"]["DO"]["vapor_camara"]
    canal_nuevo = a["cambios"]["vapor_camara"]
    RESULTADOS[numero] = {
        "fase_final": estado.fase_ciclo,
        "vapor_en_canal_nuevo": canal_nuevo in a["tarjeta"].encendidos,
        "canal_viejo_tocado": canal_viejo in a["tarjeta"].encendidos,
        "P_max": round(p_max, 1),
        "minutos": round((a["reloj"][0] - 1000.0) / 60, 1),
    }
    assert resultado == CicloResultado.ESPERANDO_CONFIRMACION, (estado.fase_ciclo, estado.motivo_fallo)
    assert estado.fase_ciclo == "COMPLETADO"
    assert canal_nuevo in a["tarjeta"].encendidos
    assert canal_viejo not in a["tarjeta"].encendidos
    assert p_max > 200.0                                     # el vapor sí entró a la cámara


def test_control_negativo_sin_reasignar_lee_y_acciona_los_puertos_muertos(programas, monkeypatch):  # noqa: F811
    """Sin aplicar la asignación, el software sigue en los puertos de fábrica:
    lee 0 en el paro (puerto muerto), no ve la presión ni la temperatura de la
    cámara y su orden de vapor va a un canal que no mueve nada."""
    a = _armar(programas[2], monkeypatch, reasignar=False)
    estado, planta = a["estado"], a["planta"]
    assert estado.sensores_di["paro_emergencia"] == 0
    assert estado.sensores_pres["pres_camara"] == 0.0
    assert estado.sensores_temp["temp_camara"] == 0.0
    a["set_do"].vapor_camara_on()
    assert a["fabrica"]["DO"]["vapor_camara"] in a["tarjeta"].encendidos
    assert planta.tarjeta.on("vapor_camara") is False


def test_escribir_informe():
    if os.environ.get("R8_ESCRIBIR_INFORME") != "1" or len(RESULTADOS) < len(PROGRAMAS):
        pytest.skip("R8_ESCRIBIR_INFORME=1 y los 4 programas en la misma corrida")
    c = _cambios()
    f = aio.fabrica_codigo()
    filas = ["| Programa | Resultado |", "|---|---|"]
    for n in sorted(RESULTADOS):
        filas.append(f"| {n} {PROGRAMAS[n]} | "
                     + ", ".join(f"{k}={v}" for k, v in RESULTADOS[n].items()) + " |")
    mov = ", ".join(f"{fn}: {aio.etiqueta(t, f[t][fn])} -> {aio.etiqueta(t, c[fn])}"
                    for fn, t in (("vapor_camara", "DO"), ("pres_camara", "AI"),
                                  ("temp_camara", "AI"), ("paro_emergencia", "DI")))
    Path("docs/informes/tanda8/R8_ensayo_tabla.md").write_text(
        "Reasignación ensayada (cableado de la planta movido igual): " + mov + "\n\n"
        + "\n".join(filas) + "\n", encoding="utf-8")

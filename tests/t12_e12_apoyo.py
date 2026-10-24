# tests/t12_e12_apoyo.py
#
# Apoyo de las pruebas de la etapa E12 (tanda 12, ESTERILIZACION): fase con
# reloj monotonic simulado y parámetros nuevos (tipo de carga, timeout de
# excursión, asignación de sensores). No es un módulo de pruebas.

import time

from autoclave.core.runtime.steam import p_saturacion_kpa
from tests.test_esterilizacion_fase import _make_fase

ASIG_REF = {"temp_camara": "principal", "temp_2_camara": "no_en_uso", "temp_ref": "referencia"}


class Reloj:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t

    def avanzar(self, s):
        self.t += s


def fase(monkeypatch, *, tipo_carga=None, timeout_exc=None, sensores=None, refs=None,
         temp=None, pres=None, **kw):
    """(fase, estado, set_do, reloj). `temp`/`pres`: lectura inicial del
    Principal y de la cámara (por defecto T_est y Psat(T_est))."""
    reloj = Reloj()
    monkeypatch.setattr(time, "monotonic", reloj)
    f, estado, set_do = _make_fase(**kw)
    base = f.cycle.get_param.side_effect
    extras = {}
    if tipo_carga is not None:
        extras["tipo_carga"] = tipo_carga
    if timeout_exc is not None:
        extras["timeout_excursion_referencia"] = timeout_exc

    def get_param(seccion, param, default=None):
        if param in extras:
            return extras[param]
        return base(seccion, param, default)

    f.cycle.get_param.side_effect = get_param
    if sensores is not None:
        f.cycle.sensores = sensores
    estado.avisos_ciclo = []
    if refs:
        estado.sensores_temp.update(refs)
    if temp is not None:
        estado.sensores_temp["temp_camara"] = temp
    if pres is not None:
        estado.sensores_pres["pres_camara"] = pres
    return f, estado, set_do, reloj


def poner(estado, temp=None, pres=None, **refs):
    if temp is not None:
        estado.sensores_temp["temp_camara"] = temp
    if pres is not None:
        estado.sensores_pres["pres_camara"] = pres
    estado.sensores_temp.update(refs)


def psat(t):
    return p_saturacion_kpa(t)


def activaciones(f, codigo):
    return [c for c in f.alarm_manager.activar.call_args_list if c.args and c.args[0] == codigo]

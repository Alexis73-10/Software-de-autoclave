# tests/test_r8_arranque.py
#
# R8 (tanda 8, D8-5.12): al arrancar, el backend aplica la asignación vigente
# (persistencia tras reiniciar), bloquea si el archivo está dañado y, tras una
# reasignación, verifica que cada función responde en su puerto nuevo.

import json
from unittest.mock import MagicMock

import pytest

from autoclave.backend import context as ctx_mod
from autoclave.backend.context import BackendContext
from autoclave.core.runtime import asignacion_io as aio
from autoclave.core.runtime.status import EstadoAutoclave


@pytest.fixture(autouse=True)
def _mapas_de_fabrica():
    aio.restablecer_memoria_fabrica_codigo()
    yield
    aio.restablecer_memoria_fabrica_codigo()


def _ctx(tmp_path, cambios=None, pendiente=None, texto=None):
    ruta = tmp_path / "data" / "asignacion_io.json"
    arch = aio.ArchivoAsignacion(ruta)
    if texto is not None:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(texto, encoding="utf-8")
    elif cambios is not None:
        arch.guardar(cambios, "ing", pendiente or [])
    ctx = BackendContext()
    ctx.cargar_asignacion_io(archivo=aio.ArchivoAsignacion(ruta))
    return ctx, ruta


def test_sin_archivo_rige_la_de_fabrica(tmp_path):
    ctx, _ = _ctx(tmp_path)
    assert ctx.motivo_asignacion == ""
    assert aio.en_memoria() == aio.fabrica_codigo()
    assert ctx.alarm_manager.activas() == []


def test_la_vigente_se_aplica_al_arrancar_persistencia_tras_reiniciar(tmp_path):
    """Lo guardado en data/ sobrevive al reinicio: un contexto nuevo (= un
    backend recién arrancado) la aplica antes de construir el control."""
    ctx, _ = _ctx(tmp_path, {"vapor_camara": 25, "pres_camara": 13}, ["vapor_camara", "pres_camara"])
    assert EstadoAutoclave.map_do["vapor_camara"] == 24
    assert EstadoAutoclave.map_pres["pres_camara"] == 4
    assert sorted(ctx.asignacion_pendiente) == ["pres_camara", "vapor_camara"]
    assert ctx.verificacion_asignacion["estado"] == "pendiente"
    # segundo "reinicio": sigue aplicada
    aio.restablecer_memoria_fabrica_codigo()
    ctx2 = BackendContext()
    ctx2.cargar_asignacion_io(archivo=ctx.archivo_asignacion)
    assert EstadoAutoclave.map_do["vapor_camara"] == 24


@pytest.mark.parametrize("texto", ["{dañado", '{"formato": 1, "cambios": {"vapor_camara": 3}}'])
def test_archivo_danado_bloquea_con_alarma_sin_usar_fabrica_en_silencio(tmp_path, texto):
    ctx, _ = _ctx(tmp_path, texto=texto)
    assert ctx.motivo_asignacion.startswith("Asignación de E/S inválida")
    [alarma] = ctx.alarm_manager.activas()
    assert alarma.codigo == "CONFIGURACION_INVALIDA"
    assert alarma.definicion.bloquea_inicio is True


def test_construir_control_bloquea_antes_de_start_si_el_archivo_esta_danado(tmp_path, monkeypatch):
    loop = MagicMock()
    monkeypatch.setattr(ctx_mod, "build_serial", lambda units, al_conectar=None: MagicMock())
    monkeypatch.setattr(ctx_mod, "build_doors_cfg", lambda profile: [])
    for nombre in ("SetOutput", "ServicioPuertas", "RealtimePrinter", "CycleLogger"):
        monkeypatch.setattr(ctx_mod, nombre, MagicMock())
    monkeypatch.setattr(ctx_mod, "ControlLoop", MagicMock(return_value=loop))
    ctx, _ = _ctx(tmp_path, texto="{dañado")
    ctx.construir_control(object())
    nombres = [c[0] for c in loop.method_calls]
    assert nombres.index("bloquear_por_configuracion") < nombres.index("start")
    assert "Asignación de E/S" in loop.bloquear_por_configuracion.call_args.args[0]


def test_fabrica_del_yaml_invalida_es_fallo_bloqueante(tmp_path, monkeypatch):
    from autoclave.backend.arranque.secuencia import ErrorArranque
    monkeypatch.setattr(aio, "fabrica", MagicMock(side_effect=aio.ErrorAsignacion(
        [{"codigo": "conflicto", "funcion": "a", "puerto": 1, "tipo": "DO", "ocupado_por": "b"}])))
    with pytest.raises(ErrorArranque) as e:
        BackendContext().cargar_asignacion_io(archivo=aio.ArchivoAsignacion(tmp_path / "x.json"))
    assert e.value.codigo == "CONFIGURACION_INVALIDA"


# ── verificación tras reiniciar ─────────────────────────────────────────────

def _datos(conectado=True, pres_nueva=101.0):
    pres = [0.0] * 8
    pres[4] = pres_nueva           # AI 13
    return {"connected": conectado, "raw_di": [0] * 56, "raw_do": [0] * 32,
            "temperature": [20.0] * 8, "pressure": pres}


def _verificar(ctx, datos, plazo_s=10.0):
    reloj = [0.0]
    ctx.units = MagicMock()
    ctx.units.get_all.return_value = datos
    ctx.db = MagicMock()

    def dormir(s):
        reloj[0] += s
    ctx.iniciar_verificacion_asignacion(plazo_s=plazo_s, reloj=lambda: reloj[0], dormir=dormir)
    ctx._hilo_verificacion_io.join(5)
    return ctx


def test_verificacion_ok_registra_y_limpia_la_marca(tmp_path):
    ctx, ruta = _ctx(tmp_path, {"vapor_camara": 25, "pres_camara": 13}, ["vapor_camara", "pres_camara"])
    _verificar(ctx, _datos())
    assert ctx.verificacion_asignacion == {"estado": "ok",
                                           "funciones": {"vapor_camara": "ok", "pres_camara": "ok"}}
    eventos = [c.args[0] for c in ctx.db.registrar_auditoria.call_args_list]
    assert eventos == ["reasignacion_io_verificada"] * 2
    entidades = {c.kwargs["entidad"]: c.kwargs["valor_nuevo"] for c in ctx.db.registrar_auditoria.call_args_list}
    assert entidades == {"vapor_camara": "DO 25", "pres_camara": "AI 13"}
    assert json.loads(ruta.read_text(encoding="utf-8"))["verificacion_pendiente"] == []


def test_verificacion_sin_respuesta_conserva_la_marca(tmp_path):
    """Lazo abierto en el puerto nuevo (0,0 kPa): no responde."""
    ctx, ruta = _ctx(tmp_path, {"pres_camara": 13}, ["pres_camara"])
    _verificar(ctx, _datos(pres_nueva=0.0))
    assert ctx.verificacion_asignacion["estado"] == "fallida"
    assert ctx.verificacion_asignacion["funciones"] == {"pres_camara": "sin_respuesta"}
    c = ctx.db.registrar_auditoria.call_args
    assert c.kwargs["detalle"]["resultado"] == "sin_respuesta"
    assert json.loads(ruta.read_text(encoding="utf-8"))["verificacion_pendiente"] == ["pres_camara"]


def test_verificacion_sin_tarjeta_vence_el_plazo(tmp_path):
    ctx, _ = _ctx(tmp_path, {"vapor_camara": 25}, ["vapor_camara"])
    _verificar(ctx, _datos(conectado=False), plazo_s=5.0)
    assert ctx.verificacion_asignacion["estado"] == "fallida"


def test_sin_pendientes_no_verifica(tmp_path):
    ctx, _ = _ctx(tmp_path, {"vapor_camara": 25}, [])
    ctx.iniciar_verificacion_asignacion()
    assert getattr(ctx, "_hilo_verificacion_io", None) is None
    assert ctx.verificacion_asignacion["estado"] == "sin_cambios"

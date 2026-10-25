"""R11 (tanda 11, D11-1): reinicio del software al cambiar la impresora.

Backend: PUT /printer/config con `reiniciar` guarda la bandera con auditoría y
luego reinicia el software (`reiniciar_software`): el mismo cierre ordenado de
"Apagar equipo" (ALL_OFF y parada del lazo, base de datos) pero SIN apagar
Windows, auditado como `software_reiniciado` con motivo, y el backend termina
con CODIGO_REINICIO_SOFTWARE para que el lanzador relance todo. Rechazado en
CICLO; permitido en PREPARACION, PREPARADO y FALLA.

Ninguna prueba reinicia nada de verdad: el hilo de cierre se captura y el
"detener uvicorn" es un registro en memoria."""

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from autoclave.backend import reinicio
from autoclave.core.runtime.vigilancia_impresora import ConfigImpresora
from autoclave.state_machine.machine.enum_global import GlobalState
from tests.helpers.backend_doble import cabecera, cargar_servidor, modulo_backend


@pytest.fixture
def entorno(monkeypatch, tmp_path):
    orden = []
    ctx = MagicMock()
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    ctx.estado.get_flag.return_value = False
    ctx.sin_base_de_datos = False
    ctx.control_loop.apagando = False
    ctx.control_loop.bloqueo_maquina.return_value = threading.RLock()
    ctx.control_loop.iniciar_apagado.side_effect = lambda: orden.append("iniciar_apagado")
    ctx.control_loop.stop.side_effect = lambda: orden.append("detener_lazo")
    ctx.db.close.side_effect = lambda: orden.append("cerrar_base")
    ctx.db.registrar_auditoria.side_effect = lambda ev, **k: orden.append("auditar:" + ev)
    config = ConfigImpresora(tmp_path / "impresora.json")
    real_guardar = config.guardar

    def guardar(valor):
        orden.append(f"guardar:{valor}")
        return real_guardar(valor)
    config.guardar = guardar
    ctx.config_impresora = config
    srv, _ = cargar_servidor(ctx)

    apagados = []
    monkeypatch.setattr(modulo_backend("rutas.apagado"), "_apagar_windows", lambda: apagados.append(True))
    monkeypatch.setattr(modulo_backend("rutas.apagado"), "_apagado_windows_habilitado", lambda: True)
    hilos = []
    real = threading.Thread

    def falso(target, **k):
        if k.get("name") in ("ReiniciarSoftware", "ApagarEquipo"):
            args = k.get("args", ())
            return SimpleNamespace(start=lambda: hilos.append((k["name"], lambda: target(*args))))
        return real(target=target, **k)
    monkeypatch.setattr(srv.threading, "Thread", falso)

    # "detener uvicorn" simulado: registra el pedido y su código de salida
    detenido = []
    monkeypatch.setattr(reinicio, "_al_reiniciar", None)
    reinicio.registrar(lambda: detenido.append(True))
    solicitudes = []

    def solicitar(motivo, retraso_s=1.0, dormir=None, codigo=reinicio.CODIGO_REINICIO):
        orden.append(f"solicitar:{codigo}")
        solicitudes.append((motivo, codigo))
        return True
    monkeypatch.setattr(reinicio, "solicitar", solicitar)
    yield SimpleNamespace(client=TestClient(srv.app), ctx=ctx, srv=srv, orden=orden, hilos=hilos,
                          apagados=apagados, solicitudes=solicitudes, config=config)
    monkeypatch.setattr(reinicio, "_al_reiniciar", None)


def _put(e, habilitada=False, reiniciar=True, rol="tecnico"):
    cuerpo = {"habilitada": habilitada}
    if reiniciar is not None:
        cuerpo["reiniciar"] = reiniciar
    return e.client.put("/printer/config", headers=cabecera(e.srv, rol), json=cuerpo)


def _auditorias(e, evento):
    return [c for c in e.ctx.db.registrar_auditoria.call_args_list if c.args[0] == evento]


# ── confirmar: guardar → cerrar → relanzar ─────────────────────────────────

def test_confirmar_guarda_audita_cierra_sin_apagar_windows_y_pide_relanzar(entorno):
    e = entorno
    r = _put(e)
    assert r.status_code == 200, r.text
    assert r.json()["reiniciando"] is True and r.json()["habilitada"] is False
    assert e.config.habilitada() is False
    [(nombre, secuencia)] = e.hilos
    assert nombre == "ReiniciarSoftware"
    secuencia()
    assert e.orden == ["guardar:False", "iniciar_apagado", "auditar:impresora_configurada",
                       "auditar:software_reiniciado", "detener_lazo", "cerrar_base",
                       f"solicitar:{reinicio.CODIGO_REINICIO_SOFTWARE}"]
    assert e.apagados == []                         # nunca shutdown de Windows
    assert e.solicitudes[0][1] == reinicio.CODIGO_REINICIO_SOFTWARE


def test_la_auditoria_lleva_el_motivo_y_el_estado(entorno):
    e = entorno
    assert _put(e).status_code == 200
    [llamada] = _auditorias(e, "software_reiniciado")
    detalle = llamada.kwargs["detalle"]
    assert detalle["motivo"] == "impresora_configurada"
    assert detalle["estado"] == "PREPARADO"
    assert llamada.kwargs["usuario"] == "usuario_tecnico"
    [imp] = _auditorias(e, "impresora_configurada")
    assert imp.kwargs["valor_anterior"] == {"habilitada": True}
    assert imp.kwargs["valor_nuevo"] == {"habilitada": False}


def test_al_reiniciar_no_aplica_la_configuracion_en_caliente(entorno):
    """La bandera rige al volver a abrir; aplicar ahora lanzaría la verificación
    de la impresora en pleno cierre."""
    e = entorno
    assert _put(e).status_code == 200
    e.ctx.aplicar_config_impresora.assert_not_called()


@pytest.mark.parametrize("estado", [GlobalState.PREPARACION, GlobalState.PREPARADO,
                                    GlobalState.FALLA])
def test_permitido_en_preparacion_preparado_y_falla(entorno, estado):
    e = entorno
    e.ctx.estado.get_machine_state.return_value = estado
    assert _put(e).status_code == 200
    assert _auditorias(e, "software_reiniciado")[0].kwargs["detalle"]["estado"] == estado.name


# ── rechazos: nada se guarda ni se reinicia ────────────────────────────────

def test_rechazado_en_ciclo_sin_guardar_ni_reiniciar(entorno):
    e = entorno
    e.ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    r = _put(e)
    assert r.status_code == 409 and r.json()["codigo"] == "estado_no_permitido"
    assert e.config.habilitada() is True
    assert e.hilos == [] and e.solicitudes == []
    assert _auditorias(e, "software_reiniciado") == []
    e.ctx.control_loop.iniciar_apagado.assert_not_called()


def test_sin_reiniciar_tambien_se_rechaza_en_ciclo(entorno):
    """D11-1.3: igual que las otras acciones de Parámetros del equipo."""
    e = entorno
    e.ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    assert _put(e, reiniciar=None).status_code == 409
    assert e.config.habilitada() is True


def test_ciclo_entre_guardar_y_cerrar_deshace_la_bandera(entorno):
    """Si al volver a comprobar bajo el lock ya hay ciclo (carrera con un
    inicio desde la otra pantalla), la escritura se deshace (como R8)."""
    e = entorno
    estados = iter([GlobalState.PREPARADO, GlobalState.CICLO])
    e.ctx.estado.get_machine_state.side_effect = lambda: next(estados, GlobalState.CICLO)
    r = _put(e)
    assert r.status_code == 409
    assert e.config.habilitada() is True
    assert e.hilos == [] and _auditorias(e, "impresora_configurada") == []


def test_sin_lanzador_que_relance_no_guarda_nada(entorno, monkeypatch):
    e = entorno
    monkeypatch.setattr(reinicio, "_al_reiniciar", None)
    r = _put(e)
    assert r.status_code == 503 and r.json()["codigo"] == "reinicio_no_disponible"
    assert e.config.habilitada() is True and e.hilos == []


def test_con_un_apagado_o_reinicio_en_curso_se_rechaza(entorno):
    e = entorno
    e.ctx.control_loop.apagando = True
    r = _put(e)
    assert r.status_code == 409 and r.json()["codigo"] == "apagado_en_curso"
    assert e.config.habilitada() is True and e.hilos == []


def test_operador_no_puede(entorno):
    e = entorno
    assert _put(e, rol="operador").status_code == 403
    assert e.config.habilitada() is True and e.hilos == []


# ── sin `reiniciar` (menú PySide): como antes ──────────────────────────────

def test_sin_reiniciar_guarda_y_aplica_como_antes(entorno):
    e = entorno
    r = _put(e, reiniciar=None)
    assert r.status_code == 200 and r.json().get("reiniciando") is False
    assert e.config.habilitada() is False
    e.ctx.aplicar_config_impresora.assert_called_once_with()
    assert e.hilos == [] and _auditorias(e, "software_reiniciado") == []


# ── la secuencia de cierre ─────────────────────────────────────────────────

def test_la_secuencia_sigue_aunque_falle_un_paso(entorno):
    e = entorno
    assert _put(e).status_code == 200
    e.ctx.control_loop.stop.side_effect = OSError("puerto roto")
    e.ctx.db.close.side_effect = RuntimeError("db")
    e.hilos[0][1]()
    assert e.solicitudes and e.apagados == []


def test_tras_el_cierre_ordenado_el_lifespan_no_vuelve_a_detener_el_lazo(entorno):
    """El lifespan de uvicorn corre al salir: el lazo ya se detuvo en la
    secuencia (un segundo ALL_OFF sobre el puerto cerrado solo dejaría error)."""
    import asyncio
    e = entorno
    assert _put(e).status_code == 200
    e.hilos[0][1]()
    e.ctx.control_loop.stop.reset_mock()

    async def correr():
        async with e.srv._ciclo_de_vida(e.srv.app):
            pass
    asyncio.run(correr())
    e.ctx.control_loop.stop.assert_not_called()


def test_apagar_equipo_sigue_apagando_windows(entorno):
    """El parámetro nuevo de la secuencia no cambia "Apagar equipo"."""
    e = entorno
    e.ctx.programas_para_seguridad.return_value = []
    e.ctx.temp_max_tras_ciclo.return_value = None
    e.ctx.profile = None
    r = e.client.post("/system/shutdown", json={"ventana": "principal"})
    assert r.status_code == 200
    [(nombre, secuencia)] = e.hilos
    assert nombre == "ApagarEquipo"
    secuencia()
    assert e.apagados == [True] and e.solicitudes == []


def test_el_evento_tiene_texto_en_la_bitacora():
    import json
    from pathlib import Path
    from autoclave.core.runtime.bitacora import EVENTOS
    assert "software_reiniciado" in EVENTOS
    raiz = Path(__file__).resolve().parents[1] / "src" / "autoclave" / "i18n"
    for lang in ("es", "en"):
        d = json.loads((raiz / f"{lang}.json").read_text(encoding="utf-8"))
        assert d["bitacora"]["ev"]["software_reiniciado"]


# ── Revisión de seguridad (SAF-01..03) ─────────────────────────────────────

def _estado_seguro(ctx, activo=True, requiere_confirmacion=False, paro=False):
    ctx.control_loop.estado_seguro.activo = activo
    ctx.control_loop.estado_seguro.requiere_confirmacion = requiere_confirmacion
    ctx.control_loop.datos_vigentes = True
    ctx.estado.get_flag.side_effect = lambda k: paro if k == "PARO_EMERGENCIA" else False


@pytest.mark.parametrize("preparar, codigo", [
    # SAF-01: el protocolo de estado seguro actuando sobre las válvulas
    (lambda c: _estado_seguro(c), "estado_seguro_activo"),
    # confirmación pendiente tras un paro real (D9-1.2): se perdería al reiniciar
    (lambda c: _estado_seguro(c, requiere_confirmacion=True), "confirmacion_pendiente"),
    # estado seguro pausado por el paro: todavía no terminó
    (lambda c: _estado_seguro(c, paro=True), "estado_seguro_activo"),
    # modo prueba activo o con el ALL_OFF de su salida sin confirmar
    (lambda c: setattr(c.control_loop, "test_mode_active", True), "modo_prueba_activo"),
    (lambda c: setattr(c.control_loop, "salidas_sin_confirmar_pendiente", True),
     "modo_prueba_activo"),
])
def test_saf01_rechaza_con_estado_seguro_confirmacion_o_modo_prueba(entorno, preparar, codigo):
    e = entorno
    e.ctx.estado.get_machine_state.return_value = GlobalState.FALLA
    preparar(e.ctx)
    r = _put(e)
    assert r.status_code == 409 and r.json()["codigo"] == codigo
    assert e.config.habilitada() is True and e.hilos == []
    e.ctx.control_loop.iniciar_apagado.assert_not_called()
    assert _auditorias(e, "software_reiniciado") == []


def test_saf01_falla_con_el_estado_seguro_terminado_si_se_permite(entorno):
    e = entorno
    e.ctx.estado.get_machine_state.return_value = GlobalState.FALLA
    _estado_seguro(e.ctx, activo=False)
    assert _put(e).status_code == 200


def test_saf01_se_vuelve_a_comprobar_bajo_el_lock_y_deshace(entorno):
    """El estado seguro se activa entre el guardado y el bloqueo: 409 y la
    bandera vuelve a su valor."""
    e = entorno
    previo = e.ctx.config_impresora.guardar

    def guardar(valor):
        previo(valor)
        if valor is False:
            _estado_seguro(e.ctx)
    e.ctx.config_impresora.guardar = guardar
    r = _put(e)
    assert r.status_code == 409 and r.json()["codigo"] == "estado_seguro_activo"
    assert e.config.habilitada() is True and e.hilos == []


def test_saf02_dos_solicitudes_simultaneas_no_dejan_archivo_y_bitacora_en_desacuerdo(entorno):
    """La segunda espera a que la primera termine lectura-guardado-bloqueo y
    se rechaza (apagando) sin tocar el archivo."""
    e = entorno
    escrito, soltar = threading.Event(), threading.Event()
    previo = e.ctx.config_impresora.guardar

    def guardar(valor):
        previo(valor)
        if valor is False and not escrito.is_set():
            escrito.set()
            soltar.wait(5)                   # la primera queda entre guardar y bloquear
    e.ctx.config_impresora.guardar = guardar

    def iniciar_apagado():
        e.orden.append("iniciar_apagado")
        e.ctx.control_loop.apagando = True
    e.ctx.control_loop.iniciar_apagado.side_effect = iniciar_apagado
    resultados = {}
    primera = threading.Thread(target=lambda: resultados.setdefault("a", _put(e, False)))
    primera.start()
    assert escrito.wait(5)
    segunda = threading.Thread(target=lambda: resultados.setdefault("b", _put(e, True)))
    segunda.start()
    segunda.join(0.5)
    assert segunda.is_alive()                # espera al cerrojo del reinicio
    soltar.set()
    primera.join(5)
    segunda.join(5)
    assert resultados["a"].status_code == 200
    assert resultados["b"].status_code == 409
    assert e.config.habilitada() is False    # lo que escribió y auditó la primera
    nuevos = [c.kwargs["valor_nuevo"] for c in _auditorias(e, "impresora_configurada")]
    assert nuevos == [{"habilitada": False}]


def test_saf03_si_no_se_puede_deshacer_queda_auditado(entorno):
    e = entorno
    previo = e.ctx.config_impresora.guardar
    estados = iter([GlobalState.PREPARADO, GlobalState.CICLO])
    e.ctx.estado.get_machine_state.side_effect = lambda: next(estados, GlobalState.CICLO)

    def guardar(valor):
        if valor is True:                    # la reversión falla
            raise OSError("disco lleno")
        return previo(valor)
    e.ctx.config_impresora.guardar = guardar
    r = _put(e)
    assert r.status_code == 409
    assert e.config.habilitada() is False and e.hilos == []
    [llamada] = _auditorias(e, "impresora_configurada")
    assert llamada.kwargs["valor_nuevo"] == {"habilitada": False}
    assert llamada.kwargs["detalle"]["reversion_fallida"] is True

# tests/test_registro_arranque.py
#
# Registro de etapas de arranque (backend/arranque/registro.py) que publica
# GET /arranque (planeacion_barra_arranque_real.md §5 y §7).

import threading

import pytest

from autoclave.backend.arranque.registro import (
    ETAPAS_ARRANQUE,
    EstadoEtapa,
    RegistroArranque,
)

CLAVES = [c for c, _, _ in ETAPAS_ARRANQUE]
BACKEND_Y_LANZADOR = CLAVES[:8]


def _completar(reg, claves):
    for c in claves:
        reg.iniciar(c)
        reg.completar(c)


def test_las_nueve_etapas_con_pesos_y_origen_de_la_tabla_7():
    assert ETAPAS_ARRANQUE == (
        ("verificando_instalacion", 1.0, "lanzador"),
        ("liberando_procesos",      1.0, "lanzador"),
        ("iniciando_servicios",     2.0, "backend"),
        ("cargando_configuracion",  1.0, "backend"),
        ("verificando_calibracion", 1.0, "backend"),
        ("abriendo_base_datos",     1.0, "backend"),
        ("conectando_modulos_es",   2.0, "backend"),
        ("verificando_sensores",    2.0, "backend"),
        ("preparando_interfaz",     1.0, "ui"),
    )


def test_instantanea_inicial_cumple_el_contrato():
    inst = RegistroArranque().instantanea()
    assert set(inst) == {"terminado", "falloBloqueante", "etapaActual", "etapas"}
    assert inst["terminado"] is False
    assert inst["falloBloqueante"] is False
    assert inst["etapaActual"] == "verificando_instalacion"
    assert [e["clave"] for e in inst["etapas"]] == CLAVES
    for e in inst["etapas"]:
        assert set(e) == {"clave", "estado", "codigo", "peso"}
        assert e["estado"] == "pendiente"
        assert e["codigo"] is None
        assert isinstance(e["peso"], float)


def test_transiciones_validas_y_etapa_actual():
    reg = RegistroArranque()
    reg.iniciar("verificando_instalacion")
    assert reg.etapa_actual == "verificando_instalacion"
    assert reg.estado_de("verificando_instalacion") == EstadoEtapa.EN_CURSO
    reg.completar("verificando_instalacion")
    assert reg.estado_de("verificando_instalacion") == EstadoEtapa.OK
    assert reg.etapa_actual == "liberando_procesos"   # primera pendiente


def test_degradado_cuenta_como_completada_y_conserva_el_codigo():
    reg = RegistroArranque()
    _completar(reg, BACKEND_Y_LANZADOR[:5])
    reg.iniciar("abriendo_base_datos")
    reg.degradar("abriendo_base_datos", "ARR_SIN_BD")
    _completar(reg, BACKEND_Y_LANZADOR[6:])
    inst = reg.instantanea()
    assert inst["terminado"] is True
    assert inst["falloBloqueante"] is False
    bd = inst["etapas"][5]
    assert (bd["estado"], bd["codigo"]) == ("degradado", "ARR_SIN_BD")


def test_fallo_es_bloqueante_y_es_la_etapa_actual():
    reg = RegistroArranque()
    _completar(reg, BACKEND_Y_LANZADOR[:4])
    reg.iniciar("verificando_calibracion")
    reg.fallar("verificando_calibracion", "ARR_CALIBRACION")
    inst = reg.instantanea()
    assert inst["falloBloqueante"] is True
    assert inst["terminado"] is False
    assert inst["etapaActual"] == "verificando_calibracion"
    assert inst["etapas"][4]["codigo"] == "ARR_CALIBRACION"


@pytest.mark.parametrize("cerrar, reabrir", [
    (lambda r, c: r.completar(c), lambda r, c: r.iniciar(c)),
    (lambda r, c: r.fallar(c, "X"), lambda r, c: r.completar(c)),
    (lambda r, c: r.degradar(c, "X"), lambda r, c: r.iniciar(c)),
    (lambda r, c: r.completar(c), lambda r, c: r.fallar(c, "X")),
])
def test_no_hay_retroceso(cerrar, reabrir):
    reg = RegistroArranque()
    reg.iniciar("cargando_configuracion")
    cerrar(reg, "cargando_configuracion")
    antes = reg.instantanea()
    with pytest.raises(ValueError):
        reabrir(reg, "cargando_configuracion")
    assert reg.instantanea() == antes


def test_completar_sin_iniciar_y_clave_desconocida_son_errores():
    reg = RegistroArranque()
    with pytest.raises(ValueError):
        reg.completar("cargando_configuracion")
    with pytest.raises(ValueError):
        reg.iniciar("no_existe")


def test_terminado_no_espera_a_la_etapa_de_la_ui():
    reg = RegistroArranque()
    _completar(reg, BACKEND_Y_LANZADOR)
    inst = reg.instantanea()
    assert inst["terminado"] is True
    assert inst["etapaActual"] is None
    assert inst["etapas"][8]["estado"] == "pendiente"   # preparando_interfaz: la completa cada UI


def test_anotar_deja_el_codigo_sin_marcar_fallo():
    reg = RegistroArranque()
    reg.iniciar("conectando_modulos_es")
    reg.anotar("conectando_modulos_es", "ARR_SIN_ES")
    inst = reg.instantanea()
    assert inst["falloBloqueante"] is False
    assert inst["etapaActual"] == "conectando_modulos_es"
    assert inst["etapas"][6] == {"clave": "conectando_modulos_es", "estado": "en_curso",
                                 "codigo": "ARR_SIN_ES", "peso": 2.0}
    reg.completar("conectando_modulos_es")
    assert reg.instantanea()["etapas"][6]["codigo"] is None   # al conectar se limpia


def test_anotar_fuera_de_en_curso_es_error():
    reg = RegistroArranque()
    with pytest.raises(ValueError):
        reg.anotar("conectando_modulos_es", "ARR_SIN_ES")


def test_la_instantanea_es_una_copia_independiente():
    reg = RegistroArranque()
    inst = reg.instantanea()
    inst["etapas"][0]["estado"] = "ok"
    inst["terminado"] = True
    assert reg.instantanea()["etapas"][0]["estado"] == "pendiente"
    assert reg.terminado is False


def test_lectura_concurrente_mientras_avanzan_las_etapas():
    reg = RegistroArranque()
    errores, vistos = [], []
    fin = threading.Event()

    def leer():
        try:
            while not fin.is_set():
                inst = reg.instantanea()
                estados = [e["estado"] for e in inst["etapas"][:8]]
                # monotonía: nunca una etapa ok después de una pendiente anterior
                vistos.append(estados)
                if inst["terminado"]:
                    assert all(s in ("ok", "degradado") for s in estados)
        except Exception as e:   # pragma: no cover - solo si falla
            errores.append(e)

    lectores = [threading.Thread(target=leer) for _ in range(4)]
    for t in lectores:
        t.start()
    for _ in range(50):
        r = RegistroArranque()
        _completar(r, BACKEND_Y_LANZADOR)
    _completar(reg, BACKEND_Y_LANZADOR)
    fin.set()
    for t in lectores:
        t.join()
    assert errores == []
    assert reg.terminado is True
    for estados in vistos:
        # las etapas se completan en orden: lo completado es siempre un prefijo
        completadas = [s == "ok" for s in estados]
        assert completadas == sorted(completadas, reverse=True)

"""AJUSTES 2026-11-02 (revisión de las fases 2 a 5): códigos de rechazo
propios de las rutas de Opciones que el cliente deja pasar solo en su ruta.

Antes llegaban como "error_generico" y los textos de los controladores
(`_MENSAJES`) nunca se usaban. Se comprueba:

(a) `sesion_backend.codigos_conocidos(ruta)` deja pasar cada código en su
    ruta (y subrutas) y fuera de ella `interpretar` da "error_generico";
(b) para cada código existe texto en el `_MENSAJES` del controlador que
    atiende esa ruta.
"""
import importlib

import pytest

from autoclave.ui_qml import sesion_backend

# ruta -> códigos esperados (los reales del backend, verificados en la revisión)
ESPERADOS = {
    "/email": {"correo_invalido", "duplicado", "demasiados", "nombre_largo",
               "sin_destinatarios", "correo_no_configurado", "envio_fallido",
               "envio_desactivado", "ARCHIVO_NO_ESCRIBIBLE"},
    "/maintenance": {"reloj_invalido", "reloj_adelantado", "calibracion_en_curso"},
    "/programas": {"nombre_repetido", "programa_activo", "programa_no_encontrado",
                   "programa_existente"},
    "/global_params": {"no_existe", "solo_lectura", "tipo_invalido", "fuera_de_rango",
                       "incoherente", "calibracion_en_curso"},
    "/language": {"ARCHIVO_NO_ESCRIBIBLE"},
    "/units": {"ARCHIVO_NO_ESCRIBIBLE"},
    "/printer/config": {"ARCHIVO_NO_ESCRIBIBLE", "reinicio_no_disponible",
                        "estado_seguro_activo", "confirmacion_pendiente",
                        "modo_prueba_activo"},
}

# ruta -> controlador que la atiende y muestra su rechazo
CONTROLADOR = {
    "/email": "conectividad_controller",
    "/maintenance": "mantenimiento_controller",
    "/programas": "manejo_ciclos_controller",
    "/global_params": "parametros_equipo_controller",
    "/language": "parametros_equipo_controller",
    "/units": "parametros_equipo_controller",
    "/printer/config": "parametros_equipo_controller",
}

# Textos que faltan en controladores ajenos a este cambio (pedidos al
# director). xfail estricto: al añadirlos, hay que quitar la entrada.
FALTAN_AJENOS: set = set()

CASOS = sorted((r, c) for r, cs in ESPERADOS.items() for c in cs)


def _rutas_de(codigo):
    return {r for r, cs in ESPERADOS.items() if codigo in cs}


def test_tabla_por_ruta_coincide():
    tabla = {}
    for prefijo, codigos in sesion_backend._CODIGOS_POR_RUTA:
        tabla.setdefault(prefijo, set()).update(codigos)
    for ruta, codigos in ESPERADOS.items():
        assert tabla.get(ruta) == codigos, ruta


def test_no_son_globales():
    # si alguno fuera global, pasaría en cualquier ruta
    globales = sesion_backend.codigos_conocidos("")
    assert not (set().union(*ESPERADOS.values()) & globales)


@pytest.mark.parametrize("ruta,codigo", CASOS)
def test_pasa_en_su_ruta(ruta, codigo):
    for r in (ruta, ruta + "/x", ruta + "?a=1", ruta + "/x?a=1"):
        assert codigo in sesion_backend.codigos_conocidos(r)
        res = sesion_backend.interpretar(409, {"codigo": codigo}, r)
        assert res.causa == codigo


@pytest.mark.parametrize("ruta,codigo", CASOS)
def test_error_generico_fuera_de_su_ruta(ruta, codigo):
    propias = _rutas_de(codigo)
    otras = ["/status", "/cycle/parameter", "/io/assignment", "/usuarios",
             ruta + "x", "/x" + ruta]
    otras += [r for r in ESPERADOS if r not in propias]
    for r in otras:
        assert codigo not in sesion_backend.codigos_conocidos(r), (codigo, r)
        res = sesion_backend.interpretar(409, {"codigo": codigo}, r)
        assert res.causa == sesion_backend.ERROR_GENERICO, (codigo, r)


def _param_texto():
    for ruta, codigo in CASOS:
        marcas = ()
        if (ruta, codigo) in FALTAN_AJENOS:
            marcas = (pytest.mark.xfail(strict=True,
                                        reason="texto pendiente en un controlador ajeno"),)
        yield pytest.param(ruta, codigo, marks=marcas, id=f"{ruta}-{codigo}")


@pytest.mark.parametrize("ruta,codigo", list(_param_texto()))
def test_controlador_tiene_texto(ruta, codigo):
    mod = importlib.import_module(f"autoclave.ui_qml.controllers.{CONTROLADOR[ruta]}")
    texto = mod._MENSAJES.get(codigo)
    assert isinstance(texto, str) and texto, (CONTROLADOR[ruta], codigo)

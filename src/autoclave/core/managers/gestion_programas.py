# core/managers/gestion_programas.py
#
# O1 (tanda 5; planeacion_opciones.md v4 §3.1): gestión de programas para
# técnico e ingeniero. Neutral (sin FastAPI ni Qt): el backend valida rol y
# estado y audita; aquí solo las reglas sobre los programas y sus archivos.
#
# - Habilitar / deshabilitar: bandera "habilitado" en el JSON del programa de
#   usuario. Un programa deshabilitado no se ofrece en Preciclo ni se
#   selecciona. El programa activo no se puede deshabilitar.
# - Duplicar: copia el programa de usuario de origen a cycles/user/ con un
#   número nuevo (nunca reutilizado), "personalizado": true, y deja sus valores
#   como defecto del duplicado en cycles/defecto/<id>.json.
# - Borrar: solo programas personalizados, nunca el activo ni uno de fábrica.
#   Su número queda registrado como usado y no vuelve a asignarse.
#
# Las escrituras son atómicas (.tmp + fsync + os.replace).
#
# Modo fábrica (Etapa 2; planeacion_modo_fabrica.md §5.3, D-05..D-07, DF-06,
# PA-07). Estas funciones no leen la base: el backend les pasa el estado
# (`modo_fabrica`).
# - En FÁBRICA, crear y duplicar dan un programa de fábrica del equipo
#   ("fabrica_equipo": true, sin "personalizado") con el primer número libre
#   del 1 al 10, sin consultar ni escribir numeros_usados.json; con los 10
#   ocupados, 409 `maximo_programas_fabrica`.
# - En ENTREGADO, un programa de usuario nuevo toma max(11, numero_nuevo()).
# - borrar_fabrica: borra un programa de fábrica (genérico sembrado o del
#   equipo) con su .bak y su defecto, sin registrar el número, y lo anota en
#   fabrica_vistos.lst y fabrica_borrados.lst (el cargador y la siembra no lo
#   recrean).

import json
import os
import re

from autoclave.core.managers.cycle_manager import Cycle
from autoclave.core.runtime import sensores_ciclo as sc
from autoclave.utils.resources import (MARCA_FABRICA_BORRADOS, MARCA_FABRICA_VISTOS,
                                       _FABRICA_LEGADA, escribir_lista_ids, leer_lista_ids)

NUMEROS_USADOS = "numeros_usados.json"   # en cycles/user/
NOMBRE_MAX = 40
# Modo fábrica (D-05, PA-07): rango de los programas de fábrica y primer número
# de los programas de usuario en ENTREGADO
MAXIMO_NUMERO_FABRICA = 10
PRIMER_NUMERO_USUARIO = 11


class ErrorPrograma(Exception):
    def __init__(self, codigo: str, motivo: str, estado_http: int = 409):
        super().__init__(motivo)
        self.codigo, self.motivo, self.estado_http = codigo, motivo, estado_http


def _escribir_atomico(ruta: str, data) -> None:
    tmp = ruta + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, ruta)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def programa(cm, numero: int):
    for c in list(cm.cycles.values()):
        if getattr(c, "number", None) == numero:
            return c
    raise ErrorPrograma("programa_no_encontrado", f"Programa {numero} no encontrado", 404)


def _de_usuario(c) -> None:
    if getattr(c, "source", "") != "user" or not hasattr(c, "_path"):
        raise ErrorPrograma("programa_de_fabrica", "Solo se gestionan programas de usuario", 422)


def _numeros_usados(cm) -> set[int]:
    ruta = os.path.join(cm.carpeta("cycles/user"), NUMEROS_USADOS)
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            return {n for n in json.load(f) if isinstance(n, int) and not isinstance(n, bool)}
    except (OSError, ValueError, TypeError):
        return set()


def _registrar_numero(cm, numero: int) -> None:
    usados = _numeros_usados(cm) | {numero}
    _escribir_atomico(os.path.join(cm.carpeta("cycles/user"), NUMEROS_USADOS), sorted(usados))


def numero_nuevo(cm) -> int:
    """Siguiente número libre: mayor que todo número existente, de fábrica o
    ya usado alguna vez (los números nunca se reutilizan)."""
    vistos = {c.number for c in list(cm.cycles.values()) if getattr(c, "number", None)}
    vistos |= set(cm.fabrica) | set(cm.defectos) | _numeros_usados(cm)
    return max(vistos | {0}) + 1


def numero_usuario_nuevo(cm) -> int:
    """PA-07 (ENTREGADO): número de un programa de usuario nuevo,
    max(11, numero_nuevo()). Los existentes no se renumeran."""
    return max(PRIMER_NUMERO_USUARIO, numero_nuevo(cm))


def _es_numero(n) -> bool:
    return isinstance(n, int) and not isinstance(n, bool)


def numero_fabrica_libre(cm) -> int:
    """D-07 (FÁBRICA): primer número del 1 al 10 que no ocupa ningún programa
    cargado (de usuario o genérico de factory/, también uno que cedió su
    número), ni un genérico de fábrica, ni un defecto. No consulta
    numeros_usados.json. 409 `maximo_programas_fabrica` con los 10 ocupados."""
    ocupados = set()
    for c in list(cm.cycles.values()):
        for n in (getattr(c, "number", None), getattr(c, "numero_json", None)):
            if _es_numero(n):
                ocupados.add(n)
    ocupados |= {n for n in list(cm.fabrica) + list(cm.defectos) if _es_numero(n)}
    for n in range(1, MAXIMO_NUMERO_FABRICA + 1):
        if n not in ocupados:
            return n
    raise ErrorPrograma("maximo_programas_fabrica",
                        f"Ya hay {MAXIMO_NUMERO_FABRICA} programas de fábrica", 409)


def fijar_habilitado(cm, numero: int, habilitado: bool, activo_id: str | None) -> tuple[bool, bool]:
    """Devuelve (anterior, nuevo)."""
    if not isinstance(habilitado, bool):
        raise ErrorPrograma("VALOR_INVALIDO", "habilitado debe ser verdadero o falso", 422)
    c = programa(cm, numero)
    _de_usuario(c)
    if not habilitado and c.id == activo_id:
        raise ErrorPrograma("programa_activo", "No se puede deshabilitar el programa seleccionado")
    anterior = getattr(c, "habilitado", True)
    _escribir_campo(c, "habilitado", habilitado)
    c.habilitado = habilitado
    return anterior, habilitado


def _clave_nombre(nombre: str) -> str:
    return " ".join(nombre.split()).casefold()


def _nombre_valido(cm, nombre) -> str:
    """No vacío, hasta NOMBRE_MAX, sin caracteres de control (van al ticket y
    al historial) y distinto de todo programa existente (revisión O1, SAF-03:
    un duplicado con el mismo nombre se confundiría con el original)."""
    if not isinstance(nombre, str) or not nombre.strip():
        raise ErrorPrograma("VALOR_INVALIDO", "El nombre no puede estar vacío", 422)
    if any(not ch.isprintable() for ch in nombre):      # saltos de línea, tabuladores, control
        raise ErrorPrograma("VALOR_INVALIDO", "El nombre tiene caracteres no válidos", 422)
    nombre = " ".join(nombre.split())
    if len(nombre) > NOMBRE_MAX:
        raise ErrorPrograma("VALOR_INVALIDO", f"El nombre admite hasta {NOMBRE_MAX} caracteres", 422)
    if any(_clave_nombre(getattr(c, "name", "") or "") == _clave_nombre(nombre)
           for c in list(cm.cycles.values())):
        raise ErrorPrograma("nombre_repetido", "Ya existe un programa con ese nombre", 409)
    return nombre


def _id_nuevo(cm, numero: int) -> str:
    """programa_<n>; en FÁBRICA un número se reutiliza, así que el id de un
    programa borrado (fabrica_borrados.lst) no vuelve: se le agrega un sufijo
    para que la bitácora y la última modificación no mezclen los dos."""
    usuario = cm.carpeta("cycles/user")
    try:
        borrados = leer_lista_ids(usuario, MARCA_FABRICA_BORRADOS) or set()
    except OSError:
        borrados = set()
    candidato, k = f"programa_{numero}", 2
    while (candidato in borrados or candidato in cm.cycles
           or os.path.exists(os.path.join(usuario, f"{candidato}.json"))):
        candidato, k = f"programa_{numero}_{k}", k + 1
    return candidato


def duplicar(cm, numero: int, nombre, *, modo_fabrica: bool = False) -> Cycle:
    """Duplica (o «Crear», C9) el programa `numero`. `modo_fabrica` True
    (equipo en FÁBRICA): programa de fábrica del equipo con número del 1 al
    10; False (ENTREGADO): programa de usuario personalizado desde el 11."""
    origen = programa(cm, numero)
    _de_usuario(origen)
    if getattr(origen, "danado", None):
        raise ErrorPrograma("PROGRAMA_NO_EDITABLE", "Programa dañado: no se puede duplicar")
    nombre = _nombre_valido(cm, nombre)
    # revisión O1 (SAF-04): el duplicado cumple las mismas reglas que la carga
    from autoclave.core.managers import catalogo_parametros
    errores = catalogo_parametros.errores_programa(origen.parameters)
    if errores:
        raise ErrorPrograma("PROGRAMA_NO_EDITABLE", "Programa fuera del catálogo: " + errores[0])
    nuevo_num = numero_fabrica_libre(cm) if modo_fabrica else numero_usuario_nuevo(cm)
    nuevo_id = _id_nuevo(cm, nuevo_num) if modo_fabrica else f"programa_{nuevo_num}"
    with open(origen._path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # valores vigentes en memoria (los mismos que el disco tras cada guardado)
    data["parameters"] = json.loads(json.dumps(origen.parameters))
    data.update({"cycle_id": nuevo_id, "cycle_number": nuevo_num, "display_name": nombre,
                 "habilitado": True, "duplicado_de": numero})
    if modo_fabrica:
        data.pop("personalizado", None)
        data["fabrica_equipo"] = True
    else:
        data.pop("fabrica_equipo", None)
        data["personalizado"] = True
    carpeta_user = cm.carpeta("cycles/user")
    ruta = os.path.join(carpeta_user, f"{nuevo_id}.json")
    if os.path.exists(ruta) or nuevo_id in cm.cycles:
        raise ErrorPrograma("programa_existente", f"Ya existe {nuevo_id}")
    # defecto del duplicado = valores del origen al duplicar
    carpeta_def = cm.carpeta("cycles/defecto")
    os.makedirs(carpeta_def, exist_ok=True)
    defecto = {"cycle_id": nuevo_id, "cycle_number": nuevo_num, "display_name": nombre,
               "parameters": data.get("parameters", {})}
    ruta_def = os.path.join(carpeta_def, f"{nuevo_id}.json")
    if not modo_fabrica:
        _registrar_numero(cm, nuevo_num)        # primero: el número nunca se reutiliza
    try:
        _escribir_atomico(ruta_def, defecto)
        _escribir_atomico(ruta, data)
    except Exception:
        for r in (ruta, ruta_def):
            if os.path.exists(r):
                os.remove(r)
        raise

    c = origen.copia()
    c.id, c.name, c.number = nuevo_id, nombre, nuevo_num
    c.source, c._path = "user", ruta
    c.habilitado, c.personalizado = True, not modo_fabrica
    c.fabrica_equipo = modo_fabrica
    c.numero_json = nuevo_num
    c._ruta_defecto = ruta_def
    cm.cycles[nuevo_id] = c
    cm.defectos[nuevo_num] = Cycle(nuevo_id, nombre, json.loads(json.dumps(defecto["parameters"])),
                                   nuevo_num)
    return c


def borrar(cm, numero: int, activo_id: str | None) -> Cycle:
    c = programa(cm, numero)
    _de_usuario(c)
    if not getattr(c, "personalizado", False):
        raise ErrorPrograma("programa_de_fabrica", "Solo se borran programas personalizados", 422)
    if c.id == activo_id:
        raise ErrorPrograma("programa_activo", "No se puede borrar el programa seleccionado")
    _registrar_numero(cm, numero)          # el número no se reutiliza
    # en dos pasos (revisión O1, SAF-01): se aparta con sufijo .borrado y solo
    # se elimina tras auditar (confirmar_borrado); si la auditoría falla,
    # deshacer_borrado lo restaura
    rutas = [c._path, c._path + ".bak"]
    ruta_def = os.path.join(cm.carpeta("cycles/defecto"), os.path.basename(c._path))
    if re.fullmatch(r"programa_\d+\.json", os.path.basename(c._path)):
        rutas.append(ruta_def)
    apartadas = []
    for r in rutas:
        if os.path.exists(r):
            os.replace(r, r + ".borrado")
            apartadas.append(r)
    c._apartadas = apartadas
    c._defecto_borrado = cm.defectos.pop(numero, None)
    cm.cycles.pop(c.id, None)
    return c


def _defectos_de(cm, c) -> list[str]:
    """Archivos de cycles/defecto del programa: por `cycle_number` (el
    índice de los defectos) o por `cycle_id`, no por el nombre del archivo."""
    carpeta = cm.carpeta("cycles/defecto")
    if not os.path.isdir(carpeta):
        return []
    numero = c.number if _es_numero(c.number) else getattr(c, "numero_json", None)
    salida = []
    for nombre in sorted(os.listdir(carpeta)):
        if not nombre.endswith(".json"):
            continue
        ruta = os.path.join(carpeta, nombre)
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            continue
        if not isinstance(d, dict):
            continue
        if (_es_numero(numero) and d.get("cycle_number") == numero) or d.get("cycle_id") == c.id:
            salida.append(ruta)
    return salida


def _restaurar_lista(usuario: str, nombre: str, previa) -> None:
    if previa is None:
        ruta = os.path.join(usuario, nombre)
        if os.path.exists(ruta):
            os.remove(ruta)
    else:
        escribir_lista_ids(usuario, nombre, previa)


def borrar_fabrica(cm, cycle_id: str, activo_id: str | None) -> Cycle:
    """Modo fábrica (D-06, DF-06): borra un programa de fábrica, genérico
    (sembrado en cycles/user o cargado de factory/) o del equipo. No un
    personalizado (422 `no_es_programa_de_fabrica`) ni el seleccionado (409
    `programa_activo`). El número no va a numeros_usados.json. El id queda en
    fabrica_vistos.lst y en fabrica_borrados.lst. Como `borrar`, en dos pasos:
    los archivos se apartan con .borrado y `confirmar_borrado` los elimina
    tras auditar; `deshacer_borrado_fabrica` lo revierte todo."""
    c = cm.cycles.get(cycle_id) if isinstance(cycle_id, str) else None
    if c is None:
        raise ErrorPrograma("programa_no_encontrado", f"Programa {cycle_id} no encontrado", 404)
    if (getattr(c, "personalizado", False) is True
            or getattr(c, "source", "") not in ("user", "factory")):
        raise ErrorPrograma("no_es_programa_de_fabrica",
                            "Solo se borran aquí programas de fábrica", 422)
    if c.id == activo_id:
        raise ErrorPrograma("programa_activo", "No se puede borrar el programa seleccionado")
    usuario = cm.carpeta("cycles/user")
    try:
        previa_vistos = leer_lista_ids(usuario, MARCA_FABRICA_VISTOS)
        previa_borrados = leer_lista_ids(usuario, MARCA_FABRICA_BORRADOS)
    except OSError:
        raise ErrorPrograma("error_archivo",
                            "No se pudo leer la lista de programas de fábrica", 503)
    rutas = []
    if c.source == "user" and getattr(c, "_path", None):
        rutas = [c._path, c._path + ".bak"]
    rutas += _defectos_de(cm, c)
    apartadas = []
    try:
        # primero las listas: si el borrado queda a medias, el programa no
        # vuelve a aparecer desde factory/ ni por la siembra
        escribir_lista_ids(usuario, MARCA_FABRICA_BORRADOS, (previa_borrados or set()) | {c.id})
        base_vistos = previa_vistos if previa_vistos is not None else set(_FABRICA_LEGADA)
        escribir_lista_ids(usuario, MARCA_FABRICA_VISTOS, base_vistos | {c.id})
        for r in rutas:
            if os.path.exists(r):
                os.replace(r, r + ".borrado")
                apartadas.append(r)
    except OSError:
        for r in apartadas:
            if os.path.exists(r + ".borrado"):
                os.replace(r + ".borrado", r)
        try:
            _restaurar_lista(usuario, MARCA_FABRICA_BORRADOS, previa_borrados)
            _restaurar_lista(usuario, MARCA_FABRICA_VISTOS, previa_vistos)
        except OSError:
            pass
        raise ErrorPrograma("error_archivo", "No se pudo borrar el programa", 503)
    c._apartadas = apartadas
    c._listas_previas = (previa_vistos, previa_borrados)
    numero = c.number if _es_numero(c.number) else getattr(c, "numero_json", None)
    c._numero_borrado = numero
    c._defecto_borrado = cm.defectos.pop(numero, None) if _es_numero(numero) else None
    fab = cm.fabrica.get(numero) if _es_numero(numero) else None
    c._fabrica_borrada = cm.fabrica.pop(numero) if getattr(fab, "id", None) == c.id else None
    cm.cycles.pop(c.id, None)
    return c


def deshacer_borrado_fabrica(cm, c) -> None:
    """Auditoría fallida (RB-03.5): todo vuelve como estaba."""
    for r in getattr(c, "_apartadas", []):
        if os.path.exists(r + ".borrado"):
            os.replace(r + ".borrado", r)
    cm.cycles[c.id] = c
    usuario = cm.carpeta("cycles/user")
    previa_vistos, previa_borrados = getattr(c, "_listas_previas", (None, None))
    _restaurar_lista(usuario, MARCA_FABRICA_BORRADOS, previa_borrados)
    _restaurar_lista(usuario, MARCA_FABRICA_VISTOS, previa_vistos)
    numero = getattr(c, "_numero_borrado", None)
    if _es_numero(numero):
        if getattr(c, "_defecto_borrado", None) is not None:
            cm.defectos[numero] = c._defecto_borrado
        if getattr(c, "_fabrica_borrada", None) is not None:
            cm.fabrica[numero] = c._fabrica_borrada


def confirmar_borrado(c) -> None:
    for r in getattr(c, "_apartadas", []):
        if os.path.exists(r + ".borrado"):
            os.remove(r + ".borrado")


def deshacer_borrado(cm, c) -> None:
    for r in getattr(c, "_apartadas", []):
        if os.path.exists(r + ".borrado"):
            os.replace(r + ".borrado", r)
    cm.cycles[c.id] = c
    if getattr(c, "_defecto_borrado", None) is not None:
        cm.defectos[c.number] = c._defecto_borrado


def deshacer_duplicado(cm, c) -> None:
    """Auditoría fallida (SAF-01): el duplicado desaparece; su número queda usado."""
    for r in (c._path, getattr(c, "_ruta_defecto", None)):
        if r and os.path.exists(r):
            os.remove(r)
    cm.cycles.pop(c.id, None)
    cm.defectos.pop(c.number, None)


def _escribir_campo(c, clave: str, valor) -> None:
    """Escribe (o quita, con valor None) un campo de primer nivel del JSON."""
    with open(c._path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if valor is None:
        data.pop(clave, None)
    else:
        data[clave] = valor
    _escribir_atomico(c._path, data)


def deshacer_habilitado(cm, numero: int, anterior: bool) -> None:
    c = programa(cm, numero)
    _escribir_campo(c, "habilitado", anterior)
    c.habilitado = anterior


def deshacer_entradas(cm, numero: int, previas) -> None:
    c = programa(cm, numero)
    _escribir_campo(c, "entradas_mostradas", list(previas) if previas else None)
    c.entradas_mostradas = list(previas) if previas else None


# ── Entradas mostradas por programa (1 a 3; planeacion_opciones.md v4 §3.1) ──

# Antes de O11 eran la omisión fija de Preciclo y Ciclo. O11 (tanda 11,
# D11-7.4): la omisión depende de los roles del programa (entradas_por_omision).
ENTRADAS_POR_OMISION = ("temp_camara", "temp_referencia", "pres_camara")

# O11 (D11-7): sensor de temperatura del programa (sensores_ciclo) -> nombre de la AI
AI_DE_SENSOR = {"temp_camara": "temp_camara", "temp_2_camara": "temp_2_camara",
                "temp_ref": "temp_referencia"}
# Tanda 17 (SON-01, decisión de Cristian): ya no se rechaza al guardar; se
# conserva el nombre por compatibilidad con la interfaz (mensaje_de).
SENSOR_NO_EN_USO = "SENSOR_NO_EN_USO"


def entradas_no_en_uso(c, habilitadas: list[str] | None = None) -> list[str]:
    """AI de los sensores de temperatura que el programa no usa (ni Principal
    ni Referencia). Con una asignación inválida solo cuenta como en uso el
    Principal de respaldo (temp_camara), igual que sensores_ciclo.sensor_principal.

    Tanda 17 (SON-01, revierte O11 / D11-7.1): ya no filtra nada; la interfaz
    la usa para rotular la entrada «(monitoreo)». Con `habilitadas` (AI que
    declara el perfil), solo las de sondas instaladas."""
    en_uso = set(sc.sensores_en_uso(c))
    lista = [AI_DE_SENSOR[s] for s in sc.SENSORES if s not in en_uso]
    if habilitadas is not None:
        lista = [e for e in lista if e in habilitadas]
    return lista


def entradas_por_omision(c, habilitadas: list[str] | None = None) -> list[str]:
    """O11 (D11-7.4, propuesta del asistente): [AI del Principal, primera
    Referencia si la hay, pres_camara], hasta 3, entre las habilitadas. Si
    ninguna está habilitada, la primera habilitada en uso; sin habilitadas
    conocidas (None o vacía), la lista sin filtrar. La omisión sigue sin
    proponer sondas No en uso (SON-01 solo permite elegirlas)."""
    refs = sc.sensores_referencia(c)
    lista = [AI_DE_SENSOR[sc.sensor_principal(c)]]
    if refs:
        lista.append(AI_DE_SENSOR[refs[0]])
    lista.append("pres_camara")
    if not habilitadas:
        return lista[:3]
    no = set(entradas_no_en_uso(c))
    return ([e for e in lista if e in habilitadas][:3]
            or [e for e in habilitadas if e not in no][:1] or lista[:3])


def entradas_disponibles(c, habilitadas: list[str]) -> list[str]:
    """Lo que ofrece el selector: las AI habilitadas en el equipo (perfil de
    instalación: una sonda no instalada no aparece). Tanda 17 (SON-01,
    decisión de Cristian): también las de sondas No en uso del programa."""
    return list(habilitadas)


def entradas_de(c, habilitadas: list[str]) -> list[str]:
    """Selección vigente del programa; sin selección propia, o si no queda
    ninguna, la omisión. Tanda 17 (SON-01, decisión de Cristian): las de
    sondas No en uso se conservan (se muestran como monitoreo); con
    `habilitadas` conocidas se quitan las que el equipo no declara (una sonda
    no instalada sigue oculta)."""
    propias = getattr(c, "entradas_mostradas", None)
    if isinstance(propias, list):
        visibles = [e for e in propias if not habilitadas or e in habilitadas]
        if visibles:
            return visibles
    return entradas_por_omision(c, habilitadas)


# Tanda 17 (SON-01, decisión de Cristian): se retira entradas_tras_cambio_de_rol
# (O11, D11-7.3). Al pasar una sonda a No en uso ya no sale de las Entradas
# mostradas del programa.


def fijar_entradas(cm, numero: int, entradas, habilitadas: list[str]) -> tuple[list, list]:
    """Valida (1 a 3, sin repetir, entre las AI habilitadas en `io_enabled`) y
    guarda en el JSON del programa. Devuelve (anterior, nueva). Tanda 17
    (SON-01, decisión de Cristian): una sonda No en uso del programa ya no se
    rechaza (retirado el rechazo SENSOR_NO_EN_USO de O11, D11-7.1)."""
    if (not isinstance(entradas, list) or not 1 <= len(entradas) <= 3
            or not all(isinstance(e, str) for e in entradas) or len(set(entradas)) != len(entradas)):
        raise ErrorPrograma("ASIGNACION_INVALIDA", "Elija de 1 a 3 entradas distintas", 422)
    fuera = [e for e in entradas if e not in habilitadas]
    if fuera:
        raise ErrorPrograma("SENSOR_NO_DISPONIBLE",
                            f"Entrada no habilitada en el equipo: {', '.join(fuera)}", 422)
    c = programa(cm, numero)
    _de_usuario(c)
    anterior = entradas_de(c, habilitadas)
    _escribir_campo(c, "entradas_mostradas", list(entradas))
    c.entradas_mostradas = list(entradas)
    return anterior, list(entradas)

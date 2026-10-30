# autoclave/installation/modelo.py
#
# Nombre comercial del equipo (M1, tanda 7; planeacion_asistente_modelo.md §2,
# decisiones AM-1 a AM-6 de Cristian). Módulo puro: lo usan el puente del
# asistente de instalación, la validación del perfil y las pruebas.
#
#   SPK-SAT <capacidad><carga>[2][-LAB]
#
# - capacidad: litros nominales de la cámara, entero de 20 a 2000 (AM-4);
# - carga: "V" (vertical) o "H" (horizontal);
# - "2" solo con dos puertas;
# - "-LAB" solo en la clase piso_lab (AM-2).
#
# Solo las clases de piso se instalan (AM-3): cualquier otra clase lanza
# ValueError. El nombre es un rótulo informativo (AM-5): no cambia ningún
# parámetro del equipo.

import re

CLASES_INSTALABLES = ("piso", "piso_lab")
CAPACIDAD_MIN = 20
CAPACIDAD_MAX = 2000
TIPOS_CARGA = ("V", "H")
PUERTAS_VALIDAS = (1, 2)


def _valor_clase(clase):
    """Acepta la enumeración EquipmentClass o su valor en texto."""
    return getattr(clase, "value", clase)


def clase_instalable(clase) -> bool:
    """True si la clase se puede instalar con el asistente (AM-3)."""
    return _valor_clase(clase) in CLASES_INSTALABLES


def _entero_estricto(valor) -> bool:
    # bool es subclase de int: True no es una capacidad ni un número de puertas
    return isinstance(valor, int) and not isinstance(valor, bool)


def calcular_modelo(clase, capacidad_litros, tipo_carga, door_count) -> str:
    """Nombre comercial calculado. Lanza ValueError si algún dato está fuera
    de la regla (clase de mesa u otra, capacidad no entera o fuera de 20-2000,
    carga distinta de "V"/"H", puertas distintas de 1/2)."""
    valor = _valor_clase(clase)
    if valor not in CLASES_INSTALABLES:
        raise ValueError(f"clase fuera de alcance: {valor!r} (solo {list(CLASES_INSTALABLES)})")
    if not _entero_estricto(capacidad_litros) or not CAPACIDAD_MIN <= capacidad_litros <= CAPACIDAD_MAX:
        raise ValueError(f"capacidad_litros inválida: {capacidad_litros!r} "
                         f"(entero de {CAPACIDAD_MIN} a {CAPACIDAD_MAX})")
    if not isinstance(tipo_carga, str) or tipo_carga not in TIPOS_CARGA:
        raise ValueError(f"tipo_carga inválido: {tipo_carga!r} (se espera 'V' o 'H')")
    if not _entero_estricto(door_count) or door_count not in PUERTAS_VALIDAS:
        raise ValueError(f"door_count inválido: {door_count!r} (se espera 1 o 2)")
    return (f"SPK-SAT {capacidad_litros}{tipo_carga}"
            + ("2" if door_count == 2 else "")
            + ("-LAB" if valor == "piso_lab" else ""))


_PATRON_MODELO = re.compile(r"SPK-SAT ([1-9][0-9]{1,3})([VH])(2?)(-LAB)?")


def desglosar_modelo(nombre) -> dict | None:
    """Inverso de calcular_modelo (E2, tanda 8; D8-3.23): {clase,
    capacidad_litros, tipo_carga, door_count} de un nombre "SPK-SAT …", o None
    si el nombre no sigue la regla (modelos anteriores a M1). Solo informativo:
    lo usa la cabecera del PDF, que recibe el modelo guardado con el ciclo."""
    if not isinstance(nombre, str):
        return None
    m = _PATRON_MODELO.fullmatch(nombre)
    if m is None:
        return None
    datos = {"clase": "piso_lab" if m.group(4) else "piso", "capacidad_litros": int(m.group(1)),
             "tipo_carga": m.group(2), "door_count": 2 if m.group(3) else 1}
    try:
        if calcular_modelo(datos["clase"], datos["capacidad_litros"], datos["tipo_carga"],
                           datos["door_count"]) != nombre:
            return None
    except ValueError:
        return None
    return datos

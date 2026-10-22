
import copy
import json
import os
import sys
import logging
from autoclave.utils.resources import resource_path
from autoclave.core.runtime.sensores_ciclo import asignacion_por_omision, interpretar_asignacion
from autoclave.core.managers import catalogo_parametros

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _numero_de_ciclo(valor) -> int | None:
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 1:
        return None
    return valor


# Parámetros vinculados (T-17, decisión de Cristian 2026-10-10): deben valer
# siempre lo mismo; editar uno ajusta el otro en la misma operación, tanto en
# el programa almacenado como en la copia del ciclo en curso.
_VINCULADOS = (
    (("calentamiento", "temperatura_calentamiento"),
     ("esterilizacion", "temperatura_esterilizacion")),
)


# R1-P3 (tanda 7, decisión 1.3 de Cristian): `rango_calentamiento` era a la vez
# banda de temperatura (°C) y de presión (kPa) en calentamiento.py. Se separa en
# dos parámetros de clase "diferencia" con el mismo defecto. Un programa viejo
# (archivo, defecto del hospital, .bak o instantánea de recuperación) se migra
# al construir el Cycle copiando el valor a los dos; el archivo queda migrado la
# próxima vez que se guarde.
_RANGO_VIEJO = "rango_calentamiento"
_RANGOS_NUEVOS = (("rango_calentamiento_temp", "°C"), ("rango_calentamiento_pres", "kPa"))
# SAF-04 / SEN-07a (revisión Q1): defecto de fábrica (mismo que el catálogo de
# los perfiles) cuando el viejo no es un dict y no se puede copiar
_RANGO_DEFECTO = {"value": 2.0, "type": "float", "clase": "diferencia", "min": 0, "max": 30}


def migrar_parametros(parameters) -> bool:
    """Migra en el sitio los parámetros de un programa viejo. Devuelve True si
    cambió algo. Si ya trae los nuevos, el viejo se descarta sin tocarlos."""
    cal = parameters.get("calentamiento") if isinstance(parameters, dict) else None
    if not isinstance(cal, dict) or _RANGO_VIEJO not in cal:
        return False
    viejo = cal[_RANGO_VIEJO]
    reemplazo = {}
    for clave, valor in cal.items():
        if clave != _RANGO_VIEJO:
            if clave not in reemplazo:
                reemplazo[clave] = valor
            continue
        for nueva, unidad in _RANGOS_NUEVOS:
            if nueva in cal:
                reemplazo[nueva] = cal[nueva]
            elif isinstance(viejo, dict):
                hoja = copy.deepcopy(viejo)
                hoja["unit"] = unidad
                hoja["clase"] = "diferencia"
                reemplazo[nueva] = hoja
            else:
                hoja = dict(_RANGO_DEFECTO)
                hoja["unit"] = unidad
                reemplazo[nueva] = hoja
                logger.warning("Programa con '%s' sin formato válido (%r): %s queda con el "
                               "defecto de fábrica %.1f %s", _RANGO_VIEJO, viejo, nueva,
                               _RANGO_DEFECTO["value"], unidad)
    cal.clear()
    cal.update(reemplazo)
    logger.warning("Programa con '%s' (formato anterior): migrado a %s y %s",
                   _RANGO_VIEJO, _RANGOS_NUEVOS[0][0], _RANGOS_NUEVOS[1][0])
    return True


class Cycle:
    def __init__(self, cycle_id: str, name: str, parameters: dict, number: int | None = None):
        self.id = cycle_id
        self.name = name
        migrar_parametros(parameters)          # R1-P3
        self.parameters = parameters
        # Indicativo del ciclo ("cycle_number" del JSON), único entre ciclos.
        # None si falta, no es entero positivo o está repetido.
        self.number = number
        # Roles de los sensores de temperatura (tanda §1.1). La carga desde
        # JSON la fija con interpretar_asignacion (migración perezosa).
        self.sensores: dict = asignacion_por_omision()
        self.sensores_formato_antiguo = True
        # RB-04.4 / RB-05.5 (T10): errores del catálogo al cargar; un programa
        # dañado no se selecciona, no se inicia ni se edita
        self.danado: list[str] = []
        # O1 (tanda 5): gestión de programas. Un programa deshabilitado no se
        # ofrece ni se selecciona; uno personalizado (duplicado en el hospital)
        # se puede borrar. Los de fábrica nunca.
        self.habilitado = True
        self.personalizado = False

    def copia(self) -> "Cycle":
        """Copia profunda de los parámetros (T-17, §5.8): el ciclo en curso
        trabaja con ella, así que editar el programa almacenado no cambia
        ningún valor de una fase ya iniciada."""
        c = Cycle(self.id, self.name, copy.deepcopy(self.parameters), self.number)
        c.source = getattr(self, "source", None)
        # RS-03.4: la asignación de sensores es una instantánea al iniciar
        c.sensores = dict(getattr(self, "sensores", None) or asignacion_por_omision())
        c.sensores_formato_antiguo = getattr(self, "sensores_formato_antiguo", True)
        c.habilitado = getattr(self, "habilitado", True)
        c.personalizado = getattr(self, "personalizado", False)
        c.entradas_mostradas = getattr(self, "entradas_mostradas", None)
        c.nombre_clave = getattr(self, "nombre_clave", None)
        return c

    def instantanea(self) -> dict:
        """Programa con el que corre un ciclo (E4, §7.5): basta para
        reconstruirlo tras un reinicio (desde_instantanea)."""
        return {"cycle_id": self.id, "nombre": self.name, "numero": self.number,
                "source": getattr(self, "source", None),
                "sensores": dict(getattr(self, "sensores", None) or asignacion_por_omision()),
                "parameters": copy.deepcopy(self.parameters)}

    @classmethod
    def desde_instantanea(cls, datos: dict) -> "Cycle":
        c = cls(datos.get("cycle_id", ""), datos.get("nombre", ""),
                copy.deepcopy(datos.get("parameters") or {}), datos.get("numero"))
        c.source = datos.get("source")
        c.sensores, c.sensores_formato_antiguo = interpretar_asignacion(datos.get("sensores"))
        return c

    def get_param(self, *keys, default=None):
        data = self.parameters

        for key in keys:
            data = data.get(key, {})

        return data.get("value", default)

    def vinculados(self, fase: str, path: list[str]) -> list[tuple[str, list[str]]]:
        """Parámetros que una edición de (fase, path) cambia: él mismo y, si
        está en _VINCULADOS, su pareja (solo si existe en este programa)."""
        resultado = [(fase, list(path))]
        if len(path) == 1:
            for a, b in _VINCULADOS:
                for propio, otro in ((a, b), (b, a)):
                    if propio == (fase, path[0]) and self._hoja(otro[0], [otro[1]]) is not None:
                        resultado.append((otro[0], [otro[1]]))
        return resultado

    def _hoja(self, fase: str, path: list[str]):
        """Nodo del parámetro, o None si la ruta no existe."""
        node = self._nodo(fase, path)
        return node if isinstance(node, dict) and "value" in node else None

    def set_param(self, fase: str, path: list[str], value):
        """Actualiza el 'value' de un parámetro navegando fase + path, coercionando
        y validando contra el 'type'/'min'/'max' propio del JSON del ciclo.
        Un parámetro vinculado (_VINCULADOS) arrastra a su pareja, validada
        igual. Devuelve el valor ya coercionado. No muta nada si la validación
        falla."""
        if self.parameters.get(fase) is None:
            raise KeyError(f"El ciclo no tiene la sección '{fase}'")
        if not isinstance(self._nodo(fase, path[:-1]), dict):
            raise KeyError(f"Ruta de parámetro inválida: {'.'.join(path)}")
        if self._hoja(fase, path) is None:
            raise KeyError(f"El parámetro '{'.'.join(path)}' no existe en '{fase}'")

        cambios = [(self._hoja(f, p), catalogo_parametros.coercionar(self._hoja(f, p), f, p, value))
                   for f, p in self.vinculados(fase, path)]
        previos = [(hoja, hoja["value"]) for hoja, _ in cambios]
        for hoja, valor in cambios:
            hoja["value"] = valor
        # Reglas entre parámetros (T10, decisión 1.2): si no se cumplen, nada cambia
        errores = catalogo_parametros.errores_coherencia(self.parameters)
        if errores:
            for hoja, valor in previos:
                hoja["value"] = valor
            raise ValueError("; ".join(errores))
        return cambios[0][1]

    def _nodo(self, fase: str, path: list[str]):
        node = self.parameters.get(fase)
        for key in path:
            if not isinstance(node, dict) or key not in node:
                return None
            node = node[key]
        return node



class CycleManager:
    def __init__(self):
        self.cycles = {}
        self.selected_cycle = None
        # Perfil de fábrica inmutable por NÚMERO de programa (opciones §6.1,
        # T12): el valor por defecto de cada parámetro. Los de usuario con el
        # mismo cycle_id reemplazan al de fábrica en `cycles`, no aquí.
        self.fabrica: dict[int, Cycle] = {}
        # O1 (tanda 5): defectos creados en el hospital (cycles/defecto/), por
        # número. Mandan sobre el de fábrica; el de un duplicado son los valores
        # del origen al duplicar.
        self.defectos: dict[int, Cycle] = {}
        # raíz de las carpetas de ciclos (None = la del paquete); las pruebas
        # la apuntan a una copia temporal
        self.raiz: str | None = None
        # JSON de ciclo que no se pudieron cargar en el último load_all_cycles()
        # (el arranque degrada su etapa con ARR_CICLO_CORRUPTO)
        self.errores_carga: list[str] = []

    def load_all_cycles(self):
        self.cycles.clear()
        self.fabrica.clear()
        self.defectos.clear()
        self.errores_carga = []

        self._load_from_folder("cycles/factory", source="factory")
        self._load_from_folder("cycles/user", source="user")
        self._descartar_numeros_repetidos()
        self._cargar_defectos()

    def carpeta(self, folder_path: str) -> str:
        """Ruta absoluta de cycles/<...> (en el .exe, la copia persistente)."""
        if self.raiz is not None:
            return os.path.join(self.raiz, folder_path)
        return (resource_path(f"autoclave/{folder_path}") if getattr(sys, "frozen", False)
                else os.path.join(BASE_DIR, folder_path))

    def _cargar_defectos(self) -> None:
        carpeta = self.carpeta("cycles/defecto")
        if not os.path.isdir(carpeta):
            return
        for file in os.listdir(carpeta):
            if not file.endswith(".json"):
                continue
            try:
                with open(os.path.join(carpeta, file), "r", encoding="utf-8") as f:
                    data = json.load(f)
                numero = _numero_de_ciclo(data.get("cycle_number"))
                if numero is None:
                    continue
                self.defectos[numero] = Cycle(data["cycle_id"], data.get("display_name", ""),
                                              data.get("parameters", {}), numero)
            except Exception:
                logger.exception("Defecto %s ilegible: se ignora", file)

    def nombre_clave_de(self, cycle) -> str | None:
        """I4 (tanda 6; D-14, §3.7): clave de catálogo del nombre del ciclo. La
        propia, o la del ciclo de fábrica con el mismo cycle_id si el nombre no
        se cambió en el hospital (un nombre propio se muestra igual en ambos
        idiomas). None si no hay."""
        propia = getattr(cycle, "nombre_clave", None)
        if isinstance(propia, str) and propia:
            return propia
        for fab in self.fabrica.values():
            if fab.id == cycle.id and fab.name == cycle.name:
                clave = getattr(fab, "nombre_clave", None)
                return clave if isinstance(clave, str) and clave else None
        return None

    def nombres_de(self, cycle) -> dict:
        """{"es", "en"}: el nombre del ciclo en cada idioma (sin clave, el
        display_name en los dos). Nunca lanza."""
        try:
            from autoclave import i18n
            clave = self.nombre_clave_de(cycle)
            return {idioma: (i18n.t(clave, idioma) if clave and i18n.existe(clave, idioma)
                             else cycle.name) for idioma in i18n.IDIOMAS}
        except Exception:
            return {"es": cycle.name, "en": cycle.name}

    def defecto(self, numero: int):
        """Perfil por defecto de un número de programa: el del hospital
        (cycles/defecto) o, si no hay, el de fábrica. None si ninguno."""
        return self.defectos.get(numero) or self.fabrica.get(numero)

    def _descartar_numeros_repetidos(self):
        """Un mismo cycle_number en dos ciclos distintos es un error de
        configuración: ninguno de los dos lo conserva (se muestra sin número)
        antes que presentar un indicativo ambiguo."""
        por_numero = {}
        for cycle in self.cycles.values():
            if cycle.number is not None:
                por_numero.setdefault(cycle.number, []).append(cycle)
        for numero, ciclos in por_numero.items():
            if len(ciclos) > 1:
                logger.error("cycle_number %d repetido en %s — se descarta en todos",
                             numero, ", ".join(sorted(c.id for c in ciclos)))
                for c in ciclos:
                    c.number = None

    def _load_from_folder(self, folder_path, source):
        # en el .exe, resource_path da la copia persistente junto al ejecutable
        # (los ciclos de usuario se guardan; ver utils/resources.py)
        folder_path = self.carpeta(folder_path)

        logger.info(f"📂 Buscando en: {folder_path}")

        if not os.path.exists(folder_path):
            print("❌ No existe la carpeta")
            return

        for file in os.listdir(folder_path):
            if file.endswith(".json"):
                full_path = os.path.join(folder_path, file)

                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                        cycle = Cycle(
                            cycle_id=data["cycle_id"],
                            name=data.get("display_name", data.get("cycle_name", data["cycle_id"])),
                            parameters=data.get("parameters", {}),
                            number=_numero_de_ciclo(data.get("cycle_number")),
                        )

                        cycle.source = source
                        cycle._path  = full_path
                        cycle.habilitado = data.get("habilitado", True) is not False
                        # I4 (tanda 6; D-14): clave de catálogo del nombre (solo fábrica)
                        clave = data.get("nombre_clave")
                        cycle.nombre_clave = clave if isinstance(clave, str) and clave else None
                        cycle.personalizado = data.get("personalizado", False) is True
                        em = data.get("entradas_mostradas")
                        cycle.entradas_mostradas = (list(em) if isinstance(em, list)
                                                    and all(isinstance(x, str) for x in em) else None)
                        cycle.sensores, cycle.sensores_formato_antiguo =                             interpretar_asignacion(data.get("cycle_temperature_sensors"))
                        if cycle.sensores_formato_antiguo:
                            logger.warning("Ciclo %s: cycle_temperature_sensors ausente o en "
                                           "formato antiguo; se usa la asignación de fábrica "
                                           "(Principal = temp_camara)", cycle.id)

                        # RB-05.5 (T10): valores fuera del catálogo → se intenta
                        # el .bak; si tampoco vale, el programa queda dañado
                        self._validar_al_cargar(cycle, full_path)
                        self.cycles[cycle.id] = cycle
                        if source == "factory" and cycle.number is not None:
                            self.fabrica[cycle.number] = cycle.copia()

                except Exception as e:
                    print(f"⚠️ Error cargando {file}: {e}")
                    self.errores_carga.append(full_path)

    def _validar_al_cargar(self, cycle, full_path: str) -> None:
        errores = catalogo_parametros.errores_programa(cycle.parameters)
        if not errores:
            return
        bak = full_path + ".bak"
        if os.path.exists(bak):
            try:
                with open(bak, "r", encoding="utf-8") as f:
                    respaldo = json.load(f).get("parameters", {})
                migrar_parametros(respaldo)            # R1-P3
                if not catalogo_parametros.errores_programa(respaldo):
                    logger.error("Programa %s fuera del catálogo (%s); se usa %s",
                                 cycle.id, "; ".join(errores), os.path.basename(bak))
                    cycle.parameters = respaldo
                    return
            except Exception:
                logger.exception("Programa %s: %s ilegible", cycle.id, os.path.basename(bak))
        logger.error("Programa %s DAÑADO, no ejecutable: %s", cycle.id, "; ".join(errores))
        cycle.danado = errores
        self.errores_carga.append(full_path)

    def set_default_cycle(self, cycle_id: str):
        if cycle_id in self.cycles:
            self.selected_cycle = self.cycles[cycle_id]
            return

        raise Exception(f"Ciclo por defecto '{cycle_id}' no encontrado")
    
    def get_selected_cycle(self):
        if self.selected_cycle is None:
            raise Exception("No hay ciclo seleccionado")
        return self.selected_cycle
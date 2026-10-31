# Sistema de alarmas, Parte A — Plan de implementación

> **Para agentes:** SUB-SKILL REQUERIDO: usar superpowers:subagent-driven-development (recomendado) o superpowers:executing-plans para implementar este plan tarea por tarea. Los pasos usan casillas (`- [ ]`) para el seguimiento.

**Objetivo:** reemplazar las alarmas de hoy (identificador interno + texto genérico) por un catálogo central con código, título legible, descripción con valores y acción sugerida. Cada alarma pasa a tener instancias con origen, horas y reconocimiento, se guarda en un historial en SQLite y se publica en un contrato `/status` compatible con la interfaz actual.

**Arquitectura:** patrón de reemplazo gradual. Las tareas 1 a 5 construyen el sistema nuevo (catálogo, `AlarmManager` con la API nueva, historial, instancia única, endpoints) **al lado** de la API vieja `report/clear`, que sigue funcionando. Las tareas 6 a 9 migran los módulos, uno por grupo. La tarea 10 borra la API vieja. La suite queda verde al cerrar cada tarea.

**Tecnología:** Python 3.11+, FastAPI (`backend/server.py`), SQLite (`DbManager`), pytest.

**Spec:** `docs/superpowers/specs/2026-10-06-sistema-alarmas-parte-a-design.md`, incluidas las correcciones del 2026-10-07 en §4.3 (origen) y §5.5 (buzer).

## Restricciones globales

- No cambia **cuándo** se dispara ninguna alarma ni su nivel. Equivalencias: ALERTA→AVISO, FALLA→ALARMA, EMERGENCIA→FALLO_CRITICO.
- No se toca el buzer ni ninguna salida digital (spec §5.5, corregida).
- Formato de código: `ÁREA-NN`, con áreas `PUE CIC PRE COM SEN SUM SIS`.
- El origen **nunca** es el estado de la máquina (spec §4.3, corregida). Es la puerta (PUE), el sensor legible (SEN-01) o la fase legible (CIC-01…06, SUM-01, SEN-02, COM-02). En el resto es `None`.
- `motivo_fallo` = `"{codigo} · {titulo}: {descripcion}"`. En los tickets térmicos se usa `" - "` como separador, no `"·"` ni `"—"`, por compatibilidad con la impresora.
- Las horas de los registros usan `datetime.now()`. Todo temporizador sigue con `time.monotonic()` (`CLAUDE.md`).
- **Commits:** el árbol de trabajo tiene cambios ajenos sin confirmar en `server.py`, `db_manager.py`, `ui_bridge.py` y otros archivos (serial, nuevo usuario). **No se hace commit por tarea.** El único commit va en la tarea 10, con aprobación explícita de Cristian, y entra solo lo de alarmas (ver tarea 10, paso 6).
- Comando de pruebas: `python -m pytest -q -p no:cacheprovider <ruta>`. Suite base al iniciar: **1794 passed**.

## Foco de revisión

1. **Clave de alarma en la URL**: lleva `|` y espacios (`PUE-01|Puerta 1`). Reconocerla codificada en la URL debe funcionar (tarea 5).
2. **Plantilla con un valor `None`**: un sensor puede dar `None` y llegar a un campo `{temp:.1f}`. `activar()` no debe lanzar; debe usar "Detalle no disponible." (tarea 2).
3. **Reconocer desde HTTP mientras el loop resuelve**: dos hilos sobre la misma instancia no deben corromper la lista ni dejar una instancia reconocida y resuelta sin borrar (tarea 2).
4. **Base de datos caída o de una versión anterior**: una escritura fallida no debe propagarse al ControlLoop. Abrir una base de datos vieja, sin tabla de alarmas ni columna `codigo_fallo`, debe migrarla (tarea 3).
5. **Alarma sin reconocer al salir de FALLA**: debe sobrevivir como `RESUELTA_SIN_RECONOCER`, y si su condición vuelve, debe reactivarse sin duplicarse ni crear una fila nueva en el historial (tareas 2 y 8).

---

## Mapa de archivos

| Archivo | Acción | Responsabilidad |
|---|---|---|
| `src/autoclave/state_machine/alarms/catalogo.py` | Crear | `Nivel`, `Despeje`, `DefinicionAlarma`, constantes de código, `CATALOGO`, `NOMBRES_LEGIBLES`, `nombre_legible()` |
| `src/autoclave/state_machine/alarms/instancia.py` | Crear | `EstadoInstancia`, `EventoAlarma`, `InstanciaAlarma`, `clave_de()` |
| `src/autoclave/state_machine/alarms/alarm_manager.py` | Modificar | API nueva (`activar/resolver/reconocer/...`), candado y oyentes. API vieja hasta la tarea 10 |
| `src/autoclave/services/domain/logging/historial_alarmas.py` | Crear | Oyente que escribe en `DbManager` y activa SIS-02 si falla |
| `src/autoclave/services/domain/logging/db_manager.py` | Modificar | Tabla `alarmas_historial`, columna `ciclos.codigo_fallo`, métodos de historial |
| `src/autoclave/state_machine/state_machine.py` | Modificar | Recibe `alarm_manager`; `resolver_todas_por_reinicio()` al salir de FALLA |
| `src/autoclave/services/domain/loop/control_loop.py` | Modificar | Pasa su `alarm_manager` a `StateMachine`; COM-01 |
| `src/autoclave/backend/context.py` | Modificar | Registra `HistorialAlarmas` |
| `src/autoclave/backend/server.py` | Modificar | DTO nuevo en `/status`, `eventos_recientes`, `POST /alarms/{clave}/acknowledge`, `GET /alarms/history` |
| `src/autoclave/state_machine/states/{preparacion,preparado,falla,hibernacion,ciclo}.py` | Modificar | Migración a códigos de catálogo |
| `src/autoclave/devices/puertas/advanced_door.py` | Modificar | PUE-04/05 |
| `src/autoclave/core/runtime/status.py` | Modificar | `codigo_fallo`; quitar `Alarmas_activas` (tarea 10) |
| `src/autoclave/services/domain/logging/{cycle_logger,ticket_formatter}.py` | Modificar | `codigo_fallo` en la base de datos y `motivo_ticket()` |
| `src/autoclave/ui_pyside/views/impresion_menu.py` | Modificar | Ticket de alarmas: código, título, hora y origen |
| `src/autoclave/state_machine/alarms/{alarm,alarm_types}.py` | Borrar (tarea 10) | — |
| `tests/alarmas_helpers.py` | Crear | Lectura de llamadas `activar/resolver` sobre `MagicMock` que valida las plantillas |

---

### Tarea 1: Catálogo de alarmas

**Archivos:**
- Crear: `src/autoclave/state_machine/alarms/catalogo.py`
- Probar: `tests/test_alarmas_catalogo.py`

**Interfaces:**
- Produce: `Nivel` (enum con `INFORMATIVO=1, AVISO=2, ALARMA=3, FALLO_CRITICO=4` y las propiedades `requiere_reconocimiento: bool` y `nombre_compat: str`); `Despeje` (`AUTOMATICO`, `MANUAL`); `DefinicionAlarma(codigo, nivel, titulo, descripcion, accion, bloquea_inicio, despeje)` con `campos() -> set[str]` y `renderizar(valores: dict) -> str` (lanza `KeyError/ValueError/TypeError/IndexError` si faltan valores); constantes `SIS_01 … COM_02` (str); `CATALOGO: dict[str, DefinicionAlarma]`; `DEFINICIONES: tuple[DefinicionAlarma, ...]`; `NOMBRES_LEGIBLES: dict[str, str]`; `nombre_legible(clave: str) -> str`.

- [ ] **Paso 1: escribir la prueba que falla**

```python
# tests/test_alarmas_catalogo.py
import re

import pytest

from autoclave.state_machine.alarms import catalogo as cat
from autoclave.state_machine.alarms.catalogo import (
    CATALOGO, DEFINICIONES, Despeje, Nivel, nombre_legible,
)

_AREAS = {"PUE", "CIC", "PRE", "COM", "SEN", "SUM", "SIS"}

# Valores de ejemplo por código: deben cubrir EXACTAMENTE los campos de la
# plantilla. Si una plantilla cambia, esta tabla tiene que cambiar con ella.
_EJEMPLOS = {
    "SIS-01": {"estado": "Preparación"},
    "SIS-02": {"error": "disk I/O error"},
    "SUM-01": {"fase": "Esterilización"},
    "SUM-02": {}, "SUM-03": {}, "SUM-04": {}, "SUM-05": {},
    "SUM-06": {"estado": "Ciclo"},
    "PRE-01": {"pres": 250.0, "minimo": 270.0, "objetivo": 320.0, "rango": 50.0},
    "PRE-02": {"pres": 380.0, "maximo": 370.0, "objetivo": 320.0, "rango": 50.0},
    "PRE-03": {"pres": 70.0, "minimo": 81.3},
    "PRE-04": {"pres": 140.0, "maximo": 121.3},
    "PRE-05": {},
    "PRE-06": {"temp": 72.4, "maximo": 65.0},
    "PUE-01": {"puerta": "Puerta 1"},
    "PUE-02": {"puerta": "Puerta 1", "fase": "Prevacío"},
    "PUE-03": {"puerta": "Puerta 2", "pres": 150.0, "minimo": 180.0, "fase": "Secado"},
    "PUE-04": {"puerta": "Puerta 1"},
    "PUE-05": {"puerta": "Puerta 1"},
    "SEN-01": {"sensor": "Temperatura de cámara", "valor": 0},
    "SEN-02": {"sensores": "Temperatura de cámara", "fase": "Calentamiento"},
    "CIC-01": {"motivo": "x"}, "CIC-02": {"motivo": "x"}, "CIC-03": {"motivo": "x"},
    "CIC-04": {"motivo": "x"}, "CIC-05": {"motivo": "x"}, "CIC-06": {"motivo": "x"},
    "CIC-07": {"temp": 95.0, "maximo": 80.0, "minutos": 31.0},
    "CIC-08": {"puerta": "Puerta 2", "motivo": "bloqueo mecánico"},
    "COM-01": {},
    "COM-02": {"segundos": 5.0, "fase": "Calentamiento"},
}


def test_codigos_unicos():
    assert len(DEFINICIONES) == len(CATALOGO)


@pytest.mark.parametrize("d", DEFINICIONES, ids=lambda d: d.codigo)
def test_formato_y_campos(d):
    assert re.fullmatch(r"[A-Z]{3}-\d{2}", d.codigo)
    assert d.codigo[:3] in _AREAS
    assert isinstance(d.nivel, Nivel) and isinstance(d.despeje, Despeje)
    assert d.titulo.strip() and d.descripcion.strip()
    if d.nivel is not Nivel.INFORMATIVO:
        assert d.accion.strip()


@pytest.mark.parametrize("d", DEFINICIONES, ids=lambda d: d.codigo)
def test_plantilla_coincide_con_ejemplo(d):
    ejemplo = _EJEMPLOS[d.codigo]
    assert d.campos() == set(ejemplo)
    texto = d.renderizar(ejemplo)
    assert "{" not in texto and "}" not in texto


def test_renderizar_sin_valores_lanza():
    with pytest.raises(KeyError):
        CATALOGO["PRE-01"].renderizar({})


def test_todos_los_codigos_tienen_constante():
    constantes = {v for k, v in vars(cat).items() if re.fullmatch(r"[A-Z]{3}_\d{2}", k)}
    assert constantes == set(CATALOGO)


def test_niveles_reconocimiento_y_compat():
    assert Nivel.ALARMA.requiere_reconocimiento
    assert Nivel.FALLO_CRITICO.requiere_reconocimiento
    assert not Nivel.AVISO.requiere_reconocimiento
    assert not Nivel.INFORMATIVO.requiere_reconocimiento
    assert Nivel.AVISO.nombre_compat == "ALERTA"
    assert Nivel.ALARMA.nombre_compat == "FALLA"
    assert Nivel.FALLO_CRITICO.nombre_compat == "EMERGENCIA"


def test_niveles_migrados_iguales_a_hoy():
    # Restricción global: ninguna alarma cambia de nivel.
    esperado = {
        "SIS-01": Nivel.FALLO_CRITICO, "SUM-01": Nivel.FALLO_CRITICO,
        "SEN-02": Nivel.FALLO_CRITICO, "COM-02": Nivel.FALLO_CRITICO,
        "PUE-02": Nivel.ALARMA, "PUE-03": Nivel.ALARMA, "COM-01": Nivel.ALARMA,
        **{f"CIC-0{i}": Nivel.ALARMA for i in range(1, 7)},
    }
    for codigo, d in CATALOGO.items():
        assert d.nivel is esperado.get(codigo, Nivel.AVISO), codigo


@pytest.mark.parametrize("clave", [
    "temp_camara", "temp_2_camara", "temp_ref", "temp_chaqueta",
    "temp_drenaje_cam", "temp_drenaje", "pres_camara", "pres_chaqueta",
    "pres_empaque_1", "pres_empaque_2",
    "PRECALENTAMIENTO", "PRE_VACIO", "CALENTAMIENTO", "ESTERILIZACION",
    "DESCOMPRESION", "SECADO",
])
def test_nombres_legibles_cubren_claves_actuales(clave):
    assert nombre_legible(clave) != clave


def test_nombre_legible_desconocido_devuelve_la_clave():
    assert nombre_legible("sensor_raro") == "sensor_raro"
```

- [ ] **Paso 2: correr la prueba y verificar que falla**

Correr: `python -m pytest -q -p no:cacheprovider tests/test_alarmas_catalogo.py`
Esperado: ERROR de colección, `ModuleNotFoundError: ...alarms.catalogo`.

- [ ] **Paso 3: implementar**

```python
# src/autoclave/state_machine/alarms/catalogo.py
#
# Catálogo central de alarmas (spec 2026-10-06-sistema-alarmas-parte-a §4).
# Nivel y bloqueo son decisiones de seguridad: viven aquí, bajo control de
# versiones, no en configuración editable.

import string
from dataclasses import dataclass
from enum import Enum


class Nivel(Enum):
    INFORMATIVO = 1
    AVISO = 2
    ALARMA = 3
    FALLO_CRITICO = 4

    @property
    def requiere_reconocimiento(self) -> bool:
        return self in (Nivel.ALARMA, Nivel.FALLO_CRITICO)

    @property
    def nombre_compat(self) -> str:
        """Nombre de nivel que esperan los consumidores viejos de /status."""
        return _NOMBRE_COMPAT[self]


_NOMBRE_COMPAT = {
    Nivel.INFORMATIVO: "INFORMATIVO",
    Nivel.AVISO: "ALERTA",
    Nivel.ALARMA: "FALLA",
    Nivel.FALLO_CRITICO: "EMERGENCIA",
}


class Despeje(Enum):
    AUTOMATICO = "AUTOMATICO"
    MANUAL = "MANUAL"


@dataclass(frozen=True)
class DefinicionAlarma:
    codigo: str
    nivel: Nivel
    titulo: str
    descripcion: str
    accion: str
    bloquea_inicio: bool
    despeje: Despeje

    def campos(self) -> set[str]:
        return {campo for _, campo, _, _ in string.Formatter().parse(self.descripcion) if campo}

    def renderizar(self, valores: dict) -> str:
        return self.descripcion.format(**valores)


SIS_01, SIS_02 = "SIS-01", "SIS-02"
SUM_01, SUM_02, SUM_03, SUM_04, SUM_05, SUM_06 = (
    "SUM-01", "SUM-02", "SUM-03", "SUM-04", "SUM-05", "SUM-06")
PRE_01, PRE_02, PRE_03, PRE_04, PRE_05, PRE_06 = (
    "PRE-01", "PRE-02", "PRE-03", "PRE-04", "PRE-05", "PRE-06")
PUE_01, PUE_02, PUE_03, PUE_04, PUE_05 = "PUE-01", "PUE-02", "PUE-03", "PUE-04", "PUE-05"
SEN_01, SEN_02 = "SEN-01", "SEN-02"
CIC_01, CIC_02, CIC_03, CIC_04, CIC_05, CIC_06, CIC_07, CIC_08 = (
    "CIC-01", "CIC-02", "CIC-03", "CIC-04", "CIC-05", "CIC-06", "CIC-07", "CIC-08")
COM_01, COM_02 = "COM-01", "COM-02"

_A, _M = Despeje.AUTOMATICO, Despeje.MANUAL
_AV, _AL, _FC = Nivel.AVISO, Nivel.ALARMA, Nivel.FALLO_CRITICO


def _d(codigo, nivel, bloquea, despeje, titulo, descripcion, accion):
    return DefinicionAlarma(codigo, nivel, titulo, descripcion, accion, bloquea, despeje)


DEFINICIONES: tuple[DefinicionAlarma, ...] = (
    _d(SIS_01, _FC, True, _A, "Paro de emergencia activado",
       "Se presionó el paro de emergencia en estado {estado}. Todas las salidas están apagadas.",
       "Verifique que no haya riesgo y libere el botón de paro."),
    _d(SIS_02, _AV, False, _M, "Historial de alarmas no disponible",
       "No se pudo guardar el historial de alarmas: {error}. Las alarmas siguen "
       "funcionando, pero no quedan registradas.",
       "Avise a soporte técnico."),
    _d(SUM_01, _FC, True, _M, "Corte eléctrico durante el ciclo",
       "Se perdió el suministro eléctrico en la fase {fase}. El ciclo se abortó.",
       "Verifique la alimentación del equipo antes de reiniciar."),
    _d(SUM_02, _AV, True, _A, "Sin suministro eléctrico",
       "La señal de suministro eléctrico está inactiva.",
       "Verifique la alimentación del equipo."),
    _d(SUM_03, _AV, True, _A, "Sin agua para la bomba de vacío",
       "La señal de suministro de agua de la bomba está inactiva.",
       "Abra la válvula de agua de la bomba y verifique la presión de la red."),
    _d(SUM_04, _AV, True, _A, "Sin agua para el generador",
       "La señal de suministro de agua del generador está inactiva.",
       "Abra la válvula de agua del generador y verifique la presión de la red."),
    _d(SUM_05, _AV, True, _A, "Sin aire comprimido",
       "La señal de suministro de aire comprimido está inactiva.",
       "Verifique el compresor y la válvula de aire."),
    _d(SUM_06, _AV, False, _A, "Sin suministro de vapor",
       "No hay suministro de vapor en estado {estado}. La chaqueta queda en espera "
       "hasta que regrese.",
       "Verifique el generador y la válvula de vapor."),
    _d(PRE_01, _AV, True, _A, "Presión de chaqueta baja",
       "La chaqueta está en {pres:.0f} kPa, por debajo del mínimo de {minimo:.0f} kPa "
       "(objetivo {objetivo:.0f} ± {rango:.0f}).",
       "Espere a que la chaqueta alcance presión. Si no sube, verifique el suministro de vapor."),
    _d(PRE_02, _AV, True, _A, "Presión de chaqueta alta",
       "La chaqueta está en {pres:.0f} kPa, por encima del máximo de {maximo:.0f} kPa "
       "(objetivo {objetivo:.0f} ± {rango:.0f}).",
       "Verifique la válvula de vapor de chaqueta."),
    _d(PRE_03, _AV, True, _A, "Presión de cámara baja",
       "La cámara está en {pres:.0f} kPa, por debajo de {minimo:.0f} kPa.",
       "Espere a que la cámara se iguale con la atmósfera."),
    _d(PRE_04, _AV, True, _A, "Presión de cámara alta",
       "La cámara está en {pres:.0f} kPa, por encima de {maximo:.0f} kPa.",
       "No abra la puerta. Espere a que la cámara descomprima."),
    _d(PRE_05, _AV, True, _A, "Agua residual en la cámara",
       "El sensor de nivel detecta agua acumulada en la cámara. Se está drenando.",
       "Si no desaparece, verifique el drenaje de la cámara y la trampa de vapor."),
    _d(PRE_06, _AV, True, _A, "Temperatura de drenaje alta",
       "El drenaje está en {temp:.1f} °C, por encima del máximo de {maximo:.1f} °C. "
       "Se activó el enfriamiento.",
       "Verifique el agua del intercambiador."),
    _d(PUE_01, _AV, True, _A, "Puerta abierta",
       "{puerta} está abierta. El ciclo no puede iniciar.",
       "Cierre la puerta."),
    _d(PUE_02, _AL, True, _M, "Puerta abierta durante el ciclo",
       "{puerta} dejó de detectarse cerrada en la fase {fase}. El ciclo se abortó.",
       "Verifique el sensor de puerta cerrada y el cierre mecánico."),
    _d(PUE_03, _AL, True, _M, "Presión de empaque insuficiente",
       "El empaque de {puerta} bajó a {pres:.0f} kPa (mínimo {minimo:.0f} kPa) en la "
       "fase {fase}. El ciclo se abortó.",
       "Verifique el aire comprimido y el estado del empaque."),
    _d(PUE_04, _AV, False, _A, "Apertura en modo seguro",
       "{puerta} se está abriendo sin bomba de vacío por falla eléctrica.",
       "Ninguna, la apertura continúa."),
    _d(PUE_05, _AV, False, _A, "Cierre en modo seguro",
       "{puerta} se está cerrando sin bomba de vacío por falla eléctrica.",
       "Ninguna, el cierre continúa."),
    _d(SEN_01, _AV, True, _A, "Lectura inválida de sensor",
       "{sensor} entrega una lectura inválida ({valor}).",
       "Verifique la conexión del sensor."),
    _d(SEN_02, _FC, True, _M, "Sensor crítico sin lectura",
       "Sin lectura de: {sensores}, en la fase {fase}. El ciclo se abortó.",
       "Verifique la conexión de los sensores antes de reiniciar."),
    _d(CIC_01, _AL, True, _M, "Fallo en precalentamiento", "{motivo}",
       "Revise el suministro de vapor de la chaqueta."),
    _d(CIC_02, _AL, True, _M, "Fallo en prevacío", "{motivo}",
       "Revise la bomba de vacío y su agua de sello."),
    _d(CIC_03, _AL, True, _M, "Fallo en calentamiento", "{motivo}",
       "Revise el suministro de vapor y la presión del generador."),
    _d(CIC_04, _AL, True, _M, "Fallo en esterilización", "{motivo}",
       "La carga NO está estéril. Revise el suministro de vapor y repita el ciclo."),
    _d(CIC_05, _AL, True, _M, "Fallo en descompresión", "{motivo}",
       "No abra la puerta hasta confirmar presión atmosférica. Revise las válvulas de escape."),
    _d(CIC_06, _AL, True, _M, "Fallo en secado", "{motivo}",
       "Revise la bomba de vacío. La carga puede salir húmeda."),
    _d(CIC_07, _AV, False, _A, "Enfriamiento demorado",
       "La cámara sigue en {temp:.1f} °C (máximo para abrir {maximo:.1f} °C) tras "
       "{minutos:.0f} min.",
       "Espere. La puerta se abrirá sola al enfriar."),
    _d(CIC_08, _AV, False, _A, "Apertura automática denegada",
       "No se pudo abrir {puerta}: {motivo}.",
       "Verifique el bloqueo mecánico de la puerta."),
    _d(COM_01, _AL, True, _A, "Sin comunicación con la tarjeta",
       "No llegan datos válidos de la tarjeta de control.",
       "Verifique el cable USB y la alimentación de la tarjeta."),
    _d(COM_02, _FC, True, _M, "Comunicación perdida durante el ciclo",
       "Se perdió la comunicación con la tarjeta por más de {segundos:.0f} s en la fase "
       "{fase}. El ciclo se abortó.",
       "Verifique el cable USB y la alimentación de la tarjeta antes de reiniciar."),
)

CATALOGO: dict[str, DefinicionAlarma] = {d.codigo: d for d in DEFINICIONES}

NOMBRES_LEGIBLES: dict[str, str] = {
    # Sensores
    "temp_camara": "Temperatura de cámara",
    "temp_2_camara": "Temperatura de cámara 2",
    "temp_ref": "Temperatura de referencia",
    "temp_chaqueta": "Temperatura de chaqueta",
    "temp_drenaje_cam": "Temperatura de drenaje de cámara",
    "temp_drenaje": "Temperatura de drenaje",
    "pres_camara": "Presión de cámara",
    "pres_chaqueta": "Presión de chaqueta",
    "pres_empaque_1": "Presión de empaque puerta 1",
    "pres_empaque_2": "Presión de empaque puerta 2",
    # Fases (CicloState / BaseFase.name)
    "PRECALENTAMIENTO": "Precalentamiento",
    "PRE_VACIO": "Prevacío",
    "CALENTAMIENTO": "Calentamiento",
    "ESTERILIZACION": "Esterilización",
    "DESCOMPRESION": "Descompresión",
    "SECADO": "Secado",
}


def nombre_legible(clave: str) -> str:
    return NOMBRES_LEGIBLES.get(clave, clave)
```

- [ ] **Paso 4: correr la prueba y verificar que pasa**

Correr: `python -m pytest -q -p no:cacheprovider tests/test_alarmas_catalogo.py`
Esperado: todo PASS.

---

### Tarea 2: Instancias y API nueva de `AlarmManager`

**Archivos:**
- Crear: `src/autoclave/state_machine/alarms/instancia.py`
- Modificar: `src/autoclave/state_machine/alarms/alarm_manager.py` (todo el archivo)
- Probar: `tests/test_alarm_manager.py`

**Interfaces:**
- Consume: `CATALOGO`, `DefinicionAlarma`, `Nivel` (tarea 1).
- Produce:
  - `clave_de(codigo: str, origen: str | None) -> str`, que devuelve `codigo` o `"codigo|origen"`.
  - `EstadoInstancia.ACTIVA / RESUELTA_SIN_RECONOCER`.
  - `EventoAlarma.APARECIDA / RESUELTA / RECONOCIDA / REACTIVADA`.
  - `InstanciaAlarma`, con los campos `clave, definicion, origen, valores, descripcion, aparecida, estado, resuelta, reconocida_por, reconocida_en, ciclo_id, id_historial` y las propiedades `codigo`, `titulo`, `nivel`.
  - `AlarmManager(estado=None, catalogo=None, reloj=None)`, con estos métodos:

    | Método | Devuelve |
    |---|---|
    | `activar(codigo, origen=None, **valores)` | `InstanciaAlarma` |
    | `resolver(codigo, origen=None)` | `None` |
    | `obtener(clave)` | `InstanciaAlarma \| None` |
    | `reconocer(clave, usuario)` | `bool` |
    | `resolver_todas_por_reinicio()` | `None` |
    | `activas()` | `list[InstanciaAlarma]` |
    | `eventos_recientes()` | `list[InstanciaAlarma]` |
    | `suscribir(oyente)` | `None`; el oyente es `Callable[[EventoAlarma, InstanciaAlarma], None]` |

  - Constante `DETALLE_NO_DISPONIBLE`.
  - La API vieja (`report`, `clear`, `clear_recoverable`, `active_alarms`) queda intacta hasta la tarea 10. `has_*` mira la lista vieja **y** las instancias `ACTIVA`.

- [ ] **Paso 1: escribir la prueba que falla**

```python
# tests/test_alarm_manager.py
import threading
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from autoclave.state_machine.alarms.alarm_manager import AlarmManager, DETALLE_NO_DISPONIBLE
from autoclave.state_machine.alarms.catalogo import (
    CATALOGO, COM_01, DefinicionAlarma, Despeje, Nivel, PRE_06, PUE_01, SIS_01,
)
from autoclave.state_machine.alarms.instancia import EstadoInstancia, EventoAlarma, clave_de


class _Reloj:
    def __init__(self):
        self.t = datetime(2026, 10, 7, 8, 0, 0)

    def __call__(self):
        self.t += timedelta(seconds=1)
        return self.t


_INFO = DefinicionAlarma("SIS-99", Nivel.INFORMATIVO, "Evento de prueba",
                         "Pasó {algo}.", "", False, Despeje.AUTOMATICO)


def _gestor(con_informativo=False):
    catalogo = dict(CATALOGO)
    if con_informativo:
        catalogo[_INFO.codigo] = _INFO
    eventos = []
    am = AlarmManager(estado=SimpleNamespace(Alarmas_activas=[]), catalogo=catalogo, reloj=_Reloj())
    am.suscribir(lambda ev, inst: eventos.append((ev, inst.clave)))
    return am, eventos


def test_activar_crea_instancia_con_titulo_y_descripcion():
    am, eventos = _gestor()
    inst = am.activar(PRE_06, temp=72.4, maximo=65.0)
    assert inst.clave == "PRE-06" and inst.titulo == "Temperatura de drenaje alta"
    assert "72.4 °C" in inst.descripcion and inst.estado is EstadoInstancia.ACTIVA
    assert eventos == [(EventoAlarma.APARECIDA, "PRE-06")]


def test_activar_de_nuevo_actualiza_valores_sin_evento_ni_nueva_hora():
    am, eventos = _gestor()
    primera = am.activar(PRE_06, temp=70.0, maximo=65.0)
    hora = primera.aparecida
    segunda = am.activar(PRE_06, temp=75.0, maximo=65.0)
    assert segunda is primera and "75.0" in segunda.descripcion
    assert segunda.aparecida == hora and len(eventos) == 1


def test_origen_distingue_instancias():
    am, _ = _gestor()
    am.activar(PUE_01, origen="Puerta 1", puerta="Puerta 1")
    am.activar(PUE_01, origen="Puerta 2", puerta="Puerta 2")
    assert {i.clave for i in am.activas()} == {"PUE-01|Puerta 1", "PUE-01|Puerta 2"}
    assert clave_de("PUE-01", None) == "PUE-01"


def test_codigo_desconocido_lanza():
    am, _ = _gestor()
    with pytest.raises(KeyError):
        am.activar("XXX-01")


@pytest.mark.parametrize("valores", [{}, {"temp": None, "maximo": 65.0}])
def test_plantilla_incompleta_o_none_no_lanza(valores, caplog):
    am, _ = _gestor()
    inst = am.activar(PRE_06, **valores)
    assert inst.descripcion == DETALLE_NO_DISPONIBLE
    assert "PRE-06" in caplog.text


def test_resolver_aviso_sale_de_la_lista():
    am, eventos = _gestor()
    am.activar(PRE_06, temp=70.0, maximo=65.0)
    am.resolver(PRE_06)
    assert am.activas() == []
    assert eventos[-1] == (EventoAlarma.RESUELTA, "PRE-06")


def test_resolver_inexistente_no_hace_nada():
    am, eventos = _gestor()
    am.resolver(PRE_06)
    assert eventos == []


def test_alarma_sin_reconocer_queda_resuelta_sin_reconocer():
    am, _ = _gestor()
    am.activar(COM_01)
    am.resolver(COM_01)
    [inst] = am.activas()
    assert inst.estado is EstadoInstancia.RESUELTA_SIN_RECONOCER and inst.resuelta is not None


def test_reconocer_resuelta_la_saca():
    am, eventos = _gestor()
    am.activar(COM_01)
    am.resolver(COM_01)
    assert am.reconocer("COM-01", "cristian") is True
    assert am.activas() == []
    assert eventos[-1] == (EventoAlarma.RECONOCIDA, "COM-01")


def test_reconocer_activa_la_marca_y_al_resolver_sale():
    am, _ = _gestor()
    inst = am.activar(COM_01)
    am.reconocer("COM-01", "cristian")
    assert inst.reconocida_por == "cristian" and inst.reconocida_en is not None
    assert am.activas() == [inst]
    am.resolver(COM_01)
    assert am.activas() == []


def test_reconocer_inexistente_o_aviso_devuelve_false():
    am, _ = _gestor()
    assert am.reconocer("COM-01", "x") is False
    am.activar(PRE_06, temp=70.0, maximo=65.0)
    assert am.reconocer("PRE-06", "x") is False


def test_reactivar_resuelta_sin_reconocer():
    am, eventos = _gestor()
    inst = am.activar(COM_01)
    hora = inst.aparecida
    am.resolver(COM_01)
    otra = am.activar(COM_01)
    assert otra is inst and inst.estado is EstadoInstancia.ACTIVA
    assert inst.resuelta is None and inst.aparecida == hora
    assert eventos[-1] == (EventoAlarma.REACTIVADA, "COM-01")
    assert [e for e, _ in eventos].count(EventoAlarma.APARECIDA) == 1


def test_resolver_todas_por_reinicio_conserva_no_reconocidas():
    am, _ = _gestor()
    am.activar(PRE_06, temp=70.0, maximo=65.0)
    am.activar(COM_01)
    am.activar(SIS_01, estado="Falla")
    am.reconocer("SIS-01", "cristian")
    am.resolver_todas_por_reinicio()
    [inst] = am.activas()
    assert inst.clave == "COM-01" and inst.estado is EstadoInstancia.RESUELTA_SIN_RECONOCER


def test_activas_ordenadas_por_nivel_y_hora():
    am, _ = _gestor()
    am.activar(PRE_06, temp=70.0, maximo=65.0)
    am.activar(COM_01)
    am.activar(SIS_01, estado="Ciclo")
    assert [i.codigo for i in am.activas()] == ["SIS-01", "COM-01", "PRE-06"]


def test_informativo_no_entra_a_activas_y_va_a_eventos():
    am, eventos = _gestor(con_informativo=True)
    inst = am.activar("SIS-99", algo="algo")
    assert am.activas() == []
    assert am.eventos_recientes() == [inst] and inst.resuelta == inst.aparecida
    assert eventos == [(EventoAlarma.APARECIDA, "SIS-99")]


def test_eventos_recientes_limita_a_20():
    am, _ = _gestor(con_informativo=True)
    for i in range(25):
        am.activar("SIS-99", algo=str(i))
    recientes = am.eventos_recientes()
    assert len(recientes) == 20 and recientes[-1].descripcion == "Pasó 24."


def test_oyente_que_falla_no_rompe_activar(caplog):
    am, _ = _gestor()
    am.suscribir(lambda ev, inst: 1 / 0)
    am.activar(COM_01)
    assert len(am.activas()) == 1


def test_oyente_se_llama_fuera_del_candado():
    am, _ = _gestor()
    dentro = []
    am.suscribir(lambda ev, inst: dentro.append(am._lock.locked()))
    am.activar(COM_01)
    assert dentro == [False]


def test_has_consultas_con_instancias_nuevas():
    am, _ = _gestor()
    assert not am.has_active_alarms()
    am.activar(SIS_01, estado="Ciclo")
    assert am.has_emergency() and am.has_blocking_alarm() and am.has_active_alarms()


def test_concurrencia_reconocer_y_resolver():
    am, _ = _gestor()
    for _ in range(200):
        am.activar(COM_01)
        t1 = threading.Thread(target=am.resolver, args=(COM_01,))
        t2 = threading.Thread(target=am.reconocer, args=("COM-01", "x"))
        t1.start(); t2.start(); t1.join(); t2.join()
        restantes = am.activas()
        # Resuelta y reconocida, en cualquier orden: no puede quedar en la lista.
        assert restantes == [], restantes
```

- [ ] **Paso 2: correr la prueba y verificar que falla**

Correr: `python -m pytest -q -p no:cacheprovider tests/test_alarm_manager.py`
Esperado: ERROR de colección, `ModuleNotFoundError: ...alarms.instancia`.

- [ ] **Paso 3: implementar `instancia.py`**

```python
# src/autoclave/state_machine/alarms/instancia.py
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from autoclave.state_machine.alarms.catalogo import DefinicionAlarma, Nivel


class EstadoInstancia(Enum):
    ACTIVA = "ACTIVA"
    RESUELTA_SIN_RECONOCER = "RESUELTA_SIN_RECONOCER"


class EventoAlarma(Enum):
    APARECIDA = "APARECIDA"
    RESUELTA = "RESUELTA"
    RECONOCIDA = "RECONOCIDA"
    REACTIVADA = "REACTIVADA"


def clave_de(codigo: str, origen: str | None) -> str:
    return f"{codigo}|{origen}" if origen else codigo


@dataclass
class InstanciaAlarma:
    clave: str
    definicion: DefinicionAlarma
    origen: str | None
    valores: dict
    descripcion: str
    aparecida: datetime
    estado: EstadoInstancia = EstadoInstancia.ACTIVA
    resuelta: datetime | None = None
    reconocida_por: str | None = None
    reconocida_en: datetime | None = None
    ciclo_id: int | None = None
    id_historial: int | None = None

    @property
    def codigo(self) -> str:
        return self.definicion.codigo

    @property
    def titulo(self) -> str:
        return self.definicion.titulo

    @property
    def nivel(self) -> Nivel:
        return self.definicion.nivel
```

- [ ] **Paso 4: implementar `alarm_manager.py`**

Reemplazar el archivo completo por:

```python
import logging
import threading
from collections import deque
from datetime import datetime

from autoclave.state_machine.alarms.alarm_types import AlarmType
from autoclave.state_machine.alarms.catalogo import CATALOGO, Nivel
from autoclave.state_machine.alarms.instancia import (
    EstadoInstancia, EventoAlarma, InstanciaAlarma, clave_de,
)

logger = logging.getLogger(__name__)

DETALLE_NO_DISPONIBLE = "Detalle no disponible."
_MAX_EVENTOS_RECIENTES = 20
_LOG_POR_NIVEL = {
    Nivel.INFORMATIVO: logging.INFO,
    Nivel.AVISO: logging.WARNING,
    Nivel.ALARMA: logging.ERROR,
    Nivel.FALLO_CRITICO: logging.CRITICAL,
}


class AlarmManager:
    """Alarmas del equipo (spec 2026-10-06-sistema-alarmas-parte-a §5).

    API nueva: activar / resolver / reconocer. Las instancias viven aquí,
    protegidas por un candado: reconocer() llega por HTTP mientras el
    ControlLoop activa y resuelve. Los oyentes (historial) se notifican
    fuera del candado.

    report/clear/active_alarms son la API vieja; se eliminan al terminar
    la migración (plan 2026-10-07, tarea 10)."""

    def __init__(self, estado=None, catalogo=None, reloj=None):
        self.estado = estado
        # API vieja: lista compartida en estado.Alarmas_activas
        self.active_alarms = estado.Alarmas_activas if estado is not None else []

        self._catalogo = catalogo if catalogo is not None else CATALOGO
        self._reloj = reloj if reloj is not None else datetime.now
        self._lock = threading.Lock()
        self._instancias: dict[str, InstanciaAlarma] = {}
        self._eventos: deque[InstanciaAlarma] = deque(maxlen=_MAX_EVENTOS_RECIENTES)
        self._oyentes = []

    # ------------------------------------------------------------------
    # API nueva
    # ------------------------------------------------------------------

    def suscribir(self, oyente) -> None:
        self._oyentes.append(oyente)

    def activar(self, codigo: str, origen: str | None = None, **valores) -> InstanciaAlarma:
        definicion = self._catalogo[codigo]          # código desconocido → KeyError
        descripcion = self._renderizar(definicion, valores)
        ahora = self._reloj()
        clave = clave_de(codigo, origen)
        evento = None
        with self._lock:
            if definicion.nivel is Nivel.INFORMATIVO:
                inst = InstanciaAlarma(clave, definicion, origen, dict(valores),
                                       descripcion, ahora, resuelta=ahora)
                self._eventos.append(inst)
                evento = EventoAlarma.APARECIDA
            else:
                inst = self._instancias.get(clave)
                if inst is None:
                    inst = InstanciaAlarma(clave, definicion, origen, dict(valores),
                                           descripcion, ahora)
                    self._instancias[clave] = inst
                    evento = EventoAlarma.APARECIDA
                else:
                    inst.valores = dict(valores)
                    inst.descripcion = descripcion
                    if inst.estado is EstadoInstancia.RESUELTA_SIN_RECONOCER:
                        inst.estado = EstadoInstancia.ACTIVA
                        inst.resuelta = None
                        evento = EventoAlarma.REACTIVADA
        if evento is EventoAlarma.APARECIDA:
            logger.log(_LOG_POR_NIVEL[definicion.nivel], "Alarma %s: %s — %s",
                       clave, definicion.titulo, descripcion)
        self._notificar(evento, inst)
        return inst

    def resolver(self, codigo: str, origen: str | None = None) -> None:
        with self._lock:
            inst = self._resolver_sin_candado(clave_de(codigo, origen))
        if inst is not None:
            logger.info("Alarma resuelta: %s", inst.clave)
            self._notificar(EventoAlarma.RESUELTA, inst)

    def obtener(self, clave: str) -> InstanciaAlarma | None:
        with self._lock:
            return self._instancias.get(clave)

    def reconocer(self, clave: str, usuario: str) -> bool:
        with self._lock:
            inst = self._instancias.get(clave)
            if inst is None or not inst.nivel.requiere_reconocimiento:
                return False
            if inst.reconocida_por is not None:
                return True
            inst.reconocida_por = usuario
            inst.reconocida_en = self._reloj()
            if inst.estado is EstadoInstancia.RESUELTA_SIN_RECONOCER:
                del self._instancias[clave]
        logger.info("Alarma reconocida: %s por %s", clave, usuario)
        self._notificar(EventoAlarma.RECONOCIDA, inst)
        return True

    def resolver_todas_por_reinicio(self) -> None:
        with self._lock:
            resueltas = [self._resolver_sin_candado(c) for c in list(self._instancias)]
        for inst in resueltas:
            if inst is not None:
                self._notificar(EventoAlarma.RESUELTA, inst)

    def activas(self) -> list[InstanciaAlarma]:
        with self._lock:
            instancias = list(self._instancias.values())
        return sorted(instancias, key=lambda i: (-i.nivel.value, i.aparecida))

    def eventos_recientes(self) -> list[InstanciaAlarma]:
        with self._lock:
            return list(self._eventos)

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def _resolver_sin_candado(self, clave: str) -> InstanciaAlarma | None:
        inst = self._instancias.get(clave)
        if inst is None or inst.estado is not EstadoInstancia.ACTIVA:
            return None
        inst.resuelta = self._reloj()
        if inst.nivel.requiere_reconocimiento and inst.reconocida_por is None:
            inst.estado = EstadoInstancia.RESUELTA_SIN_RECONOCER
        else:
            del self._instancias[clave]
        return inst

    @staticmethod
    def _renderizar(definicion, valores) -> str:
        try:
            return definicion.renderizar(valores)
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            logger.error("Alarma %s: plantilla con valores incompletos (%r): %r",
                         definicion.codigo, exc, valores)
            return DETALLE_NO_DISPONIBLE

    def _notificar(self, evento, inst) -> None:
        if evento is None:
            return
        for oyente in list(self._oyentes):
            try:
                oyente(evento, inst)
            except Exception:
                logger.exception("Oyente de alarmas falló en %s de %s", evento, inst.clave)

    def _activas_nuevas(self, *niveles) -> bool:
        with self._lock:
            return any(i.estado is EstadoInstancia.ACTIVA and (not niveles or i.nivel in niveles)
                       for i in self._instancias.values())

    # ------------------------------------------------------------------
    # API vieja (se elimina en la tarea 10)
    # ------------------------------------------------------------------

    def report(self, alarm):
        if alarm is None:
            return
        if any(a.id == alarm.id for a in self.active_alarms):
            return
        self.active_alarms.append(alarm)
        logger.info(f"Alarma reportada: {alarm.id} - {alarm.description}")

    def clear(self, alarm_id: str):
        before = len(self.active_alarms)
        self.active_alarms[:] = [a for a in self.active_alarms if a.id != alarm_id]
        if len(self.active_alarms) < before:
            logger.info(f"Alarma despejada: {alarm_id}")

    def clear_recoverable(self):
        self.active_alarms[:] = [a for a in self.active_alarms if not a.is_auto_clearable()]

    def has_emergency(self) -> bool:
        return (any(a.type == AlarmType.EMERGENCIA for a in self.active_alarms)
                or self._activas_nuevas(Nivel.FALLO_CRITICO))

    def has_failure(self) -> bool:
        return (any(a.type == AlarmType.FALLA for a in self.active_alarms)
                or self._activas_nuevas(Nivel.ALARMA))

    def has_alert(self) -> bool:
        return (any(a.type == AlarmType.ALERTA for a in self.active_alarms)
                or self._activas_nuevas(Nivel.AVISO))

    def has_blocking_alarm(self) -> bool:
        with self._lock:
            nuevas = any(i.estado is EstadoInstancia.ACTIVA and i.definicion.bloquea_inicio
                         for i in self._instancias.values())
        return any(a.blocks_operation for a in self.active_alarms) or nuevas

    def has_active_alarms(self) -> bool:
        return bool(self.active_alarms) or self._activas_nuevas()
```

Nota: se eliminan los logs `critical/error/warning` por nivel de `report()`. Ninguna prueba los consulta, y la API nueva ya registra en el log según el nivel.

- [ ] **Paso 5: correr las pruebas y verificar que pasan**

Correr: `python -m pytest -q -p no:cacheprovider tests/test_alarm_manager.py tests/test_alarmas_catalogo.py`
Esperado: todo PASS.

Correr también la suite completa: `python -m pytest -q -p no:cacheprovider`
Esperado: 1794 + nuevas, sin fallos (la API vieja no cambió).

---

### Tarea 3: Historial en la base de datos

**Archivos:**
- Modificar: `src/autoclave/services/domain/logging/db_manager.py` (`_SCHEMA`, `_migrate`, `cerrar_ciclo`, más métodos nuevos al final de la sección de ciclos)
- Crear: `src/autoclave/services/domain/logging/historial_alarmas.py`
- Probar: `tests/test_historial_alarmas.py`

**Interfaces:**
- Consume: `AlarmManager.suscribir/activar`, `EventoAlarma`, `InstanciaAlarma`, `SIS_02` (tareas 1-2).
- Produce:
  - Métodos nuevos de `DbManager`:

    | Método | Devuelve |
    |---|---|
    | `insertar_alarma(codigo, nivel, titulo, origen, descripcion, valores_json, aparecida, resuelta, ciclo_id)` | `int` |
    | `marcar_alarma_resuelta(id_, resuelta, descripcion_final, valores_json)` | `None` |
    | `marcar_alarma_reconocida(id_, usuario, en)` | `None` |
    | `reabrir_alarma(id_)` | `None` |
    | `get_alarmas_historial(desde=None, hasta=None, nivel=None, limite=200)` | `list[dict]` |

    Las horas entran como `str` en ISO.
  - `cerrar_ciclo(ciclo_id, resultado, motivo_fallo=None, codigo_fallo=None)` agrega el parámetro `codigo_fallo`, opcional, así que las llamadas actuales siguen funcionando.
  - `HistorialAlarmas(db, alarm_manager, ciclo_actual=lambda: None)` se registra solo como oyente al construirse.

- [ ] **Paso 1: escribir la prueba que falla**

```python
# tests/test_historial_alarmas.py
import sqlite3
from types import SimpleNamespace

from autoclave.services.domain.logging.db_manager import DbManager
from autoclave.services.domain.logging.historial_alarmas import HistorialAlarmas
from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.alarms.catalogo import COM_01, PRE_06


def _db(tmp_path):
    return DbManager(db_path=tmp_path / "t.db")


def _gestor():
    return AlarmManager(estado=SimpleNamespace(Alarmas_activas=[]))


def test_aparicion_resolucion_y_reconocimiento_quedan_en_bd(tmp_path):
    db, am = _db(tmp_path), _gestor()
    HistorialAlarmas(db, am, ciclo_actual=lambda: None)
    am.activar(COM_01)
    am.resolver(COM_01)
    am.reconocer("COM-01", "cristian")
    [fila] = db.get_alarmas_historial()
    assert fila["codigo"] == "COM-01" and fila["nivel"] == "ALARMA"
    assert fila["titulo"] == "Sin comunicación con la tarjeta"
    assert fila["resuelta"] and fila["reconocida_por"] == "cristian"
    assert fila["descripcion_final"] == fila["descripcion_inicial"]


def test_valores_finales_y_reapertura(tmp_path):
    db, am = _db(tmp_path), _gestor()
    HistorialAlarmas(db, am)
    am.activar(PRE_06, temp=70.0, maximo=65.0)
    am.activar(PRE_06, temp=80.0, maximo=65.0)
    am.resolver(PRE_06)
    [fila] = db.get_alarmas_historial()
    assert "70.0" in fila["descripcion_inicial"] and "80.0" in fila["descripcion_final"]
    assert '"temp": 80.0' in fila["valores_json"]

    am.activar(COM_01)
    am.resolver(COM_01)
    am.activar(COM_01)            # reactivación: misma fila, resuelta vuelve a NULL
    filas = [f for f in db.get_alarmas_historial() if f["codigo"] == "COM-01"]
    assert len(filas) == 1 and filas[0]["resuelta"] is None


def test_ciclo_id_se_toma_al_aparecer(tmp_path):
    db, am = _db(tmp_path), _gestor()
    ciclo_id = db.crear_ciclo(**_args_ciclo())
    HistorialAlarmas(db, am, ciclo_actual=lambda: ciclo_id)
    inst = am.activar(COM_01)
    assert inst.ciclo_id == ciclo_id
    assert db.get_alarmas_historial()[0]["ciclo_id"] == ciclo_id


def test_filtros_y_limite(tmp_path):
    db, am = _db(tmp_path), _gestor()
    HistorialAlarmas(db, am)
    am.activar(PRE_06, temp=70.0, maximo=65.0)
    am.activar(COM_01)
    assert [f["codigo"] for f in db.get_alarmas_historial(nivel="ALARMA")] == ["COM-01"]
    assert len(db.get_alarmas_historial(limite=1)) == 1
    assert db.get_alarmas_historial(desde="2999-01-01T00:00:00") == []


def test_fallo_de_escritura_no_propaga_y_activa_sis02_una_vez(tmp_path):
    class _DbRota:
        def insertar_alarma(self, *a, **k):
            raise sqlite3.OperationalError("disk I/O error")

    am = _gestor()
    HistorialAlarmas(_DbRota(), am)
    am.activar(COM_01)                      # no lanza
    am.activar(PRE_06, temp=70.0, maximo=65.0)
    codigos = [i.codigo for i in am.activas()]
    assert codigos.count("SIS-02") == 1
    sis02 = next(i for i in am.activas() if i.codigo == "SIS-02")
    assert "disk I/O error" in sis02.descripcion


def test_bd_vieja_se_migra(tmp_path):
    ruta = tmp_path / "vieja.db"
    con = sqlite3.connect(ruta)
    con.execute("CREATE TABLE ciclos (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "numero_ciclo INTEGER)")
    con.commit()
    con.close()
    db = DbManager(db_path=ruta)
    columnas = {r[1] for r in db._conn.execute("PRAGMA table_info(ciclos)")}
    assert "codigo_fallo" in columnas
    assert db.get_alarmas_historial() == []


def _args_ciclo():
    # Ajustar a la firma real de DbManager.crear_ciclo (db_manager.py:178).
    import inspect
    firma = inspect.signature(DbManager.crear_ciclo)
    return {n: (1 if "numero" in n else "x") for n in firma.parameters if n != "self"}
```

> Nota para quien implementa: `_args_ciclo` arma argumentos de relleno a partir de la firma real de `crear_ciclo`. Si algún parámetro exige un tipo distinto de `int` o `str`, ajusta ese valor ahí.

- [ ] **Paso 2: correr la prueba y verificar que falla**

Correr: `python -m pytest -q -p no:cacheprovider tests/test_historial_alarmas.py`
Esperado: ERROR de colección, `ModuleNotFoundError: ...historial_alarmas`.

- [ ] **Paso 3: esquema y migración en `db_manager.py`**

Agregar al final de `_SCHEMA` (antes del cierre `"""`):

```sql
CREATE TABLE IF NOT EXISTS alarmas_historial (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo               TEXT NOT NULL,
    nivel                TEXT NOT NULL,
    titulo               TEXT NOT NULL,
    origen               TEXT DEFAULT '',
    descripcion_inicial  TEXT NOT NULL,
    descripcion_final    TEXT DEFAULT '',
    valores_json         TEXT DEFAULT '{}',
    aparecida            TEXT NOT NULL,
    resuelta             TEXT,
    reconocida_por       TEXT,
    reconocida_en        TEXT,
    ciclo_id             INTEGER REFERENCES ciclos(id)
);

CREATE INDEX IF NOT EXISTS idx_alarmas_aparecida ON alarmas_historial(aparecida);
```

En `_migrate()`, justo después del bloque de `motivo_fallo`:

```python
        try:
            self._conn.execute(
                "ALTER TABLE ciclos ADD COLUMN codigo_fallo TEXT DEFAULT ''"
            )
            self._conn.commit()
        except sqlite3.OperationalError:
            pass  # la columna ya existe
```

Reemplazar `cerrar_ciclo`:

```python
    def cerrar_ciclo(self, ciclo_id: int, resultado: str, motivo_fallo: str | None = None,
                     codigo_fallo: str | None = None):
        with self._lock:
            self._conn.execute(
                "UPDATE ciclos SET fecha_fin=?, resultado=?, motivo_fallo=?, codigo_fallo=? "
                "WHERE id=?",
                (datetime.now().isoformat(), resultado, motivo_fallo or "",
                 codigo_fallo or "", ciclo_id),
            )
            self._conn.commit()
```

(Antes de reemplazarlo, leer el `cerrar_ciclo` actual, `db_manager.py:216-224`, y conservar cualquier otra cosa que haga.)

Agregar después de `get_duraciones_referencia`:

```python
    # ------------------------------------------------------------------
    # Historial de alarmas
    # ------------------------------------------------------------------

    def insertar_alarma(self, codigo, nivel, titulo, origen, descripcion, valores_json,
                        aparecida, resuelta, ciclo_id) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO alarmas_historial (codigo, nivel, titulo, origen, "
                "descripcion_inicial, valores_json, aparecida, resuelta, ciclo_id) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (codigo, nivel, titulo, origen or "", descripcion, valores_json,
                 aparecida, resuelta, ciclo_id),
            )
            self._conn.commit()
            return cur.lastrowid

    def marcar_alarma_resuelta(self, id_, resuelta, descripcion_final, valores_json):
        with self._lock:
            self._conn.execute(
                "UPDATE alarmas_historial SET resuelta=?, descripcion_final=?, valores_json=? "
                "WHERE id=?",
                (resuelta, descripcion_final, valores_json, id_),
            )
            self._conn.commit()

    def marcar_alarma_reconocida(self, id_, usuario, en):
        with self._lock:
            self._conn.execute(
                "UPDATE alarmas_historial SET reconocida_por=?, reconocida_en=? WHERE id=?",
                (usuario, en, id_),
            )
            self._conn.commit()

    def reabrir_alarma(self, id_):
        with self._lock:
            self._conn.execute(
                "UPDATE alarmas_historial SET resuelta=NULL WHERE id=?", (id_,))
            self._conn.commit()

    def get_alarmas_historial(self, desde: str | None = None, hasta: str | None = None,
                              nivel: str | None = None, limite: int = 200) -> list[dict]:
        condiciones, args = [], []
        if desde:
            condiciones.append("aparecida >= ?"); args.append(desde)
        if hasta:
            condiciones.append("aparecida <= ?"); args.append(hasta)
        if nivel:
            condiciones.append("nivel = ?"); args.append(nivel)
        where = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
        with self._lock:
            filas = self._conn.execute(
                f"SELECT * FROM alarmas_historial {where} ORDER BY aparecida DESC, id DESC "
                "LIMIT ?", (*args, int(limite)),
            ).fetchall()
        return [dict(f) for f in filas]
```

- [ ] **Paso 4: implementar `historial_alarmas.py`**

```python
# services/domain/logging/historial_alarmas.py
#
# Oyente de AlarmManager que persiste aparición, resolución y reconocimiento
# en alarmas_historial (spec 2026-10-06-sistema-alarmas-parte-a §6). Una
# escritura fallida nunca se propaga al ControlLoop: queda en el log y activa
# SIS-02 una sola vez por arranque.

import json
import logging

from autoclave.state_machine.alarms.catalogo import SIS_02
from autoclave.state_machine.alarms.instancia import EventoAlarma

logger = logging.getLogger(__name__)


def _iso(dt):
    return dt.isoformat(timespec="seconds") if dt is not None else None


def _json(valores) -> str:
    return json.dumps(valores, ensure_ascii=False, default=str, sort_keys=True)


class HistorialAlarmas:
    def __init__(self, db, alarm_manager, ciclo_actual=lambda: None):
        self._db = db
        self._am = alarm_manager
        self._ciclo_actual = ciclo_actual
        self._sis02_activada = False
        alarm_manager.suscribir(self)

    def __call__(self, evento, inst):
        if inst.codigo == SIS_02:
            return
        try:
            self._escribir(evento, inst)
        except Exception as exc:
            logger.error("Historial de alarmas: no se pudo registrar %s de %s: %s",
                         evento.value, inst.clave, exc)
            if not self._sis02_activada:
                self._sis02_activada = True
                self._am.activar(SIS_02, error=str(exc))

    def _escribir(self, evento, inst):
        if evento is EventoAlarma.APARECIDA:
            inst.ciclo_id = self._ciclo_actual()
            inst.id_historial = self._db.insertar_alarma(
                inst.codigo, inst.nivel.name, inst.titulo, inst.origen, inst.descripcion,
                _json(inst.valores), _iso(inst.aparecida), _iso(inst.resuelta), inst.ciclo_id,
            )
            return
        if inst.id_historial is None:
            return
        if evento is EventoAlarma.RESUELTA:
            self._db.marcar_alarma_resuelta(
                inst.id_historial, _iso(inst.resuelta), inst.descripcion, _json(inst.valores))
        elif evento is EventoAlarma.RECONOCIDA:
            self._db.marcar_alarma_reconocida(
                inst.id_historial, inst.reconocida_por, _iso(inst.reconocida_en))
        elif evento is EventoAlarma.REACTIVADA:
            self._db.reabrir_alarma(inst.id_historial)
```

- [ ] **Paso 5: correr las pruebas y verificar que pasan**

Correr: `python -m pytest -q -p no:cacheprovider tests/test_historial_alarmas.py tests/test_generador_db.py tests/test_db_grafica_fases.py tests/test_cycle_logger_printer.py`
Esperado: todo PASS.

---

### Tarea 4: Instancia única de `AlarmManager` y registro del historial

**Archivos:**
- Modificar: `src/autoclave/state_machine/state_machine.py:15-28`, `:118-124`
- Modificar: `src/autoclave/services/domain/loop/control_loop.py:59-63`, `:306-310`
- Modificar: `src/autoclave/backend/context.py` (después de crear `self.cycle_logger`)
- Probar: `tests/test_alarm_manager_unico.py`

**Interfaces:**
- Consume: `AlarmManager`, `resolver_todas_por_reinicio()` (tarea 2); `HistorialAlarmas` (tarea 3); `CycleLogger.ciclo_id` (propiedad ya existente, `cycle_logger.py:170`).
- Produce: `StateMachine(io, estado, set_do, cycle, config, cap=None, door_service=None, alarm_manager=None)`.

- [ ] **Paso 1: escribir la prueba que falla**

```python
# tests/test_alarm_manager_unico.py
from unittest.mock import MagicMock

from autoclave.state_machine.machine.enum_global import GlobalState
from tests.test_control_loop_set_active_cycle import _FakeEstado


def _loop():
    from autoclave.services.domain.loop.control_loop import ControlLoop
    estado = _FakeEstado()
    cm = MagicMock()
    am = MagicMock(name="alarm_manager")
    loop = ControlLoop(
        units=MagicMock(), door_service=MagicMock(), doors=[], estado=estado,
        link=MagicMock(), set_do=MagicMock(), alarm_manager=am,
        cycle_manager=cm, config_manager=MagicMock(), cap=None,
    )
    return loop, am, estado


def test_state_machine_usa_el_alarm_manager_del_loop():
    loop, am, _ = _loop()
    sm = loop.state_machine
    assert sm.alarm_manager is am
    assert sm.preparacion.alarm_manager is am and sm.ciclo.alarm_manager is am


def test_cambiar_de_ciclo_conserva_el_mismo_alarm_manager():
    loop, am, _ = _loop()
    ok, _ = loop.set_active_cycle(MagicMock())
    assert ok and loop.state_machine.alarm_manager is am


def test_salida_de_falla_usa_resolver_todas_por_reinicio():
    loop, am, estado = _loop()
    sm = loop.state_machine
    estado.estado_maquina = {}          # StateMachine.update() lo lee para el log
    estado.set_machine_state(GlobalState.FALLA)
    sm.prev_state = GlobalState.FALLA
    sm.falla = MagicMock()
    sm.falla.run.return_value = True
    estado.fase_ciclo = "FALLO_SECADO"
    sm.update()
    am.resolver_todas_por_reinicio.assert_called_once()
```

> Antes de correrla, revisar en `tests/test_control_loop_set_active_cycle.py` el nombre real del método para cambiar de ciclo (`set_active_cycle` en `control_loop.py:~296`) y cómo `StateMachine.update()` decide el estado actual (`state_machine.py:~60-125`). Si `update()` necesita más atributos en `_FakeEstado`, agregarlos en esta prueba con `estado.<attr> = ...`, no en la otra.

- [ ] **Paso 2: correr la prueba y verificar que falla**

Correr: `python -m pytest -q -p no:cacheprovider tests/test_alarm_manager_unico.py`
Esperado: FAIL en `sm.alarm_manager is am`.

- [ ] **Paso 3: implementar**

En `state_machine.py`, cambiar la firma y la creación:

```python
    def __init__(self, io, estado, set_do, cycle, config, cap=None, door_service=None,
                 alarm_manager=None):
        ...
        # Una sola instancia en todo el backend (spec §5.3): la inyecta el
        # ControlLoop. El AlarmManager propio queda solo para usos aislados.
        self.alarm_manager = alarm_manager if alarm_manager is not None else AlarmManager(estado)
```

En la rama `FALLA`, reemplazar `self.estado.Alarmas_activas.clear()` por:

```python
                self.estado.Alarmas_activas.clear()          # API vieja (tarea 10 lo quita)
                self.alarm_manager.resolver_todas_por_reinicio()
```

En `control_loop.py`, agregar `alarm_manager=self.alarm_manager,` a **las dos** construcciones de `StateMachine(...)` (`:59` y `:306`).

En `backend/context.py`, agregar el import `from autoclave.services.domain.logging.historial_alarmas import HistorialAlarmas` y, justo después de crear `self.cycle_logger = CycleLogger(...)`:

```python
        # Historial persistente de alarmas (spec 2026-10-06 §6). El ciclo en
        # curso se lee al aparecer cada alarma.
        self.historial_alarmas = HistorialAlarmas(
            self.db, self.alarm_manager,
            ciclo_actual=lambda: self.cycle_logger.ciclo_id,
        )
```

- [ ] **Paso 4: correr las pruebas y verificar que pasan**

Correr: `python -m pytest -q -p no:cacheprovider tests/test_alarm_manager_unico.py tests/test_control_loop_set_active_cycle.py tests/test_control_loop_test_mode.py tests/test_control_loop_resilience.py`
Esperado: todo PASS. Algunas pruebas de `set_active_cycle` verifican los argumentos con que se construye `StateMachine` (`mock_sm_class.assert_called_once_with(...)`). Si alguna falla solo por el nuevo `alarm_manager=...`, agregar ese argumento a lo esperado.

---

### Tarea 5: `/status` con el contrato nuevo y endpoints de alarmas

**Archivos:**
- Modificar: `src/autoclave/backend/server.py` (bloque `# ALARMAS` de `get_status`, `:164-174`, y el `return` final; endpoints nuevos después de `/cycle/acknowledge`)
- Modificar: `tests/test_status_endpoint_alarms.py`
- Crear: `tests/test_alarms_endpoints.py`

**Interfaces:**
- Consume: `context.alarm_manager.activas/eventos_recientes/obtener/reconocer`, `context.db.get_alarmas_historial`, `Nivel`.
- Produce: `/status` → `alarms[]` con los campos nuevos y los de compatibilidad (spec §7.1), más `eventos_recientes[]`; `POST /alarms/{clave}/acknowledge`; `GET /alarms/history`.

- [ ] **Paso 1: escribir las pruebas que fallan**

Agregar a `tests/test_status_endpoint_alarms.py` (las pruebas existentes siguen igual: cubren la API vieja hasta la tarea 10):

```python
def test_status_publica_instancias_nuevas_con_compatibilidad(status_client):
    from datetime import datetime
    from types import SimpleNamespace
    from autoclave.state_machine.alarms.alarm_manager import AlarmManager
    from autoclave.state_machine.alarms.catalogo import PUE_01

    client, mock_ctx = status_client
    _stub_estado_collections(mock_ctx)
    mock_ctx.estado.Alarmas_activas = []
    am = AlarmManager(estado=SimpleNamespace(Alarmas_activas=[]),
                      reloj=lambda: datetime(2026, 10, 7, 9, 30, 0))
    am.activar(PUE_01, origen="Puerta 1", puerta="Puerta 1")
    mock_ctx.alarm_manager = am

    cuerpo = client.get("/status").json()
    assert cuerpo["alarms"] == [{
        "clave": "PUE-01|Puerta 1", "codigo": "PUE-01", "nivel": "AVISO",
        "titulo": "Puerta abierta",
        "descripcion": "Puerta 1 está abierta. El ciclo no puede iniciar.",
        "accion": "Cierre la puerta.", "origen": "Puerta 1",
        "aparecida": "2026-10-07T09:30:00", "estado": "ACTIVA",
        "requiere_reconocimiento": False, "reconocida_por": None,
        "id": "PUE-01|Puerta 1", "level": "ALERTA",
        "description": "Puerta 1 está abierta. El ciclo no puede iniciar.",
        "source_state": "Puerta 1",
    }]
    assert cuerpo["eventos_recientes"] == []
```

Las pruebas existentes de este archivo usan un `mock_ctx` sin `alarm_manager` real (es un `MagicMock`). Agregarles `mock_ctx.alarm_manager.activas.return_value = []` y `mock_ctx.alarm_manager.eventos_recientes.return_value = []` después de `_stub_estado_collections(mock_ctx)`.

```python
# tests/test_alarms_endpoints.py
from types import SimpleNamespace
from urllib.parse import quote

from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.alarms.catalogo import COM_01, PRE_06, PUE_02
from tests.test_status_endpoint_alarms import status_client  # noqa: F401  (fixture)


def _con_gestor(mock_ctx):
    am = AlarmManager(estado=SimpleNamespace(Alarmas_activas=[]))
    mock_ctx.alarm_manager = am
    return am


def test_reconocer_clave_con_barra_y_espacios(status_client):
    client, mock_ctx = status_client
    am = _con_gestor(mock_ctx)
    am.activar(PUE_02, origen="Puerta 1", puerta="Puerta 1", fase="Secado")
    resp = client.post(f"/alarms/{quote('PUE-02|Puerta 1', safe='')}/acknowledge",
                       json={"usuario": "cristian"})
    assert resp.status_code == 200 and resp.json() == {"ok": True}
    assert am.obtener("PUE-02|Puerta 1").reconocida_por == "cristian"


def test_reconocer_inexistente_404(status_client):
    client, mock_ctx = status_client
    _con_gestor(mock_ctx)
    assert client.post("/alarms/COM-01/acknowledge", json={"usuario": "x"}).status_code == 404


def test_reconocer_aviso_422(status_client):
    client, mock_ctx = status_client
    _con_gestor(mock_ctx).activar(PRE_06, temp=70.0, maximo=65.0)
    assert client.post("/alarms/PRE-06/acknowledge", json={"usuario": "x"}).status_code == 422


def test_reconocer_sin_usuario_422(status_client):
    client, mock_ctx = status_client
    _con_gestor(mock_ctx).activar(COM_01)
    assert client.post("/alarms/COM-01/acknowledge", json={}).status_code == 422


def test_historial_pasa_filtros_y_recorta_limite(status_client):
    client, mock_ctx = status_client
    mock_ctx.db.get_alarmas_historial.return_value = [{"codigo": "COM-01"}]
    resp = client.get("/alarms/history", params={
        "desde": "2026-10-01T00:00:00", "nivel": "ALARMA", "limite": 5000})
    assert resp.status_code == 200 and resp.json() == {"alarmas": [{"codigo": "COM-01"}]}
    mock_ctx.db.get_alarmas_historial.assert_called_once_with(
        "2026-10-01T00:00:00", None, "ALARMA", 1000)


def test_historial_rechaza_nivel_o_fecha_invalidos(status_client):
    client, _ = status_client
    assert client.get("/alarms/history", params={"nivel": "GRAVE"}).status_code == 422
    assert client.get("/alarms/history", params={"desde": "ayer"}).status_code == 422
```

- [ ] **Paso 2: correr las pruebas y verificar que fallan**

Correr: `python -m pytest -q -p no:cacheprovider tests/test_status_endpoint_alarms.py tests/test_alarms_endpoints.py`
Esperado: FAIL (no existen los campos nuevos y los endpoints dan 404/405).

- [ ] **Paso 3: implementar en `server.py`**

Agregar el import junto a los demás: `from autoclave.state_machine.alarms.catalogo import Nivel`. Agregar estas funciones antes de `get_status`:

```python
def _hora_iso(dt) -> str | None:
    return dt.isoformat(timespec="seconds") if dt is not None else None


def _alarma_dto(inst) -> dict:
    """Instancia de alarma → JSON de /status (spec 2026-10-06 §7.1). Los
    campos id/level/description/source_state mantienen compatible a la UI
    actual hasta la Parte C."""
    origen = inst.origen or ""
    return {
        "clave": inst.clave,
        "codigo": inst.codigo,
        "nivel": inst.nivel.name,
        "titulo": inst.titulo,
        "descripcion": inst.descripcion,
        "accion": inst.definicion.accion,
        "origen": origen,
        "aparecida": _hora_iso(inst.aparecida),
        "estado": inst.estado.value,
        "requiere_reconocimiento": inst.nivel.requiere_reconocimiento,
        "reconocida_por": inst.reconocida_por,
        "id": inst.clave,
        "level": inst.nivel.nombre_compat,
        "description": inst.descripcion,
        "source_state": origen,
    }


def _evento_dto(inst) -> dict:
    return {
        "codigo": inst.codigo,
        "titulo": inst.titulo,
        "descripcion": inst.descripcion,
        "origen": inst.origen or "",
        "hora": _hora_iso(inst.aparecida),
    }
```

En `get_status`, después de la lista `alarms` vieja:

```python
    alarms += [_alarma_dto(inst) for inst in context.alarm_manager.activas()]
    eventos_recientes = [_evento_dto(inst) for inst in context.alarm_manager.eventos_recientes()]
```

En el `return`, después de `"alarms": alarms,`, agregar `"eventos_recientes": eventos_recientes,`.

Después de `acknowledge_cycle`:

```python
@app.post("/alarms/{clave}/acknowledge")
def acknowledge_alarm(clave: str, body: dict = Body(default={})):
    """El operador reconoce una alarma ALARMA/FALLO_CRITICO (spec §7.2)."""
    usuario = str(body.get("usuario") or "").strip()
    if not usuario:
        raise HTTPException(status_code=422, detail="Falta el usuario que reconoce")
    inst = context.alarm_manager.obtener(clave)
    if inst is None:
        raise HTTPException(status_code=404, detail="La alarma no está activa")
    if not inst.nivel.requiere_reconocimiento:
        raise HTTPException(status_code=422, detail="Esta alarma no requiere reconocimiento")
    context.alarm_manager.reconocer(clave, usuario)
    return {"ok": True}


def _fecha_iso_o_422(valor: str | None, campo: str) -> str | None:
    if valor is None:
        return None
    try:
        datetime.fromisoformat(valor)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"{campo} no es una fecha ISO válida")
    return valor


@app.get("/alarms/history")
def alarm_history(desde: str | None = None, hasta: str | None = None,
                  nivel: str | None = None, limite: int = 200):
    if nivel is not None and nivel not in Nivel.__members__:
        raise HTTPException(status_code=422, detail="Nivel desconocido")
    filas = context.db.get_alarmas_historial(
        _fecha_iso_o_422(desde, "desde"), _fecha_iso_o_422(hasta, "hasta"),
        nivel, max(1, min(int(limite), 1000)),
    )
    return {"alarmas": filas}
```

Verificar que `server.py` ya importa `datetime` (`from datetime import datetime`). Si no, agregarlo.

- [ ] **Paso 4: correr las pruebas y verificar que pasan**

Correr: `python -m pytest -q -p no:cacheprovider tests/test_status_endpoint_alarms.py tests/test_alarms_endpoints.py tests/test_io_test_mode_endpoints.py tests/test_ui_bridge.py`
Esperado: todo PASS.

---

### Tarea 6: Migrar PREPARACION y PREPARADO

**Archivos:**
- Crear: `tests/alarmas_helpers.py`
- Modificar: `src/autoclave/state_machine/states/preparacion.py`, `src/autoclave/state_machine/states/preparado.py`
- Modificar las pruebas: `tests/test_preparacion_alarm_wording.py` (se reescribe), `test_preparacion_{chaqueta,drenaje,presion_camara,suministro,temperatura_drenaje,ejecutor_paralelo}.py`, `test_preparado_{chaqueta,drenaje,presion_camara,suministro}.py`

**Interfaces:**
- Consume: `AlarmManager.activar/resolver` y las constantes y `nombre_legible` del catálogo.
- Produce: `tests/alarmas_helpers.py` con `activaciones(mock)`, `codigos_activados(mock)`, `codigos_resueltos(mock)` y `ultima_activacion(mock)`. Las usan las tareas 7 y 8.

**Correspondencia de códigos en estos módulos:**

| Id viejo | Llamada nueva |
|---|---|
| `PARO_EMERGENCIA` | `activar(SIS_01, estado="Preparación")` / `"Preparado"`; `resolver(SIS_01)` |
| `ERROR_AI_<SENSOR>` | `activar(SEN_01, origen=nombre_legible(sensor), sensor=nombre_legible(sensor), valor=valor)`; `resolver(SEN_01, origen=nombre_legible(sensor))` |
| `SUMINISTRO_AGUA_BOMBA` / `_AGUA_GENERADOR` / `_AIRE_COMPRIMIDO` | `SUM_03` / `SUM_04` / `SUM_05`, sin valores |
| `SUMINISTRO_ELECTRICO` (preparado) | `SUM_02` |
| `SUMINISTRO_VAPOR` | `activar(SUM_06, estado="Preparación")` / `"Preparado"`; `resolver(SUM_06)` |
| `CHAQUETA_FRIA` | `PRE_01` con `pres, minimo=obj-rango, objetivo=obj, rango` |
| `CHAQUETA_SOBRECALENTADA` | `PRE_02` con `pres, maximo=obj+rango, objetivo=obj, rango` |
| `PRESION_CAMARA_BAJA` / `_ALTA` | `PRE_03` con `pres, minimo` / `PRE_04` con `pres, maximo` |
| `AGUA_RESIDUAL_CAMARA` | `PRE_05` |
| `TEMP_DRENAJE_ALTA` | `PRE_06` con `temp, maximo=temp_obj+rango` |
| `PUERTA_1_ABIERTA` / `PUERTA_2_ABIERTA` | `activar(PUE_01, origen="Puerta N", puerta="Puerta N")`; `resolver(PUE_01, origen="Puerta N")` |

- [ ] **Paso 1: crear el helper de pruebas**

```python
# tests/alarmas_helpers.py
"""Lectura de llamadas activar/resolver sobre un AlarmManager MagicMock.
Cada activación se renderiza contra el catálogo real: si un módulo no pasa
los valores que pide la plantilla, la prueba falla aquí (spec §4, prueba de
plantillas), no en el equipo."""

from autoclave.state_machine.alarms.catalogo import CATALOGO


def activaciones(mock_manager) -> list[tuple[str, str | None, dict]]:
    resultado = []
    for llamada in mock_manager.activar.call_args_list:
        codigo = llamada.args[0]
        origen = llamada.args[1] if len(llamada.args) > 1 else llamada.kwargs.get("origen")
        valores = {k: v for k, v in llamada.kwargs.items() if k != "origen"}
        CATALOGO[codigo].renderizar(valores)
        resultado.append((codigo, origen, valores))
    return resultado


def codigos_activados(mock_manager) -> list[str]:
    return [codigo for codigo, _, _ in activaciones(mock_manager)]


def codigos_resueltos(mock_manager) -> list[str]:
    return [llamada.args[0] for llamada in mock_manager.resolver.call_args_list]


def ultima_activacion(mock_manager) -> tuple[str, str | None, dict]:
    return activaciones(mock_manager)[-1]
```

- [ ] **Paso 2: reescribir `tests/test_preparacion_alarm_wording.py` (prueba que falla)**

```python
from unittest.mock import MagicMock

from autoclave.state_machine.alarms.catalogo import (
    PRE_01, PRE_06, SEN_01, SIS_01, SUM_03,
)
from autoclave.state_machine.states.preparacion import preparacion_state
from tests.alarmas_helpers import activaciones, codigos_activados, codigos_resueltos


def _make_state(sensores_pres=None, sensores_temp=None, di=None):
    estado = MagicMock()
    estado.sensores_pres = sensores_pres or {
        "pres_camara": 101.3, "pres_chaqueta": 250.0,
        "pres_empaque_1": 300.0, "pres_empaque_2": 300.0}
    estado.sensores_temp = sensores_temp or {
        "temp_camara": 25.0, "temp_2_camara": 25.0, "temp_ref": 25.0,
        "temp_chaqueta": 25.0, "temp_drenaje_cam": 25.0, "temp_drenaje": 72.0}
    estado.sensores_di = di or {
        "paro_emergencia": 0, "vapor_suministro": 1, "agua_bomba": 1,
        "agua_generador": 1, "aire_comprimido": 1, "agua_camara": 0}
    cycle = MagicMock()
    cycle.get_param.side_effect = lambda s, n, **k: {"presion_chaqueta": 320,
                                                     "rango_presion_chaqueta": 50}[n]
    config = MagicMock()
    config.get.side_effect = lambda k: {
        "presion_admosferica": 101.3, "rango_presion_atm": 20.0,
        "temp_segura_drenaje": 60.0, "rango_temp_drenaje": 5.0}.get(k)
    return preparacion_state(MagicMock(), estado, MagicMock(), cycle, config)


def test_chaqueta_baja_activa_pre01_con_valores():
    s = _make_state()
    s.suministrar_vapor_chaqueta()
    [(codigo, origen, valores)] = [a for a in activaciones(s.alarm_manager) if a[0] == PRE_01]
    assert origen is None
    assert valores == {"pres": 250.0, "minimo": 270, "objetivo": 320, "rango": 50}


def test_drenaje_alto_activa_pre06_con_maximo_de_banda():
    s = _make_state()
    s.verificar_temperatura_drenaje()
    [(_, _, valores)] = [a for a in activaciones(s.alarm_manager) if a[0] == PRE_06]
    assert valores == {"temp": 72.0, "maximo": 65.0}


def test_sensor_en_cero_activa_sen01_con_nombre_legible():
    s = _make_state(sensores_pres={"pres_camara": 0, "pres_chaqueta": 300.0,
                                   "pres_empaque_1": 300.0, "pres_empaque_2": 300.0})
    s.verificar_sensores()
    sen = [a for a in activaciones(s.alarm_manager) if a[0] == SEN_01]
    assert sen == [(SEN_01, "Presión de cámara", {"sensor": "Presión de cámara", "valor": 0})]


def test_suministro_agua_bomba_activa_sum03():
    s = _make_state(di={"paro_emergencia": 0, "vapor_suministro": 1, "agua_bomba": 0,
                        "agua_generador": 1, "aire_comprimido": 1, "agua_camara": 0})
    s.verificar_suministros()
    assert SUM_03 in codigos_activados(s.alarm_manager)


def test_paro_activa_y_resuelve_sis01():
    s = _make_state(di={"paro_emergencia": 1})
    s.run()
    assert ("SIS-01", None, {"estado": "Preparación"}) in activaciones(s.alarm_manager)
    s.estado.sensores_di = {"paro_emergencia": 0, "vapor_suministro": 1, "agua_bomba": 1,
                            "agua_generador": 1, "aire_comprimido": 1, "agua_camara": 0}
    s.run()
    assert SIS_01 in codigos_resueltos(s.alarm_manager)
```

Correr: `python -m pytest -q -p no:cacheprovider tests/test_preparacion_alarm_wording.py`
Esperado: FAIL (`preparacion` todavía llama a `report`).

- [ ] **Paso 3: migrar `preparacion.py`**

1. Reemplazar los imports de `Alarm`/`AlarmType` y el bloque `_NIVEL_TXT` por:

```python
from autoclave.state_machine.alarms.catalogo import (
    PRE_01, PRE_02, PRE_03, PRE_04, PRE_05, PRE_06, SEN_01, SIS_01,
    SUM_03, SUM_04, SUM_05, SUM_06, nombre_legible,
)

_ESTADO = "Preparación"
_SUMINISTROS = {"agua_bomba": SUM_03, "agua_generador": SUM_04, "aire_comprimido": SUM_05}
```

2. Borrar el método `alarm(...)`.
3. En `run()`: `self.alarm("PARO_EMERGENCIA", AlarmType.EMERGENCIA)` → `self.alarm_manager.activar(SIS_01, estado=_ESTADO)`; `self.alarm_manager.clear("PARO_EMERGENCIA")` → `self.alarm_manager.resolver(SIS_01)`.
4. En `verificar_sensores()`, los dos bucles quedan así (mismo patrón para temperatura con `temp_value`):

```python
            for sensor in sensores_presion:
                pres_value = self.estado.sensores_pres[sensor]
                legible = nombre_legible(sensor)
                if pres_value == 0:
                    self.alarm_manager.activar(SEN_01, origen=legible, sensor=legible,
                                               valor=pres_value)
                    ok = False
                else:
                    self.alarm_manager.resolver(SEN_01, origen=legible)
```

5. En `verificar_suministros()`:

```python
        for suministro, codigo in _SUMINISTROS.items():
            if not self.estado.sensores_di[suministro]:
                self.alarm_manager.activar(codigo)
                ok = False
            else:
                self.alarm_manager.resolver(codigo)
```

6. En `suministrar_vapor_chaqueta()`:

```python
            if not self.estado.sensores_di["vapor_suministro"]:
                self.set_do.vapor_chaqueta_off()
                self._confirmador_chaqueta.reset()
                self.alarm_manager.activar(SUM_06, estado=_ESTADO)
                self.alarm_manager.resolver(PRE_01)
                self.alarm_manager.resolver(PRE_02)
                return True
            else:
                self.alarm_manager.resolver(SUM_06)
            ...
            if r.fuera_por_debajo:
                self.alarm_manager.activar(PRE_01, pres=presion, minimo=pres_obj - rango,
                                           objetivo=pres_obj, rango=rango)
            else:
                self.alarm_manager.resolver(PRE_01)

            if r.fuera_por_encima:
                self.alarm_manager.activar(PRE_02, pres=presion, maximo=pres_obj + rango,
                                           objetivo=pres_obj, rango=rango)
            else:
                self.alarm_manager.resolver(PRE_02)
```

7. En `igualar_presion_camara()`: los `clear` de `PRESION_CAMARA_*` pasan a `resolver(PRE_03)` y `resolver(PRE_04)`; el lado bajo usa `self.alarm_manager.activar(PRE_03, pres=presion_camara, minimo=pres_cam_min)` y el alto `self.alarm_manager.activar(PRE_04, pres=presion_camara, maximo=pres_cam_max)`.
8. En `drenar_camara()`: `clear("AGUA_RESIDUAL_CAMARA")` → `resolver(PRE_05)`; la activación → `self.alarm_manager.activar(PRE_05)`.
9. En `verificar_temperatura_drenaje()`: `self.alarm_manager.activar(PRE_06, temp=temp_drenaje, maximo=temp_obj + rango)` y `resolver(PRE_06)`.

- [ ] **Paso 4: migrar `preparado.py`**

1. Imports: reemplazar `from autoclave.state_machine.alarms.alarm import Alarm, AlarmType` por:

```python
from autoclave.state_machine.alarms.catalogo import (
    PRE_01, PRE_02, PRE_03, PRE_04, PRE_06, PUE_01, SEN_01, SIS_01,
    SUM_02, SUM_03, SUM_04, SUM_05, SUM_06, nombre_legible,
)

_ESTADO = "Preparado"
_SUMINISTROS = {"agua_bomba": SUM_03, "agua_generador": SUM_04, "aire_comprimido": SUM_05}
```

2. Borrar el método `alarm(...)` (`:31-40`).
3. `generar_alarma_temporizada` cambia de firma, conservando el mismo temporizador:

```python
    def generar_alarma_temporizada(self, codigo, **valores):
        if self.timer_estabilidad is None:
            self.timer_estabilidad = time.monotonic() + self.tiempo_estable

        if time.monotonic() >= self.timer_estabilidad:
            self.alarm_manager.activar(codigo, **valores)
```

4. En `run()`: paro igual que en preparación, con `estado=_ESTADO`.
5. En `mantener_chaqueta()`: misma lógica que el paso 3.6. La activación de PRE-01/PRE-02 pasa por `self.generar_alarma_temporizada(PRE_01, pres=press_chaqueta, minimo=press_obj - rango, objetivo=press_obj, rango=rango)` (y lo análogo para PRE-02 con `maximo=press_obj + rango`). SUM-06 se activa con `estado=_ESTADO`.
6. En `mantener_presion_camara()`: `generar_alarma_temporizada(PRE_03, pres=presion_camara, minimo=min_p)` / `(PRE_04, pres=presion_camara, maximo=max_p)`, y `resolver(PRE_03/PRE_04)`.
7. En `mantener_drenaje()`: `generar_alarma_temporizada(PRE_06, temp=temp, maximo=temp_obj + rango)` y `resolver(PRE_06)`.
8. En `puertas_cerradas()`:

```python
        for num, cerrada in ((1, p1), (2, p2)):
            puerta = f"Puerta {num}"
            if not cerrada:
                self.alarm_manager.activar(PUE_01, origen=puerta, puerta=puerta)
            else:
                self.alarm_manager.resolver(PUE_01, origen=puerta)
```

9. `verificar_sensores()` / `verificar_suministros()`: igual que en preparación, recorriendo `self.estado.sensores_pres.items()` / `sensores_temp.items()` como hoy. El suministro eléctrico pasa a `activar(SUM_02)` / `resolver(SUM_02)`.

- [ ] **Paso 5: actualizar las demás pruebas de preparación y preparado**

Sustituciones mecánicas en cada archivo listado:

| Hoy | Nuevo |
|---|---|
| `[call.args[0].id for call in alarm_mgr.report.call_args_list]` | `codigos_activados(alarm_mgr)` (importar de `tests.alarmas_helpers`) |
| `alarm_mgr.report.assert_not_called()` | `alarm_mgr.activar.assert_not_called()` |
| `alarm_mgr.report.reset_mock()` | `alarm_mgr.activar.reset_mock()` |
| `alarm_mgr.clear` | `alarm_mgr.resolver` (y los ids por código con `codigos_resueltos`) |
| ids viejos en los `assert` | constantes de la tabla de correspondencia (por ejemplo `"CHAQUETA_FRIA"` → `PRE_01`) |
| `alarma = alarm_mgr.report.call_args.args[0]; assert alarma.id == "SUMINISTRO_VAPOR"; assert alarma.blocks_operation is False` | `codigo, _, valores = ultima_activacion(alarm_mgr); assert codigo == SUM_06; assert CATALOGO[SUM_06].bloquea_inicio is False` |
| `from ...alarm_types import AlarmType` | quitar si queda sin uso |

- [ ] **Paso 6: correr las pruebas**

Correr: `python -m pytest -q -p no:cacheprovider tests/test_preparacion_alarm_wording.py tests/test_preparacion_chaqueta.py tests/test_preparacion_drenaje.py tests/test_preparacion_presion_camara.py tests/test_preparacion_suministro.py tests/test_preparacion_temperatura_drenaje.py tests/test_preparacion_ejecutor_paralelo.py tests/test_preparado_chaqueta.py tests/test_preparado_drenaje.py tests/test_preparado_presion_camara.py tests/test_preparado_suministro.py tests/test_control_banda.py`
Esperado: todo PASS. Después: `grep -n "AlarmType\|\.report(\|\.clear(" src/autoclave/state_machine/states/preparacion.py src/autoclave/state_machine/states/preparado.py` debe dar vacío.

---

### Tarea 7: Migrar FALLA, HIBERNACION, ControlLoop (COM-01) y puertas (PUE-04/05)

**Archivos:**
- Modificar: `src/autoclave/state_machine/states/falla.py`, `src/autoclave/state_machine/states/hibernacion.py`
- Modificar: `src/autoclave/services/domain/loop/control_loop.py:96-130`
- Modificar: `src/autoclave/devices/puertas/advanced_door.py` (`_from_abriendo`, `_from_cerrando`, helpers `:577-586`)
- Modificar las pruebas: `tests/test_advanced_door_safe_mode.py`, `tests/test_control_loop_connectivity_ticket.py` (si verifica `report`), y crear `tests/test_alarmas_falla_hibernacion.py`

**Interfaces:**
- Consume: `activar/resolver`, `SIS_01`, `COM_01`, `PUE_04`, `PUE_05`, `tests/alarmas_helpers.py`.

- [ ] **Paso 1: escribir las pruebas que fallan**

```python
# tests/test_alarmas_falla_hibernacion.py
from unittest.mock import MagicMock

from autoclave.state_machine.states.falla import FallaState
from autoclave.state_machine.states.hibernacion import Hibernacion
from tests.alarmas_helpers import activaciones


def _estado(paro):
    estado = MagicMock()
    estado.get_flag.side_effect = lambda f: paro if f == "PARO_EMERGENCIA" else False
    return estado


def test_falla_con_paro_activa_sis01():
    am = MagicMock()
    FallaState(_estado(True), MagicMock(), am).run()
    assert activaciones(am) == [("SIS-01", None, {"estado": "Falla"})]


def test_hibernacion_con_paro_activa_sis01():
    am = MagicMock()
    Hibernacion(_estado(True), MagicMock(), am).run()
    assert activaciones(am) == [("SIS-01", None, {"estado": "Hibernación"})]
```

En `tests/test_advanced_door_safe_mode.py`, reemplazar las verificaciones de las líneas 51, 63-67, 96 y 109-113:

```python
from autoclave.state_machine.alarms.catalogo import CATALOGO, PUE_04, PUE_05
from tests.alarmas_helpers import activaciones, codigos_resueltos

# :51 y :96
    alarm_mgr.activar.assert_not_called()

# :63-67
    [(codigo, origen, valores)] = activaciones(alarm_mgr)
    assert (codigo, origen, valores) == (PUE_04, "Puerta 1", {"puerta": "Puerta 1"})
    assert CATALOGO[PUE_04].bloquea_inicio is False

# :109-113 (mismo patrón con PUE_05)
```

Si en ese archivo hay pruebas de despeje con `alarm_mgr.clear.assert_called_with("ABRIENDO_MODO_SEGURO_Puerta 1")`, pasan a `assert PUE_04 in codigos_resueltos(alarm_mgr)`.

Correr: `python -m pytest -q -p no:cacheprovider tests/test_alarmas_falla_hibernacion.py tests/test_advanced_door_safe_mode.py`
Esperado: FAIL.

- [ ] **Paso 2: implementar**

`falla.py`: reemplazar los imports por `from autoclave.state_machine.alarms.catalogo import SIS_01`, y el `report(Alarm(...))` por `self.alarm_manager.activar(SIS_01, estado="Falla")`.

`hibernacion.py`: igual, con `estado="Hibernación"`.

`control_loop.py`: reemplazar los imports `Alarm`/`AlarmType` por `from autoclave.state_machine.alarms.catalogo import COM_01`; el bloque `self.alarm_manager.report(Alarm(...NO_HAY_CONEXION...))` por `self.alarm_manager.activar(COM_01)`; y `self.alarm_manager.clear("NO_HAY_CONEXION")` por `self.alarm_manager.resolver(COM_01)`.

`advanced_door.py`: reemplazar los imports `Alarm`/`AlarmType` por `from autoclave.state_machine.alarms.catalogo import PUE_04, PUE_05`, y los helpers por:

```python
    def _alarma_activar(self, codigo):
        if self.alarm_manager is not None:
            self.alarm_manager.activar(codigo, origen=self.name, puerta=self.name)

    def _alarma_resolver(self, codigo):
        if self.alarm_manager is not None:
            self.alarm_manager.resolver(codigo, origen=self.name)
```

Reemplazos en `_from_abriendo`/`_from_cerrando`: `self._alarm_report(Alarm(... ABRIENDO_MODO_SEGURO ...))` → `self._alarma_activar(PUE_04)`; `self._alarm_clear(f"ABRIENDO_MODO_SEGURO_{self.name}")` → `self._alarma_resolver(PUE_04)`; ídem CERRANDO → `PUE_05`.

No cambiar nada más de la puerta. `time.time()` y las alarmas nuevas de puertas son de la Parte B.

- [ ] **Paso 3: correr las pruebas**

Correr: `python -m pytest -q -p no:cacheprovider tests/test_alarmas_falla_hibernacion.py tests/test_advanced_door_safe_mode.py tests/test_advanced_door.py tests/test_control_loop_connectivity_ticket.py tests/test_control_loop_desconexion_ciclo.py tests/test_control_loop_resilience.py tests/test_door_from_profile.py`
Esperado: todo PASS. Si alguna prueba de conectividad usa un `AlarmManager` real y verifica `estado.Alarmas_activas`, cambiarla a `alarm_manager.activas()` / `codigos_activados`.

---

### Tarea 8: Migrar CICLO (fallos de ciclo, `motivo_fallo` y `codigo_fallo`)

**Archivos:**
- Modificar: `src/autoclave/state_machine/states/ciclo.py`
- Modificar: `src/autoclave/core/runtime/status.py` (agregar `self.codigo_fallo: str = ""` junto a `motivo_fallo`)
- Modificar: `src/autoclave/services/domain/loop/control_loop.py` (llamada a `abortar_por_desconexion`)
- Modificar las pruebas: `tests/test_ciclo_{apertura_automatica,chaqueta,desconexion,drenaje,drenaje_espera_confirmacion,sensores,suministro}.py`
- Crear: `tests/test_ciclo_alarmas_fallo.py`

**Interfaces:**
- Consume: `activar` devuelve `InstanciaAlarma` (con `.codigo`, `.titulo` y `.descripcion`), las constantes y `nombre_legible`.
- Produce: `estado.motivo_fallo = "{codigo} · {titulo}: {descripcion}"` y `estado.codigo_fallo = codigo`; `CicloState.abortar_por_desconexion(segundos: float = 5.0)`.

**Correspondencia en `ciclo.py`:**

| Hoy | Nuevo |
|---|---|
| `PARO_EMERGENCIA` (rama 2) | `_registrar_fallo(SIS_01, estado="Ciclo")` |
| `FALLO_SUMINISTRO_ELECTRICO` (rama 2b) | `_registrar_fallo(SUM_01, origen=fase, fase=fase)` |
| `FALLO_PUERTA_n_ABIERTA` | `_registrar_fallo(PUE_02, origen="Puerta n", puerta="Puerta n", fase=fase)` |
| `FALLO_PUERTA_n_EMPAQUE` | `_registrar_fallo(PUE_03, origen="Puerta n", puerta=..., pres=emp, minimo=min_empaque, fase=fase)` |
| `SENSOR_AUSENTE` | `_registrar_fallo(SEN_02, origen=fase, sensores=", ".join(legibles), fase=fase)` |
| `FALLO_<FASE>` | `_registrar_fallo(_CIC_POR_FASE[fase.name], origen=fase, motivo=motivo)` |
| `FALLO_CONEXION` | `_registrar_fallo(COM_02, origen=fase, segundos=segundos, fase=fase)` |
| `SUMINISTRO_VAPOR` | `activar(SUM_06, estado="Ciclo")` / `resolver(SUM_06)` |
| `TEMP_DRENAJE_ALTA` | `activar(PRE_06, temp=temp, maximo=temp_segura)` / `resolver(PRE_06)` |
| `TIMEOUT_APERTURA_AUTOMATICA` | `activar(CIC_07, temp=temp, maximo=temp_max, minutos=(elapsed - tiempo_espera) / 60)` / `resolver(CIC_07)` |
| `APERTURA_AUTOMATICA_DENEGADA` | `activar(CIC_08, puerta=puerta, motivo=motivo or "sin motivo reportado")` / `resolver(CIC_08)` |

(`fase` = `self._fase_actual_legible()`.) **`estado.fase_ciclo` conserva exactamente los valores de hoy**: `EMERGENCIA`, `FALLO_SUMINISTRO`, `FALLO_PUERTA_n_*`, `SENSOR_AUSENTE`, `FALLO_<FASE>`, `FALLO_CONEXION`. `CycleLogger`, `/cycle/acknowledge` y la interfaz dependen de ellos.

- [ ] **Paso 1: escribir la prueba que falla**

```python
# tests/test_ciclo_alarmas_fallo.py
from types import SimpleNamespace
from unittest.mock import MagicMock

from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.cycle_phases.base_fase import FaseResult
from autoclave.state_machine.states.ciclo import CicloState


def _ciclo(sensores_di=None, sensores_pres=None, sensores_temp=None, flags=None):
    estado = MagicMock()
    estado.sensores_temp = sensores_temp or {"temp_camara": 100.0}
    estado.sensores_pres = sensores_pres or {"pres_camara": 200.0, "pres_chaqueta": 300.0,
                                             "pres_empaque_1": 300.0, "pres_empaque_2": 300.0}
    estado.sensores_di = sensores_di or {"puerta_1_cerrada": 1, "puerta_2_cerrada": 1,
                                         "vapor_suministro": 1}
    estado.get_flag.side_effect = lambda f: (flags or {}).get(f, False)
    cycle = MagicMock(); cycle.get_param.return_value = None
    config = MagicMock(); config.get.return_value = None
    am = AlarmManager(estado=SimpleNamespace(Alarmas_activas=[]))
    ciclo = CicloState(estado, MagicMock(), cycle, config, am)
    ciclo.reset()
    ciclo._protocolo = MagicMock()
    return ciclo, estado, am


def test_fallo_de_fase_usa_motivo_de_la_fase():
    ciclo, estado, am = _ciclo()
    fase = ciclo._fases[0]
    def falla():
        estado.motivo_fallo = "Timeout: no se alcanzó 320 kPa en 10 min"
        return FaseResult.FALLO
    fase.update = falla
    ciclo.run()
    [inst] = am.activas()
    assert (inst.codigo, inst.origen) == ("CIC-01", "Precalentamiento")
    assert estado.motivo_fallo == ("CIC-01 · Fallo en precalentamiento: "
                                   "Timeout: no se alcanzó 320 kPa en 10 min")
    assert estado.codigo_fallo == "CIC-01"
    assert estado.fase_ciclo == "FALLO_PRECALENTAMIENTO"


def test_fallo_de_fase_sin_motivo_usa_texto_por_defecto():
    ciclo, estado, am = _ciclo()
    ciclo._fases[0].update = lambda: FaseResult.FALLO
    estado.motivo_fallo = ""
    ciclo.run()
    assert "el motivo detallado aún no se registra" in am.activas()[0].descripcion


def test_empaque_bajo_registra_pue03_con_presion_y_minimo():
    ciclo, estado, am = _ciclo(sensores_pres={"pres_camara": 200.0, "pres_chaqueta": 300.0,
                                              "pres_empaque_1": 300.0, "pres_empaque_2": 100.0})
    ciclo.run()
    [inst] = am.activas()
    assert (inst.codigo, inst.origen) == ("PUE-03", "Puerta 2")
    assert "100 kPa" in inst.descripcion and "Precalentamiento" in inst.descripcion
    assert estado.fase_ciclo == "FALLO_PUERTA_2_EMPAQUE"


def test_sensor_ausente_lista_nombres_legibles():
    ciclo, estado, am = _ciclo(sensores_temp={"temp_camara": None})
    ciclo.run()
    [inst] = am.activas()
    assert inst.codigo == "SEN-02" and "Temperatura de cámara" in inst.descripcion
    assert "temp_camara" not in inst.descripcion


def test_desconexion_registra_segundos():
    ciclo, estado, am = _ciclo()
    ciclo.abortar_por_desconexion(segundos=6.2)
    [inst] = am.activas()
    assert inst.codigo == "COM-02" and "6 s" in inst.descripcion
    assert estado.fase_ciclo == "FALLO_CONEXION"


def test_reset_limpia_codigo_fallo():
    ciclo, estado, _ = _ciclo()
    estado.codigo_fallo = "CIC-03"
    ciclo.reset()
    assert estado.codigo_fallo == ""
```

Correr: `python -m pytest -q -p no:cacheprovider tests/test_ciclo_alarmas_fallo.py`
Esperado: FAIL.

- [ ] **Paso 2: implementar en `ciclo.py`**

1. Imports: reemplazar `Alarm`/`AlarmType` por:

```python
from autoclave.state_machine.alarms.catalogo import (
    CIC_01, CIC_02, CIC_03, CIC_04, CIC_05, CIC_06, CIC_07, CIC_08,
    COM_02, PRE_06, PUE_02, PUE_03, SEN_02, SIS_01, SUM_01, SUM_06, nombre_legible,
)
```

y agregar las constantes:

```python
_CIC_POR_FASE = {
    "PRECALENTAMIENTO": CIC_01, "PRE_VACIO": CIC_02, "CALENTAMIENTO": CIC_03,
    "ESTERILIZACION": CIC_04, "DESCOMPRESION": CIC_05, "SECADO": CIC_06,
}
_MOTIVO_NO_REGISTRADO = "La fase terminó en fallo; el motivo detallado aún no se registra."
```

2. En `reset()`, después de `self.estado.motivo_fallo = ""`: `self.estado.codigo_fallo = ""`.
3. Métodos nuevos (en la sección de supervisores):

```python
    def _fase_actual_legible(self) -> str:
        if self._fase_idx < len(self._fases):
            return nombre_legible(self._fases[self._fase_idx].name)
        return "fin de ciclo"

    def _registrar_fallo(self, codigo, origen=None, **valores):
        """Activa la alarma causante y deja motivo_fallo/codigo_fallo para
        CycleLogger y el ticket (spec §5.4)."""
        inst = self.alarm_manager.activar(codigo, origen, **valores)
        self.estado.motivo_fallo = f"{inst.codigo} · {inst.titulo}: {inst.descripcion}"
        self.estado.codigo_fallo = inst.codigo
```

4. `_verificar_puertas()` devuelve cuatro valores:

```python
    def _verificar_puertas(self) -> tuple[bool, str, str | None, dict]:
        """Retorna (ok, fase_ciclo, codigo_alarma, valores). fase_ciclo
        conserva el código histórico (FALLO_PUERTA_n_*) que usan CycleLogger
        y la UI."""
        min_empaque = (self.config.get("presion_empaque") or 300) * 0.6

        for num, di_cerrada, sensor_emp in [
            (1, "puerta_1_cerrada", "pres_empaque_1"),
            (2, "puerta_2_cerrada", "pres_empaque_2"),
        ]:
            puerta = f"Puerta {num}"
            cerrada = bool(self.estado.sensores_di.get(di_cerrada, 0))
            if not cerrada:
                return False, f"FALLO_PUERTA_{num}_ABIERTA", PUE_02, {"puerta": puerta}

            emp = self.estado.sensores_pres.get(sensor_emp)
            if emp is not None and emp < min_empaque:
                return (False, f"FALLO_PUERTA_{num}_EMPAQUE", PUE_03,
                        {"puerta": puerta, "pres": emp, "minimo": min_empaque})

        return True, "", None, {}
```

5. En `run()`, reemplazar cada bloque `self.estado.motivo_fallo = ...` + `self.alarm_manager.report(Alarm(...))` por su `_registrar_fallo` de la tabla, **conservando** `logger.error`, `self.estado.fase_ciclo = ...`, `self._protocolo.ejecutar()` y `self._resultado_pendiente = ...` tal como están. Ejemplos exactos:

```python
        # ── 3. Verificar puertas y empaque ────────────────────────────
        puertas_ok, fase_fallo, codigo, valores = self._verificar_puertas()
        if not puertas_ok:
            logger.error("CicloState: FALLO de seguridad — %s", fase_fallo)
            self.estado.fase_ciclo = fase_fallo
            self._registrar_fallo(codigo, origen=valores["puerta"],
                                  fase=self._fase_actual_legible(), **valores)
            self._protocolo.ejecutar()
            self._resultado_pendiente = CicloResultado.FALLO
            return CicloResultado.ESPERANDO_CONFIRMACION
```

```python
        elif resultado == FaseResult.FALLO:
            logger.error("CicloState: FALLO en fase %s", fase.name)
            self.estado.fase_ciclo = f"FALLO_{fase.name}"
            fase_legible = nombre_legible(fase.name)
            self._registrar_fallo(_CIC_POR_FASE[fase.name], origen=fase_legible,
                                  motivo=self.estado.motivo_fallo or _MOTIVO_NO_REGISTRADO)
            self._protocolo.ejecutar()
            self._resultado_pendiente = CicloResultado.FALLO
            return CicloResultado.ESPERANDO_CONFIRMACION
```

Para SEN-02: `legibles = [nombre_legible(s) for s in ausentes]`.

6. `abortar_por_desconexion(self, segundos: float = 5.0)`: usar `_registrar_fallo(COM_02, origen=fase, segundos=segundos, fase=fase)`, con `fase = self._fase_actual_legible()`.
7. `_mantener_chaqueta`, `_mantener_drenaje` y `_mantener_apertura_automatica`: aplicar la tabla. En `_mantener_apertura_automatica`, CIC-07 necesita `temp_max` y `elapsed - tiempo_espera`, que ya existen en ese punto.

En `control_loop.py`, cambiar la llamada a `self.state_machine.ciclo.abortar_por_desconexion(segundos=now - self._desconectado_desde)`.

En `status.py`, agregar `self.codigo_fallo: str = ""` debajo de `self.motivo_fallo: str = ""`.

- [ ] **Paso 3: actualizar las pruebas de ciclo existentes**

Aplicar las sustituciones de la tarea 6, paso 5, más estas:

| Archivo | Hoy | Nuevo |
|---|---|---|
| `test_ciclo_suministro.py:44-46` | `report ... alarma.id == "FALLO_SUMINISTRO_ELECTRICO"` | `assert codigos_activados(ciclo.alarm_manager) == ["SUM-01"]` |
| `test_ciclo_desconexion.py:27-29, 56` | `report.assert_called_once()` / `id == "FALLO_CONEXION"` | `activar.assert_called_once()` / `codigos_activados(...) == ["COM-02"]` |
| `test_ciclo_sensores.py:34` | `report.assert_called_once()` | `activar.assert_called_once()` + `ultima_activacion(...)[0] == "SEN-02"` |
| `test_ciclo_chaqueta.py:23-25` | `SUMINISTRO_VAPOR`, `blocks_operation is False` | `SUM_06`, `CATALOGO[SUM_06].bloquea_inicio is False` |
| `test_ciclo_drenaje.py:34-36` | `TEMP_DRENAJE_ALTA`, `blocks_operation is False` | `ultima_activacion(...)[0] == PRE_06`. Quitar la verificación de bloqueo: PRE-06 tiene `bloquea_inicio=True` y no tiene efecto (spec §4.3) |
| `test_ciclo_apertura_automatica.py:202-229, 370-382` | `TIMEOUT_APERTURA_AUTOMATICA` / `APERTURA_AUTOMATICA_DENEGADA`, `"... no esta cerrada" in alarma.description` | `CIC_07` / `CIC_08`, `"... no esta cerrada" in ultima_activacion(am)[2]["motivo"]` |

Con un `alarm_manager` `MagicMock`, `_registrar_fallo` deja en `estado.motivo_fallo` un texto con repr de mocks. Las pruebas de ciclo no lo verifican; si alguna lo hace, configurar `alarm_manager.activar.return_value = SimpleNamespace(codigo="X", titulo="T", descripcion="D")`.

- [ ] **Paso 4: correr las pruebas**

Correr: `python -m pytest -q -p no:cacheprovider tests/test_ciclo_alarmas_fallo.py tests/test_ciclo_apertura_automatica.py tests/test_ciclo_chaqueta.py tests/test_ciclo_desconexion.py tests/test_ciclo_drenaje.py tests/test_ciclo_drenaje_espera_confirmacion.py tests/test_ciclo_sensores.py tests/test_ciclo_suministro.py tests/test_ciclo_sin_purga.py tests/test_ciclo_valvula_reposo.py tests/test_ciclo_reset_f0.py tests/test_control_loop_desconexion_ciclo.py tests/test_calentamiento_fase.py tests/test_esterilizacion_fase.py`
Esperado: todo PASS. `test_control_loop_desconexion_ciclo.py` solo usa `assert_not_called()`/`assert_called_once()`. Si alguna verifica `assert_called_once_with()` sin argumentos, cambiarla a `assert_called_once()`.

---

### Tarea 9: `codigo_fallo` en la base de datos y tickets

**Archivos:**
- Modificar: `src/autoclave/services/domain/logging/ticket_formatter.py` (función `motivo_ticket` y uso en `format_ticket`)
- Modificar: `src/autoclave/services/domain/logging/cycle_logger.py:269-284`
- Modificar: `src/autoclave/ui_pyside/views/impresion_menu.py:51-70`
- Modificar las pruebas: `tests/test_ticket_formatter.py`, `tests/test_cycle_logger_printer.py` (`cerrar_ciclo` falso), `tests/test_impresion_menu.py`

**Interfaces:**
- Consume: `CATALOGO`; `DbManager.cerrar_ciclo(..., codigo_fallo=...)` (tarea 3); `estado.codigo_fallo` (tarea 8).
- Produce: `motivo_ticket(codigo: str | None, motivo: str | None) -> str | None`.

- [ ] **Paso 1: escribir las pruebas que fallan**

Agregar a `tests/test_ticket_formatter.py`:

```python
def test_motivo_ticket_usa_codigo_y_titulo():
    from autoclave.services.domain.logging.ticket_formatter import motivo_ticket
    assert motivo_ticket("CIC-03", "CIC-03 · Fallo en calentamiento: largo") == \
        "CIC-03 - Fallo en calentamiento"


def test_motivo_ticket_sin_codigo_conserva_motivo_viejo():
    from autoclave.services.domain.logging.ticket_formatter import motivo_ticket
    assert motivo_ticket("", "Fallo en la fase secado.") == "Fallo en la fase secado."
    assert motivo_ticket("XXX-99", "texto") == "texto"
    assert motivo_ticket(None, None) is None


def test_format_ticket_usa_codigo_fallo_si_existe():
    from autoclave.services.domain.logging.ticket_formatter import format_ticket
    ciclo = {
        "numero_ciclo": 1, "serie": "S", "modelo": "M", "version_sw": "v",
        "nombre_ciclo": "N", "tipo_ciclo": "T", "temp_esterilizacion": 134,
        "tiempo_esterilizacion": 3.5, "fecha_inicio": "2026-10-07T08:00:00",
        "resultado": "FALLO", "fecha_fin": "2026-10-07T09:00:00",
        "motivo_fallo": "COM-02 · Comunicación perdida durante el ciclo: ...",
        "codigo_fallo": "COM-02",
    }
    texto = format_ticket(ciclo, [])
    assert "Motivo: COM-02 - Comunicación perdida durante el ciclo" in texto
```

> Si `format_header` exige más claves de `ciclo` que las de este diccionario, copiarlas del fixture que ya usa `tests/test_ticket_formatter.py`.

Agregar a `tests/test_impresion_menu.py`:

```python
def test_ticket_alarmas_formato_nuevo():
    from autoclave.ui_pyside.views.impresion_menu import _build_alarms_ticket_lines
    texto = "\n".join(_build_alarms_ticket_lines([{
        "codigo": "PUE-02", "titulo": "Puerta abierta durante el ciclo",
        "aparecida": "2026-10-07T09:30:05", "origen": "Puerta 1",
        "id": "PUE-02|Puerta 1", "level": "FALLA", "description": "largo",
        "source_state": "Puerta 1",
    }]))
    assert "PUE-02 - Puerta abierta durante el ciclo" in texto
    assert "09:30:05 07/10/2026 - Puerta 1" in texto
    assert "largo" not in texto and "Nivel:" not in texto
```

Las pruebas viejas de `_build_alarms_ticket_lines` (formato `ID:`/`Nivel:`) siguen válidas para alarmas sin `codigo` hasta la tarea 10.

En `tests/test_cycle_logger_printer.py:24-25`, el `cerrar_ciclo` falso pasa a:

```python
    def cerrar_ciclo(self, ciclo_id, resultado, motivo_fallo=None, codigo_fallo=None):
        self.cerrados.append((ciclo_id, resultado, motivo_fallo))
        self.codigos.append(codigo_fallo)
```

(inicializar `self.codigos = []` en su `__init__`). Agregar al mismo archivo una prueba que, con `estado.codigo_fallo = "CIC-03"` y `estado.motivo_fallo = "CIC-03 · Fallo en calentamiento: x"`, cierre un ciclo con resultado de fallo y verifique `db.codigos == ["CIC-03"]` y que el pie encolado en la impresora contenga `"Motivo: CIC-03 - Fallo en calentamiento"`. Para disparar el cierre, seguir el patrón de las pruebas existentes de ese archivo; el `_FakeEstado` de la línea ~87 necesita `self.codigo_fallo = ""`.

Correr: `python -m pytest -q -p no:cacheprovider tests/test_ticket_formatter.py tests/test_impresion_menu.py tests/test_cycle_logger_printer.py`
Esperado: FAIL.

- [ ] **Paso 2: implementar**

`ticket_formatter.py`, agregar:

```python
from autoclave.state_machine.alarms.catalogo import CATALOGO


def motivo_ticket(codigo: str | None, motivo: str | None) -> str | None:
    """Línea de motivo del ticket térmico: solo código y título (spec §5.4).
    Ciclos anteriores al catálogo (sin codigo_fallo) conservan su motivo."""
    definicion = CATALOGO.get(codigo or "")
    if definicion is not None:
        return f"{definicion.codigo} - {definicion.titulo}"
    return motivo or None


def _campo(fila, clave):
    try:
        return fila[clave]
    except (KeyError, IndexError):
        return None
```

En `format_ticket`: `motivo=motivo_ticket(_campo(ciclo, "codigo_fallo"), ciclo.get("motivo_fallo"))`. Si `ciclo` es un `sqlite3.Row` sin `.get`, usar `_campo(ciclo, "motivo_fallo")` también. Revisar cómo llega `ciclo` hoy (`server.py` `/cycle/history/{id}/ticket`).

`cycle_logger.py`, en `_on_fin`:

```python
            motivo = getattr(self.estado, "motivo_fallo", "") or None
            codigo = getattr(self.estado, "codigo_fallo", "") or None
            self.db.cerrar_ciclo(self._ciclo_id, resultado, motivo, codigo)
            ...
                self.printer.enqueue(format_footer(
                    resultado, datetime.now().isoformat(),
                    temp_final=self._ultima_temp, motivo=motivo_ticket(codigo, motivo),
                    f0_total=f0_total,
                ))
```

(importar `motivo_ticket` desde `ticket_formatter`).

`impresion_menu.py`, `_build_alarms_ticket_lines`: dentro del `for`:

```python
    for alarma in alarms:
        codigo, titulo = alarma.get("codigo"), alarma.get("titulo")
        if codigo and titulo:
            lines += [
                f"{codigo} - {titulo}",
                f"{_hora_ticket(alarma.get('aparecida'))} - {alarma.get('origen') or '-'}",
                "------------------------",
            ]
            continue
        lines += [
            f"ID: {alarma.get('id', '')}",
            f"Nivel: {alarma.get('level', '')}",
            f"Origen: {alarma.get('source_state', '')}",
            alarma.get("description") or "",
            "------------------------",
        ]
```

y la función auxiliar a nivel de módulo:

```python
def _hora_ticket(iso: str | None) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%H:%M:%S %d/%m/%Y")
    except (TypeError, ValueError):
        return "--:--:--"
```

- [ ] **Paso 3: correr las pruebas**

Correr: `python -m pytest -q -p no:cacheprovider tests/test_ticket_formatter.py tests/test_impresion_menu.py tests/test_cycle_logger_printer.py tests/test_cycle_logger_grafica.py tests/test_ciclos_print.py tests/test_backend_cycle_summary.py`
Esperado: todo PASS.

---

### Tarea 10: Quitar la API vieja, verificar, revisar y hacer commit

**Archivos:**
- Borrar: `src/autoclave/state_machine/alarms/alarm.py`, `src/autoclave/state_machine/alarms/alarm_types.py`
- Modificar: `alarm_manager.py` (quitar `report`, `clear`, `clear_recoverable`, `active_alarms` y el import de `AlarmType`; `has_*` solo con instancias), `state_machine.py` (quitar `self.estado.Alarmas_activas.clear()`), `core/runtime/status.py` (quitar `self.Alarmas_activas = []`), `server.py` (quitar la lista `alarms` vieja: `alarms = [_alarma_dto(i) for i in context.alarm_manager.activas()]`)
- Modificar las pruebas: `tests/test_status_endpoint_alarms.py` (borrar `test_status_incluye_description_y_source_state_por_alarma`, que prueba la API vieja), `tests/test_alarm_manager.py` (la fábrica `_gestor` deja de pasar `estado`)

- [ ] **Paso 1: escribir la verificación de que no queda la API vieja (prueba que falla)**

```python
# tests/test_alarmas_sin_api_vieja.py
import pathlib
import re

_SRC = pathlib.Path(__file__).resolve().parents[1] / "src" / "autoclave"
_PROHIBIDO = re.compile(
    r"alarms\.alarm import|alarms\.alarm_types|AlarmType|Alarmas_activas|"
    r"alarm_manager\.(report|clear)\(|_alarm_(report|clear)\("
)


def test_ningun_modulo_usa_la_api_vieja():
    hallazgos = [
        f"{p.relative_to(_SRC)}:{n}: {linea.strip()}"
        for p in _SRC.rglob("*.py")
        for n, linea in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if _PROHIBIDO.search(linea)
    ]
    assert hallazgos == []
```

Correr: `python -m pytest -q -p no:cacheprovider tests/test_alarmas_sin_api_vieja.py`
Esperado: FAIL, con la lista de restos (`alarm_manager.py`, `state_machine.py`, `status.py`, `server.py`).

- [ ] **Paso 2: quitar los restos**

1. `alarm_manager.py`: borrar el bloque "API vieja" completo y el import de `AlarmType`, y dejar:

```python
    def has_emergency(self) -> bool:
        return self._activas_nuevas(Nivel.FALLO_CRITICO)

    def has_failure(self) -> bool:
        return self._activas_nuevas(Nivel.ALARMA)

    def has_alert(self) -> bool:
        return self._activas_nuevas(Nivel.AVISO)

    def has_blocking_alarm(self) -> bool:
        with self._lock:
            return any(i.estado is EstadoInstancia.ACTIVA and i.definicion.bloquea_inicio
                       for i in self._instancias.values())

    def has_active_alarms(self) -> bool:
        return self._activas_nuevas()
```

En `__init__`, quitar `self.active_alarms = ...` y conservar el parámetro `estado` (StateMachine lo sigue pasando).

2. Borrar `alarm.py` y `alarm_types.py`.
3. Quitar los restos en `state_machine.py`, `status.py` y `server.py` (ver la lista de Archivos).
4. Pruebas: borrar la prueba vieja de `/status`; en `test_status_alarmas_vacias_devuelve_lista_vacia`, quitar `mock_ctx.estado.Alarmas_activas = []`. En `tests/test_io_test_mode_endpoints.py:70`, quitar esa misma línea y poner `mock_ctx.alarm_manager.activas.return_value = []` y `mock_ctx.alarm_manager.eventos_recientes.return_value = []`. En `tests/test_control_loop_set_active_cycle.py:15`, el atributo sobra pero no molesta: dejarlo.

- [ ] **Paso 3: suite completa**

Correr: `python -m pytest -q -p no:cacheprovider`
Esperado: **0 fallos**, y un total igual a 1794 más las pruebas nuevas, menos las borradas. Anotar los números exactos para el informe.

- [ ] **Paso 4: revisión de seguridad y de concurrencia**

Lanzar en paralelo los agentes `safety-reviewer` y `timing-auditor`, de solo lectura, sobre el diff de alarmas (`git diff -- src/autoclave/state_machine src/autoclave/services src/autoclave/devices src/autoclave/backend src/autoclave/core`). Pedirles que verifiquen:
- ninguna condición de disparo ni nivel cambió (restricción global);
- el buzer y las salidas no cambiaron;
- el candado de `AlarmManager` no puede bloquear el ControlLoop (los oyentes corren fuera del candado);
- ninguna escritura de la base de datos dentro del tick puede lanzar hacia `_tick()`;
- `abortar_por_desconexion(segundos=...)` conserva su semántica.

Corregir los hallazgos confirmados, volver a correr la suite y registrar los descartados con su razón en el informe.

- [ ] **Paso 5: informe**

Escribir `docs/informes/sistema_alarmas_parte_a.md` (en español) con: qué se hizo por tarea, el resultado de la suite (números exactos), los hallazgos de las revisiones y su tratamiento, las desviaciones de la spec (ninguna esperada, salvo las ya anotadas del 2026-10-07) y lo pendiente para las partes B y C.

- [ ] **Paso 6: commit (solo con aprobación de Cristian)**

Mostrar a Cristian el resumen y **esperar su aprobación explícita**. El commit lleva solo los archivos y fragmentos de alarmas:
- Archivos nuevos o solo de alarmas: `git add` directo (catálogo, instancia, `alarm_manager.py`, `historial_alarmas.py`, `state_machine/states/*.py` tocados, `advanced_door.py`, `ticket_formatter.py`, `cycle_logger.py`, `status.py`, las pruebas nuevas y las migradas, la spec, el plan y el informe), y `git rm` de `alarm.py`/`alarm_types.py`.
- Archivos con cambios ajenos previos (`server.py`, `db_manager.py`, `control_loop.py`, `context.py`, `impresion_menu.py`; confirmar con `git diff --stat` cuáles tienen fragmentos que no son de alarmas): generar `git diff <archivo> > %TEMP%/<archivo>.patch`, editar el parche para dejar solo los fragmentos de alarmas y aplicarlo con `git apply --cached`. Verificar con `git diff --cached <archivo>` antes del commit.

Mensaje:

```
feat(alarmas): catálogo con códigos, historial y reconocimiento (Parte A)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0148DLprsc39Co3fUuHAvQ83
```

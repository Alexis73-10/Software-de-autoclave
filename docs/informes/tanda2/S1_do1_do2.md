# S1 — DO1/DO2 en el equipo de pruebas

Instrucción: `instruccion_claude_code_tanda_2.md` §2 S1 y decisión 1 (19-oct): el equipo de pruebas NO lleva DO1 ni DO2. El generador interno tiene sus propios controles; el software no los enciende ni los lee.

## Qué se hizo

- `installation/profile.py`: con `vapor_source = "generator"` ya **no se permite ninguna** salida de fuente de vapor. DO1 (`vapor_generador`) y DO2 (`vapor_caldera`) quedan bloqueadas:
  - `SetOutput` las fuerza a OFF;
  - `/io/test/output` las rechaza con 409 `fuente_vapor_no_instalada`, con un mensaje más claro.

  Antes de S1, `generator` permitía DO1.
- `devices/io/set_io.py`: al arrancar se registra en el log qué DO quedan deshabilitadas (revisión SAF-02).
- Asistente QML: `instalacion.vapor_generator_desc` dice "El equipo genera su propio vapor; el generador tiene sus propios controles (sin salidas DO1/DO2)" (es/en; anotado como sin revisar).
- **Caldera externa y mixto: sin cambios.** `boiler` → solo DO2; `mixed` y perfil sin campo → DO1 y DO2. **La asignación de DO para esos equipos queda abierta**: hay que definir en campo quién las enciende y cuándo.

## Verificación (a)–(d)

- **(a) Nadie enciende ni espera DO1/DO2.**
  - `vapor_generador_on` y `vapor_caldera_on` solo existen en `set_io.py`, sin llamadores. Tampoco hay llamadas dinámicas ni con canal literal 1/2.
  - Nadie lee `salidas_do["vapor_generador"/"vapor_caldera"]`.
  - Lo fija la prueba estática `test_ningun_codigo_de_control_enciende_ni_lee_do1_do2`.
  - Lazo, fases, protocolo de fallo, estado seguro, puertas (DO 9–12, 20–23) y bomba (DO18/19) no los tocan. `reset_all_outputs` los apaga.
- **(b) Nada los requiere.**
  - Las alarmas SUM_04 (DI9 `agua_generador`) y SUM_06 (DI12 `vapor_suministro`) leen **entradas**, no dependen de DO1.
  - El simulador no publica DO.
  - El firmware V3 no tiene lógica para DO1/DO2.
  - DISCREPANCIA_SALIDAS no se ve afectada: lo comandado es OFF y lo reportado también.
  - En el modo prueba, el backend rechaza el encendido.
- **(c) Perfil y asistente.**
  - El asistente QML exige elegir la fuente; con "Generador interno" el perfil se escribe con `generator` y ya no deja DO1 habilitada.
  - La vista PySide de salidas (`ui_pyside/views/entrdas_salidas/io_do.py`) sigue mostrando DO1/DO2 como tarjetas: al pulsarlas, el backend rechaza y la vista ignora el 409. Ver PENDIENTE.
- **(d) Salidas de generador en otras DO:** no hay.
  - El generador solo tiene entradas: DI9 `agua_generador` y DI12 `vapor_suministro`.
  - `agua_bomba` (DO18) es el agua de la bomba de vacío, no del generador.
  - No se cambió el cableado asumido.

**Cierre del pendiente T2** ("DO1/DO2: no está definido quién ni cuándo las enciende"):
- **resuelto para el generador interno:** nadie, nunca;
- **abierto para caldera externa y mixto.**

## Pruebas

- Antes: 3386. Después: 3394.
- Nueva `tests/test_s1_do1_do2_generador.py`: permitidas vacías, DO1/DO2 forzadas a OFF, caldera/mixto/None sin cambios, prueba estática, 409 del modo prueba sin tocar la tarjeta y texto del asistente.
- `tests/test_t2_vapor_source.py`: ajustada a la regla nueva.

## Revisor (safety-reviewer)

Sin Críticos ni Altos.
- **SAF-01 (Medio):** un perfil **sin** `vapor_source` se trata como mixto y deja DO1/DO2 permitidas. Es el caso de los perfiles anteriores a E1b y de los del asistente tkinter. El `installation_profile.json` de la raíz del repo es uno de ellos: `SPK-AVH-450`, `locked`, sin el campo.
  - **Acción para Cristian:** reinstalar el perfil del equipo de pruebas con el asistente QML y elegir "Generador interno" (comprobación manual 1).
  - R1 retira el asistente tkinter.
  - No se cambió el valor por defecto de "sin campo". Cambiarlo afectaría a equipos con caldera ya instalados; DECISIÓN SIN CONFIRMAR D-S1-2.
- **SAF-02 (Bajo):** un equipo ya instalado con `generator` que usara DO1 la pierde al actualizar. **Corregido:** queda en el log de arranque. Hay que anotarlo en las notas de la versión.
- **SAF-03 (Bajo):** la vista PySide de E/S muestra DO1/DO2 accionables y no muestra el rechazo. PENDIENTE: la Fase 5 de Opciones, que retira PySide, está fuera de alcance.
- **SAF-04 (Bajo):** `config/instances/ACV-2026-001.yaml` (`steam_supply.mode: generator`) lista `vapor_generador` como habilitada. Ningún `.py` lee esos YAML; queda como documentación incoherente. PENDIENTE: retirar ese YAML o marcarlo como obsoleto.
- **SAF-05 (Bajo):** prueba estática ampliada (`.get(...)`, `set_output(1|2, True)` literal). **Corregido.**

## DECISIONES SIN CONFIRMAR

- **D-S1-1:** la decisión 1 se aplica a **todo** equipo con `vapor_source = generator`, no solo al de pruebas: "generador interno" = generador con controles propios, sin DO1/DO2. Alternativa: una cuarta opción, p. ej. `generator_autonomo`, y dejar `generator` con DO1.
- **D-S1-2:** un perfil sin `vapor_source` sigue tratándose como mixto (E1b, D-T2).

## Comprobaciones manuales

1. Ver el perfil instalado en el equipo de pruebas (`installation_profile.json`): debe tener `"vapor_source": "generator"`. Si no lo tiene, reinstalar con el asistente QML.
2. Revisar si los bornes DO1/DO2 de la tarjeta del banco tienen algo cableado.
3. **Entradas del generador:** DI9 `agua_generador` (SUM_04, bloqueante) y DI12 `vapor_suministro` (SUM_06, corta la chaqueta) vienen marcadas como cableadas por defecto en el asistente. Si el generador interno no las entrega al software, hay que desmarcarlas en el paso de suministros. Si no, el equipo queda bloqueado por SUM_04 o se corta la chaqueta.
4. En modo prueba, intentar encender DO1/DO2: el rechazo debe ser "Esta salida de fuente de vapor no la usa este equipo".

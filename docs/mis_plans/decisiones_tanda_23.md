# Decisiones de la tanda 23 — «módulo E/S» y numeración RTD / AI

Fecha: 29-oct-2026. Decisiones de Cristian (chat del 29-oct) y de diseño marcadas como tales. Esta spec la ejecuta `prompt_claude_code_tanda23.md`.

## Contexto

- Hoy el software llama «tarjeta» (y en inglés «board») al hardware de E/S: 124 archivos de `src/`, `tools/` y `packaging/`, 60 cadenas en `i18n/es.json` y unas 46 «board» en `en.json`, 11 códigos de alarma `TARJETA_*`.
- Hoy los puertos analógicos son AI 01–06 (temperatura, PT100 del M31-GXDXX0600-U) y AI 09–16 (presión = AI 1–8 del principal), `_OFFSET_PRES = 8` en `core/runtime/asignacion_io.py`, y el enlace lee solo 8 AI (`DIR_PRES = 0x0000`, `N_PRES = 8` en `protocols/modbus_link.py`).
- El principal M31-XAXX0A00G-U del equipo de pruebas (el mismo de las tandas 19–20) tiene 16 AI de corriente de una sola terminal; según el manual del principal V1.4, §4.10.3, son registros de entrada contiguos desde 0x0000 (AI1 = 0x0000 … AI16 = 0x000F, fc04, µA). El rango 4–20 mA de las 16 (0x0DAC ×16, holding) ya se escribe hoy (MOD-07).

## Nombre del hardware (MES)

- **MES-01 Nombre.** El hardware de E/S se llama «módulo E/S», en singular aun cuando se refiera al conjunto principal + 5 expansiones (decisión de Cristian), con concordancia masculina («el módulo E/S desconectado», «emparejado»). En inglés «I/O module». Reemplaza a «tarjeta», «tarjeta de E/S», «tarjeta de control», «tarjeta del equipo», «targeta» y a «board» cuando se refiere a ese hardware (no tocar «keyboard», «dashboard», «onboard», etc.). Ejemplos: «Conectando con el módulo E/S», «Versión del módulo E/S», «ID del módulo E/S», «Módulo E/S desconectado: no se puede verificar el paro ni la cámara. NO ABRIR.». El Setup: «Red del módulo E/S».
- **MES-02 Alcance (aprobado).** Todo texto visible: QML, `ui_pyside`, `i18n` es/en, ticket, PDF, correo, historial, nombres y descripciones de alarmas, Setup (`tools/instalador/autoclave.iss` y su LEEME), textos del rol `configurar-modulo`, herramientas (`tools/emparejar_tarjeta.py`, `tools/registro_pruebas`, `tools/diagnostico`), mensajes de log, comentarios y docstrings, nombres de pruebas. También los identificadores internos: `tarjeta` → `modulo_es` (snake), `Tarjeta` → `ModuloEs` (Pascal), `tarjeta` → `moduloEs` (camel), incluidas claves de i18n, campos de `/status` y del cliente, propiedades QML y archivos (`git mv tools/emparejar_tarjeta.py tools/emparejar_modulo_es.py`).
- **MES-03 Lo que NO se renombra.**
  1. Los códigos de alarma `TARJETA_*`: se guardan en el historial de alarmas y los citan el catálogo, el registro de riesgos y la trazabilidad (aprobado). Solo cambian su nombre y descripción visibles.
  2. Nombres persistidos en datos de campo: columnas o valores de SQLite, claves de JSON/YAML en `data/`, perfil, respaldos, registro de Windows y nombres de evento de la bitácora. Se conservan y se listan en el informe.
  3. «Tarjeta» con sentido de recuadro de interfaz (`TarjetaMenu`, `TarjetaResumen`, `TarjetaContenido`, `TarjetaSensor`, `tarjetaOpciones`, la «tarjeta Último ciclo», etc.). Cada caso dudoso se decide leyendo el uso.
  4. Documentos históricos: informes de tandas, decisiones, planes y prompts de tandas cerradas; filas viejas de la bitácora; tickets ya impresos.
- **MES-04 Códigos visibles (decisión de diseño).** Donde la UI, el ticket, el PDF, el correo o una exportación muestran el código de una alarma, un `TARJETA_<x>` se muestra como `MODULO_ES_<x>` mediante una sola función de presentación (p. ej. `codigo_visible()`); el código guardado no cambia. Así no queda «tarjeta» visible en ningún lado sin romper el historial ni la trazabilidad.

## Numeración de entradas analógicas (AIN)

- **AIN-01 Etiquetas (aprobado).** DI 01–16 y DO 01–32 sin cambio. Temperatura: «RTD 01» … «RTD 06». Presión: «AI 01» … «AI 16». En Entradas/Salidas, Reasignación, Calibración de sensor, Información del equipo, errores y avisos (`puerto_inexistente`, `puerto_sin_calibracion`, etc.), filas nuevas de la bitácora, logs y documentación vigente.
- **AIN-02 Modelo de datos (aprobado).** El tipo sigue siendo `"AI"`, separado en los grupos `AI_TEMP` (puertos 1–6) y `AI_PRES` (puertos 1–16); solo cambia la etiqueta visible. `_OFFSET_PRES` deja de sumar para el número de puerto. `asignacion_io.FORMATO` pasa a 2 (= presión numerada 1–16).
- **AIN-03 Lectura.** fc04 0x0000 ×16 (`N_PRES = 16`). Disposición cruda: `ai[0..5]` = RTD 1–6, `ai[6..7]` = None, `ai[8..23]` = AI 1–16 (largo 24). `map_pres[f] = i` sigue significando AI i+1 (canal crudo 8+i) y `map_temp` no cambia; así las asignaciones y calibraciones de los canales 0–7 conservan su canal físico. Se actualizan `hal/measures/units.py`, el simulador `tests/helpers/m31_simulado.py`, `tests/helpers/enlace_doble.py`, el simulador de `src/autoclave/simulador` y todo consumidor que suponga 16 posiciones.
- **AIN-04 Calibración (decisión de diseño).** `config/calibration_modbus.yaml`: 16 entradas de presión nominales (4000–20000 µA → 0–400 kPa abs). Una copia en `data/` o un respaldo con 8 entradas de presión se completa al cargar con las nominales para los canales 8–15, sin tocar los canales 0–7, con un registro en el log. Sin esto, asignar una función a AI 09–16 daría `puerto_sin_calibracion`. `tools/verificar_calibracion_neutra.py` exige las 16.
- **AIN-05 Migración (aprobado: automática).** Un `asignacion_io.json` con FORMATO 1 se migra al cargar: cada función del grupo `AI_PRES` pasa de p a p − 8; se escribe en FORMATO 2 con `.bak` y una fila en la bitácora (evento con categoría válida en `bitacora.CATEGORIAS`). Es idempotente (un FORMATO 2 no se toca). La misma migración se aplica a un respaldo de configuración con FORMATO 1 al restaurarlo. Se corrigen los YAML de `config/instances/` (p. ej. `ACV-2026-001.yaml`). Las filas viejas de la bitácora no se reescriben; el informe dice desde cuándo rige la numeración nueva.

## Riesgos (para `docs/riesgos/registro_riesgos.md`)

- **AIN-R1 (ALTA).** Desde ahora el mismo número sirve en dos grupos (RTD 01 y AI 01). La comprobación de puertos duplicados, las búsquedas puerto → función, las evidencias de reasignación, los ids de Entradas/Salidas y la UI de Reasignación deben trabajar por grupo; antes funcionaban por tipo `"AI"` porque los rangos no se solapaban. Control: revisión de cada uso de `puerto` con tipo `"AI"` y pruebas con RTD 01 y AI 01 asignados a la vez.
- **AIN-R2 (ALTA).** Una migración errada movería un sensor de presión a otro canal físico. Control: prueba de equivalencia (para toda asignación FORMATO 1, el canal crudo `ai[]` de cada función es idéntico antes y después) y verificación en el equipo (la presión de cámara sigue leyendo lo mismo).
- **AIN-R3 (MEDIA).** AI 09–16 quedan con calibración nominal. Control: calibración en sitio antes de usar un canal nuevo (procedimiento existente).

## Verificación en el equipo (después de instalar)

1. Entradas/Salidas: presiones en AI 01–04 con las mismas lecturas que antes; temperaturas en RTD 01–06.
2. Reasignación: etiquetas RTD/AI, AI 09–16 disponibles; asignar RTD 01 y AI 01 a la vez no da conflicto.
3. Desconectar el cable de red de los módulos: mensajes con «módulo E/S», ninguno con «tarjeta».
4. Ticket, PDF, Información del equipo y del sistema, Setup: sin «tarjeta»; en inglés sin «board».

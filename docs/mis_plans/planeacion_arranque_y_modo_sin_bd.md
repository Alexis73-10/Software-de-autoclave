# Planeación: arranque con splash, verificación de sensores y modo sin base de datos

Estado: especificación para aprobación final antes de instruir a Code. No contiene código.
Fecha: 2026-10-02. Marco: IEC 62304 Clase C, ISO 14971.
Actualización 2026-10-07: D-01 resuelta (opción B, el backend es el único custodio de la base). La fase A de comunicación serial queda pausada porque la tarjeta KinCony/ESP32 será reemplazada por módulos de E/S remotas M31-U con el PC como maestro Modbus TCP (conexión por RJ45; llegada estimada en 15 a 30 días). La etapa 7 del splash pasa a llamarse "Conectando con módulos de E/S".
Ubicación sugerida: `docs\mis_plans\planeacion_arranque_y_modo_sin_bd.md`
Documento hermano: `planeacion_protocolo_serial_esp32.md` (CRC, handshake con la tarjeta, trama ST).

---

## 1. Alcance

- Lanzador único, backend y dos UI QML (una por pantalla).
- Pantalla de arranque (splash) con barra y nombre del proceso.
- Verificación de sensores al arrancar y en supervisión continua.
- Modo de operación sin base de datos y numeración de ciclos.
- Retiro del ejecutable viejo en tkinter.
- Fuera de alcance: pantallas de ciclo en curso, opciones y nuevo usuario (documentos propios).

## 2. Decisiones aprobadas por Cristian

1. Un solo ejecutable arranca las dos UI y el backend. Las UI arrancan primero.
2. El backend corre como subproceso independiente del lanzador: si una UI se cierra o falla, el `ControlLoop` sigue corriendo.
3. Splash: una barra con el nombre del proceso en curso, sin más detalle. Animación liviana del logo de Especifika permitida.
4. Ante un fallo de arranque, el comportamiento depende del tipo de fallo (clasificación de la sección 5).
5. La base de datos es degradable: si falla, el equipo debe poder operar y ejecutar ciclos con alarma persistente de operación sin base de datos.
6. Login sin base de datos: ciclo sin operador registrado, con confirmación explícita por ciclo y restricciones (sección 7.6).
7. Se agrega la etapa de verificación de sensores.
8. Contador consecutivo persistente, índice UNIQUE sobre el número de ciclo, instantánea del programa por ciclo y marcado de ciclos interrumpidos al arrancar.
9. El ejecutable viejo (tkinter) se elimina; la UI es solo QML.
10. Hardware de la estación: PC con AMD Ryzen 5 y 16 GB de RAM (el mini PC Intel N150 no se compró).
11. Prueba de banco de sensores diferida.
12. D-01 resuelta el 2026-10-07: opción B (sección 7.8).
13. E/S futura: módulos M31-U por Modbus TCP (RJ45); la capa de E/S se especificará aparte cuando haya documentación de los módulos.

## 3. Arquitectura de arranque

- El lanzador inicia las dos UI QML y el backend. Cada UI muestra el splash de inmediato.
- Hallazgo ARR-01 [Alto]: hoy `BackendContext` inicializa todo al importar `server.py`, antes de que uvicorn abra el puerto 8000, así que ninguna UI puede ver el avance. Cambio requerido: la inicialización pasa a una función de arranque explícita, por etapas, con el puerto abierto desde el inicio y un endpoint de estado de arranque (etapa actual, resultado y código de falla de cada etapa). Esto también corrige el hallazgo 1 de Code (puerto ocupado detectado antes de abrir el serial y arrancar el `ControlLoop`).
- Fuente única de estado: las dos UI consultan el mismo endpoint por polling (aceptado en la migración a QML) y muestran la misma etapa.
- Responsabilidades que hoy hace solo el `main.py` de tkinter y que migran al arranque nuevo (ARR-02 [Alto]): verificación del perfil de instalación y del reloj, limpieza de backend huérfano, heartbeat de `last_shutdown.json` y ticket de arranque. El ticket se mantiene (en segundo plano, no es una etapa).
- Los ajustes de tiempo usan `time.monotonic()`.
- Supuesto D-04: si una UI se cierra, el lanzador la relanza hasta 3 veces con 5 s de espera; el backend nunca se reinicia por eso.

## 4. Etapas del splash

Cada etapa tiene peso en la barra, texto corto y resultado. El avance refleja el estado real; no hay temporizador falso. Tiempo mínimo de visualización del splash: 1,5 s para evitar un destello. Tiempos de timeout por defecto, medidos en el PC de desarrollo: validar en el Ryzen real y ajustar en configuración.

1. Verificando instalación — perfil y reloj. Sin timeout. Falla: bloqueante (asistente para el técnico si falta el perfil; error si el reloj fue alterado).
2. Liberando procesos previos — 10 s. Falla: bloqueante.
3. Iniciando servicios — el backend abre el puerto: 20 s (cubre la extracción de PyInstaller si el ejecutable es de un solo archivo). Falla: bloqueante.
4. Cargando configuración y ciclos — sin timeout. Bloqueante: `global_params.json` ilegible o ciclo por defecto inexistente. Degradable: un JSON de ciclo individual corrupto (se omite, queda en log y se avisa).
5. Verificando calibración — sin timeout. Falla: bloqueante, sin valores por defecto silenciosos.
6. Abriendo base de datos — 5 s, 3 reintentos. Falla: degradable (modo sin base de datos, sección 7).
7. Conectando con módulos de E/S — 15 s (antes "Conectando con la tarjeta"). El handshake del protocolo serial queda sin objeto con Modbus TCP; el criterio se conserva: ningún ciclo ni salida hasta tener las E/S verificadas en estado seguro. Las condiciones de falla se redefinen en la capa de E/S abstracta (secciones 6 y 7 del documento hermano, que sobreviven al cambio de medio).
8. Verificando sensores — 10 s tras la conexión. Criterios en la sección 6.
9. Preparando interfaz — 10 s. Bloqueante: `es.json` ausente o inválido. Degradable: imágenes de botones. Informativo: fuentes.

Comportamiento ante resultado:
- Bloqueante: el splash muestra el nombre del proceso que falló y un código; no avanza. Cuando el flujo sea reintentable (tarjeta, sensores), reintenta automáticamente.
- Degradable: aviso breve y continúa; si aplica, queda alarma persistente.
- Informativo: se registra y continúa.
- Falla del ticket de arranque o del heartbeat: informativo.

Interfaz del splash:
- Barra de progreso determinada y nombre de la etapa. Animación del logo de Especifika en QML puro (fade y leve escalado), sin lógica pesada en el hilo de UI. Si el logo es SVG, respetar las restricciones de assets documentadas en `engineering-principles`.
- La pantalla de espera (reloj) sigue siendo la que aparece al terminar.
- Hallazgo ARR-03 [Medio]: las dos esperas de 40 s encadenadas (U9 y U10) del arranque actual se eliminan; cada etapa tiene su propio timeout y resultado.

## 5. Clasificación de fallos de arranque (aprobada)

Bloqueante:
- Perfil de instalación inválido; reloj alterado.
- Calibración ausente, corrupta o que no pasa la validación.
- `global_params.json` ilegible; ciclo por defecto inexistente.
- Backend que no abre el puerto; puerto ocupado.
- `es.json` ausente o inválido.
- Canal de sensor crítico inválido (sección 6).

Degradable (continúa con aviso):
- Base de datos no disponible.
- Un ciclo individual corrupto.
- Imágenes de botones que no cargan.
- Sensores no críticos con falla.

Informativo: fuentes ausentes, ticket de arranque, escritura del heartbeat.

Sin tarjeta o con handshake fallido: ver D-02 en el documento hermano.

## 6. Verificación de sensores

Hardware informado: temperatura con PT100 y convertidor 0-10 V; presión con transmisores 4-20 mA; la tarjeta convierte internamente ambas señales (entradas directas a la tarjeta).

Hallazgos:
- SEN-01 [Alto] `ERROR_AI_*` nunca detecta un canal de temperatura abierto: un abierto produce `None` y `None == 0` es falso, de modo que la alarma se limpia. Además el criterio `raw == 0` es frágil con el promedio de 64 muestras.
- SEN-02 [Alto] Presión: `converters.py` recorta a `max(0.0, valor)`, así que un mínimo en el valor convertido nunca dispara; un transmisor abierto lee 0.0 y un corto a VCC lee unos 400 kPa o más sin alarma. Que un lazo abierto sea distinguible de la presión mínima depende del comportamiento de la tarjeta fuera de 4-20 mA y está pendiente de prueba de banco.
- SEN-03 [Alto] `evaluar_banda()` compara `None < float` sin protección: con `temp_drenaje = None` lanza `TypeError` en cada tick y el tick se interrumpe antes de F0, `cycle_logger` y buzzer.
- SEN-04 [Medio] Con 0-10 V, un PT100 abierto o en corto da 0 V en ambos casos (informado por Cristian); ambos se detectan por crudo bajo, pero no se distinguen entre sí.
- SEN-05 [Medio] No existe ningún rango de plausibilidad de ingeniería aplicado a las lecturas; los umbrales actuales son los de proceso de cada fase.

Especificación:
- Una sola función `validar_canal()` usada tanto en el arranque como en la supervisión continua, para que ambos criterios no diverjan.
- Criterios por canal: (a) valor distinto de `None`; (b) crudo dentro de umbrales por canal (en configuración; valores pendientes de medición); (c) valor convertido dentro de `[mín − 5 % del span, máx + 5 % del span]`, con el rango de `calibration.yaml` de fábrica (±10 °C en temperatura y ±20 kPa en presión como valores iniciales); (d) 3 tramas consecutivas válidas.
- El 5 % debe validarse contra el histórico de la tabla `lecturas` (mínimos y máximos observados por canal), porque las calibraciones de usuario actuales aplican correcciones grandes.
- La verificación de crudo es la única útil como límite inferior en presión (por el recorte).
- La trama `ST:` aporta `ai_inv` (canales con muestra descartada) y `pcf_ok` (documento hermano); un canal con `ai_inv` activo es inválido.
- Corregir SEN-01 (tratar `None` como falla) y SEN-03 (`None` como falla explícita) como parte de esta fase.

Clasificación aprobada:
- Bloqueante: `temp_camara`, `pres_camara`, `pres_chaqueta`, `temp_drenaje`; llegada de la trama `DI:` junto con `paro_emergencia` y `suministro_electrico`.
- Bloqueante si el equipo tiene puerta con empaque: `pres_empaque_1` y `pres_empaque_2`.
- Bloqueante solo si F0 está activo: `temp_2_camara`.
- Degradable con aviso: `temp_ref`, `temp_chaqueta`, `temp_drenaje_cam` y canales sin nombre (temperatura 6 y 7; presión AI12 a AI15).
- Atención: hoy `ERROR_AI_*` ya impide pasar a "listo" por cualquiera de los seis canales de temperatura; esta fase decide si los tres degradables siguen bloqueando ese paso. Supuesto D-06: no bloquean (solo avisan).

Pendiente (diferido): prueba de banco. Procedimiento: usar `tools/log_calibracion_sensores.py` (necesita el puerto libre; no corre junto al backend) con una etiqueta por condición (`reposo`, `pt100_abierto`, `pt100_corto`; en presión, `lazo_0mA`, `lazo_3_6mA`, `lazo_4mA`, `lazo_20mA`, `lazo_21mA` si hay calibrador de lazo), mínimo 20 tramas por canal y condición, con el equipo en reposo y las salidas en OFF.

## 7. Modo sin base de datos

Contexto (reporte de Code): el arranque es el único punto donde una falla de la base impide operar; además `CycleLogger` no está protegido dentro del tick y, si la base falla en pleno ciclo, apaga el buzzer y se pierde el registro sin aviso.

Hallazgos:
- BD-01 [Crítico] Si `autoclave.db` no abre o está corrupta, el backend no arranca (ni `ControlLoop` ni control del equipo).
- BD-02 [Alto] `crear_ciclo`, `cerrar_ciclo` e `insertar_lectura` sin protección dentro del tick; un fallo detiene el resto del tick, apaga el buzzer y deja `_activo` en falso reintentando en cada tick.
- BD-03 [Alto] Auditoría de calibración no atómica: la calibración se escribe, se confirma en git y se recarga antes de auditar; si la auditoría falla, queda activa sin registro.
- BD-04 [Alto] Consecutivo `MAX(numero)+1`: se repite si la base se borra o se reemplaza (TODO MP-06a), el índice no es UNIQUE y los ciclos interrumpidos quedan con `fecha_fin` NULL sin cierre.
- BD-05 [Medio] El número de programa no se guarda en `ciclos`; si se renumera o se borra el programa, el historial muestra otro número o `None`.
- BD-06 [Medio] Si se recrea una base vacía se siembra `admin`/`admin1234` (hallazgo 7 de Code).

Especificación:

7.1 Estados. Estado de base: OK o DEGRADADA, expuesto por el backend (`/db/estado`) y consultable por las UI. En DEGRADADA hay alarma persistente `OPERANDO_SIN_BD` (supuesto D-03: severidad ALERTA no bloqueante), visible en pantalla y en el ticket.

7.2 Arranque. El backend arranca aunque la base falle. Reintentos acotados ante bloqueo transitorio (3 reintentos, etapa de 5 s).

7.3 `CycleLogger` protegido. Cada acceso a la base va dentro de `try/except` y degrada al respaldo. Esto elimina la pérdida del buzzer (BD-02).

7.4 Respaldo por ciclo. Archivo de solo-anexar por ciclo en `data/respaldo_ciclos/<uuid>.jsonl`, con encabezado, lecturas y cierre (con motivo), `flush` y `os.fsync` en cada escritura. Si la escritura en disco también falla: alarma y el ciclo continúa. La impresión de ticket en tiempo real no depende de la base y debe imprimir siempre. Al recuperar la base, reimportación idempotente usando el UUID como clave.

7.5 Numeración (aprobada).
- Contador consecutivo persistente en `data/ciclo_contador.json`, con escritura atómica (archivo temporal, `fsync` y `os.replace`), incrementado al iniciar el ciclo. Es la fuente única en ambos modos (con y sin base), por lo que no hay colisiones al reimportar y no se usa prefijo para ciclos de contingencia (supuesto D-07).
- Al arrancar se sincroniza con `max(contador, MAX(numero))`.
- UUID por ciclo, generado al inicio: clave de idempotencia en la reimportación; no es el número visible del operador.
- Índice UNIQUE sobre `numero`. Migración no destructiva: antes de crearlo, verificar duplicados existentes; si los hay, reportarlos y no crear el índice automáticamente.
- Instantánea del programa por ciclo: guardar al iniciar el número y nombre del programa (nuevas columnas en `ciclos` y campos en el respaldo).
- Ciclos interrumpidos: al arrancar, todo ciclo con `fecha_fin` NULL se marca como `interrumpido` (motivo propio, registrado en la base o, si está degradada, en el respaldo).

7.6 Login sin base (aprobado).
- Las UI abren su propia conexión a la base para el login; en modo DEGRADADA el login no puede validar.
- La pantalla informa que la base no está disponible y ofrece "Continuar sin operador". El ciclo se registra y se imprime como `SIN OPERADOR / SIN BD`.
- Al iniciar cada ciclo en este modo se pide confirmación explícita ("Continuar sin registro").
- Restricciones en este modo: sin acceso a calibración, parámetros de ciclo, alta de usuarios y Opciones, porque todas dependen de una auditoría en base de datos. Permisos mínimos: iniciar ciclo y consultar estado; el mapeo al esquema de roles se confirma al implementar (ver `decisiones-roles-y-programas`).
- BD-03 se corrige igualmente: la calibración no se activa si no se puede registrar la auditoría (rollback).

7.7 Base corrupta. No se borra ni se sobrescribe: se renombra a `autoclave.db.corrupta-<fecha>`. No se recrea automáticamente: una marca en `data/` (p. ej. `BD_BLOQUEADA`) impide crear la base y sembrar `admin` hasta la intervención de un técnico (BD-06).

7.8 Custodia (D-01 resuelta: opción B). El backend es el único custodio de la base de datos. Login, consulta y alta de usuarios y cualquier otra operación sobre `autoclave.db` pasan por endpoints del backend; las UI (PySide y QML) dejan de abrir `DbManager`. Consecuencias:
- El backend expone `/db/estado` y los endpoints de autenticación y de usuarios.
- La pantalla de login decide el modo sin base según `/db/estado` (7.6).
- Los trabajos en curso que acceden a `DbManager` desde la UI (Nuevo usuario, OPCIONES) deben migrar a esos endpoints.
- Endurecimiento obligatorio al pasar credenciales por HTTP: el backend escucha solo en 127.0.0.1 (hallazgo H-03: hoy escucha en todas las interfaces), sin registrar contraseñas ni hashes en los logs.
- El alcance de la autorización por rol en los endpoints de usuarios y calibración se define tras el inventario de Code (fase B, paso 0).

## 8. Retiro del ejecutable viejo (tkinter)

Orden obligatorio, para no eliminar funciones que aún no tienen equivalente:
1. Code entrega un inventario de solo lectura de lo eliminable: dependencias de `tkinter` y `customtkinter`, `AutoclaveUI.spec`, `main.py` y lo que solo ellos usan.
2. Etiqueta de git sobre el commit actual de `dev` antes de borrar.
3. Eliminación cuando las funciones migradas (sección 3) existan en el arranque nuevo: verificación de perfil y reloj, asistente de instalación, ticket, heartbeat y limpieza de backend huérfano.

## 9. Orden de implementación sugerido

Cada fase termina con la confirmación visual de Cristian antes del commit.

1. Fase A (pausada): A1 y A2 implementados en el PC y respaldados en la rama `feat/serial-v2-wip`; el resto se reemplaza por la capa de E/S abstracta (Modbus TCP) cuando lleguen los módulos M31-U.
2. Fase B (backend): arranque por etapas con endpoint de estado, `CycleLogger` protegido, respaldo, contador, UNIQUE, instantánea de programa y marcado de ciclos interrumpidos.
3. Fase C (sensores): `validar_canal()`, SEN-01 y SEN-03, umbrales en configuración.
4. Fase D (interfaz): splash en QML y pantalla de login en modo sin base.
5. Fase E (limpieza): retiro de tkinter (sección 8).

## 10. Riesgos para ISO 14971

- R-ARR-01: ciclo ejecutado sin registro en base (trazabilidad de esterilización). Mitigación: respaldo JSONL, impresión en tiempo real, alarma persistente.
- R-ARR-02: ciclo sin operador identificado. Mitigación: confirmación explícita por ciclo, leyenda en ticket y respaldo, restricciones del modo.
- R-ARR-03: número de ciclo repetido o salteado. Mitigación: contador persistente y UNIQUE.
- R-ARR-04: arranque con sensor crítico en falla no detectada. Mitigación: `validar_canal()` con supervisión continua; riesgo residual en presión hasta la prueba de banco (lazo abierto posiblemente indistinguible de presión mínima).
- R-ARR-05: base recreada con usuario `admin` por defecto. Mitigación: marca `BD_BLOQUEADA`.

## 11. Supuestos y decisiones por confirmar

- D-01: RESUELTA el 2026-10-07, opción B (backend único custodio, sección 7.8).
- D-02: sin tarjeta (documento hermano, sección 10).
- D-03: severidad de `OPERANDO_SIN_BD` como ALERTA no bloqueante.
- D-04: relanzado de UI cerrada por el lanzador (3 veces, 5 s).
- D-06: sensores no críticos no bloquean el paso a "listo".
- D-07: sin prefijo para ciclos de contingencia.
- Pendiente diferido: prueba de banco de sensores y umbrales de crudo por canal.
- Los informes y respuestas de Code deben venir en español.

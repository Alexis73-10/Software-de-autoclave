# Hoja de pruebas de banco — equipo de pruebas

> Generado desde `docs/mis_plans/hoja_pruebas_banco/pruebas.py` (editar ahí y regenerar con `generar.py`). Versión imprimible: `hoja_pruebas_banco_equipo_pruebas.html`.

- Equipo de pruebas: autoclave de laboratorio, 2 puertas abatibles manuales, generador interno (sin DO1/DO2), sondas Cámara 1, Cámara 2, Referencia y drenaje.
- Origen: tanda 2 (P1, E7). Reúne las 11 comprobaciones manuales de `docs/informes/informe_tanda_2026-10-14.md` §5 y las de la tanda 2 (`docs/informes/tanda2/`).
- Valores de los programas de fábrica (provisionales, por validar aquí): Bowie & Dick 134 °C / 3,5 min; Instrumental 134 °C / 7 min; Instrumental 121 °C / 15 min; Líquidos 121 °C / 15 min, sin prevacío ni secado, descompresión modo 4 con contrapresión hasta 80 °C (Principal).

## Orden seguro de ejecución

1. Bloques A a D en seco, en ese orden: primero se confirma el perfil, la tarjeta y la seguridad sin energía térmica en la cámara.
2. No pasar al bloque E sin haber aprobado B-01 (paro), B-03 (NO ABRIR), B-04 (puertas) y A-04 (DO1/DO2).
3. Bloque E (ciclos normales) antes del F (fallas provocadas): las fallas se provocan solo con un ciclo normal ya aprobado.
4. F-04 (puerta en ciclo) solo durante PREVACIO, nunca con presión positiva.
5. Bloque G (Líquidos) al final y con vidrio real; detener ante cualquier ebullición o rotura.
6. Entre pruebas en operación, esperar a cámara segura (NO ABRIR apagado) antes de manipular la carga.

## Resumen

| ID | Prueba | Modo | Origen |
|---|---|---|---|
| A-01 | Instalación con el asistente QML | En seco (sin vapor) | §5.7; S1 |
| A-02 | Arranque con la tarjeta conectada: ALL_OFF | En seco (sin vapor) | §5.1 (T6) |
| A-03 | Firmware 1.0.0: versión e ID solo en Información del sistema | En seco (sin vapor) | E6; tanda 2 §1 |
| A-04 | DO1/DO2 nunca se encienden (generador interno) | En seco (sin vapor) | S1 |
| A-05 | Ejecutable compilado: engrane, ajustes y cierre limpio | En seco (sin vapor) | B2 (tanda 4) |
| B-01 | Paro de emergencia NC: pulsar, soltar, confirmar | En seco (sin vapor) | §5.2; PF-21; U1 |
| B-02 | Paro NC: cable cortado = paro | En seco (sin vapor) | PF-21 |
| B-03 | NO ABRIR con la cámara no segura (simulado en seco) | En seco (sin vapor) | §5.2 (T4) |
| B-04 | Puertas manuales: un sensor de cerrada por puerta | En seco (sin vapor) | tanda 2; T9 |
| B-05 | Tarjeta desconectada fuera de ciclo | En seco (sin vapor) | §5.10; U4 |
| B-06 | Apagar equipo (solo pantalla 1; cualquier estado salvo ciclo) | En seco (sin vapor) | §5.8; T7; A1 (tanda 3) |
| B-07 | Apagar equipo en FALLA, con paro, sin tarjeta y con la cámara no segura | En seco (sin vapor) | A1 (tanda 3); A2 |
| C-01 | Modo sin base de datos | En seco (sin vapor) | §5.6 (T8); S3 |
| C-02 | Alarmas de la tarjeta fuera de ciclo | En seco (sin vapor) | §5.10 (T1) |
| C-03 | Corte de energía fuera de ciclo y arranque | En seco (sin vapor) | §5.1 (T6) |
| C-04 | Corte de energía abrupto: base y archivos de estado íntegros | En seco (sin vapor) | A2 (tanda 3) |
| D-01 | Roles de sensor: Principal / Referencias / No en uso | En seco (sin vapor) | §5.5 (T3, T12) |
| D-02 | Parámetros: técnico edita en PREPARADO, rechazado en ciclo | En seco (sin vapor) | §5.9 (T10, T12) |
| D-03 | Calibración con límites de plausibilidad | En seco (sin vapor) | S3a |
| D-04 | Pantallas: navegación, campana y legibilidad | En seco (sin vapor) | §5.11; U1; U2 |
| D-05 | Cambio de programa: permitido en FALLA, rechazado con algo en curso | En seco (sin vapor) | S2 |
| D-06 | Próximo mantenimiento: cálculo, registro y aviso | En seco (sin vapor) | M1 (tanda 3) |
| D-07 | Calibración y Entradas/Salidas desde el ejecutable (engrane) | En seco (sin vapor) | C1 (tanda 3); S3a |
| D-08 | Programas de usuario persistentes con el ejecutable | En seco (sin vapor) | C2 (tanda 3) |
| D-09 | Menú Principal sin la tarjeta de secado; CIC-10 indica qué hacer | En seco (sin vapor) | S4; U5 (tanda 3) |
| D-10 | Selector de ciclo en Preciclo | En seco (sin vapor) | B6 (tanda 4) |
| D-11 | Aviso de impresora desconectada al arrancar | En seco (sin vapor) | B5 (tanda 4) |
| D-12 | Caducidad de la sesión por inactividad (5 min) | En seco (sin vapor) | B7 (tanda 4) |
| D-13 | Salida forzada del modo prueba huérfano (ingeniero) | En seco (sin vapor) | B8 (tanda 4) |
| D-14 | Nombre "Parámetros del equipo" | En seco (sin vapor) | B4 (tanda 4) |
| E-01 | Instrumental 134 completo | En operación (vapor) | §5.3 |
| E-02 | Instrumental 121 completo | En operación (vapor) | §5.3; T11 |
| E-03 | SECADO alcanza vacío con la bomba y las válvulas cerradas | En operación (vapor) | T5 §1.6 |
| E-04 | Vigilar el corte por calidad de vapor del calentamiento | En operación (vapor) | CLAUDE.md (calentamiento) |
| E-05 | NO ABRIR en las dos pantallas con la cámara caliente | En operación (vapor) | §5.2 |
| E-06 | Operador del ciclo en ticket, historial y detalle | En operación (vapor) | O1 (tanda 3) |
| F-01 | Paro de emergencia durante el ciclo | En operación (vapor) | B-01 en ciclo |
| F-02 | Pérdida de comunicación durante el ciclo | En operación (vapor) | §5.10 (T1) |
| F-03 | Corte de energía durante el ciclo | En operación (vapor) | §5.1 (T6) |
| F-04 | Puerta abierta durante el ciclo = FALLO | En operación (vapor) | tanda 2 §1 |
| G-01 | Líquidos con la sonda dentro del líquido | En operación (vapor) | §5.4; T11; HAZ-LIQ-01 |
| B-08 | Modo prueba: termina al cerrar su ventana por cualquier camino | En seco (sin vapor) | P1 (tanda 5) |
| C-05 | Arranque con cámara no segura: confirmar estado seguro sin técnico | En seco (sin vapor) | T1 (tanda 5), P-10 |
| D-15 | Interruptor "Impresora habilitada" | En seco (sin vapor) | P2 (tanda 5) |
| D-16 | Ajustes PySide: renovación del token y reingreso tras sesión vencida | En seco (sin vapor) | P3 (tanda 5) |
| D-17 | Parámetros del ciclo: defecto, sensores, entradas y gestión de programas | En seco (sin vapor) | O1 (tanda 5) |
| D-18 | Cambio de unidades: °F y psig/inHg en vacío y en presión | En operación (vapor) | U1 (tanda 5) |
| D-19 | Recorrido en inglés (solo verificación: R-06 sigue vigente) | En seco (sin vapor) | I1, I2, I3 (tanda 5) |
| G-02 | Líquidos: tras confirmar un ciclo completado con presión, se ventea por la LENTA | En operación (vapor) | T1-01 (tanda 5, D-19) |
| A-06 | Estados EMERGENCIA e HIBERNACION retirados: suspensión sigue funcionando | En seco (sin vapor) | T2 P-8 (tanda 6) |
| B-09 | Alarma bloqueante impide iniciar ciclo desde PREPARADO | En seco (sin vapor) | T2 P-4 (tanda 6) |
| B-10 | Cancelar en estados no permitidos responde 409 con motivo | En seco (sin vapor) | T2 P-7 (tanda 6) |
| C-06 | COM-02/COM-03 persisten hasta DESPEJAR en el panel de notificaciones | En seco (sin vapor) | T2 P-5 (tanda 6) |
| D-20 | Ticket de ciclo INTERRUMPIDO dice CARGA NO ESTÉRIL | En seco (sin vapor) | T2 P-9 (tanda 6) |
| D-21 | PySide: teclado en pantalla y reingreso tras sesión vencida | En seco (sin vapor) | C1a (tanda 6) |
| D-22 | Admin ve Parámetros del equipo en solo lectura | En seco (sin vapor) | C1b (tanda 6) |
| D-23 | Unidades: clase de parámetro y chaqueta absoluta en psig | En seco (sin vapor) | C1c, C1d (tanda 6) |
| D-24 | Entradas mostradas en Preciclo, Ciclo en curso y gráfica | En seco (sin vapor) | O3 (tanda 6) |
| D-25 | OPCIONES › Parámetros del equipo: rangos, permisos y aplicación sin reiniciar | En seco (sin vapor) | O2a (tanda 6) |
| D-26 | OPCIONES › Usuarios y operadores | En seco (sin vapor) | O2b (tanda 6) |
| D-26b | Cuentas del sistema Admin e Ingeniero | En seco (sin vapor) | U11 (tanda 11, D11-6) |
| D-27 | OPCIONES › Fecha y hora en solo lectura | En seco (sin vapor) | O2c (tanda 6) |
| D-28 | OPCIONES › Información del sistema | En seco (sin vapor) | O2d (tanda 6) |
| D-29 | OPCIONES › Bitácora de auditoría con filtros | En seco (sin vapor) | O2e (tanda 6) |
| D-30 | Calibración de presión atmosférica: medición aceptada | En seco (sin vapor) | O2f (tanda 6) |
| D-31 | Calibración atmosférica: abortos y rechazos | En seco (sin vapor) | O2f (tanda 6) |
| D-32 | OPCIONES › Conectividad: red, destinatarios y correo de prueba | En seco (sin vapor) | O2g (tanda 6) |
| D-33 | Respaldo y restauración por USB | En seco (sin vapor) | O2h (tanda 6) |
| D-34 | Recorrido completo en inglés | En seco (sin vapor) | I4 (tanda 6) |
| D-35 | PDF de ciclo y consolidado en inglés y en °F/psig | En seco (sin vapor) | I4 (tanda 6) |
| D-36 | Correo de prueba y de ciclo en inglés | En seco (sin vapor) | I4 (tanda 6); O2g |
| E-07 | Reconocer un COMPLETADO con la cámara no segura lleva a estado seguro | En operación (vapor) | T2 P-1 (tanda 6) |
| F-05 | Sonda Principal perdida en ciclo: FALLO con escape solo por la lenta | En operación (vapor) | T2 P-2 (tanda 6) |
| F-06 | Trama de la tarjeta vencida en ciclo: tolerancia de 4 s | En operación (vapor) | T2 P-3 (tanda 6) |
| F-07 | Paro con el ciclo terminando: diálogo de estado seguro al CONFIRMAR | En operación (vapor) | T2 P-6 (tanda 6) |
| G-03 | Líquidos: drenaje a atmosférica por la lenta hasta temp_max_apertura | En operación (vapor) | T2 P-12 (tanda 6) |
| B-11 | PREPARADO: el aire de cámara cierra a los 3 ticks reales | En seco (sin vapor) | Q1 R1-P2 (tanda 7) |
| C-07 | DESPEJAR de COM-02/03 solo con el enlace de vuelta en ok | En seco (sin vapor) | Q1 T2-b (tanda 7); complementa C-06 |
| D-37 | Calentamiento: rango de temperatura y de presión por separado | En seco (sin vapor) | Q1 R1-P3 (tanda 7) |
| D-R8-01 | Reasignación de E/S: solo ingeniero, fuera de ciclo, conflictos rechazados | En seco (sin vapor) | R8 (tanda 8, D8-5.12) |
| D-R8-02 | Reasignar una salida: Vapor cámara de DO 04 a un puerto libre | En seco (sin vapor) | R8 (tanda 8, D8-5.12) |
| D-R8-03 | Reasignar el paro de emergencia: confirmación reforzada y cambio observado | En seco (sin vapor) | R8 (tanda 8, D8-5.12) |
| D-R8-04 | Reasignar una entrada analógica: calibración obligatoria en el puerto nuevo | En seco (sin vapor) | R8 (tanda 8, D8-5.12) |
| D-R8-05 | Restaurar fábrica, respaldo y archivo dañado | En seco (sin vapor) | R8 (tanda 8, D8-5.12) |
| E-R8-01 | Ciclo completo con Vapor cámara y Presión cámara reasignados | En operación (vapor) | R8 (tanda 8, D8-5.12) |
| E-08 | Calentamiento con los rangos separados: sin cambio de comportamiento | En operación (vapor) | Q1 R1-P3 (tanda 7) |
| F-08 | Sin datos de la tarjeta en esterilización: la exposición se alarga | En operación (vapor) | Q1 T2-a (tanda 7) |
| F-09 | CARGA NO ESTÉRIL en todo ciclo que no termine COMPLETADO | En operación (vapor) | Q1 T2-c (tanda 7) |
| F-10 | Principal perdido con el protocolo de fallo ya en marcha: pasa a solo la lenta | En operación (vapor) | Q1 R1-P4 (tanda 7) |
| F-11 | Cancelar durante la tolerancia por DI vencida | En operación (vapor) | Q1 R1-P5 (tanda 7) |
| F-12 | Desconexión total breve de la tarjeta en esterilización: la exposición se alarga y no suma F0 | En operación (vapor) | S2a D8-2.7 (tanda 8) |
| F-13 | Cortes repetidos en una esterilización: falla por comunicación inestable (CIC-11) | En operación (vapor) | S2a D8-2.8 (tanda 8) |
| F-14 | DESPEJAR de COM-02/03 exige tramas DI nuevas, no solo tiempo | En seco (sin vapor) | S2a D8-2.9 (tanda 8) |
| F-15 | Líquidos: se pierde el Principal en el enfriamiento con contrapresión — cámara sellada | En operación (vapor) | S2a D8-2.10 (tanda 8) |
| F-16 | Líquidos sin Referencia: espera sellada sin sonda y luego la lenta | En operación (vapor) | S2a D8-2.10 (tanda 8) |
| B-12 | Salir del modo prueba sin confirmación del apagado de salidas (COM-04) | En seco (sin vapor) | S2b D8-2.11 (tanda 8) |
| B-13 | Paro de emergencia: con el buzzer sonando no se enciende ninguna otra salida | En seco (sin vapor) | B9 D9-9 (tanda 9); HAZ-B9-01 |
| F-17 | Ventana de estabilidad en pausa durante la tolerancia por DI vencida | En operación (vapor) | S2b D8-2.12 (tanda 8) |
| F-18 | Cancelar con la tarjeta totalmente desconectada: texto en pantalla | En operación (vapor) | S2b D8-2.13 y D8-2.15 (tanda 8); complementa F-11 |
| C-08 | Rechazo de DESPEJAR con texto del catálogo | En seco (sin vapor) | S2b D8-2.15 (tanda 8); complementa C-07 |
| F-19 | Reimpresión idéntica al ticket original (avisos del pie) | En operación (vapor) | S2b D8-2.14 (tanda 8) |
| F-20 | CARGA NO ESTÉRIL en la pantalla de resultado | En operación (vapor) | S2b D8-2.16 (tanda 8) |
| D-38 | Transductor de presión sin señal fuera de ciclo: cuentas ADC, «—», alarma propia, inicio bloqueado y NO ABRIR | En seco (sin vapor) | S1 D8-1.1/1.3/1.4 (tanda 8) |
| F-21 | Transductor de presión de cámara sin señal en ciclo: FALLO SEN-04, solo la lenta | En operación (vapor) | S1 D8-1.2 (tanda 8) |
| F-22 | Transductor de presión de chaqueta sin señal en ciclo: FALLO SEN-05, solo la lenta | En operación (vapor) | S1 D8-1.2/1.4 (tanda 8) |
| B-14 | Modo prueba: el aire atmosférico solo abre sin presión en la cámara | En seco (sin vapor) | E1 D8-3.19 (tanda 8) |
| B-15 | Apagar equipo: Windows rechaza el apagado | En seco (sin vapor) | E1 D8-3.21 (tanda 8) |
| D-39 | Canales de Entradas/Salidas según el perfil de instalación | En seco (sin vapor) | E1 D8-3.17 (tanda 8) |
| G-04 | Tipo de carga en Parámetros del ciclo: Líquido arrastra el modo de descompresión | En seco (sin vapor) | V8a D8-5.7 (tanda 8) |
| A-E9-01 | Instalación limpia de la D: modo de descompresión 5 en los 4 programas y entrega sin datos del banco | En seco (sin vapor) | E9 D9-8 (H14) y D9-7 (H17) (tanda 9) |
| A-E9-02 | Actualización B → D con el Setup, sin copiar archivos a mano | En seco (sin vapor) | E9 D9-13.1 (tanda 9) |
| D-E9-01 | Sin transductores conectados: la presión se muestra «—», nunca 0 | En seco (sin vapor) | E9; H4 resuelto en S1 D8-1.1 (tanda 8) |
| D-E9-02 | Carga Líquido: el modo de descompresión no válido muestra su motivo | En seco (sin vapor) | E9; H13 resuelto en D8-5.7/5.8 (tanda 8) |
| D-E9-03 | Entradas/Salidas solo con los canales del perfil (equipo sin sensores) | En seco (sin vapor) | E9; H16 resuelto en D8-3.17 (tanda 8) |
| D-X9-01 | Cambio de un parámetro con el ciclo en curso: bitácora antes de aplicar | En operación (o planta simulada) | X9 D9-13.3 (tanda 9); HAZ-X9-01 |
| D-X9-02 | Interfaz en inglés: ticket, reimpresión y motivo de fallo en inglés | En seco (sin vapor) | X9 D9-13.4 (tanda 9); HAZ-X9-02 |

## Bloque A. Arranque, instalación y firmware (en seco)

### A-01 — Instalación con el asistente QML

- **Modo:** En seco (sin vapor)  ·  **Origen:** §5.7; S1
- **Objetivo:** El perfil del equipo de pruebas queda con la fuente de vapor correcta y bloqueado.
- **Precondiciones:** Sin `installation_profile.json` (o apartado). Tarjeta conectada.
- **Pasos:**
  1. Arrancar el software.
  2. Verificar que la pantalla de la puerta 1 abre el asistente de instalación.
  3. Elegir tipo de equipo, tipo de puerta, fuente de vapor = Generador interno.
  4. En el paso de suministros, desmarcar las entradas que el banco NO tiene cableadas (DI9 agua del generador, DI12 presostato de vapor, etc.).
  5. Terminar y reiniciar el equipo.
- **Resultado esperado:** El perfil se escribe con `vapor_source = generator` y `locked = true`. El resumen indica si hay cerrojo. Tras reiniciar, arranca normal.
- **Criterio de aprobado/fallo:** Aprobado si `installation_profile.json` tiene `vapor_source: "generator"`, `locked: true` y las entradas de suministro coinciden con el cableado real.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### A-02 — Arranque con la tarjeta conectada: ALL_OFF

- **Modo:** En seco (sin vapor)  ·  **Origen:** §5.1 (T6)
- **Objetivo:** Al conectar con la tarjeta, todas las salidas quedan apagadas.
- **Precondiciones:** Equipo apagado, tarjeta conectada por USB.
- **Pasos:**
  1. Encender el PC y el software.
  2. Observar los LED/relés de salida de la tarjeta durante el arranque.
- **Resultado esperado:** Ninguna salida se enciende durante el arranque; la barra de arranque termina.
- **Criterio de aprobado/fallo:** Aprobado si ninguna salida se activa hasta que el equipo lo pida.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### A-03 — Firmware 1.0.0: versión e ID solo en Información del sistema

- **Modo:** En seco (sin vapor)  ·  **Origen:** E6; tanda 2 §1
- **Objetivo:** La versión y el ID de la tarjeta se ven solo en Información del sistema.
- **Precondiciones:** Tarjeta con firmware 1.0.0 conectada.
- **Pasos:**
  1. Abrir Menú Principal › Información.
  2. Revisar la preciclo y el ciclo en curso.
- **Resultado esperado:** Información muestra versión 1.0.0 y el ID único de la tarjeta, y si está emparejada. Las demás pantallas no los muestran.
- **Criterio de aprobado/fallo:** Aprobado si versión e ID son correctos y aparecen solo ahí.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### A-04 — DO1/DO2 nunca se encienden (generador interno)

- **Modo:** En seco (sin vapor)  ·  **Origen:** S1
- **Objetivo:** Con generador interno, el software no usa DO1 ni DO2.
- **Precondiciones:** Perfil con `vapor_source = generator`. Sesión de técnico.
- **Pasos:**
  1. Activar el modo prueba.
  2. Intentar encender DO1 (vapor_generador) y DO2 (vapor_caldera).
  3. Revisar el log de arranque.
- **Resultado esperado:** Ambos rechazados: "Esta salida de fuente de vapor no la usa este equipo". El log dice "salidas deshabilitadas: DO1, DO2".
- **Criterio de aprobado/fallo:** Aprobado si DO1/DO2 no se activan físicamente en ningún momento.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### A-05 — Ejecutable compilado: engrane, ajustes y cierre limpio

- **Modo:** En seco (sin vapor)  ·  **Origen:** B2 (tanda 4)
- **Objetivo:** El .exe (con `scipy` ya incluido) abre el menú de ajustes y se cierra sin dejar procesos.
- **Precondiciones:** `pyinstaller --noconfirm Autoclave.spec` ya ejecutado; `dist\Autoclave\Autoclave.exe` en el equipo.
- **Pasos:**
  1. Abrir el engrane: debe aparecer el menú de ajustes (ventana PySide) sin cierre inmediato.
  2. Iniciar sesión como técnico/ingeniero y abrir Calibración (lee valores; guardar uno normal).
  3. Entradas/Salidas: ver tarjetas de DI/DO/temperatura/presión con valores.
  4. Probar un login incorrecto (mensaje, sin sesión) y uno correcto.
  5. Cerrar el menú y el programa: en el Administrador de tareas no queda `Autoclave.exe` y el puerto 8000 se libera.
- **Resultado esperado:** Las 5 comprobaciones pasan; si el menú no abre, revisar que `scipy` no esté en `excludes` del spec.
- **Criterio de aprobado/fallo:** Aprobado si el engrane abre y todo cierra limpio.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### A-06 — Estados EMERGENCIA e HIBERNACION retirados: suspensión sigue funcionando

- **Modo:** En seco (sin vapor)  ·  **Origen:** T2 P-8 (tanda 6)
- **Objetivo:** El retiro de estados muertos no rompe arranque, suspensión ni paro.
- **Precondiciones:** PREPARADO, sin ciclo.
- **Pasos:**
  1. Arrancar y llegar a PREPARADO.
  2. Dejar el equipo inactivo hasta que entre en suspensión; tocar para salir.
  3. Pulsar el paro de emergencia y liberarlo.
- **Resultado esperado:** Ningún estado EMERGENCIA/HIBERNACION aparece en pantalla ni en `/status`; la suspensión entra y sale (bitácora `suspension_entra`/`suspension_sale`); el paro se maneja como siempre.
- **Criterio de aprobado/fallo:** Aprobado si no hay estados desconocidos ni errores en el log.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

## Bloque B. Seguridad en seco: paro, puertas, NO ABRIR, alarmas

### B-01 — Paro de emergencia NC: pulsar, soltar, confirmar

- **Modo:** En seco (sin vapor)  ·  **Origen:** §5.2; PF-21; U1
- **Objetivo:** El paro detiene todo, se ve en las dos pantallas y exige confirmación para el estado seguro.
- **Precondiciones:** PREPARADO, cámara fría y a presión atmosférica, sin sesión.
- **Pasos:**
  1. Pulsar el paro.
  2. Observar las dos pantallas (preciclo, menú, login).
  3. Soltar el paro.
  4. Pulsar "Confirmar y llevar a estado seguro" sin iniciar sesión.
  5. Esperar a que termine.
- **Resultado esperado:** Con paro: todas las salidas apagadas, alarma de paro en rojo, campana con insignia roja. Al soltar: aviso naranja y botón azul, insignia parpadeando. Al confirmar: "En curso…" y luego vuelve a PREPARACION/PREPARADO.
- **Criterio de aprobado/fallo:** Aprobado si el paro se ve sin buscarlo en las dos pantallas, el botón funciona sin sesión y no queda ninguna salida encendida durante el paro.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### B-02 — Paro NC: cable cortado = paro

- **Modo:** En seco (sin vapor)  ·  **Origen:** PF-21
- **Objetivo:** Con lógica invertida, un cable del paro desconectado se trata como paro.
- **Precondiciones:** PREPARADO.
- **Pasos:**
  1. Desconectar el cable de la entrada del paro (DI10) en la bornera.
  2. Reconectar.
- **Resultado esperado:** Desconectado = paro activo (igual que B-01).
- **Criterio de aprobado/fallo:** Aprobado si el cable abierto produce paro.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### B-03 — NO ABRIR con la cámara no segura (simulado en seco)

- **Modo:** En seco (sin vapor)  ·  **Origen:** §5.2 (T4)
- **Objetivo:** El aviso NO ABRIR y el bloqueo de puerta dependen de la cámara segura.
- **Precondiciones:** Cámara fría. Si es posible, calentar el sensor Principal con una fuente controlada (baño o pistola de calor) por encima de `temp_max_apertura` (100 °C; 80 °C en Líquidos).
- **Pasos:**
  1. Calentar el sensor Principal.
  2. Abrir el panel de la campana en las dos pantallas.
  3. Intentar abrir la puerta desde la UI.
  4. Dejar enfriar.
- **Resultado esperado:** Fila "NO ABRIR" con el motivo en el panel; la puerta no se abre desde la UI. Al enfriar, desaparece.
- **Criterio de aprobado/fallo:** Aprobado si nunca se permite abrir con el Principal caliente.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### B-04 — Puertas manuales: un sensor de cerrada por puerta

- **Modo:** En seco (sin vapor)  ·  **Origen:** tanda 2; T9
- **Objetivo:** Cada puerta abatible manual se lee con su único sensor de cerrada.
- **Precondiciones:** PREPARADO.
- **Pasos:**
  1. Abrir y cerrar a mano la puerta 1; luego la puerta 2.
  2. Observar el estado de cada puerta en su pantalla.
- **Resultado esperado:** Cada pantalla refleja su puerta (abierta/cerrada) sin cruzarlas. Con cualquier puerta abierta no se puede iniciar ciclo.
- **Criterio de aprobado/fallo:** Aprobado si los estados coinciden con la realidad y bloquean el inicio.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### B-05 — Tarjeta desconectada fuera de ciclo

- **Modo:** En seco (sin vapor)  ·  **Origen:** §5.10; U4
- **Objetivo:** Desconectar el USB no se confunde con un paro y deja el equipo en estado seguro.
- **Precondiciones:** PREPARADO.
- **Pasos:**
  1. Desconectar el USB de la tarjeta.
  2. Observar alarmas y campana.
  3. Reconectar.
- **Resultado esperado:** FALLA recuperable con "Tarjeta de E/S desconectada" (no "paro de emergencia"); NO ABRIR activo; sin inicio de ciclo. Al reconectar vuelve sin pedir confirmación de estado seguro (si nunca hubo paro real).
- **Criterio de aprobado/fallo:** Aprobado si no se muestra un paro falso y el equipo se recupera solo al reconectar. (Depende de U4.)
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### B-06 — Apagar equipo (solo pantalla 1; cualquier estado salvo ciclo)

- **Modo:** En seco (sin vapor)  ·  **Origen:** §5.8; T7; A1 (tanda 3)
- **Objetivo:** El apagado está disponible solo desde la puerta 1 y se permite en cualquier estado salvo ciclo en curso, con aviso si la cámara no es segura.
- **Precondiciones:** PREPARADO (luego repetir en FALLA). Instalado con el ejecutable, o `AUTOCLAVE_APAGADO_REAL=1`.
- **Pasos:**
  1. Desde la puerta 2, buscar "Apagar equipo".
  2. Desde la puerta 1, Información del equipo › Apagar equipo, cancelar en la confirmación.
  3. Iniciar un ciclo corto e intentar Apagar equipo.
  4. Cancelar el ciclo y, ya en FALLA o PREPARADO, Apagar equipo y confirmar.
- **Resultado esperado:** Puerta 2: no disponible. Puerta 1: pide confirmación; durante el ciclo, rechazado (hay que cancelar antes). Fuera de ciclo: salidas apagadas, bitácora `apagar_equipo` (estado, cámara segura, tarjeta), base cerrada y Windows se apaga.
- **Criterio de aprobado/fallo:** Aprobado si solo apaga desde la puerta 1, nunca en ciclo, y la bitácora registra el estado y la condición de la cámara.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### B-07 — Apagar equipo en FALLA, con paro, sin tarjeta y con la cámara no segura

- **Modo:** En seco (sin vapor)  ·  **Origen:** A1 (tanda 3); A2
- **Objetivo:** El personal técnico puede dejar el equipo fuera de servicio aunque haya una falla, el paro esté pulsado o no haya tarjeta; el siguiente arranque es normal.
- **Precondiciones:** Sin ciclo en curso. Probar cada condición por separado: (a) FALLA recuperable (p. ej. USB desconectado); (b) paro de emergencia pulsado; (c) tarjeta desconectada; (d) cámara no segura (si se puede, con la cámara caliente, p. ej. tras E-01).
- **Pasos:**
  1. Provocar la condición.
  2. En la puerta 1, Información del equipo › Apagar equipo.
  3. Con la cámara no segura, leer el aviso del diálogo y confirmar.
  4. Tras el apagado, volver a encender el PC y el software.
- **Resultado esperado:** Con la cámara no segura el diálogo avisa "NO ABRIR… no abra las puertas". En todos los casos el equipo se apaga. Al encender, arranca normal (estado seguro o confirmación si la cámara no es segura) sin intervención técnica.
- **Criterio de aprobado/fallo:** Aprobado si ninguna condición impide el apagado, no se abre ninguna puerta ni válvula por el apagado y el arranque siguiente es normal.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### B-08 — Modo prueba: termina al cerrar su ventana por cualquier camino

- **Modo:** En seco (sin vapor)  ·  **Origen:** P1 (tanda 5)
- **Objetivo:** Ninguna salida queda encendida al abandonar Entradas/Salidas.
- **Precondiciones:** PREPARADO, técnico con sesión, cámara fría y a presión atmosférica.
- **Pasos:**
  1. Entrar al modo prueba y encender una salida inocua (p. ej. una luz piloto o la bomba sin agua solo 1 s).
  2. Salir con Atrás: la salida se apaga.
  3. Repetir saliendo por: otra entrada del cajón, Inicio, el engranaje (Menú principal) y Cerrar sesión.
  4. Repetir dejando la sesión inactiva hasta que se cierre sola (5 min).
  5. Repetir cerrando la aplicación (Salir) con la salida encendida.
  6. Repetir desconectando el cable de red/USB del PC de la UI si es una UI aparte (el backend la apaga a ≤ 90 s).
- **Resultado esperado:** En todos los caminos la salida se apaga en ≤ 1 s (≤ 2 s por el vigilante si la sesión ya no vale; ≤ 90 s si la UI desaparece). Auditoría `modo_prueba_sale` con el motivo.
- **Criterio de aprobado/fallo:** Aprobado si en ningún camino la salida sigue encendida más de lo indicado.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### B-09 — Alarma bloqueante impide iniciar ciclo desde PREPARADO

- **Modo:** En seco (sin vapor)  ·  **Origen:** T2 P-4 (tanda 6)
- **Objetivo:** No se inicia un ciclo con alguna alarma bloqueante activa.
- **Precondiciones:** PREPARADO; provocar una alarma bloqueante (p. ej. desconectar la sonda de drenaje).
- **Pasos:**
  1. Intentar iniciar un ciclo.
  2. Quitar la causa, reconocer la alarma e intentar de nuevo.
- **Resultado esperado:** Con la alarma activa, el inicio se rechaza; sin ella, inicia.
- **Criterio de aprobado/fallo:** Aprobado si nunca inicia con alarma bloqueante.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### B-10 — Cancelar en estados no permitidos responde 409 con motivo

- **Modo:** En seco (sin vapor)  ·  **Origen:** T2 P-7 (tanda 6)
- **Objetivo:** CANCELAR no hace nada indebido con resultado pendiente, con paro o fuera de ciclo.
- **Precondiciones:** Ciclo de prueba en seco terminado sin confirmar; luego paro de emergencia pulsado.
- **Pasos:**
  1. Con el resultado pendiente, pulsar Cancelar (o `POST /cycle/abort`).
  2. Con el paro pulsado, repetir.
  3. Fuera de ciclo, repetir.
- **Resultado esperado:** 409 con `resultado_pendiente`, `paro_emergencia` y `estado_no_permitido` respectivamente; no cambia el estado.
- **Criterio de aprobado/fallo:** Aprobado si ningún caso cambia el estado ni deja una cancelación colgada.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### B-11 — PREPARADO: el aire de cámara cierra a los 3 ticks reales

- **Modo:** En seco (sin vapor)  ·  **Origen:** Q1 R1-P2 (tanda 7)
- **Objetivo:** El debounce de apagado del aire atmosférico de cámara cuenta ticks reales (antes avanzaba de a 2).
- **Precondiciones:** PREPARACION/PREPARADO, cámara fría, puertas cerradas; sesión de técnico para ver el log; aire de cámara abierto porque la presión estaba bajo la banda (p. ej. tras un vacío breve en modo prueba y su salida).
- **Pasos:**
  1. Dejar que la presión de cámara vuelva a la banda atmosférica (P_atm ± rango).
  2. Observar el LED/relé de `aire_admosferico_camara` y el log del backend (un tick ≈ 0,5 s).
  3. Anotar cuántos ticks pasan entre la entrada en banda y el cierre.
- **Resultado esperado:** El aire cierra 3 ticks (≈ 1,5 s) después de entrar en banda, no a los 2 ticks; la válvula no oscila en el borde.
- **Criterio de aprobado/fallo:** Aprobado si el cierre ocurre al tercer tick en banda y no hay oscilación.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### B-12 — Salir del modo prueba sin confirmación del apagado de salidas (COM-04)

- **Modo:** En seco (sin vapor)  ·  **Origen:** S2b D8-2.11 (tanda 8)
- **Objetivo:** Si la tarjeta no confirma el apagado de todas las salidas al salir del modo prueba, se reintenta 3 veces y, si sigue sin confirmar, sale la alarma "Salidas sin confirmar" y no se puede iniciar ciclo.
- **Precondiciones:** PREPARADO, sesión de técnico, modo prueba activo con una salida segura encendida.
- **Pasos:**
  1. Salir del modo prueba con normalidad: anotar en la bitácora el evento de salida con el apagado confirmado.
  2. Volver a entrar al modo prueba; desconectar el USB de la tarjeta y salir del modo prueba enseguida.
  3. Observar el panel de notificaciones e intentar iniciar un ciclo.
  4. Reconectar la tarjeta y esperar a que se complete la conexión.
- **Resultado esperado:** Paso 1: sin alarma. Paso 3: alarma COM-04 "Salidas sin confirmar"; el inicio de ciclo queda bloqueado. Paso 4: al completarse la conexión (o un apagado confirmado) la alarma se despeja y el inicio vuelve a estar permitido.
- **Criterio de aprobado/fallo:** Aprobado si con la tarjeta sin confirmar nunca se permite iniciar ciclo.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### B-13 — Paro de emergencia: con el buzzer sonando no se enciende ninguna otra salida

- **Modo:** En seco (sin vapor)  ·  **Origen:** B9 D9-9 (tanda 9); HAZ-B9-01
- **Objetivo:** Con el paro pulsado solo conmuta el buzzer (DO24); ninguna salida que estuviera activa al pulsar el paro se enciende, ni un instante, cuando el buzzer reinicia su patrón. Fuera del paro, el buzzer no altera las demás salidas.
- **Precondiciones:** Anotar el tipo de puerta del perfil (Información del sistema o `installation_profile.json`: simple o avanzada) y la versión de firmware (debe ser 1.0.0). PREPARACION o PREPARADO. Mirar los LED de la tarjeta de salidas (o un multímetro en las bornas). Lista de salidas a observar: DO3 vapor de chaqueta, DO4 vapor de cámara, DO5 descompresión rápida, DO6 descompresión lenta, DO7 descompresión de chaqueta, DO8 vacío de cámara, DO9/DO10 desbloqueo de puerta 1/2, DO11/DO12 bloqueo de puerta 1/2, DO13 libre (sin función desde la tanda 11; debe seguir siempre apagada), DO14 aire comprimido de cámara, DO15 aire atmosférico de cámara, DO16 agua de chaqueta, DO17 agua del intercambiador, DO18 agua de la bomba, DO19 bomba de vacío, DO20/DO21 abrir puerta 1/2, DO22/DO23 cerrar puerta 1/2, y DO24 buzzer (canal según la asignación de E/S vigente).
- **Pasos:**
  1. Con el modo prueba (técnico), encender 3 o 4 salidas seguras de la lista (p. ej. DO6, DO15, DO17) y salir del modo prueba; o dejar que el estado encienda las suyas (con el perfil de puertas avanzadas, la puerta cerrada mantiene DO22 y, con empaque bajo, DO11). Anotar cuáles quedan encendidas.
  2. Pulsar el paro y mantenerlo 30 s. Observar cada salida de la lista durante al menos 5 repeticiones del patrón del buzzer.
  3. En el log del backend (`logs/`), buscar "paro de emergencia detectado; ALL_OFF inmediato" y, si aparecen, las líneas "DOn no se enciende con el paro de emergencia activo" (indican qué función intentó encender y fue bloqueada).
  4. Soltar el paro y confirmar. Provocar una alarma no bloqueante con buzzer (o el pitido de fin de ciclo) con alguna salida encendida y observar que esa salida no cambia mientras suena el buzzer.
- **Resultado esperado:** Paso 2: al pulsar, todas las salidas se apagan de inmediato; durante el paro solo parpadea DO24; ninguna otra salida de la lista se enciende ni un instante. Paso 3: la línea del ALL_OFF inmediato aparece una vez por pulsación. Paso 4: el buzzer conmuta solo su canal.
- **Criterio de aprobado/fallo:** Aprobado si en el paso 2 ninguna salida distinta del buzzer se enciende. Si alguna se enciende: anotar cuál, el tipo de puerta y la versión de firmware, y guardar el log (si el log NO muestra órdenes de encendido para ese canal, la causa está en la tarjeta o el cableado, no en el PC: ver B9_buzzer_paro.md).
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

## Bloque C. Comunicación, energía y base de datos (en seco)

### C-01 — Modo sin base de datos

- **Modo:** En seco (sin vapor)  ·  **Origen:** §5.6 (T8); S3
- **Objetivo:** Sin base, el equipo opera con respaldo JSONL, alarma y confirmación por ciclo.
- **Precondiciones:** Copia de seguridad de la base. Reemplazar la base por un archivo que no sea SQLite.
- **Pasos:**
  1. Arrancar.
  2. Verificar la marca BD_BLOQUEADA y la alarma "Operando sin base de datos".
  3. Iniciar un ciclo corto (o B&D en seco si el banco lo permite) y confirmar "Continuar sin registro".
  4. Restaurar la base y reiniciar.
- **Resultado esperado:** El ciclo pide confirmación; el ticket imprime "SIN OPERADOR / SIN BD"; calibración y parámetros bloqueados. Al restaurar, el ciclo del respaldo se reimporta.
- **Criterio de aprobado/fallo:** Aprobado si el ciclo queda en el ticket, en `data/respaldo_ciclos/` y después en la base.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### C-02 — Alarmas de la tarjeta fuera de ciclo

- **Modo:** En seco (sin vapor)  ·  **Origen:** §5.10 (T1)
- **Objetivo:** Pérdida de comunicación fuera de ciclo = FALLA recuperable.
- **Precondiciones:** PREPARADO.
- **Pasos:**
  1. Desconectar el USB en PREPARADO.
  2. Reconectar.
- **Resultado esperado:** FALLA recuperable con la causa; al reconectar vuelve a PREPARADO.
- **Criterio de aprobado/fallo:** Aprobado si se recupera sin reiniciar el software.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### C-03 — Corte de energía fuera de ciclo y arranque

- **Modo:** En seco (sin vapor)  ·  **Origen:** §5.1 (T6)
- **Objetivo:** El arranque tras un corte deja todo apagado y pide confirmación si la cámara no es segura.
- **Precondiciones:** PREPARADO.
- **Pasos:**
  1. Cortar la energía del PC y la tarjeta.
  2. Restaurar y arrancar.
- **Resultado esperado:** ALL_OFF al conectar; si la cámara no es segura, el estado seguro pide confirmación.
- **Criterio de aprobado/fallo:** Aprobado si ninguna salida se enciende sola tras el corte.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### C-04 — Corte de energía abrupto: base y archivos de estado íntegros

- **Modo:** En seco (sin vapor)  ·  **Origen:** A2 (tanda 3)
- **Objetivo:** Sin UPS, un corte (incluso mientras se escribe) no daña la base ni los archivos de estado.
- **Precondiciones:** PREPARADO, con al menos un ciclo en el historial. Copia de seguridad de `data/`.
- **Pasos:**
  1. Cortar la energía del PC con el interruptor (sin apagar), durante una calibración o un cambio de parámetro.
  2. Restaurar y arrancar.
  3. Revisar Historial, la calibración y `data/` (sin archivos `.tmp` pendientes).
- **Resultado esperado:** Arranca sin avisos de base corrupta; el historial está completo hasta el último ciclo cerrado; la calibración y los parámetros están íntegros (la versión anterior o la nueva, nunca truncados).
- **Criterio de aprobado/fallo:** Aprobado si la base abre (sin BD_BLOQUEADA), la calibración se lee y el contador de ciclos sigue consecutivo.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### C-05 — Arranque con cámara no segura: estado seguro automático, sin confirmación

- **Modo:** En seco (sin vapor)  ·  **Origen:** T1 (tanda 5), P-10; cambiado por S9 D9-1.1/1.2 (tanda 9: ya no se pide confirmación al arrancar)
- **Objetivo:** Tras un corte con la cámara caliente, el equipo lleva la cámara a seguro SOLO, sin confirmación ni rol técnico.
- **Precondiciones:** Simular cámara no segura al arrancar (sensor Principal calentado > temp_max_apertura) con un ciclo previo interrumpido en la BD (o cortar la energía en pleno ciclo de prueba en seco). Sin pulsar el paro en este encendido.
- **Pasos:**
  1. Arrancar el software.
  2. Observar "NO ABRIR" y el aviso de estado seguro en la tarjeta de alarmas de Preciclo y en la campana.
  3. Verificar que NO aparece el botón "Confirmar y llevar a estado seguro" ni el texto "Paro liberado".
  4. Dejar enfriar.
- **Resultado esperado:** El ciclo previo aparece como INTERRUMPIDO ("la carga NO está estéril"); no se reanuda; el aviso dice «Arranque con la cámara no segura: el equipo la lleva solo a estado seguro, sin confirmación (no hubo paro de emergencia)»; con presión sobre la atmosférica solo abre la lenta (nunca la rápida ni la chaqueta); al quedar segura vuelve a PREPARACION.
- **Criterio de aprobado/fallo:** Aprobado si no se reanuda nada, no se pide confirmación, no dice "paro liberado" y solo abre la lenta.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### C-05b — Arranque sin sensor de presión de cámara: sin bloqueos (H1, H2, H5, H6, H8)

- **Modo:** En seco (sin vapor)  ·  **Origen:** S9 D9-1.1 a 1.5 (tanda 9)
- **Objetivo:** Con el transmisor de presión de cámara desconectado (equipo de pruebas sin sensores), el arranque no deja el equipo bloqueado.
- **Precondiciones:** Lazo del transmisor de presión de cámara desconectado. Paro de emergencia sin pulsar.
- **Pasos:**
  1. Arrancar el software.
  2. Revisar la tarjeta de alarmas de Preciclo y la campana.
  3. Pulsar el avatar e iniciar sesión como técnico; entrar y salir del modo prueba.
  4. Cambiar el programa seleccionado.
  5. Intentar iniciar un ciclo.
  6. Apagar el equipo desde OPCIONES.
- **Resultado esperado:** Sin botón de confirmación ni texto «Paro liberado»; alarmas SEN-06 (presión de cámara sin lectura) y CIC-10 «Estado seguro detenido» con el motivo «Sensor de presión de cámara sin lectura: sin el sensor de presión de cámara no se puede llevar la cámara a estado seguro. Revise la conexión del sensor de presión de cámara o llame a servicio técnico» (texto de la tanda 10, D10-3; ver C-05i); NO ABRIR; ninguna válvula del protocolo abierta. El login, el modo prueba, el cambio de programa y el apagado se permiten; el inicio de ciclo queda rechazado. Revisión ★ SAF-01 (tanda 9): en el modo prueba, sin presión de cámara (o con el estado seguro activo) NO se encienden `abrir_puerta_N` ni `desbloqueo_puerta_N` (mensaje «No se puede desbloquear ni abrir la puerta…»), ni `descompresion_rapida`, `descompresion_chaqueta` ni `vapor_camara` mientras el estado seguro siga activo (mensaje «No se puede encender esta salida: la cámara se está llevando a estado seguro»). **En el equipo de pruebas sin sensores esto impide probar la apertura de puertas desde Entradas / Salidas** (ver C-05g).
- **Criterio de aprobado/fallo:** Aprobado si login, modo prueba, cambio de programa y apagado funcionan y el ciclo no inicia.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### C-05c — Arranque con la cámara en vacío: aire atmosférico, sin confirmación

- **Modo:** En seco (bomba de vacío)  ·  **Origen:** S9 D9-1.1 (tanda 9)
- **Objetivo:** Al arrancar con la cámara bajo la atmosférica − brecha, el protocolo abre el aire atmosférico (nunca la lenta mientras haya vacío), sin confirmación.
- **Precondiciones:** Hacer vacío en la cámara en modo prueba (puerta cerrada) y cortar la energía con la cámara en vacío.
- **Pasos:**
  1. Arrancar el software.
  2. Observar las salidas `aire_admosferico_camara`, `descompresion_lenta` y `descompresion_rapida`.
- **Resultado esperado:** Se abre el aire atmosférico hasta la presión atmosférica; no se pide confirmación; al quedar segura vuelve a PREPARACION.
- **Criterio de aprobado/fallo:** Aprobado si abre el aire atmosférico sin confirmación y la rápida no abre.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### C-05d — Paro real pulsado y liberado durante el estado seguro del arranque: sí pide confirmación

- **Modo:** En seco  ·  **Origen:** S9 D9-1.2 (tanda 9)
- **Objetivo:** La confirmación se exige solo tras un paro real visto en este encendido, y entonces sí dice «Paro liberado».
- **Precondiciones:** Como C-05, con el estado seguro del arranque en curso.
- **Pasos:**
  1. Pulsar el paro de emergencia; esperar 5 s; liberarlo.
  2. Observar la tarjeta de alarmas y las salidas durante 1 minuto sin confirmar.
  3. Pulsar «Confirmar y llevar a estado seguro» (sin sesión).
- **Resultado esperado:** Tras liberar: «Paro de emergencia liberado — estado seguro pendiente», aviso «Paro liberado…» y el botón; ninguna salida de proceso se mueve hasta confirmar; al confirmar sigue solo por la lenta.
- **Criterio de aprobado/fallo:** Aprobado si pide confirmación tras el paro y no antes.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### C-05e — Cambio de programa y modo prueba con el estado seguro en curso

- **Modo:** En seco  ·  **Origen:** S9 D9-1.3 (tanda 9; revierte SAF-03 de T6)
- **Objetivo:** Con el estado seguro activo se puede cambiar de programa y entrar al modo prueba sin relajar la seguridad.
- **Precondiciones:** Como C-05 (cámara caliente, estado seguro en curso), con un ciclo interrumpido de un programa con `temp_max_apertura` menor que la del programa al que se cambiará.
- **Pasos:**
  1. Cambiar el programa seleccionado a otro con otra sonda Principal o mayor temperatura de apertura.
  2. Verificar que NO ABRIR sigue y que la puerta no abre aunque la sonda Principal del programa nuevo ya esté fría.
  3. Entrar al modo prueba (técnico): observar que el protocolo se pausa (todas las salidas en 0).
  4. En Entradas / Salidas intentar encender `desbloqueo_puerta_1`, `abrir_puerta_1`, `descompresion_rapida`, `descompresion_chaqueta`, `vapor_camara`, `aire_comprimido_camara`, `vapor_generador` y `vapor_caldera` (revisión ★ pasada 2, P-a); encender `descompresion_lenta` y `vapor_chaqueta`. Con el atrapamiento activo (si la puerta lo tiene), intentar `cerrar_puerta_1`.
  5. Salir del modo prueba: el protocolo se reanuda solo.
  6. Intentar iniciar un ciclo.
- **Resultado esperado:** El cambio se acepta; la seguridad sigue usando la sonda y la temperatura de apertura del programa del ciclo interrumpido. En el modo prueba (revisión ★ SAF-01 y P-a, DECISIÓN SIN CONFIRMAR): las ocho salidas del paso 4 se rechazan con su mensaje y, si alguna estaba encendida, el lazo la apaga en el siguiente tick (queda `salida_prueba_cortada` en la bitácora); la lenta y el vapor de chaqueta sí encienden; el cierre con atrapamiento no se convierte en apertura. Tras el modo prueba la lenta vuelve a abrir sola; el ciclo no inicia mientras el estado seguro siga.
- **Criterio de aprobado/fallo:** Aprobado si la puerta no abre (ni por el programa nuevo ni desde el modo prueba) antes de que la sonda del ciclo interrumpido esté bajo su temperatura de apertura y la presión en la banda atmosférica.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### C-05f — Coherencia puerta-presión (SEN-10)

- **Modo:** En seco  ·  **Origen:** S9 D9-1.6 (tanda 9)
- **Objetivo:** Con la puerta abierta, una presión de cámara fuera de la banda atmosférica se detecta como incoherencia (calibración, referencia atmosférica o sensor de puerta).
- **Precondiciones:** Fuera de ciclo, puerta abierta. Presión de referencia (`presion_admosferica`) cambiada a propósito en Parámetros del equipo a un valor alejado de la real más de `rango_presion_atm` (o simular la presión con el calibrador en el lazo).
- **Pasos:**
  1. Observar la tarjeta de alarmas durante 5 s.
  2. Con SEN-10 activa, CERRAR la puerta (sin restaurar la referencia): observar 10 s e intentar iniciar un ciclo.
  3. Abrir de nuevo la puerta, restaurar la referencia (o el valor del calibrador) y observar.
  4. Con la referencia mal configurada y la puerta cerrada desde el principio, observar 10 s.
- **Resultado esperado:** En unas 3 lecturas aparece SEN-10 «Presión de cámara incoherente con la puerta abierta» (ALARMA, bloquea el inicio) con las causas posibles en la acción. Revisión ★ SAF-02 (tanda 9): al cerrar la puerta SEN-10 NO se despeja y el inicio sigue rechazado (con la puerta cerrada no hay referencia atmosférica); solo se despeja sola con 3 lecturas coherentes con la puerta ABIERTA. Con la puerta cerrada desde el principio no aparece. Durante un ciclo nunca aparece. En el modo prueba no se evalúa.
- **Criterio de aprobado/fallo:** Aprobado si aparece, sigue al cerrar la puerta, se despeja sola con la puerta abierta y coherente, y no aparece con la puerta cerrada desde el principio.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### C-05g — Modo prueba con la cámara no segura: apertura de puertas bloqueada (SAF-01)

- **Modo:** En seco  ·  **Origen:** S9, revisión ★ SAF-01 (tanda 9; DECISIÓN SIN CONFIRMAR, excepción nueva a D-ES-15)
- **Objetivo:** En el modo prueba no se puede desbloquear ni abrir una puerta con la cámara no segura (presión fuera de la banda atmosférica, temperatura sobre la de apertura o sin lectura), aunque no haya estado seguro en curso.
- **Precondiciones:** Fuera de ciclo, sin estado seguro activo, cámara segura (presión atmosférica, Principal frío). Puerta con actuador (`AdvancedDoor`).
- **Pasos:**
  1. Entrar al modo prueba; encender y apagar `desbloqueo_puerta_1` y `abrir_puerta_1`: deben funcionar.
  2. Con la puerta cerrada, desconectar el lazo del transmisor de presión de cámara (o subir la presión con el calibrador sobre atm + `rango_presion_atm`).
  3. Intentar de nuevo `desbloqueo_puerta_1` y `abrir_puerta_1`.
  4. Si alguna quedó encendida antes del paso 2, observar que el lazo la apaga.
- **Resultado esperado:** Paso 1 aceptado. Paso 3 rechazado con «No se puede desbloquear ni abrir la puerta: la cámara no es segura…». Paso 4: apagada en el tick siguiente y `salida_prueba_cortada` en la bitácora.
- **Criterio de aprobado/fallo:** Aprobado si con la cámara no segura ninguna orden de prueba desbloquea ni abre la puerta.
- **Nota:** en el equipo de pruebas SIN sensores la cámara nunca es segura: la apertura de puertas no se puede probar desde el modo prueba (PREGUNTA PARA CRISTIAN en el informe S9).
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### C-05h — Estado seguro con la trama AI vencida (TMG-02)

- **Modo:** En seco  ·  **Origen:** S9, revisión ★ TMG-02 (tanda 9)
- **Objetivo:** Si la tarjeta sigue mandando entradas digitales pero deja de mandar las analógicas, el estado seguro no toma la presión congelada como vigente.
- **Precondiciones:** Estado seguro en curso (C-05). Firmware de pruebas o simulador que permita suspender solo las tramas `AI:`.
- **Pasos:**
  1. Suspender las tramas `AI:` durante 10 s; observar la tarjeta de alarmas y las salidas.
  2. Reanudarlas.
  3. Repetir el paso 1 con un programa de líquidos en modo 4/5 durante el enfriamiento con contrapresión (estado seguro tras un fallo en DESCOMPRESION, y también con la confirmación del fallo pendiente en CICLO).
  4. Con la cámara segura y fuera de ciclo, suspender las tramas `AI:` e intentar abrir la puerta; observar «NO ABRIR» en Preciclo.
  5. (Revisión ★ pasada 3, R3-A1) Con un programa de líquidos en modo 4/5 y la cámara presurizada, suspender las tramas `AI:` y CANCELAR el ciclo; esperar 10 s y reanudar las tramas.
- **Resultado esperado:** En menos de 2 s aparece CIC-10 con el motivo de presión de cámara sin lectura; no se abre aire comprimido, aire atmosférico ni ninguna válvula nueva; lo que ya estaba abierto (la lenta) sigue igual; el estado seguro no termina aunque la última presión fuera atmosférica. Revisión ★ pasada 2 (R2-M1): el protocolo NO pasa a «solo la lenta» por esto y una carga líquida sellada con contrapresión no se ventea; al volver las tramas, con 3 tramas válidas se retira el motivo y el protocolo sigue donde estaba. Paso 4 (R2-M3, R3-M1): la puerta no abre (cámara no segura con la presión no vigente) ni por botón ni por apertura automática, y Preciclo muestra «NO ABRIR». Paso 5: mientras no hay tramas, ninguna válvula abre; al volver, el protocolo aplica la contrapresión (aire comprimido) con la lenta cerrada, nunca ventea el líquido por la lenta.
- **Criterio de aprobado/fallo:** Aprobado si sin tramas AI no termina el estado seguro, no abre nada nuevo, no ventea una carga líquida sellada y la puerta no abre.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### C-05i — Arranque sin sensor de presión de cámara: texto de CIC-10 según la causa

- **Modo:** En seco (sin vapor)  ·  **Origen:** T10 D10-3 (tanda 10)
- **Objetivo:** Con la presión de cámara sin lectura, el motivo y la acción de CIC-10 dicen que sin el sensor de presión de cámara no se puede llevar la cámara a estado seguro y piden revisar su conexión o llamar a servicio técnico; no mencionan la sonda Principal. Con la causa de sonda Principal el texto no cambia.
- **Precondiciones:** Lazo del transmisor de presión de cámara desconectado (equipo de pruebas sin sensores, igual que C-05b). Paro de emergencia sin pulsar. Idioma en español.
- **Pasos:**
  1. Arrancar el software y esperar la pantalla de Preciclo.
  2. Leer la fila de CIC-10 en la tarjeta «Alarmas y avisos» de Preciclo.
  3. Abrir la campana: leer el aviso del estado seguro detenido (grupo Emergencia) y la fila de CIC-10.
  4. Cambiar el idioma a inglés (OPCIONES) y repetir los pasos 2 y 3.
  5. (Contraprueba, causa sonda Principal) Con el transmisor de presión conectado y la sonda Principal desconectada, provocar el estado seguro detenido por la sonda (C-05 con el Principal sin lectura) y leer el mismo aviso.
- **Resultado esperado:** Pasos 2 y 3: «Sensor de presión de cámara sin lectura: sin el sensor de presión de cámara no se puede llevar la cámara a estado seguro. Revise la conexión del sensor de presión de cámara o llame a servicio técnico.» (en la fila de alarmas, seguido de «La cámara sigue sin considerarse segura.»); no aparece «Revise la sonda Principal…» ni el botón «Asignar sonda Principal». Paso 4: el aviso de la campana dice «Chamber pressure sensor without reading: without the chamber pressure sensor the chamber cannot be brought to a safe state. Check the chamber pressure sensor connection or call technical service.» (la fila de la lista de alarmas sigue en español: pendiente conocido de la tanda 9, CAP9). Paso 5: el texto de la sonda Principal es el de siempre («Revise la sonda Principal o asigne otra sonda como Principal en OPCIONES › Parámetros del ciclo › Sensores.») con su botón. El comportamiento de C-05b no cambia (NO ABRIR, sin bloquear login, modo prueba, cambio de programa ni apagado).
- **Criterio de aprobado/fallo:** Aprobado si sin presión de cámara ningún texto de CIC-10 menciona la sonda Principal y sí el sensor de presión de cámara, en Preciclo y en la campana, y con la sonda Principal el texto no cambió.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### C-06 — COM-02/COM-03 persisten hasta DESPEJAR en el panel de notificaciones

- **Modo:** En seco (sin vapor)  ·  **Origen:** T2 P-5 (tanda 6)
- **Objetivo:** Una falla de comunicación no se borra sola al salir de FALLA.
- **Precondiciones:** Ciclo de prueba en seco; desconectar el USB de la tarjeta para provocar COM-03; reconectar.
- **Pasos:**
  1. Confirmar la falla y volver a PREPARACION.
  2. Abrir la campana: COM-03 sigue.
  3. Pulsar DESPEJAR en la fila de la alarma.
- **Resultado esperado:** COM-03 sigue visible hasta DESPEJAR; tras despejar desaparece y queda en bitácora.
- **Criterio de aprobado/fallo:** Aprobado si no se despeja sola y el botón funciona fuera de ciclo.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### C-07 — DESPEJAR de COM-02/03 solo con el enlace de vuelta en ok

- **Modo:** En seco (sin vapor)  ·  **Origen:** Q1 T2-b (tanda 7); complementa C-06
- **Objetivo:** El operador no puede despejar la alarma de comunicación mientras el enlace no se recupere.
- **Precondiciones:** Como C-06: ciclo de prueba en seco y COM-03 provocada desconectando el USB de la tarjeta; confirmar la falla y volver a PREPARACION con la tarjeta aún desconectada.
- **Pasos:**
  1. Con la tarjeta aún desconectada, pulsar DESPEJAR en el panel de notificaciones.
  2. Reconectar la tarjeta y esperar ~2 s (3 tramas vigentes).
  3. Pulsar DESPEJAR de nuevo, sin iniciar sesión.
- **Resultado esperado:** Primer intento: rechazado con "No se puede despejar: el enlace con la tarjeta de control todavía no ha vuelto a la normalidad"; la alarma sigue. Segundo intento: se despeja sin pedir sesión.
- **Criterio de aprobado/fallo:** Aprobado si no se despeja sin enlace y sí se despeja sin sesión con el enlace ok.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### F-14 — DESPEJAR de COM-02/03 exige tramas DI nuevas, no solo tiempo

- **Modo:** En seco (sin vapor)  ·  **Origen:** S2a D8-2.9 (tanda 8)
- **Objetivo:** DESPEJAR se acepta solo tras 3 tramas DI distintas y nuevas con el enlace en "ok".
- **Precondiciones:** COM-02 activa tras una desconexión en ciclo (o provocada en seco con un ciclo de prueba).
- **Pasos:**
  1. Reconectar el USB y pulsar DESPEJAR de inmediato.
  2. Esperar 2-3 s y volver a pulsar DESPEJAR.
- **Resultado esperado:** El primer intento se rechaza con el motivo del enlace; tras unas 3 tramas DI (≈1-2 s con el firmware V3) se acepta.
- **Criterio de aprobado/fallo:** Aprobado si no se despeja antes de que la tarjeta envíe tramas DI nuevas.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### C-08 — Rechazo de DESPEJAR con texto del catálogo

- **Modo:** En seco (sin vapor)  ·  **Origen:** S2b D8-2.15 (tanda 8); complementa C-07
- **Objetivo:** El rechazo de DESPEJAR se muestra en el panel de notificaciones con texto legible, no con el texto técnico de la petición.
- **Precondiciones:** Como C-07 (COM-03 activa con la tarjeta desconectada, en PREPARACION).
- **Pasos:**
  1. Pulsar DESPEJAR con la tarjeta aún desconectada.
  2. Cerrar y volver a abrir el panel de notificaciones.
  3. Cambiar el idioma a inglés y repetir el paso 1.
- **Resultado esperado:** Bajo el título del panel: "No se puede despejar: el enlace con la tarjeta de control todavía no ha vuelto a la normalidad." (en inglés: "Cannot clear: ..."). Al cerrar el panel el mensaje desaparece. El panel de Equipo no muestra "apagado rechazado".
- **Criterio de aprobado/fallo:** Aprobado si nunca aparece un texto del tipo "409 Client Error".
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

## Bloque D. Sensores, parámetros y pantallas (en seco)

### D-01 — Roles de sensor: Principal / Referencias / No en uso

- **Modo:** En seco (sin vapor)  ·  **Origen:** §5.5 (T3, T12)
- **Objetivo:** La asignación de roles se guarda y un sensor en uso sin lectura impide iniciar.
- **Precondiciones:** Sesión de técnico, PREPARADO.
- **Pasos:**
  1. OPCIONES › Parámetros del ciclo › Sensores de temperatura: poner Cámara 2 como Referencia en Instrumental 121.
  2. Desconectar la sonda Cámara 2.
  3. Intentar iniciar Instrumental 121.
  4. Dejar Cámara 2 en No en uso y volver a intentar.
- **Resultado esperado:** Con Cámara 2 en uso y sin lectura: inicio rechazado. En No en uso: no genera alarma ni bloquea.
- **Criterio de aprobado/fallo:** Aprobado si el inicio se bloquea solo cuando el sensor está en uso.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-02 — Parámetros: técnico edita en PREPARADO, rechazado en ciclo

- **Modo:** En seco (sin vapor)  ·  **Origen:** §5.9 (T10, T12)
- **Objetivo:** La edición queda auditada y se rechaza durante un ciclo.
- **Precondiciones:** Sesión de técnico.
- **Pasos:**
  1. Editar un parámetro en PREPARADO y guardar.
  2. Iniciar un ciclo e intentar editar.
- **Resultado esperado:** En PREPARADO se guarda y queda la última modificación; en ciclo, rechazado.
- **Criterio de aprobado/fallo:** Aprobado si ambos comportamientos se cumplen.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-03 — Calibración con límites de plausibilidad

- **Modo:** En seco (sin vapor)  ·  **Origen:** S3a
- **Objetivo:** Una calibración imposible se rechaza; una corrección grande pide confirmación.
- **Precondiciones:** Sesión de técnico. Patrón de temperatura y de presión.
- **Pasos:**
  1. Calibrar temp_camara con dos puntos normales (corrección < 5 °C).
  2. Intentar una corrección de 20 °C.
- **Resultado esperado:** La primera se aplica y se audita; la segunda se rechaza como no plausible.
- **Criterio de aprobado/fallo:** Aprobado si no se puede guardar una calibración absurda. (Depende de S3a.)
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-04 — Pantallas: navegación, campana y legibilidad

- **Modo:** En seco (sin vapor)  ·  **Origen:** §5.11; U1; U2
- **Objetivo:** La navegación es uniforme y los textos y áreas táctiles son usables en el equipo real.
- **Precondiciones:** Las dos pantallas encendidas.
- **Pasos:**
  1. Preciclo → Menú → Iniciar sesión → OPCIONES y volver con Atrás paso a paso; luego con Home de un toque.
  2. Abrir la campana con alarmas activas.
  3. Salir con Home con sesión abierta y esperar 5 min sin tocar pantallas con sesión.
  4. Revisar tamaño de textos y botones (avisos, login sin BD, asistente, Opciones).
- **Resultado esperado:** Atrás regresa a la anterior sin cerrar sesión; Home a la principal; la sesión vence a los 5 min aunque se use la preciclo.
- **Criterio de aprobado/fallo:** Aprobado si no hay pantallas sin salida ni textos/botones inutilizables.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-05 — Cambio de programa: permitido en FALLA, rechazado con algo en curso

- **Modo:** En seco (sin vapor)  ·  **Origen:** S2
- **Objetivo:** El cambio de programa sin sesión sigue la decisión 2 y queda en la bitácora.
- **Precondiciones:** Equipo en FALLA (p. ej. tras C-02).
- **Pasos:**
  1. Cambiar de programa sin sesión.
  2. Pulsar el paro e intentar cambiar.
- **Resultado esperado:** En FALLA se acepta; con paro (o estado seguro pendiente) se rechaza. Ambos quedan en `audit_log`.
- **Criterio de aprobado/fallo:** Aprobado si la bitácora tiene `PROGRAMA_SELECCIONADO` y `PROGRAMA_SELECCION_RECHAZADA`.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-06 — Próximo mantenimiento: cálculo, registro y aviso

- **Modo:** En seco (sin vapor)  ·  **Origen:** M1 (tanda 3)
- **Objetivo:** El próximo mantenimiento se calcula desde la instalación, se registra y nunca bloquea un ciclo.
- **Precondiciones:** Sesión de técnico. Intervalos por defecto DEFINITIVOS (aprobados 20-oct-2026): 365 días y 1000 ciclos, contados desde la instalación; vence por lo que ocurra primero.
- **Pasos:**
  1. Ver Menú Principal: tarjeta Próximo mantenimiento, su ventana e Información del equipo.
  2. OPCIONES › Mantenimiento: Registrar mantenimiento realizado (preventivo).
  3. Con `intervalo_dias` muy bajo (p. ej. 1) y el reloj adelantado, comprobar "VENCIDO" y el aviso en la campana; iniciar un ciclo.
  4. Con el reloj anterior a la instalación, abrir la ventana de mantenimiento.
  5. OPCIONES › Mantenimiento › Intervalos: ver 365 días y 1000 ciclos; cambiar los días a 200 con el teclado numérico y Guardar; poner 0 en ciclos (No aplica); comprobar que un valor fuera de rango se rechaza y que un operador (sin sesión técnica) no puede editar.
  6. Con el programa en marcha, adelantar el reloj de Windows más de un día y reabrir la ventana de mantenimiento.
- **Resultado esperado:** Fecha = instalación + 365 días (o 1000 ciclos desde la instalación, lo primero). Tras registrar, la base es esa fecha y ese contador. Vencido: aviso SIS-04 en la campana y el ciclo se inicia igual. Reloj anterior a la instalación o adelantado: "—" (no un valor falso) y el registro se rechaza con su motivo. Los intervalos editados quedan auditados.
- **Criterio de aprobado/fallo:** Aprobado si nunca se bloquea un ciclo por el mantenimiento, no se muestra una fecha falsa y solo técnico/ingeniero editan los intervalos.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-07 — Calibración y Entradas/Salidas desde el ejecutable (engrane)

- **Modo:** En seco (sin vapor)  ·  **Origen:** C1 (tanda 3); S3a
- **Objetivo:** El menú de ajustes (PySide) abre con el ejecutable, se autentica con el backend y respeta roles y plausibilidad.
- **Precondiciones:** Ejecutable instalado. Usuario técnico e ingeniero. Patrón de temperatura.
- **Pasos:**
  1. Tocar el engrane; iniciar sesión en el menú de ajustes (técnico).
  2. Entradas/Salidas › Temperaturas › calibrar con dos puntos normales; luego una corrección de 20 °C; luego una grande confirmable.
  3. Modo prueba: encender una salida segura; cerrar la ventana con "✕ Salir".
  4. Iniciar un ciclo e intentar abrir calibración/modo prueba.
- **Resultado esperado:** Abre sin error (si no abre: revisar `scipy` en el spec). Calibración normal se guarda y audita; la absurda se rechaza con el motivo (no como fallo de conexión); la grande pide confirmación explícita. Al salir, el modo prueba termina. En ciclo, rechazado.
- **Criterio de aprobado/fallo:** Aprobado si ninguna escritura es posible sin sesión ni en ciclo y los rechazos muestran el motivo real.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-08 — Programas de usuario persistentes con el ejecutable

- **Modo:** En seco (sin vapor)  ·  **Origen:** C2 (tanda 3)
- **Objetivo:** Lo que el técnico edita en los programas de usuario no se pierde al cerrar ni al actualizar.
- **Precondiciones:** Ejecutable instalado en Archivos de programa. Sesión de técnico.
- **Pasos:**
  1. Editar un parámetro de un programa de usuario y cerrar el software.
  2. Reabrir y comprobar el valor.
  3. Reemplazar la carpeta del programa por una versión nueva y comprobar de nuevo.
  4. Dañar a propósito un archivo de usuario (`%ProgramData%\Especifika\Autoclave\programa\autoclave\cycles\user\*.json`) y reiniciar.
- **Resultado esperado:** El valor editado se conserva tras cerrar y tras actualizar; `factory` es solo lectura. Con el archivo dañado, aviso de arranque y se usa el programa de fábrica (nunca un ciclo inválido).
- **Criterio de aprobado/fallo:** Aprobado si no se pierde ninguna edición y un programa dañado jamás corre.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-09 — Menú Principal sin la tarjeta de secado; CIC-10 indica qué hacer

- **Modo:** En seco (sin vapor)  ·  **Origen:** S4; U5 (tanda 3)
- **Objetivo:** La tarjeta "Tiempo adicional de secado" ya no existe, y un estado seguro detenido indica cómo recuperarlo.
- **Precondiciones:** Equipo con el estado seguro detenido por el Principal sin lectura (desconectar la sonda Principal tras un ciclo en operación, o simulador).
- **Pasos:**
  1. Abrir el Menú Principal y revisar la fila de Reportes e Información (iconos incluidos).
  2. Con el estado seguro detenido, abrir la campana: leer el aviso y pulsar "Asignar sonda Principal".
  3. En OPCIONES › Parámetros del ciclo › Sensores, asignar otra sonda con lectura como Principal.
- **Resultado esperado:** Reportes e Información a mitad de ancho cada una, con iconos. El aviso dice "Revise la sonda Principal o asigne otra…"; NO ABRIR sigue vigente. Con otra sonda con lectura y no más fría que las demás, el protocolo continúa; si es más fría, sigue detenido.
- **Criterio de aprobado/fallo:** Aprobado si no hay ninguna forma de declarar la cámara segura a mano y el cambio de sonda solo libera con una lectura segura.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-10 — Selector de ciclo en Preciclo

- **Modo:** En seco (sin vapor)  ·  **Origen:** B6 (tanda 4)
- **Objetivo:** El operador cambia de programa tocando el recuadro "Programa"; los 3 más usados salen primero.
- **Precondiciones:** Equipo en PREPARADO, sin ciclo en curso. Historial con ciclos de al menos 2 programas (o equipo sin historial).
- **Pasos:**
  1. Con el equipo en reposo, tocar el recuadro "Programa" (debe decir "Toque para cambiar de ciclo").
  2. Revisar el orden: primero los más usados (marca "Más usado"), después el resto 1-2-3-4.
  3. Elegir otro programa; comprobar que el número y el nombre cambian y que sigue elegido tras volver al reposo.
  4. Iniciar un ciclo y tocar el recuadro; con el paro pulsado o un estado seguro pendiente, también.
  5. Repetir sin historial (base nueva): orden 1-2-3-4 y sin marcas.
- **Resultado esperado:** La ventana lista número, nombre y temperatura/tiempo; elegir usa el mismo cambio de programa de siempre (queda `PROGRAMA_SELECCIONADO` en `audit_log`, origen `puerta_N`). En ciclo, con paro o estado seguro el recuadro no es tocable. Si el backend rechaza, la ventana muestra el motivo.
- **Criterio de aprobado/fallo:** Aprobado si no se puede cambiar de programa en ciclo, el orden por uso es correcto y ningún rechazo se muestra como fallo genérico.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-11 — Aviso de impresora desconectada al arrancar

- **Modo:** En seco (sin vapor)  ·  **Origen:** B5 (tanda 4)
- **Objetivo:** Si la impresora está habilitada y desconectada, el equipo avisa sin bloquear nada.
- **Precondiciones:** Impresora térmica instalada en Windows como `Impresora_Termica`. Sesión de técnico para la bandera (`GET/PUT /printer/config`).
- **Pasos:**
  1. Con la impresora conectada, arrancar el software: no debe haber aviso.
  2. Cerrar el software, desconectar el cable USB de la impresora y arrancar de nuevo.
  3. Abrir la campana y revisar la bandeja de avisos de Preciclo: aviso "Impresora no conectada" (no en la barra superior).
  4. Iniciar y terminar un ciclo con la impresora desconectada.
  5. Conectar la impresora y reimprimir un ciclo del Historial: el aviso desaparece.
  6. Con `habilitada = false` (`PUT /printer/config`), arrancar sin impresora.
- **Resultado esperado:** Desconectada y habilitada: aviso de baja prioridad (SIS-05) en la campana y en Preciclo; no impide iniciar ni cerrar el ciclo. Se limpia con una impresión exitosa. Deshabilitada: ni verificación ni aviso. No retrasa el arranque.
- **Criterio de aprobado/fallo:** Aprobado si el aviso aparece solo con la impresora desconectada y habilitada y nunca bloquea un ciclo.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-12 — Caducidad de la sesión por inactividad (5 min)

- **Modo:** En seco (sin vapor)  ·  **Origen:** B7 (tanda 4)
- **Objetivo:** Un token sin actividad caduca en el backend con el mismo plazo que la UI, sin afectar al ciclo.
- **Precondiciones:** Sesión de técnico en OPCIONES. Cronómetro.
- **Pasos:**
  1. Iniciar sesión y navegar por OPCIONES sin dejar de tocar la pantalla durante más de 6 min: la sesión debe seguir viva.
  2. Dejar la pantalla sin tocar 5 min: la UI vuelve al Login/Reposo con "Sesión cerrada por inactividad".
  3. En el menú del engrane (PySide), iniciar sesión, esperar 6 min sin actuar e intentar guardar un parámetro.
  4. Con un ciclo en marcha, dejar caducar la sesión y observar el ciclo.
- **Resultado esperado:** Con uso la sesión no caduca; sin uso, a los 5 min (la UI cierra y el backend rechaza el token con 401). En el engrane el guardado responde "Sesión no válida o vencida". El ciclo en marcha no se interrumpe y "Apagar equipo" sigue permitido sin sesión.
- **Criterio de aprobado/fallo:** Aprobado si la caducidad nunca afecta al ciclo ni a las salidas y el operador debe volver a iniciar sesión.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-13 — Salida forzada del modo prueba huérfano (ingeniero)

- **Modo:** En seco (sin vapor)  ·  **Origen:** B8 (tanda 4)
- **Objetivo:** Si el dueño del modo prueba ya no tiene sesión, un ingeniero puede terminarlo; el técnico no.
- **Precondiciones:** Un técnico con el modo prueba activo (menú del engrane › Entradas/Salidas). Un ingeniero con sesión. Herramienta para llamar a `POST /io/test/force-exit` (no hay botón aún).
- **Pasos:**
  1. Con el técnico aún en sesión, intentar la salida forzada con el ingeniero: debe rechazarse (dueño vigente).
  2. Dejar caducar la sesión del técnico (5 min) o cerrarla; con una sesión de técnico distinta intentar la salida forzada: 403.
  3. Con el ingeniero, `POST /io/test/force-exit` con `{"confirmar": true, "motivo": "..."}`.
  4. Revisar `audit_log` (`modo_prueba_salida_forzada`) y que todas las salidas estén apagadas.
- **Resultado esperado:** Dueño vigente: 409. Técnico: 403. Ingeniero con dueño vencido y confirmación: el modo prueba termina, salidas en seguro; la bitácora dice quién fuerza, a quién y por qué.
- **Criterio de aprobado/fallo:** Aprobado si solo el ingeniero puede forzar, solo con el dueño sin sesión, con confirmación y con salidas apagadas.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-14 — Nombre "Parámetros del equipo"

- **Modo:** En seco (sin vapor)  ·  **Origen:** B4 (tanda 4)
- **Objetivo:** El antiguo "Parámetros del sistema" se llama "Parámetros del equipo" en toda la interfaz visible.
- **Precondiciones:** Sesión de técnico. Probar en español e inglés.
- **Pasos:**
  1. OPCIONES: revisar el nombre de la sección en el cajón y el título.
  2. Menú del engrane (PySide): revisar el elemento del menú.
  3. Cambiar el idioma a inglés y repetir.
- **Resultado esperado:** Se lee "Parámetros del equipo" (en inglés "Equipment parameters"); no queda "Parámetros del sistema" en ninguna pantalla.
- **Criterio de aprobado/fallo:** Aprobado si no aparece el nombre antiguo en ninguna pantalla ni idioma.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-15 — Interruptor "Impresora habilitada"

- **Modo:** En seco (sin vapor)  ·  **Origen:** P2 (tanda 5)
- **Objetivo:** El aviso de impresora desconectada sigue al interruptor sin reiniciar.
- **Precondiciones:** Técnico con sesión; impresora desconectada.
- **Pasos:**
  1. Con el interruptor en Sí: ver el aviso SIS-05 en la campana.
  2. Poner el interruptor en No (OPCIONES › Parámetros del equipo).
  3. Volver a Sí.
  4. Revisar la bitácora.
- **Resultado esperado:** En No, el aviso desaparece; en Sí, reaparece en ≤ 5 s. Auditoría `impresora_configurada` con el usuario.
- **Criterio de aprobado/fallo:** Aprobado si el aviso sigue al interruptor y queda auditado.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-16 — Ajustes PySide: renovación del token y reingreso tras sesión vencida

- **Modo:** En seco (sin vapor)  ·  **Origen:** P3 (tanda 5)
- **Objetivo:** Editar en PySide no pierde la sesión mientras se usa y, si venció, permite reingresar sin perder lo editado.
- **Precondiciones:** Técnico con sesión en el menú de ajustes PySide (engranaje).
- **Pasos:**
  1. Trabajar en Calibración tocando la pantalla durante más de 6 min: la sesión sigue.
  2. Dejar la ventana sin tocar 7 min, editar un parámetro de secado y Guardar.
  3. En el diálogo, ingresar el MISMO usuario y su contraseña.
  4. Repetir cancelando el diálogo.
  5. Repetir ingresando OTRO usuario.
- **Resultado esperado:** En uso no caduca. Tras inactividad, Guardar pide login; con el mismo usuario guarda el valor editado; cancelado dice "NO se guardó"; otro usuario se rechaza.
- **Criterio de aprobado/fallo:** Aprobado si nunca se guarda sin sesión válida ni a nombre de otro usuario.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-17 — Parámetros del ciclo: defecto, sensores, entradas y gestión de programas

- **Modo:** En seco (sin vapor)  ·  **Origen:** O1 (tanda 5)
- **Objetivo:** El flujo completo de Opciones › Parámetros del ciclo funciona con permisos correctos.
- **Precondiciones:** Técnico con sesión, PREPARADO.
- **Pasos:**
  1. Programa → fase → parámetro: ver actual, por defecto, mín., máx., usuario y fecha del último cambio.
  2. Cambiar un valor y luego tocar "Por defecto" y Guardar.
  3. Sensores: intentar dejar 0 o 2 Principales (debe rechazar) y 3 Referencias (debe rechazar).
  4. Entradas mostradas: elegir 1, 2 y 3 entradas; intentar 0.
  5. Duplicar un programa con nombre nuevo; intentar duplicar con el mismo nombre de otro (rechazo).
  6. Deshabilitar el duplicado: ya no aparece en Preciclo. Borrarlo.
  7. Intentar borrar un programa de fábrica y el programa seleccionado (rechazo).
  8. Iniciar un ciclo y, como técnico, intentar editar (bloqueado); como ingeniero sí.
- **Resultado esperado:** Todo lo anterior se comporta como se indica y queda en la bitácora (`param_ciclo_cambio`, `programa_duplicado`, `programa_habilitado`, `programa_borrado`, `entradas_mostradas`). Nota: Preciclo aún muestra las entradas fijas (pendiente).
- **Criterio de aprobado/fallo:** Aprobado si ningún rechazo falta y la auditoría está completa.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-18 — Cambio de unidades: °F y psig/inHg en vacío y en presión

- **Modo:** En operación (vapor)  ·  **Origen:** U1 (tanda 5)
- **Objetivo:** La presentación cambia sin alterar el control; psi nunca negativo.
- **Precondiciones:** Técnico con sesión, fuera de ciclo. Patrón de presión conectado.
- **Pasos:**
  1. Opciones › Parámetros del equipo: elegir °F y psig/inHg.
  2. Ver en las DOS pantallas que Preciclo cambia a °F y psig sin reiniciar.
  3. Con la cámara en vacío (prevacío de un ciclo o bomba en modo prueba): la presión se muestra en inHg, positiva.
  4. Con la cámara en presión (esterilización): psig ≈ patrón − P_atm.
  5. Editar un parámetro de presión de vacío (p. ej. presion_baja_pulso_a) en inHg y verificar que el valor guardado en kPa abs es el esperado (bitácora).
  6. Intentar cambiar las unidades con un ciclo en curso (rechazo).
  7. Imprimir el ticket de un ciclo: cabecera "Unidades: F, psig (v=inHg vacio)" y vacíos con sufijo v.
  8. Volver a °C y kPa.
- **Resultado esperado:** Valores coherentes con el patrón (tolerancia de calibración); en vacío nunca un psi negativo; el ciclo se comporta igual que en °C/kPa.
- **Criterio de aprobado/fallo:** Aprobado si ninguna lectura convertida difiere del patrón más de lo tolerado y no hay valores negativos en psi.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-19 — Recorrido en inglés (solo verificación: R-06 sigue vigente)

- **Modo:** En seco (sin vapor)  ·  **Origen:** I1, I2, I3 (tanda 5)
- **Objetivo:** Las pantallas, alarmas y el ticket se leen en inglés sin truncados.
- **Precondiciones:** Ingeniero; idioma cambiado a inglés por `PUT /language` (no hay selector para el operador).
- **Pasos:**
  1. Recorrer arranque, login, preciclo, ciclo, Opciones.
  2. Provocar una alarma (p. ej. puerta abierta).
  3. Imprimir un ticket.
  4. Volver a español.
- **Resultado esperado:** Textos en inglés, sin cortes en 1024 px; la alarma muestra título y descripción en inglés; el ticket dice Date/Status/Operator. Anotar todo texto que siga en español.
- **Criterio de aprobado/fallo:** Informativo: lista de textos pendientes para la revisión de traducciones (F5).
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-20 — Ticket de ciclo INTERRUMPIDO dice CARGA NO ESTÉRIL

- **Modo:** En seco (sin vapor)  ·  **Origen:** T2 P-9 (tanda 6)
- **Objetivo:** El ticket reimpreso de un ciclo interrumpido advierte que la carga no está estéril.
- **Precondiciones:** Un ciclo INTERRUMPIDO en el historial (p. ej. el de C-05).
- **Pasos:**
  1. Reimprimir el ticket desde Historial en español.
  2. Cambiar el idioma a inglés y reimprimir.
- **Resultado esperado:** Aparece "*** CARGA NO ESTÉRIL ***" / "*** LOAD NOT STERILE ***" sin caracteres extraños.
- **Criterio de aprobado/fallo:** Aprobado si la leyenda aparece legible en ambos idiomas.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-21 — PySide: teclado en pantalla y reingreso tras sesión vencida

- **Modo:** En seco (sin vapor)  ·  **Origen:** C1a (tanda 6)
- **Objetivo:** Sin teclado físico se puede ingresar, editar y reingresar en PySide, siempre con el mismo usuario.
- **Precondiciones:** Sin teclado físico conectado. Técnico con sesión en el menú PySide.
- **Pasos:**
  1. Tocar un campo de texto y uno numérico (secado, calibración): abre el teclado táctil.
  2. En el numérico con valor 1, teclear 2: debe quedar 2 (no 12); probar un valor fuera de rango.
  3. Dejar vencer la sesión, editar y Guardar: el diálogo muestra el usuario fijo; ingresar la clave.
  4. Repetir con la clave vacía (anotar el comportamiento; SAF-05 pendiente).
- **Resultado esperado:** El teclado abre una sola vez por toque; el rango se valida en vivo; el reingreso guarda a nombre del mismo usuario y no permite cambiarlo.
- **Criterio de aprobado/fallo:** Aprobado si todo se opera sin teclado físico y nunca se guarda a nombre de otro.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-22 — Admin ve Parámetros del equipo en solo lectura

- **Modo:** En seco (sin vapor)  ·  **Origen:** C1b (tanda 6)
- **Objetivo:** El admin no modifica parámetros del equipo, impresora ni unidades.
- **Precondiciones:** Sesión de admin.
- **Pasos:**
  1. Entrar a OPCIONES (abre en Usuarios) y luego a Parámetros del equipo.
  2. Intentar editar un valor, la impresora y las unidades.
- **Resultado esperado:** Controles deshabilitados con el aviso de solo lectura por rol; el backend responde 403 si se intenta.
- **Criterio de aprobado/fallo:** Aprobado si ningún cambio se guarda.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-23 — Unidades: clase de parámetro y chaqueta absoluta en psig

- **Modo:** En seco (sin vapor)  ·  **Origen:** C1c, C1d (tanda 6)
- **Objetivo:** Los parámetros de ciclo y la chaqueta se muestran y teclean con la conversión correcta.
- **Precondiciones:** Técnico con sesión, unidades en °F y psig/inHg. Patrón de presión en la chaqueta.
- **Pasos:**
  1. Ver en Parámetros del ciclo una temperatura absoluta (134 °C → 273,2 °F) y un rango (3 °C → 5,4 °F).
  2. Ver `presion_chaqueta` en psig y comparar con (P_abs − P_atm)/6,894757.
  3. Comparar la lectura viva de chaqueta con el patrón.
  4. Volver a °C/kPa.
- **Resultado esperado:** Absolutos con desplazamiento, rangos sin él; chaqueta en psig coherente con el patrón; `rango_calentamiento` sin conversión.
- **Criterio de aprobado/fallo:** Aprobado si todas las cifras coinciden con el cálculo manual.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-24 — Entradas mostradas en Preciclo, Ciclo en curso y gráfica

- **Modo:** En seco (sin vapor)  ·  **Origen:** O3 (tanda 6)
- **Objetivo:** Las 1 a 3 entradas elegidas por programa se ven en las tarjetas y en la gráfica.
- **Precondiciones:** Técnico con sesión. Programa con 3 entradas elegidas en Parámetros del ciclo (D-17).
- **Pasos:**
  1. Ver Preciclo: las 3 columnas muestran las entradas elegidas con su icono y unidad.
  2. Elegir 1 entrada: las columnas sobrantes quedan vacías.
  3. Elegir una sonda en "No en uso": muestra "—".
  4. Cambiar a °F/psi: valores y ejes cambian.
  5. Iniciar un ciclo de prueba: la gráfica muestra las mismas series con su leyenda.
- **Resultado esperado:** Las entradas siguen la selección del programa y la unidad vigente; nunca un número sin lectura.
- **Criterio de aprobado/fallo:** Aprobado si coinciden en las dos pantallas y en la gráfica.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-25 — OPCIONES › Parámetros del equipo: rangos, permisos y aplicación sin reiniciar

- **Modo:** En seco (sin vapor)  ·  **Origen:** O2a (tanda 6)
- **Objetivo:** Cada parámetro del equipo se edita dentro de su rango, por el rol correcto, y se aplica en vivo.
- **Precondiciones:** Técnico con sesión, sin ciclo.
- **Pasos:**
  1. Ver `temp_max_apertura` = 80 °C y `tiempo_standby` = 10 min por defecto.
  2. Intentar un valor fuera de rango (rechazo).
  3. Cambiar `tiempo_standby` a 1 min y comprobar que la suspensión llega en 1 min sin reiniciar.
  4. Restablecer al defecto.
  5. Intentar editar `presion_atmosferica` (solo lectura).
  6. Con un ciclo en curso, intentar editar como ingeniero (bloqueado).
- **Resultado esperado:** Rangos respetados, efecto inmediato, bitácora `param_sistema_cambio` con valor anterior y nuevo; operador y admin sin edición.
- **Criterio de aprobado/fallo:** Aprobado si nada fuera de rango o con ciclo se guarda.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-26 — OPCIONES › Usuarios y operadores

- **Modo:** En seco (sin vapor)  ·  **Origen:** O2b (tanda 6)
- **Objetivo:** Desactivar, reactivar y restablecer claves respeta roles; no se borra a nadie.
- **Precondiciones:** Sesiones de admin, técnico e ingeniero disponibles.
- **Pasos:**
  1. Como técnico: la sección se ve con todo deshabilitado y el motivo.
  2. Como admin: desactivar un técnico; su sesión abierta se cierra. Reactivarlo.
  3. Restablecer su clave: al ingresar pide cambiarla.
  4. Intentar desactivarse a sí mismo (rechazo). (Desde U11 la cuenta `Ingeniero` no se desactiva, así que en banco nunca queda un único ingeniero que desactivar; esa regla la cubre la prueba automática.)
  5. Agregar un operador, desactivarlo y reactivarlo; verificar la lista de operadores al iniciar ciclo.
- **Resultado esperado:** Cada acción queda en bitácora (`usuario_desactivado`, `clave_restablecida`, `operador_creado`…); el admin no toca a un ingeniero.
- **Criterio de aprobado/fallo:** Aprobado si ningún rechazo falta y no hay forma de borrar.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-26b — Cuentas del sistema Admin e Ingeniero

- **Modo:** En seco (sin vapor)  ·  **Origen:** U11 (tanda 11, D11-6)
- **Objetivo:** Las cuentas `Admin` e `Ingeniero` entran sin distinguir mayúsculas, no se pueden desactivar y, al actualizar, `admin`/`ingeniero` pasan a `Admin`/`Ingeniero` con su contraseña.
- **Precondiciones:** Equipo actualizado desde la compilación F (BD con `admin` e `ingeniero`) y, aparte, una instalación limpia. Sesión de ingeniero.
- **Pasos:**
  1. Instalación limpia: ingresar como `Ingeniero` / `ingeniero1234` y como `Admin` / `admin1234` (los dos piden cambiar la contraseña).
  2. Ingresar escribiendo el usuario en minúsculas (`admin`) y en mayúsculas (`ADMIN`): entra a la misma cuenta `Admin`.
  3. Equipo actualizado: ingresar con la contraseña que tenía `admin` antes de actualizar; la lista de OPCIONES › Usuarios muestra `Admin` e `Ingeniero` y la bitácora tiene dos filas «Cuenta renombrada».
  4. OPCIONES › Usuarios: seleccionar `Admin` y luego `Ingeniero`: «Desactivar» deshabilitado con el aviso de cuenta del sistema; «Restablecer contraseña» habilitado.
  5. Restablecer la contraseña de `Admin` desde el ingeniero: al ingresar pide cambiarla.
  6. Nuevo usuario con el nombre `ADMIN` o `ingeniero`: se rechaza (ya existe).
- **Resultado esperado:** Las dos cuentas entran con cualquier capitalización del usuario; no se pueden desactivar desde la pantalla; su contraseña se cambia y restablece; al actualizar conservan la contraseña.
- **Criterio de aprobado/fallo:** Aprobado si ninguna de las dos cuentas se puede desactivar, el ingreso no depende de las mayúsculas del usuario y la actualización no pide contraseñas nuevas.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-27 — OPCIONES › Fecha y hora en solo lectura

- **Modo:** En seco (sin vapor)  ·  **Origen:** O2c (tanda 6)
- **Objetivo:** La pantalla muestra la hora del PC y avisa si el reloj es anterior a la instalación.
- **Precondiciones:** Cualquier rol con sesión.
- **Pasos:**
  1. Abrir Fecha y hora: la hora avanza cada segundo; zona y fecha de instalación visibles.
  2. Atrasar el reloj de Windows a antes de la instalación y volver a abrir.
  3. Restaurar la hora.
- **Resultado esperado:** No hay campos editables; con el reloj atrasado aparece el aviso rojo.
- **Criterio de aprobado/fallo:** Aprobado si no se puede cambiar nada y el aviso aparece.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-28 — OPCIONES › Información del sistema

- **Modo:** En seco (sin vapor)  ·  **Origen:** O2d (tanda 6)
- **Objetivo:** Modelo, serie, versiones, ciclos, idioma, unidades, impresora y red se muestran correctos.
- **Precondiciones:** Cualquier rol con sesión. Tarjeta conectada.
- **Pasos:**
  1. Comparar cada dato con el perfil, el firmware real y el número de ciclos.
  2. Desconectar la impresora y la red: los chips pasan a naranja.
  3. Desconectar la tarjeta y reabrir: los demás datos siguen.
- **Resultado esperado:** Datos correctos; un dato que falla muestra "—" sin afectar a los otros.
- **Criterio de aprobado/fallo:** Aprobado si coinciden con la realidad del equipo.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-29 — OPCIONES › Bitácora de auditoría con filtros

- **Modo:** En seco (sin vapor)  ·  **Origen:** O2e (tanda 6)
- **Objetivo:** La bitácora es legible, filtrable y no editable.
- **Precondiciones:** Haber hecho D-25 y D-26 en la sesión.
- **Pasos:**
  1. Abrir Bitácora: ver los eventos recientes con fecha, usuario en negrita y frase.
  2. Filtrar por fecha, usuario y tipo; paginar.
  3. Con °F, ver un cambio de `temp_max_apertura` (80 °C → 176 °F).
  4. Como operador, intentar abrir la bitácora.
- **Resultado esperado:** Filtros y paginación correctos; valores en la unidad vigente; no hay acción de editar ni borrar.
- **Criterio de aprobado/fallo:** Aprobado si cada evento hecho antes aparece con texto propio.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-30 — Calibración de presión atmosférica: medición aceptada

- **Modo:** En seco (sin vapor)  ·  **Origen:** O2f (tanda 6)
- **Objetivo:** La referencia atmosférica se mide con la cámara abierta y fría y se aplica sin reiniciar.
- **Precondiciones:** Técnico con sesión, fuera de ciclo, una puerta ABIERTA, Principal < 80 °C. Barómetro de referencia.
- **Pasos:**
  1. Iniciar la calibración atmosférica y esperar los 120 s (24 muestras).
  2. Comparar el promedio con el barómetro (dispersión ≤ 1,5 kPa; valor entre 60 y 105 kPa).
  3. Si difiere > 5 kPa del anterior o no había anterior, confirmar dentro de 5 min.
  4. Ver en psig que la cámara abierta marca ≈ 0.
  5. Imprimir la página de prueba y las ganancias.
- **Resultado esperado:** Nuevo valor aplicado; bitácora `calibracion_atm_ok` con anterior, nuevo, muestras, promedio y dispersión.
- **Criterio de aprobado/fallo:** Aprobado si el valor coincide con el barómetro (± 0,5 kPa) y queda auditado.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-31 — Calibración atmosférica: abortos y rechazos

- **Modo:** En seco (sin vapor)  ·  **Origen:** O2f (tanda 6)
- **Objetivo:** La medición aborta sin cambiar el valor ante cualquier condición perdida.
- **Precondiciones:** Como D-30.
- **Pasos:**
  1. Intentar iniciar con las puertas cerradas (rechazo con motivo).
  2. Iniciar y cerrar la puerta a mitad: aborta.
  3. Iniciar y cancelar.
  4. Dejar vencer una confirmación pendiente (5 min).
  5. Como admin, intentar iniciar (403).
  6. Mientras mide, intentar cambiar un parámetro del equipo (bloqueado).
- **Resultado esperado:** En cada caso se conserva el valor anterior, sin reintento automático; bitácora `calibracion_atm_abortada`/`calibracion_atm_rechazada`.
- **Criterio de aprobado/fallo:** Aprobado si el valor nunca cambia sin una medición completa y válida.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-32 — OPCIONES › Conectividad: red, destinatarios y correo de prueba

- **Modo:** En seco (sin vapor)  ·  **Origen:** O2g (tanda 6)
- **Objetivo:** El estado de red es real y el correo de prueba llega solo a destinatarios guardados.
- **Precondiciones:** Ingeniero o admin con sesión; red con Internet; cuenta de correo configurada.
- **Pasos:**
  1. Ver Wi-Fi/SSID, señal e IP; desconectar la red y ver el cambio.
  2. Agregar un destinatario (nombre y correo con el teclado); intentar uno inválido o duplicado.
  3. Enviar correo de prueba; revisar la bandeja.
  4. Apagar el interruptor de envío e intentar de nuevo (rechazo); enviar desde Historial ("correo no configurado").
  5. Como técnico: todo deshabilitado con el motivo.
- **Resultado esperado:** Correo recibido por cada destinatario guardado; la contraseña nunca se muestra; bitácora `correo_configurado` y `correo_prueba`.
- **Criterio de aprobado/fallo:** Aprobado si el correo llega y ninguna contraseña aparece en pantalla ni en el log.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-33 — Respaldo y restauración por USB

- **Modo:** En seco (sin vapor)  ·  **Origen:** O2h (tanda 6)
- **Objetivo:** Un respaldo del mismo equipo se restaura completo; uno ajeno o alterado se rechaza sin tocar nada.
- **Precondiciones:** Técnico con sesión, fuera de ciclo, memoria USB.
- **Pasos:**
  1. Exportar respaldo (con y sin historial); ver el ZIP en `Especifika_respaldos/`.
  2. Cambiar un parámetro del equipo y uno de calibración; restaurar: vuelven los valores sin reiniciar.
  3. Editar un byte de un archivo del ZIP e intentar restaurar (rechazo).
  4. Intentar restaurar un respaldo de otro número de serie (rechazo).
  5. Con ciclo en curso, intentar exportar (bloqueado).
- **Resultado esperado:** Restauración completa o nada; bitácora `respaldo_exportado`/`respaldo_restaurado`; el ZIP no contiene contraseñas.
- **Criterio de aprobado/fallo:** Aprobado si ningún respaldo inválido aplica cambios.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-34 — Recorrido completo en inglés

- **Modo:** En seco (sin vapor)  ·  **Origen:** I4 (tanda 6)
- **Objetivo:** Pantallas, motivos de puerta y fallas se ven en inglés sin cortes.
- **Precondiciones:** Idioma en inglés (técnico), resolución 1024 px.
- **Pasos:**
  1. Recorrer Inicio, Preciclo, Ciclo en curso, Historial, Reportes y cada sección de OPCIONES.
  2. Intentar abrir una puerta con la cámara no segura: el motivo sale en inglés con las unidades vigentes.
  3. Ver un ciclo con falla en Historial: el motivo se traduce.
- **Resultado esperado:** Sin textos en español ni recortados; nombres de ciclo, roles y estados traducidos.
- **Criterio de aprobado/fallo:** Aprobado si no queda ningún texto de seguridad en español; anotar los demás pendientes.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-35 — PDF de ciclo y consolidado en inglés y en °F/psig

- **Modo:** En seco (sin vapor)  ·  **Origen:** I4 (tanda 6)
- **Objetivo:** El PDF sale en el idioma y las unidades de la UI.
- **Precondiciones:** Idioma inglés, °F y psig; un ciclo completado y uno con falla en el historial.
- **Pasos:**
  1. Exportar el PDF de ambos ciclos y el consolidado.
  2. Revisar cabecera (Units), motivo traducido y gráfica.
- **Resultado esperado:** Textos en inglés; Units "°F, psig"; gráfica de presión en psig en un solo eje; motivo de falla con código y título traducidos.
- **Criterio de aprobado/fallo:** Aprobado si no hay textos en español ni unidades mezcladas (salvo I4-4, documentado).
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-36 — Correo de prueba y de ciclo en inglés

- **Modo:** En seco (sin vapor)  ·  **Origen:** I4 (tanda 6); O2g
- **Objetivo:** Asunto y cuerpo del correo siguen el idioma vigente.
- **Precondiciones:** Como D-32, idioma inglés.
- **Pasos:**
  1. Enviar correo de prueba desde Conectividad.
  2. Enviar un ciclo desde Historial.
- **Resultado esperado:** Asunto y cuerpo en inglés; el PDF adjunto también.
- **Criterio de aprobado/fallo:** Aprobado si ambos correos llegan en inglés.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-37 — Calentamiento: rango de temperatura y de presión por separado

- **Modo:** En seco (sin vapor)  ·  **Origen:** Q1 R1-P3 (tanda 7)
- **Objetivo:** `rango_calentamiento` ya no existe; hay `rango_calentamiento_temp` (°C) y `rango_calentamiento_pres` (kPa), ambos con defecto 2,0 y convertidos como banda.
- **Precondiciones:** Sesión de ingeniero. Copia de un programa de usuario guardado con una versión anterior (con `rango_calentamiento`).
- **Pasos:**
  1. Abrir Opciones › Parámetros del ciclo › Calentamiento de cada programa de fábrica.
  2. Cambiar las unidades a °F y psig y volver a revisar los dos rangos.
  3. Colocar el programa viejo en `cycles/user/`, reiniciar y abrir sus parámetros.
- **Resultado esperado:** Se ven «Rango calentamiento temp» (2,0 °C = 3,6 °F) y «Rango calentamiento pres» (2,0 kPa ≈ 0,29 psi) como bandas (sin desplazamiento). El programa viejo se carga con los dos rangos iguales al valor que tenía y no queda dañado.
- **Criterio de aprobado/fallo:** Aprobado si los dos rangos aparecen, se convierten como banda y la migración copia el valor a los dos.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-R8-01 — Reasignación de E/S: solo ingeniero, fuera de ciclo, conflictos rechazados

- **Modo:** En seco (sin vapor)  ·  **Origen:** R8 (tanda 8, D8-5.12)
- **Objetivo:** Opciones avanzadas solo la ve el ingeniero; no se puede reasignar en ciclo ni con un conflicto o un puerto inexistente.
- **Precondiciones:** Equipo en PREPARADO. Sesiones de técnico, administrador e ingeniero.
- **Pasos:**
  1. Con técnico y con administrador, abrir OPCIONES: no aparece Opciones avanzadas.
  2. Con ingeniero, abrir Opciones avanzadas y revisar la tabla (función, puerto actual, puerto nuevo, tipo, crítica).
  3. Elegir para Vapor cámara el puerto de otra función: la pantalla marca el conflicto y no deja aplicar.
  4. Iniciar un ciclo y volver a Opciones avanzadas.
- **Resultado esperado:** Tabla completa (también las funciones sin uso en este equipo, marcadas). Conflicto visible y Aplicar deshabilitado. En ciclo: aviso «No disponible con un ciclo en curso» y nada editable.
- **Criterio de aprobado/fallo:** Aprobado si ningún rol distinto del ingeniero llega a la pantalla y ninguna reasignación se acepta en ciclo ni con conflicto.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-R8-02 — Reasignar una salida: Vapor cámara de DO 04 a un puerto libre

- **Modo:** En seco (sin vapor)  ·  **Origen:** R8 (tanda 8, D8-5.12)
- **Objetivo:** La salida reasignada se acciona en su puerto nuevo y el equipo no inicia ciclos hasta que el ingeniero la verifica.
- **Precondiciones:** Equipo en PREPARADO, cámara a presión atmosférica, válvula de vapor de cámara con alimentación de vapor CERRADA. Mover el cable de la válvula de DO 04 a un DO libre (p. ej. DO 25).
- **Pasos:**
  1. En Opciones avanzadas elegir el DO libre para Vapor cámara y Aplicar: alerta de criticidad, «Se reiniciará el control», contraseña.
  2. Esperar el reinicio del control y volver a iniciar sesión.
  3. Intentar iniciar un ciclo.
  4. En Entradas / Salidas, modo prueba: encender Vapor cámara y comprobar que actúa la válvula correcta (y que DO 04 no hace nada).
  5. En Opciones avanzadas, Verificar Vapor cámara (contraseña).
  6. Revisar la bitácora.
- **Resultado esperado:** Tras el reinicio: alarma SEN-04 y el ciclo no inicia. Antes de la prueba de salida el botón Verificar está deshabilitado con «Falta: encender esta salida en modo prueba». Tras verificar, SEN-04 desaparece y el ciclo puede iniciar. Bitácora: reasignacion_io (DO 04 → DO 25, usuario), reinicio_control, reasignacion_io_verificada (método ingeniero).
- **Criterio de aprobado/fallo:** Aprobado si la válvula solo actúa por el puerto nuevo y no se pudo iniciar ningún ciclo antes de verificar.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-R8-03 — Reasignar el paro de emergencia: confirmación reforzada y cambio observado

- **Modo:** En seco (sin vapor)  ·  **Origen:** R8 (tanda 8, D8-5.12)
- **Objetivo:** Mover una función de seguridad exige escribir su nombre, y solo se verifica si el control vio cambiar la entrada en su puerto nuevo.
- **Precondiciones:** Equipo en PREPARADO. Mover el cable del paro de emergencia de DI 11 a un DI libre (p. ej. DI 15).
- **Pasos:**
  1. Reasignar Paro de emergencia al DI libre: escribir mal el nombre una vez, luego bien.
  2. Tras el reinicio, intentar Verificar sin accionar el paro.
  3. Pulsar y soltar el paro; Verificar (nombre y contraseña).
  4. Pulsar el paro con el equipo en PREPARADO.
- **Resultado esperado:** Con el nombre mal escrito se rechaza. Sin accionar el paro: «Falta: accionar la entrada». Tras pulsar y soltar, se verifica. Al pulsar el paro: SIS-01 (el paro se lee en su puerto nuevo).
- **Criterio de aprobado/fallo:** Aprobado si el paro funciona en el puerto nuevo y no se pudo verificar sin accionarlo.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-R8-04 — Reasignar una entrada analógica: calibración obligatoria en el puerto nuevo

- **Modo:** En seco (sin vapor)  ·  **Origen:** R8 (tanda 8, D8-5.12)
- **Objetivo:** Una analógica reasignada usa la calibración del puerto nuevo: no se verifica sin calibrarla después de reasignar; un puerto sin calibración se rechaza.
- **Precondiciones:** Equipo en PREPARADO, puerta abierta, patrón de presión. Mover el transmisor de presión de cámara de AI 09 a AI 13.
- **Pasos:**
  1. Intentar reasignar Presión cámara a AI 16.
  2. Reasignar Presión cámara a AI 13 y reiniciar.
  3. Intentar Verificar sin calibrar.
  4. Calibrar Presión cámara en Entradas / Salidas contra el patrón y Verificar.
- **Resultado esperado:** AI 16: rechazo «Ese puerto analógico no tiene calibración». AI 13 sin calibrar: «Falta: calibrar el sensor en su puerto nuevo». Tras calibrar, la lectura coincide con el patrón (± tolerancia de calibración) y se verifica.
- **Criterio de aprobado/fallo:** Aprobado si nunca se pudo dejar la presión de cámara verificada sin calibrarla en el puerto nuevo.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-R8-05 — Restaurar fábrica, respaldo y archivo dañado

- **Modo:** En seco (sin vapor)  ·  **Origen:** R8 (tanda 8, D8-5.12)
- **Objetivo:** La asignación vigente se guarda fuera del ejecutable, va en el respaldo y un archivo dañado bloquea el equipo hasta restaurar la de fábrica.
- **Precondiciones:** Una reasignación aplicada (D-R8-02). Memoria USB.
- **Pasos:**
  1. Exportar un respaldo (con calibración) y comprobar que trae asignacion_io.json.
  2. Restaurar asignación de fábrica (confirmación y contraseña) y volver a mover el cable a DO 04.
  3. Con el control detenido, dañar a mano data/asignacion_io.json (texto cualquiera) y arrancar.
  4. Restaurar asignación de fábrica desde la pantalla.
- **Resultado esperado:** El respaldo incluye la asignación. Tras restaurar fábrica, todo vuelve a su puerto y queda pendiente de verificar lo que cambió. Con el archivo dañado: CONFIGURACION_INVALIDA, sin ciclo; la restauración de fábrica lo resuelve.
- **Criterio de aprobado/fallo:** Aprobado si un archivo dañado nunca hace que el equipo use la de fábrica en silencio.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-39 — Canales de Entradas/Salidas según el perfil de instalación

- **Modo:** En seco (sin vapor)  ·  **Origen:** E1 D8-3.17 (tanda 8)
- **Objetivo:** La lista de canales de E/S sale del perfil (sondas, entradas de suministro, puertas, fuente de vapor), sin editar el YAML a mano.
- **Precondiciones:** Equipo instalado; sesión de técnico. Anotar del resumen del asistente: número y tipo de puertas, fuente de vapor, sondas.
- **Pasos:**
  1. Abrir Opciones › Entradas/Salidas y anotar los canales que aparecen.
  2. Comparar con el perfil: con 1 puerta no deben aparecer los canales de la puerta 2; con generador interno no aparece `vapor_caldera`; sin segunda sonda no aparece `temp_2_camara`.
  3. Revisar las entradas mostradas en Preciclo.
- **Resultado esperado:** Solo aparecen los canales que el perfil declara, en las dos pantallas.
- **Criterio de aprobado/fallo:** Aprobado si no sobra ni falta ningún canal respecto al perfil. Desde la tanda 9 (D9-13.1) un equipo actualizado refresca solo su YAML de fábrica, con respaldo: ver A-E9-02.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

## Bloque E. Ciclos de sólidos (en operación)

### E-01 — Instrumental 134 completo

- **Modo:** En operación (vapor)  ·  **Origen:** §5.3
- **Objetivo:** Un ciclo de sólidos a 134 °C / 7 min termina COMPLETADO con el ticket correcto.
- **Precondiciones:** PREPARADO, chaqueta en banda, puertas cerradas, carga de prueba.
- **Pasos:**
  1. Seleccionar Instrumental 134 e iniciar.
  2. Observar las fases en la pantalla de ciclo en curso.
  3. Al terminar, revisar el ticket.
  4. Abrir la puerta de descarga.
- **Resultado esperado:** Fases: PRECALENTAMIENTO, PREVACIO, CALENTAMIENTO, ESTERILIZACION, DESCOMPRESION, SECADO. COMPLETADO. El ticket muestra la temperatura del Principal. La puerta solo se habilita con la cámara segura.
- **Criterio de aprobado/fallo:** Aprobado si el resultado es COMPLETADO, las curvas son coherentes y la puerta no se pudo abrir antes de la cámara segura.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### E-02 — Instrumental 121 completo

- **Modo:** En operación (vapor)  ·  **Origen:** §5.3; T11
- **Objetivo:** Un ciclo de sólidos a 121 °C / 15 min termina COMPLETADO.
- **Precondiciones:** Como E-01.
- **Pasos:**
  1. Seleccionar Instrumental 121 e iniciar.
  2. Revisar fases, ticket y apertura.
- **Resultado esperado:** Como E-01, con meseta de 15 min a 121 °C.
- **Criterio de aprobado/fallo:** Aprobado si COMPLETADO y coherente.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### E-03 — SECADO alcanza vacío con la bomba y las válvulas cerradas

- **Modo:** En operación (vapor)  ·  **Origen:** T5 §1.6
- **Objetivo:** SECADO (modos 1/2) llega a `atm − rango_presion_atm` dentro de `timeout_pulso`.
- **Precondiciones:** Ciclo con SECADO modo 1 (p. ej. Instrumental 121 o Bowie & Dick).
- **Pasos:**
  1. Durante SECADO, anotar la presión mínima alcanzada y el tiempo.
  2. Verificar que rápida, lenta y chaqueta están cerradas.
  3. Repetir con la bomba desconectada (solo si es seguro).
- **Resultado esperado:** Con bomba: presión bajo ≈ atm − rango (≈70 kPa con atm 75) en < 180 s. Sin bomba: FALLO de SECADO a los `timeout_pulso` s.
- **Criterio de aprobado/fallo:** Aprobado si se alcanza el vacío con bomba y falla sin ella. Avisar si esas válvulas eran necesarias durante el secado.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### E-04 — Vigilar el corte por calidad de vapor del calentamiento

- **Modo:** En operación (vapor)  ·  **Origen:** CLAUDE.md (calentamiento)
- **Objetivo:** El corte "97 % del objetivo sin vapor saturado" no oscila indefinidamente.
- **Precondiciones:** Ciclo de 134 o 121.
- **Pasos:**
  1. Durante CALENTAMIENTO, registrar temperatura, presión y estado de `vapor_camara` cada 5 s en el tramo final.
  2. Comparar presión con P_sat(T).
- **Resultado esperado:** El vapor no queda oscilando entre el 97 % y el objetivo; la transición a ESTABLE/ESTERILIZACION ocurre.
- **Criterio de aprobado/fallo:** Aprobado si no hay oscilación sostenida (> 2 min) cerca del 97 %. Anotar si la sonda es rápida o hay fugas.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### E-05 — NO ABRIR en las dos pantallas con la cámara caliente

- **Modo:** En operación (vapor)  ·  **Origen:** §5.2
- **Objetivo:** Tras un ciclo, ambas pantallas muestran NO ABRIR hasta que la cámara es segura.
- **Precondiciones:** Fin de E-01 o E-02, antes de abrir.
- **Pasos:**
  1. Abrir la campana en las dos pantallas.
  2. Intentar abrir la puerta antes de la cámara segura.
- **Resultado esperado:** NO ABRIR con el motivo en ambas; apertura rechazada hasta cámara segura.
- **Criterio de aprobado/fallo:** Aprobado si no se abre antes de tiempo en ninguna puerta.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### E-06 — Operador del ciclo en ticket, historial y detalle

- **Modo:** En operación (vapor)  ·  **Origen:** O1 (tanda 3)
- **Objetivo:** El usuario con sesión que inicia el ciclo queda registrado.
- **Precondiciones:** Dos ciclos cortos: uno con sesión iniciada en la pantalla (Iniciar sesión) y otro sin sesión.
- **Pasos:**
  1. Con sesión, iniciar un ciclo y dejarlo terminar.
  2. Sin sesión, iniciar otro.
  3. Revisar el ticket impreso, Último ciclo, Historial y la reimpresión.
- **Resultado esperado:** El ciclo con sesión muestra `Operador: <usuario>` en el ticket y el operador en el detalle; el otro deja la línea para firmar y "—". Los ciclos antiguos siguen mostrándose.
- **Criterio de aprobado/fallo:** Aprobado si ambos casos coinciden entre ticket, historial y detalle.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### E-07 — Reconocer un COMPLETADO con la cámara no segura lleva a estado seguro

- **Modo:** En operación (vapor)  ·  **Origen:** T2 P-1 (tanda 6)
- **Objetivo:** Confirmar un ciclo completado con la cámara aún en vacío o caliente no deja abrir la puerta.
- **Precondiciones:** Bowie & Dick terminando con la cámara en vacío (o Principal > temp_max_apertura).
- **Pasos:**
  1. Pulsar CONFIRMAR apenas termina.
  2. Observar fase y salidas.
- **Resultado esperado:** Se ejecuta el protocolo de fallo y pasa a ESTADO SEGURO; la puerta no abre hasta que la cámara sea segura.
- **Criterio de aprobado/fallo:** Aprobado si la puerta nunca abre con la cámara no segura.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### E-R8-01 — Ciclo completo con Vapor cámara y Presión cámara reasignados

- **Modo:** En operación (vapor)  ·  **Origen:** R8 (tanda 8, D8-5.12)
- **Objetivo:** Con funciones reasignadas y verificadas, el ciclo se comporta igual que con la asignación de fábrica.
- **Precondiciones:** D-R8-02 y D-R8-04 aprobados y verificados (cables en los puertos nuevos).
- **Pasos:**
  1. Correr Instrumental 134 completo.
  2. Comparar la gráfica y el ticket con un E-02 de fábrica.
- **Resultado esperado:** Ciclo COMPLETADO; misma forma de la rampa y de la meseta; presión y temperatura coherentes con P_sat.
- **Criterio de aprobado/fallo:** Aprobado si el ciclo termina COMPLETADO y los registros son equivalentes a los de fábrica.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### E-08 — Calentamiento con los rangos separados: sin cambio de comportamiento

- **Modo:** En operación (vapor)  ·  **Origen:** Q1 R1-P3 (tanda 7)
- **Objetivo:** Con los dos rangos en 2,0 (defecto) la rampa se comporta igual que con el `rango_calentamiento` anterior.
- **Precondiciones:** Instrumental 134 con los rangos de fábrica. Registro de un ciclo previo con la versión anterior, si existe.
- **Pasos:**
  1. Correr el ciclo completo.
  2. Comparar la curva de calentamiento y el sobrepaso con el registro previo.
- **Resultado esperado:** COMPLETADO; misma forma de rampa y sobrepaso que antes (el duty cae a 0 al pasar 2 °C o 2 kPa sobre el objetivo).
- **Criterio de aprobado/fallo:** Aprobado si el ciclo completa y no hay sobrepaso mayor que con la versión anterior.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

## Bloque F. Fallas durante el ciclo (en operación)

### F-01 — Paro de emergencia durante el ciclo

- **Modo:** En operación (vapor)  ·  **Origen:** B-01 en ciclo
- **Objetivo:** El paro en ciclo aborta, apaga salidas y lleva a estado seguro tras confirmar.
- **Precondiciones:** Ciclo en ESTERILIZACION.
- **Pasos:**
  1. Pulsar el paro.
  2. Esperar 30 s.
  3. Soltar y confirmar el estado seguro.
- **Resultado esperado:** Salidas apagadas al instante; resultado EMERGENCIA; tras confirmar, el protocolo ventea y enfría; NO ABRIR hasta cámara segura.
- **Criterio de aprobado/fallo:** Aprobado si ninguna salida queda encendida con el paro y la cámara llega a segura.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### F-02 — Pérdida de comunicación durante el ciclo

- **Modo:** En operación (vapor)  ·  **Origen:** §5.10 (T1)
- **Objetivo:** Desconectar la tarjeta en ciclo da COM-03 y la tarjeta queda en ALL_OFF.
- **Precondiciones:** Ciclo en CALENTAMIENTO.
- **Pasos:**
  1. Desconectar el USB 5 s.
  2. Reconectar.
  3. Revisar alarmas y resultado.
- **Resultado esperado:** COM-03 con su causa; el ciclo termina en FALLO_IO; la tarjeta apaga salidas por su watchdog; al reconectar, estado seguro.
- **Criterio de aprobado/fallo:** Aprobado si las salidas se apagan sin el PC y el ciclo no sigue "a ciegas".
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### F-03 — Corte de energía durante el ciclo

- **Modo:** En operación (vapor)  ·  **Origen:** §5.1 (T6)
- **Objetivo:** Un ciclo interrumpido por corte queda como INTERRUMPIDO y el arranque es seguro.
- **Precondiciones:** Ciclo en ESTERILIZACION.
- **Pasos:**
  1. Cortar la energía (PC y tarjeta).
  2. Restaurar y arrancar.
  3. Revisar el historial y el ticket.
- **Resultado esperado:** El ciclo aparece como INTERRUMPIDO; ALL_OFF al conectar; con cámara no segura, pide confirmación de estado seguro.
- **Criterio de aprobado/fallo:** Aprobado si nada se enciende solo y el registro queda INTERRUMPIDO.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### F-04 — Puerta abierta durante el ciclo = FALLO

- **Modo:** En operación (vapor)  ·  **Origen:** tanda 2 §1
- **Objetivo:** Con puertas manuales, perder el sensor de cerrada en ciclo provoca FALLO.
- **Precondiciones:** Ciclo en PREVACIO (presión baja, seguro de simular). NO hacerlo con presión positiva.
- **Pasos:**
  1. Desconectar el cable del sensor de cerrada de la puerta 1 (simula puerta abierta).
- **Resultado esperado:** FALLO del ciclo con el motivo de puerta; protocolo de fallo.
- **Criterio de aprobado/fallo:** Aprobado si el ciclo falla de inmediato (debounce).
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### F-05 — Sonda Principal perdida en ciclo: FALLO con escape solo por la lenta

- **Modo:** En operación (vapor)  ·  **Origen:** T2 P-2 (tanda 6)
- **Objetivo:** Sin Principal, el equipo ventila solo por la lenta y no permite un nuevo ciclo.
- **Precondiciones:** Ciclo de Instrumental 134 en esterilización.
- **Pasos:**
  1. Desconectar la sonda Principal.
  2. Observar salidas y alarma CIC-10.
  3. Confirmar la falla e intentar iniciar otro ciclo.
- **Resultado esperado:** FALLO; solo `descompresion_lenta` abre (sin rápida, chaqueta ni contrapresión); CIC-10 activa mientras no lea; inicio rechazado con "Sonda principal sin lectura: llame a servicio".
- **Criterio de aprobado/fallo:** Aprobado si la rápida no abre y no inicia otro ciclo.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### F-06 — Trama de la tarjeta vencida en ciclo: tolerancia de 4 s

- **Modo:** En operación (vapor)  ·  **Origen:** T2 P-3 (tanda 6)
- **Objetivo:** Un corte breve de la tarjeta corta el vapor y uno largo termina en FALLO_CONEXION.
- **Precondiciones:** Ciclo en calentamiento o esterilización.
- **Pasos:**
  1. Desconectar el USB de la tarjeta menos de 4 s y reconectar.
  2. Repetir dejándolo más de 4 s.
- **Resultado esperado:** Corte breve: vapor de cámara y chaqueta en OFF durante el corte; el ciclo sigue. Corte largo: `FALLO_CONEXION` + COM-03, sin abrir válvulas.
- **Criterio de aprobado/fallo:** Aprobado si el vapor nunca sigue sin trama vigente.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### F-07 — Paro con el ciclo terminando: diálogo de estado seguro al CONFIRMAR

- **Modo:** En operación (vapor)  ·  **Origen:** T2 P-6 (tanda 6)
- **Objetivo:** El operador ve la advertencia de §15.2 antes de llevar el equipo a estado seguro.
- **Precondiciones:** Ciclo en descompresión o secado.
- **Pasos:**
  1. Pulsar el paro de emergencia y liberarlo.
  2. Pulsar CONFIRMAR.
- **Resultado esperado:** Diálogo con el texto de verificar fugas y botón "Confirmar y llevar a estado seguro".
- **Criterio de aprobado/fallo:** Aprobado si el diálogo aparece y el estado seguro se inicia solo tras aceptarlo.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### F-08 — Sin datos de la tarjeta en esterilización: la exposición se alarga

- **Modo:** En operación (vapor)  ·  **Origen:** Q1 T2-a (tanda 7)
- **Objetivo:** Los segundos de tolerancia por DI vencida no cuentan como exposición y quedan en el ticket.
- **Precondiciones:** Bowie & Dick o Instrumental 134 en esterilización (cronometrar desde el inicio de la fase).
- **Pasos:**
  1. Desconectar el USB de la tarjeta unos 2-3 s (menos de 4 s) y reconectar.
  2. Dejar terminar el ciclo y anotar la duración real de la esterilización.
  3. Revisar el pie del ticket.
- **Resultado esperado:** La esterilización dura el tiempo programado más los segundos sin datos; el vapor estuvo en OFF durante el corte; el pie dice "Sin datos de la tarjeta: n s" y el ciclo queda COMPLETADO (sin marca de no estéril).
- **Criterio de aprobado/fallo:** Aprobado si la duración se alarga en los segundos del corte (± 1 s) y el ticket los anota.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### F-09 — CARGA NO ESTÉRIL en todo ciclo que no termine COMPLETADO

- **Modo:** En operación (vapor)  ·  **Origen:** Q1 T2-c (tanda 7)
- **Objetivo:** El ticket marca la carga como no estéril en FALLO, CANCELADO, paro de emergencia e INTERRUMPIDO.
- **Precondiciones:** Tickets de F-01 (cancelación), F-02 (paro), F-03 (falla) y del ciclo INTERRUMPIDO de C-05; idioma español y luego inglés.
- **Pasos:**
  1. Revisar el pie de cada ticket impreso en vivo.
  2. Reimprimir cada uno desde Historial, también en inglés.
  3. Revisar el ticket de un ciclo COMPLETADO.
- **Resultado esperado:** Todos los no completados llevan "*** CARGA NO ESTÉRIL ***" ("*** LOAD NOT STERILE ***" en inglés), en vivo y al reimprimir; el COMPLETADO no la lleva.
- **Criterio de aprobado/fallo:** Aprobado si ningún ticket de ciclo no completado sale sin la marca.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### F-10 — Principal perdido con el protocolo de fallo ya en marcha: pasa a solo la lenta

- **Modo:** En operación (vapor)  ·  **Origen:** Q1 R1-P4 (tanda 7)
- **Objetivo:** Si se cancela (o falla) y después se pierde la sonda Principal, el escape sigue solo por la lenta.
- **Precondiciones:** Instrumental 134 en esterilización.
- **Pasos:**
  1. Cancelar el ciclo y esperar unos segundos (protocolo de fallo en marcha).
  2. Desconectar la sonda Principal.
  3. Observar salidas y CIC-10; confirmar y revisar si pasa a PREPARACION sin técnico.
- **Resultado esperado:** Al perder la Principal se cierran rápida, chaqueta y contrapresión y queda solo `descompresion_lenta`; CIC-10 activa; el reconocimiento lleva a PREPARACION sin técnico; inicio bloqueado mientras no lea.
- **Criterio de aprobado/fallo:** Aprobado si la rápida no vuelve a abrir tras perder la Principal.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### F-11 — Cancelar durante la tolerancia por DI vencida

- **Modo:** En operación (vapor)  ·  **Origen:** Q1 R1-P5 (tanda 7)
- **Objetivo:** La cancelación pedida mientras la tarjeta no manda entradas se acepta y se aplica al volver los datos.
- **Precondiciones:** Ciclo en esterilización.
- **Pasos:**
  1. Desconectar el USB de la tarjeta y, antes de 4 s, pulsar Cancelar.
  2. Reconectar enseguida.
  3. Repetir dejándolo desconectado más de 4 s.
- **Resultado esperado:** La cancelación se acepta (sin el rechazo "sin datos de la tarjeta"); al volver los datos el ciclo queda CANCELADO. Si no vuelven a tiempo, termina en FALLO_CONEXION.
- **Criterio de aprobado/fallo:** Aprobado si en ningún caso el ciclo sigue corriendo después de la cancelación.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### F-12 — Desconexión total breve de la tarjeta en esterilización: la exposición se alarga y no suma F0

- **Modo:** En operación (vapor)  ·  **Origen:** S2a D8-2.7 (tanda 8)
- **Objetivo:** Los segundos con el USB desconectado (menos de 5 s) y la ventana tras reconectar no cuentan como esterilización ni como F0.
- **Precondiciones:** Programa con F0 activo (o Instrumental 134) en esterilización; cronometrar desde el inicio de la fase y anotar el F0 en pantalla.
- **Pasos:**
  1. Desconectar el USB de la tarjeta unos 3 s y reconectar (antes de que salga COM-02).
  2. Dejar terminar el ciclo; anotar la duración real de la esterilización y el F0 final.
  3. Revisar el pie del ticket.
- **Resultado esperado:** La esterilización dura lo programado más los segundos sin datos (corte + ventana de reconexión, hasta ~2 s más por la vigencia de la última trama); el F0 no sube durante el corte; el pie dice "Sin datos de la tarjeta: n s"; COMPLETADO.
- **Criterio de aprobado/fallo:** Aprobado si la duración se alarga al menos los segundos del corte y el F0 no aumenta mientras no hay datos.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### F-13 — Cortes repetidos en una esterilización: falla por comunicación inestable (CIC-11)

- **Modo:** En operación (vapor)  ·  **Origen:** S2a D8-2.8 (tanda 8)
- **Objetivo:** Si las pausas por falta de datos suman más de pausa_max_esterilizacion_s (30 s por defecto), el ciclo falla con CIC-11.
- **Precondiciones:** Instrumental 134 en esterilización; pausa_max_esterilizacion_s = 30 s (OPCIONES › Parámetros del equipo).
- **Pasos:**
  1. Desconectar el USB unos 3 s y reconectar; esperar 5 s; repetir hasta sumar más de 30 s de cortes.
  2. Repetir con cortes muy cortos y seguidos (desconectar/reconectar sin esperar).
- **Resultado esperado:** Al superar 30 s acumulados el ciclo termina en FALLO con "Comunicación inestable en esterilización" (CIC-11) y el ticket lleva CARGA NO ESTÉRIL; con cortes seguidos (sin que llegue COM-02) también falla al pasar el tope.
- **Criterio de aprobado/fallo:** Aprobado si nunca termina COMPLETADO con más de 30 s de pausas.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### F-15 — Líquidos: se pierde el Principal en el enfriamiento con contrapresión — cámara sellada

- **Modo:** En operación (vapor)  ·  **Origen:** S2a D8-2.10 (tanda 8)
- **Objetivo:** No se ventea de inmediato: todo cerrado mientras la Referencia esté caliente; con la Referencia en o bajo temp_max_apertura (3 lecturas), la lenta.
- **Precondiciones:** Programa Líquidos (modo 4) con la Referencia asignada (OPCIONES › Parámetros del ciclo › Sensores) y en la carga; ciclo en DESCOMPRESION, enfriamiento con contrapresión.
- **Pasos:**
  1. Desconectar la sonda Principal.
  2. Observar las salidas 5-10 min (y la presión de cámara).
  3. Llevar la Referencia a menos de temp_max_apertura (p. ej. sacarla y meterla en agua fría) y observar.
- **Resultado esperado:** SENSOR_AUSENTE; cierran aire comprimido, agua de chaqueta, chaqueta, lenta, rápida y vapor; CIC-10 "cámara sellada…"; ninguna válvula abre con la Referencia caliente (salvo alivio por sobrepresión); con la Referencia fría abre solo la lenta; NO ABRIR sigue; FALLA sale sin técnico.
- **Criterio de aprobado/fallo:** Aprobado si no se ventea con la Referencia caliente y la rápida nunca abre. Anotar cuánto baja la presión sellada (PREGUNTA de contrapresión).
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### F-16 — Líquidos sin Referencia: espera sellada sin sonda y luego la lenta

- **Modo:** En operación (vapor)  ·  **Origen:** S2a D8-2.10 (tanda 8)
- **Objetivo:** Sin ninguna Referencia válida (el drenaje solo no cuenta para ventear), la cámara espera sellada espera_sellado_sin_sonda_min y luego ventea por la lenta.
- **Precondiciones:** Programa Líquidos con la asignación de fábrica (sin Referencia); espera_sellado_sin_sonda_min = 10 min para acortar la prueba.
- **Pasos:**
  1. En el enfriamiento con contrapresión, desconectar la sonda Principal.
  2. Cronometrar hasta que abra la lenta.
- **Resultado esperado:** Todo cerrado durante 10 min (aunque el drenaje lea frío); a los 10 min abre solo la lenta.
- **Criterio de aprobado/fallo:** Aprobado si la lenta abre a los 10 min (± 1 tick) y no antes.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### F-17 — Ventana de estabilidad en pausa durante la tolerancia por DI vencida

- **Modo:** En operación (vapor)  ·  **Origen:** S2b D8-2.12 (tanda 8)
- **Objetivo:** Los segundos sin datos de la tarjeta no cuentan en la ventana de estabilidad previa a la esterilización (ni en el hold del prevacío ni en el secado); los tiempos límite de fase sí siguen.
- **Precondiciones:** Ciclo Instrumental 134 en curso; sesión de técnico para ver el log.
- **Pasos:**
  1. Esperar a que el calentamiento llegue al tramo estable (log: ventana de estabilidad abierta).
  2. Provocar 2-3 s sin datos de la tarjeta (desconectar y reconectar el USB antes de 4 s).
  3. Dejar terminar el ciclo.
- **Resultado esperado:** Log: "ventana _timer_sostenido_desde en pausa n s"; sin vapor durante el tramo; el ciclo termina COMPLETADO y el ticket dice "Sin datos de la tarjeta: n s".
- **Criterio de aprobado/fallo:** Aprobado si la ventana se alarga lo que duró el tramo y el ciclo no se da por estable con segundos sin datos.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### F-18 — Cancelar con la tarjeta totalmente desconectada: texto en pantalla

- **Modo:** En operación (vapor)  ·  **Origen:** S2b D8-2.13 y D8-2.15 (tanda 8); complementa F-11
- **Objetivo:** Con la tarjeta desconectada (antes de COM-02) la cancelación se acepta en espera y la pantalla lo explica con el texto del catálogo.
- **Precondiciones:** Ciclo en esterilización.
- **Pasos:**
  1. Desconectar el USB de la tarjeta y, antes de 5 s, pulsar CANCELAR CICLO y confirmar.
  2. Leer el aviso de la pantalla y reconectar enseguida.
  3. Repetir dejándolo desconectado más de 5 s.
- **Resultado esperado:** Aviso: "Cancelación aceptada: se aplicará cuando vuelvan los datos de la tarjeta de control..." (no un error ni un texto técnico); al volver los datos, CANCELADO. Sin reconectar a tiempo, FALLO_CONEXION.
- **Criterio de aprobado/fallo:** Aprobado si el aviso sale con ese texto y el ciclo nunca sigue corriendo tras la cancelación.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### F-19 — Reimpresión idéntica al ticket original (avisos del pie)

- **Modo:** En operación (vapor)  ·  **Origen:** S2b D8-2.14 (tanda 8)
- **Objetivo:** La reimpresión desde el Historial trae las mismas líneas de aviso del pie que el ticket impreso en vivo.
- **Precondiciones:** Ciclo con un tramo sin datos de la tarjeta (F-17) y, si el equipo tiene sensores de referencia, con un aviso de uniformidad.
- **Pasos:**
  1. Guardar el ticket impreso en vivo.
  2. Reimprimir el mismo ciclo desde el Historial.
  3. Comparar los pies.
- **Resultado esperado:** Ambos traen "Sin datos de la tarjeta: n s", los avisos de uniformidad y (si el ciclo tenía F0) "F0 total". Los ciclos anteriores a esta versión se reimprimen como antes.
- **Criterio de aprobado/fallo:** Aprobado si el pie reimpreso es idéntico al original.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### F-20 — CARGA NO ESTÉRIL en la pantalla de resultado

- **Modo:** En operación (vapor)  ·  **Origen:** S2b D8-2.16 (tanda 8)
- **Objetivo:** La pantalla de resultado del ciclo marca "CARGA NO ESTÉRIL" en todo ciclo que no termine COMPLETADO.
- **Precondiciones:** Programa corto de prueba.
- **Pasos:**
  1. Terminar un ciclo completo y mirar la pantalla de resultado.
  2. Cancelar otro ciclo y mirar la pantalla.
  3. Provocar un fallo (p. ej. desconexión mayor de 5 s) y mirar la pantalla.
- **Resultado esperado:** Ciclo completo: sin la marca. Cancelado y fallo: recuadro rojo "CARGA NO ESTÉRIL" sobre la gráfica, igual que en el ticket.
- **Criterio de aprobado/fallo:** Aprobado si la marca aparece exactamente en los ciclos no completados.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

## Bloque G. Líquidos (en operación, al final)

### G-01 — Líquidos con la sonda dentro del líquido

- **Modo:** En operación (vapor)  ·  **Origen:** §5.4; T11; HAZ-LIQ-01
- **Objetivo:** El programa Líquidos (121 °C / 15 min, sin prevacío ni secado) enfría con contrapresión hasta 80 °C antes de la rápida.
- **Precondiciones:** Frascos de vidrio con agua, volumen conocido; sonda flexible Principal (Cámara 1) DENTRO del líquido del frasco de mayor volumen; aire comprimido conectado.
- **Pasos:**
  1. Seleccionar Líquidos e iniciar.
  2. Verificar que no hay prevacío.
  3. Registrar temperatura del Principal y presión durante el enfriamiento.
  4. Verificar que la rápida (despresurización final) solo actúa con el Principal ≤ 80 °C.
  5. Al terminar, revisar que ningún frasco hirvió o se rompió.
- **Resultado esperado:** Esterilización con el Principal en 121 °C; enfriamiento con contrapresión (≈250 kPa); despresurización final solo ≤ 80 °C; sin secado; apertura solo ≤ 80 °C.
- **Criterio de aprobado/fallo:** Aprobado si no hay ebullición/rotura y la secuencia respeta 80 °C. Registrar el aire residual sin prevacío (diferencia T vs P_sat al inicio de la meseta).
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### G-02 — Líquidos: tras confirmar un ciclo completado con presión, se ventea por la LENTA

- **Modo:** En operación (vapor)  ·  **Origen:** T1-01 (tanda 5, D-19)
- **Objetivo:** Con carga líquida, PREPARADO/PREPARACION nunca abren la descompresión rápida por sobrepresión.
- **Precondiciones:** Ciclo de Líquidos completado y confirmado con la cámara aún sobre la banda atmosférica.
- **Pasos:**
  1. Observar las salidas al volver a PREPARADO.
  2. Esperar a que la presión llegue a la banda.
- **Resultado esperado:** Abre `descompresion_lenta`, nunca `descompresion_rapida`; al llegar a la banda la lenta se cierra.
- **Criterio de aprobado/fallo:** Aprobado si la rápida no se abre en ningún momento.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### G-03 — Líquidos: drenaje a atmosférica por la lenta hasta temp_max_apertura

- **Modo:** En operación (vapor)  ·  **Origen:** T2 P-12 (tanda 6)
- **Objetivo:** La rápida solo abre con el Principal en o bajo `temp_max_apertura` 3 lecturas seguidas.
- **Precondiciones:** Ciclo de Líquidos terminado, PREPARACION con presión residual y Principal > 80 °C.
- **Pasos:**
  1. Observar las salidas mientras enfría.
  2. Anotar la temperatura a la que abre la rápida.
- **Resultado esperado:** Solo la lenta mientras el Principal esté > 80 °C (o sin lectura); la rápida después de 3 lecturas ≤ 80 °C.
- **Criterio de aprobado/fallo:** Aprobado si la rápida nunca abre por encima de 80 °C.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### G-04 — Tipo de carga en Parámetros del ciclo: Líquido arrastra el modo de descompresión

- **Modo:** En seco  ·  **Origen:** V8a D8-5.7 (tanda 8); HAZ-V8A-01
- **Objetivo:** Al pasar un programa a carga Líquido, el modo de descompresión pasa a 4 con aviso; con Líquido solo se aceptan los modos 4, 5 y 0; al volver a Sólido se recupera el modo de fábrica del programa (o el 1). Cada cambio queda en la bitácora.
- **Precondiciones:** Sesión de técnico o ingeniero; sin ciclo en curso; un programa sólido con modo de descompresión 1.
- **Pasos:**
  1. Opciones › Parámetros del ciclo › programa › tipo de carga: elegir Líquido.
  2. Verificar el aviso en pantalla y que el modo de descompresión quedó en 4.
  3. Con Líquido, intentar elegir el modo 1 (o 2/3).
  4. Volver a Sólido.
  5. Revisar la bitácora.
- **Resultado esperado:** Paso 2: aviso «Carga líquida: el modo de descompresión cambió a 4 (…)». Paso 3: la lista solo ofrece 4, 5 y 0; si se fuerza, el backend rechaza con su motivo (ebullición violenta). Paso 4: modo de fábrica del programa o el 1. Paso 5: una fila por cambio, incluido el automático.
- **Criterio de aprobado/fallo:** Aprobado si en ningún momento un programa Líquido queda con un modo distinto de 4, 5 o 0.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

## Bloque E9. Entrega, actualización y verificaciones de la tanda 9 (en seco)

### A-E9-01 — Instalación limpia de la D: modo de descompresión 5 en los 4 programas y entrega sin datos del banco

- **Modo:** En seco (sin vapor)  ·  **Origen:** E9 D9-8 (H14) y D9-7 (H17) (tanda 9)
- **Objetivo:** En la B, la primera instalación solo ofrecía hasta el modo 4 de descompresión (después, en configuración, sí dejaba el 5). En la D la lista de Parámetros del ciclo ofrece 0 a 5 (con carga Líquido: 4, 5 y 0) desde la primera instalación. Además, la entrega no trae datos del banco: correo sin remitente ni destinatarios y programas iguales a los de fábrica.
- **Precondiciones:** PC de prueba o equipo SIN instalación previa (sin `C:\ProgramData\Especifika\Autoclave`, o apartada y respaldada). Setup de la D (`Autoclave_Setup_1.0.0-d.exe`). Sesión de técnico o ingeniero. Sin ciclo en curso.
- **Pasos:**
  1. Instalar con el Setup y completar el asistente de instalación del equipo.
  2. Opciones › Parámetros del ciclo › Instrumental 134 › Descompresión › modo: abrir la lista y anotar los modos ofrecidos.
  3. Elegir el modo 5, guardar, salir y volver a entrar: el valor sigue en 5. Devolverlo a su valor original.
  4. Repetir 2 y 3 con Instrumental 121, Bowie-Dick y Líquidos (en Líquidos la lista ofrece 4, 5 y 0).
  5. Anotar el modo de descompresión con el que viene cada programa (instalación limpia: el de fábrica; el Bowie-Dick NO debe venir en 4).
  6. Opciones › Conectividad: revisar los destinatarios del correo.
- **Resultado esperado:** Pasos 2 y 4: la lista ofrece el 5 en los 4 programas desde la primera instalación. Paso 3: el 5 se guarda y queda en la bitácora. Paso 5: los 4 programas con los valores de fábrica. Paso 6: sin destinatarios precargados y el correo sin configurar (no aparece ninguna dirección de Especifika).
- **Criterio de aprobado/fallo:** Aprobado si el modo 5 se puede elegir y guardar en los 4 programas tras una instalación limpia y no aparece ningún dato del banco. **Si solo se ofrece hasta el 4: tomar captura de la lista y del programa, anotar la versión (Información del sistema) y avisar a Code (D9-8 pide investigarlo).**
- **Modos ofrecidos:** 134 ______ · 121 ______ · Bowie-Dick ______ · Líquidos ______
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### A-E9-02 — Actualización B → D con el Setup, sin copiar archivos a mano

- **Modo:** En seco (sin vapor)  ·  **Origen:** E9 D9-13.1 (tanda 9)
- **Objetivo:** Al instalar la D encima de la B, la D refresca sola sus archivos de configuración de fábrica (`instances\*.yaml` y `global_params.json`), con respaldo con fecha, y aparecen la Cámara 2 y la descompresión lenta sin ningún paso manual. Nada del sitio cambia.
- **Precondiciones:** Equipo de pruebas con la B instalada y su perfil (2 puertas, cámara 1 y 2, referencia y drenaje). Anotar antes: destinatarios del correo, un valor de Parámetros del equipo cambiado en el sitio (por ejemplo, `temp_max_apertura`), el modo de descompresión del Bowie-Dick y un ajuste de calibración. Software cerrado. Respaldo de `C:\ProgramData\Especifika\Autoclave` en una USB.
- **Pasos:**
  1. Ejecutar el Setup de la D (doble clic) sobre la B. No copiar ningún archivo a mano.
  2. Abrir Autoclave (o reiniciar si el Setup lo pide).
  3. Opciones › Entradas/Salidas: buscar Cámara 2 (`temp_2_camara`) y Descompresión lenta (`descompresion_lenta`).
  4. Revisar en `C:\ProgramData\Especifika\Autoclave\programa\respaldos_configuracion\` la carpeta con fecha y hora de la actualización.
  5. Comparar con lo anotado en las precondiciones.
- **Resultado esperado:** Paso 3: los dos canales aparecen. Paso 4: una carpeta `AAAA-MM-DD_HHMMSS` con `autoclave\config\global_params.json` e `instances\ACV-2026-001.yaml` de la B (nada más). Paso 5: perfil, usuarios, correo, Parámetros del equipo, calibración y programas de usuario iguales a los de la B. **Ojo:** el Bowie-Dick conserva el modo que tenía en la B (los programas de usuario de un equipo ya instalado no se tocan; D9-7 solo cambia lo que trae una instalación nueva).
- **Criterio de aprobado/fallo:** Aprobado si los dos canales aparecen sin pasos manuales y no cambió ningún dato del sitio.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-E9-01 — Sin transductores conectados: la presión se muestra «—», nunca 0

- **Modo:** En seco (sin vapor)  ·  **Origen:** E9; H4 resuelto en S1 D8-1.1 (tanda 8). Complementa D-38 (que mide las cuentas ADC).
- **Objetivo:** Con el equipo de pruebas sin sensores conectados (como en el hallazgo H4), la presión de cámara y de chaqueta nunca se muestra ni se usa como 0 kPa.
- **Precondiciones:** Tarjeta conectada, transductores de presión desconectados. Sesión de técnico.
- **Pasos:**
  1. Arrancar el software y esperar unos segundos.
  2. Revisar la presión de cámara y de chaqueta en el Menú principal, en Preciclo y en Opciones › Entradas/Salidas, en las dos pantallas.
  3. Cambiar las unidades a psig y repetir el paso 2; volver a kPa.
- **Resultado esperado:** En todos los lugares «—» (o «---»), nunca 0,0 ni un número; alarma de sensor de presión sin lectura con «llame a servicio».
- **Criterio de aprobado/fallo:** Aprobado si en ninguna pantalla ni unidad aparece un valor numérico de presión sin transductor.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-E9-02 — Carga Líquido: el modo de descompresión no válido muestra su motivo

- **Modo:** En seco (sin vapor)  ·  **Origen:** E9; H13 resuelto en D8-5.7 y D8-5.8 (tanda 8). Complementa G-04.
- **Objetivo:** Con carga Líquido, el modo de descompresión se elige de una lista con los modos válidos y su descripción, y un modo no válido se rechaza mostrando por qué (no un error genérico).
- **Precondiciones:** Sesión de técnico o ingeniero; sin ciclo en curso; programa Líquidos.
- **Pasos:**
  1. Opciones › Parámetros del ciclo › Líquidos › Descompresión › modo: abrir la lista.
  2. Comprobar que cada modo trae su descripción y que solo se ofrecen 4, 5 y 0.
  3. Si la pantalla permite intentar otro modo (por ejemplo, desde un programa sólido cambiando el tipo de carga), anotar el texto del rechazo.
- **Resultado esperado:** Lista con descripción; un modo no válido con Líquido se rechaza con su motivo (riesgo de ebullición violenta), en el idioma vigente.
- **Criterio de aprobado/fallo:** Aprobado si nunca aparece un rechazo sin motivo ni un modo distinto de 4, 5 o 0 con carga Líquido.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-E9-03 — Entradas/Salidas solo con los canales del perfil (equipo sin sensores)

- **Modo:** En seco (sin vapor)  ·  **Origen:** E9; H16 resuelto en D8-3.17 (tanda 8). Complementa D-39.
- **Objetivo:** En el equipo de pruebas, Opciones › Entradas/Salidas muestra solo los canales que declara el perfil de instalación, aunque no haya sensores conectados.
- **Precondiciones:** Equipo instalado con el perfil del equipo de pruebas (2 puertas simples, cámara 1 y 2, referencia y drenaje, solo aire comprimido, generador). Sesión de técnico.
- **Pasos:**
  1. Abrir Opciones › Entradas/Salidas y anotar las entradas analógicas, las digitales y las salidas.
  2. Comparar con el perfil.
- **Resultado esperado:** Entradas analógicas: `temp_camara`, `temp_2_camara`, `temp_referencia`, `temp_drenaje`, `pres_camara`, `pres_chaqueta`. Sin `temp_drenaje_camara`, `pres_empaque_1/2` ni `vapor_caldera`. Salidas con `descompresion_lenta` y `buzer_alarma`. (Lista obtenida en el ensayo B → D de E9 con ese perfil.)
- **Criterio de aprobado/fallo:** Aprobado si no sobra ni falta ningún canal respecto al perfil.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-X9-01 — Cambio de un parámetro con el ciclo en curso: bitácora antes de aplicar

- **Modo:** En operación (o con la planta simulada)  ·  **Origen:** X9 D9-13.3 (tanda 9); HAZ-X9-01
- **Objetivo:** Un cambio de parámetro hecho por el ingeniero con el ciclo en curso queda primero en la bitácora y solo después llega al ciclo en curso (si su fase no ha iniciado). Si la bitácora no se puede escribir, ni el programa ni el ciclo en curso cambian. El cambio del tipo de carga y su arrastre del modo de descompresión quedan juntos en la bitácora (todo o nada).
- **Precondiciones:** Sesión de ingeniero; ciclo en curso en CALENTAMIENTO con un programa de usuario.
- **Pasos:**
  1. Opciones › Parámetros del ciclo › programa en curso › Secado: cambiar el tiempo de secado.
  2. Revisar la respuesta en pantalla ("aplica al ciclo en curso") y la bitácora.
  3. Cambiar un parámetro de Calentamiento (fase ya iniciada).
  4. Fuera de ciclo, en un programa sólido, pasar el tipo de carga a Líquido y revisar la bitácora.
- **Resultado esperado:** Paso 2: una fila «cambió …/secado/tiempo_secado» con «aplica: en_curso»; el ticket del ciclo usa el valor nuevo en el secado. Paso 3: rige desde el siguiente ciclo; el ciclo en curso no cambia. Paso 4: dos filas (el cambio y el automático del modo) con la misma hora.
- **Criterio de aprobado/fallo:** Aprobado si ningún valor llega al ciclo en curso sin su fila en la bitácora y las filas del cambio y del arrastre aparecen siempre juntas.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### D-X9-02 — Interfaz en inglés: ticket, reimpresión y motivo de fallo en inglés

- **Modo:** En seco (sin vapor)  ·  **Origen:** X9 D9-13.4 (tanda 9); HAZ-X9-02
- **Objetivo:** Con el idioma en inglés, el ticket en vivo, la reimpresión desde el Historial y el motivo de fallo de una fase (alarma, Historial, PDF) salen en inglés y en las unidades vigentes. En español el ticket queda igual que antes.
- **Precondiciones:** Impresora térmica conectada; un ciclo fallado en el Historial (por ejemplo, cancelado o un FALLO de ensayo); unidades °F y psi en una segunda pasada.
- **Pasos:**
  1. Opciones › Idioma: English. Reimprimir desde el Historial el ciclo fallado.
  2. Abrir el detalle del ciclo y su motivo; generar el PDF.
  3. Cambiar a °F / psi y repetir el paso 2.
  4. Volver a Español y reimprimir.
- **Resultado esperado:** Paso 1: «Status: FAILED (…)» con la fase en inglés, «Reason: CIC-0x - … failure», rótulos en inglés (abreviaturas permitidas solo en el ticket). Paso 2: el motivo en inglés (por ejemplo «High temperature: …»). Paso 3: los valores del motivo en °F / psi. Paso 4: el ticket en español igual que antes.
- **Criterio de aprobado/fallo:** Aprobado si con la interfaz en inglés no aparece texto en español en el ticket ni en el motivo de fallo de las fases (salvo nombres propios de programas creados en el hospital) y los valores coinciden con los del ciclo.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

## Registros que se deben conservar (expediente IEC 62304)

- Esta hoja firmada (cada prueba con valor observado, resultado y firma).
- `installation_profile.json` instalado (copia) y fecha de instalación.
- Exportación de `audit_log` y del historial de ciclos de la sesión de pruebas (base `data/` o respaldo JSONL de `data/respaldo_ciclos/`).
- Tickets impresos (o PDF) de cada ciclo E-01, E-02, E-03, E-06, F-01, F-02, F-03, G-01.
- Gráficas de cada ciclo (captura de la pantalla de ciclo en curso o del Historial).
- Log del backend (`logs/`) del día de pruebas.
- Versión del software (commit) y del firmware (Información del sistema) usados.
- Certificados de calibración de los patrones de temperatura y presión usados.
- Lista de desviaciones/no conformidades encontradas, con su informe de problema (IEC 62304 §9).

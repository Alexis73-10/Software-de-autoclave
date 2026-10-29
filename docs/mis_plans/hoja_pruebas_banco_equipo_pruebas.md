# Hoja de pruebas de banco — equipo de pruebas

> Generado desde `docs/mis_plans/hoja_pruebas_banco/pruebas.py` (editar ahí y regenerar con `generar.py`). Versión imprimible: `hoja_pruebas_banco_equipo_pruebas.html`.

- Equipo de pruebas: autoclave de laboratorio, 2 puertas abatibles manuales, generador interno (sin DO1/DO2), sondas Cámara 1, Cámara 2, Referencia y drenaje.
- Origen: tanda 2 (P1, E7). Reúne las 11 comprobaciones manuales de `docs/informes/informe_tanda_2026-10-14.md` §5 y las de la tanda 2 (`docs/informes/tanda2/`).
- Valores de los programas de fábrica (provisionales, por validar aquí): Bowie & Dick 134 °C / 3,5 min; Instrumental 134 °C / 7 min; Instrumental 121 °C / 15 min; Líquidos 121 °C / 15 min, sin prevacío ni secado, descompresión modo 4 con contrapresión hasta 80 °C (Principal).

## Orden seguro de ejecución

1. Bloques A a D en seco, en ese orden: primero se confirma el perfil, el módulo E/S y la seguridad sin energía térmica en la cámara.
2. No pasar al bloque E sin haber aprobado B-01 (paro), B-03 (NO ABRIR), B-04 (puertas) y A-04 (DO1/DO2).
3. Bloque E (ciclos normales) antes del F (fallas provocadas): las fallas se provocan solo con un ciclo normal ya aprobado.
4. F-04 (puerta en ciclo) solo durante PREVACIO, nunca con presión positiva.
5. Bloque G (Líquidos) al final y con vidrio real; detener ante cualquier ebullición o rotura.
6. Entre pruebas en operación, esperar a cámara segura (NO ABRIR apagado) antes de manipular la carga.

## Resumen

| ID | Prueba | Modo | Origen |
|---|---|---|---|
| A-01 | Instalación con el asistente QML | En seco (sin vapor) | §5.7; S1 |
| A-02 | Arranque con el módulo E/S conectado: ALL_OFF | En seco (sin vapor) | §5.1 (T6) |
| A-03 | Firmware de los módulos e ID solo en Información del sistema | En seco (sin vapor) | E6; tanda 2 §1; ADB-02/ADB-03 (tanda 20) |
| A-04 | DO1/DO2 nunca se encienden (generador interno) | En seco (sin vapor) | S1 |
| A-05 | Ejecutable compilado: engrane, ajustes y cierre limpio | En seco (sin vapor) | B2 (tanda 4) |
| B-01 | Paro de emergencia NC: pulsar, soltar, confirmar | En seco (sin vapor) | §5.2; PF-21; U1 |
| B-02 | Paro NC: cable cortado = paro | En seco (sin vapor) | PF-21 |
| B-03 | NO ABRIR con la cámara no segura (simulado en seco) | En seco (sin vapor) | §5.2 (T4) |
| B-04 | Puertas manuales: un sensor de cerrada por puerta | En seco (sin vapor) | tanda 2; T9 |
| B-05 | Módulo E/S desconectado fuera de ciclo | En seco (sin vapor) | §5.10; U4 |
| B-06 | Apagar equipo (solo pantalla 1; cualquier estado salvo ciclo) | En seco (sin vapor) | §5.8; T7; A1 (tanda 3) |
| B-07 | Apagar equipo en FALLA, con paro, sin módulo E/S y con la cámara no segura | En seco (sin vapor) | A1 (tanda 3); A2 |
| C-01 | Modo sin base de datos | En seco (sin vapor) | §5.6 (T8); S3 |
| C-02 | Alarmas del módulo E/S fuera de ciclo | En seco (sin vapor) | §5.10 (T1) |
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
| C-05b | Arranque sin sensor de presión de cámara: sin bloqueos (H1, H2, H5, H6, H8) | En seco (sin vapor) | S9 D9-1.1 a 1.5 (tanda 9) |
| C-05c | Arranque con la cámara en vacío: aire atmosférico, sin confirmación | En seco (bomba de vacío) | S9 D9-1.1 (tanda 9) |
| C-05d | Paro real pulsado y liberado durante el estado seguro del arranque: sí pide confirmación | En seco | S9 D9-1.2 (tanda 9) |
| C-05e | Cambio de programa y modo prueba con el estado seguro en curso | En seco | S9 D9-1.3 (tanda 9; revierte SAF-03 de T6) |
| C-05f | Coherencia puerta-presión (SEN-10) | En seco | S9 D9-1.6 (tanda 9) |
| C-05g | Modo prueba con la cámara no segura: apertura de puertas bloqueada (SAF-01) | En seco | S9, revisión ★ SAF-01 (tanda 9; DECISIÓN SIN CONFIRMAR, excepción nueva a D-ES-15) |
| C-05h | Estado seguro con la trama AI vencida (TMG-02) | En seco | S9, revisión ★ TMG-02 (tanda 9) |
| C-05i | Arranque sin sensor de presión de cámara: texto de CIC-10 según la causa | En seco (sin vapor) | T10 D10-3 (tanda 10) |
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
| F-06 | Lectura del módulo E/S vencida en ciclo: tolerancia de 4 s | En operación (vapor) | T2 P-3 (tanda 6) |
| F-07 | Paro con el ciclo terminando: diálogo de estado seguro al CONFIRMAR | En operación (vapor) | T2 P-6 (tanda 6) |
| G-03 | Líquidos: drenaje a atmosférica por la lenta hasta temp_max_apertura | En operación (vapor) | T2 P-12 (tanda 6) |
| G-04 | Tipo de carga en Parámetros del ciclo: Líquido arrastra el modo de descompresión | En seco | V8a D8-5.7 (tanda 8); HAZ-V8A-01 |
| A-E9-01 | Instalación limpia de la D: modo de descompresión 5 en los 4 programas y entrega sin datos del banco | En seco (sin vapor) | E9 D9-8 (H14) y D9-7 (H17) (tanda 9) |
| A-E9-02 | Actualización B → D con el Setup, sin copiar archivos a mano | En seco (sin vapor) | E9 D9-13.1 (tanda 9) |
| D-E9-01 | Sin transductores conectados: la presión se muestra «—», nunca 0 | En seco (sin vapor) | E9; H4 resuelto en S1 D8-1.1 (tanda 8). Complementa D-38 (que mide las cuentas ADC). |
| D-E9-02 | Carga Líquido: el modo de descompresión no válido muestra su motivo | En seco (sin vapor) | E9; H13 resuelto en D8-5.7 y D8-5.8 (tanda 8). Complementa G-04. |
| D-E9-03 | Entradas/Salidas solo con los canales del perfil (equipo sin sensores) | En seco (sin vapor) | E9; H16 resuelto en D8-3.17 (tanda 8). Complementa D-39. |
| D-X9-01 | Cambio de un parámetro con el ciclo en curso: bitácora antes de aplicar | En operación (o con la planta simulada) | X9 D9-13.3 (tanda 9); HAZ-X9-01 |
| D-X9-02 | Interfaz en inglés: ticket, reimpresión y motivo de fallo en inglés | En seco (sin vapor) | X9 D9-13.4 (tanda 9); HAZ-X9-02 |
| A-N11-01 | Setup sobre una versión anterior: Actualizar conserva los datos | En seco (sin vapor) | N11 D11-4 (tanda 11) |
| A-N11-02 | Instalación limpia: doble confirmación, respaldo completo y menú de instalación | En seco (sin vapor) | N11 D11-4 (tanda 11) |
| A-N11-03 | Instalación limpia rechazada: confirmación en No y Autoclave abierto no borran nada | En seco (sin vapor) | N11 D11-4 (tanda 11) |
| A-N11-04 | Asociación de los 2 táctiles con sus pantallas desde el Setup | En seco (sin vapor) | N11 D11-5 (tanda 11) |
| A-N11-05 | Reinicio del PC: la asociación de los táctiles se conserva; el desinstalador la revierte | En seco (sin vapor) | N11 D11-5 (tanda 11) |
| A-T12-01 | Tras instalar la H: Bowie & Dick migrado de 99 a 9 con aviso SIS-06 en Preciclo y campana | En seco (sin vapor) | J12 C-04.2/C-04.4 (tanda 12) |
| E-T12-01 | Chaqueta en ciclo: consigna calculada (134 °C / 9 → ≈ 328,2 kPa, banda ±10) vs presión real | En operación (vapor) | J12 C-05 (tanda 12) |
| E-T12-02 | Entrada a ESTABLE_PREESTERILIZACION con la presión de saturación, sin aire | En operación (vapor) | P12 C-01/C-02 (tanda 12) |
| E-T12-03 | Esterilización sin conmutación rápida RECUPERACION ↔ PWM | En operación (vapor) | E12 C-07/C-08 (tanda 12) |
| E-T12-04 | Bowie & Dick de usuario con `presion_add` 9 | En operación (vapor) | J12 C-04.1 (tanda 12) |
| F-T12-01 | Excursión de una Referencia en la exposición: el conteo se detiene y reinicia (C-13) | En operación (vapor) | E12 C-13 (tanda 12) |
| F-T12-02 | Referencia desconectada: el ciclo sigue, SEN-11 y ticket NO CONFORME | En operación (vapor) | E12 C-13.7b (tanda 12) |
| B-11 | PREPARADO: el aire de cámara cierra a los 3 ticks reales | En seco (sin vapor) | Q1 R1-P2 (tanda 7) |
| C-07 | DESPEJAR de COM-02/03 solo con el enlace de vuelta en ok | En seco (sin vapor) | Q1 T2-b (tanda 7); complementa C-06 |
| D-37 | Calentamiento: rango de temperatura y de presión por separado | En seco (sin vapor) | Q1 R1-P3 (tanda 7) |
| D-R8-01 | Reasignación de E/S: solo ingeniero, fuera de ciclo, conflictos rechazados | En seco (sin vapor) | R8 (tanda 8, D8-5.12) |
| D-R8-02 | Reasignar una salida: Vapor cámara de DO 04 a un puerto libre | En seco (sin vapor) | R8 (tanda 8, D8-5.12) |
| D-R8-03 | Reasignar el paro de emergencia: confirmación reforzada y cambio observado | En seco (sin vapor) | R8 (tanda 8, D8-5.12) |
| D-R8-04 | Reasignar una entrada analógica: calibración obligatoria en el puerto nuevo | En seco (sin vapor) | R8 (tanda 8, D8-5.12) |
| D-R8-05 | Restaurar fábrica, respaldo y archivo dañado | En seco (sin vapor) | R8 (tanda 8, D8-5.12) |
| D-39 | Canales de Entradas/Salidas según el perfil de instalación | En seco (sin vapor) | E1 D8-3.17 (tanda 8) |
| E-R8-01 | Ciclo completo con Vapor cámara y Presión cámara reasignados | En operación (vapor) | R8 (tanda 8, D8-5.12) |
| E-08 | Calentamiento con los rangos separados: sin cambio de comportamiento | En operación (vapor) | Q1 R1-P3 (tanda 7) |
| F-08 | Sin datos del módulo E/S en esterilización: la exposición se alarga | En operación (vapor) | Q1 T2-a (tanda 7) |
| F-09 | CARGA NO ESTÉRIL en todo ciclo que no termine COMPLETADO | En operación (vapor) | Q1 T2-c (tanda 7) |
| F-10 | Principal perdido con el protocolo de fallo ya en marcha: pasa a solo la lenta | En operación (vapor) | Q1 R1-P4 (tanda 7) |
| F-11 | Cancelar durante la tolerancia por DI vencida | En operación (vapor) | Q1 R1-P5 (tanda 7) |
| F-12 | Desconexión total breve del módulo E/S en esterilización: la exposición se alarga y no suma F0 | En operación (vapor) | S2a D8-2.7 (tanda 8) |
| F-13 | Cortes repetidos en una esterilización: falla por comunicación inestable (CIC-11) | En operación (vapor) | S2a D8-2.8 (tanda 8) |
| F-14 | DESPEJAR de COM-02/03 exige tramas DI nuevas, no solo tiempo | En seco (sin vapor) | S2a D8-2.9 (tanda 8) |
| F-15 | Líquidos: se pierde el Principal en el enfriamiento con contrapresión — cámara sellada | En operación (vapor) | S2a D8-2.10 (tanda 8) |
| F-16 | Líquidos sin Referencia: espera sellada sin sonda y luego la lenta | En operación (vapor) | S2a D8-2.10 (tanda 8) |
| B-12 | Salir del modo prueba sin confirmación del apagado de salidas (COM-04) | En seco (sin vapor) | S2b D8-2.11 (tanda 8) |
| B-13 | Paro de emergencia: con el buzzer sonando no se enciende ninguna otra salida | En seco (sin vapor) | B9 D9-9 (tanda 9); HAZ-B9-01 |
| F-17 | Ventana de estabilidad en pausa durante la tolerancia por DI vencida | En operación (vapor) | S2b D8-2.12 (tanda 8) |
| F-18 | Cancelar con el módulo E/S totalmente desconectado: texto en pantalla | En operación (vapor) | S2b D8-2.13 y D8-2.15 (tanda 8); complementa F-11 |
| C-08 | Rechazo de DESPEJAR con texto del catálogo | En seco (sin vapor) | S2b D8-2.15 (tanda 8); complementa C-07 |
| F-19 | Reimpresión idéntica al ticket original (avisos del pie) | En operación (vapor) | S2b D8-2.14 (tanda 8) |
| F-20 | CARGA NO ESTÉRIL en la pantalla de resultado | En operación (vapor) | S2b D8-2.16 (tanda 8) |
| H-01 | Válvulas por fase en modo chaqueta | En operación (vapor) | VCH §4.1–4.3, §8.1 y §8.8 (tanda 16) |
| H-02 | Golpe inicial al abrir vapor_camara tras el prevacío | En operación (vapor) | VCH-02 (D5) |
| H-03 | Sobrepaso y tiempo de calentamiento frente al control anterior | En operación (vapor) | VCH-01 (ALTA) |
| H-04 | Aislamiento de cámara por sobrepresión | En operación (vapor) | VCH §4.4–4.5, §8.3–8.5 |
| H-05 | Corte de vapor de chaqueta | En operación (vapor) | D-CHQ / SAF-09 / VCH-CHQ |
| H-06 | Temperatura real con la presión en el techo de ESTERILIZACION | En operación (vapor) | P1 / D-14.1 (DECISIÓN SIN CONFIRMAR) |
| H-07 | Diferencia Principal–Referencia y oscilación pico a pico | En operación (vapor) | P3 / D-14.3 y P6 / D-14.6 (DECISIONES SIN CONFIRMAR) |
| H-08 | Ciclo NO CONFORME: franja, reconocimiento y marcas | En operación (vapor) | P4 / D-14.4 |
| I-01 | Setup: zona horaria de Windows | En seco (sin vapor) | INS-01 (tanda 17) |
| I-02 | Setup: unidad D: y disposición programa/datos | En seco (sin vapor) | INS-02 (tanda 17) |
| I-03 | ACL de programa con un usuario estándar | En seco (sin vapor) | INS-02 ACL (tanda 17, revisión V17-s1-01) |
| I-04 | Actualización con la unidad fija y bloqueo de la disposición anterior | En seco (sin vapor) | INS-02 (tanda 17) |
| I-05 | Instalación limpia y desinstalación sobre datos | En seco (sin vapor) | INS-02 / D11-4 (tanda 17) |
| I-06 | Táctiles sin MultiDigitizer: herramienta propia | En seco (sin vapor) | EST-06 (tanda 17, DECISIONES SIN CONFIRMAR) |
| I-07b | Del inicio de sesión a la intro: escritorio de la estación, sin cubierta | En seco (sin vapor) | EST-08 / EST-09 (tanda 18; sustituye a I-07) |
| I-08 | Sonda en No en uso: monitoreo | En seco (sin vapor) | SON-01 (tanda 17) |
| I-09 | Estado seguro sin transductor de presión de cámara | En seco (sin vapor) | ESG-01 (tanda 17) |
| I-10 | Modo prueba con estado seguro activo y protecciones permanentes | En operación (vapor) | ESG-02 (tanda 17, DECISIONES SIN CONFIRMAR) |
| I-11 | Pantallas: presión en modo prueba, alarmas y selector de programas | En seco (sin vapor) | MPR-01, ALM-01, PRC-01 (tanda 17) |
| I-12 | Bitácora: eventos, instalación y filtros | En seco (sin vapor) | BIT-01..05 (tanda 17) |
| I-13 | Intro de arranque sin perfil de instalación | En seco (sin vapor) | ARR-06 (tanda 18) |
| I-14 | Reinicio del PC al terminar el asistente | En seco (sin vapor) | REI-01 (tanda 18) |
| I-15 | Desinstalar devuelve el escritorio original | En seco (sin vapor) | EST-09 (tanda 18) |
| M-0 | Paso previo: red dedicada y acceso a los módulos | En seco (sin vapor) | MOD-17 (tanda 19); T20-05 (tanda 20) |
| M-1 | Corte por desconexión: el relé abre solo | En seco (sin vapor) | MOD-08 / MOD-07 (tanda 19; 1,0 s es DECISIÓN SIN CONFIRMAR) |
| M-2 | Composición y orden de los módulos | En seco (sin vapor) | MOD-06 / MOD-10 (tanda 19) |
| M-3 | Canal por canal: DI, DO, PT100 y transmisores | En seco (sin vapor) | MOD-03 / MOD-05 / MOD-07 (tanda 19) |
| M-4 | Exactitud de PT100 y AI de presión | En seco (sin vapor) | MOD-16: MED-01 y MED-02 (tanda 19) |
| M-5 | Restablecimiento de fábrica del módulo con el software corriendo | En seco (sin vapor) | MOD-07 / MED-03 (tanda 19) |
| M-5b | Prueba aislada: ¿la configuración de falla exige reiniciar el módulo? | En seco (sin vapor) | ADB-04 (adenda tanda 19; decisión 8 de la tanda 20, pendiente de prueba aislada) |
| M-7 | Setup con Modbus: red de los módulos, contraseña web y prueba de conexión | En seco (sin vapor) | T20-04 / T20-05 (tanda 20); MED-04 |
| T23-01 | Entradas/Salidas tras la migración: mismas lecturas con la numeración nueva | En seco (sin vapor) | AIN-01 / AIN-03 / AIN-05; AIN-R2 (tanda 23) |
| T23-02 | Reasignación por grupo: RTD y AI con el mismo número sin conflicto | En seco (sin vapor) | AIN-01 / AIN-02 / AIN-04; AIN-R1, AIN-R3 (tanda 23) |
| T23-03 | Módulo E/S desconectado: textos con «módulo E/S», ninguno con «tarjeta» | En seco (sin vapor) | MES-01 / MES-04 (tanda 23) |
| T23-04 | Ticket, PDF, Información del equipo y del sistema y Setup sin «tarjeta» | En seco (sin vapor) | MES-02 / MES-04 (tanda 23) |

## Bloque A. Arranque, instalación y módulo E/S (en seco)

### A-01 — Instalación con el asistente QML

- **Modo:** En seco (sin vapor)  ·  **Origen:** §5.7; S1
- **Objetivo:** El perfil del equipo de pruebas queda con la fuente de vapor correcta y bloqueado.
- **Precondiciones:** Sin `installation_profile.json` (o apartado). Módulo E/S conectado.
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

### A-02 — Arranque con el módulo E/S conectado: ALL_OFF

- **Modo:** En seco (sin vapor)  ·  **Origen:** §5.1 (T6)
- **Objetivo:** Al conectar con el módulo E/S, todas las salidas quedan apagadas.
- **Precondiciones:** Equipo apagado, módulos de E/S M31-U conectados por red (M-0).
- **Pasos:**
  1. Encender el PC y el software.
  2. Observar los LED/relés de salida de los módulos durante el arranque.
- **Resultado esperado:** Ninguna salida se enciende durante el arranque; la barra de arranque termina.
- **Criterio de aprobado/fallo:** Aprobado si ninguna salida se activa hasta que el equipo lo pida.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### A-03 — Firmware de los módulos e ID solo en Información del sistema

- **Modo:** En seco (sin vapor)  ·  **Origen:** E6; tanda 2 §1; ADB-02/ADB-03 (tanda 20)
- **Objetivo:** El firmware de los módulos y el ID del equipo (MAC del principal) se ven solo en Información del sistema.
- **Precondiciones:** Módulos M31-U conectados (M-0). La ESP32 (enlace serial) ya no es compatible (tanda 20).
- **Pasos:**
  1. Abrir Menú Principal › Información.
  2. Revisar la preciclo y el ciclo en curso.
- **Resultado esperado:** Información muestra el firmware del principal y de las expansiones (p. ej. 9232-0-13 / 10,12,12,12,10), el ID `005404849DB1` (MAC del principal en el banco) y si está emparejado. Las demás pantallas no los muestran.
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
- **Precondiciones:** `pyinstaller --noconfirm packaging\Autoclave.spec` (desde la raíz) ya ejecutado; `dist\Autoclave\Autoclave.exe` en el equipo.
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

### B-05 — Módulo E/S desconectado fuera de ciclo

- **Modo:** En seco (sin vapor)  ·  **Origen:** §5.10; U4
- **Objetivo:** Desconectar el cable de red de los módulos no se confunde con un paro y deja el equipo en estado seguro.
- **Precondiciones:** PREPARADO.
- **Pasos:**
  1. Desconectar el cable de red de los módulos.
  2. Observar alarmas y campana.
  3. Reconectar.
- **Resultado esperado:** FALLA recuperable con "Módulo E/S desconectado" (no "paro de emergencia"); NO ABRIR activo; sin inicio de ciclo. Al reconectar vuelve sin pedir confirmación de estado seguro (si nunca hubo paro real).
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
- **Resultado esperado:** Puerta 2: no disponible. Puerta 1: pide confirmación; durante el ciclo, rechazado (hay que cancelar antes). Fuera de ciclo: salidas apagadas, bitácora `apagar_equipo` (estado, cámara segura, módulo E/S), base cerrada y Windows se apaga.
- **Criterio de aprobado/fallo:** Aprobado si solo apaga desde la puerta 1, nunca en ciclo, y la bitácora registra el estado y la condición de la cámara.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### B-07 — Apagar equipo en FALLA, con paro, sin módulo E/S y con la cámara no segura

- **Modo:** En seco (sin vapor)  ·  **Origen:** A1 (tanda 3); A2
- **Objetivo:** El personal técnico puede dejar el equipo fuera de servicio aunque haya una falla, el paro esté pulsado o no haya módulo E/S; el siguiente arranque es normal.
- **Precondiciones:** Sin ciclo en curso. Probar cada condición por separado: (a) FALLA recuperable (p. ej. cable de red de los módulos desconectado); (b) paro de emergencia pulsado; (c) módulo E/S desconectado; (d) cámara no segura (si se puede, con la cámara caliente, p. ej. tras E-01).
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
- **Objetivo:** Si el módulo E/S no confirma el apagado de todas las salidas al salir del modo prueba, se reintenta 3 veces y, si sigue sin confirmar, sale la alarma "Salidas sin confirmar" y no se puede iniciar ciclo.
- **Precondiciones:** PREPARADO, sesión de técnico, modo prueba activo con una salida segura encendida.
- **Pasos:**
  1. Salir del modo prueba con normalidad: anotar en la bitácora el evento de salida con el apagado confirmado.
  2. Volver a entrar al modo prueba; desconectar el cable de red de los módulos y salir del modo prueba enseguida.
  3. Observar el panel de notificaciones e intentar iniciar un ciclo.
  4. Reconectar el módulo E/S y esperar a que se complete la conexión.
- **Resultado esperado:** Paso 1: sin alarma. Paso 3: alarma COM-04 "Salidas sin confirmar"; el inicio de ciclo queda bloqueado. Paso 4: al completarse la conexión (o un apagado confirmado) la alarma se despeja y el inicio vuelve a estar permitido.
- **Criterio de aprobado/fallo:** Aprobado si con el módulo E/S sin confirmar nunca se permite iniciar ciclo.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### B-13 — Paro de emergencia: con el buzzer sonando no se enciende ninguna otra salida

- **Modo:** En seco (sin vapor)  ·  **Origen:** B9 D9-9 (tanda 9); HAZ-B9-01
- **Objetivo:** Con el paro pulsado solo conmuta el buzzer (DO24); ninguna salida que estuviera activa al pulsar el paro se enciende, ni un instante, cuando el buzzer reinicia su patrón. Fuera del paro, el buzzer no altera las demás salidas.
- **Precondiciones:** Anotar el tipo de puerta del perfil (Información del sistema o `installation_profile.json`: simple o avanzada) y el firmware de los módulos (Información del sistema). PREPARACION o PREPARADO. Mirar los LED de los módulos de salidas (o un multímetro en las bornas). Lista de salidas a observar: DO3 vapor de chaqueta, DO4 vapor de cámara, DO5 descompresión rápida, DO6 descompresión lenta, DO7 descompresión de chaqueta, DO8 vacío de cámara, DO9/DO10 desbloqueo de puerta 1/2, DO11/DO12 bloqueo de puerta 1/2, DO13 libre (sin función desde la tanda 11; debe seguir siempre apagada), DO14 aire comprimido de cámara, DO15 aire atmosférico de cámara, DO16 agua de chaqueta, DO17 agua del intercambiador, DO18 agua de la bomba, DO19 bomba de vacío, DO20/DO21 abrir puerta 1/2, DO22/DO23 cerrar puerta 1/2, y DO25 buzzer (canal según la asignación de E/S vigente; DO 25 desde la tanda 19).
- **Pasos:**
  1. Con el modo prueba (técnico), encender 3 o 4 salidas seguras de la lista (p. ej. DO6, DO15, DO17) y salir del modo prueba; o dejar que el estado encienda las suyas (con el perfil de puertas avanzadas, la puerta cerrada mantiene DO22 y, con empaque bajo, DO11). Anotar cuáles quedan encendidas.
  2. Pulsar el paro y mantenerlo 30 s. Observar cada salida de la lista durante al menos 5 repeticiones del patrón del buzzer.
  3. En el log del backend (`logs/`), buscar "paro de emergencia detectado; ALL_OFF inmediato" y, si aparecen, las líneas "DOn no se enciende con el paro de emergencia activo" (indican qué función intentó encender y fue bloqueada).
  4. Soltar el paro y confirmar. Provocar una alarma no bloqueante con buzzer (o el pitido de fin de ciclo) con alguna salida encendida y observar que esa salida no cambia mientras suena el buzzer.
- **Resultado esperado:** Paso 2: al pulsar, todas las salidas se apagan de inmediato; durante el paro solo parpadea DO24; ninguna otra salida de la lista se enciende ni un instante. Paso 3: la línea del ALL_OFF inmediato aparece una vez por pulsación. Paso 4: el buzzer conmuta solo su canal.
- **Criterio de aprobado/fallo:** Aprobado si en el paso 2 ninguna salida distinta del buzzer se enciende. Si alguna se enciende: anotar cuál, el tipo de puerta y el firmware de los módulos, y guardar el log (si el log NO muestra órdenes de encendido para ese canal, la causa está en los módulos o el cableado, no en el PC: ver B9_buzzer_paro.md).
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

### C-02 — Alarmas del módulo E/S fuera de ciclo

- **Modo:** En seco (sin vapor)  ·  **Origen:** §5.10 (T1)
- **Objetivo:** Pérdida de comunicación fuera de ciclo = FALLA recuperable.
- **Precondiciones:** PREPARADO.
- **Pasos:**
  1. Desconectar el cable de red de los módulos en PREPARADO.
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
  1. Cortar la energía del PC y del módulo E/S.
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

### C-05 — Arranque con cámara no segura: confirmar estado seguro sin técnico

- **Modo:** En seco (sin vapor)  ·  **Origen:** T1 (tanda 5), P-10
- **Objetivo:** Tras un corte con la cámara caliente, el operador lleva el equipo a seguro sin rol técnico.
- **Precondiciones:** Simular cámara no segura al arrancar (sensor Principal calentado > temp_max_apertura) con un ciclo previo interrumpido en la BD (o cortar la energía en pleno ciclo de prueba en seco).
- **Pasos:**
  1. Arrancar el software.
  2. Observar "NO ABRIR" y el aviso de estado seguro.
  3. Pulsar el botón que ofrece la UI (debe ser "Confirmar y llevar a estado seguro", no "Reconocer falla").
  4. Dejar enfriar.
- **Resultado esperado:** El ciclo previo aparece como INTERRUMPIDO ("la carga NO está estéril"); no se reanuda; el botón correcto funciona sin sesión; al quedar segura vuelve a PREPARACION.
- **Criterio de aprobado/fallo:** Aprobado si no se reanuda nada, el botón correcto aparece y no se exige técnico.
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
- **Objetivo:** Si el módulo E/S sigue mandando entradas digitales pero deja de mandar las analógicas, el estado seguro no toma la presión congelada como vigente.
- **Precondiciones:** Estado seguro en curso (C-05). Desde la tanda 20 (solo Modbus) las lecturas de AI y DI van en el mismo sondeo y no se pueden suspender por separado con los módulos M31-U reales: se ejecuta solo con un simulador de los módulos (las pruebas automáticas lo cubren); con el equipo real, marcar «No ejecutada (no aplica con M31-U)». Donde dice tramas `AI:`, entiéndase las lecturas de AI.
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
- **Precondiciones:** Ciclo de prueba en seco; desconectar el cable de red de los módulos para provocar COM-03; reconectar.
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
- **Precondiciones:** Como C-06: ciclo de prueba en seco y COM-03 provocada desconectando el cable de red de los módulos; confirmar la falla y volver a PREPARACION con el módulo E/S aún desconectado.
- **Pasos:**
  1. Con el módulo E/S aún desconectado, pulsar DESPEJAR en el panel de notificaciones.
  2. Reconectar el módulo E/S y esperar ~2 s (3 lecturas vigentes).
  3. Pulsar DESPEJAR de nuevo, sin iniciar sesión.
- **Resultado esperado:** Primer intento: rechazado con "No se puede despejar: el enlace con el módulo E/S todavía no ha vuelto a la normalidad"; la alarma sigue. Segundo intento: se despeja sin pedir sesión.
- **Criterio de aprobado/fallo:** Aprobado si no se despeja sin enlace y sí se despeja sin sesión con el enlace ok.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### F-14 — DESPEJAR de COM-02/03 exige tramas DI nuevas, no solo tiempo

- **Modo:** En seco (sin vapor)  ·  **Origen:** S2a D8-2.9 (tanda 8)
- **Objetivo:** DESPEJAR se acepta solo tras 3 tramas DI distintas y nuevas con el enlace en "ok".
- **Precondiciones:** COM-02 activa tras una desconexión en ciclo (o provocada en seco con un ciclo de prueba).
- **Pasos:**
  1. Reconectar el cable de red y pulsar DESPEJAR de inmediato.
  2. Esperar 2-3 s y volver a pulsar DESPEJAR.
- **Resultado esperado:** El primer intento se rechaza con el motivo del enlace; tras unas 3 tramas DI (≈0,3 s con el sondeo Modbus de 0,1 s) se acepta.
- **Criterio de aprobado/fallo:** Aprobado si no se despeja antes de que el módulo E/S envíe lecturas DI nuevas.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### C-08 — Rechazo de DESPEJAR con texto del catálogo

- **Modo:** En seco (sin vapor)  ·  **Origen:** S2b D8-2.15 (tanda 8); complementa C-07
- **Objetivo:** El rechazo de DESPEJAR se muestra en el panel de notificaciones con texto legible, no con el texto técnico de la petición.
- **Precondiciones:** Como C-07 (COM-03 activa con el módulo E/S desconectado, en PREPARACION).
- **Pasos:**
  1. Pulsar DESPEJAR con el módulo E/S aún desconectado.
  2. Cerrar y volver a abrir el panel de notificaciones.
  3. Cambiar el idioma a inglés y repetir el paso 1.
- **Resultado esperado:** Bajo el título del panel: "No se puede despejar: el enlace con el módulo E/S todavía no ha vuelto a la normalidad." (en inglés: "Cannot clear: ..."). Al cerrar el panel el mensaje desaparece. El panel de Equipo no muestra "apagado rechazado".
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
- **Precondiciones:** Cualquier rol con sesión. Módulo E/S conectado.
- **Pasos:**
  1. Comparar cada dato con el perfil, el firmware real y el número de ciclos.
  2. Desconectar la impresora y la red: los chips pasan a naranja.
  3. Desconectar el módulo E/S y reabrir: los demás datos siguen.
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
- **Precondiciones:** Equipo en PREPARADO, puerta abierta, patrón de presión. Mover el transmisor de presión de cámara de AI 01 a AI 05 (antes de la tanda 23 se rotulaban AI 09 y AI 13).
- **Pasos:**
  1. Intentar reasignar Presión cámara a un puerto AI sin calibración, si lo hay.
  2. Reasignar Presión cámara a AI 05 y reiniciar.
  3. Intentar Verificar sin calibrar.
  4. Calibrar Presión cámara en Entradas / Salidas contra el patrón y Verificar.
- **Resultado esperado:** Puerto sin calibración: rechazo «Ese puerto analógico no tiene calibración» (desde la tanda 23 las AI 01–16 traen calibración nominal, AIN-04, y este caso puede no existir: anotarlo como no aplicable). AI 05 sin calibrar en sitio: «Falta: calibrar el sensor en su puerto nuevo». Tras calibrar, la lectura coincide con el patrón (± tolerancia de calibración) y se verifica.
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
- **Objetivo:** Desconectar el módulo E/S en ciclo da COM-03 y el módulo E/S queda en ALL_OFF.
- **Precondiciones:** Ciclo en CALENTAMIENTO.
- **Pasos:**
  1. Desconectar el cable de red de los módulos 5 s.
  2. Reconectar.
  3. Revisar alarmas y resultado.
- **Resultado esperado:** COM-03 con su causa; el ciclo termina en FALLO_IO; los módulos apagan las salidas por su corte por desconexión (1,0 s); al reconectar, estado seguro.
- **Criterio de aprobado/fallo:** Aprobado si las salidas se apagan sin el PC y el ciclo no sigue "a ciegas".
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### F-03 — Corte de energía durante el ciclo

- **Modo:** En operación (vapor)  ·  **Origen:** §5.1 (T6)
- **Objetivo:** Un ciclo interrumpido por corte queda como INTERRUMPIDO y el arranque es seguro.
- **Precondiciones:** Ciclo en ESTERILIZACION.
- **Pasos:**
  1. Cortar la energía (PC y módulo E/S).
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

### F-06 — Lectura del módulo E/S vencida en ciclo: tolerancia de 4 s

- **Modo:** En operación (vapor)  ·  **Origen:** T2 P-3 (tanda 6)
- **Objetivo:** Un corte breve del módulo E/S corta el vapor y uno largo termina en FALLO_CONEXION.
- **Precondiciones:** Ciclo en calentamiento o esterilización.
- **Pasos:**
  1. Desconectar el cable de red de los módulos menos de 4 s y reconectar.
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

### F-08 — Sin datos del módulo E/S en esterilización: la exposición se alarga

- **Modo:** En operación (vapor)  ·  **Origen:** Q1 T2-a (tanda 7)
- **Objetivo:** Los segundos de tolerancia por DI vencida no cuentan como exposición y quedan en el ticket.
- **Precondiciones:** Bowie & Dick o Instrumental 134 en esterilización (cronometrar desde el inicio de la fase).
- **Pasos:**
  1. Desconectar el cable de red de los módulos unos 2-3 s (menos de 4 s) y reconectar.
  2. Dejar terminar el ciclo y anotar la duración real de la esterilización.
  3. Revisar el pie del ticket.
- **Resultado esperado:** La esterilización dura el tiempo programado más los segundos sin datos; el vapor estuvo en OFF durante el corte; el pie dice "Sin datos del módulo E/S: n s" y el ciclo queda COMPLETADO (sin marca de no estéril).
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
- **Objetivo:** La cancelación pedida mientras el módulo E/S no manda entradas se acepta y se aplica al volver los datos.
- **Precondiciones:** Ciclo en esterilización.
- **Pasos:**
  1. Desconectar el cable de red de los módulos y, antes de 4 s, pulsar Cancelar.
  2. Reconectar enseguida.
  3. Repetir dejándolo desconectado más de 4 s.
- **Resultado esperado:** La cancelación se acepta (sin el rechazo "sin datos del módulo E/S"); al volver los datos el ciclo queda CANCELADO. Si no vuelven a tiempo, termina en FALLO_CONEXION.
- **Criterio de aprobado/fallo:** Aprobado si en ningún caso el ciclo sigue corriendo después de la cancelación.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### F-12 — Desconexión total breve del módulo E/S en esterilización: la exposición se alarga y no suma F0

- **Modo:** En operación (vapor)  ·  **Origen:** S2a D8-2.7 (tanda 8)
- **Objetivo:** Los segundos con el cable de red desconectado (menos de 5 s) y la ventana tras reconectar no cuentan como esterilización ni como F0.
- **Precondiciones:** Programa con F0 activo (o Instrumental 134) en esterilización; cronometrar desde el inicio de la fase y anotar el F0 en pantalla.
- **Pasos:**
  1. Desconectar el cable de red de los módulos unos 3 s y reconectar (antes de que salga COM-02).
  2. Dejar terminar el ciclo; anotar la duración real de la esterilización y el F0 final.
  3. Revisar el pie del ticket.
- **Resultado esperado:** La esterilización dura lo programado más los segundos sin datos (corte + ventana de reconexión, hasta ~2 s más por la vigencia de la última trama); el F0 no sube durante el corte; el pie dice "Sin datos del módulo E/S: n s"; COMPLETADO.
- **Criterio de aprobado/fallo:** Aprobado si la duración se alarga al menos los segundos del corte y el F0 no aumenta mientras no hay datos.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### F-13 — Cortes repetidos en una esterilización: falla por comunicación inestable (CIC-11)

- **Modo:** En operación (vapor)  ·  **Origen:** S2a D8-2.8 (tanda 8)
- **Objetivo:** Si las pausas por falta de datos suman más de pausa_max_esterilizacion_s (30 s por defecto), el ciclo falla con CIC-11.
- **Precondiciones:** Instrumental 134 en esterilización; pausa_max_esterilizacion_s = 30 s (OPCIONES › Parámetros del equipo).
- **Pasos:**
  1. Desconectar el cable de red de los módulos unos 3 s y reconectar; esperar 5 s; repetir hasta sumar más de 30 s de cortes.
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
- **Objetivo:** Los segundos sin datos del módulo E/S no cuentan en la ventana de estabilidad previa a la esterilización (ni en el hold del prevacío ni en el secado); los tiempos límite de fase sí siguen.
- **Precondiciones:** Ciclo Instrumental 134 en curso; sesión de técnico para ver el log.
- **Pasos:**
  1. Esperar a que el calentamiento llegue al tramo estable (log: ventana de estabilidad abierta).
  2. Provocar 2-3 s sin datos del módulo E/S (desconectar y reconectar el cable de red de los módulos antes de 4 s).
  3. Dejar terminar el ciclo.
- **Resultado esperado:** Log: "ventana _timer_sostenido_desde en pausa n s"; sin vapor durante el tramo; el ciclo termina COMPLETADO y el ticket dice "Sin datos del módulo E/S: n s".
- **Criterio de aprobado/fallo:** Aprobado si la ventana se alarga lo que duró el tramo y el ciclo no se da por estable con segundos sin datos.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### F-18 — Cancelar con el módulo E/S totalmente desconectado: texto en pantalla

- **Modo:** En operación (vapor)  ·  **Origen:** S2b D8-2.13 y D8-2.15 (tanda 8); complementa F-11
- **Objetivo:** Con el módulo E/S desconectado (antes de COM-02) la cancelación se acepta en espera y la pantalla lo explica con el texto del catálogo.
- **Precondiciones:** Ciclo en esterilización.
- **Pasos:**
  1. Desconectar el cable de red de los módulos y, antes de 5 s, pulsar CANCELAR CICLO y confirmar.
  2. Leer el aviso de la pantalla y reconectar enseguida.
  3. Repetir dejándolo desconectado más de 5 s.
- **Resultado esperado:** Aviso: "Cancelación aceptada: se aplicará cuando vuelvan los datos del módulo E/S..." (no un error ni un texto técnico); al volver los datos, CANCELADO. Sin reconectar a tiempo, FALLO_CONEXION.
- **Criterio de aprobado/fallo:** Aprobado si el aviso sale con ese texto y el ciclo nunca sigue corriendo tras la cancelación.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### F-19 — Reimpresión idéntica al ticket original (avisos del pie)

- **Modo:** En operación (vapor)  ·  **Origen:** S2b D8-2.14 (tanda 8)
- **Objetivo:** La reimpresión desde el Historial trae las mismas líneas de aviso del pie que el ticket impreso en vivo.
- **Precondiciones:** Ciclo con un tramo sin datos del módulo E/S (F-17) y, si el equipo tiene sensores de referencia, con un aviso de uniformidad.
- **Pasos:**
  1. Guardar el ticket impreso en vivo.
  2. Reimprimir el mismo ciclo desde el Historial.
  3. Comparar los pies.
- **Resultado esperado:** Ambos traen "Sin datos del módulo E/S: n s", los avisos de uniformidad y (si el ciclo tenía F0) "F0 total". Los ciclos anteriores a esta versión se reimprimen como antes.
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
- **Precondiciones:** Módulo E/S conectado, transductores de presión desconectados. Sesión de técnico.
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

## Bloque N11. Instalador: Actualizar o Instalación limpia y táctiles (tanda 11, en seco)

### A-N11-01 — Setup sobre una versión anterior: Actualizar conserva los datos

- **Modo:** En seco (sin vapor)  ·  **Origen:** N11 D11-4 (tanda 11)
- **Objetivo:** Con una versión más vieja instalada, el Setup muestra la página "Actualizar Autoclave" con "Actualizar (conserva los datos)" marcada por defecto y la actualización conserva todos los datos, igual que antes.
- **Precondiciones:** F instalada con datos. Autoclave cerrado. Copia de `C:\ProgramData\Especifika\Autoclave` en una USB.
- **Pasos:**
  1. Ejecutar el Setup nuevo (doble clic).
  2. Revisar la página "Actualizar Autoclave": versión instalada y la de este instalador, dos opciones y cuál viene marcada.
  3. Dejar "Actualizar" y seguir con el asistente hasta terminar.
  4. Abrir Autoclave y revisar perfil, usuarios, Historial y calibración.
  5. Revisar que no se creó `C:\ProgramData\Especifika\Autoclave_respaldos\`.
- **Resultado esperado:** Paso 2: "Actualizar (conserva los datos)" marcada; "Instalación limpia" sin marcar. Pasos 3 y 4: ninguna confirmación de borrado; todo igual que antes de actualizar. Paso 5: no existe (o no cambió).
- **Criterio de aprobado/fallo:** Aprobado si la actualización por defecto no pide confirmar ningún borrado y no se pierde ni cambia ningún dato.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### A-N11-02 — Instalación limpia: doble confirmación, respaldo completo y menú de instalación

- **Modo:** En seco (sin vapor)  ·  **Origen:** N11 D11-4 (tanda 11)
- **Objetivo:** La instalación limpia pide dos confirmaciones (la segunda nombra los ciclos registrados y los usuarios), respalda toda la carpeta de datos antes de borrarla y deja el equipo como recién instalado: al abrir Autoclave aparece el menú de instalación.
- **Precondiciones:** Una versión instalada con datos (puede ser la misma del Setup: en ese caso la página es "Autoclave ya está instalado"). Autoclave cerrado. Anotar el número de archivos y el tamaño de `C:\ProgramData\Especifika\Autoclave` (clic derecho › Propiedades).
- **Pasos:**
  1. Ejecutar el Setup. En la página de opciones elegir "Instalación limpia" y pulsar Siguiente.
  2. Leer la primera confirmación y responder Sí. Leer la segunda y responder Sí.
  3. Completar las tareas y la cuenta y pulsar Instalar.
  4. Revisar `C:\ProgramData\Especifika\Autoclave_respaldos\`: una carpeta `AAAAMMDD-HHMMSS` con la fecha y la hora de la instalación. Comparar su número de archivos y su tamaño con lo anotado.
  5. Con la cuenta del operador (sin privilegios), intentar abrir esa carpeta.
  6. Revisar `C:\ProgramData\Especifika\Autoclave`: solo debe quedar `estacion\` (si la estación estaba configurada) y lo que cree el programa al abrirse.
  7. Abrir Autoclave.
  8. (Opcional) Restaurar: cerrar Autoclave y copiar como administrador el contenido del respaldo a `C:\ProgramData\Especifika\Autoclave`; abrir Autoclave.
- **Resultado esperado:** Paso 2: las dos confirmaciones tienen "No" como botón por defecto; la segunda dice que se borran los ciclos registrados y los usuarios. Paso 4: mismo número de archivos y mismo tamaño. Paso 5: acceso denegado (solo administradores). Paso 6: el perfil, la base, la calibración y los usuarios ya no están. Paso 7: se abre el menú de instalación del equipo (no hay perfil) y los usuarios son los iniciales. Paso 8: vuelven el perfil, los usuarios y el Historial.
- **Criterio de aprobado/fallo:** Aprobado si nada se borra sin las dos confirmaciones, el respaldo está completo y protegido, y el primer arranque abre el menú de instalación.
- **Carpeta del respaldo:** ______________________ · **Archivos / tamaño original:** ________ · **Respaldo:** ________
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### A-N11-03 — Instalación limpia rechazada: confirmación en No y Autoclave abierto no borran nada

- **Modo:** En seco (sin vapor)  ·  **Origen:** N11 D11-4 (tanda 11)
- **Objetivo:** Si el técnico no confirma, o si Autoclave está abierto al instalar, no se borra nada. Un fallo del respaldo se comporta igual que el caso de Autoclave abierto: el Setup se detiene sin borrar (ese fallo no se provoca en el banco; está revisado en el código, informe N11).
- **Precondiciones:** Versión instalada con datos.
- **Pasos:**
  1. Setup › "Instalación limpia" › Siguiente › responder **No** en la primera confirmación. Repetir y responder Sí en la primera y **No** en la segunda.
  2. Elegir "Instalación limpia", confirmar las dos veces y pulsar **Atrás** hasta la página de opciones; elegir la otra opción (Actualizar o Reparar) y terminar.
  3. Abrir Autoclave y dejarlo abierto. Ejecutar el Setup, elegir "Instalación limpia", confirmar las dos veces y pulsar Instalar.
- **Resultado esperado:** Paso 1: el Setup se queda en la página de opciones; los datos siguen. Paso 2: instala como Actualizar o Reparar y los datos siguen; no hay respaldo nuevo. Paso 3: el Setup se detiene con el aviso "Autoclave está abierto… No se borró nada" y no instala; los datos siguen y no hay respaldo nuevo.
- **Criterio de aprobado/fallo:** Aprobado si en ninguno de los tres pasos desaparece un dato.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### A-N11-04 — Asociación de los 2 táctiles con sus pantallas desde el Setup

- **Modo:** En seco (sin vapor)  ·  **Origen:** N11 D11-5 (tanda 11)
- **Objetivo:** Con dos monitores táctiles conectados, el Setup ofrece (marcada) la asociación de los táctiles, abre la herramienta de Windows y, tras tocar cada pantalla, cada toque responde en su propia pantalla.
- **Precondiciones:** PC de prueba con los 2 paneles táctiles conectados (video y USB). Antes, comprobar el problema: tocar la pantalla 2 y ver si el cursor aparece en la 1. Si se puede, probar también una vez con un solo monitor conectado.
- **Pasos:**
  1. Ejecutar el Setup. En "Tareas adicionales" revisar la subcasilla "Asociar cada pantalla táctil con su monitor" debajo de "Configurar este PC como estación del autoclave".
  2. Instalar. Cuando aparezca el mensaje de Windows en una pantalla, tocar esa pantalla; luego tocar la otra cuando muestre el mensaje.
  3. Al terminar el Setup, revisar si aparece el aviso "Repita la asociación de pantallas táctiles".
  4. Revisar `C:\ProgramData\Especifika\Autoclave\estacion\estacion.log`: línea `Asociaciones tactiles en HKLM\SOFTWARE\Microsoft\Wisp\Pen\Digimon: N`.
  5. Tocar botones de Autoclave en cada pantalla.
  6. Marcar los puertos USB de cada táctil y anotarlos.
  7. (Con un solo monitor) La subcasilla no aparece.
- **Resultado esperado:** Paso 1: subcasilla marcada. Paso 3: sin aviso si se tocaron las dos. Paso 4: N = 2 (o más). Paso 5: cada toque responde en la pantalla tocada. Paso 7: no aparece la subcasilla.
- **Criterio de aprobado/fallo:** Aprobado si tras la asociación cada táctil responde en su pantalla. Si el aviso aparece con las dos pantallas tocadas, anotar el N del log y avisar a Code.
- **Puertos USB:** pantalla 1 ______________ · pantalla 2 ______________
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### A-N11-05 — Reinicio del PC: la asociación de los táctiles se conserva; el desinstalador la revierte

- **Modo:** En seco (sin vapor)  ·  **Origen:** N11 D11-5 (tanda 11)
- **Objetivo:** La asociación sobrevive al reinicio y a Reparar; cambiar un táctil de puerto USB la deshace; el desinstalador borra solo las asociaciones que creó el paso.
- **Precondiciones:** A-N11-04 aprobada.
- **Pasos:**
  1. Reiniciar el PC (Apagar equipo desde Autoclave o reinicio de Windows). Tocar cada pantalla.
  2. Ejecutar el Setup de la misma versión › Reparar. Comprobar que no abre la herramienta de los táctiles. Tocar cada pantalla.
  3. Pasar el cable USB de un táctil a otro puerto, tocar cada pantalla y devolverlo a su puerto marcado.
  4. Desinstalar Autoclave. Revisar en `estacion.log` las líneas `Borrada asociacion creada por el paso 6`. Tocar cada pantalla.
- **Resultado esperado:** Paso 1: cada toque en su pantalla. Paso 2: sin herramienta; la asociación sigue. Paso 3: con el cable en otro puerto el toque puede ir a la otra pantalla; al devolverlo, vuelve a estar bien. Paso 4: las asociaciones del paso se borran (los toques pueden volver a ir a la pantalla equivocada, como antes de instalar).
- **Criterio de aprobado/fallo:** Aprobado si la asociación se conserva tras el reinicio y Reparar, y el desinstalador la revierte sin error.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

## Bloque T12. Tanda 12: calentamiento, esterilización y chaqueta (lunes 26-oct)

### A-T12-01 — Tras instalar la H: Bowie & Dick migrado de 99 a 9 con aviso SIS-06 en Preciclo y campana

- **Modo:** En seco (sin vapor)  ·  **Origen:** J12 C-04.2/C-04.4 (tanda 12)
- **Objetivo:** El Bowie & Dick de usuario de la G traía `presion_add_calentamiento` 99 (techo 407,7 kPa, por encima del alivio de 385). Al cargarlo, la H lo baja a 9, lo deja en la bitácora de auditoría y muestra un aviso no bloqueante (SIS-06, programa corregido por migración) en la bandeja de Preciclo y en la campana. La chaqueta 350/25 de los programas de usuario se conserva (válida, con advertencia).
- **Precondiciones:** G instalada con sus programas de usuario sin tocar. Anotar antes, en Opciones › Parámetros del ciclo › Bowie & Dick: `presion_add_calentamiento` (debe ser 99), `presion_add_esterilizacion`, `presion_chaqueta` / `rango_presion_chaqueta` (350 / 25). Sesión de técnico o ingeniero.
- **Pasos:**
  1. Instalar la H con el Setup (Actualizar) y abrir Autoclave.
  2. Ir a Preciclo y revisar la bandeja de avisos; abrir la campana (`PanelNotificaciones`).
  3. Opciones › Parámetros del ciclo › Bowie & Dick › Calentamiento: leer `presion_add_calentamiento`. Revisar también Instrumental 134 y 121 (chaqueta).
  4. Opciones › Bitácora de auditoría: filtrar por parámetros del programa Bowie & Dick.
  5. Seleccionar Bowie & Dick e iniciar hasta PREPARADO (sin arrancar): comprobar que el aviso no bloquea.
  6. En un programa de usuario de prueba (copia), intentar `presion_add_calentamiento` = 31; luego 30 con `temperatura_calentamiento` 137 (techo 359,6 kPa) y con 140 (techo 389,0 kPa). Devolver los valores originales.
  7. Cerrar y volver a abrir Autoclave: revisar si el aviso SIS-06 sigue en la campana hasta que alguien lo revise.
- **Resultado esperado:** Paso 2: aviso SIS-06 en Preciclo y en la campana que nombra el programa Bowie & Dick y el parámetro, de 99 a 9, en el idioma vigente. Paso 3: Bowie & Dick con 9; los demás programas sin cambios; la chaqueta 350/25 se conserva. Paso 4: una fila con programa, parámetro, valor anterior 99, nuevo 9 y origen "migración tanda 12". Paso 5: se puede iniciar (aviso no bloqueante). Paso 6: 31 rechazado (máximo 30); 137 / 30 se guarda con la advertencia "la cámara no alcanzará el techo de presión…"; 140 / 30 rechazado con el valor máximo admisible (≈ 26 kPa, menos de 385 − 359,0). Paso 7: anotar si persiste (el comportamiento lo decide J12).
- **Criterio de aprobado/fallo:** Aprobado si el Bowie & Dick queda en 9 con su fila de auditoría y el aviso visible en Preciclo y en la campana, sin bloquear el inicio, y ningún programa de fábrica ni de usuario queda inválido.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### E-T12-01 — Chaqueta en ciclo: consigna calculada (134 °C / 9 → ≈ 328,2 kPa, banda ±10) vs presión real

- **Modo:** En operación (vapor)  ·  **Origen:** J12 C-05 (tanda 12)
- **Objetivo:** En CICLO la chaqueta deja de usar `presion_chaqueta` y sigue la consigna calculada `max(Psat(T_est + 1,5), Psat(T_est) + presion_add_esterilizacion + 15)`. Para Instrumental 134 de usuario: `max(Psat(135,5) = 317,8; 304,2 + 9 + 15 = 328,2)` = **328,2 kPa** (≈ 136,6 °C). `vapor_chaqueta` enciende bajo 318,2 kPa y apaga sobre 338,2 kPa; dentro, no cambia. En PREPARADO/PREPARACION sigue rigiendo `presion_chaqueta` 350 ± 25.
- **Precondiciones:** Instrumental 134 de usuario; suministro de vapor regulado (≈ 40 psig, ≈ 350 kPa abs); log del backend accesible.
- **Pasos:**
  1. En PREPARADO anotar la presión de chaqueta (debe rondar 350 kPa, la válvula de chaqueta queda casi siempre abierta: el objetivo coincide con el suministro).
  2. Iniciar el ciclo; buscar en el log la línea de inicio de ciclo con la consigna de chaqueta calculada y anotarla.
  3. Durante CALENTAMIENTO y ESTERILIZACION registrar cada minuto la presión de chaqueta y el estado de Vapor chaqueta (pantalla o LED del módulo E/S).
  4. Anotar la presión mínima y máxima de chaqueta en la meseta y las presiones a las que la válvula enciende y apaga.
  5. En SECADO y en el enfriamiento comprobar que el control de chaqueta es el de antes (secado excluido).
- **Resultado esperado:** Paso 2: consigna 328,2 ± 0,2 kPa en el log. Paso 3: al entrar a CICLO desde ~350 kPa la válvula queda cerrada hasta bajar de 318,2 kPa; luego enciende bajo 318,2 y apaga sobre 338,2; la presión de chaqueta queda en 318–338 kPa (con la inercia puede pasar unos kPa). Nunca sobre 385. Paso 5: sin cambios respecto a la G.
- **Criterio de aprobado/fallo:** Aprobado si la consigna del log coincide con la calculada y los encendidos/apagados ocurren en los bordes de la banda ±10. Si la presión real de chaqueta no llega a 316 kPa con la válvula abierta, anotar la presión de suministro (caso válvula siempre abierta, C-05.5).
- **Consigna en el log:** ________ kPa · **Chaqueta mín / máx en meseta:** ________ / ________ kPa · **ON a / OFF a:** ________ / ________ kPa
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### E-T12-02 — Entrada a ESTABLE_PREESTERILIZACION con la presión de saturación, sin aire

- **Modo:** En operación (vapor)  ·  **Origen:** P12 C-01/C-02 (tanda 12)
- **Objetivo:** `presion_add_calentamiento` ya es solo techo: la fase entra a sostener con `T ≥ 134,0 °C` y `P ≥ Psat(134) − 2 = 302,2 kPa` (antes exigía `Psat + presion_add`, 315,2 kPa con 11). Además, con sólidos, la ventana exige coherencia `|Tsat(P) − T| ≤ 1,0 K`: presión de vapor saturado sin aire. Techo de calentamiento: `Psat(134) + 11 = 315,2 kPa` (no 2 × 11). Corte por calidad de vapor desde 131,0 °C (T_obj − 3 K, antes 97 %).
- **Precondiciones:** Mismo ciclo que E-T12-01 (Instrumental 134 de usuario, sólido, con prevacío).
- **Pasos:**
  1. Registrar temperatura del Principal y presión de cámara cada 15 s desde 128 °C hasta el paso a ESTERILIZACION.
  2. Buscar en el log la línea de entrada a ESTABLE_PREESTERILIZACION y las de coherencia (Tsat(P), T y diferencia). Anotar T y P en la entrada.
  3. Anotar si hubo reinicios de la ventana o el timeout de recuperación, y su motivo (fuera de banda o coherencia).
  4. Calcular, para el momento de la entrada, `Tsat(P) − T`.
- **Resultado esperado:** Entrada con T ≈ 134,0–134,5 °C y P ≈ 302–309 kPa (no ≈ 315); diferencia `Tsat(P) − T` dentro de ±1 K durante la ventana (3 s); la presión nunca pasa de 315,2 kPa en el calentamiento; el paso a ESTERILIZACION sin reinicios repetidos.
- **Criterio de aprobado/fallo:** Aprobado si entra con la presión de saturación (no con la de antes) y la diferencia T–P queda dentro de 1 K. Si la diferencia es positiva y mayor de 1 K de forma sostenida (presión de más para la temperatura), anotarlo: indica aire residual (revisar prevacío) y es justo lo que C-02 debe impedir.
- **T / P en la entrada:** ________ °C / ________ kPa · **Tsat(P) − T:** ________ K · **Reinicios de ventana:** ________
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### E-T12-03 — Esterilización sin conmutación rápida RECUPERACION ↔ PWM

- **Modo:** En operación (vapor)  ·  **Origen:** E12 C-07/C-08 (tanda 12)
- **Objetivo:** La fase entra a RECUPERACION si `T < 134 + brecha` o `P < 302,7 kPa`, y vuelve a PWM solo con `T ≥ 134 + brecha + 0,3` **y** `P ≥ 303,7 kPa` (histéresis). Con la brecha de 0,3 que conservan los programas de usuario: entrada bajo 134,3 °C y salida desde 134,6 °C. Con 1,0: entrada bajo 135,0 °C y salida desde 135,3 °C. En RECUPERACION el vapor también se corta en el techo `P_control_max = 313,2 kPa` y no vuelve a abrir hasta bajar de 311,2 kPa (histéresis de 2 kPa agregada al unir, DECISIÓN SIN CONFIRMAR). Las fallas (temp/pres alta/baja y saturación) exigen 5 s continuos, no 3 lecturas.
- **Precondiciones:** Mismo ciclo (Instrumental 134 de usuario, 7 min de meseta).
- **Pasos:**
  1. Durante la meseta, registrar cada 15 s T, P y el estado de Vapor cámara (pantalla, o LED de la salida en el módulo E/S); en el log buscar los cambios RECUPERACION ↔ PWM_ACTIVO si se registran.
  2. Durante 1 minuto en la mitad de la meseta, contar cuántas veces cambia Vapor cámara (abre o cierra).
  3. Anotar la presión máxima de cámara en la meseta.
  4. Revisar que ninguna falla dispare por un pico de una sola lectura.
- **Resultado esperado:** Sin alternancia RECUPERACION ↔ PWM en cada tick; P máxima ≤ 313,2 kPa + inercia; meseta completa sin FALLO. **Ojo (observación de L12):** con 134 °C y `presion_add` 9, la temperatura de saturación del techo es `Tsat(313,2) = 135,0 °C`, menor que el umbral de salida (135,3 °C): con vapor saturado lo esperable es que la fase quede **toda la meseta en RECUPERACION** y que la válvula se regule en el techo de 313,2 kPa. Eso no es conmutación RECUPERACION ↔ PWM: la válvula se regula en el techo, entre 311,2 y 313,2 kPa. Con la brecha de 0,3 este caso no aplica (134,6 °C < 135,0 °C) y la meseta debe correr en PWM.
- **Criterio de aprobado/fallo:** Aprobado si no hay conmutación rápida RECUPERACION ↔ PWM y la meseta completa. Si Vapor cámara cambia más de ~20 veces por minuto (en el techo o en la banda), anotar la cuenta, la presión y el tramo y **avisar a Code** (pregunta abierta de L12 sobre el techo).
- **Cambios de Vapor cámara en 1 min:** ________ · **Tramo (log):** ________ · **P máx. meseta:** ________ kPa
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### E-T12-04 — Bowie & Dick de usuario con `presion_add` 9

- **Modo:** En operación (vapor)  ·  **Origen:** J12 C-04.1 (tanda 12)
- **Objetivo:** El Bowie & Dick de usuario (134,5 °C / 3,9 min, F0 activo) ya migrado a `presion_add_calentamiento` 9 completa el ciclo: techo de calentamiento `Psat(134,5) + 9 = 317,7 kPa`, entrada a sostener con `P ≥ 306,7 kPa`, chaqueta ≈ 332,7 kPa. Con 99 el techo era 407,7 kPa (sobre el alivio).
- **Precondiciones:** A-T12-01 aprobada. Cámara vacía con el paquete de prueba Bowie & Dick (hoja indicadora) en el punto habitual, primer ciclo del día tras el calentamiento de chaqueta.
- **Pasos:**
  1. Seleccionar Bowie & Dick de usuario y comprobar en Parámetros del ciclo que `presion_add_calentamiento` es 9.
  2. Iniciar y registrar T y P en la entrada a ESTABLE_PREESTERILIZACION y la presión máxima en calentamiento y meseta.
  3. Anotar F0 total del ticket.
  4. Al terminar, revisar la hoja indicadora.
- **Resultado esperado:** Ciclo COMPLETADO; presión de cámara ≤ 317,7 kPa (+ inercia) en todo el ciclo; entrada con P ≈ 307–311 kPa; F0 total en el ticket; hoja con viraje uniforme (sin zona clara en el centro).
- **Criterio de aprobado/fallo:** Aprobado si completa sin FALLO, sin pasar el techo y con la hoja uniforme. Una hoja no uniforme indica aire: no liberar el equipo y anotar la diferencia `Tsat(P) − T` del log.
- **P máx. calentamiento / meseta:** ________ / ________ kPa · **F0 total:** ________ min · **Hoja:** ☐ uniforme ☐ no uniforme
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### F-T12-01 — Excursión de una Referencia en la exposición: el conteo se detiene y reinicia (C-13)

- **Modo:** En operación (vapor)  ·  **Origen:** E12 C-13 (tanda 12)
- **Objetivo:** Una Referencia fuera de la banda `[T_est − brecha_error_temperatura, T_est + rango_temperatura_ester]` (134 °C: [133,9; 137,0]) durante 5 s continuos detiene el conteo de la exposición; al volver a la banda el conteo se reinicia desde cero (el tiempo restante de la pantalla vuelve al total); F0 no se reinicia. Sin volver en `timeout_excursion_referencia` (5 min) → FALLO CIC-14 (Referencia sin retorno). Cada excursión queda en el ticket con sensor, duración y temperatura mínima (y máxima si salió por arriba). El Principal fuera de banda sigue siendo FALLO.
- **Precondiciones:** Solo si hay una Referencia asignada en el programa (Opciones › Parámetros del ciclo › sensores: `temp_ref` o `temp_2_camara` como Referencia; los programas vienen con `no_en_uso`, asignarla en una copia de Instrumental 134 de usuario). La forma controlable de provocar la excursión es un **simulador de PT100 (o caja de décadas) conectado en el canal de la Referencia** en lugar de la sonda, ajustado a ~134,5 °C (≈ 151,5 Ω; 133,0 °C ≈ 151,0 Ω); sin simulador, la prueba solo se puede observar si la Referencia sale sola de la banda (por ejemplo, dentro de un paquete denso), sin forzarla.
- **Pasos:**
  1. Iniciar el ciclo con el simulador en ~134,5 °C (dentro de banda: la ventana de calentamiento exige Referencias ≥ T_obj).
  2. Con la exposición en marcha (anotar el tiempo restante), bajar el simulador a ~133,0 °C durante **3 s** y volverlo a 134,5: el conteo no debe detenerse.
  3. Bajarlo a ~133,0 °C durante **20 s**: a los 5 s el conteo se detiene; anotar el tiempo restante mostrado.
  4. Volver a 134,5 °C: el tiempo restante vuelve a 7:00 y cuenta de nuevo. Anotar el F0 antes y después (no vuelve a 0).
  5. (Opcional, con un segundo ciclo) dejar la Referencia fuera de banda más de 5 min.
  6. Al terminar, revisar el ticket.
- **Resultado esperado:** Paso 2: sin cambio. Paso 3: conteo detenido tras 5 s, el control de vapor sigue igual (sin FALLO). Paso 4: reinicio desde cero; F0 sigue acumulado. Paso 5: FALLO con alarma CIC-14. Paso 6: una línea por excursión con el nombre de la sonda, duración en s y mínima ≈ 133,0 °C; CIC-09 aparece una sola vez por sensor.
- **Criterio de aprobado/fallo:** Aprobado si una excursión < 5 s no detiene, una > 5 s detiene y reinicia desde cero, F0 no se reinicia y el ticket lista cada excursión. Cualquier conteo que siga corriendo con la Referencia confirmada fuera de banda es Fallo.
- **Tiempo restante al detener / tras volver:** ________ / ________ · **F0 antes / después:** ________ / ________
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### F-T12-02 — Referencia desconectada: el ciclo sigue, SEN-11 y ticket NO CONFORME

- **Modo:** En operación (vapor)  ·  **Origen:** E12 C-13.7b (tanda 12)
- **Objetivo:** Una Referencia sin lectura ya no hace fallar el ciclo: el ciclo continúa con las sondas que leen, aparece la alarma no bloqueante SEN-11 (Referencia sin lectura) con el nombre de la sonda y el ciclo queda marcado **"NO CONFORME: punto de referencia sin verificar"** en el ticket y en el registro, aunque la Referencia vuelva a leer. Un ciclo NO CONFORME no usa apertura automática. El Principal o la presión sin lectura siguen siendo FALLO (SEN-02 / código de presión).
- **Precondiciones:** Programa con una Referencia asignada (como F-T12-01; puede ser la sonda real). Si se quiere comprobar la apertura automática, una copia del programa con `apertura_automatica` = true.
- **Pasos:**
  1. Iniciar el ciclo. Durante la exposición, desconectar el conector de la Referencia (o el simulador) unos 30 s y volverlo a conectar.
  2. Observar la pantalla, la campana y que el ciclo no pasa a FALLO.
  3. Dejar terminar el ciclo; revisar si la puerta se abre sola (con apertura automática) o pide CONFIRMAR.
  4. Revisar el ticket, el detalle del ciclo en el Historial y el PDF.
  5. (Opcional, otro ciclo) desconectar la Referencia durante CALENTAMIENTO: la ventana de estabilidad debe completarse con las sondas que sí leen.
- **Resultado esperado:** Paso 2: alarma SEN-11 no bloqueante con el nombre de la sonda; el conteo de la exposición sigue. Paso 3: flujo manual de confirmación, sin apertura automática. Paso 4: la marca NO CONFORME en el ticket, el Historial y el PDF (en el idioma vigente), aunque la Referencia volvió a leer. Paso 5: el ciclo pasa a ESTERILIZACION sin esperar a la Referencia.
- **Criterio de aprobado/fallo:** Aprobado si el ciclo termina con la marca NO CONFORME y sin apertura automática. Es Fallo si un ciclo con una Referencia que perdió lectura termina como conforme, o si se abre la puerta sola.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

## Bloque H. Control de vapor por chaqueta y pendientes de la tanda 14 (tanda 16, en operación)

### H-01 — Válvulas por fase en modo chaqueta

- **Modo:** En operación (vapor)  ·  **Origen:** VCH §4.1–4.3, §8.1 y §8.8 (tanda 16)
- **Objetivo:** En un equipo con chaqueta, CALENTAMIENTO y ESTERILIZACION controlan con vapor_chaqueta y vapor_camara queda abierta.
- **Precondiciones:** Equipo de piso (clase PISO o PISO_LAB) con vapor_chaqueta y pres_chaqueta. Programa Instrumental 134 °C.
- **Pasos:**
  1. Iniciar el ciclo y revisar en backend.log la línea de CALENTAMIENTO con el modo ("chaqueta").
  2. Observar los LED/relés de DO vapor_camara y vapor_chaqueta durante PRECALENTAMIENTO, PRE_VACIO, CALENTAMIENTO, ESTERILIZACION y SECADO.
  3. Anotar el instante exacto de la transición CALENTAMIENTO → ESTERILIZACION.
- **Resultado esperado:** vapor_camara se abre en el primer tick de CALENTAMIENTO y no se cierra hasta el fin de ESTERILIZACION (tampoco en la transición). vapor_chaqueta conmuta con el control. Al terminar ESTERILIZACION se cierran las dos y la chaqueta vuelve a su consigna.
- **Criterio de aprobado/fallo:** Aprobado si vapor_camara no se cierra en la transición y el control conmuta solo vapor_chaqueta.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### H-02 — Golpe inicial al abrir vapor_camara tras el prevacío

- **Modo:** En operación (vapor)  ·  **Origen:** VCH-02 (D5)
- **Objetivo:** Registrar el pico de presión del golpe inicial y confirmar que no dispara fallas.
- **Precondiciones:** Como H-01. Registro de presión de cámara y de chaqueta (gráfica o log).
- **Pasos:**
  1. Registrar presión de cámara, de chaqueta y temperatura Principal los primeros 60 s de CALENTAMIENTO.
- **Resultado esperado:** El pico de presión no llega al techo de CALENTAMIENTO (sin aislamiento) ni produce CIC-12/CIC-13 ni falla de calentamiento.
- **Criterio de aprobado/fallo:** Aprobado si no hay aislamiento ni falla por el golpe inicial. Anotar el pico (kPa) y su duración.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### H-03 — Sobrepaso y tiempo de calentamiento frente al control anterior

- **Modo:** En operación (vapor)  ·  **Origen:** VCH-01 (ALTA)
- **Objetivo:** Comparar el control por chaqueta con el control por vapor_camara para reajustar los parámetros de las dos fases.
- **Precondiciones:** Ciclos de referencia de la alpha.1 (control por vapor_camara) con el mismo programa y carga.
- **Pasos:**
  1. Correr el mismo programa con la alpha.2 (modo chaqueta).
  2. Medir: tiempo de CALENTAMIENTO, sobrepaso máximo de temperatura y de presión, número de aislamientos y oscilación en ESTERILIZACION.
  3. Repetir variando intervalo_segmentos_calor/ester, factor_*, tasas y rangos si el sobrepaso es alto.
- **Resultado esperado:** Sobrepaso y oscilación dentro de las bandas del programa, sin aislamientos frecuentes.
- **Criterio de aprobado/fallo:** Aprobado cuando hay un juego de parámetros que da un ciclo estable; anotar los valores para fijarlos (VCH-01).
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### H-04 — Aislamiento de cámara por sobrepresión

- **Modo:** En operación (vapor)  ·  **Origen:** VCH §4.4–4.5, §8.3–8.5
- **Objetivo:** Comprobar la entrada, la salida con histéresis y 3 s, y que la exposición y F0 siguen.
- **Precondiciones:** Como H-01. Programa de prueba con presion_add_esterilizacion bajo para alcanzar el techo.
- **Pasos:**
  1. Provocar que la presión de cámara alcance el techo en ESTERILIZACION.
  2. Observar vapor_camara y vapor_chaqueta y el log (entrada/salida del aislamiento).
  3. Comprobar el restante de exposición en pantalla durante el aislamiento.
- **Resultado esperado:** Al llegar al techo se cierran vapor_camara y vapor_chaqueta; reabren cuando la presión baja histeresis_cierre_camara (3 kPa) bajo el techo durante 3 s. La exposición sigue descontando.
- **Criterio de aprobado/fallo:** Aprobado si el aislamiento entra y sale como se describe; anotar cuántos aislamientos hubo por ciclo.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### H-05 — Corte de vapor de chaqueta

- **Modo:** En operación (vapor)  ·  **Origen:** D-CHQ / SAF-09 / VCH-CHQ
- **Objetivo:** Con la chaqueta en presion_max_chaqueta_control (375 kPa abs) la válvula se cierra siempre.
- **Precondiciones:** Equipo con chaqueta. Bajar presion_max_chaqueta_control (Parámetros del equipo › Chaqueta) por debajo de la presión de chaqueta habitual, solo para la prueba.
- **Pasos:**
  1. Correr un ciclo y observar vapor_chaqueta en cada fase.
  2. En CALENTAMIENTO/ESTERILIZACION verificar el aviso CIC-18.
  3. Restablecer el parámetro a 375.
- **Resultado esperado:** vapor_chaqueta queda en OFF mientras la presión de chaqueta esté en el corte, en todas las fases; CIC-18 aparece en CAL/EST (modo chaqueta) y se despeja solo.
- **Criterio de aprobado/fallo:** Aprobado si nunca se ve un pulso de vapor_chaqueta con la presión en el corte.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### H-06 — Temperatura real con la presión en el techo de ESTERILIZACION

- **Modo:** En operación (vapor)  ·  **Origen:** P1 / D-14.1 (DECISIÓN SIN CONFIRMAR)
- **Objetivo:** Datos para confirmar el margen de 0,3 K de la regla P1.
- **Precondiciones:** Programa Instrumental 134 °C (presion_add_esterilizacion 15).
- **Pasos:**
  1. Durante la exposición, registrar la temperatura del Principal y la presión de cámara cuando la presión está en el techo (P_control_max).
  2. Anotar si el control sale de RECUPERACION a PWM_ACTIVO (log).
- **Resultado esperado:** Con la presión en el techo, la temperatura queda por encima de T_est + brecha_segura_temperatura + 0,3 K y el control modula.
- **Criterio de aprobado/fallo:** Anotar T real en el techo y si hay PWM; con eso se confirma o reajusta el margen.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### H-07 — Diferencia Principal–Referencia y oscilación pico a pico

- **Modo:** En operación (vapor)  ·  **Origen:** P3 / D-14.3 y P6 / D-14.6 (DECISIONES SIN CONFIRMAR)
- **Objetivo:** Datos para confirmar brecha_error_temperatura = 0,1 K y el debounce de 5 s en 10 s.
- **Precondiciones:** Equipo con sonda de Referencia asignada como Referencia.
- **Pasos:**
  1. Durante la ventana de CALENTAMIENTO y la exposición, registrar Principal y Referencia cada segundo.
  2. Calcular la diferencia media Principal − Referencia y la oscilación pico a pico de cada sonda.
- **Resultado esperado:** La Referencia no queda más de brecha_error_temperatura bajo T_obj de forma sostenida; la oscilación pico a pico es menor que la banda de falla.
- **Criterio de aprobado/fallo:** Anotar diferencia media, máxima y pico a pico; con eso se confirman o reajustan P3 y P6.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### H-08 — Ciclo NO CONFORME: franja, reconocimiento y marcas

- **Modo:** En operación (vapor)  ·  **Origen:** P4 / D-14.4
- **Objetivo:** Un ciclo con la Referencia sin lectura no se confirma sin el reconocimiento explícito.
- **Precondiciones:** Ciclo corto con la sonda de Referencia asignada.
- **Pasos:**
  1. Desconectar la sonda de Referencia durante la exposición.
  2. Al terminar, intentar CONFIRMAR; luego pulsar «Reconozco que la carga no es liberable» y confirmar.
  3. Revisar el historial, el ticket, el PDF y el correo del ciclo.
- **Resultado esperado:** Franja roja «CICLO NO CONFORME»; CONFIRMAR deshabilitado hasta el reconocimiento; el reconocimiento queda en la bitácora; «NO CONFORME» en historial, ticket, PDF y correo.
- **Criterio de aprobado/fallo:** Aprobado si no se puede confirmar sin reconocer y la marca aparece en todos los registros.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

## Bloque I. Instalación y estación; sondas, estado seguro, modo prueba, pantallas y bitácora (tandas 17 y 18)

### I-01 — Setup: zona horaria de Windows

- **Modo:** En seco (sin vapor)  ·  **Origen:** INS-01 (tanda 17)
- **Objetivo:** El Setup ofrece la zona horaria, la aplica con tzutil y la verifica.
- **Precondiciones:** PC de prueba con Windows en una zona distinta de la deseada. Setup 1.0.0-alpha.2.
- **Pasos:**
  1. Ejecutar el Setup y llegar a la página de zona horaria.
  2. Comprobar que viene marcada la zona actual y que se ven la fecha y hora locales.
  3. Elegir «(UTC-05:00) Bogotá, Lima, Quito» y terminar la instalación.
  4. En una consola: `tzutil /g`. Revisar el log del Setup.
  5. Repetir en silencio con `/VERYSILENT /ZONA="SA Pacific Standard Time"` y con un id inexistente.
- **Resultado esperado:** `tzutil /g` devuelve la zona elegida; el log del Setup la registra; con un `/ZONA=` inexistente el Setup se detiene con mensaje. La bitácora solo tiene la fila `equipo_instalado` (con la zona) tras el asistente.
- **Criterio de aprobado/fallo:** Aprobado si la zona queda aplicada y verificada, y un fallo de tzutil no aborta la instalación (muestra el procedimiento manual).
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### I-02 — Setup: unidad D: y disposición programa/datos

- **Modo:** En seco (sin vapor)  ·  **Origen:** INS-02 (tanda 17)
- **Objetivo:** El Setup instala en `D:\Especifika\Autoclave\{programa,datos}` y escribe la clave de registro.
- **Precondiciones:** PC con un disco fijo D: (NTFS) y una memoria USB conectada.
- **Pasos:**
  1. Llegar a la página de unidad: revisar la lista.
  2. Comprobar la preselección y terminar la instalación.
  3. Revisar `HKLM\SOFTWARE\Especifika\Autoclave` (RutaPrograma, RutaDatos) con regedit (vista de 64 bits).
  4. Arrancar el software y comprobar dónde quedan el perfil, la base, los logs y `estacion\estacion.log`.
- **Resultado esperado:** Solo discos fijos (la USB no aparece, tampoco un disco USB externo); D: preseleccionada; programa en `D:\Especifika\Autoclave\programa`; datos en `...\datos`; nada nuevo en `C:\ProgramData\Especifika\Autoclave`.
- **Criterio de aprobado/fallo:** Aprobado si la disposición y la clave de registro son las esperadas y el programa no vuelve a ofrecerse a instalar.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### I-03 — ACL de programa con un usuario estándar

- **Modo:** En seco (sin vapor)  ·  **Origen:** INS-02 ACL (tanda 17, revisión V17-s1-01)
- **Objetivo:** Un usuario estándar no puede modificar el programa (Clase C).
- **Precondiciones:** Antes de instalar, crear `D:\Especifika` como usuario estándar y darle `Todos: Control total`. Luego instalar como administrador.
- **Pasos:**
  1. `icacls` de `D:\Especifika`, `...\Autoclave`, `...\programa`, `...\datos` y `...\datos\estacion`.
  2. Con el usuario estándar: intentar crear o borrar un archivo en `programa` y en `programa\_internal`.
  3. Con el usuario estándar: abrir Autoclave.
- **Resultado esperado:** Sin herencia; sin la entrada `Todos` ni Usuarios autentificados; programa: Administradores/SYSTEM control total, Usuarios lectura y ejecución; datos: Usuarios modificar; datos\estacion: solo Administradores y SYSTEM. El usuario estándar no puede escribir en programa pero sí abre Autoclave.
- **Criterio de aprobado/fallo:** Aprobado si ninguna escritura en programa tiene éxito con el usuario estándar.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### I-04 — Actualización con la unidad fija y bloqueo de la disposición anterior

- **Modo:** En seco (sin vapor)  ·  **Origen:** INS-02 (tanda 17)
- **Objetivo:** Una actualización reutiliza la unidad; una instalación de la compilación I detiene el Setup.
- **Precondiciones:** (a) Instalada la alpha.2 en D:. (b) Otro PC (o tras desinstalar) con la compilación I instalada en Archivos de programa.
- **Pasos:**
  1. (a) Ejecutar de nuevo el Setup (misma o mayor versión): revisar la página de unidad.
  2. (b) Ejecutar el Setup alpha.2 sobre la compilación I.
- **Resultado esperado:** (a) La unidad aparece fija, sin poder cambiarla; los datos se conservan. (b) El Setup se detiene y pide desinstalar la anterior e instalar en limpio (sin migrar datos).
- **Criterio de aprobado/fallo:** Aprobado si (a) no cambia de unidad ni pierde datos y (b) no instala.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### I-05 — Instalación limpia y desinstalación sobre datos

- **Modo:** En seco (sin vapor)  ·  **Origen:** INS-02 / D11-4 (tanda 17)
- **Objetivo:** La limpia y el desinstalador actúan sobre la carpeta datos nueva.
- **Precondiciones:** Alpha.2 instalada con datos (perfil, usuarios, ciclos).
- **Pasos:**
  1. Mantenimiento › Instalación limpia (dos confirmaciones).
  2. Comprobar el respaldo en `D:\Especifika\Autoclave_respaldos\<fecha>` y que `datos` quedó vacío salvo `estacion`.
  3. Desinstalar: comprobar que la estación se revierte, que se borran los valores de registro y que `datos` se conserva.
- **Resultado esperado:** Respaldo completo y protegido (solo Administradores y SYSTEM); datos vacíos; tras desinstalar, `datos` conservado. Si una reversión falla, `RutaDatos` se conserva.
- **Criterio de aprobado/fallo:** Aprobado si no se borra nada fuera de `datos` y el respaldo es íntegro.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### I-06 — Táctiles sin MultiDigitizer: herramienta propia

- **Modo:** En seco (sin vapor)  ·  **Origen:** EST-06 (tanda 17, DECISIONES SIN CONFIRMAR)
- **Objetivo:** Sin `MultiDigitizer.exe`, el paso 06 usa `Autoclave.exe --rol asociar-tactiles` y cada toque cae en su pantalla.
- **Precondiciones:** PC de prueba sin `C:\Windows\System32\MultiDigitizer.exe`, dos pantallas táctiles.
- **Pasos:**
  1. Instalar con la subtarea de táctiles; tocar cada pantalla cuando lo pida.
  2. Revisar `datos\estacion\estacion.log` (herramienta propia y código de salida).
  3. Exportar `HKLM\SOFTWARE\Microsoft\Wisp\Pen\Digimon` y comparar con una exportación hecha por MultiDigitizer en otro equipo (prefijo `20-`, mayúsculas).
  4. Reiniciar y tocar cada pantalla.
  5. Probar Esc, Enter y el tope de 120 s; la herramienta sin administrador; la reversión (`06_revertir_asociar_tactiles.ps1` o desinstalar).
- **Resultado esperado:** Cada toque cae en su pantalla tras reiniciar; sin administrador sale con 2 sin escribir; la reversión deja Digimon como estaba. El fallo del 06 no corta los demás pasos.
- **Criterio de aprobado/fallo:** Aprobado si la asociación funciona y se revierte limpia.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### I-07b — Del inicio de sesión a la intro: escritorio de la estación, sin cubierta

- **Modo:** En seco (sin vapor)  ·  **Origen:** EST-08 / EST-09 (tanda 18; sustituye a I-07)
- **Objetivo:** Entre el inicio de sesión y la intro solo se ve el fondo de Especifika, sin barra ni íconos.
- **Precondiciones:** Equipo instalado con «Configurar este PC como estación» (autologon, tarea de arranque con Delay PT0S, paso 07).
- **Pasos:**
  1. Reiniciar en frío tres veces, con cronómetro o vídeo.
  2. Observar desde que entra Windows hasta la intro: fondo, barra de tareas, íconos del escritorio y cualquier texto «Iniciando… / Starting…».
  3. Medir el tiempo del inicio de sesión a la intro: Visor de eventos Seguridad 4624 (tipo 2) frente a «Lanzador iniciado» en `datos\lanzador.log`; TaskScheduler/Operational 107/119/100.
  4. Configuración › Personalización: fondo tipo «Imagen» en modo Rellenar en los dos monitores; barra con «Ocultar automáticamente».
  5. Doble clic en el acceso directo con el software abierto (segunda instancia).
- **Resultado esperado:** Solo el fondo de Especifika en los dos monitores, sin barra visible ni íconos y sin «Iniciando… / Starting…»; tiempo medido y anotado; una segunda instancia no abre otras pantallas.
- **Criterio de aprobado/fallo:** Aprobado si el escritorio no muestra barra, íconos ni texto de la cubierta antes de la intro.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### I-08 — Sonda en No en uso: monitoreo

- **Modo:** En seco (sin vapor)  ·  **Origen:** SON-01 (tanda 17)
- **Objetivo:** Una sonda instalada en No en uso se ve y se registra, pero no participa.
- **Precondiciones:** Perfil con Cámara 2 instalada; rol No en uso.
- **Pasos:**
  1. Elegirla en Entradas mostradas (Preciclo, Ciclo en curso, gráfica).
  2. Correr un ciclo corto; desconectar la sonda durante el ciclo.
  3. Revisar gráfica del historial, PDF, correo y ticket.
- **Resultado esperado:** Rotulada «(monitoreo)»; registrada en gráfica, historial, PDF y correo; no en el ticket; sin lectura «—» sin alarma ni aviso; el ciclo no cambia.
- **Criterio de aprobado/fallo:** Aprobado si la sonda nunca afecta al control ni genera alarmas.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### I-09 — Estado seguro sin transductor de presión de cámara

- **Modo:** En seco (sin vapor)  ·  **Origen:** ESG-01 (tanda 17)
- **Objetivo:** Sin presión solo se ve la alarma del sensor, sin CIC-10.
- **Precondiciones:** Estado seguro pendiente (p. ej. arranque tras un ciclo interrumpido). Transductor de presión de cámara desconectado.
- **Pasos:**
  1. Arrancar y observar alarmas, NO ABRIR y el inicio de ciclo.
  2. Reconectar el transductor.
- **Resultado esperado:** Solo SEN-04/SEN-06 (y presión baja/alta si existe), sin CIC-10 por la presión; NO ABRIR visible; inicio bloqueado; protocolo pausado. Al reconectar, el estado seguro sigue normal.
- **Criterio de aprobado/fallo:** Aprobado si no aparece CIC-10 por la presión y la cámara nunca se declara segura sin presión.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### I-10 — Modo prueba con estado seguro activo y protecciones permanentes

- **Modo:** En operación (vapor)  ·  **Origen:** ESG-02 (tanda 17, DECISIONES SIN CONFIRMAR)
- **Objetivo:** Con presión vigente se retiran los bloqueos del estado seguro y rigen siempre las protecciones 1–3.
- **Precondiciones:** Estado seguro activo, presión de cámara con lectura. Sesión de técnico en Entradas/Salidas.
- **Pasos:**
  1. Activar el modo prueba: encender descompresión rápida, de chaqueta y vapor de cámara (puertas cerradas).
  2. Con vapor de cámara encendido, abrir una puerta: observar el corte y el aviso.
  3. Con la cámara presurizada: intentar abrir puerta y desbloqueo; con abrir/desbloqueo encendidos, presurizar.
  4. Desconectar el transductor de presión con el modo prueba activo.
  5. Probar el aire atmosférico con la cámara presurizada.
- **Resultado esperado:** Salidas libres con presión vigente; vapor de cámara cortado en el mismo tick con aviso en pantalla; puerta y desbloqueo rechazados con su código (presurizada, vacío o sin lectura) y cortados si la cámara se presuriza; sin presión vuelven todos los bloqueos; aire atmosférico sigue cortado (D8-3.19). Nada de esto en la bitácora.
- **Criterio de aprobado/fallo:** Aprobado si ninguna combinación permite vapor con puerta abierta ni puerta/desbloqueo con la cámara presurizada.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### I-11 — Pantallas: presión en modo prueba, alarmas y selector de programas

- **Modo:** En seco (sin vapor)  ·  **Origen:** MPR-01, ALM-01, PRC-01 (tanda 17)
- **Objetivo:** La interfaz nueva funciona con el táctil.
- **Precondiciones:** 15 o más programas creados. Alguna alarma activa (p. ej. COM-02).
- **Pasos:**
  1. Entradas/Salidas con modo prueba: presión de cámara en kPa, bar y psi; sin módulo E/S «—».
  2. Preciclo y campana: cada fila solo el nombre; tocar → ventana de detalle; DESPEJAR COM-02/03 con su mensaje de rechazo dentro de la ventana; con un paro, la ventana se cierra y «Confirmar y llevar a estado seguro» queda accesible.
  3. Parámetros del ciclo y Manejo de ciclos: desplegable vertical con desplazamiento táctil y toque fuera.
- **Resultado esperado:** Todo legible y táctil; ninguna ventana emergente tapa las acciones de seguridad.
- **Criterio de aprobado/fallo:** Aprobado si se puede elegir cualquier programa y despejar o ver cualquier alarma sin teclado.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### I-12 — Bitácora: eventos, instalación y filtros

- **Modo:** En seco (sin vapor)  ·  **Origen:** BIT-01..05 (tanda 17)
- **Objetivo:** La bitácora solo guarda lo pedido y se filtra por usuario, categoría y fechas.
- **Precondiciones:** Instalación recién hecha con el asistente.
- **Pasos:**
  1. Tras el asistente: abrir Opciones › Bitácora.
  2. Entrar y salir del modo prueba; probar salidas; 3 logins fallidos y uno bueno; cerrar sesión; 5 fallidos seguidos.
  3. Filtrar por Usuario, por cada Tipo (categoría) y por Desde–Hasta con el calendario.
- **Resultado esperado:** Una sola fila `equipo_instalado` de la instalación (serie, modelo, versión, zona); del modo prueba solo «entra», «salida forzada» y «aire atmosférico cortado»; sin `login_fallido` ni `logout`; el 5.º fallido bloquea igual que antes (`login_bloqueado`). Los filtros dan lo esperado.
- **Criterio de aprobado/fallo:** Aprobado si el bloqueo no cambia y la bitácora no se llena de eventos retirados.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### I-13 — Intro de arranque sin perfil de instalación

- **Modo:** En seco (sin vapor)  ·  **Origen:** ARR-06 (tanda 18)
- **Objetivo:** Sin perfil (o con perfil inválido) la intro se ve en las dos pantallas antes del asistente.
- **Precondiciones:** Equipo sin `installation_profile.json` (instalación limpia); para el caso inválido, un perfil alterado a mano.
- **Pasos:**
  1. Arrancar sin perfil: observar las dos pantallas.
  2. Repetir con un perfil presente pero inválido.
  3. Revisar `datos\lanzador.log`, `ui_puerta1.log`, `ui_puerta2.log` y Opciones › Bitácora tras la instalación.
- **Resultado esperado:** Intro completa (animación y barra) en las dos pantallas; la barra se detiene en «Sin perfil de instalación: se abre el asistente» (o «Perfil de instalación inválido: …») unos 2 s y sale; la puerta 1 pasa al asistente y la 2 al Reposo «Instalación en curso en la pantalla 1». Sin colores de alarma. Nada en la bitácora salvo `equipo_instalado` al terminar.
- **Criterio de aprobado/fallo:** Aprobado si la intro nunca queda trabada y el asistente siempre aparece.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### I-14 — Reinicio del PC al terminar el asistente

- **Modo:** En seco (sin vapor)  ·  **Origen:** REI-01 (tanda 18)
- **Objetivo:** Al terminar la instalación el equipo se reinicia solo y arranca normal.
- **Precondiciones:** Equipo sin perfil, con la estación configurada; ejecutable compilado (Setup).
- **Pasos:**
  1. Completar el asistente: observar la cuenta regresiva de 10 s en las dos pantallas.
  2. Dejarla llegar a 0 en un intento; en otro, pulsar «Reiniciar ahora».
  3. Tras el reinicio: inicio automático, escritorio de la estación y arranque normal.
  4. Revisar `datos\lanzador.log` (reinicio pedido) y que la bitácora tenga una sola `equipo_instalado`.
- **Resultado esperado:** «Instalación completada. El equipo se reiniciará en N s» en las dos pantallas, sin cancelar; el PC reinicia a los 10 s o al pulsar; tras el reinicio, intro y barra completas y menú normal. Si Windows negara el reinicio, `lanzador.log` lo dice y el equipo sigue con el arranque normal.
- **Criterio de aprobado/fallo:** Aprobado si el equipo reinicia y vuelve solo al arranque normal con el perfil nuevo.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### I-15 — Desinstalar devuelve el escritorio original

- **Modo:** En seco (sin vapor)  ·  **Origen:** EST-09 (tanda 18)
- **Objetivo:** La reversión del paso 07 deja el fondo, la barra y los íconos como estaban.
- **Precondiciones:** Anotar (foto) el fondo, el modo de la barra y los íconos antes de instalar.
- **Pasos:**
  1. Instalar con la estación; reparar (Setup › Reparar) y revisar `estacion.log` (`Aplicar paso 07 ... terminado`).
  2. Desinstalar.
  3. Revisar `datos\estacion\estacion.log` y el escritorio tras iniciar sesión.
- **Resultado esperado:** `Revertir paso 07 ... terminado` en el log (revertido antes que 06, 05, 04, 02 y 01); fondo, barra e íconos como en la foto inicial.
- **Criterio de aprobado/fallo:** Aprobado si el escritorio vuelve exactamente al estado anterior.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

## Bloque M. Enlace Modbus TCP con los módulos M31-U y Setup con Modbus (tandas 19 y 20, en seco)

### M-0 — Paso previo: red dedicada y acceso a los módulos

- **Modo:** En seco (sin vapor)  ·  **Origen:** MOD-17 (tanda 19); T20-05 (tanda 20)
- **Objetivo:** El PC habla con el principal M31-U por un puerto de red propio, sin la red de la oficina.
- **Precondiciones:** Módulos montados sin energía en el orden principal (16 AI) → 16 DI → 16 DO n.º 1 (DO 01–16) → 16 DO n.º 2 (DO 17–32) → 6 PT100; negociados (doble pulsación de Reload).
- **Pasos:**
  1. Conectar el puerto de red dedicado del PC a un RJ45 del principal; el segundo RJ45 queda libre (no a la red de oficina).
  2. Instalar con el Setup (M-7): el paso 08 pone en ese adaptador IP fija 192.168.3.10/24, sin puerta de enlace, y cambia la contraseña web del módulo. Anotar la contraseña en el expediente, no en la hoja.
  3. Comprobar con `ipconfig` que el adaptador tiene 192.168.3.10 (una 169.254.x.x indica que no se aplicó).
- **Resultado esperado:** Ping a 192.168.3.7 responde; la web abre y acepta la contraseña nueva; Información del equipo muestra «Enlace de E/S: Modbus TCP (módulos M31-U)».
- **Criterio de aprobado/fallo:** Aprobado si la conexión es directa y la contraseña de fábrica ya no sirve.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### M-1 — Corte por desconexión: el relé abre solo

- **Modo:** En seco (sin vapor)  ·  **Origen:** MOD-08 / MOD-07 (tanda 19; 1,0 s es DECISIÓN SIN CONFIRMAR)
- **Objetivo:** Con una salida encendida, si el PC deja de hablar con los módulos el relé abre en menos de 2 s.
- **Precondiciones:** M-0 aprobado; una salida sin riesgo (p. ej. un indicador) encendida desde Entradas/Salidas en modo prueba; cronómetro.
- **Pasos:**
  1. Caso 1: quitar el cable de red del PC; medir el tiempo hasta que el relé abre.
  2. Caso 2: con la salida encendida otra vez, matar el proceso del backend (Administrador de tareas); medir.
  3. Caso 3: congelar el lazo de control, si existe una forma de prueba; si no, anotar «omitido».
  4. Tras cada caso, restablecer y comprobar que el software reconecta solo, que la reconexión apaga todo y que las salidas no vuelven solas (desde la tanda 20 el registro 0x0C37 solo se anota en el log, ADB-05; ya no da TARJETA_WATCHDOG, que en pantalla se vería como MODULO_ES_WATCHDOG).
- **Resultado esperado:** En los casos ejecutados el relé abre en menos de 2 s (tiempo de desconexión del módulo 1,0 s).
- **Criterio de aprobado/fallo:** Aprobado si en todos los casos ejecutados el relé abre en menos de 2 s.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### M-2 — Composición y orden de los módulos

- **Modo:** En seco (sin vapor)  ·  **Origen:** MOD-06 / MOD-10 (tanda 19)
- **Objetivo:** El software rechaza una composición distinta y una negociación pendiente.
- **Precondiciones:** M-0 aprobado. Unir y separar módulos SIEMPRE sin energía.
- **Pasos:**
  1. Sin energía, quitar el módulo de PT100 y arrancar.
  2. Sin energía, reponerlo SIN negociar y arrancar.
  3. Negociar (doble pulsación de Reload) y arrancar.
- **Resultado esperado:** 1: MODULO_ES_VERSION_INCOMPATIBLE en pantalla (código guardado TARJETA_VERSION_INCOMPATIBLE; composición distinta), inicio bloqueado. 2: MODULO_ES_MODULOS_ORDEN (guardado TARJETA_MODULOS_ORDEN), inicio bloqueado. 3: conexión correcta, sin alarmas del módulo E/S.
- **Criterio de aprobado/fallo:** Aprobado si en 1 y 2 el equipo queda bloqueado y en 3 conecta.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### M-3 — Canal por canal: DI, DO, PT100 y transmisores

- **Modo:** En seco (sin vapor)  ·  **Origen:** MOD-03 / MOD-05 / MOD-07 (tanda 19)
- **Objetivo:** Cada entrada y salida de fábrica corresponde a su función y las direcciones de las expansiones son las previstas.
- **Precondiciones:** M-0 y M-2 aprobados; pantalla de Entradas/Salidas.
- **Pasos:**
  1. Activar cada DI 01–14 desde su elemento de campo y verla cambiar en su función.
  2. Encender en modo prueba cada DO 01–23 (la 13 libre) y la DO 25 (buzzer, 24 VDC) y confirmar la carga que se mueve.
  3. Cada PT100 (RTD 01, 02, 03 y 05) y cada transmisor (AI 01–04; antes de la tanda 23 se rotulaban AI 09–12): lectura coherente; desconectar uno y ver «—» y su alarma.
  4. En la web del módulo, confirmar que los registros de seguridad (tiempo de desconexión, estado de falla de las DO 1–32, filtro de AI 0x0DA2 y de PT100) quedaron con lo que escribe el software.
- **Resultado esperado:** Cada canal en su función; sin lectura, «—» y alarma del sensor; registros de seguridad iguales a lo escrito (si el filtro de AI resulta ser por canal en 0x0FA0, anotarlo).
- **Criterio de aprobado/fallo:** Aprobado si todos los canales coinciden y ninguna salida se mueve sin su orden.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### M-4 — Exactitud de PT100 y AI de presión

- **Modo:** En seco (sin vapor)  ·  **Origen:** MOD-16: MED-01 y MED-02 (tanda 19)
- **Objetivo:** Medir el error de las PT100 del módulo y de las AI frente a patrones.
- **Precondiciones:** Baño o calibrador de temperatura y patrón de presión con certificado vigente.
- **Pasos:**
  1. PT100 contra patrón a 121 y 134 °C: anotar el error de cada canal antes de la calibración de usuario.
  2. Presión contra patrón a 100, 200 y 300 kPa abs: anotar el error de cada transmisor antes de la calibración de usuario.
  3. Hacer la calibración de usuario y repetir las mediciones.
- **Resultado esperado:** Errores anotados antes y después; la decisión de Cristian sobre MED-01 y MED-02 se toma con estos valores.
- **Criterio de aprobado/fallo:** Aprobado si, tras la calibración de usuario, el error es compatible con los umbrales (0,1 °C, 1 K y 2 K; 1,5 y 2 kPa) o Cristian acepta el riesgo por escrito.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### M-5 — Restablecimiento de fábrica del módulo con el software corriendo

- **Modo:** En seco (sin vapor)  ·  **Origen:** MOD-07 / MED-03 (tanda 19)
- **Objetivo:** Tras un Reload largo el software reconecta y reescribe solo la configuración de seguridad.
- **Precondiciones:** M-0 aprobado; software conectado, sin ciclo.
- **Pasos:**
  1. Mantener Reload del principal 5–10 s (restablecimiento de fábrica).
  2. Si la IP vuelve a la de fábrica (192.168.3.7) no hace falta tocar la red; si no, anotarlo y restaurarla.
  3. Esperar la reconexión y revisar en la web los registros de seguridad (como en M-3).
- **Resultado esperado:** Alarma del módulo E/S mientras no hay conexión; reconexión sola; registros de seguridad reescritos; el log dice que la configuración se reescribió y que el módulo se reinició (ADB-04) antes de dar la conexión por verificada; el caso 1 de M-1 vuelve a aprobar.
- **Criterio de aprobado/fallo:** Aprobado si la configuración de seguridad queda reescrita sin intervención.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### M-5b — Prueba aislada: ¿la configuración de falla exige reiniciar el módulo?

- **Modo:** En seco (sin vapor)  ·  **Origen:** ADB-04 (adenda tanda 19; decisión 8 de la tanda 20, pendiente de prueba aislada)
- **Objetivo:** Confirmar si el corte por desconexión funciona con la configuración recién escrita o solo después de un reinicio del módulo.
- **Precondiciones:** Software CERRADO. Una salida sin riesgo cableada a un indicador. Herramienta Modbus de banco (fuera del producto).
- **Pasos:**
  1. Restablecer la fábrica del principal (Reload 5–10 s).
  2. Escribir la configuración de seguridad SIN reiniciar (0x0C35 = 10, 0x0C36 = 1, 0x1B58–0x1B77 = 1) y releerla.
  3. Encender la salida con tráfico de lectura cada 0,1 s y quitar el cable de red: cronometrar si el relé abre.
  4. Reiniciar el módulo (0x0C1D = 0x5BB5 o sin energía) y repetir el paso 3.
  5. Hacer otro Reload, arrancar el software y confirmar en el log que reescribe, reinicia y relee antes de dar la conexión por verificada.
- **Resultado esperado:** Se anota en qué caso abre el relé (antes o después del reinicio). Si abre también antes del reinicio, el reinicio de ADB-04 es innecesario pero inofensivo (se informa a Cristian).
- **Criterio de aprobado/fallo:** Aprobado si después del reinicio el relé abre en menos de 2 s y el software reinicia el módulo cuando reescribe la configuración.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### M-7 — Setup con Modbus: red de los módulos, contraseña web y prueba de conexión

- **Modo:** En seco (sin vapor)  ·  **Origen:** T20-04 / T20-05 (tanda 20); MED-04
- **Objetivo:** El Setup configura la red dedicada, cambia la contraseña web del módulo y prueba la conexión sin pasos manuales en Windows.
- **Precondiciones:** PC con un adaptador Ethernet dedicado a los módulos y otra red (Wi-Fi u otro Ethernet) con salida a Internet; módulos encendidos y negociados. Anotar (foto o `ipconfig /all`) la configuración del adaptador antes de instalar. Contraseña nueva de 1–6 caracteres ASCII anotada en el expediente.
- **Pasos:**
  1. Ejecutar el Setup: en «Red del módulo E/S» comprobar que solo aparecen adaptadores Ethernet físicos (sin Wi-Fi ni virtuales) y elegir el dedicado.
  2. Intentar elegir el adaptador que tiene la puerta de enlace: debe advertir que se perderá esa red; cancelar y elegir el dedicado.
  3. Escribir la contraseña web y su confirmación; terminar la instalación.
  4. En la página de resultado: conexión correcta, modelo M31-XAXX0A00G, 5 módulos, firmware e ID (MAC).
  5. `ipconfig`: el adaptador dedicado tiene 192.168.3.10/24 sin puerta de enlace; la otra red sigue con Internet.
  6. Abrir http://192.168.3.7: la contraseña anterior ya no entra y la nueva sí.
  7. Desconectar el cable del módulo y ejecutar Setup › Reparar: la red se reaplica y la página de resultado da «sin conexión» con la acción sugerida (cable, adaptador, módulo encendido); la instalación no se aborta.
  8. Desinstalar: el adaptador vuelve a la configuración anotada antes de instalar (`datos\estacion\estacion.log`: «Revertir paso 08 ... terminado», antes que el 07).
- **Resultado esperado:** Red aplicada y revertida; contraseña cambiada; resultado correcto con el cable y «sin conexión» sin él; nunca se pierde la red con salida sin advertencia.
- **Criterio de aprobado/fallo:** Aprobado si todos los pasos se cumplen y la contraseña no aparece en `estacion.log`, en el log del Setup ni en `configurar_modulo.log`.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

## Bloque T23. Módulo E/S y numeración RTD 01–06 / AI 01–16 (tanda 23, en seco, después de instalar)

### T23-01 — Entradas/Salidas tras la migración: mismas lecturas con la numeración nueva

- **Modo:** En seco (sin vapor)  ·  **Origen:** AIN-01 / AIN-03 / AIN-05; AIN-R2 (tanda 23)
- **Objetivo:** La migración automática FORMATO 1 → 2 no mueve ningún sensor de canal físico: las presiones salen en AI 01–04 con las mismas lecturas que antes y las temperaturas en RTD 01–06.
- **Precondiciones:** Antes de actualizar: foto de Entradas/Salidas con las lecturas de presión (AI 09–12 en la numeración anterior) y temperatura, cámara a presión atmosférica y fría. Actualizar a la versión de la tanda 23 sin tocar la asignación.
- **Pasos:**
  1. Abrir Entradas/Salidas y comparar cada presión (ahora AI 01–04) y cada temperatura (RTD 01–06) con la foto previa.
  2. En la carpeta de datos, junto a `asignacion_io.json` debe quedar `asignacion_io.json.bak` (el original FORMATO 1) y el archivo nuevo debe tener `"formato": 2`.
  3. En Opciones › Bitácora, buscar la fila «Migración de la asignación de E/S» (evento `asignacion_io_migrada`, categoría configuración) con los puertos anterior → nuevo.
  4. Reiniciar el software y confirmar que no aparece una segunda fila de migración (idempotente).
- **Resultado esperado:** Cada función lee lo mismo que antes (± ruido); presión de cámara coherente con la atmosférica; una sola fila de migración; `.bak` presente.
- **Criterio de aprobado/fallo:** Aprobado si ninguna lectura cambió de sensor y la presión de cámara sigue leyendo lo mismo (AIN-R2).
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### T23-02 — Reasignación por grupo: RTD y AI con el mismo número sin conflicto

- **Modo:** En seco (sin vapor)  ·  **Origen:** AIN-01 / AIN-02 / AIN-04; AIN-R1, AIN-R3 (tanda 23)
- **Objetivo:** La pantalla de Reasignación rotula RTD 01–06 y AI 01–16, ofrece AI 09–16 y trata RTD 01 y AI 01 como puertos distintos.
- **Precondiciones:** Sesión de técnico o superior. Equipo en PREPARADO, sin ciclo. Anotar la asignación vigente para restaurarla al final.
- **Pasos:**
  1. Abrir Opciones › Reasignación: las temperaturas muestran «RTD 0n» y las presiones «AI 0n»; en presión se ofrecen AI 01–16 (las 09–16 libres).
  2. Con una temperatura en RTD 01, asignar una presión a AI 01 (o confirmar que ya lo está): no debe aparecer «conflicto» ni rechazo por puerto ocupado.
  3. Intentar asignar dos presiones al mismo AI: debe dar conflicto.
  4. Restaurar la asignación anotada (o «Restaurar fábrica») y reiniciar el control.
- **Resultado esperado:** Etiquetas RTD/AI correctas; AI 09–16 disponibles con calibración nominal (AIN-04; antes de usarlas en servicio se calibran en sitio, AIN-R3); RTD 01 y AI 01 conviven; dos presiones en el mismo AI sí chocan.
- **Criterio de aprobado/fallo:** Aprobado si no hay falso conflicto entre RTD y AI con el mismo número y sí lo hay dentro de un mismo grupo (AIN-R1).
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### T23-03 — Módulo E/S desconectado: textos con «módulo E/S», ninguno con «tarjeta»

- **Modo:** En seco (sin vapor)  ·  **Origen:** MES-01 / MES-04 (tanda 23)
- **Objetivo:** Al desconectar la red de los módulos, todos los mensajes, alarmas y códigos visibles hablan del «módulo E/S».
- **Precondiciones:** PREPARADO, sin ciclo. Idioma español; repetir el paso 4 en inglés.
- **Pasos:**
  1. Desconectar el cable de red de los módulos (puerto dedicado del PC).
  2. Revisar Preciclo («Alarmas y avisos»), la campana, la ventana de detalle de cada alarma (campo «Código») y la barra de estado seguro.
  3. Reconectar y esperar la reconexión.
  4. Cambiar a inglés y repetir los pasos 1 a 3.
- **Resultado esperado:** Mensajes como «Módulo E/S desconectado: no se puede verificar el paro ni la cámara. NO ABRIR.»; códigos `TARJETA_*` mostrados como `MODULO_ES_*`; en inglés «I/O module», nunca «board».
- **Criterio de aprobado/fallo:** Aprobado si no aparece «tarjeta» (ni «board» en inglés) en ningún texto o código visible.
- **Valor observado:** ______________________________________________
- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)
- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________

### T23-04 — Ticket, PDF, Información del equipo y del sistema y Setup sin «tarjeta»

- **Modo:** En seco (sin vapor)  ·  **Origen:** MES-02 / MES-04 (tanda 23)
- **Objetivo:** Los documentos y pantallas de información usan «módulo E/S».
- **Precondiciones:** Un ciclo corto terminado (en seco basta un ciclo cancelado) con un corte breve de red de los módulos, para que el ticket traiga «Sin datos del módulo E/S».
- **Pasos:**
  1. Imprimir el ticket del ciclo y generar su PDF (Historial).
  2. Abrir Información del equipo e Información del sistema: «Versión del módulo E/S», «ID del módulo E/S», «Firmware del módulo E/S».
  3. Ejecutar el Setup (Reparar) y revisar sus páginas: «Red del módulo E/S» y la página de resultado.
  4. Repetir ticket, PDF e Información en inglés.
- **Resultado esperado:** Ningún texto con «tarjeta» (ni «board» en inglés); un código de alarma `TARJETA_*` en el ticket o el PDF sale como `MODULO_ES_*`.
- **Criterio de aprobado/fallo:** Aprobado si ninguno de los cuatro muestra «tarjeta» o «board».
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
- Versión del software (commit) y firmware de los módulos M31-U (Información del sistema) usados.
- Certificados de calibración de los patrones de temperatura y presión usados.
- Lista de desviaciones/no conformidades encontradas, con su informe de problema (IEC 62304 §9).

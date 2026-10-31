# Anomalías residuales conocidas — 1.0.0-alpha.4

NTC-IEC 62304 §5.8.2 y §5.8.3. Fecha: 27-oct-2026. Base: `dev` después de la tanda 20 (cierre de la migración a Modbus TCP: adenda del banco ADB-01..05, retiro del enlace serial de la ESP32 y Setup con Modbus: red de los módulos, contraseña web y prueba de conexión), que se suma a las tandas 16 a 19. Parte de `anomalias_conocidas_1.0.0-alpha.3.md`.

**Uso previsto de esta versión:** sin uso clínico. Igual que las alpha.1 a alpha.3: equipo de pruebas de laboratorio (puertas manuales), en verificación de banco y validación del proceso. **No se libera carga para uso clínico** con esta versión.

**Enlace de E/S (tanda 20):** **solo Modbus TCP** con los módulos Ebyte M31-U (principal 192.168.3.7:502, unidad 1). **La tarjeta ESP32 ya no es compatible**: el enlace serial, su firmware y la selección `enlace_io.json` se retiraron (copia previa en `G:\Respaldos_autoclave\pre_tanda20_20261027_1448`, etiqueta `respaldo-serial-pre-t20`). El Setup configura la red dedicada del PC (192.168.3.10/24, paso 08), cambia la contraseña web del módulo y prueba la conexión al terminar.

Ninguna de estas anomalías anula las protecciones independientes del software: el enclavamiento mecánico de la puerta por presión (D-02), las válvulas de alivio mecánicas de cámara y chaqueta, y el paro de emergencia por hardware.

## Corregidas en esta versión (tanda 20)

| ID | Anomalía de la alpha.3 | Corrección |
|---|---|---|
| AN-32 | La alpha.3 no conectaba con los módulos reales (composición de 4 esclavos, firmware con prefijo, 0x0C37 como bandera, configuración de falla sin reinicio). | ADB-01 (5 esclavos, el principal como esclavo 0), ADB-02 (firmware solo por la versión), ADB-03 (ID = MAC del principal), ADB-04 (reinicio del módulo con evidencia y relectura tras escribir la configuración; sin reinicio en ciclo ni con salidas encendidas) y ADB-05 (0x0C37 solo valor crudo). |
| AN-30 | MODULOS_ORDEN/WATCHDOG en ciclo invalidan la conexión (DECISIÓN SIN CONFIRMAR). | Aceptada como decisión de Cristian (decisión 7); con ADB-05 ya no hay TARJETA_WATCHDOG por 0x0C37. |
| AN-31 | Elección del enlace en la carpeta del programa; buzzer y calibración de equipos serial al actualizar. | Sin selección de enlace ni equipos serial (T20-03). |
| MOD-17 | Red del PC y contraseña web del módulo a mano. | Paso 08 del Setup (adaptador Ethernet físico, IP fija con respaldo y reversión; Reparar lo reaplica) y contraseña web desde el Setup con `Autoclave.exe --rol configurar-modulo` (T20-04, T20-05). |

## Corregidas en esta versión (tanda 16)

| ID | Anomalía de la alpha.1 | Corrección |
|---|---|---|
| AN-01 | SAF-04: a 134 °C con `presion_add_esterilizacion` = 9 no se salía de RECUPERACION. | P1: regla de coherencia al guardar y cargar (mínimo en el mensaje); programas de fábrica y de usuario de 134 °C con 15 kPa. |
| AN-02 | Programas de usuario con `brecha_segura_temperatura` = 0,3 K. | P2: migración 0,3 → 1,0 con auditoría, SIS-06 y `.bak`; sube `presion_add_esterilizacion` al mínimo de P1 si hace falta, con salvaguarda del alivio. |
| AN-03 | Ventana de CALENTAMIENTO con `T_ref ≥ T_obj`. | P3: `T_ref ≥ T_obj − brecha_error_temperatura`, igual que ESTERILIZACION. |
| AN-04 | NO CONFORME solo en el ticket. | P4: franja roja en la pantalla final, reconocimiento explícito auditado antes de CONFIRMAR, «NO CONFORME» en historial, ticket, PDF y correo. |
| AN-05 | Sin tope de reinicios de la exposición. | P5: `max_reinicios_exposicion` (defecto 3); la siguiente excursión confirmada falla con CIC-17. |
| AN-06 | Debounce de 5 s continuos. | P6: `DebounceAcumulado`, 5 s acumulados en una ventana de 10 s (fallas, C-03 y excursiones). |
| AN-07 | Lecturas fuera del rango físico. | P7: temperatura fuera de 0–200 °C y presión fuera de −10–450 kPa se publican sin lectura, con log del valor crudo. |
| AN-08 | SAF-05 y SAF-09. | P8: el tramo sin lectura se descuenta desde la última lectura válida; corte único de chaqueta (`presion_max_chaqueta_control`, 375 kPa abs). |
| AN-10 | PRG-01. | Roles de sensor validados contra las sondas activas del perfil, al asignar y al iniciar el ciclo. |
| AN-11 | DEU-01: límites de presión como constantes. | Fondo de escala, suministro y alivios en Parámetros del equipo (submenú Chaqueta), con auditoría y regla de coherencia. |

## Corregidas en esta versión (tanda 17, hallazgos de la instalación I)

| ID | Hallazgo | Corrección |
|---|---|---|
| INS-01 | La zona horaria de Windows no se elegía al instalar. | Página de zona horaria en el Setup, `tzutil /s` verificado con `tzutil /g`, `/ZONA=` en silencio. |
| INS-02 | Programa en Archivos de programa y datos en `%ProgramData%` de la unidad del sistema. | Unidad elegible (solo discos fijos, sin USB): `X:\Especifika\Autoclave\{programa,datos}`, ACL explícitas verificadas (un usuario estándar no puede modificar el programa), clave `HKLM\SOFTWARE\Especifika\Autoclave`. |
| SON-01 | Las sondas «No en uso» desaparecían (O11). | Se leen, se muestran con «(monitoreo)» y se registran; no participan en control, fallas ni ticket. |
| ESG-01 | CIC-10 sin el sensor de presión de cámara. | Sin presión solo la alarma del sensor; NO ABRIR y el bloqueo de inicio se mantienen; CIC-10 por los demás motivos. |
| ESG-02 | El modo prueba quedaba bloqueado con el estado seguro activo. | Con presión vigente se retiran los bloqueos propios del estado seguro; protecciones permanentes 1–3 (abajo). |
| PRC-01 / MPR-01 / ALM-01 / UI-VER | Selector de programas en cuadrícula; sin presión en el modo prueba; filas de alarma recargadas; «V:1.0» en las barras. | Desplegable vertical; presión de cámara en la cabecera del modo prueba; filas con solo el nombre y ventana de detalle; versión solo en Información. |
| VER-08 | La versión no aparecía en Información (compilación I, anterior a VER). | Prueba que exige `version_completa()` con `_build_info`. |
| BIT-01..05 | 3 páginas de bitácora en 10 minutos de instalado. | Filtro central de eventos; nada durante la instalación y una fila `equipo_instalado`; sin `login_fallido`/`logout` (el bloqueo de usuario no cambia); filtros por usuario, categoría y fechas con calendario. |
| EST-06 | El paso 06 de la estación fallaba sin `MultiDigitizer.exe`. | Herramienta propia `Autoclave.exe --rol asociar-tactiles`; el fallo no corta la estación. |
| EST-07 | Escritorio de Windows expuesto unos 30 s al iniciar sesión. | Tarea con `PT0S` y cubierta de arranque inmediata (cierre por primer cuadro, 15 s o 180 s); un segundo lanzador no abre nada. |
| A1 | `test_historial_entrada_debajo_de_la_marca` bloqueaba la entrega (R16 §8). | La prueba comprueba la inserción sobre la cabecera sin entradas. |

## Corregidas en esta versión (tanda 18, hallazgos de la instalación de la alpha.2)

| ID | Hallazgo | Corrección |
|---|---|---|
| ARR-06 | Sin perfil no se veía la intro de arranque: solo «Iniciando… / Starting…» y el asistente. | Intro completa en las dos pantallas; la barra se detiene en «Sin perfil de instalación…» o «Perfil de instalación inválido…» unos 2 s y pasa al asistente (puerta 1) y al Reposo (puerta 2). Sin bitácora. |
| REI-01 | Al terminar el asistente se seguía sin reiniciar el PC. | Cuenta regresiva de 10 s con «Reiniciar ahora» (sin cancelar) en las dos pantallas; el lanzador reinicia con `shutdown /r /t 0` solo en el compilado de Windows. Si Windows lo niega, hay un backend escuchando o el PC no reinicia en 120 s, se sigue con el arranque normal. |
| EST-08 | «Iniciando… / Starting…» de la cubierta antes de la animación de arranque. | Se retira la cubierta de arranque de EST-07 (sale AN-22); se conserva `Delay PT0S`. |
| EST-09 | Escritorio de Windows visible entre el inicio de sesión y la intro. | Paso 07 de la estación: fondo de Especifika en modo Rellenar, barra con ocultar automáticamente e íconos ocultos, con respaldo y reversión (desinstalador primero, Reparar lo reaplica). |

## Protecciones permanentes del modo prueba (ESG-02)

Rigen siempre, con o sin estado seguro; fallan cerradas (sin dato no se permite); rechazo con código propio y sin bitácora:
1. `abrir_puerta_N` se rechaza con la cámara fuera de `presion_atmosferica ± rango_presion_atm` (presurizada o en vacío) o sin lectura (`salida_prueba_camara_presurizada`); si la cámara se presuriza con la salida encendida, se apaga.
2. `desbloqueo_puerta_N` (vacío al empaque), igual que 1.
3. `vapor_camara` se rechaza si alguna puerta instalada no está confirmada cerrada o no tiene lectura (`salida_prueba_puerta_abierta`), y se apaga en el mismo tick si una puerta deja de estar cerrada, con aviso en Entradas/Salidas.

Se conservan el corte de `aire_atmosferico_camara` (D8-3.19) y la regla anterior de puertas por temperatura. Sin lectura vigente de presión rigen todos los bloqueos anteriores.

Riesgo residual (ISO 14971): sin datos de presión o de puerta el modo prueba queda más restringido; el técnico debe resolver el sensor antes de probar esas salidas.

## Vigentes

| ID | Anomalía | Efecto / riesgo | Mitigación en esta versión | Se corrige en |
|---|---|---|---|---|
| VCH-01 | **ALTA.** Los parámetros de CALENTAMIENTO y ESTERILIZACION (intervalos, factores, tasas, rangos) se ajustaron para `vapor_camara`. Con la chaqueta como válvula de control (equipos de piso) hay más retardo y más riesgo de sobrepaso. | Sobrepaso de temperatura o presión, aislamientos frecuentes (CIC-15/16). | **Antes de liberar, reajustarlos en el banco con la chaqueta.** Aislamiento por sobrepresión, fallas de la fase y alivio mecánico. | Banco (hoja de pruebas, sección VCH) |
| VCH-02 | Golpe inicial de vapor al abrir `vapor_camara` después del prevacío (D5, aceptado). | Pico de presión al inicio del calentamiento. | Aislamiento VCH-AIS y fallas de la fase. Verificar en el banco que no dispare sobrepresión ni CIC-12/13. | Banco |
| AN-09 | Líquidos: implementación provisional de la tanda 11; C-11/C-12 sin implementar. | Igual que en la alpha.1. | Igual que en la alpha.1. | Tanda posterior |
| AN-13 | Prueba de humo fuera del script de entrega. | Igual que en la alpha.1. | Prueba de humo manual (§ siguiente). | Pendiente |
| AN-14 | DECISIONES SIN CONFIRMAR de P1 (margen 0,3 K e histéresis 0,3 K), P3 (`brecha_error_temperatura` = 0,1) y P6 (5 s de 10 s), aplicadas sin los datos del banco (D-14.1, D-14.3, D-14.6). | Puede haber falsos FALLO o una confirmación más lenta que la deseada. | Valores configurables; registrar en el banco la temperatura real con la presión en el techo, la diferencia Principal–Referencia y la oscilación pico a pico. | Banco |
| AN-15 | Los límites de presión que se cambian en Parámetros del equipo se aplican a los programas en la carga y al cambiar el límite, pero la migración P2 del arranque se evalúa con los valores de fábrica, antes de leer los del sitio (V16-s4-02). | En un sitio con un alivio distinto de 385 kPa, un programa puede quedar dañado tras migrarse en memoria, o válido de más hasta revalidar. | Esta versión solo se instala en el equipo de pruebas en Bogotá, con los límites de fábrica. | Tanda posterior |
| AN-16 | El fondo de escala configurable (100–1000 kPa) no se ata al rango real del transductor (0–400 kPa) ni a la plausibilidad P7 (450 kPa) (V16-s4-03, s2-02). | Con un fondo y un alivio por encima de 400, el corte de chaqueta podría quedar por encima de lo que el transductor mide. | No cambiar los límites de fábrica en el equipo de pruebas. | Decisión de Cristian |
| MED-01 | **ALTA** (tanda 19, MOD-16). Exactitud de las PT100 del módulo M31-GXDXX0600-U: ±(0,1 % + 1 °C), unos ±1,1 °C a 134 °C, frente a los umbrales de 0,1 °C (temperatura baja en ESTERILIZACION), 1 K (coherencia C-02) y 2 K (C-03). | Carga dada por buena con la temperatura real por debajo de la medida, o fallos falsos. | Calibración de usuario por canal; compensación interna del módulo en 0 y filtro en 1. **Bloquea la liberación clínica.** | Banco M-4 y decisión de Cristian |
| MED-02 | MEDIA (tanda 19). Exactitud de las AI de una sola terminal (3 ‰): unos ±1,2 a 1,5 kPa en 0–400 kPa, frente a `brecha_error_presion` 2 kPa y `brecha_segura_presion` 1,5 kPa. | Fallos falsos de presión baja o RECUPERACION tardía. | Calibración de usuario por canal; falla de lazo 3600/21000 µA y piso 3850 µA. | Banco M-4 y decisión de Cristian |
| MED-03 | MEDIA (tanda 19, actualizada en la 20). La configuración de seguridad vive en el módulo; un restablecimiento de fábrica o un cambio por la web la borra; el módulo descarta en silencio una escritura fuera de rango; la configuración de falla puede necesitar un reinicio para activarse. | Salidas que no se apagan al perder la comunicación. | Se lee, se escribe lo que difiere y se relee en cada conexión (MOD-07); si se escribió algo, se apagan y comprueban las salidas, se reinicia el módulo con evidencia y se relee todo antes de verificar la conexión (ADB-04; en ciclo no se escribe ni se reinicia: la conexión queda sin verificar); contraseña web cambiada por el Setup. Residual: evidencia de reinicio indirecta y banderas en memoria (V20-rr-02/03). | Banco M-5, M-5b y M-1 |
| AN-29 | DECISIONES SIN CONFIRMAR de la tanda 19 que siguen vigentes (detalle en `docs/informes/tanda19/R19_informe.md` §5): sondeo 100 ms y corte del módulo a 1,0 s; filtro de PT100 1 y filtro de AI 0x0DA2 como registro único (el manual se contradice); texto de modelo, MAC y máscara con la palabra/byte alto primero; `discrepancia_dispara_fallo` true; piso de señal con cuenta > 3850; PT100 fuera de −50…250 °C = sin lectura; encender exige tick reciente del lazo, `all_off` y el 0F tras una conexión fallida salen siempre; respaldo con otra calibración de fábrica rechazado. (Las de la selección de enlace y la bandera 0x0C37 dejaron de aplicar en la tanda 20.) | Interpretaciones pendientes de Cristian. | Todas fallan cerradas. | Banco (bloque M) y decisión de Cristian |
| MED-04 | MEDIA (tanda 20). Modbus TCP no tiene autenticación: cualquier equipo en la red de los módulos puede leer y escribir registros y bobinas; la contraseña web se puede leer por la función 03 (0x7590). | Salidas o configuración alteradas por un tercero con acceso a la red de los módulos. | Red dedicada (paso 08: adaptador propio, sin puerta de enlace), segundo RJ45 libre, contraseña web cambiada por el Setup; configuración reescrita y releída en cada conexión; la contraseña nunca va al repositorio, logs, línea de comandos ni resultado. | Banco M-0 y M-7; decisión antes de la liberación clínica |
| AN-33 | DECISIONES SIN CONFIRMAR de la tanda 20 (detalle en `docs/informes/tanda20/R20_informe.md` §8): `/status.enlace_io` constante `"modbus"`; alarmas solo-serial conservadas para el historial; acciones de alarma reescritas sin la ESP32; texto 0x0C2C prevalece sobre el byte bajo de 0x0C1F y regla «esclavo ≤ principal» (la tabla del manual no es monótona); ADB-04 con espera 5 s, presupuesto 30 s, evidencia = cierre o 2 lecturas sin respuesta, tope de 2 reinicios sin verificar y sin reinicio en ciclo; codificación de usuario/contraseña web (2 ASCII por registro); el rol solo reintenta sin conexión; Setup: `/ADAPTADOR=` inválido detiene el Setup, `/ADAPTADORCONFIRMADO=1` para el único adaptador con puerta de enlace, `Exec` del rol sin tope propio, DNS manuales sobre DHCP vuelven a automáticos, respaldo `respaldo_08_red_modulos.json`. | Interpretaciones pendientes de Cristian. | Todas fallan cerradas. | Banco (bloque M) y decisión de Cristian |
| AN-34 | Tanda 20 (HAZ-T2-03): `_TOLERANCIA_DI_VENCIDA_SEG = 4,0 s` se justificaba con el WD de 5 s del firmware de la ESP32; con Modbus el módulo corta a 1,0 s sin tráfico y el enlace declara la pérdida tras 3 transacciones fallidas. | Ninguno conocido (el corte del módulo es más rápido que la tolerancia). | Valor sin cambiar. | Decisión de Cristian |
| AN-35 | Tanda 20: el `.iss` del Setup con Modbus (páginas de red, contraseña y resultado; paso 08) solo se validó con pruebas estáticas y la compilación de la entrega; los `.ps1` del paso 08 no se ejecutaron en un PC real. | El paso 08 o la prueba de conexión podrían fallar en el PC del equipo. | Respaldo antes de cambiar la red, restauración ante un fallo a mitad, reversión al desinstalar; la instalación nunca aborta por la prueba de conexión. | Banco M-7 |
| AN-17 | SIS-06 dice «kPa» y «sobre el máximo» también para la migración de `brecha_segura_temperatura` (°C) de P2. | Texto del aviso impreciso. | El registro de auditoría lleva el parámetro, el valor anterior y el nuevo. | Tanda posterior |
| AN-18 | El reconocimiento de carga NO CONFORME no exige sesión (se audita sin usuario si no la hay; V16-s5-01). | Trazabilidad incompleta del reconocimiento. | Queda en la bitácora con el operador del ciclo en el detalle. | Decisión de Cristian |
| AN-19 | El corte de chaqueta y CIC-18 no tienen histéresis (V16-s3-05). | Con la chaqueta oscilando en 375 kPa, la válvula y el aviso conmutan en ticks alternos. | Suministro regulado a 40 psig (no debería llegar al corte, VCH-04). | Tanda posterior |
| AN-20 | DECISIONES SIN CONFIRMAR de ESG-02 (tanda 17): el criterio de puerta cubre también el vacío; la recuperación de arranque pendiente también se libera con presión vigente; `bomba_vacio` no se bloquea (solo lleva vacío al empaque con `desbloqueo_puerta_N`, ya protegida); sin presión, `vapor_camara` con puerta abierta se rechaza con el código del estado seguro; `salida_prueba_cortada` (actuación de las protecciones) va solo al log de desarrollo y al aviso de pantalla (BIT-01). | Interpretación pendiente de Cristian. | Las protecciones 1–3 fallan cerradas; el aviso de corte queda en pantalla. | Decisión de Cristian |
| AN-21 | DECISIONES SIN CONFIRMAR de EST-06 (tanda 17): formato Digimon (`20-` + ruta HID → ruta del monitor) documentado sin una exportación real de MultiDigitizer. | Los táctiles podrían no asociarse. | Respaldo y reversión; el fallo no corta la estación; asociación manual. | Banco (I-06) |
| AN-23 | DECISIONES SIN CONFIRMAR de ALM-01 (tanda 17): «Confirmar y llevar a estado seguro» fuera de la ventana de detalle; las ventanas emergentes se cierran ante un paro o estado seguro urgente en las dos pantallas. | Ninguno conocido. | Acción de seguridad de acceso directo. | Decisión de Cristian |
| AN-24 | ESG-01: la trama AI vencida también cuenta como presión sin lectura (sin CIC-10 por ella). `Autoclave.exe` abierto desde una USB en un equipo con el Setup solo avisa. | Ninguno conocido (falla cerrada). | NO ABRIR y el bloqueo de inicio se mantienen. | Decisión de Cristian |
| AN-25 | DECISIONES SIN CONFIRMAR de REI-01 (tanda 18): `shutdown /r /t 0` sin `/f`; si Windows acepta pero no reinicia (una aplicación lo bloquea o se cancela), el lanzador espera 120 s y sigue con el arranque normal; con un backend escuchando no se reinicia (V18-01/02). | Hasta 120 s sin pantallas si el reinicio se bloquea. | Solo tras el código de instalación terminada con perfil válido; desactivado en desarrollo; todo queda en `lanzador.log`. | Banco (I-14) |
| AN-26 | EST-09 (tanda 18): `BackgroundType` y `StuckRects3` no están documentados por Microsoft; la reversión no restaura fondos distintos por monitor ni la configuración de una presentación/Spotlight; sin `-Usuario` ni `DefaultUserName` el paso 07 actúa sobre la cuenta que ejecuta (V18-05/06/07). Las pruebas automáticas del paso 07 son de texto (no aplican ni revierten). | Escritorio no exactamente igual tras desinstalar; en un PC con otra cuenta de administrador, ajustes en la cuenta equivocada. | Respaldo por valor (también la ausencia), reversión por lista blanca y SID; el PC de la estación tiene una sola cuenta; ida y vuelta JSON del binario verificada en Windows PowerShell 5.1. | Banco (I-07b, I-15) |
| AN-27 | DECISIONES SIN CONFIRMAR de ARR-06 (tanda 18): mensaje sin perfil sostenido 2 s; la intro termina sola a los 15 s aunque la barra no se haya visto. | Mensaje más corto en un arranque muy lento. | Nunca deja la pantalla en la intro. | Banco (I-13) |
| AN-28 | EST-08 (tanda 18): sin la cubierta, el escritorio de la estación recibe toques entre el inicio de sesión y la intro. | Un toque podría abrir algo del escritorio. | Sin íconos ni barra visibles (EST-09). | Banco (I-07b) |

## Instalación de la alpha.4
La alpha.4 **actualiza** una alpha.2 o alpha.3 con el Setup (misma disposición `X:\Especifika\Autoclave\{programa,datos}`). Novedades del Setup: página «Red de los módulos de E/S» (elegir el adaptador Ethernet dedicado; no se ofrecen Wi-Fi ni virtuales), página de contraseña web del módulo (obligatoria en instalación nueva; vacía = no se cambia en actualización o Reparar) y página final con el resultado de la prueba de conexión (no aborta la instalación). Silencioso: `/ADAPTADOR=<MAC>` (y `/ADAPTADORCONFIRMADO=1` si es el único adaptador con puerta de enlace); en silencioso la contraseña no se cambia.

### Regla heredada de la alpha.2
Por INS-02 (D-17.2b) el Setup de la alpha.2 **no actualiza** una instalación con la disposición anterior (compilación I o alpha.1 en Archivos de programa): se detiene y pide desinstalarla e instalar en limpio. **No hay migración de datos**: antes de desinstalar, exportar el respaldo y la bitácora si se necesitan; el perfil de instalación, la calibración y los usuarios se vuelven a crear con el asistente.

## Pruebas de banco de las tandas 19 y 20 (enlace Modbus; detalle en la hoja de banco, bloque M)
- M-0: red dedicada configurada por el Setup (paso 08), comprobada con `ipconfig` (una 169.254.x.x indica que no se aplicó); segundo RJ45 libre.
- M-1: corte por desconexión con una salida encendida (cable de red, proceso muerto, lazo congelado si se puede): relé abierto en menos de 2 s; las salidas no vuelven solas al reconectar.
- M-2: sin el módulo de PT100 → TARJETA_VERSION_INCOMPATIBLE; repuesto sin negociar → TARJETA_MODULOS_ORDEN; negociado → conexión. Anotar los valores crudos de 0x0C1F, 0x0D80 y 0x0C2C.
- M-3: canal por canal (DI 01–14, DO 01–23 y 25, PT100 1/2/3/5, AI 09–12) y registros de seguridad en la web.
- M-4: exactitud de PT100 (121 y 134 °C) y presión (100, 200 y 300 kPa abs), antes y después de la calibración de usuario (MED-01, MED-02).
- M-5 (ampliada): Reload largo con el software corriendo: reconecta, reescribe la configuración, reinicia el módulo (log de ADB-04) y la verifica.
- M-5b (nueva): prueba aislada de ADB-04: ¿el corte funciona con la configuración recién escrita o solo tras reiniciar el módulo?
- M-7 (nueva): Setup con Modbus: adaptador e IP, advertencia del único adaptador con puerta de enlace, contraseña web cambiada (entrar a http://192.168.3.7 con la nueva), prueba de conexión correcta y con el cable desconectado (Reparar), cambio de adaptador en Reparar, reversión al desinstalar; la contraseña no aparece en ningún log.

## Pruebas manuales en el PC de prueba (tanda 18; detalle en la hoja de banco, bloque I)
- Intro sin perfil (I-13): en las dos pantallas, con perfil ausente e inválido; asistente y Reposo después.
- Reinicio al terminar el asistente (I-14): cuenta regresiva de 10 s, «Reiniciar ahora», reinicio y arranque normal con intro completa.
- Del inicio de sesión a la intro (I-07b, sustituye a I-07): solo el fondo de Especifika, sin barra, íconos ni «Iniciando… / Starting…»; medir el tiempo.
- Desinstalar devuelve el escritorio (I-15): fondo, barra e íconos originales; `Revertir paso 07 ... terminado`.

## Pruebas manuales heredadas (tanda 17)
- Zona horaria (I-01): página, `tzutil /g`, `/ZONA=` válido e inválido.
- Unidad D: (I-02): solo discos fijos, sin USB; disposición `D:\Especifika\Autoclave\{programa,datos}`; clave de registro.
- ACL de `programa` (I-03): con `D:\Especifika` creada antes por un usuario estándar con `Todos:F`; el usuario estándar no puede escribir en `programa`; `AplicarAcl` con código 0 como administrador.
- Actualización (I-04): con la unidad fija y sin pérdida de datos.
- Bloqueo de la disposición anterior (I-04): con la compilación I instalada, el Setup se detiene.
- Instalación limpia y desinstalación (I-05), incluida una reversión fallida que conserve `RutaDatos`.
- Táctiles sin MultiDigitizer (I-06): herramienta propia, exportación de Digimon comparada, reversión.
- SON-01, ESG-01, ESG-02, MPR-01/ALM-01/PRC-01 y bitácora (I-08 a I-12).

## Prueba de humo en el equipo (después de instalar la alpha.4)
1. Instalación limpia: intro con «Sin perfil de instalación…», el asistente crea el perfil, cuenta regresiva y reinicio del PC; tras el reinicio, escritorio de la estación y arranque normal; la bitácora tiene una sola fila `equipo_instalado` con la zona horaria.
2. Información del sistema, el ticket de arranque y la primera línea de los logs muestran `1.0.0-alpha.4 (<commit>)`.
3. Login, Preciclo, modo prueba de E/S, Parámetros del ciclo (`histeresis_cierre_camara`, `max_reinicios_exposicion`) y del equipo (submenú Chaqueta: corte, aislamientos y límites de presión), historial, exportar respaldo y apagar equipo.
4. Información del equipo muestra «Enlace de E/S: Modbus TCP (módulos M31-U)»; el ID es la MAC del principal (`005404849DB1` en el banco) y el firmware `9232-0-13 / 10,12,12,12,10`; las lecturas de los sensores son coherentes. La página final del Setup dio «conexión correcta» y la web del módulo pide la contraseña nueva.
5. Un ciclo en seco termina con la versión en el ticket y en el historial; el log de CALENTAMIENTO indica el modo de vapor (chaqueta en el equipo de piso).
6. Los programas de usuario cargan sin quedar dañados; si se migraron, aparece SIS-06 y hay `.bak`.

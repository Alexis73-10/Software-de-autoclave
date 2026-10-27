# Anomalías residuales conocidas — 1.0.0-alpha.3

NTC-IEC 62304 §5.8.2 y §5.8.3. Fecha: 27-oct-2026. Base: `dev` después de la tanda 18 (hallazgos de la instalación de la alpha.2: intro sin perfil, reinicio del PC al terminar el asistente, retiro de la cubierta de arranque y escritorio de la estación), que se suma a la tanda 16 (pendientes de la tanda 14 + control de vapor por chaqueta VCH + PRG-01 + DEU-01) y de la tanda 17 (hallazgos de la instalación I: Setup con unidad y zona horaria, sondas en monitoreo, estado seguro y modo prueba, bitácora, arranque y táctiles). Parte de `anomalias_conocidas_1.0.0-alpha.2.md` (y esta de la alpha.1).

**Uso previsto de esta versión:** igual que la alpha.1 y la alpha.2. Equipo de pruebas de laboratorio (puertas manuales), en verificación de banco y validación del proceso. **No se libera carga para uso clínico** con esta versión.

Ninguna de estas anomalías anula las protecciones independientes del software: el enclavamiento mecánico de la puerta por presión (D-02), las válvulas de alivio mecánicas de cámara y chaqueta, y el paro de emergencia por hardware.

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

## Instalación de la alpha.3
La alpha.3 **actualiza** una alpha.2 con el Setup (misma disposición `X:\Especifika\Autoclave\{programa,datos}`, unidad fija). Una instalación anterior a la alpha.2 sigue la regla de la alpha.2:

### Regla heredada de la alpha.2
Por INS-02 (D-17.2b) el Setup de la alpha.2 **no actualiza** una instalación con la disposición anterior (compilación I o alpha.1 en Archivos de programa): se detiene y pide desinstalarla e instalar en limpio. **No hay migración de datos**: antes de desinstalar, exportar el respaldo y la bitácora si se necesitan; el perfil de instalación, la calibración y los usuarios se vuelven a crear con el asistente.

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

## Prueba de humo en el equipo (después de instalar la alpha.3)
1. Instalación limpia: intro con «Sin perfil de instalación…», el asistente crea el perfil, cuenta regresiva y reinicio del PC; tras el reinicio, escritorio de la estación y arranque normal; la bitácora tiene una sola fila `equipo_instalado` con la zona horaria.
2. Información del sistema, el ticket de arranque y la primera línea de los logs muestran `1.0.0-alpha.3 (<commit>)`.
3. Login, Preciclo, modo prueba de E/S, Parámetros del ciclo (`histeresis_cierre_camara`, `max_reinicios_exposicion`) y del equipo (submenú Chaqueta: corte, aislamientos y límites de presión), historial, exportar respaldo y apagar equipo.
4. Las lecturas de los sensores coinciden con las de la alpha.1.
5. Un ciclo en seco termina con la versión en el ticket y en el historial; el log de CALENTAMIENTO indica el modo de vapor (chaqueta en el equipo de piso).
6. Los programas de usuario cargan sin quedar dañados; si se migraron, aparece SIS-06 y hay `.bak`.

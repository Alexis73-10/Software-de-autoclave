# Tanda 6: decisiones para revisar

Formato: decisión · motivo · alternativa · commit · cómo revertir.

## T2 (respuestas a T1)
| Id | Decisión | Motivo | Alternativa | Commit | Cómo revertir |
|---|---|---|---|---|---|
| T2-1 | Tolerancia de DI vencida = 4 s | WD del firmware V3 = 5 s; 1 s de margen. Ese WD mide PC→tarjeta y no protege este caso | 5 s | 5d7c93b | `_TOLERANCIA_DI_VENCIDA_SEG` en `ciclo.py` |
| T2-2 | Durante la tolerancia: vapor de cámara y chaqueta OFF, la fase no corre; 3 ticks vigentes reinician | Revisión TMG-01/02/03, SAF-01 | Seguir la fase con solo AI | 5d7c93b | Bloque P-3 de `ciclo.py` |
| T2-3 | Despeje manual de COM-02/03 = reconocimiento explícito con botón DESPEJAR nuevo (usuario "operador", sin rol) | Sin botón, con P-4 el equipo quedaba bloqueado desde QML | Exigir sesión; despejar al volver el enlace | 25727f6 | `DESPEJE_POR_RECONOCIMIENTO` y el botón en `PanelNotificaciones.qml` |
| T2-4 | Un 0 de un sensor de temperatura en uso = sin lectura en ciclo | Coherencia con `estado_sensor`/`temp_seguridad` (SEN-01) | Solo None | 5d7c93b | Lista `ausentes` en `ciclo.py` |
| T2-5 | P-12: 3 lecturas en o bajo el menor `temp_max_apertura` para la rápida; sin valor global, siempre la lenta | Debounce estándar; falla segura | Sin debounce | 5b1afa9 | `_liquido_frio_para_rapida` |
| T2-6 | Se conservan el alias `DISTINTO_DE_CICLO_E_HIBERNACION` y el manejador muerto de HIBERNACION en `Main.qml` | Cambio mínimo | Renombrar o quitar | commit P-8 | — |
| T2-7 | Marca "CARGA NO ESTÉRIL" solo en INTERRUMPIDO | Es lo pedido en P-9 | Todos los fallos | 34552db | `format_footer` |

## PREGUNTAS PARA CRISTIAN (T2)
- ¿Los segundos de tolerancia por DI vencida cuentan como exposición en ESTERILIZACION?
- ¿DESPEJAR debe exigir el enlace "ok" o una sesión?
- ¿La marca "no estéril" también para FALLO/CANCELADO/EMERGENCIA?

## C1 (correcciones de la tanda 5)
| Id | Decisión | Motivo | Alternativa | Commit | Cómo revertir |
|---|---|---|---|---|---|
| C1-1 | DECISIÓN SIN CONFIRMAR. El teclado PySide usa el mismo juego de caracteres del QML (TEC-D03): no admite `# $ % & , ;`. | Una sola lógica para los dos teclados | Ampliar el juego solo en PySide | C1a | `SIMBOLOS` en `ui_qml/domain/teclado_alfanumerico.py` |
| C1-2 | DECISIÓN SIN CONFIRMAR. Aa queda armada con el campo vacío también en el usuario de login, así que la primera letra sale en mayúscula. | TEC-D05, igual que en QML | Desarmar Aa en los campos de usuario | C1a | `aa_al_abrir` / `DialogoCredenciales.activar` |
| C1-3 | DECISIÓN SIN CONFIRMAR. El teclado se conecta a todo QLineEdit y spinbox de las vistas PySide, incluida la calibración. El valor se valida contra el mín./máx. del spinbox. | "Cualquier lugar que pida texto" | Solo los QLineEdit | C1a | Quitar `conectar_todos(self)` de cada vista |
| C1-4 | DECISIÓN SIN CONFIRMAR. El admin aterriza en Usuarios aunque Parámetros del equipo esté antes en la lista. | Conserva el comportamiento de la tanda 5 | Aterrizar en la primera sección visible | C1b | `seccion_inicial` en `permisos_opciones.py` |
| C1-5 | DECISIÓN SIN CONFIRMAR. `vacio_empaque` y `presion_empaque` se clasifican como "absoluto". | `advanced_door.py` los compara directamente con la lectura del sensor de empaque | "diferencia", si el transductor es manométrico | C1c | Cambiar `clase` en `global_params.json` |
| C1-6 | DECISIÓN SIN CONFIRMAR. `rango_calentamiento` se clasifica como "sin_conversion". | Banda de °C y de kPa a la vez en `calentamiento.py` | Separarlo en dos parámetros (PREGUNTA PARA CRISTIAN, de la tanda 5) | C1c | `clase` en los 8 JSON |
| C1-7 | DECISIÓN SIN CONFIRMAR. Una clase desconocida no se convierte y se muestra en la unidad original. Sin clase, se usa la migración por prefijo con una advertencia en el log. Los programas viejos no se reescriben. | Lo más seguro y reversible | Reescribir los archivos al cargarlos | C1c | `clase_de_unidad` |
| C1-8 | DECISIÓN SIN CONFIRMAR. "El catálogo" se interpreta como `catalogo_parametros.py`. No tiene hojas propias: una prueba exige que sus entradas absolutas tengan "clase": "absoluto" en los JSON. | El catálogo solo guarda límites | Agregar la clase al catálogo | C1c | `test_catalogo_absolutos_coinciden...` |

## PREGUNTAS PARA CRISTIAN (C1)
- ¿Los programas duplicados antes de C1c (sin "clase") se reescriben con la clase, o basta con la migración con advertencia?
- ¿El transductor de empaque mide en absoluto?

## R1 (hallazgos Medios/Bajos pendientes)
| Id | Decisión | Motivo | Alternativa | Commit | Cómo revertir |
|---|---|---|---|---|---|
| R1-1 | DECISIÓN SIN CONFIRMAR. `ConfigUnidades.leer` cachea por (mtime_ns, tamaño); `guardar` invalida | `/status` releía el disco en cada sondeo (I4 SAF-02) | Caché con TTL | ver git log `fix(r1)` | quitar `_cache` en `unidades.py` |
| R1-2 | Los hallazgos de PySide (P3 SAF-03/04/05, C1 SAF-05) y los Bajos de O1 (SAF-06/07) se dejan abiertos | Riesgo de tocar flujos de guardado la víspera de la instalación | Corregirlos en la tanda 7 | — | — |

## PREGUNTAS PARA CRISTIAN (R1)
Detalle y recomendaciones en `R1_hallazgos_pendientes.md`.
- R1-P1: ¿auditar el ACK del ALL_OFF al salir del modo prueba (SAF-04 t4)? Recomendación: sí.
- R1-P2: `mantener_presion_camara` corre 2 veces por tick en PREPARADO (T1-01-C). Recomendación: una sola llamada, con prueba de banco.
- R1-P3: ¿separar `rango_calentamiento` en temperatura y presión? Recomendación: sí.
- R1-P4: ¿un Principal perdido después de un protocolo ya iniciado pasa a `solo_lenta`? Recomendación: sí.
- R1-P5: abort durante la tolerancia DI. Recomendación: aceptar la cancelación o, como mínimo, cambiar el texto.

## O2a (Parámetros del equipo)
| Id | Decisión | Motivo | Alternativa | Commit | Cómo revertir |
|---|---|---|---|---|---|
| O2a-1 | DECISIÓN SIN CONFIRMAR. Migración v8 (no v2: ya estaba usada); `system_params` guarda el vigente y `global_params.json` el de fábrica. | v2–v7 ya ocupadas | — | o2a | quitar `_migracion_v8` |
| O2a-2 | DECISIÓN SIN CONFIRMAR. Los lectores conservan el nombre viejo `presion_admosferica` vía alias en `ConfigManager.get`. | Decenas de pruebas y lectores; cero riesgo | Migrar todos los lectores (SAF-05) | o2a | `ALIAS` |
| O2a-3 | DECISIÓN SIN CONFIRMAR. Coherencia empaque/atm: `presion_empaque` ≥ atm+20 y ×0,6 > atm; `vacio_empaque` ≤ atm−10 y < presion_empaque (SAF-01). | Evita puerta "sellada" sin estarlo | Otros márgenes | o2a | `MARGEN_*` en `config_manager.py` |
| O2a-4 | DECISIÓN SIN CONFIRMAR. Sin base de datos rigen los de fábrica y no se puede cambiar nada (503). | Fail-safe | Guardar en archivo | o2a | — |
| O2a-5 | DECISIÓN SIN CONFIRMAR. La ventana de ajuste es una copia de la de Parámetros del ciclo, no un componente compartido. | No tocar la pantalla de ciclo en la víspera | Extraer `VentanaAjuste.qml` | o2a | — |
| O2a-6 | Se mantienen los respaldos `or 101.3/120/20` de los lectores (SAF-03). | Lógica de puertas: no definida en §1 | Fail-closed | — | — |

## PREGUNTAS PARA CRISTIAN (O2a)
- `timeout_chaqueta`: ¿conectarlo en PREPARACION/PREPARADO (`preparado.py` ~l.138) con alarma que bloquee inicio y se despeje al alcanzar la presión?
- SAF-02: ¿limitar `temp_max_apertura` por debajo de T_sat(P_atm) (~85–90 °C) o reservar >80 °C al ingeniero?
- SAF-04: ¿un cambio de parámetro en PREPARADO debe reiniciar la ventana de estabilidad?
- ¿El transductor de empaque y el rango 100–400 kPa son absolutos?
- Idioma: la segunda ventana QML no lee `GET /language`; ¿se sincroniza en el sondeo?

## O2b (Usuarios)
| Id | Decisión | Motivo | Alternativa | Cómo revertir |
|---|---|---|---|---|
| O2b-1 | DECISIÓN SIN CONFIRMAR. El técnico VE Usuarios (antes no la veía) con todo deshabilitado y el motivo. | Decisión 1.9 / APROBADO.md: "ve esos controles deshabilitados" | Ocultarle la sección | `_VE_USUARIOS` en `permisos_opciones.py` |
| O2b-2 | DECISIÓN SIN CONFIRMAR. Migración v9 = `operadores`. Si el otro agente (O2f–O2h) también usa v9, al unir hay que renumerar la suya a v10. | Siguiente libre | — | quitar `_migracion_v9` |
| O2b-3 | DECISIÓN SIN CONFIRMAR. Reglas sobre el objetivo = `ROLES_CREABLES` (el admin no desactiva ni restablece a un ingeniero). | Misma matriz que crear | Admin gestiona a todos | `_objetivo_gestionable` |
| O2b-4 | DECISIÓN SIN CONFIRMAR. Restablecer = el gestor escribe una contraseña temporal (no se genera); la propia no se restablece (409). | Sin canal para entregar una generada | Generar e imprimir | — |
| O2b-5 | DECISIÓN SIN CONFIRMAR. `GET /operadores` sin token (iniciar ciclo no exige sesión). | Coherente con O1 | Exigir sesión | — |

## PREGUNTAS PARA CRISTIAN (O2b)
- La tabla `operadores` ya existe, pero el inicio de ciclo sigue registrando como operador al usuario con sesión (O1). ¿Se agrega un selector de operador en Preciclo (y se valida en el backend que esté activo, H-06)?
- H-02: ¿revalidar en cada petición que el usuario siga activo (generación de credenciales en la sesión)?

## O2c (Fecha y hora)
| Id | Decisión | Motivo | Alternativa | Cómo revertir |
|---|---|---|---|---|
| O2c-1 | DECISIÓN SIN CONFIRMAR. La hora mostrada es la del PC donde corre la UI (el mismo del backend en el equipo); el backend aporta zona, instalación y aviso. | Hora fluida sin sondear cada segundo | Tomarla del backend | `fecha_hora_controller.py` |
| O2c-2 | DECISIÓN SIN CONFIRMAR. La fecha de instalación es `profile.created_at`, la misma que usa `clock_guard`. | Coherencia con M1-01 | Fecha propia de instalación | — |

## O2d (Información del sistema)
| Id | Decisión | Motivo | Alternativa | Cómo revertir |
|---|---|---|---|---|
| O2d-1 | DECISIÓN SIN CONFIRMAR. "Ciclos realizados" = mayor `numero_ciclo` de la base. | Mismo dato que el panel del Menú principal | Contador de M1 | `get_system_info` |
| O2d-2 | DECISIÓN SIN CONFIRMAR. Red = hay IPv4 no loopback (sin probar Internet). El detalle de adaptadores y Wi-Fi es de O2g. | Sin dependencias ni privilegios | Consultar O2g | `_hay_red` |
| O2d-3 | DECISIÓN SIN CONFIRMAR. `GET /system/info` sin token (no expone secretos; serie y modelo ya están en el ticket). | Todos los roles lo ven | Exigir sesión | — |

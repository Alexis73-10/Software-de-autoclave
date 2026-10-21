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

# Tanda 6: decisiones para revisar

## Resumen (lo más importante)
1. T2 aplicó P-1…P-9 y P-12 de T1: tolerancia de DI vencida de 4 s con FALLO_CONEXION (T2-1) y botón DESPEJAR de COM-02/03 sin sesión (T2-3).
2. Abierta: ¿los 4 s de tolerancia DI cuentan como exposición en ESTERILIZACION? Y el abort durante esa tolerancia responde 409 (R1-P5).
3. Abiertas de seguridad: Principal perdido tras un protocolo ya iniciado debería ir a `solo_lenta` (R1-P4); `mantener_presion_camara` corre 2 veces por tick en PREPARADO (R1-P2).
4. `vacio_empaque`/`presion_empaque` clasificados "absoluto" sin confirmar el transductor (C1-5, O2a); `rango_calentamiento` sin separar en temperatura/presión (R1-P3).
5. Parámetros del equipo en `system_params` (v8), alias `presion_admosferica` y márgenes empaque/atm nuevos (O2a-2/3); `timeout_chaqueta` sigue sin conectar.
6. `temp_max_apertura` editable por el técnico hasta 120 °C (O2a SAF-02): pregunta abierta.
7. Calibración atmosférica sin referencia fija por sitio: puede derivar por pasos de ≤5 kPa (O2f SAF-01).
8. Respaldo USB: no restaura programas ni perfil; el hash no autentica (O2h).
9. Wi-Fi/IP en solo lectura (O2g-1); scripts W1 sin ejecutar, con autologon en texto plano y botón de encendido "no hacer nada" (W1-5/6).
10. Inglés: nombres de fábrica y traducciones nuevas "sin revisar"; el motivo de bloqueo del estado seguro sigue en español (I4Q-2); D1 deja varios campos "por completar".

Formato: decisión · motivo · alternativa · commit · cómo revertir. Todas las "PREGUNTA PARA CRISTIAN" están en la sección final, agrupadas por etapa.


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

## R1 (hallazgos Medios/Bajos pendientes)
| Id | Decisión | Motivo | Alternativa | Commit | Cómo revertir |
|---|---|---|---|---|---|
| R1-1 | DECISIÓN SIN CONFIRMAR. `ConfigUnidades.leer` cachea por (mtime_ns, tamaño); `guardar` invalida | `/status` releía el disco en cada sondeo (I4 SAF-02) | Caché con TTL | ver git log `fix(r1)` | quitar `_cache` en `unidades.py` |
| R1-2 | Los hallazgos de PySide (P3 SAF-03/04/05, C1 SAF-05) y los Bajos de O1 (SAF-06/07) se dejan abiertos | Riesgo de tocar flujos de guardado la víspera de la instalación | Corregirlos en la tanda 7 | — | — |

## O2a (Parámetros del equipo)
| Id | Decisión | Motivo | Alternativa | Commit | Cómo revertir |
|---|---|---|---|---|---|
| O2a-1 | DECISIÓN SIN CONFIRMAR. Migración v8 (no v2: ya estaba usada); `system_params` guarda el vigente y `global_params.json` el de fábrica. | v2–v7 ya ocupadas | — | o2a | quitar `_migracion_v8` |
| O2a-2 | DECISIÓN SIN CONFIRMAR. Los lectores conservan el nombre viejo `presion_admosferica` vía alias en `ConfigManager.get`. | Decenas de pruebas y lectores; cero riesgo | Migrar todos los lectores (SAF-05) | o2a | `ALIAS` |
| O2a-3 | DECISIÓN SIN CONFIRMAR. Coherencia empaque/atm: `presion_empaque` ≥ atm+20 y ×0,6 > atm; `vacio_empaque` ≤ atm−10 y < presion_empaque (SAF-01). | Evita puerta "sellada" sin estarlo | Otros márgenes | o2a | `MARGEN_*` en `config_manager.py` |
| O2a-4 | DECISIÓN SIN CONFIRMAR. Sin base de datos rigen los de fábrica y no se puede cambiar nada (503). | Fail-safe | Guardar en archivo | o2a | — |
| O2a-5 | DECISIÓN SIN CONFIRMAR. La ventana de ajuste es una copia de la de Parámetros del ciclo, no un componente compartido. | No tocar la pantalla de ciclo en la víspera | Extraer `VentanaAjuste.qml` | o2a | — |
| O2a-6 | Se mantienen los respaldos `or 101.3/120/20` de los lectores (SAF-03). | Lógica de puertas: no definida en §1 | Fail-closed | — | — |

## O2b (Usuarios)
| Id | Decisión | Motivo | Alternativa | Cómo revertir |
|---|---|---|---|---|
| O2b-1 | DECISIÓN SIN CONFIRMAR. El técnico VE Usuarios (antes no la veía) con todo deshabilitado y el motivo. | Decisión 1.9 / APROBADO.md: "ve esos controles deshabilitados" | Ocultarle la sección | `_VE_USUARIOS` en `permisos_opciones.py` |
| O2b-2 | DECISIÓN SIN CONFIRMAR. Migración v9 = `operadores`. Si el otro agente (O2f–O2h) también usa v9, al unir hay que renumerar la suya a v10. | Siguiente libre | — | quitar `_migracion_v9` |
| O2b-3 | DECISIÓN SIN CONFIRMAR. Reglas sobre el objetivo = `ROLES_CREABLES` (el admin no desactiva ni restablece a un ingeniero). | Misma matriz que crear | Admin gestiona a todos | `_objetivo_gestionable` |
| O2b-4 | DECISIÓN SIN CONFIRMAR. Restablecer = el gestor escribe una contraseña temporal (no se genera); la propia no se restablece (409). | Sin canal para entregar una generada | Generar e imprimir | — |
| O2b-5 | DECISIÓN SIN CONFIRMAR. `GET /operadores` sin token (iniciar ciclo no exige sesión). | Coherente con O1 | Exigir sesión | — |

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

## O2e (Bitácora)
| Id | Decisión | Motivo | Alternativa | Cómo revertir |
|---|---|---|---|---|
| O2e-1 | DECISIÓN SIN CONFIRMAR. El backend convierte anterior/nuevo a la unidad vigente (global); la frase la arma la UI en su idioma. | Una sola conversión, misma que U1 | Convertir en la UI | `core/runtime/bitacora.py` |
| O2e-2 | DECISIÓN SIN CONFIRMAR. Suspensión: cada pantalla avisa al entrar/salir (`POST /ui/standby`, usuario "sistema"); con dos pantallas quedan dos filas. | La suspensión vive en la UI | Agregar en el backend | `registrar_suspension` en `app.py` |
| O2e-3 | DECISIÓN SIN CONFIRMAR. Filtros Usuario y Tipo rotan con cada toque (sin lista desplegable). | Simple y táctil | Selector modal | `OpcionesBitacora.qml` |

## O2f (Calibración atmosférica)
| Id | Decisión | Motivo | Alternativa | Cómo revertir |
|---|---|---|---|---|
| O2f-1 | DECISIÓN SIN CONFIRMAR. TMG-04 abierto: hilo daemon; si el proceso se cierra entre `fijar()` y `aplicar_valor()` queda el valor nuevo sin auditoría. | Ventana mínima | Hilo no daemon con cierre ordenado | `calibracion_atm.py` |
| O2f-2 | DECISIÓN SIN CONFIRMAR. TMG-05 abierto: GET síncrono en el hilo GUI (igual que TMG-02 de O2a). | Consistencia con O2a | GET asíncrono | `calibracion_atm_controller.py` |

## O2g (Conectividad)
| Id | Decisión | Motivo | Alternativa | Cómo revertir |
|---|---|---|---|---|
| O2g-1 | DECISIÓN SIN CONFIRMAR. Wi-Fi/IP en solo lectura (405). Habilitarlo exige servicio elevado, comunicación autenticada, lista blanca, reversión automática y bitácora. | Riesgo de perder soporte remoto (AnyDesk) | Servicio de Windows elevado | — |
| O2g-2 | DECISIÓN SIN CONFIRMAR. Cambios de correo rechazados con ciclo en curso (R-01), también para el ingeniero. | Coherencia con R-01 | Permitir al ingeniero | `PUT /email/config` |
| O2g-3 | DECISIÓN SIN CONFIRMAR. Con el interruptor de envío apagado, el Historial no envía. | — | — | `config_correo.py` |

## O2h (Respaldo)
| Id | Decisión | Motivo | Alternativa | Cómo revertir |
|---|---|---|---|---|
| O2h-1 | DECISIÓN SIN CONFIRMAR. Los programas no se restauran (SAF-02). | Evitar programas sin validar | Reutilizar el validador de `PATCH /cycle/parameter` | `respaldo.py` |
| O2h-2 | DECISIÓN SIN CONFIRMAR. No se deshacen los parámetros ya aplicados si uno posterior recibe 409 (SAF-03 parcial). | Queda auditado en `finally` | Restauración transaccional | `respaldo.py` |
| O2h-3 | DECISIÓN SIN CONFIRMAR. El respaldo no restaura el perfil (USB de recuperación no conectada al arranque). | Se exige la serie del perfil instalado | Modo "sin perfil" en el asistente | — |

## Unión O2f–O2h en tanda-6
- Los eventos nuevos `respaldo_exportado/rechazado/restaurado`, `correo_configurado`, `correo_prueba`, `impresora_prueba` e `impresion_ganancias` se agregaron a `bitacora.EVENTOS` con frase es/en en la unión (lo exigía `test_textos_de_todos_los_eventos`). Revisar redacción.

## I4 (parte QML)
| Id | Decisión | Motivo | Alternativa | Cómo revertir |
|---|---|---|---|---|
| I4Q-1 | DECISIÓN SIN CONFIRMAR. En el Historial, un nombre guardado que coincide con el de un ciclo de fábrica en español se muestra traducido (también si es un programa de usuario con ese nombre). | La BD guarda solo el texto | Guardar la clave del nombre con el ciclo | `nombres_ciclo.py` |
| I4Q-2 | DECISIÓN SIN CONFIRMAR. `estadoSeguroBloqueadoMotivo` sigue en español (SAF-01): el QML busca "Principal" en él. | Traducirlo rompería el botón de sondas | Código `bloqueado_motivo_codigo` en el backend | — |
| I4Q-3 | DECISIÓN SIN CONFIRMAR. `resultado_detalle` del Historial se muestra como código. | Es un código, neutro | Título del catálogo de alarmas | — |
| I4Q-4 | DECISIÓN SIN CONFIRMAR. El `detail` del rechazo de cambio de programa sigue en español. | El backend no trae código | `RechazoApi` en `/cycle/select` | — |

## X1 (solapamiento en Entradas/Salidas)
| Id | Decisión | Motivo | Alternativa | Commit | Cómo revertir |
|---|---|---|---|---|---|
| X1-1 | DECISIÓN SIN CONFIRMAR. La causa probada (varias OPCIONES apiladas en la misma ventana y E/S sin fondo opaco) se da por la que vio Cristian; el caso con dos pantallas no se reprodujo | Reproducida offscreen (`[4,1,1,0]`) | Seguir investigando con dos pantallas | 15ffbbd (merge 8181b66) | `git revert 15ffbbd` (`irAOpciones` en `Main.qml`, páginas por segmento) |

## I4 (backend y salidas)
| Id | Decisión | Motivo | Alternativa | Commit | Cómo revertir |
|---|---|---|---|---|---|
| I4-1 | DECISIÓN SIN CONFIRMAR. En el ticket de arranque un estado desconocido cuenta como FALLO (antes, listo) | Lo más seguro; solo texto | Contarlo como listo | af24210 | ticket de arranque |
| I4-2 | DECISIÓN SIN CONFIRMAR. Nombres de fábrica en `ciclos_fabrica.<cycle_id>.nombre`, no en `ciclo.<id>.nombre` (plan §3.2). Inglés propuesto sin revisar: "Bowie & Dick", "Instruments 121°C/134°C", "Liquids" | No mezclar con los textos planos de `ciclo` | Lo del plan | ed4c650 | claves en `i18n/*.json` y `nombre_clave` |
| I4-3 | DECISIÓN SIN CONFIRMAR. En psi la gráfica del PDF usa psig en un eje continuo; sin P_atm válida no se dibujan presión ni consigna | Evitar cambio de unidad a mitad de curva | psig/inHg como el ticket | af24210 | `ui_qml/exportacion/unidades_pdf.py` |
| I4-4 | DECISIÓN SIN CONFIRMAR. Descripciones de alarma del motivo de fallo (PDF) en °C/kPa de la plantilla | Convertir exige la clase en 49 plantillas | Marcar la clase de cada parámetro | af24210 | — |
| I4-5 | DECISIÓN SIN CONFIRMAR. El ticket térmico sigue con "código - título" del motivo (spec §5.4) | Spec | Imprimir parámetros | af24210 | — |
| I4-6 | DECISIÓN SIN CONFIRMAR. Causas de fallo del ticket de resumen con el código guardado, sin traducir | Cambio mínimo | Traducir por catálogo | af24210 | — |
| I4-7 | Migración v7: `ciclos.valores_fallo` (JSON); `motivo_fallo` y `codigo_fallo` no cambian | §3.10 | — | 5ff5139 | quitar la migración v7 |
| I4-8 | NO se unificaron las familias de códigos (D-22, `EMERGENCIA` ↔ `PARO_EMERGENCIA`) | Toca la lógica de alarmas | Hacerlo con banco | — | — |

## W1 (estación Windows; scripts sin ejecutar)
| Id | Decisión | Motivo | Alternativa | Commit | Cómo revertir |
|---|---|---|---|---|---|
| W1-1 | DECISIÓN SIN CONFIRMAR. Tarea programada en vez de Shell Launcher para lanzar `Autoclave.exe` | Funciona en cualquier edición (la del PC no está confirmada, plan §10.1) | Shell Launcher | 74af54f | `03_revertir_tarea_autoclave.ps1` |
| W1-2 | DECISIÓN SIN CONFIRMAR. AnyDesk sin script (queda en la checklist del LEEME) | Plan: sin acceso desatendido por defecto | Script de configuración | 74af54f | — |
| W1-3 | DECISIÓN SIN CONFIRMAR. Sin bloqueos de la cuenta del operador (administrador de tareas, cmd, Explorador) | Depende de cómo entra el técnico (plan §4); podría dejarlo fuera | Aplicarlos | 74af54f | — |
| W1-4 | DECISIÓN SIN CONFIRMAR. Windows Update: horas activas 6–23, `AUOptions=2`, diferir 30/365 días (en Home pueden ignorarse) | Evitar reinicios en uso | Otra política | 74af54f | `04_revertir_notificaciones_actualizaciones_gestos.ps1` |
| W1-5 | DECISIÓN SIN CONFIRMAR. Botón de encendido "no hacer nada"; tapa y suspensión desactivadas; inicio rápido desactivado | El software no hace cierre ordenado desde ese evento (plan §7) | Apagado | 74af54f | `05_revertir_plan_energia.ps1` |
| W1-6 | DECISIÓN SIN CONFIRMAR. Contraseña de autologon en texto plano en Winlogon (`DefaultPassword`) | Riesgo aceptado en el plan §3.1; sin software externo | LSA secret (Sysinternals Autologon) | 74af54f | `01_revertir_cuenta_autologon.ps1` |
| W1-7 | DECISIÓN SIN CONFIRMAR. Usuario por defecto `operador`; ruta `%ProgramFiles%\Especifika\Autoclave\Autoclave.exe` | — | Parámetros | 74af54f | parámetros de los scripts |

## D1 (documentación 62304 mínima)
| Id | Decisión | Motivo | Alternativa | Commit | Cómo revertir |
|---|---|---|---|---|---|
| D1-1 | Quedan "por completar": probabilidad y severidad de cada riesgo, ids de banco en la matriz, anomalías de los SOUP, uso real de scipy y tk/customtkinter, requisitos de las specs de 2026-05, V-01 (HAZ-FC-06), revisión nativa de las traducciones de seguridad, versiones del firmware | No inventar (instrucción D1) | — | 910e4e3 | — |
| D1-2 | La lista SOUP toma las versiones del entorno: `requirements.lock.txt` está incompleto (faltan PySide6, FastAPI…) | Versión exacta | Regenerar el lock antes | 910e4e3 | — |

## B1 (barra flotante en Preciclo y Ciclo en curso)
| Id | Decisión | Motivo | Alternativa | Commit | Cómo revertir |
|---|---|---|---|---|---|
| B1-1 | DECISIÓN SIN CONFIRMAR. Margen tarjeta-barra de 10 px (no 30 como en Opciones) | Con 30 px los botones y la barra de progreso quedarían fuera de la tarjeta sin refactorizar | Reubicar esos controles | d8a27b4 (merge 700e3e9) | `git revert d8a27b4` |
| B1-2 | DECISIÓN SIN CONFIRMAR. "Menú a la izquierda" del mockup = celda de equipo (abre el panel con Apagar); el engranaje sigue en la cabecera | Función de hoy en esa posición | Mover el engranaje | d8a27b4 | ídem |
| B1-3 | DECISIÓN SIN CONFIRMAR. Versión al centro solo en Preciclo; en Ciclo en curso el centro es el avatar | Mockup 1 y función actual | Versión al centro en ambas | d8a27b4 | ídem |
| B1-4 | DECISIÓN SIN CONFIRMAR. Avatar centrado en su celda (antes desplazado unos px) | Geometría del componente | — | d8a27b4 | ídem |

## O3 (entradas mostradas)
| Id | Decisión | Motivo | Alternativa | Commit | Cómo revertir |
|---|---|---|---|---|---|
| O3-1 | DECISIÓN SIN CONFIRMAR. La gráfica solo traza lo registrado (`temp_camara`, `temp_ref`, `pres_camara`); otras entradas salen "(sin registro)" | Ampliar el registro toca `db_manager.py` | Ampliar `lecturas_grafica` | 33fd8de (merge 739e849) | `git revert 33fd8de` |
| O3-2 | DECISIÓN SIN CONFIRMAR. En psi la gráfica usa psia | psig/inHg cambian de unidad y signo en el prevacío | psig/inHg | 33fd8de | ídem |
| O3-3 | DECISIÓN SIN CONFIRMAR. "No en uso" solo en sondas de temperatura con rol por programa | Presiones y drenaje no tienen rol | — | 33fd8de | ídem |
| O3-4 | DECISIÓN SIN CONFIRMAR. Formato del módulo de unidades (`121.0`, sin el `085.0` del mockup) | Coherencia con U1 | Ceros a la izquierda | 33fd8de | ídem |
| O3-5 | DECISIÓN SIN CONFIRMAR. `temp_drenaje_camara` siempre "—" (no está en `EstadoAutoclave` ni en `/status`) | Sin fuente | Publicarla | 33fd8de | ídem |

## H1 (hoja de banco)
| Id | Decisión | Motivo | Alternativa | Commit | Cómo revertir |
|---|---|---|---|---|---|
| H1-1 | DECISIÓN SIN CONFIRMAR. Tolerancia de ±0,5 kPa contra el barómetro en D-30 (propuesta de H1); los criterios 60–105 kPa, dispersión ≤1,5 kPa y 5 kPa vienen de O2f | Sin dato del cliente | Otra tolerancia | 980a9f5 | `pruebas.py` + `generar.py` |
| H1-2 | 26 pruebas nuevas (49 → 75), ids existentes sin renumerar; D-21 anota el SAF-05 de C1a y D-35 la limitación I4-4 | Instrucción H1 | — | 980a9f5 | ídem |

# PREGUNTAS PARA CRISTIAN

### T2
- ¿Los segundos de tolerancia por DI vencida cuentan como exposición en ESTERILIZACION?
- ¿DESPEJAR debe exigir el enlace "ok" o una sesión?
- ¿La marca "no estéril" también para FALLO/CANCELADO/EMERGENCIA?

### C1
- ¿Los programas duplicados antes de C1c (sin "clase") se reescriben con la clase, o basta con la migración con advertencia?
- ¿El transductor de empaque mide en absoluto?

### R1
Detalle y recomendaciones en `R1_hallazgos_pendientes.md`.
- R1-P1: ¿auditar el ACK del ALL_OFF al salir del modo prueba (SAF-04 t4)? Recomendación: sí.
- R1-P2: `mantener_presion_camara` corre 2 veces por tick en PREPARADO (T1-01-C). Recomendación: una sola llamada, con prueba de banco.
- R1-P3: ¿separar `rango_calentamiento` en temperatura y presión? Recomendación: sí.
- R1-P4: ¿un Principal perdido después de un protocolo ya iniciado pasa a `solo_lenta`? Recomendación: sí.
- R1-P5: abort durante la tolerancia DI. Recomendación: aceptar la cancelación o, como mínimo, cambiar el texto.

### O2a
- `timeout_chaqueta`: ¿conectarlo en PREPARACION/PREPARADO (`preparado.py` ~l.138) con alarma que bloquee inicio y se despeje al alcanzar la presión?
- SAF-02: ¿limitar `temp_max_apertura` por debajo de T_sat(P_atm) (~85–90 °C) o reservar >80 °C al ingeniero?
- SAF-04: ¿un cambio de parámetro en PREPARADO debe reiniciar la ventana de estabilidad?
- ¿El transductor de empaque y el rango 100–400 kPa son absolutos?
- Idioma: la segunda ventana QML no lee `GET /language`; ¿se sincroniza en el sondeo?

### O2b
- La tabla `operadores` ya existe, pero el inicio de ciclo sigue registrando como operador al usuario con sesión (O1). ¿Se agrega un selector de operador en Preciclo (y se valida en el backend que esté activo, H-06)?
- H-02: ¿revalidar en cada petición que el usuario siga activo (generación de credenciales en la sesión)?

### O2e
- ¿Unificar en el visor las tablas viejas `cycle_params_audit` y `sensor_calibration_audit` (§3.9) o basta `audit_log`?
- ¿Mostrar la entidad con su nombre traducido (p. ej. "Temperatura segura de apertura") en vez de la clave?

### O2f
- (SAF-01) ¿Referencia fija por sitio (presión esperada o altitud) en el perfil, rechazando o exigiendo ingeniero si la calibración se aleja más de ±5 kPa? Hoy calibraciones sucesivas de ≤5 kPa pueden mover la referencia por todo 60–105 kPa.
- (SAF-02) ¿`ABIERTO` viene de sensor de posición en todos los tipos de puerta, incluida `SimpleDoor`? ¿Se exige además presión inicial cerca de la referencia vigente?
- Si arranca un ciclo durante `por_confirmar`, hoy la medición solo se rechaza al confirmar. ¿Descartarla en ese momento?

### O2g
- ¿Remitente y servidor SMTP editables desde aquí (ingeniero)? Hoy siguen en `config/correo.json` y la contraseña en el almacén de credenciales de Windows.

### O2h
- ¿Firmar el respaldo (HMAC con clave del equipo)? Hoy el hash detecta daños pero no autentica.
- ¿Habilitar la restauración de programas reutilizando el validador de `PATCH /cycle/parameter`?
- ¿Recrear los usuarios del respaldo con contraseña temporal y cambio obligatorio?
- ¿Restaurar también la presión atmosférica de referencia del mismo equipo?

### I4 QML
- ¿Exponer un código para el motivo de bloqueo del estado seguro (S4), para poder traducirlo sin romper la decisión del botón de sondas?
- Truncado: la revisión automática cubre el estado vacío de cada pantalla (sin backend); los diálogos y ventanas con datos quedan para el recorrido en inglés de H1. ¿Basta?

### X1
- Confirmar en el equipo, con las dos pantallas, que el solapamiento de Entradas/Salidas no reaparece.

### I4 (backend)
- ¿Se aprueba el inglés propuesto para los nombres de fábrica (I4-2)?
- ¿Se marca la clase de los parámetros en las 49 plantillas de alarma para convertir sus unidades (I4-4)?
- ¿Se unifican las familias de códigos D-22 (`EMERGENCIA` ↔ `PARO_EMERGENCIA`) en una tanda con banco?

### W1
- ¿Qué edición de Windows tiene el PC industrial (Shell Launcher o tarea programada)?
- ¿Cómo entra el técnico? (decide los bloqueos de la cuenta del operador, plan §4)
- ¿Se acepta la contraseña de autologon en texto plano o se usa Sysinternals Autologon?

### O3
- ¿Se amplía el registro de lecturas para guardar las entradas elegidas de cada ciclo (`planeacion_opciones.md` §3.1)?

### H1
- ¿Se confirma la tolerancia de ±0,5 kPa contra el barómetro (D-30)?

### T2 (adicional, de `T2_respuestas_T1.md`)
- P-10: verificar en banco (C-05) qué botón ofrece la UI al arrancar con la cámara no segura.

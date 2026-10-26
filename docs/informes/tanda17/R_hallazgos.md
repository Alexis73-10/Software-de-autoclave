# Tanda 17 — hallazgos de R

## R1 · Setup y ruta de datos
| Hallazgo | Sev. | Archivo | Motivo |
|---|---|---|---|
| V17-s1-01 | Alta | `tools/instalador/autoclave.iss` `ProtegerCarpeta` (también `ProtegerRespaldos`, `_comun.ps1 Protect-DirEstacion`) | `/inheritance:r /grant:r` no quita entradas explícitas de otros SID: un usuario que creó antes `D:\Especifika` (dueño) deja `Todos:F` y conserva escritura en `programa`. Falta `/reset` previo y verificación de la ACL final |
| V17-s1-02 | Media | `autoclave.iss` `CarpetaVacia(Programa)` antes de proteger | ventana para plantar una DLL entre la comprobación y el `icacls` |
| V17-s1-03 | Alta | `src/autoclave/instalador_exe.py` `ofrecer_instalacion`/`instalar` | con el Setup nuevo instalado, un `Autoclave.exe` desde USB sigue ofreciendo instalarse en Archivos de programa con datos en `%ProgramData%` (calibración vieja de la I) y pisa el acceso directo |
| V17-s1-04 | Media | `autoclave.iss` `CargarUnidades`/`PreseleccionarUnidad` | `DRIVE_FIXED` incluye discos USB externos; podría preseleccionarse (silenciosa: sin preguntar) |
| V17-s1-05 | Media | `_comun.ps1` y `RevertirEstacion`/`ReversionFallo` | si la reversión falla al desinstalar, se borra `RutaDatos` y los inversos manuales caen a `%ProgramData%` sin respaldo y salen en 0 (autologon queda puesto) |
| V17-s1-06 | Baja | `PrepararCarpetas` / `Protect-DirEstacion` | `datos\estacion` creable antes por un usuario estándar con respaldos falsos |
| V17-s1-07 | Baja | `tests/test_t17_s1_setup.py`, `test_t9_e9_setup_estacion.py` | pruebas estáticas o de réplica; no detectan V17-s1-01 |

## R2 · Estación y arranque (sin hallazgos altos)
| Hallazgo | Sev. | Archivo | Motivo |
|---|---|---|---|
| V17-s2-01 | Media | `src/autoclave/exe_unico.py` `_lanzador` | una segunda instancia del lanzador abre la cubierta encima de pantallas vivas (ciclo en curso) y come los toques hasta 15–180 s |
| V17-s2-02 | Baja | `estacion/cubierta_arranque.py:115`, `_ventanas.py:115-116` | tras la primera señal, `MsgWaitForMultipleObjects` con eventos ya señalados gira sin pausa (CPU) |
| V17-s2-03 | Baja | `tools/estacion/03_tarea_autoclave.ps1:58-61` | la idempotencia deja `PT10S` en tareas ya existentes |
| V17-s2-04 | Baja | `exe_unico.py:450` | `_log_a_archivo` fuera del try del rol `asociar-tactiles` (diálogo modal sin consola) |
| V17-s2-05 | Baja | `estacion/digimon.py:83-91` | `prefijo_observado` copia el prefijo de cualquier valor existente |
| V17-s2-06 | Baja | `06_asociar_tactiles.ps1:177` | pide reiniciar aunque la herramienta no haya escrito nada |

## R3 · Backend de seguridad (sin hallazgos altos)
| Hallazgo | Sev. | Archivo | Motivo |
|---|---|---|---|
| V17-s3-01 | Media | `backend/context.py` `instalacion_en_curso`, `db_manager._motivo_no_registrar` | relee y valida el perfil en cada escritura (también en el hilo del lazo y con el lock); si el perfil se corrompe con el equipo en marcha se pierden en silencio los eventos de seguridad |
| V17-s3-02 | Baja | `estado_seguro.py:203-214`, `protocolo_fallo.py:977-981` | con presión perdida se anula todo motivo: quedan sin CIC-10 otros motivos simultáneos; la AI vencida también cuenta como presión perdida |
| V17-s3-03 | Baja | `bitacora.py:61` | `salida_prueba_cortada` (evidencia de que actuaron las protecciones 1–3) retirado; solo log y aviso volátil |
| V17-s3-04 | Baja | `salidas_prueba_seguridad.py:91-93` | con presión vigente también se liberan los bloqueos de la recuperación de arranque pendiente |
| V17-s3-05 | Baja | `test_s9_planta_simulada.py:373-379`; `test_t17_f2_bitacora.py:140,257` | aserción que pasa por presión no vigente; pruebas de texto sin comportamiento |
| V17-s3-06 | Baja | `control_loop.py:373-376` | `aplicar_roles_sensores` compara contra sondas No en uso (solo puede negar la liberación: lado seguro) |

## R4 · Interfaz (sin hallazgos altos)
| Hallazgo | Sev. | Archivo | Motivo |
|---|---|---|---|
| V17-s4-01 | Media | `PanelNotificaciones.qml:179-209`, `PantallaPreciclo.qml:887-895` | el rechazo de DESPEJAR (COM-02/03) queda tapado por la ventana de detalle o no se ve desde Preciclo; sin indicación de ocupado |
| V17-s4-02 | Media | `VentanaDetalleAlarma.qml`, `Desplegable.qml`, `Calendario.qml`, `Main.qml:203-218` | las capas emergentes (z 1000) no se cierran ante paro o estado seguro y tapan «Confirmar y llevar a estado seguro» |
| V17-s4-03 | Media | `ui_bridge.py:86-99`, `VentanaDetalleAlarma.qml:87-94` | DESPEJAR sigue disponible con la alarma ya reconocida en CICLO (ligado a 01) |
| V17-s4-04 | Baja | `OpcionesBitacora.qml:82-88` | «Sin fecha» en Hasta significa hoy; `hoy` no se refresca tras medianoche |
| V17-s4-05 | Baja | `IntroArranque.qml:285` | la intro muestra «Software v…» (D-07, previo) con texto fijo sin i18n |
| V17-s4-06 | Baja | `test_t17_s4_alarmas_qml.py`, `test_t17_s4_opciones_qml.py` | pruebas de texto o sin comprobar visibilidad; presión solo en kPa |
| V17-s4-07 | Baja | `OpcionesBitacora.qml:186` | clave dinámica `bitacora.tipo.<evento>` sin `I18n.existe` |

### Resolución R2 (rama `tanda-17-r2`: f72409f, 6ad8360)
- V17-s2-01 corregido: `estacion/instancia_unica.py`, mutex `Local\EspecifikaAutoclaveLanzador` antes de la cubierta; un segundo lanzador no abre nada y sale con 0 (DECISIÓN SIN CONFIRMAR); R11 (`--esperar-pid`) reintenta hasta 60 s; si el mutex falla, sigue sin protección (log). Solo build congelado (`AUTOCLAVE_INSTANCIA_UNICA`).
- V17-s2-02 corregido: solo se esperan los eventos pendientes.
- V17-s2-03 corregido: el 03 reemplaza una tarea con retraso distinto de `PT0S`/vacío.
- V17-s2-04 corregido: `_log_a_archivo` del rol `asociar-tactiles` en try/except.
- V17-s2-05 corregido: `elegir_prefijo` usa siempre `20-` salvo forma completa del mismo táctil tocado (DECISIÓN SIN CONFIRMAR).
- V17-s2-06 corregido: el 06 pide reiniciar solo si la herramienta escribió.

### Resolución R4 (rama `tanda-17-r4`: 661c85e, 94781b1)
- V17-s4-01/03 corregidos: `VentanaDetalleAlarma.mensaje` (texto `mensajeDespejarDetalle`) conectado en la campana y en Preciclo; `descartarMensajeDespejar()` al cerrar; DESPEJAR oculto con la alarma reconocida.
- V17-s4-02 corregido: singleton `Tema/Capas.qml` (`cierreSolicitado`, `cerrarTodas()`); Desplegable, Calendario y VentanaDetalleAlarma se cierran con él y al ocultarse; `Main.qml irAPanelSeguridad()` lo llama (también desde el login). DECISIÓN SIN CONFIRMAR: cierra las capas de las dos pantallas.
- V17-s4-04 corregido: «Sin fecha» solo en Desde; `cargar()` refresca `hoy`.
- V17-s4-05: la intro sigue mostrando la versión (D-07, DECISIÓN SIN CONFIRMAR) con la clave `arranque.version_software`.
- V17-s4-06 corregido: clics reales y `isVisible()`; presión en kPa, psi (p_atm 74,6), sin lectura y `/status` 500.
- V17-s4-07 corregido: `I18n.existe` antes de la clave dinámica.

### Resolución R1 (rama `tanda-17-r1`: f027afb, 9d0e897)
- V17-s1-01 corregido (ALTA): `AplicarAcl` — dueño Administradores, `/inheritance:r /grant:r`, DACL protegida `D:P(...)` reemplazada entera con `SetAccessControl` y verificada con `Get-Acl` por SID y máscara (FA 2032127, RX 1179817, M 1245631); cualquier fallo detiene el Setup. Cubre `Especifika`, `Autoclave`, `programa`, `datos`, `datos\estacion`, `Autoclave_respaldos`; `Protect-DirEstacion` igual. Comprobado en una carpeta temporal: un `Todos:F` explícito desaparece.
- V17-s1-02 corregido: `CarpetaVacia(programa)` después de proteger.
- V17-s1-03 corregido (ALTA): `instalador_exe.instalacion_con_setup()`; con instalación del Setup en el registro y el exe fuera de `RutaPrograma`, solo avisa y termina; `--rol instalar` devuelve 1 sin copiar.
- V17-s1-04 corregido: `ConsultarBuses` (`Get-Partition`+`Get-Disk`, solo lectura) excluye buses USB, SD y MMC; si falla, solo se preselecciona la del sistema.
- V17-s1-05 corregido: con una reversión fallida se reescriben `RutaDatos`/`RutaPrograma` y se conserva `Estacion`; `ReversionFallo` cita `datos\estacion`; `_comun.ps1` acepta `AUTOCLAVE_RUTA_DATOS`.
- V17-s1-06 corregido: `PrepararEstacion` crea `datos\estacion` protegido; una preexistente en instalación nueva se aparta a `estacion_anterior_<fecha>`.
- V17-s1-07 corregido: pruebas renombradas por tipo (`texto`, `replica`, `ejecuta`, `parser`); pruebas manuales nuevas en `tools/instalador/LEEME.md`.
- DECISIONES SIN CONFIRMAR: (1) si falla la consulta de bus, solo se preselecciona la del sistema; (2) también se excluyen SD y MMC; (3) `estacion` preexistente se aparta; (4) con reversión fallida se conservan `RutaPrograma` y `Estacion`; (5) `AUTOCLAVE_RUTA_DATOS` prevalece; (6) el exe desde USB solo avisa. Pendiente en el PC de prueba: `AplicarAcl` como administrador con código 0.

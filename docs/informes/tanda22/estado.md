# Tanda 22 — estado

Rama `tanda-22` (desde `dev` 14f62f34). Spec: `docs/mis_plans/prompt_claude_code_tanda22.md`.

| Paso | Estado | Notas / último commit |
|---|---|---|
| A0 | Hecho | rama, evidencia en `evidencia/`, lista de afectados verificada |
| P1 teclado | Hecho | e8bf32fc (`abrirAlfanumericoAccion`, `_enVivo`, `_entregarAccion` anula y cierra antes de llamar; 16 pruebas) |
| P2 cliente | Hecho | 182a6480 (TEC-ACC-05: 403 reautenticacion_* reconocidos con reasignacion.err_clave[_requerida], sin cerrar sesión; 429 usuario_bloqueado en `enviar` cierra la sesión local con aviso y segundos; DSC: el 429 cierra en cualquier ruta de `enviar`; `enviar_al_cerrar` sin cambio), unido a tanda-22 |
| Unión P1+P2 | Hecho | ef295843 (P2), fbbdf6ee (P1) |
| TEC-ACC-04 pantallas | Hecho | c5b8cf3a (7 puntos; `test_t22_pantallas_accion_qml.py` 8 pruebas, 7 fallan con el código anterior) |
| TEC-ACC-07 prueba de regla | Hecho | c5b8cf3a (`test_t22_regla_teclado_accion.py`, sin lista blanca; línea en CLAUDE.md, TEC-ACC-06) |
| R revisión | Hecho | ed938ad1 (sin hallazgos altos/medios; correcciones bajas: solo espacios = vacío (DSC), regla más estricta, pruebas de pantalla ampliadas) |
| Suite | Hecha | 9151 passed, 11 skipped, 7 xfailed; `test_home_view` (caída conocida de trabajador xdist, pasa en serie) y 2 errores de `test_o3` por carrera del .qml temporal, corregida en el commit siguiente (9 passed con -n 4). `suite_raw.txt` |
| K entrega | Hecha | merge 45966035 en dev; 1.0.0-alpha.11 (25e48bb8, etiqueta v1.0.0-alpha.11), `entrega/v1.0.0-alpha.11_2026-10-29`; Setup SHA-256 8fdfa87c6b124d83b9d96cb254977adbc4a38beb32119d5b1956cf9cc5db0754; no hizo falta tocar `.git/info/exclude` |
| U USB | Hecha | E: (disco 1, USB 14,65 GB) formateada exFAT `AUTOCLAVE`; Setup alpha.11 copiado, SHA-256 8fdfa87c… verificado |
| Z | Hecha | `R22_informe.md`, `CERRADO.txt` |

## A0 — verificación con grep (26 llamadas a `abrirAlfanumerico(`/`abrirNumerico(` en `ui_qml/qml`)

Puntos que ejecutan una acción (pasan a modo acción), 7, la lista del prompt está completa:
1. `OpcionesReasignacion._pedirClave` (l. 612; usada por Aplicar → `control.aplicar`, Restaurar fábrica → `control.restaurarFabrica`, Verificar → `control.verificar`).
2. `OpcionesReasignacion` nombre reforzado (l. 548: `control.fijarNombre` + `Qt.callLater(_pasoReforzada(i+1))`).
3. `OpcionesReasignacion` nombre reforzado de Verificar (l. 605: `Qt.callLater(conClave(texto))`).
4. `OpcionesConectividad.agregarDestinatario` nombre (l. 38: abre el teclado del correo).
5. `OpcionesConectividad.agregarDestinatario` correo (l. 42: `control.agregar`).
6. `OpcionesManejoCiclos.elegirBase` (l. 53: `control.crear`).
7. `OpcionesManejoCiclos.pedirDuplicar` (l. 61: `control.duplicar`).

Solo asignan (sin cambios): Login, CambioClave, NuevoUsuario, Instalacion (texto y capacidad), OpcionesUsuarios (clave temporal, confirmación, nombre de operador), SelectorDestino, OpcionesCalibracionSensor (`editar` → asigna `realBajo`/`lecturaBaja`...), OpcionesMantenimiento (`campo.elegido` → `onElegido` asigna `diasNuevo`/`ciclosNuevo`), OpcionesParametrosCiclo/Equipo (`ajuste.recibir`: convierte, valida y asigna en memoria; no envía). No apareció ningún punto nuevo.

## Suite (primer intento, antes de R)

- 1.er intento: se colgó al 43 % tras caer un trabajador xdist (`node down`), detenido por el límite de tiempo.
- 2.º intento: 9149 passed, 11 skipped, 7 xfailed; fallos: `test_home_view::...impresion_menu` (caída conocida de trabajador xdist, R20/ajustes_28oct) y `test_o3_entradas_mostradas_qml` (2: carrera previa, dos procesos usan el mismo `_prueba_o3_entradas.qml` temporal; ajena a esta tanda). En serie: 10 passed.

## U — datos de E: antes de formatear (29-oct)

- Disco 1, `Generic Flash Disk`, serie `1`, 14,65 GB, BusType USB, IsBoot False, IsSystem False.
- Disco de C: = 0; disco del repositorio = 0; `HKLM\SOFTWARE\Especifika\Autoclave` no existe en este PC (sin RutaDatos). Sesión de administrador.
- E: etiqueta `CCCOMA_X64F`, FAT32. `E:\Autoclave_Setup_1.0.0-alpha.11.exe` no existe (no aplica la idempotencia).
- Primer nivel de E:\: `System Volume Information\`, `drivers\`, `Autoclave_Setup_1.0.0-alpha.10.exe` (89 767 566 B), `LEEME_INSTALACION.md`, `SHA256SUMS.txt`, `recoger_logs.bat`, `recoger_logs.ps1` (copias de `tools\diagnostico\`, que siguen en el repositorio).

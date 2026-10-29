# Tanda 22 — estado

Rama `tanda-22` (desde `dev` 14f62f34). Spec: `docs/mis_plans/prompt_claude_code_tanda22.md`.

| Paso | Estado | Notas / último commit |
|---|---|---|
| A0 | Hecho | rama, evidencia en `evidencia/`, lista de afectados verificada |
| P1 teclado | Pendiente | |
| P2 cliente | Hecho | 182a6480 (TEC-ACC-05: 403 reautenticacion_* reconocidos con reasignacion.err_clave[_requerida], sin cerrar sesión; 429 usuario_bloqueado en `enviar` cierra la sesión local con aviso y segundos; DSC: el 429 cierra en cualquier ruta de `enviar`; `enviar_al_cerrar` sin cambio), unido a tanda-22 |
| Unión P1+P2 | Pendiente | |
| TEC-ACC-04 pantallas | Pendiente | |
| TEC-ACC-07 prueba de regla | Pendiente | |
| R revisión | Pendiente | |
| Suite | Pendiente | |
| K entrega | Pendiente | |
| U USB | Pendiente | |
| Z cierre | Pendiente | |

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

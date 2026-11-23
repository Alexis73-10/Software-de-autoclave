# Modo fábrica y liberación del equipo: informe final

Fecha: 22-nov-2026. Rama `modo-fabrica` (desde `dev` f4a9aa9f). **La rama no está unida a `dev` y la entrega no está compilada.** Plan: `docs/mis_plans/planeacion_modo_fabrica.md` (v2). Cristian ordenó ejecutarlo sin supervisión y sin responder antes las preguntas abiertas: todo lo que se decidió sin él está marcado `DECISIÓN SIN CONFIRMAR` y se consolida al final.

## Resumen

El equipo tiene ahora un estado propio, FÁBRICA → ENTREGADO, de un solo sentido e independiente de la licencia. Una instalación limpia con código `INS` deja el equipo en FÁBRICA, con la franja «MODO FÁBRICA» en pantalla. En FÁBRICA, el ingeniero puede crear y borrar programas de fábrica (números 1 a 10) y ajustar parámetros y calibración. Al terminar ejecuta el cierre de fabricación, que hace tres cosas:

1. Genera y verifica en una USB un paquete de liberación con toda la evidencia.
2. Consolida la base de fábrica propia del equipo: parámetros, calibración y defectos de programas, que luego usa «Restaurar».
3. Deja el equipo limpio y en ENTREGADO, tras un reinicio, en dos tiempos tolerantes a cortes.

En ENTREGADO, todas las funciones de fábrica responden 409 para todos los roles, y nada devuelve el equipo a FÁBRICA. Una revisión de seguridad independiente encontró 8 hallazgos (SAF-01..08), corregidos o documentados. Los dos más graves eran que una marca de cierre plantada borraba registros, y que un cierre incompleto dejaba el equipo en modo sin base, con ciclos.

## Qué se hizo, por etapa

| Etapa | Contenido | Commits |
|---|---|---|
| Plan | Planeación v2, revisión contra el código (`R_revision_plan.md`, R-01..R-06) y decisiones para ejecutar sin supervisión (`decisiones.md`) | 9f4f920c, 220fa6fd |
| 1 | Tabla `estado_fabrica` (migración v16) y sus triggers; entrada desde el asistente; `/status.modo_fabrica`; `requiere_modo_fabrica` (409 `solo_modo_fabrica`); franja `FranjaModoFabrica.qml` (`E1_informe.md`) | d97e8bfd, c350c200 |
| 2 | Programas de fábrica: numeración 1–10, `fabrica_equipo`, `DELETE /fabrica/programas/{cycle_id}`, `fabrica_borrados.lst`, usuario desde 11 en ENTREGADO; botón en Manejo de ciclos (`E2_informe.md`) | b1d37c70, 873793e1, dff6db85 |
| 3 | Base de fábrica del equipo (`core/runtime/fabrica_equipo.py`): parámetros sobre `global_params.json`, calibración por función para «defecto», consolidación de defectos; solo lectura en ENTREGADO (`E3_informe.md`) | f2aa3833, dd5b8c63, 3139e789 |
| 4 | Paquete de liberación (`core/runtime/paquete_liberacion.py`, PDF sin Qt en `services/domain/exportacion/`); `tipo` en el manifiesto y rechazo de la restauración (`E4_informe.md`) | c2e37c4d, a6b825c4 |
| 5 | Cierre en dos tiempos (`core/runtime/cierre_fabrica.py`, `backend/rutas/fabrica.py`, fase 2 en `backend/main.py`) y pantalla `OpcionesCierreFabrica.qml` (`E5_informe.md`) | 7a3bf749, 3ac53ce9 |
| Revisión de seguridad | Agente independiente, solo lectura (`S_revision_seguridad.md`) | b1c04819 |
| Correcciones SAF | SAF-01..04, 06..08 corregidas; SAF-05 documentada; pregunta 4 verificada; `_unidades_usb` único (`S_correcciones.md`) | 0a31e948, 0953f8ae |
| 6 | Riesgos HAZ-FAB-01..07, trazabilidad REQ-117..REQ-123, aceptación `P_aceptacion.md`, bloque de banco FAB, sección de CLAUDE.md y este informe | (commit de esta etapa) |

## Resultados de pruebas

- 18 archivos `tests/test_fab_*.py` (E1..E5, S). Corridos juntos en la Etapa 6: 322 en verde (279 s; con el árbol de trabajo que incluía cambios sin commitear de otra sesión en `ui_bridge.py` y `SeccionEstadoSeguro.qml`).
- Subconjuntos por etapa en verde (ver cada informe): E1, 1042; E2, suite completa igual a la base; E4, 857; E5, 489 + 526; correcciones SAF, 2012, con 4 rojas preexistentes de `test_s9_planta_simulada`.
- Base de comparación: `suite_base.txt`, con 20 fallos y 6 errores preexistentes.
- **Suite completa (copia aislada en 0953f8ae, `-n 4`):** 21 failed, 13073 passed, 11 skipped, 15 xfailed, 6 errors. Contra la base (20 failed, 6 errors, `suite_base.txt`): los 20 fallos de base siguen y hay 1 más, `test_t26_arq_revision.py::test_latido_se_renueva_en_cada_tick_retenido_aunque_verificar_sensores_lance`, que pasa al correrlo solo, en la rama y en `dev` (intermitente por la ejecución en paralelo). Ninguna regresión confirmada.
- Aceptación P-01..P-12: todas tienen prueba automática. P-06 solo cubre la lógica y necesita el Setup real. El detalle está en `P_aceptacion.md`.

## Riesgos y trazabilidad

- `docs/riesgos/registro_riesgos.md`, sección «Modo fábrica y liberación del equipo»:
  - HAZ-FAB-01 a HAZ-FAB-06: los de la §9 de la spec, actualizados con lo implementado.
  - HAZ-FAB-07: nuevo, por las contraseñas semilla tras el cierre (FAB-11, PA-06).
- `docs/riesgos/matriz_trazabilidad.md`: REQ-117 a REQ-123, uno por bloque funcional:
  - estado y entrada;
  - protección y franja;
  - programas;
  - base de fábrica del equipo;
  - paquete;
  - cierre;
  - rechazo de la restauración.

## `DECISIÓN SIN CONFIRMAR`: lista consolidada para Cristian

### Prioridad 1: afectan la seguridad o modifican algo aprobado (D-xx)

| Id | Decisión | Por qué urge |
|---|---|---|
| PA-06 | Rige D-11: tras el cierre, `Admin` e `Ingeniero` quedan con la contraseña semilla, cambio obligatorio y SIS-07. La opción b), fijarlas en el cierre (LIC-02), queda pendiente. | El equipo viaja con contraseñas públicas (HAZ-FAB-07). Cambiar a b) cuesta poco. |
| SAF-01 / S-1 | Sin sello HMAC de la marca de cierre: la protección es la validación contra la base. | La carpeta `datos` es escribible por Usuarios (HAZ-FAB-01). Con K_t común, un sello solo frenaría la edición casual. |
| SAF-04 / pregunta 1 | Un código v1 ya no cuenta como primera instalación; solo v2 `INS`/`INSA`. ¿Se emiten v1 para reinstalaciones? | Cambia DF-02 tal como se había escrito. Depende de la práctica del generador. |
| Pregunta 2 | ¿El desinstalador borra `datos\autoclave.db`? | Si se pierden la base, el perfil y `datos`, un `INS` vigente deja el equipo en FÁBRICA en campo (residual de HAZ-FAB-01). |
| E4-D1 | PDF del paquete con un generador propio sin Qt, distinto del PDF del correo. Alternativa: un rol `--rol pdf-lote` con Qt offscreen. | Es el registro de liberación (ISO 13485). Su formato debe aprobarlo Cristian. |
| Pregunta 5 | ¿La pantalla debe avisar cuando «defecto» cae al neutro? Hoy solo lo indica el campo `origen` de la respuesta y de la auditoría. | Sensor sin corregir sin aviso visible (HAZ-FAB-05). |
| E1-D1 | Franja en el borde inferior (no arriba, por solape con el reloj); revisada solo en arranque, Preciclo y Ciclo en curso. | D-13 / §5.4 piden validarla en todas las pantallas (HAZ-FAB-03, banco FAB-B11). |
| PA-04 | El ciclo con carga real en FÁBRICA no se bloquea. | Registros clínicos que luego borraría el cierre (HAZ-FAB-03). |
| E5-D11 | Durante el cierre se bloquean todas las escrituras (409 `cierre_en_curso`), salvo login, logout, actividad, standby, apagado, alarmas y arranque. | Interacción con la seguridad durante el cierre. |
| S-2 | Una base no verificable bloquea el arranque (`ARR_CIERRE_FABRICA`) en lugar de rechazar la marca. | El equipo no opera hasta un reinicio o la intervención de un técnico. |
| S-3 | Los respaldos de ciclo posteriores a la marca se conservan aunque luego se reimporten en la base entregada. | Residual de HAZ-FAB-04. |
| S-5 / SAF-08 | Un polinomio de calibración debe además ser creciente en el rango; si no, rige el neutro. | Afecta la calibración restaurada. |
| E3-D4, E3-D5 | Criterios de calibración válida (finita, plausible; un «aviso» se restaura) y canal estricto. | Afecta la calibración restaurada. |
| E5-D3 | Superada por SAF-02: ya no se usa la `BD_BLOQUEADA` propia; queda solo como historia. | — |

### Prioridad 2: comportamiento visible o de proceso

- **PA-01:** tickets y PDF como siempre en FÁBRICA.
- **PA-02:** sin marca externa en el registro de Windows.
- **PA-03:** firmas del ingeniero que libera y del aprobador.
- **PA-07:** usuario desde 11 en ENTREGADO.
- **PA-08:** se copia `equipo_instalado`.
- **PA-09:** se borra el catálogo de carga.
- **DF-01..DF-10:** diseño (`decisiones.md`).
- **E1-D2..D10:**
  - color violeta;
  - z 2000 sobre los diálogos;
  - último valor sin conexión;
  - 409 antes de la autenticación;
  - INSA como primera instalación;
  - sin `equipo_instalado` no entra;
  - trigger de base nueva;
  - FÁBRICA → ENTREGADO por UPDATE;
  - texto de cliente.
- **E2-D1..D10:**
  - el id borrado no se reutiliza (`programa_N_2`);
  - «programa de fábrica» = no personalizado;
  - las listas se escriben antes que los archivos;
  - técnico con 403;
  - defectos por número o id;
  - el defecto al duplicar;
  - el número libre cuenta los que cedieron;
  - duplicar en ENTREGADO da un personalizado;
  - lista ilegible;
  - `DialogoConfirmacion`.
- **Observaciones de E2:**
  - el texto `manejo_ciclos.explicacion` («Los programas de fábrica no se borran») contradice el botón en FÁBRICA;
  - el respaldo USB no lleva las listas `.lst`.
- **E3-D1..D3, D6..D10:**
  - se aceptan parámetros de solo lectura;
  - la regla de empaque cuenta en la coherencia;
  - el valor del equipo es también el inicial;
  - T29-05 sigue leyendo el `factory/` original;
  - los no `.json` de `cycles/defecto` no se tocan;
  - FAB-06 permite las escrituras de `gestion_programas` que ya existían;
  - el respaldo lleva la copia sin restaurarla;
  - se guardan todas las funciones de `map_temp`/`map_pres`.
- **E4-D2..D9:**
  - textos en español fijo;
  - hash global = SHA-256 del ZIP;
  - espacio × 1,5 + 20 MB;
  - CSV con «;» y BOM;
  - el PDF de ciclo fallido queda ausente sin abortar;
  - `.lst` en el paquete y programas 1–10 con todos sus parámetros;
  - nombre del PDF con número e id;
  - el informe no incluye los archivos de fábrica del equipo.
- **E5-D1, D2, D4..D10, D12..D14:**
  - fase 2 en `main()`;
  - pasos que no se repiten;
  - mejor esfuerzo en `registros` y `base_vieja`;
  - `system_params` sin usuario;
  - la primera `equipo_instalado`;
  - el detalle de la liberación;
  - 10 s antes del reinicio;
  - confirmación antes que la contraseña;
  - el segmento en Opciones avanzadas;
  - 403 antes que 409 y prueba real de USB;
  - sin bitácora de inicio o aborto;
  - apagado permitido.
- **S-4:** los temporales de la fase 1 se borran siempre.
- **S-6:** texto de la acción del detalle de `ARR_CIERRE_FABRICA`.

## Residuales aceptados o pendientes

- **SAF-05:** lo que se escribe entre la copia del paquete y la marca no llega al paquete.
- La sobrescritura con ceros en SSD no tiene garantía física.
- Los logs abiertos por otros procesos solo se truncan.
- La carpeta `datos` es escribible por Usuarios.
- Sin sello HMAC.
- El PDF propio (E4-D1).
- La franja solo se revisó en algunas pantallas.

## Lo que queda de banco (bloque FAB)

| Paso | Qué se verifica |
|---|---|
| FAB-B1 | Instalación limpia y franja. |
| FAB-B2 | Programas. |
| FAB-B3 | Calibrar y restaurar. |
| FAB-B4 | USB ausente o protegida. |
| FAB-B5 | Cierre con USB real y verificación del ZIP en un PC. |
| FAB-B6 | Reinstalar con `REI`: sigue ENTREGADO. |
| FAB-B7 | Equipo entregado tras dos reinicios. |
| FAB-B8 | Corte de energía durante el cierre. |
| FAB-B9 | Marca plantada y base borrada a mano. |
| FAB-B10 | Rutas en ENTREGADO. |
| FAB-B11 | Revisión visual de la franja con la skill revision-visual-pantallas. |

## Siguiente paso

1. Suite completa (coordinador).
2. Decisiones de prioridad 1 de Cristian.
3. Unión a `dev` y compilación con `tools/entrega/compilar_entrega.py`.
4. Banco FAB.

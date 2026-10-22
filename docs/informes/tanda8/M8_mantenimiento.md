# M8 — Mantenimiento (tanda 8)

Rama: `tanda-8-m8` (desde `23704cb`, que contiene `e1d8f5e`). Fuente: D8-3.25 de `docs/mis_plans/decisiones_tanda_8.md`, con base en `docs/informes/tanda7/M2_mantenimiento_e1.md` y `docs/mis_plans/planeacion_mantenimiento.md`. Etapa no ★: no toca ciclo, puertas, sensores ni ControlLoop.

## Qué se hizo, por punto de D8-3.25

| Punto | Qué se hizo |
|---|---|
| "Último mantenimiento" → "Último preventivo" | Solo cambian los valores del catálogo, no las claves: `menu.ultimo_mantenimiento` = "Fecha del último preventivo" / "Date of last preventive maintenance" (Menú principal y Opciones › Mantenimiento); `equipo.ultimo_mantenimiento` = "Último preventivo" / "Last preventive maintenance" (Información del sistema). También `opciones.mant_intervalos_ayuda` ahora dice "desde el último preventivo" (es) / "the last preventive maintenance" (en), porque desde MNT-01 el contador cuenta desde ahí. `mant_err_reloj` no se cambió: la protección del reloj sí compara contra el último registro de cualquier tipo (decisión 1 de M2). |
| Sin tipo `otro` (P-3) | `TIPOS = ("preventivo", "correctivo")` y `TIPOS_HISTORICOS = ("calibracion", "otro")` en `core/runtime/mantenimiento.py`, que sigue siendo la única definición. El servicio rechaza `otro` (`POST /maintenance/records` → 422 `validacion`, sin escribir nada). El controlador QML ya no ofrece el chip "Otro" ni lo envía. `opciones.mant_tipo_otro` = "Otro (histórico)" / "Other (historical)", con el mismo criterio que MNT-05. Las filas viejas se conservan (la tabla es de solo anexar) y no mueven el contador. **Sin migración ni cambio de esquema en `db_manager.py`**: la columna `tipo` no tiene restricción CHECK, y una migración no puede reescribir las filas por los disparadores de solo anexar. |
| MNT-04 | `GET /maintenance/records` admite `admin` además de técnico e ingeniero (D-9). Registrar (`POST /maintenance/records`) y configurar (`PUT /maintenance/config`) siguen siendo solo de técnico e ingeniero; el operador sigue sin acceso (403) y, sin sesión, se responde 401. **UI: no corresponde todavía.** La pestaña Historial de Opciones › Mantenimiento llega en la etapa E5 de la planeación, y hoy no existe ninguna pantalla QML de historial. Además, la sección Mantenimiento de Opciones sigue siendo solo para técnico e ingeniero (`permisos_opciones.py`, `_TECNICOS`). No se tocó. |

No se tocó el formulario del preventivo (P-1 a P-10), ni el texto del botón de registro (`opciones.mant_registrar`, que es de V8a, D8-5.3).

## Commits

- `abe1817` feat(tanda8-m8): D8-3.25 último preventivo, sin tipo otro (P-3) y el admin consulta el historial (MNT-04). Es un solo commit porque los tres cambios comparten las pruebas y los catálogos.
- (este informe y el log de la suite: commit `docs(tanda8-m8)`)

## Archivos ("puntos de choque" marcados)

- `src/autoclave/i18n/es.json` y `en.json`: **punto de choque**. Son 4 valores cambiados en cada uno y ninguna clave nueva: `menu.ultimo_mantenimiento`, `equipo.ultimo_mantenimiento`, `opciones.mant_intervalos_ayuda` y `opciones.mant_tipo_otro`.
- `src/autoclave/backend/server.py`: **punto de choque**. Solo cambia la dependencia de rol de `get_maintenance_records`.
- `src/autoclave/core/runtime/mantenimiento.py`: `TIPOS` y `TIPOS_HISTORICOS`.
- `db_manager.py`: **no se tocó**. No ocupa número de migración.
- QML: **no se tocó** (los chips salen de `control.tipos`).
- `docs/mis_plans/revision_traducciones.md`: fila nueva con los textos en inglés cambiados ("sin revisar").
- Pruebas: `tests/test_m8_mantenimiento.py` (nuevo, 11 pruebas). En `test_m1_mantenimiento_backend.py`, `test_m1_mantenimiento_ui.py`, `test_b3_mantenimiento.py` y `test_b3_mantenimiento_ui.py`, los registros de prueba con `otro` pasan a `correctivo`; en todos esos casos se usaba como cualquier tipo registrable que no fuera el preventivo. En `test_m2_mantenimiento_e1.py` se actualizaron las tuplas esperadas, y la fila de `otro` de la prueba "sin preventivo, la base es la instalación" ahora se inserta directamente como fila histórica.

## Pruebas

TDD: las 11 pruebas nuevas se escribieron primero; 9 fallaban antes del cambio. Las 2 de permisos de admin para registrar y configurar y la del operador ya pasaban, y quedan como regresión.

- Rótulos "Último preventivo" en es y en (menú, equipo) y la ayuda de intervalos.
- `otro` no es registrable y es histórico. El servicio lo rechaza con `validacion`; el endpoint da 422 sin escribir nada; el controlador no lo ofrece ni lo envía.
- Los textos "Otro (histórico)" / "Other (historical)". Una fila histórica de `otro` se conserva en el historial y no mueve el contador.
- MNT-04: el admin consulta (200, ve la fila). El admin no registra ni configura (403, nada escrito). El operador da 403 y sin sesión da 401.

Pruebas relacionadas (mantenimiento, i18n, información del equipo, menú principal QML, Opciones QML, permisos): 192 + 172 pasan.

**Suite completa:** `5392 passed, 3 skipped, 3 xfailed` en 27 min 08 s, con `autoclave.__file__` = `C:\Users\tecni\Documents\codigo_autoclave\.claude\worktrees\agent-a0b940080887b4d88\src\autoclave\__init__.py`. Comparado con la línea base (5382 / 3 / 3): +11 pruebas nuevas y −1 caso parametrizado (`otro` en `test_correctivo_y_otro_no_resuelven_el_aviso`). Log: `docs/informes/tanda8/suites/m8.log`.

## DECISIONES SIN CONFIRMAR

1. **Se cambian los valores y no las claves de i18n** (`*.ultimo_mantenimiento` conserva su nombre). Motivo: evitar choques con otras ramas y con las pruebas que buscan la clave. Alternativa: renombrar la clave a `ultimo_preventivo`.
2. **Texto en inglés: "Last preventive maintenance"** (y no "Last preventive"), porque "preventive" solo, como sustantivo, no es natural en inglés. En español se usa "Último preventivo", tal como dice la decisión. Queda en `revision_traducciones.md`.
3. **MNT-04 sin UI en esta tanda:** la planeación pone la pestaña Historial en E5. Tampoco se abrió al admin la sección Mantenimiento de Opciones, porque ahí solo se registra y se configura, que no es su permiso.
4. **`opciones.mant_intervalos_ayuda` también se ajustó** ("desde el último preventivo"). No lo pide la decisión de forma literal, pero el texto anterior era inexacto desde MNT-01. Para revertir: solo el valor en el catálogo.

## PREGUNTAS PARA CRISTIAN

Ninguna bloqueante.

## Pendientes

- La pestaña Historial (E5), con el rótulo de las filas históricas (`opciones.mant_tipo_<tipo>`) y la consulta del admin desde la UI.
- La revisión lingüística de los textos en inglés cambiados.

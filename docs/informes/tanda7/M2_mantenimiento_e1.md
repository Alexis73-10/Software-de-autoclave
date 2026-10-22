# M2 — Mantenimiento E1 (tanda 7)

Rama: `tanda-7-m2` (desde `e8e42d7`). Fuente: `docs/mis_plans/planeacion_mantenimiento.md` §10, con los cambios de la etapa M2 de `instruccion_claude_code_tanda_7.md` (commit autorizado; `state_machine.py` intacto; formulario del preventivo fuera).

## Resumen

| Hallazgo | Qué se hizo | Commit |
|---|---|---|
| — | La planeación (estaba sin versionar) se agrega a la rama | `c38e29c` |
| MNT-01 (Alta) | Solo el **preventivo** reinicia el contador (días y ciclos) y resuelve `MANTENIMIENTO_VENCIDO`. `ultimo_mantenimiento(tipo="preventivo")` filtra por tipo; `ultimo_registro()` nuevo, sin filtro, para la protección del reloj | `ac39a14` |
| MNT-02 (Media) | `calibracion` sale de `TIPOS`. `POST /maintenance/records` con `tipo="calibracion"` → 422 `validacion`, sin escribir nada | `a375d7d` |
| MNT-03 (Baja) | `TIPOS` tiene una sola definición, en `core/runtime/mantenimiento.py` (lógica pura). El servicio la reexporta y el controlador QML la importa: deja de ofrecer el chip "Calibración" | `e8bbe6e` |
| MNT-05 (Baja) | `TIPOS_HISTORICOS = ("calibracion",)`. `opciones.mant_tipo_calibracion` pasa a "Calibración (histórico)" / "Calibration (historical)". Nunca se ofrece; una fila vieja no afecta el contador | `efa57a5` |

Nada de esto bloquea un ciclo ni toca la seguridad: el aviso sigue siendo no bloqueante y el servicio no toca el ControlLoop.

## Archivos modificados

- `src/autoclave/services/domain/logging/db_manager.py`: **punto de choque**. Solo cambian dos métodos de lectura (`ultimo_mantenimiento` con el parámetro `tipo`, y el nuevo `ultimo_registro`). **Sin migración ni cambio de esquema**: no se tocó la versión de la base.
- `src/autoclave/core/runtime/servicio_mantenimiento.py`: `_ultimo()` lee el preventivo; `_ultimo_registro()` nuevo; `reloj_no_confiable()` usa el último registro de cualquier tipo; `TIPOS = m.TIPOS`.
- `src/autoclave/core/runtime/mantenimiento.py`: `TIPOS` y `TIPOS_HISTORICOS`.
- `src/autoclave/ui_qml/controllers/mantenimiento_controller.py`: importa `TIPOS` en vez de duplicarlo.
- `src/autoclave/i18n/es.json` y `en.json`: **punto de choque**. Una sola línea en cada uno (texto de `opciones.mant_tipo_calibracion`); ninguna clave nueva.
- `docs/mis_plans/revision_traducciones.md`: fila del texto en inglés cambiado ("sin revisar").
- `tests/test_m2_mantenimiento_e1.py` (nuevo, 22 pruebas) y `tests/test_i18n.py` (la familia `opciones.mant_tipo_` incluye también los tipos históricos).
- `docs/mis_plans/planeacion_mantenimiento.md` (agregado, sin cambios).

## Pruebas

Pruebas nuevas en `tests/test_m2_mantenimiento_e1.py`, las de §10.5 y algunas más:

- base de datos: filtro por tipo, desempate por id en la misma fecha, sin preventivo devuelve `None`;
- preventivo y después correctivo: la base sigue siendo el preventivo (días y ciclos);
- correctivo y "otro" no resuelven `MANTENIMIENTO_VENCIDO`; un preventivo sí, también cuando vence por ciclos;
- sin ningún preventivo, la base es la instalación aunque haya correctivos;
- una fila histórica de `calibracion` no afecta el contador y se conserva en el historial;
- con el reloj atrasado respecto de un **correctivo**, no se registra (la protección del reloj mira cualquier tipo);
- el servicio y el endpoint rechazan `calibracion` (422 `validacion`);
- servicio y controlador comparten la misma tupla; el controlador no ofrece ni envía `calibracion` y no importa el servicio ni la máquina de estados;
- textos es/en de "Calibración (histórico)"; todo tipo, registrable o histórico, tiene texto; la pantalla arma los chips desde `control.tipos`.

Antes de los cambios, las pruebas de MNT-01, 02, 03 y 05 fallaban (TDD). Después, las pruebas afectadas pasan: mantenimiento, i18n e información del equipo, 166 en total.

Suite completa: línea base 5020 passed / 2 skipped / 3 xfailed. Resultado de esta rama: SUITE_RESULTADO.

**Ojo, entorno:** `autoclave` está instalado en modo editable apuntando a `src/` de la carpeta **principal** del repositorio. Si se corre `pytest` dentro de un worktree sin `PYTHONPATH=<worktree>/src`, se prueba el código de la carpeta principal y no el del worktree (lo comprobé: las pruebas nuevas fallaban así aunque el código ya estuviera corregido). Esta rama se probó con `PYTHONPATH` apuntando al `src` del worktree. La sesión principal debería tenerlo en cuenta al verificar las ramas de los demás agentes.

## DECISIONES SIN CONFIRMAR

1. **La protección del reloj compara contra el último registro de cualquier tipo** (§10.1 pedía decidir).
   - Motivo: la tabla es de solo anexar. Ningún registro nuevo, de ningún tipo, puede quedar con fecha anterior al último que ya existe, porque no se podría corregir después.
   - Alternativa: comparar solo contra el último preventivo.
   - Commit: `ac39a14`. Para revertir: en `reloj_no_confiable()`, volver a `self._ultimo()`.
2. **`TIPOS` va a `core/runtime/mantenimiento.py` y no se importa desde el servicio** (§10.3 lo permitía).
   - Motivo: `servicio_mantenimiento` importa `state_machine.alarms.catalogo` y utilidades de E/S. `mantenimiento.py` es lógica pura, sin E/S.
   - Alternativa: un módulo de constantes aparte.
   - Commit: `e8bbe6e`.
3. **El rótulo "Último mantenimiento"** (Menú principal, Opciones › Mantenimiento, Información del sistema) ahora muestra la fecha del último **preventivo**, porque viene de la base del cálculo. El texto del rótulo no se cambió.
   - Alternativa: renombrarlo a "Último preventivo".
   - Para revertir el comportamiento hay que revertir `ac39a14`, lo que no se recomienda: reabriría MNT-01.
4. **El tipo `otro` se conserva** mientras P-3 siga abierta. No reinicia el contador.
5. **MNT-05 se limitó al catálogo i18n y a la constante.** Hoy no existe ninguna pantalla QML de historial de mantenimientos (llega en E5). `GET /maintenance/records` devuelve la fila con `tipo="calibracion"`, y la UI futura la rotulará con `opciones.mant_tipo_calibracion` = "Calibración (histórico)".

## PREGUNTAS PARA CRISTIAN

- Ninguna bloqueante. No hizo falta tocar `state_machine.py`.
- Por confirmar (relacionadas): ¿se renombra el rótulo a "Último preventivo" (decisión 3)? P-3 (`otro`) y MNT-04 (admin consulta el historial) siguen abiertas; MNT-04 no forma parte de E1.

## Fuera de alcance (no se tocó)

El formulario del preventivo (P-1 a P-10), E2 a E7 (migración de tablas nuevas, plantilla, endpoints, PDF y correo), MNT-04 y el predictivo.

## Comprobaciones manuales para Cristian

1. Opciones › Mantenimiento: los chips de tipo son solo Preventivo, Correctivo y Otro (sin Calibración).
2. Registrar un **correctivo**: "Próximo vencimiento", "Último mantenimiento" y "Ciclos restantes" no cambian.
3. Registrar un **preventivo**: "Próximo vencimiento" pasa a hoy + intervalo, y "Ciclos restantes" vuelve al intervalo completo.
4. Con el mantenimiento vencido (por ejemplo, intervalo de ciclos bajo), un correctivo no quita el aviso "Mantenimiento vencido"; un preventivo sí.

# O1 — Opciones › Parámetros del ciclo ★

Inventario previo: `O1_inventario_opciones.md`.

## Qué ya estaba (verificado)
- Flujo programa → sección → parámetros → ventana de ajuste. La ventana muestra el valor actual, el defecto (la tarjeta y el botón "Por defecto" lo aplican), mínimo, máximo y la última modificación (usuario y fecha), y abre el teclado numérico solo al tocar.
- Lectura de cualquier programa (`GET /programas`, `GET /programas/{n}/seccion/{s}`), no solo del seleccionado.
- Sensores por programa: exactamente 1 Principal, de 0 a 2 Referencias, y "No en uso"; solo sondas conectadas (T3/T12).
- Permisos: técnico e ingeniero editan; el técnico no lo hace con ciclo en curso, el ingeniero sí; el admin no ve la sección.
- Coerción de booleanos, NaN/inf y escritura atómica (ver inventario).

## Qué se agregó
1. **Modelo de defectos.** Hay tres orígenes: `cycles/factory/` (solo fábrica), `cycles/defecto/<id>.json` (defectos creados en el hospital) y `cycles/user/` (perfil completo). `CycleManager.defecto(n)` usa el del hospital y, si no existe, el de fábrica. La ventana de ajuste y el asterisco de "modificado" usan ese defecto.
2. **Gestión de programas** (`core/managers/gestion_programas.py`, `PUT /programas/{n}/habilitado`, `POST /programas/{n}/duplicar`, `DELETE /programas/{n}`). Técnico fuera de CICLO; ingeniero también en CICLO; admin, 403.
   - **Deshabilitar:** el programa no aparece en Preciclo (`/programas/seleccionables`) y `/cycle/select` lo rechaza (409 `programa_deshabilitado`). El programa activo no se puede deshabilitar.
   - **Duplicar:** crea un programa personalizado con un número nuevo. El número nunca se reutiliza (queda registrado en `cycles/user/numeros_usados.json`). El defecto del duplicado son los valores del origen al duplicar. El nombre no puede repetirse ni tener caracteres de control. Si el origen no cumple el catálogo, el duplicado se rechaza.
   - **Borrar:** solo programas personalizados, nunca el activo ni uno de fábrica.
3. **Entradas mostradas por programa** (`GET/PUT /cycle/display-inputs`). De 1 a 3 entradas, distintas, elegidas entre las AI de `io_enabled` del equipo. Se guardan en el JSON del programa (`entradas_mostradas`). Por omisión son `temp_camara`, `temp_referencia` y `pres_camara`.
4. **UI** (`OpcionesParametrosCiclo.qml`, `ParametrosCicloController`):
   - Fila "Entradas mostradas", con una vista para elegir de 1 a 3 entradas, en orden.
   - Bloque "Gestión del programa" con Habilitar/Deshabilitar, Duplicar (nombre con el teclado alfanumérico) y Borrar (con confirmación). Borrar solo aparece en programas personalizados.
5. Se agregó la clave i18n que faltaba `io.ai.temp_drenaje_camara` (también la usa Entradas/Salidas).

## Revisión (safety-reviewer)
- **Alto SAF-01:** la auditoría se escribía después de cambiar el disco, sin revertir si fallaba (RB-03.5). **Corregido:** `_gestion` audita con `registrar_auditoria` y, si falla, revierte. Duplicar borra los archivos nuevos (el número queda usado). Borrar va en dos pasos: aparta los archivos como `.borrado`, audita y después elimina; si la auditoría falla, los restaura. Habilitar y entradas restauran el valor anterior. Hay prueba de cada caso.
- Medio SAF-02 (carrera con `/cycle/select`): ya cubierto, porque `guard_estado` mantiene `bloqueo_maquina` (el mismo lock que `/cycle/select`) durante la operación. Las escrituras de archivo (pequeñas, con fsync) quedan dentro de ese lock a propósito. **DECISIÓN SIN CONFIRMAR O1-2:** se acepta el costo para el tick; en un disco lento, una escritura con fsync puede retrasar un tick decenas de milisegundos. Alternativa: dos fases (decidir dentro del lock y escribir fuera, con revalidación).
- Medio SAF-03 (nombre repetido o con caracteres de control): **corregido**.
- Medio SAF-04 (el duplicado hereda valores sin validar): **corregido en parte**. Se valida contra el catálogo; F0, líquidos y sensores se siguen comprobando al seleccionar e iniciar, como en cualquier programa.
- Bajo SAF-05 (diccionario modificado durante la iteración): `list(...)` en `gestion_programas`. **PENDIENTE** en el resto de `server.py`, que itera `cycle_manager.cycles.values()` sin copia.
- Bajo SAF-06 (`.bak` sin actualizar en habilitado y entradas): **PENDIENTE**.
- Bajo SAF-07 (`editable` de display-inputs sin rol ni estado): **PENDIENTE**. La UI combina `editable` con `edicionPermitida`.

## Pendiente
- **Preciclo y Ciclo siguen mostrando las 3 entradas fijas.** La selección se guarda y se expone, pero las pantallas todavía no la usan; tampoco la gráfica ni el registro por ciclo de la selección vigente (`planeacion_opciones.md` §3.1). Requiere tocar Preciclo, Ciclo y el registro de lecturas: no se hizo en esta tanda.
- Los valores se mostrarán en las unidades elegidas cuando exista U1. El enganche es `raiz.texto(valor, tipo)` en `OpcionesParametrosCiclo.qml`, que pasará por el formateador único.
- `sensor-role-auditor` no se ejecutó: O1 no cambia los roles de sensores ni su lectura (las entradas mostradas solo afectan a la presentación).

## Pruebas
`tests/test_o1_gestion_programas.py` (27) y `tests/test_o1_parametros_ciclo_ui.py` (5).

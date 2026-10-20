# O1 — Inventario de OPCIONES (20-oct-2026)

Reemplaza a `docs/mis_plans/informe_estado_opciones.md` (7-oct), que está desactualizado. Referencia: `planeacion_opciones.md` v4.

| Sección (clave) | Roles | Estado | Qué hay / qué falta |
|---|---|---|---|
| Parámetros del ciclo (`parametros_ciclo`) | T, I | **Listo** (tras O1) | Lista de programas → secciones → parámetros → ventana de ajuste (actual, por defecto con botón, mín., máx., última modificación, teclado al tocar). Sensores por programa (1 Principal, 0–2 Referencia). **Nuevo en O1:** defectos del hospital (`cycles/defecto/`), gestión de programas (habilitar/deshabilitar, duplicar, borrar personalizados) y entradas mostradas (1 a 3). Falta: usar las entradas mostradas en Preciclo/Ciclo (hoy siguen fijas, ver O1). |
| Parámetros del equipo (`parametros_sistema`) | T, I | **Parcial** | P2: interruptor de impresora. Faltan los parámetros de la tabla §3.2 (tiempos, temperaturas, contadores), las unidades (U1) y el idioma. |
| Entradas / Salidas (`entradas_salidas`) | T, I | **Listo** | Entradas digitales, salidas con modo prueba (P1), temperaturas y presiones con calibración por sensor. |
| Mantenimiento (`mantenimiento`) | T, I | **Parcial** | Vencimiento, registro e intervalos (M1, B3). Faltan la calibración atmosférica (§5), la página de prueba de la impresora y la impresión de ganancias. |
| Opciones avanzadas (`opciones_avanzadas`) | T, I (plan: solo I) | **Próximamente** | Fuera de esta tanda (reasignación de E/S). |
| Usuarios (`usuarios`) | A, I | **Parcial** | Botón a Nuevo usuario. Faltan desactivar, restablecer contraseña y operadores. |
| Conectividad (`conectividad`) | A, T, I | **Próximamente** | — |
| Fecha y hora | todos (plan) | **Falta** | No existe la sección. |
| Bitácora de auditoría | todos, lectura (plan) | **Falta** | No existe la sección (`audit_log` sí existe en el backend). |
| Información del sistema | todos, lectura (plan) | **Falta** | Solo el panel del Menú principal ("No disponible" para mantenimiento y versión de tarjeta). |

## Backend de parámetros de ciclo (pedido del inventario anterior)
Ya estaban resueltos por T10 (tanda del 14-oct) y se verificaron en el código:
- Coerción de booleanos: `catalogo_parametros.coercionar` solo acepta `true`/`false` JSON (nunca `bool("false")`).
- NaN e infinito: rechazados (`math.isfinite`).
- Escritura atómica del JSON: `_escribir_json_programa` (.tmp + fsync + `os.replace`, con `.bak`).

O1 agrega lo mismo en sus escrituras nuevas (`gestion_programas._escribir_atomico`) y `StrictBool` en `habilitado`.

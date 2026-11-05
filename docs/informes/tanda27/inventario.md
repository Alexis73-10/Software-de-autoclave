# Tanda 27: índice de inventarios (5-nov-2026)

Solo análisis; nada se borró. Decisiones pendientes: [dudosos.md](dudosos.md) (DEP-01..DEP-32). Criterios de borrado a–e en cada inventario detallado. «Se conserva» = vivo o conservado por decisión.

## ESP32 / enlace serial
Detalle: [inventario_esp32.md](inventario_esp32.md)

| Concepto | Borrable | Dudoso | Se conserva / acción |
|---|---|---|---|
| Código muerto en `src/` | 0 (1 constante `ALARMAS_SOLO_SERIAL` se renombra) | 1 (DEP-30) | ≈24 rastros persistidos (TARJETA_*, `adc_*`, historial, SOUP) |
| Comentarios/pruebas a reescribir (clase A) | ≈55 | 1 literal (DEP-31) | sin nombrar la ESP32 |
| Docs obsoletos a mover (E) / riesgos a marcar (F) | 0 | ≈100 archivos / ≈10 filas (DEP-28, 29) | `docs/versiones`, SOUP |

## Python (`src/autoclave`)
Detalle: [inventario_python.md](inventario_python.md)

| Concepto | Borrable | Dudoso | Se conserva |
|---|---|---|---|
| Módulos (298) | 0 | 5 (DEP-03, 04, 13) | 293 |
| Símbolos sin referencia | ≈33 (7 métodos del cliente, constantes, import, variable) | ≈90 (DEP-05..12) | resto |

## QML
Detalle: [inventario_qml_rutas_i18n.md](inventario_qml_rutas_i18n.md) §1

| Concepto | Borrable | Dudoso | Se conserva |
|---|---|---|---|
| Archivos `.qml` (113) | 2 (`ResumenPeriodo`, `BarraInferior`) | 10 de `Pruebas/` (DEP-14) | 101 |
| Puente `ReporteResumen` / propiedades sin lector | 0 | 1 + 15 (DEP-15, 16) | resto |

## Rutas del backend
Detalle: [inventario_qml_rutas_i18n.md](inventario_qml_rutas_i18n.md) §2

| Concepto | Borrable | Dudoso | Se conserva |
|---|---|---|---|
| Rutas de la app (110) | 3 (`/cycle/history/{id}/readings`, `/cycle/current/readings`, `/cycles`); exige regenerar `tanda15/base/` | 3 (DEP-17..19) | 104 |

## i18n
Detalle: [inventario_qml_rutas_i18n.md](inventario_qml_rutas_i18n.md) §3

| Concepto | Borrable | Dudoso | Se conserva |
|---|---|---|---|
| Claves (2205; el guion lista 392 sin uso) | 33 (en es y en) | 2 (DEP-20, 21) + familia TARJETA_* (DEP-22) | 357 de las 392 en uso por familias dinámicas o literales fuera del alcance del guion; 1813 usadas |

## tools
Detalle: [inventario_tools_pyside.md](inventario_tools_pyside.md) Parte 1

| Concepto | Borrable | Dudoso | Se conserva |
|---|---|---|---|
| Herramientas | 5 archivos (`ensayo_actualizacion_{b_d,f_g,g_h,i}.py`, `medir_contador_ciclos.py`) | 7 entradas (DEP-23..27) | 10 vigentes |

## Pruebas
Detalle: inventarios QML/rutas (§4), tools/ui_pyside y ESP32 (§3)

| Concepto | Borrable | Dudoso | Se conserva |
|---|---|---|---|
| Pruebas que solo prueban lo borrable | 3 (las de `/cycles`; hay que regenerar la base de rutas) | ≈16 solo-PySide + 2 con `req` (DEP-02); 3 de módulos de dominio (DEP-03) | resto; ≈14 pruebas con comentarios ESP32 se reescriben, y `test_t20_s2_retiro_serial.py` es excepción |

## Dependencias
Detalle: [inventario_python.md](inventario_python.md) §5 e [inventario_tools_pyside.md](inventario_tools_pyside.md)

| Concepto | Borrable | Dudoso | Se conserva |
|---|---|---|---|
| `pyproject`/lock | 0 | `PySide6-Fluent-Widgets[full]` y 5 transitivas exclusivas (`Frameless-Window`, `darkdetect`, `colorthief`, `scipy`, `numpy`) (DEP-01) | resto; `pyserial` ya retirado |

## ui_pyside
Detalle: [inventario_tools_pyside.md](inventario_tools_pyside.md) Parte 2

| Concepto | Borrable | Dudoso | Se conserva |
|---|---|---|---|
| 25 módulos, 4 547 líneas, 14 vistas | 0 | todo (DEP-01): faltan «Imprimir alarmas activas» y «Tiempo de secado» del ciclo activo en QML | todo, incluido `NuevoUsuarioBridge` (importado por `ui_qml/app.py:30`) y `AutoclaveSettings.spec` |

# Decisiones para revisar — tanda 4 (20-oct-2026)

## Resumen (10 líneas) — qué mirar primero
1. **Revisión con agentes hecha después (a pedido de Cristian):** B5, B7, B8 y B9a dieron 2 Altos (SAF-01 modo prueba huérfano al caducar el token; TMG-01 contador no escribible) y varios Medios: **todos los Altos y Medios corregidos**; quedan 3 Bajos pendientes. Ver `R_revision_agentes.md`.
2. **Otra sesión trabajó en el mismo árbol** (teclados QML, Entradas/Salidas, calibración, `server.py`, `sesion_backend.py`, i18n). Mis commits llevan solo mis hunks; sus cambios sin commit siguen en el árbol. Ver "Coordinación" abajo antes de unir su trabajo.
3. **B7 caducidad de tokens (5 min)**: la UI avisa al backend cada 30 s mientras se usa; sin uso el token caduca (401). El PySide no tiene aviso periódico: si se deja inactivo >5 min, el siguiente guardado pide iniciar sesión otra vez.
4. **B8**: `POST /io/test/force-exit` (solo ingeniero, con confirmación, solo con el dueño sin sesión). **No hay botón en pantalla** todavía.
5. **B5**: la bandera `impresora.habilitada` no existía; se creó en `data/impresora.json` (defecto habilitada). **Sin pantalla ni asistente** que la cambie (solo API). La bandera solo gobierna el aviso, no la impresión.
6. **B3**: valores 365 días / 1000 ciclos aplicados; migración automática de los 180/0 no editados; detector de reloj adelantado (>1 día vs monotónico, se corrige reiniciando si fue un ajuste legítimo hacia adelante); pantalla de intervalos provisional.
7. **B6**: el conteo del "más usado" incluye todo ciclo terminado (completo, abortado, con fallo); no cuenta ciclos anteriores a la columna `numero_programa`; FALLA no permite cambiar de programa desde el selector.
8. **B2**: `scipy` ya no se excluye del `.spec`; falta COMPILAR y hacer las 5 comprobaciones con el .exe (en `B2_spec_scipy.md` y la hoja A-05).
9. **B1/B4/B9**: secado PySide guarda por la ruta vigente; renombre "Parámetros del equipo" hecho; B9b (permisos de puertas por rol) DIFERIDO con `xfail`.
10. Push: ver el índice (`informe_tanda_2026-10-20_t4.md`, sección Entrega). `main` no se tocó.

Cómo revertir: cada decisión está en el commit de su etapa (`git revert <hash>`). Orden: impacto en seguridad/instalación. (Las decisiones van dentro del commit de su etapa, no en commits separados, porque son parte de la misma pieza de código; cada una indica el punto exacto a cambiar.)

## Tabla
| # | Etapa | Decisión | Motivo | Alternativa | Commit | Revertir |
|---|---|---|---|---|---|---|
| 1 | B1 | La vista PySide de secado envía solo los campos que cambiaron, uno por PATCH | menos entradas de auditoría; cada rechazo se atribuye a su campo | enviar los 5 siempre | 2163466 | `_save()` de `secado.py` |
| 2 | B2 | Solo se quita `scipy` de `excludes`; el resto no se toca | es lo único que se importa al cargar (medido) | quitar también `matplotlib`/`tkinter` (no se importan: no hace falta) | a806594 | `Autoclave.spec` |
| 3 | B3 ★ | Equipos ya instalados: el "contador al instalar" es el valor del contador en la primera evaluación con esta versión (`data/mantenimiento_base.json`) | un equipo con ciclos previos no debe nacer "vencido" | contar desde 0 | d5ef909 | `_ciclos_instalacion()` |
| 4 | B3 ★ | Reloj adelantado = pared avanza >1 día más que el monotónico desde el arranque; sin referencia tras un reinicio | no hay fuente de tiempo independiente en el equipo | otra tolerancia o ancla persistente | d5ef909 | `reloj_no_confiable()` |
| 5 | B3 | La migración 180/0→365/1000 solo si no hay auditoría de configuración y hay base; edición manual del archivo a 180/0 se migra | no pisar lo editado por una persona | migrar siempre / nunca | d5ef909 | `migrar_valores_provisionales()` |
| 6 | B4 | No se cambian identificadores, claves, rutas ni los informes históricos firmados | compatibilidad | renombrar también claves | 64d1ada | texto de `es.json`/`en.json` |
| 7 | B5 ★ | Bandera en `data/impresora.json` (defecto habilitada), solo API; no en el asistente de instalación | no existía; el perfil está bloqueado | parámetro del perfil + asistente | 9a3facc | `ConfigImpresora` / endpoints `/printer/config` |
| 8 | B5 ★ | "Desconocida" no avisa; la verificación tiene plazo de 5 s en hilo; se limpia con una impresión exitosa | no bloquear ni dar falsos avisos | reintentar periódicamente | 9a3facc | `VigilanciaImpresora` |
| 9 | B6 | Conteo = todos los ciclos terminados; anteriores a `numero_programa` no cuentan | lo pedido (completos y abortados) | solo COMPLETADO | edda249 | `conteo_ciclos_por_programa` |
| 10 | B6 | Tocable solo en PREPARACION/PREPARADO (no FALLA); la ventana lista solo programas de usuario ejecutables | conservador; el backend decide el resto | permitir FALLA | edda249 | `programaTocable` en `PantallaPreciclo.qml` |
| 11 | B6 | `/cycle/select` sigue sin exigir sesión (decisión 2 del 19-oct) y el selector tampoco | misma regla que hoy | exigir sesión | edda249 | — |
| 12 | B7 ★ | La UI renueva el token con `GET /auth/sesion` cada 30 s mientras se usa; PySide no | sin esto un operador que solo navega perdería la sesión del backend | renovar solo con escrituras | b682c6c | `_renovar_en_servidor` |
| 13 | B7 ★ | El plazo vive en `core/runtime/sesion_inactividad.py` (neutral) y la UI lo importa | un solo parámetro, sin importar Qt en el backend | importar de la UI | b682c6c | — |
| 14 | B8 ★ | La salida forzada exige dueño sin sesión; el ingeniero dueño también puede usarla; no cancela el estado seguro | solo se libera lo huérfano | permitir forzar con dueño vigente | b682c6c | endpoint `/io/test/force-exit` |
| 15 | B9a ★ | No se cambian `contador.siguiente`/`marcar_en_curso`: se documentan con medición (~2 ms, una vez por ciclo) | preservar el orden "marca antes de la base" y la numeración sin huecos | llevarlas a un hilo | e071aed | — |
| 17 | Revisión | Plazo del token del backend = 360 s (UI 300 s + 2 avisos); vigilante de 2 s del dueño del modo prueba; el técnico dueño puede forzar su propio modo prueba | SAF-01/02/03 | plazo igual al de la UI | (ver git log) | `sesion_inactividad.py`, `_revisar_dueno_modo_prueba` |
| 16 | B9b | Permisos de puertas por rol DIFERIDO con `xfail(strict)` | el equipo de pruebas tiene 2 puertas manuales | implementar ya | 6ead212 | quitar el `xfail` al implementar |

★ = sin revisión de agentes de seguridad/temporización (orden de Cristian), salvo B3 (revisada, sin Críticos/Altos).

## Coordinación con la otra sesión (archivos con cambios ajenos sin commit)
`server.py` (modo prueba/calibración/E-S), `sesion_backend.py` (claves `io.*`), `Main.qml`, `Opciones.qml`, `PantallaPreciclo.qml`, `es.json`, `en.json` y varios QML de teclado. Mis cambios en esos archivos están commiteados como hunks mínimos y son compatibles con los suyos (se editaron árbol e índice por separado). Dos pequeños retoques míos se hicieron SOLO en el árbol sobre código suyo sin commit: `tokens.obtener(..., renovar=False)` en `_caducar_momentanea` y `_salir_por_inactividad` de `server.py` (para que una consulta interna no renueve el token del dueño). Si esa sesión reescribe esas funciones, repetir el `renovar=False`.

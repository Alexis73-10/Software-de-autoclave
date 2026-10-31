# O3 — Entradas mostradas en Preciclo, Ciclo en curso y gráfica (tanda 6)

Rama `tanda-6-o3` (desde `tanda-6`, con B1). Conecta la selección de 1 a 3 entradas por programa que dejó O1 de la tanda 5 (`entradas_mostradas` del JSON del programa, `GET/PUT /cycle/display-inputs`). No cambia lógica de ciclo, de seguridad ni de registro.

## Qué cambió

| Capa | Archivo | Cambio |
|---|---|---|
| Backend | `backend/server.py` | `GET /cycle` agrega `entradas_mostradas` (la selección del programa, o las de omisión vía `gestion_programas.entradas_de`) y `entradas_no_en_uso` (sensores de temperatura que el programa tiene en "No en uso"). Si falla la lectura de `io_enabled`, se devuelven las de omisión: nunca un 500. |
| Dominio | `ui_qml/domain/entradas_mostradas.py` (nuevo) | Filas para QML (`clave, tipo, valor, unidad, enUso`) en la unidad vigente (módulo de unidades U1), series de la gráfica y conversión de los datos de la gráfica. Entrada desconocida, sin lectura, "No en uso" o psi sin P_atm: "—". |
| Puente | `ui_qml/bridge/ui_bridge.py` | Propiedades `entradasMostradas` y `seriesGrafica` (señal `entradasChanged`), calculadas en cada refresco desde el caché de `/cycle` y `/status`. Al cambiar de programa, `/cycle` cambia y con él las filas y series. |
| Puente | `ui_qml/bridge/progreso_ciclo.py` | `datosGrafica` sale en la unidad vigente (antes iba siempre en °C/kPa, con la etiqueta fija del eje). |
| QML | `Pantallas/PantallaPreciclo.qml`, `Pantallas/PantallaCicloEnCurso.qml` | Las 3 columnas derechas de la tarjeta de parámetros son un `Repeater` sobre las entradas (icono de termómetro o manómetro según el tipo, nombre corto, valor y unidad). Sin puente, las tres de siempre. Con menos de 3 entradas, las columnas sobrantes quedan vacías. |
| QML | `Componentes/GraficaCiclo.qml` | Nueva propiedad `seriesEntradas`. Leyenda en fila (se reduce la letra si no cabe). Unidad de cada eje tomada de sus series. Acceso a datos protegido si una serie no tiene arreglo. |
| i18n | `i18n/es.json`, `i18n/en.json` | `ciclo.entrada_corta_<entrada>` (9 entradas) y `ciclo.serie_sin_registro`. |

## Pruebas
- `tests/test_o3_entradas_mostradas.py`: dominio (omisión, unidades °F/bar/psi, "—" para "No en uso", sin lectura, entradas desconocidas y `sensors` mal formado), series y conversión de la gráfica, claves i18n es/en, `GET /cycle` (selección, "No en uso", cambio tras el PUT, `io_enabled` ilegible) y `UiBridge` (cambio de programa y `/cycle` vacío).
- `tests/test_o3_entradas_mostradas_qml.py`: Preciclo y Ciclo en curso (1200×1920, offscreen). Comprueba que cargan sin avisos, que muestran las entradas con su unidad, que cambian al cambiar de programa, que una lista vacía no rompe y que la leyenda y la unidad de los ejes de la gráfica siguen a las series.

## Capturas (1200×1920, offscreen; se regeneran con `O3_CAPTURAS=<carpeta>`)
`capturas/O3_Preciclo_programa_A.png`, `O3_Preciclo_programa_B.png`, `O3_CicloEnCurso_programa_A.png`, `O3_CicloEnCurso_programa_B.png`.
- Programa A: temp. cámara, pres. chaqueta y temp. drenaje sin lectura ("—"), en °C/kPa.
- Programa B: 2 entradas, presión en bar y referencia en "No en uso" en °F.

Las capturas usan un puente simulado (sin backend).

## Decisiones
- **DECISIÓN SIN CONFIRMAR — la gráfica solo traza lo que el backend registra.** Hoy `lecturas_grafica` guarda únicamente `temp_camara`, `temp_ref` y `pres_camara`. Una entrada elegida que no sea una de esas aparece en la leyenda como "(sin registro)", sin trazo. Para trazarla habría que ampliar el registro de lecturas (`db_manager.py` y el registro del ciclo), que queda fuera de O3. Además, otra sesión está tocando `db_manager.py`. **PREGUNTA PARA CRISTIAN:** ¿se amplía el registro para guardar las entradas elegidas de cada ciclo (`planeacion_opciones.md` §3.1)?
- **DECISIÓN SIN CONFIRMAR — en psi, la gráfica usa psi absoluto (psia).** Las lecturas numéricas usan psig/inHg como el resto de la UI. En la gráfica, psig/inHg cambiarían de unidad y de signo a mitad de la curva (por ejemplo, en el prevacío).
- **DECISIÓN SIN CONFIRMAR — "No en uso" solo aplica a las sondas de temperatura con rol por programa** (`temp_camara`, `temp_2_camara`, `temp_referencia`). Las presiones y el drenaje no tienen rol por programa: muestran su lectura o "—".
- **DECISIÓN SIN CONFIRMAR — formato de las lecturas.** Ahora se usa el formato del módulo de unidades (`121.0`, sin el cero a la izquierda `085.0` del mockup antiguo), igual que el resto de valores convertidos.
- **DECISIÓN SIN CONFIRMAR — `temp_drenaje_camara`.** Existe en `io_enabled` pero no en `EstadoAutoclave`, ni en `/status`. Si se elige, se muestra siempre "—".
- Nombres cortos nuevos para la tarjeta (`ciclo.entrada_corta_*`): los de `io.ai.*` no caben en la columna.

## Cómo revertir
`git revert <sha>` del commit de O3. Los tres cambios de comportamiento, que vuelven atrás con el revert:
- el campo añadido a `GET /cycle`;
- las propiedades nuevas del puente;
- la conversión de unidades de la gráfica.

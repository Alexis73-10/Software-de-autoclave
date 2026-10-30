# Informe de Fase 3 — Menú Principal (UI QML): pantalla en arnés

Plan: `docs/mis_plans/planeacion_menu_principal_ui_qml.md` (v1.4)
Fecha: 2026-10-02
Rama: `dev`. Sin commit (D-10): falta tu confirmación visual.
Fase 4 no iniciada: `Main.qml` y la navegación real no se tocaron (D-11).

---

## 1. Verificación previa

`docs/mockups/menu_principal_v3.png` existe (1188 × 1906 px).

### 1.1 Desplazamiento del v3 respecto al marco del diseñador — corrige el plan

El plan (§5) dice que el v3 se recortó 4 px por lado y que hay que sumar 4 a sus coordenadas. **Las medidas dicen otra cosa: hay que restar 5 en x y 1 en y.** La escala es la misma.

- Encabezado: el bloque de logo, hora, campana y engranaje del v3 coincide con el de la referencia de 1196 × 1917 (`images/pantalla_ciclo_sin_grafica.png`, la de `PantallaPreciclo.qml`) con el menor error cuadrático en el desplazamiento (−5, −1). El logo mide 266 px de ancho en ambos.
- Barra inferior: la del v3 (x 39–1167, y 1747–1886, separadores en 352 y 839) desplazada (−5, −1) queda en x 34–1162 y 1746–1885 con separadores en 347 y 834, los mismos de `PantallaPreciclo.qml` (separadores 347 y 834, casa en la misma caja).
- Con +4 todo quedaría 9 px a la derecha y 5 px abajo de las otras pantallas.

Decisión: la pantalla usa el marco de 1196 × 1917 y las coordenadas del v3 menos (5, 1). Así el encabezado y la barra quedan exactamente donde están en las pantallas de preciclo y de ciclo en curso. El v3 no es un recorte simétrico de ese marco: le faltan 13 px a la derecha y 10 abajo.

Corrección para el plan, a tu criterio: en §5, reemplazar "sumar 4 a las coordenadas x e y" por "restar 5 en x y 1 en y".

---

## 2. Qué se hizo

### 2.1 Archivos

| Archivo | Tipo | Contenido |
|---|---|---|
| `src/autoclave/ui_qml/qml/Pantallas/MenuPrincipal.qml` | nuevo | La pantalla: composición, enlace a `resumen` y `puente`, señales y ventanas flotantes. Sin lógica de datos. |
| `src/autoclave/ui_qml/qml/Pruebas/PruebaMenuPrincipal.qml` | nuevo | Arnés: datos de ejemplo parecidos al mockup, o el puente real con `--backend`. |
| `src/autoclave/ui_qml/qml/Componentes/VentanaFlotante.qml` | nuevo | Ventana flotante genérica de solo visualización (§3). |
| `src/autoclave/ui_qml/qml/Componentes/TarjetaMenu.qml` | modificado (Fase 1) | Disposición interna medida sobre el v3 (§4); `iconoTenido`, `iconoIncluyeAro`, `tamIcono`, `interactiva`. |
| `src/autoclave/ui_qml/qml/Componentes/TarjetaResumen.qml` | modificado (Fase 1) | Disposición medida sobre el v3; `tamIcono`; el contenido propio ocupa toda la tarjeta. |
| `src/autoclave/ui_qml/qml/Componentes/DetalleUltimoCiclo.qml` | modificado (Fase 1) | Líneas base del v3; una sola raya si no hay fecha. |
| `src/autoclave/ui_qml/qml/Componentes/BarraInferiorMenu.qml` | modificado (Fase 1) | Iconos de Salir y casa en la posición del v3. |
| `src/autoclave/ui_qml/qml/Componentes/EncabezadoMenu.qml` | modificado (Fase 1) | Solo comentarios (`Ciclo.qml` pasó a llamarse `PantallaPreciclo.qml`). |
| `src/autoclave/ui_qml/assets/iconos/{mono,color}/ciclos_totales.svg` | modificado (Fase 1) | Icono provisional más parecido al del v3: dos flechas en círculo, sin las marcas de conteo. Sigue siendo SVG Tiny 1.2. |
| `src/autoclave/ui_qml/assets/textos/es.json` | modificado (compartido, D-22) | 26 claves nuevas en la sección `menu`. Un solo bloque propio (`@@ -5`); el otro bloque (`temp_referencia`, `@@ -39`) es del otro trabajo. |
| `src/autoclave/ui_qml/prueba_menu_principal.py` | modificado (Fase 1) | `--pantalla`, `--backend`, `--ventana`, `--sin-conexion`. |
| `tests/test_menu_principal_pantalla_qml.py` | nuevo | 13 pruebas (§7). |

No se tocaron `Main.qml`, `PantallaPreciclo.qml`, `PantallaCicloEnCurso.qml`, `BarraSuperior.qml`, `BarraInferior.qml`, `GraficaCiclo.qml`, la app PySide ni el backend.

### 2.2 Cómo verla

```
python -m autoclave.ui_qml.prueba_menu_principal --pantalla                      datos de ejemplo
python -m autoclave.ui_qml.prueba_menu_principal --pantalla --backend            datos reales (solo lectura)
python -m autoclave.ui_qml.prueba_menu_principal --pantalla --ventana ultimo_ciclo
python -m autoclave.ui_qml.prueba_menu_principal --pantalla --sin-conexion
python -m autoclave.ui_qml.prueba_menu_principal --pantalla --ancho 1080 --alto 1920
```

Capturas en `docs/informes/fase3_capturas/`:

- `menu_1196x1917.png` y `menu_9x16_1080x1920.png`
- `comparacion_v3_lado_a_lado.png` (v3 a la izquierda, ya desplazado al marco; captura a la derecha) y `comparacion_v3_superpuesta.png` (las dos mezcladas al 50 %)
- `ventana_ultimo_ciclo.png`, `ventana_mantenimiento.png`, `sin_conexion.png`

Las capturas usan los datos de ejemplo del arnés (no son lecturas reales).

### 2.3 Comportamiento

- Encabezado anclado arriba; barra inferior anclada abajo, a 32 del borde (el mismo margen que tiene en el marco de 1196 × 1917).
- Alto flexible (9:16): las tarjetas de menú no se mueven; el alto sobrante se reparte en partes iguales entre las tarjetas de menú y el resumen, y entre el resumen y la barra.
- Iniciar sesión: habilitada, solo emite `iniciarSesionPulsado` (MP-07).
- Historial, Reportes e Información: visibles y deshabilitadas (D-13, `TODO(MP-04)`).
- Tiempo adicional de secado: informativa (no responde al toque, sin flecha), muestra "—" y no lee ningún parámetro (`TODO(MP-11)`).
- Resumen: Ciclos totales y Ciclos hoy deshabilitadas hasta que definas su contenido (MP-14); Próximo mantenimiento y Último ciclo abren su ventana.
- Campana: contador de alarmas de `UiBridge.alarms.count` (D-17), sin acción.
- Engranaje, Iniciar sesión y las tarjetas solo emiten señales. Salir deshabilitado (D-12, `TODO(MP-03)`); Home inactivo.
- Sondeo del resumen: la pantalla llama a `resumen.iniciar()` al hacerse visible (consulta y sondeo cada 10 s) y a `detener()` al ocultarse o destruirse.
- Backend sin respuesta: aviso "Sin conexión con el equipo" bajo el encabezado y los datos en "—" (D-16). Diseño del aviso provisional.

---

## 3. Ventanas flotantes (D-21)

Componente genérico `VentanaFlotante.qml`, diseño PROVISIONAL (el mockup no la tiene; la valida el diseñador): fondo atenuado que cierra al tocarlo, tarjeta blanca de radio 26, título en negrita, botón de cierre redondo con una X arriba a la derecha, línea divisoria y zona de contenido. Medidas en `m()`.

No se reutilizó `PanelModal.qml` (ya existe, lo usan los paneles de notificaciones y de equipo): usa `Escala.px` en vez de `m()` (D-18) y trae un botón CERRAR fijo abajo que le quita alto a la gráfica. Quedan dos componentes parecidos; unificarlos es una deuda técnica que no se aborda aquí.

### 3.1 Último ciclo

- Datos arriba, en cuatro columnas: fecha de inicio (`DD/MM/AAAA  HH:MM`), programa (número y nombre, p. ej. "02 · Instrumental 134"), resultado (Completado, Fallo o Cancelado, con su color) y operador ("—", `TODO(MP-14b)`, D-24).
- Debajo, la gráfica con `GraficaCiclo.qml`, la misma de la pantalla de ciclo en curso, escalada al ancho de la ventana. Va en modo pantalla completa porque ese modo oculta los botones Tiempos y pantalla completa, que aquí no tienen sentido. Ese modo trae su propio botón CERRAR, que también cierra la ventana; quedan dos formas de cerrar (la X y CERRAR). No se modificó `GraficaCiclo.qml` para quitarlo.
- La curva se pide solo al abrir (`cargarGraficaUltimo()` → `GET /cycle/history/{id}/graph`); la prueba lo verifica. Sin curva (backend sin respuesta o ciclo sin lecturas) se muestra "Gráfica no disponible" sobre la gráfica vacía.

### 3.2 Próximo mantenimiento

"Fecha del último mantenimiento" y "Ciclos para el próximo mantenimiento", ambos en "—" (no hay fuente de mantenimiento, MP-14c).

---

## 4. Medidas tomadas del v3 (px del mockup, relativas a cada tarjeta)

Tarjetas de menú:

- Aro de 117 de diámetro centrado en (84, 82); trazo de 4 si es de acento (Iniciar sesión, Información, Secado) y de 2 gris (Historial, Reportes).
- Glifos: usuario 72 de alto, reportes 70, secado 63; Historial e Información usan SVG que traen su propio aro.
- Título con línea base en 219 si la descripción tiene dos líneas; descripción con líneas base en 260 y 288 (interlineado 28). Secado: título en 214 y 247 (interlineado 33), descripción en 288. Regla común: última línea de la descripción a 32 del borde inferior y última del título 41 por encima de la primera de la descripción.
- Flecha de 15 × 24, a 30 del borde derecho y centrada a 62.5 del borde inferior.
- Valor de secado: línea base en 101, a 35 del borde derecho.

Tarjetas de resumen:

- Aro de 106 centrado a 79 del borde superior; trazo de 5.
- Rótulo con la última línea en 186 (alineado por abajo, interlineado 27); valor en 258; subrótulo en 303.
- Último ciclo: fecha en 231, "Programa:" en 280 y "Resultado:" en 303.

Títulos: casa de contorno de 57 × 57 en (567, 262) del marco; "MENÚ PRINCIPAL" con línea base en 390 y "RESUMEN DEL SISTEMA" en 1244, ambos semibold 39 en blanco.

Verificación sobre la captura superpuesta: títulos, descripciones, flechas, aros, valores y la barra coinciden al píxel o con 1 px de diferencia. Ajustes hechos al medir:

- Fecha de Último ciclo: medía 184 de ancho frente a 159 del v3. La causa eran las cifras tabulares (`tnum`); sin ellas mide 157.
- Valores grandes ("1248"): 118 frente a 105 por la misma causa; sin `tnum`, 103. Se quitaron las cifras tabulares de los valores de las tarjetas. Diferencia con el estilo `kpi_valor` de `Tipografia.qml`, que las pide; el v3 no las usa.

---

## 5. Diferencias intencionales con el v3

| Elemento | v3 | Pantalla | Motivo |
|---|---|---|---|
| Historial, Reportes, Información | normales | atenuadas y deshabilitadas | D-13 (no existen sus pantallas) |
| Ciclos totales, Ciclos hoy | normales | atenuadas y deshabilitadas | MP-14 (contenido de su ventana sin definir) |
| Tiempo adicional de secado | "10 min" | "—" | MP-11 (parámetro nuevo aún no existe) |
| Próximo mantenimiento | "15 días" / "Completados" | "—", sin subrótulo | MP-06b (sin fuente); el subrótulo del v3 no aplica a mantenimiento |
| Subrótulo de Ciclos totales y Ciclos hoy | "Completados" | "Realizados" | D-15 |
| Último ciclo, rótulo | "ULTIMO CICLO" | "ÚLTIMO CICLO" | ortografía |
| Último ciclo, programa | "Ciclo" | número de programa ("02") | §6.3 (número, no solo nombre) |
| Último ciclo, resultado | "Exitoso" | "Completado" | §6.3: estados reales COMPLETADO / FALLO / CANCELADO |
| Fecha y hora | 16:00, 12 oct 2026 | reloj del equipo | dato en vivo |
| Icono de ciclos totales | flechas de sincronizar | icono provisional parecido | MP-08 (pendiente del diseñador) |
| Icono de casa del título | contorno | contorno dibujado con Shape | no hay casa de contorno en assets |
| Aviso sin conexión | no existe | píldora blanca bajo el encabezado | D-16, provisional |
| Ventanas flotantes | no existen | §3 | D-21, provisionales |
| Colores de FALLO y CANCELADO | no aparecen | `peligroTexto` y `advertenciaTexto` | provisionales; no son colores de alarma (IEC 60601-1-8) |
| Glifos de usuario y secado | dibujos del v3 | SVG del paquete del diseñador | diferencias menores de forma |

---

## 6. Paso 3 — Tamaño de la respuesta de `/cycle/history/{id}/graph`

Medido con `TestClient` sobre una base de datos temporal, una lectura por segundo (como `CycleLogger`), cinco repeticiones por caso. Sin cambios en el endpoint.

| Ciclo | Lecturas | Respuesta JSON | Comprimida (gzip, referencia) | Tiempo en el backend (mediana / máximo) |
|---|---|---|---|---|
| 40 min | 2 400 | 345 KiB | 26 KiB | 37 / 73 ms |
| 60 min | 3 600 | 528 KiB | 37 KiB | 52 / 54 ms |
| 90 min | 5 400 | 799 KiB | 52 KiB | 75 / 82 ms |
| 120 min | 7 200 | 1 065 KiB | 66 KiB | 100 / 103 ms |
| 180 min | 10 800 | 1 607 KiB | 99 KiB | 151 / 161 ms |

Del lado de la UI (decodificar el JSON y pasarlo por `AcumuladorGrafica`): 11 ms a 60 min, 19 ms a 120 min y 28 ms a 180 min.

Unos 150 bytes por lectura; crece lineal con la duración. Medido en el PC de desarrollo. Observaciones, sin cambiar nada:

- `BackendClient` corta a los 0.8 s. A 180 min el backend tarda unos 0.15 s en este PC; en el PC del autoclave, más lento, el margen es menor y no está medido.
- El backend no comprime las respuestas; con gzip bajarían unas 16 veces.
- Si hiciera falta, las opciones serían decimar en el backend (la gráfica ya decima al dibujar) o comprimir. No se aplicó ninguna.

---

## 7. Pruebas

`tests/test_menu_principal_pantalla_qml.py` (13): carga real del arnés offscreen con el puente `ResumenSistema` real y un backend simulado, a 1196 × 1917, a 1080 × 1920 y con el backend sin respuesta.

- Cero avisos del motor QML en los tres casos.
- La pantalla activa el sondeo del resumen.
- Estados de las nueve tarjetas (D-13, MP-14) y secado no interactiva.
- Las nueve tarjetas y la barra en las coordenadas del v3 desplazadas al marco.
- 9:16: barra pegada abajo, tarjetas de menú fijas, resumen desplazado la mitad del sobrante y sin solaparse con la barra.
- Datos del resumen en pantalla; "—" en mantenimiento y secado; sin aviso con conexión.
- Sin conexión: aviso visible, "—" en los datos y "Gráfica no disponible" en la ventana.
- Señales: Iniciar sesión y engranaje emiten; Historial (deshabilitada) no.
- Ventana de Último ciclo: Ciclos hoy (deshabilitada) no abre nada; la curva no se pide antes de abrir y sí al abrir; datos, operador "—" y cierre con la X.
- Ventana de mantenimiento con dos "—".
- `es.json` trae todas las claves que usa la pantalla.
- Los marcadores `TODO(MP-11)`, `TODO(MP-14b)`, `TODO(MP-03)`, `TODO(MP-04)` y `TODO(MP-06a)` están en el código.

Estas pruebas se escribieron después de la pantalla (no se vieron fallar antes). Para comprobar que detectan errores se rompió la pantalla a propósito (Historial habilitada y la curva sin pedir al abrir): fallaron tres pruebas; luego se restauró el archivo.

Las pruebas de la galería de la Fase 1 siguen pasando con los componentes ajustados.

Suite completa (`python -m pytest`, 2026-10-02): **1552 passed**, 0 fallos (6 avisos de deprecación preexistentes en `test_storage.py`).

---

## 8. Commit (D-19 y D-22), cuando lo confirmes

- Todos los archivos nuevos de las Fases 1, 2 y 3, `Colores.qml` y `docs/informes/`.
- `es.json`: solo el bloque `@@ -5` (sección `menu`); el bloque de `temp_referencia` es del otro trabajo.
- `server.py`: los dos bloques de la Fase 2. `db_manager.py`: solo el bloque de `get_resumen_ciclos`.
- Quedan fuera los demás archivos modificados por otros trabajos.

---

## 9. Pendientes

De Cristian:

- Confirmación visual de la pantalla y de las ventanas flotantes.
- Corregir en el plan el desplazamiento del v3 (§1.1).
- MP-14: contenido de las ventanas de Ciclos totales y Ciclos hoy.
- D-23 pide confirmar la fecha de inicio en Último ciclo: la confirmaste en el chat el 2026-10-02 ("la de inicio").

Del diseñador:

- Ventana flotante, aviso sin conexión, estados presionado y deshabilitado.
- Icono definitivo de ciclos totales y casa de contorno del título.
- Colores de FALLO y CANCELADO en Último ciclo.

`TODO` de este trabajo en el código: `TODO(MP-11)`, `TODO(MP-14b)`, `TODO(MP-03)`, `TODO(MP-04)` y `TODO(MP-06a)` en `MenuPrincipal.qml`; `TODO(MP-06a)` en `server.py` y `db_manager.py`; `TODO(MP-11)` en `bridge/resumen_sistema.py`.

---

## 10. Anexo (2026-10-02): ajustes tras la revisión visual y conexión a la navegación

Cristian aprobó la pantalla con un cambio y autorizó conectarla.

### 10.1 Sin engranaje en el menú

Se quitó el engranaje de la esquina superior derecha del menú (`EncabezadoMenu.qml`) y la señal `ajustesPulsado` de `MenuPrincipal.qml`. El encabezado queda con logo, hora, fecha y campana. Las capturas de `docs/informes/fase3_capturas/` se regeneraron sin él.

### 10.2 Conexión en `Main.qml`

- El engranaje de la pantalla de preciclo y el de la pantalla de ciclo en curso abren el Menú Principal (antes abrían la configuración PySide).
- La casa de la barra inferior del menú queda activa y regresa a la pantalla desde la que se abrió.
- Iniciar sesión abre la configuración PySide, que contiene el login (MP-07). Es el único acceso a la configuración que queda desde la UI QML ahora que el engranaje abre el menú.
- `app.py` crea el puente `ResumenSistema` y lo pasa a `Main.qml` como `resumen`. El menú consulta el resumen al mostrarse, lo sondea cada 10 s mientras está visible y lo detiene al cerrarse; al salir de la app también se detiene.
- Archivos tocados: `Main.qml` y `app.py` (sin cambios ajenos pendientes al editarlos), `EncabezadoMenu.qml`, `MenuPrincipal.qml`, `PruebaMenuPrincipal.qml`. No se tocaron `PantallaPreciclo.qml` ni `PantallaCicloEnCurso.qml` (tienen cambios del otro trabajo): sus comentarios todavía dicen que el engranaje abre la configuración.

### 10.3 Ciclo en curso (MP-02)

El menú puede abrirse durante un ciclo, desde el engranaje de la pantalla de ciclo en curso, y mientras está abierto la tapa. Mitigaciones que quedan:

- La casa del menú regresa a la pantalla de ciclo en curso.
- Si la máquina cambia de estado (entra o sale de CICLO) con el menú abierto, `aplicarEstadoMaquina()` de `Main.qml` vacía la pila y muestra la pantalla principal que corresponda.

No hay regreso automático por tiempo. Si se quiere, iría en un plan aparte.

### 10.4 Pruebas

- `tests/test_main_menu_principal_qml.py` (2, escrita antes de conectar y vista fallar): con la máquina en PREPARADO y en CICLO, el engranaje abre el menú sin lanzar la configuración PySide; el menú no tiene engranaje; el resumen se sondea; la casa está activa; Iniciar sesión lanza la configuración; la casa cierra el menú, vuelve a la pantalla de origen y detiene el sondeo; cero avisos QML.
- `tests/test_menu_principal_pantalla_qml.py`: la prueba de señales ahora comprueba que no hay engranaje.

Suite completa (`python -m pytest`, 2026-10-02): **1554 passed**, 0 fallos.

### 10.5 Commit

Además de lo listado en §8: `Main.qml` y `app.py` completos (todos sus cambios son de este trabajo) y `tests/test_main_menu_principal_qml.py`.

---

## 11. Anexo (2026-10-02): revisión funcional de Cristian

### 11.1 Campana

Abre el panel de notificaciones, el mismo de `PantallaPreciclo.qml` (`PanelNotificaciones`, alarmas activas de `UiBridge.alarms`). Antes no tenía acción (D-17); ahora `EncabezadoMenu` emite `campanaPulsada` en la misma zona táctil que la campana de preciclo.

### 11.2 Información

Habilitada (deja D-13 para esta tarjeta). Abre el panel de información del equipo, el mismo que abre el recuadro de modelo y serie de la esquina inferior izquierda de preciclo (`PanelEquipo` con `InfoEquipo.filas`), y pide actualizar sus datos (`InfoEquipo.actualizar()`). `Main.qml` pasa `infoEquipo` al menú. Historial y Reportes siguen deshabilitadas.

### 11.3 Último ciclo sin datos — dos causas

1. **El backend en marcha (puerto 8000) es anterior a la Fase 2.** `GET /cycle/summary` responde 404, el puente lo toma como "sin respuesta" y la pantalla muestra "—" y el aviso de sin conexión. Se resuelve reiniciando el backend; no se reinició desde aquí.
2. **Error de la Fase 2, corregido.** `ciclos.resultado` no guarda solo COMPLETADO, FALLO o CANCELADO, sino la fase con que terminó el ciclo. Valores reales en la base: CANCELADO (41), FALLO_ESTERILIZACION (9), FALLO_CONEXION (7), COMPLETADO (6), sin resultado (6), EMERGENCIA (3), FALLO_SUMINISTRO (2), FALLO_PUERTA_1_ABIERTA (2), FALLO_CALENTAMIENTO (2), FALLO_SECADO (1). El formateador solo aceptaba los tres primeros nombres, así que el último ciclo real (`FALLO_CALENTAMIENTO`) salía como "—". Ahora usa la misma regla del backend (`progreso_ciclo.resultado`): COMPLETADO → Completado, CANCELADO → Cancelado, cualquier otro cierre → Fallo. El código original se conserva como detalle (`ultimoResultadoDetalle`) y la ventana de Último ciclo lo muestra en pequeño bajo el resultado.

Con la base real, al reiniciar el backend el resumen muestra: 79 ciclos totales, 0 hoy, último ciclo el 06/08/2026 a las 11:20, programa 02 (Instrumental 134), resultado Fallo (FALLO_CALENTAMIENTO). Ese ciclo es anterior a la tabla `lecturas_grafica`, así que su ventana dice "Gráfica no disponible"; los ciclos nuevos sí tendrán curva.

### 11.4 Iniciar sesión

Abre el login QML (`Login.qml`, en la pila de `Main.qml`); la casa del login regresa al menú. Ya no abre la configuración PySide. Consecuencia: **desde la UI QML no queda ningún acceso a la configuración PySide** (antes lo daba el engranaje). Hay que definir dónde va cuando el login QML autentique.

### 11.5 Pruebas

Escritas antes del cambio y vistas fallar:

- `tests/test_resumen_sistema_dominio.py`: resultados reales de la base (FALLO_*, EMERGENCIA, SENSOR_AUSENTE), fases en curso, detalle.
- `tests/test_menu_principal_pantalla_qml.py`: Información habilitada abre el panel del equipo y lo actualiza; la campana abre las notificaciones; un FALLO_CALENTAMIENTO se ve como "Fallo" con su detalle en la ventana.
- `tests/test_main_menu_principal_qml.py`: Iniciar sesión abre el login QML sin lanzar PySide y su casa vuelve al menú.

El arnés usa ahora un `ListModel` con dos alarmas de ejemplo (el falso anterior solo tenía `count` y el panel de notificaciones no podía mostrarlo).

Suite completa (`python -m pytest`, 2026-10-02): **1570 passed**, 0 fallos.

---

## 12. Anexo (2026-10-02): Ciclos totales, Ciclos hoy e Historial

Pedido de Cristian. Reemplaza lo dicho sobre estas tres tarjetas en §2.3 y §5 (antes deshabilitadas).

### 12.1 Comportamiento

- **Ciclos totales:** solo informativa. Se ve normal (sin atenuar), pero no es botón: no se ve presionada, no emite señal ni abre nada. `TarjetaResumen` tiene ahora `interactiva` (igual que `TarjetaMenu`).
- **Ciclos hoy:** habilitada. Abre la ventana "CICLOS DE HOY" con el listado de los ciclos terminados desde las 00:00 (los mismos que cuenta la tarjeta), del más reciente al más antiguo: Ciclo, Fecha, Hora, Programa y Resultado (con su color). Al tocar una fila, la ventana pasa a "CICLO N" con los datos y la gráfica de ese ciclo (la curva se pide en ese momento) y un botón "Volver al listado".
- **Historial:** habilitada. Abre la ventana "HISTORIAL", solo para ver el listado (las filas no se pueden elegir), con filtro Diario / Semanal / Mensual. Al abrir muestra Diario.
- Mensajes del listado: "Cargando…", "Sin conexión con el equipo" o "No hay ciclos en este periodo". Si hay más de 500 ciclos en el periodo se muestran los 500 más recientes con la nota "Se muestran solo los ciclos más recientes".
- Reportes sigue deshabilitada (`TODO(MP-04)`).

### 12.2 Decisiones

- **Periodos del historial:** Diario = desde las 00:00 de hoy; Semanal = últimos 7 días (hoy y los 6 anteriores); Mensual = últimos 30 días. Se eligió un periodo móvil en vez de la semana o el mes del calendario porque un lunes temprano o el día 1 la vista de calendario quedaría casi vacía. Se cambia en un solo lugar (`_DIAS_PERIODO` en `server.py`).
- **Criterio de cada listado:** Ciclos hoy cuenta y lista los terminados (por fecha de fin), igual que el número de la tarjeta. El historial lista por fecha de inicio, para que también aparezcan los ciclos interrumpidos (sin fecha de fin), que importan para la trazabilidad.
- **Detalle del ciclo:** la vista de datos y gráfica de la ventana de Último ciclo se separó en el componente `DetalleCiclo.qml`, que ahora usan Último ciclo y el ciclo elegido en Ciclos hoy.

### 12.3 Archivos

| Archivo | Tipo | Contenido |
|---|---|---|
| `src/autoclave/backend/server.py` | compartido (D-22) | `GET /cycle/list?periodo=dia\|semana\|mes&terminados=…&limite=…` (solo lectura) y `_inicio_del_periodo`; el armado de cada ciclo pasa a `_ciclo_json`, que también usa `/cycle/summary`. |
| `src/autoclave/services/domain/logging/db_manager.py` | compartido (D-22) | `get_ciclos_desde(desde, terminados, limite)`, solo lectura. |
| `src/autoclave/ui_qml/domain/resumen_sistema.py` | modificado | `ciclo_presentable` y `lista_presentable`. |
| `src/autoclave/ui_qml/bridge/ciclos_historial.py` | nuevo | Puente `CiclosHistorial`: listado por periodo y curva del ciclo elegido, bajo demanda; descarta respuestas que llegan tarde. |
| `src/autoclave/ui_qml/qml/Componentes/DetalleCiclo.qml` | nuevo | Datos y gráfica de un ciclo. |
| `src/autoclave/ui_qml/qml/Componentes/ListaCiclos.qml` | nuevo | Listado con encabezado; filas seleccionables o no. |
| `src/autoclave/ui_qml/qml/Componentes/TarjetaResumen.qml` | modificado | `interactiva`. |
| `src/autoclave/ui_qml/qml/Pantallas/MenuPrincipal.qml` | modificado | Ventanas de Ciclos hoy e Historial; estados de las tarjetas. |
| `src/autoclave/ui_qml/qml/Main.qml`, `app.py`, `Pruebas/PruebaMenuPrincipal.qml`, `prueba_menu_principal.py` | modificados | Crean y pasan `historial`; el arnés trae un listado de ejemplo; `--ventana ciclos_hoy` y `--ventana historial`. |
| `src/autoclave/ui_qml/assets/textos/es.json` | compartido (D-22) | 16 claves más en la sección `menu`, dentro del mismo bloque propio. |

### 12.4 Pruebas

- `tests/test_backend_cycle_summary.py` (+9): listado por inicio con interrumpidos; terminados por fin, igual que el conteo de hoy; límite; inicio de cada periodo; endpoint con forma de cada ciclo, `truncado` y periodo inválido (422). Vistas fallar antes de implementar.
- `tests/test_resumen_sistema_dominio.py` (+7): formateo de un ciclo y del listado, filas mal formadas, sin respuesta. Vistas fallar antes.
- `tests/test_ciclos_historial_puente.py` (11, nuevo): consulta por periodo, periodo inválido, sin conexión, pedidos superpuestos, curva de un ciclo, limpiar, respuesta tardía descartada. Vistas fallar antes.
- `tests/test_menu_principal_pantalla_qml.py` (+3, otras ajustadas): Ciclos totales informativa; Ciclos hoy pide los terminados de hoy, muestra el listado, abre el detalle del ciclo tocado con su curva y vuelve al listado; Historial pide Diario, Semanal y Mensual por inicio y no permite elegir filas. Se escribieron después de la pantalla; se comprobó que detectan errores rompiendo a propósito el criterio de Ciclos hoy y la selección del historial (fallaron dos pruebas; luego se restauró el archivo).

Suite completa (`python -m pytest`, 2026-10-02): **1600 passed**, 0 fallos.

Capturas nuevas en `docs/informes/fase3_capturas/`: `ventana_ciclos_hoy.png` y `ventana_historial.png` (datos de ejemplo). Para ver el detalle de un ciclo, abrir el arnés con `--ventana ciclos_hoy` y tocar una fila.

Recordatorio: el backend en marcha debe reiniciarse para que existan `/cycle/summary` y `/cycle/list`.

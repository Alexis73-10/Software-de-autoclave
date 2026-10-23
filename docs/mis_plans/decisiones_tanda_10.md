# Decisiones para la tanda 10 (aprobadas, 23-oct-2026 10:40)

Fuente: observaciones de Cristian en el equipo de pruebas (23-oct) y sus respuestas a las preguntas del asistente. Parte de `dev` con la tanda 9 unida (748337a).

## D10-1. Textos que no caben: abreviatura automática (revierte en parte D8-5.4)
Cristian aclara (23-oct): la regla «sin abreviaturas» de la tanda 8 era demasiado amplia. **Lo que no quepa en su cuadro se abrevia; lo que quepa se muestra completo.**
- **D10-1.1 Mecanismo:** un componente QML reutilizable (en `Componentes/`) que recibe el texto completo, el abreviado y el ancho disponible; mide el completo (`TextMetrics` o `implicitWidth`) y muestra el abreviado solo si el completo no cabe. Sigue prohibido recortar con puntos suspensivos (`elide`) o cortar en silencio (`maximumLineCount`). Si ni el abreviado cabe, eso es un error que debe detectar la prueba de D10-1.5, no un recorte.
- **D10-1.2 Catálogo:** las abreviaturas viven solo en claves propias (p. ej. `<seccion>.<clave>_abrev` o una sección `abrev.*`, a elección de Code, una sola convención), con su clave completa correspondiente en es y en. `test_v8b_textos.py` las exenta de la regla de abreviaturas, como `ticket_ciclo.*`, y exige que toda abreviatura tenga su texto completo. Fuera de esas claves la regla D8-5.4 sigue igual.
- **D10-1.3 Primero Ciclo y Preciclo:** tarjeta de parámetros y sensores de `PantallaPreciclo.qml` y `PantallaCicloEnCurso.qml` (`ciclo.temp_ester`, `tiempo_est`, `tiempo_sec` y todas las `ciclo.entrada_corta_*`). Ancho disponible = desde el `lx` de la etiqueta hasta el divisor derecho de su columna (222.2, 410.3, 598.5, `c0 + 188.2`), menos un margen. Abreviaturas sugeridas (Code ajusta a lo que quepa): es «Temp. ester.», «Tiempo ester.», «Tiempo secado», «Temp. cámara», «Temp. cámara 2», «Temp. ref.», «Temp. drenaje», «Temp. dren. cámara», «Presión», «Pres. chaqueta», «Pres. empaque 1/2»; en «Steril. temp.», «Steril. time», «Drying time», «Chamber temp.», «Ref. temp.», «Drain temp.», «Jacket press.», «Gasket press. 1/2».
- **D10-1.4 Barrido de todas las pantallas:** con el banco de capturas (D9-13.5) en es y en, en la resolución real de las pantallas del equipo, se revisa todo texto dentro de un cuadro (tarjetas, botones, filas, encabezados, barra inferior, campana, Opciones). Lo que se salga se abrevia con D10-1.1. Incluye lo visto en las capturas de la tanda 9: el motivo largo de CIC-10 cortado en la tarjeta de alarmas de Preciclo y las filas de alarma de Preciclo en español con la interfaz en inglés (estas se traducen, no se abrevian).
- **D10-1.5 Prueba automática:** una prueba QML (offscreen) que cargue cada pantalla en es y en, con textos de longitud real, y falle si un texto visible dentro de un cuadro tiene `implicitWidth` mayor que su ancho disponible (o se sale del cuadro que lo contiene). El informe lista cada texto que se abrevió, el completo, el abreviado y la pantalla.

## D10-2. Código de activación rechazado aunque coincide (bug)
Caso real (23-oct): serie `SN128745`, el generador mostró `FR4QAXQ3O43N` (letra O) y Cristian escribió `FR4QAXQ3043N` (cero), porque la fuente del generador no distingue la O del 0. El asistente respondió «Código de activación incorrecto o expirado».
- **D10-2.1:** `src/autoclave/installation/activation.py` normaliza el código antes de comparar (un solo punto, para el código de instalación y la clave de fábrica): mayúsculas, sin espacios ni guiones, y `0→O`, `1→I`, `8→B` (Base32 no usa 0, 1, 8 ni 9, así que no hay ambigüedad ni se debilita el código). Prueba con el caso real: `SN128745`, 2026-10-23, `FR4QAXQ3043N` es válido; un código de otro día sigue siendo inválido.
- **D10-2.2:** el generador (`tools/generador/app.py`) muestra los códigos en una fuente monoespaciada que distinga O de 0 (p. ej. `Consolas, "Cascadia Mono", monospace`). No cambia el formato ni el algoritmo del código.

## D10-3. Estado seguro sin sensor de presión de cámara: solo el mensaje
Cristian confirma que es requisito: sin, como mínimo, el sensor de presión de cámara, el equipo no puede llevar la cámara a estado seguro. **El comportamiento de D9-1.4 se conserva** (el protocolo se detiene con CIC-10 + SEN-06, NO ABRIR, sin bloquear login, modo prueba, cambio de programa ni apagado).
- Lo que cambia es el texto: hoy la acción de CIC-10 dice «Revise la sonda Principal…» aunque la causa sea la presión. Cuando la causa es la falta de presión de cámara, motivo y acción dicen que **sin el sensor de presión de cámara no se puede llevar la cámara a estado seguro** y piden revisar la conexión del sensor de presión de cámara o llamar a servicio técnico (es y en). Con la causa de sonda Principal se conserva el texto actual.
- Sin cambios de lógica de seguridad (no es ★). Caso nuevo en la hoja de banco: arranque sin sensor de presión → texto correcto en la tarjeta de Preciclo y en la campana.

## D10-4. Pantalla 2 durante la instalación
Hoy, sin perfil, la puerta 1 abre el asistente y la puerta 2 sigue al menú, donde el arranque informa ARR_PERFIL.
- **D10-4.1:** mientras la puerta 1 esté en el asistente de instalación, la puerta 2 muestra la pantalla de **Reposo** (logo y reloj) con el aviso «Instalación en curso en la pantalla 1» / «Installation in progress on screen 1». No responde al toque ni necesita backend.
- **D10-4.2:** al terminar la instalación, la puerta 2 pasa sola al flujo normal, con el mismo mecanismo con que lo hace la puerta 1 (revisar `app.py`, `doble_pantalla.py` y `CODIGO_INSTALACION_TERMINADA`; sin relanzamientos contados como caída). Un equipo de una sola pantalla no cambia.
- Pruebas: arranque sin perfil con dos pantallas (la 2 en Reposo con el aviso), fin de la instalación (la 2 llega al menú) y perfil válido (sin cambios).

## D10-5. Compilación E
Al final, con `dev` en verde: compilación E con su Setup (`Autoclave_Setup_1.0.0-e.exe`), igual que K9: etiqueta `inst-<fecha>-e`, `entrega/<fecha>_e/` y `usb/`, sección del LEEME «Actualizar D → E» sin copias a mano, casilla de estación desmarcada en el equipo de pruebas (K9-1). Incluye D9-12 y lo de la tanda 10. El generador de códigos se recompila (D10-2.2) y queda en `entrega/<fecha>_e/` fuera de `usb/`.

## No entran
Las preguntas abiertas de la tanda 9 (S9-18, S9-10, P9-1, X9-1 y las demás) y las arrastradas de la tanda 8: siguen en el índice de la tanda 9.

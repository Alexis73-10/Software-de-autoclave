# Paleta del modo oscuro — fuente única para `Tema/Colores.qml`

Aprobada por Cristian el 02-nov-2026 a partir del mockup de esta carpeta (`01_…05_*.png` / `*.html`).
Cada propiedad existente de `src/autoclave/ui_qml/qml/Tema/Colores.qml` conserva su nombre y su valor claro; este archivo fija su valor oscuro. Las propiedades nuevas (sección 6) solo existen porque el modo oscuro las necesita.

Regla: en modo claro todo queda idéntico a hoy. Ningún valor de este archivo se escribe a mano fuera de `Tema/`.

## 1. Fondos oscuros / chrome

- `fondoMarinoOscuro` — claro #1B222A → oscuro #090E14
- `fondoBarraSuperior` — claro #2C4B70 → oscuro #1A3150
- `fondoAzulMedio` — claro #2E597C → oscuro #0F1B2A
- `fondoCieloNucleo` — claro #5C97DB → oscuro #1B3352 (halo de reposo/arranque)
- `fondoCieloClaro` — claro #99C5E2 → oscuro #8FB2E0
- `textoFechaReposo` — claro #C7DCFD → oscuro #8FB2E0
- Fondo de la aplicación (FondoApp): en oscuro NO se usa `fondo-arranque.png`; se dibuja un gradiente radial centrado en (70 %, 0 %), 120 % × 60 %: #1A3150 en 0 %, #0F1B2A en 45 %, #090E14 en 100 %. Reposo: radial centrado (50 %, 42 %), 70 % × 45 %: #1B3352 → #0F1B2A (55 %) → #070B10.

## 2. Acción

- `accionPrimario` — #1168F6 → #4A8CFF
- `accionPrimarioTexto` — #0D53C4 → #6EA4FF
- `accionFondoTenue` — #E2ECFD → #16305E (tecla presionada / seleccionado; borde #3B6FD8)
- Botón ABRIR PUERTA (oscuro): relleno #16305E, borde #3B6FD8, texto/ícono #E9EEF4.

## 3. Peligro y advertencia (no son alarma)

- `peligroFondo` — #FFECEC → #3A1416
- `peligroTexto` — #D00000 → #FF6B6B
- `advertenciaFondo` — #FFF4E6 → #3A2610
- `advertencia` — #FF9933 → #FF9F3A
- `advertenciaTexto` — #B35A00 → #FFAE5C
- Botón CANCELAR CICLO (oscuro): gradiente vertical #D71A1A → #A30F0F, borde #FF5A5A, texto #FFFFFF.

## 4. Alarmas IEC 60601-1-8 — SIN CAMBIO en ningún modo

- `alarmaAlta` #EE0000 · `alarmaMedia` #FFCC00 · `alarmaBaja` #00CCFF
- La insignia de la campana usa #00CCFF con número #031225 en ambos modos.
- Las filas de alarma en oscuro: fondo #1E2A38, barra lateral del color de la alarma (8 px), texto #E9EEF4.

## 5. Acentos del menú, neutros y texto

- `menuVerde` — #009535 → #34C46A
- `menuVerdeTexto` — #0D8C2C → #4FD27F
- `menuAzul` — #0361EC → #4A8CFF
- `menuNaranja` — #FF9720 → #FF9F3A
- `menuNaranjaTexto` — #F26500 → #FFAE5C
- `menuMorado` — #9827D1 → #B46CF2
- `bordeDivisor` — #E6E6E6 → #2A3746
- `textoPrimario` — #031225 → #E9EEF4
- `textoSecundario` — #4D4D4D → #A7B3C1
- `textoGuia` — #808080 → #8C98A7
- `bordeCampo` — #CCCCCC → #33445A
- `fondoSutil` — #F6F6F6 → #18222F (paneles internos: sensores, gráfica, alarmas)
- `fondoTarjeta` — #FFFFFF → #152130 (tarjetas del menú y resumen; panel principal de Preciclo/Ciclo #131C27)
- `iconoBarraInferior` — #333333 → #E9EEF4
- Iconos con círculo del menú en oscuro: círculo con relleno del acento al 10 % y borde #2E3D50 (Iniciar sesión: borde 2 px #34C46A y halo del 10 %).

## 6. Propiedades nuevas (solo si hacen falta; en claro valen lo que se usa hoy)

- `fondoPanel` — oscuro #131C27 (panel grande de Preciclo / Ciclo en curso / barras superior-inferior)
- `fondoElevado` — oscuro #1E2A38 (filas, botones secundarios, desplegables, avatar)
- `fondoPista` — oscuro #243242 (barra de avance vacía, línea de fases pendiente #2A3746)
- `bordeTarjeta` — oscuro #263445
- `estadoEjecucion` — oscuro #2BD3A8 (texto «En ejecución»); círculo #1B9C7E
- Fases (BarraFases / CirculoFaseLiquido / ConectorFase): completada gradiente #1E5FD9 → #0E7A9A; activa llenado #1E5FD9 con aro #33B4F5 al 35 %; pendiente fondo #222E3C, borde #33445A, ícono #6B7889, etiqueta #7F8B99; etiqueta activa #6EC8FF; conector completado #1E5FD9 → #33B4F5.
- Vapor y burbuja de las fases (tanda 34, VAP-01/VAP-04; reemplazan a `faseChorro`, retirada; DECISIÓN SIN CONFIRMAR):
- `faseVapor` — #42FFFFFF → #42DCF0FF
- `faseVaporFondo` — #8CF6FBFF → #42DCF0FF
- `faseBurbujaBorde` — #8CFFFFFF → #8CDCF0FF
- `faseBurbujaRelleno` — #24FFFFFF → #24DCF0FF
- Barra de avance del ciclo: #1E5FD9 → #33B4F5 sobre `fondoPista`.
- Gráfica: cámara #5B9BFF, referencia #B06BF0, presión #22D3B0; rejilla #2A3746; ejes y líneas de fase #3A4A5E; texto de ejes #8C98A7; recuadro del cursor #0F1721 borde #33445A.
- `graficaZoomIcono` — #3A6FD8 → #5B9BFF (ícono de zoom de la gráfica, ZOM-07, tanda 34; DECISIÓN SIN CONFIRMAR; contraste ≥ 3:1 sobre `fondoTarjeta`)
- Valores de sensores en oscuro (tira de 6): temperatura de cámara #8AB6FF, referencia #CFA2F7, presión #5EE3C2; parámetros del programa en `textoPrimario`; unidades en `textoSecundario`.

## 7. Deslizador de inicio (AJ-01) y éxito

- `deslizadorPista` — #E9F8EE → #12301F (borde #1F5A36)
- `deslizadorPistaListo` — #D3F1DD → #18402A
- `deslizadorAcento` — #2DBE66 → #2DBE66
- `deslizadorAcentoListo` — #5ED68C → #5ED68C
- `deslizadorBrillo` — #BDEBCB → #2DBE66 al 45 % (sombra/halo)
- `deslizadorBrilloListo` — #DDF7E5 → #5ED68C al 45 %
- `deslizadorTexto` — #007A29 → #5ED68C
- `deslizadorSombraInterior` — #007A29 → #000000 (al 12 %)
- `deslizadorNucleo` — #009933 → #2DBE66
- `deslizadorManija` — #009933 → #12301F (fondo de la manija; oscuro = la pista, como en el tema oscuro previo a la unión)
- `deslizadorManijaListo` — #009933 → #18402A
- `exitoFondo` — #E9F8EE → #12301F

### Deslizador de CANCELAR (CAN-01, tanda 34; DECISIÓN SIN CONFIRMAR)

Rojo paralelo al verde; comparte las magnitudes `deslizadorBordeAlfa`, `deslizadorSombraOpacidad` y `deslizadorTextoAcento`.

- `deslizadorCancelarPista` — #FBEAEA → #301212
- `deslizadorCancelarPistaListo` — #F5D0D0 → #401818
- `deslizadorCancelarAcento` — #E03A3A → #E04848
- `deslizadorCancelarAcentoListo` — #F26060 → #FF6B6B
- `deslizadorCancelarBrillo` — #F2BFBF → #E04848 al 45 % (sombra/halo)
- `deslizadorCancelarBrilloListo` — #F9DADA → #FF6B6B al 45 %
- `deslizadorCancelarTexto` — #B00010 → #FF8A8A
- `deslizadorCancelarSombraInterior` — #B00010 → #000000 (al 12 %)
- `deslizadorCancelarNucleo` — #D10A0A → #D94040
- `deslizadorCancelarManija` — #D10A0A → #301212 (oscuro = la pista, como el verde)
- `deslizadorCancelarManijaListo` — #D10A0A → #401818

## 8. Contraste mínimo (verificar con script)

Texto normal ≥ 4,5:1 y texto ≥ 24 px de diseño o íconos ≥ 3:1 contra su fondo real. Pares a comprobar como mínimo: `textoPrimario`, `textoSecundario` y `textoGuia` sobre `fondoTarjeta`, `fondoSutil`, `fondoPanel` y `fondoElevado`; cada acento de texto sobre `fondoTarjeta`; las tres alarmas sobre `fondoElevado`. Si un par no cumple, se ajusta el tono oscuro (no el claro) y se anota aquí.

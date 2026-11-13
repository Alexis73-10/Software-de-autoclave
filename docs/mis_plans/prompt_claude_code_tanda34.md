# Tanda 34: Vapor en la barra de fases (VAP), zoom de la gráfica (ZOM), deslizador de cancelar (CAN) y mensaje de espera (ESP) (8-nov-2026)

Responde e informa SOLO en español. Prioridad: cambio mínimo, solo interfaz (QML, `grafica_ejes.mjs`, `ui_qml/domain`, i18n, `Tema/Colores.qml`, íconos, pruebas y documentos). No se toca backend, lazo de control, `progreso_ciclo` ni la lógica del nivel. Máximo 4 subagentes a la vez, sin suite completa en los subagentes; revisor de seguridad solo para CAN (cambia la confirmación de la cancelación); para lo demás basta la verificación de HAZ-LLF-01 del cierre. Decisiones de Cristian: todas las de este documento (8-nov), salvo las marcadas `DECISIÓN SIN CONFIRMAR`. Ante ambigüedad, lo más simple y `DECISIÓN SIN CONFIRMAR` en el informe.

## Requisito previo
- La tanda 33 ya está liberada y unida a `dev` (merge `eea169d3`, CERRADO `b05080f4`). Parte de `dev` tal como está; no toques la rama `tanda33`.
- Verifica que no haya cambios pendientes en `src/`, `tests/`, `tools/` ni `packaging/` (los archivos de `docs/`, `AJUSTES.md`, `Hadware/` y los `.log` de compilación y `habblaud/` de Cristian no cuentan; no los toques). Si hay cambios en esas carpetas, escribe `docs/informes/tanda34/CERRADO.txt` con `BLOQUEADO: árbol con cambios pendientes` y termina.
- Cambia a `dev` y crea la rama `tanda34` desde `dev`. Lleva `docs/informes/tanda34/estado.md` al día tras cada commit; al reanudar, sigue desde el primer paso pendiente.

## Contexto
- Archivos: `ui_qml/qml/Componentes/CirculoFaseLiquido.qml` (llenado, onda, física del chorro), `BarraFases.qml` (pasa `chorroHabilitado: fase.index > 0 && con.progreso >= 1`), `ConectorFase.qml` (el tubo: alto 7 × escala, entra al círculo por el borde izquierdo a media altura), `Tema/Colores.qml` (`faseChorro`), `Pruebas/PruebaCicloEnCurso.qml`, `tests/test_llf_barra_fases_qml.py`, `tests/test_tema_oscuro.py`, `tests/banco/llf_capturas_barra_fases.py`, paleta `docs/diseno/mockups/modo_oscuro/paleta_modo_oscuro.md`. Planeación de origen: `docs/mis_plans/planeacion_llenado_fases.md` (HAZ-LLF-01, REQ-36).
- Pedido: el chorro de agua que entra por el tubo se cambia por vapor. El llenado (nivel, degradado, onda, colores, tiempos, tope 0,90, `aplicar()`) queda exactamente igual.
- Cristian aprobó una vista previa animada en el chat; los valores numéricos de abajo salen de ella (px a escala 1; multiplica por `escala`). Son valores de partida: ajústalos solo si en la captura real no se ve como se describe, y anota el cambio en el informe.

## VAP-01 Retiro del chorro y del chapoteo
- Se retiran de `CirculoFaseLiquido.qml`: `chorroVisible`, `_parcelas`, `_gotas`, `_emitir`, `_pulso`, `_salpicarEn`, `_pasoParcelas`, `_pasoGotas`, `_puntosChorro`, la Shape `chorroFase_*`, el Repeater de gotas y todo el chapoteo (`_inclin`, `_velInclin`, `_chapoteo`, su resorte en `_paso`). `_ySuperficie()` queda solo con la onda (`amplitudOnda`, `faseOnda` sin cambios).
- `chorroHabilitado` se renombra `vaporTuboHabilitado` (misma condición en `BarraFases.qml`: `fase.index > 0 && con.progreso >= 1`). Actualiza el comentario de `ConectorFase.progreso` («lo lee el vapor del círculo siguiente»).
- `faseChorro` deja de usarse: retírala de `Colores.qml`, de la paleta y de los mapas de `test_tema_oscuro.py` (`_PALETA_LIBRE`, `_ORIGEN_CLARO`), o reutilízala si el mecanismo del test lo hace más simple; explica lo elegido en el informe.

## VAP-02 Vapor en la fase activa
Condición común: `estado === "activa" && datosVigentes && !instantaneo && visible`. Sin datos vigentes no hay vapor (igual que hoy la onda se detiene; la animación no debe sugerir un proceso vivo sin datos). Corre durante toda la fase activa, con cualquier nivel (también cuando la boca del tubo queda bajo el líquido).

a) Vapor del tubo (pluma continua + remolino por la pared), solo con `vaporTuboHabilitado` (la primera fase no tiene tubo a la izquierda: solo lleva el vapor b):
- Emisión cada 30 ms desde la boca (x = 1 px dentro del círculo, y = centro ± 0,25 × alto de la boca), velocidad inicial 60 px/s (±15 %) hacia dentro, ángulo ±13°.
- Cada partícula: la velocidad propia se amortigua (factor `1 − 2,4·dt`); desde que nace gana un movimiento tangencial que sube por la pared izquierda y sigue por arriba (en pantalla, sentido horario), con peso `min(1, edad × 1,6)` y rapidez 48 px/s; una corrección radial la lleva a un radio objetivo `R − 5…10` px que baja 3 px/s. Radio inicial 2 px, crece 5,5 px/s. Vida 2,2–2,8 s. Opacidad: sube en el primer 15 % de la vida y baja hasta 0 al final; pico 0,77 × la opacidad del color (VAP-04).
- Tope de partículas vivas: 90.

b) Bocanadas desde la superficie (propuesta B), en toda fase activa:
- Una cada 0,2 s, en x al azar dentro del 70 % central del círculo, sobre la superficie (`_ySuperficie(x)`); suben 14–24 px/s con empuje de 16 px/s², deriva lateral ±3 px/s; radio inicial 3 px, crece 4 px/s; vida 1,3–1,8 s; mismo perfil de opacidad, pico 1,0 × la del color. Tope: 12.

Recorte al círculo sin módulos nuevos: radio visible = `min(r, R − 1 − d)` (d = distancia del centro de la partícula al centro del círculo); si queda < 1 px no se dibuja. No uses `Canvas`, `QtQuick.Particles` ni máscaras de `QtQuick.Effects`/`Qt5Compat` (no agregar dependencias a PyInstaller). Usa el patrón que ya existe: un `FrameAnimation`, arreglos JS y un `Repeater` de `Rectangle` redondos con un grupo fijo (como las gotas actuales). Orden: líquido z 1, vapor z 2, ícono z 3 (el ícono sigue encima).

## VAP-03 Burbujas en la última fase completada
- `BarraFases.qml` pasa `burbujasHabilitadas` = el círculo con `estado === "completada"` de mayor índice menor que el de la fase activa. Si no hay fase activa (ciclo terminado, fallido, interrumpido o sin datos) ningún círculo tiene burbujas: queda lleno sin animación. Solo un círculo a la vez. Además `datosVigentes && !instantaneo && visible`.
- En ese círculo no sale nada del tubo (el vapor a) es solo de la activa).
- Una burbuja cada 0,12 s desde abajo, x al azar en el 75 % central; suben 18–34 px/s con vaivén lateral ±0,25 px por cuadro; radio 1,8–3,6 px, crece 0,6 px/s; se dibujan como anillo (borde 1,1 px, color `faseBurbujaBorde`) con relleno tenue (`faseBurbujaRelleno`); mueren al salir del círculo (mismo recorte de VAP-02). Tope: 20.
- Las demás fases completadas quedan como hoy: llenas, sin animación.

## VAP-04 Colores (solo en `Tema/Colores.qml`)
- `faseVapor` (vapor sobre el líquido): claro `#42FFFFFF`, oscuro `#42DCF0FF`.
- `faseVaporFondo` (vapor sobre la zona vacía del círculo; Cristian pidió que en el claro se vea más sobre el gris `#CCCCCC`): claro `#8CF6FBFF`, oscuro `#42DCF0FF`.
- `faseBurbujaBorde`: claro `#8CFFFFFF`, oscuro `#8CDCF0FF`. `faseBurbujaRelleno`: claro `#24FFFFFF`, oscuro `#24DCF0FF`.
- La zona de cada partícula de vapor se decide por cuadro: si su centro está sobre `_ySuperficie(x)` usa `faseVaporFondo`, si no `faseVapor`; la opacidad de la partícula multiplica la del color.
- Registra los cuatro en la paleta (§6, junto a las fases) y en `test_tema_oscuro.py` con el mecanismo que ya usan los colores nuevos de tandas anteriores (p. ej. los `deslizador*` de AJ-01); los claros no existían en `dev`: déjalo explícito donde el test lo pida.

## VAP-05 Arranque, parada y rendimiento
- El `FrameAnimation` corre solo si hay emisión activa o partículas vivas. Al dejar de cumplirse la condición (cambio de fase, fin del ciclo) se deja de emitir y las partículas vivas terminan su vida (≤ 3 s); con `datosVigentes` false, `instantaneo` o `visible` false se vacían en el acto.
- En toda la barra animan como máximo dos círculos (la activa y la última completada). Mide el tiempo de cuadro con `Pruebas/PruebaCicloEnCurso.qml` a 1024 px y anótalo en el informe.
- `nivel`, `nivelVisual`, `nivelObjetivo` y `_lleno` no dependen del vapor ni de las burbujas (HAZ-LLF-01).

## VAP-06 Pruebas, arnés y capturas
- `tests/test_llf_barra_fases_qml.py`: reemplaza las pruebas del chorro por: vapor del tubo solo con activa + conector lleno + índice > 0 + datos vigentes (también con nivel ≥ 0,5); bocanadas en toda activa, incluida la primera; nada de vapor en pendiente, completada, fallida o interrumpida; sin datos vigentes ni vapor ni onda; burbujas solo en la última completada mientras haya activa, ninguna al terminar el ciclo, ninguna en las completadas anteriores; `_ySuperficie` sin chapoteo; el tope 0,90 y el nivel no cambian. `objectName`: `vaporFase_<fase>` y `burbujasFase_<fase>`.
- `PruebaCicloEnCurso.qml`: textos de los escenarios con chorro → vapor.
- `tests/banco/llf_capturas_barra_fases.py`: reemplaza 11c, 11d y 11e por capturas de vapor (activa al 25 % y al 70 %, última completada con burbujas, ciclo terminado sin animación), en tema claro y oscuro; deja las capturas en `docs/informes/tanda34/capturas/` para que Cristian las apruebe.

## Zoom de la gráfica del ciclo (ZOM-01..ZOM-08)
Decisiones de Cristian (8-nov), con vista previa aprobada en el chat. Solo interfaz: no se tocan backend, datos, `progreso_ciclo` ni el registro.

Contexto: `ui_qml/qml/Componentes/GraficaCiclo.qml` (instancias en `Pantallas/PantallaCicloEnCurso.qml`, vista normal y pantalla completa, y en `Componentes/DetalleCiclo.qml` de Historial), `Componentes/grafica_ejes.mjs` (`ejeX`, `ejeY`, `decimar`; pruebas en `tests/test_grafica_ejes_js.py`), pruebas QML existentes `test_pantalla_ciclo_en_curso_qml.py`, `test_aj03_globo_grafica_qml.py` y `test_t28d_card_grafica_qml.py`. Hoy los ejes empiezan en 0: `xDe`, `yDe`, `_tDesdeX` y las marcas (`marca.index * paso`, `linea.index * paso`) suponen origen 0. Un dedo mueve el cursor (`toqueGrafica`, `MouseArea` con `preventStealing`; se oculta a los `ocultarCursorMs` = 5 s).

### ZOM-01 Alcance
Las tres instancias. Todo el comportamiento vive en `GraficaCiclo.qml` y en funciones puras de `grafica_ejes.mjs`; las pantallas no cambian salvo lo que haga falta para que un `Flickable`/vista padre no robe el gesto (revísalo en Historial y en las dos de Ciclo en curso; informa qué encontraste). La instancia de pantalla completa es otra `GraficaCiclo`: el zoom no se traslada entre la vista normal y la completa.

### ZOM-02 Ventana visible
- Sin zoom, la vista es exactamente la de hoy (ejes desde 0, `ejeX(tiempoActualMin)`, `ejeY(máximo)`); agrega una prueba que lo fije.
- Con zoom, la ventana se guarda en valores absolutos: `t0..t1` (min), `yIzq0..yIzq1` y `yDer0..yDer1` (unidades vigentes). `xDe`, `yDe`, `_tDesdeX`, la cuadrícula, las marcas, los divisores e íconos de fase, el cursor con su globo y la llamada a `decimar` (rango `t0..t1`) usan la ventana.
- Marcas: función pura nueva en `grafica_ejes.mjs` (p. ej. `marcasVentana(min, max, divisionesObjetivo)`) con paso redondo (1, 2 o 5 × 10^n), sin marcas fuera de la ventana; mismas divisiones aproximadas que hoy y mismo redondeo de etiquetas (`Math.round(v * 100) / 100`). Pruebas en `test_grafica_ejes_js.py`.
- Curvas, divisores e íconos recortados al área de trazado; un ícono de fase solo se dibuja si su tramo visible mide más de 40 px × escala (regla actual).

### ZOM-03 Gesto de dos dedos
- Zona: el área de trazado actual (`toqueGrafica`). Los botones de cabecera, Tiempos y pantalla completa no cambian.
- Factor por eje según la separación de los dedos en ese eje: X = |dx actual| / |dx inicial|, Y = |dy actual| / |dy inicial|, centrado en el punto medio inicial. Separar en horizontal amplía solo el tiempo, en vertical solo los valores, en diagonal los dos. Un eje cuya separación inicial sea menor que 40 px × escala no se escala (`DECISIÓN SIN CONFIRMAR`).
- Los dos ejes Y se escalan y desplazan con la misma fracción de su escala completa.
- Desplazamiento: el movimiento del punto medio de los dos dedos desplaza la ventana en los dos ejes, también en un gesto que ya no escala.
- Un dedo sigue moviendo el cursor como hoy. Al apoyarse el segundo dedo el cursor queda donde estaba y no se mueve hasta soltar los dos; un gesto de dos dedos nunca mueve el cursor.
- La matemática del gesto va en funciones puras de `grafica_ejes.mjs` (p. ej. `ventanaPorGesto(...)`, `acotarVentana(...)`) con pruebas en `test_grafica_ejes_js.py`; el QML solo lee los puntos de contacto (`MultiPointTouchArea`, `PointHandler` o lo que conviva sin conflicto con el cursor; explica lo elegido) y llama a esas funciones.
- Solo para probar en un PC sin táctil: rueda del mouse = zoom en X y Ctrl + rueda = zoom en Y, centrados en el puntero (`DECISIÓN SIN CONFIRMAR`).

### ZOM-04 Límites
- No se aleja más allá de la vista completa: la ventana queda siempre dentro de ella, también al desplazar.
- Ventana mínima: 2 min en X (si la vista completa dura menos de 2 min, X no se amplía) y el 10 % de la escala completa en cada eje Y.

### ZOM-05 Ciclo en curso y cambios de datos
- Con zoom la ventana queda fija: los puntos nuevos aparecen solo si caen dentro de ella; que la vista completa crezca (tiempo actual, máximo de Y) no la mueve.
- Al restablecerse vuelve a la vista completa vigente, que sigue al tiempo actual.
- Sin transición y en el acto se restablece si cambian las unidades, si `datos` pasa a otro ciclo (Historial abre otro), si la gráfica deja de ser visible o si queda sin datos.

### ZOM-06 Restablecimiento a los 20 s
- `restablecerZoomMs` = 20000, contado desde el último toque en el área de trazado: un gesto de dos dedos o el cursor de un dedo reinician la cuenta. El temporizador del cursor (5 s) sigue independiente.
- Transición de 300 ms (InOutQuad) desde la ventana actual hasta la vista completa. Un gesto nuevo durante la transición la interrumpe y parte de la ventana en que esté.

### ZOM-07 Lupa indicadora
- Con zoom activo aparece una lupa en la esquina superior derecha del área de trazado (dentro de la cuadrícula, con margen; no tapa la etiqueta «kPa» ni las del eje derecho). Es el único indicador de vista ampliada: sin rótulo ni cuenta regresiva en pantalla.
- Tocar la lupa restablece la vista con la transición de ZOM-06; zona táctil de al menos 56 × 56 px del mockup aunque el dibujo sea menor.
- Ícono nuevo `lupa.svg` (monocromo, trazo, viewBox 48 como los demás de `assets/iconos/color/`), dibujado con `IconoColor`. Fondo circular `Colores.fondoTarjeta` al 85 % para que se lea sobre las curvas. Color nuevo solo en `Tema/Colores.qml`: `graficaZoomIcono` claro `#3A6FD8`, oscuro `#5B9BFF` (`DECISIÓN SIN CONFIRMAR`), con contraste WCAG verificado en `test_tema_oscuro.py` y registrado en la paleta y en el test como en VAP-04.
- Orden: curvas < lupa < cursor y su globo.

### ZOM-08 Pruebas, arnés y capturas
- `test_grafica_ejes_js.py`: marcas de ventana, factor por eje (horizontal, vertical, diagonal, separación inicial bajo el umbral), desplazamiento, límites de ZOM-04 y que sin zoom la vista sea la de hoy.
- Prueba QML nueva (`tests/test_zom_grafica_zoom_qml.py`): ventana fija con datos nuevos, restablecimiento a los 20 s con el reloj de prueba, reinicio de la cuenta con un toque, restablecimiento al tocar la lupa, restablecimiento inmediato por unidades y por cambio de ciclo, cursor intacto con dos dedos, lupa visible solo con zoom. `objectName`: `lupaZoomGrafica`.
- `Pruebas/PruebaCicloEnCurso.qml`: escenario con zoom (15–25 min, 110–135).
- Capturas en `docs/informes/tanda34/capturas/` (vista ampliada con la lupa, claro y oscuro, a 1080 y 1024 px) para que Cristian las apruebe.
- Pendiente de banco (anótalo en la hoja de pruebas): el gesto con los táctiles reales de la estación (dos monitores asociados con EST-06).

## Deslizador de CANCELAR CICLO (CAN-01..CAN-04)
Decisiones de Cristian (8-nov). Contexto: `Componentes/DeslizadorInicio.qml` (interruptor «holográfico»: anillos, partículas, barrido, pulso, indicador que parpadea; solo emite `completado()` si la manija llega al extremo y vuelve sola si se suelta antes), su uso en `Pantallas/PantallaPreciclo.qml` (`deslizadorIniciarCiclo`, 332 × 110 px del mockup) y el botón `botonCancelarCiclo` de `Pantallas/PantallaCicloEnCurso.qml` (235 × 88 px del mockup, comparte lugar con CONFIRMAR), con su `modalCancelar`. Pruebas: `tests/test_cancelacion_ciclo_en_curso_qml.py`.

### CAN-01 Variante roja del deslizador
- `DeslizadorInicio.qml` recibe una variante de paleta (p. ej. `property string variante: "inicio"` | `"cancelar"`) que cambia solo los colores; forma, animaciones, tiempos y comportamiento son exactamente los mismos. Se conserva el nombre del componente (cambio mínimo); anota en su cabecera que también sirve para cancelar.
- Colores nuevos solo en `Tema/Colores.qml`: un `deslizadorCancelar*` por cada `deslizador*` de color (Pista, PistaListo, Acento, AcentoListo, Brillo, BrilloListo, Texto, SombraInterior, Nucleo, Manija, ManijaListo), en rojos coherentes con `cancelarArriba` / `cancelarAbajo` (claro `#F40000` / `#870004`). Valores tuyos, `DECISIÓN SIN CONFIRMAR`; mismos pares de contraste que los verdes en `test_tema_oscuro.py`, registrados en la paleta y en el test como en VAP-04. Las magnitudes (`deslizadorBordeAlfa`, etc.) se comparten.
- El deslizador de Preciclo no cambia: prueba que fije la variante "inicio" por defecto con los colores de hoy.

### CAN-02 Cancelar en Ciclo en curso
- Mientras el ciclo no termina, el lugar de `botonCancelarCiclo` (mismo x, y, 235 × 88 px del mockup) lo ocupa el deslizador rojo, `objectName` `deslizadorCancelarCiclo`: texto «CANCELAR CICLO» (`ciclo.cancelar`), texto al deslizar «Cancelando…» (clave nueva `ciclo.cancelando`, en: «Cancelling…»), ícono `detener.svg` en la manija. Textos con letra que se ajusta, nunca `elide` (D8-5.4); revísalo a 1024 px en es/en.
- `enabled`: `datosVigentes && !comandoOcupado && !modalAbierto`; oculto en los mismos casos en que hoy no se ve el botón.
- Al completarse el arrastre se cancela directamente, sin modal: `cancelarPulsado()` y `comandos.cancelar()` como hace hoy la aceptación del modal (mismo token opcional y `cancelado_por`, FC-12). Un rechazo se muestra igual que hoy (`ciclo.cancelar_error`) y el deslizador vuelve al inicio.
- Al terminar el ciclo vuelve el botón CONFIRMAR de hoy, con sus modales (`modalConfirmar`, `modalEstadoSeguro`) y el indicador de ENT-09 sin cambios.

### CAN-03 Retiro del modal de cancelar
- Se retira `modalCancelar` y sus claves i18n si ya nadie las usa. Su cuerpo mostraba el número de sensores sin lectura (`sinLectura(cicloActivo)`): verifica si esa información queda visible en otro lugar de la pantalla y dilo en el informe; si no, `DECISIÓN SIN CONFIRMAR` de Cristian, sin agregar nada.

### CAN-04 Pruebas
- `test_cancelacion_ciclo_en_curso_qml.py`: arrastre completo = una sola cancelación; soltar antes del extremo = nada; deshabilitado sin datos vigentes, con un comando en curso o con un modal abierto; rechazo vuelve al inicio con el mensaje; terminado = botón CONFIRMAR con su modal. Prueba de colores: variante "cancelar" en rojo y "inicio" sin cambio.
- Capturas del deslizador rojo en reposo y a medio arrastre, claro y oscuro, a 1080 y 1024 px, en `docs/informes/tanda34/capturas/`.

## Mensaje de espera de la cámara (ESP-01..ESP-02)
Decisión de Cristian (8-nov): en la barra inferior el texto «Esperando cámara segura: {motivo}» se sale de su cuadro y el detalle debe verse en la tarjeta de alarmas y avisos, no abajo. Contexto: `indicadorEntrega` / `textoEntrega` de `PantallaCicloEnCurso.qml`, `ui_qml/domain/entrega_camara.py`, claves `ciclo.entrega_motivo`, `ciclo.entrega_sin_motivo`, `ciclo.entrega_espera`, y la fila NO ABRIR de `SeccionEstadoSeguro.qml` en la tarjeta de alarmas de Ciclo en curso (motivo con valor y límite desde el hotfix ES, detalle en `VentanaDetalleAlarma` vía `detalle_aviso.py`).

### ESP-01 Barra inferior solo con el mensaje de espera
- El indicador muestra solo «Esperando cámara segura» (`ciclo.entrega_sin_motivo`) o, en la espera fija tras un COMPLETADO, «Esperando condiciones de apertura: m:ss» (`ciclo.entrega_espera`), sin motivos. El texto queda dentro de su cuadro en es/en a 1080 y 1024 px (letra que se ajusta, nunca `elide`).
- No cambian: el modal de confirmación forzada (sigue mostrando el motivo completo en `nota`), el rechazo `camara_no_entregada` con su motivo, ni la lógica de entrega. Si `ciclo.entrega_motivo` queda sin uso, retírala.

### ESP-02 El detalle en la tarjeta de alarmas y avisos
- Verifica que, durante la espera de entrega, la tarjeta de alarmas y avisos de Ciclo en curso muestre la fila NO ABRIR con los mismos motivos, valores y límites que hoy da `entrega.motivos_detalle` (mismo programa del ciclo, T29-04) y que su detalle se abra al tocarla. Si coinciden, no cambies nada y dilo; si difieren o la fila no aparece y se corrige solo en la interfaz, corrígelo; si hace falta tocar el backend, no lo hagas: anótalo como pendiente de Cristian en el informe.
- Prueba QML: con la cámara sin entregar, la barra inferior no contiene el motivo y la fila NO ABRIR sí.

## Cierre
- Suite completa en verde.
- `CLAUDE.md`: en «Llenado líquido de la barra de fases», párrafo corto con VAP-01..05.
- `CLAUDE.md`: sección nueva corta «Zoom de la gráfica del ciclo» con ZOM-01..07 (ventana absoluta, gesto, límites, 20 s, lupa).
- `CLAUDE.md`: en la sección de la tanda 31 (ENT-09), una línea con ESP-01/02; y una línea nueva con CAN-01..03 (deslizador rojo, cancelación sin modal).
- Riesgos en `docs/riesgos/registro_riesgos.md`: HAZ-LLF-01 sin cambio (verifícalo y dilo); nuevo HAZ-VAP-01 (BAJA): el vapor que entra por el tubo se muestra en todas las fases activas, también en las que no admiten vapor (prevacío en vacío, descompresión, secado); es decorativo y el estado real lo dan el nivel, el nombre de la fase y los valores; `DECISIÓN SIN CONFIRMAR` de Cristian sobre si limitarlo a las fases con vapor. Nuevo HAZ-ZOM-01 (BAJA): el operador lee un tramo ampliado como si fuera el ciclo completo; controles: lupa indicadora, restablecimiento a los 20 s y marcas de eje de la ventana. Nuevo HAZ-CAN-01 (BAJA): la cancelación ya no pide confirmación en un modal; controles: arrastre completo deliberado, vuelta automática si se suelta antes y deshabilitado sin datos o con un comando en curso; en una urgencia el medio es el paro de emergencia. Trazabilidad: siguientes REQ libres (uno por VAP, ZOM, CAN y ESP).
- Informe `docs/informes/tanda34/R_informe.md` (cambios, tiempo de cuadro, capturas, valores ajustados, mecanismo elegido para el gesto, padres que robaban el gesto, `DECISIÓN SIN CONFIRMAR`).
- Merge a `dev`. NO compiles: al cerrar, di que no se compiló y da el comando `python tools/entrega/compilar_entrega.py`.
- Último acto: `docs/informes/tanda34/CERRADO.txt` (fecha, commit del merge, resultado de la suite). Bloqueo que necesite a Cristian: igual, con `BLOQUEADO:` en la primera línea.

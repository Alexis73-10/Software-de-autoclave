# Tanda 34: vapor en la barra de fases (VAP), zoom de la gráfica (ZOM), deslizador de cancelar (CAN) y mensaje de espera (ESP) — informe

Estado: implementada, sin merge a `dev` y **no compilada** (para compilar: `python tools/entrega/compilar_entrega.py` desde `dev` limpio). Rama `tanda34`. Solo interfaz: no se tocó backend, lazo de control, `progreso_ciclo` ni la lógica del nivel. Riesgos HAZ-T34-VAP-01, HAZ-ZOM-01 y HAZ-CAN-01 (BAJA) en `docs/riesgos/registro_riesgos.md`; trazabilidad REQ-92..REQ-95; banco: bloque T34. Capturas en `docs/informes/tanda34/capturas/` (prefijos `vap_`, `zom_`, `can_`, `esp_`), pendientes de aprobación de Cristian.

## Commits

- `fe7fd559` colores (VAP-04, ZOM-07, CAN-01).
- `0bfc94dc` VAP-01..06.
- `ffc59d33` CAN-01..04 y ESP-01..02.
- `818a23b4` ZOM-01..08.
- `12ceb800`, `0d4be25d` retiro de los escenarios de captura del modal de cancelar.

## VAP-01..06

- Retirados de `CirculoFaseLiquido.qml` el chorro, las gotas y el chapoteo; `_ySuperficie()` queda solo con la onda. `chorroHabilitado` pasa a `vaporTuboHabilitado` y se agrega `burbujasHabilitadas`.
- Vapor del tubo (tope 90) solo con fase activa, conector lleno, índice > 0 y datos vigentes; bocanadas (tope 12) en toda fase activa; burbujas (tope 20) solo en la última completada mientras haya fase activa. `objectName`: `vaporFase_<fase>` y `burbujasFase_<fase>`. Sin `Canvas`, `Particles` ni `Effects` (sin dependencias nuevas para PyInstaller). Sin datos vigentes, `instantaneo` o no visible se vacían en el acto.
- Colores nuevos `faseVapor`, `faseVaporFondo`, `faseBurbujaBorde`, `faseBurbujaRelleno`; `faseChorro` se retiró (no se reutilizó; el `plan.md` histórico de modo oscuro todavía la cita).
- **HAZ-LLF-01 verificado sin cambio:** el diff de `0bfc94dc` no modifica `nivel`, `nivelVisual`, `nivelObjetivo`, `_lleno` ni `_topeEfectivo` (tope 0,90); el código nuevo lo declara en su comentario y no los lee ni escribe.
- **Tiempo de cuadro:** 7,0 ms a 1024 px con dos círculos animando, e igual sin animación (`Pruebas/PruebaCicloEnCurso.qml`). Es del PC de desarrollo, no del hardware destino; queda para el banco (T34-01).
- **Valores ajustados:** ninguno; se usaron los de partida del prompt.

## ZOM-01..08

- `GraficaCiclo.qml` guarda `ventanaZoom` (null = la vista de hoy) con `t0..t1` y las dos escalas Y en valores absolutos. Funciones puras en `grafica_ejes.mjs`: `vistaCompleta`, `marcasVentana`, `ventanaPorGesto`, `ventanaPorRueda`, `acotarVentana`, `esVistaCompleta`, `interpolarVentana`, `tramoVentana`, `huellaDatos`/`continuaDatos`.
- **Mecanismo del gesto:** `MultiPointTouchArea` (hasta 2 dedos) sobre `toqueGrafica`, cuyo `MouseArea` conserva `preventStealing` con `mouseEnabled` false; el gesto toma el toque con `gesto.grab()`. Un dedo mueve el cursor; con dos dedos el cursor queda quieto hasta soltar los dos. Se eligió porque convive con el cursor sin cambiar su `MouseArea`.
- Límites: dentro de la vista completa, mínimo 2 min en X y 10 % de la escala en Y. Con zoom la ventana queda fija con datos nuevos. Restablecimiento a los 20 s (`restablecerZoomMs`) con transición de 300 ms InOutQuad; en el acto por unidades, otro ciclo, sin datos o al ocultarse.
- Lupa `lupaZoomGrafica` (zona 56 × 56 px, fondo `fondoTarjeta` al 85 %, `lupa.svg` con `IconoColor` y `graficaZoomIcono`; orden curvas < lupa < cursor). Rueda = X y Ctrl+rueda = Y (factor 1,25 por clic) solo para PC sin táctil.
- **Padres que robaban el gesto: ninguno.** Vista normal de Ciclo en curso: hija directa de la pantalla. Pantalla completa: con un `MouseArea` hermano. `DetalleCiclo`: en `VentanaFlotante`, sin `Flickable`. Reportes: fuera del `Flickable`. Ninguna pantalla se modificó por esto.

## CAN-01..04 y ESP-01..02

- `DeslizadorInicio.qml` con `variante` "inicio" (defecto, colores de hoy) | "cancelar" (solo colores, `deslizadorCancelar*`). `deslizadorCancelarCiclo` (conserva también `botonCancelarCiclo`) ocupa el lugar del botón (235 × 88 px) mientras el ciclo no termina; `enabled` = `datosVigentes && !comandoOcupado && !modalAbierto`; al completar el arrastre llama `cancelarPulsado()` y `comandos.cancelar()` (mismo token y `cancelado_por`, FC-12); un rechazo abre `ciclo.cancelar_error` y el deslizador vuelve al inicio; al terminar vuelve CONFIRMAR con sus modales. `modalCancelar` y las claves `ciclo.modal_cancelar_*` se retiraron; clave nueva `ciclo.cancelando`.
- **Hallazgo CAN-03:** el `{n}` del modal era el número del ciclo activo, no un conteo de sensores sin lectura; sigue visible en la cabecera (`PantallaCicloEnCurso.qml:434`). Lo que se pierde es la advertencia «la carga quedará NO ESTÉRIL» (`DECISIÓN SIN CONFIRMAR` de Cristian).
- **Revisión de seguridad (opus, solo CAN):** sin hallazgos ALTA/MEDIA. Residual BAJO pendiente de aceptación de Cristian: tras una cancelación aceptada el deslizador se reactiva a los 250 ms mientras `resultado` sigue vacío hasta el siguiente sondeo; un segundo arrastre podría ignorarse o dar 409 `resultado_pendiente` con el mensaje `ciclo.cancelar_error` aunque el ciclo sí quedó cancelado. Arreglo posible: no reactivar hasta que llegue `resultado`.
- **ESP-01:** la barra inferior muestra solo «Esperando cámara segura» (`ciclo.entrega_sin_motivo`) o «Esperando condiciones de apertura: m:ss». `ciclo.entrega_motivo` sigue en uso (arma la nota del modal forzado) y no se retiró. El texto se decide en QML (si `textoEntrega` empieza por el prefijo de `entrega_espera` se muestra; si no, sin motivo).
- **ESP-02:** Ciclo en curso no tiene tarjeta propia; la fila NO ABRIR está en el panel de la campana, grupo «Alarmas», con motivo, valor y límite, y su detalle abre al tocarla (prueba QML). Diferencias que dependen del backend, no tocadas: `/status` publica solo el primer motivo y la entrega todos; el motivo «sellado» del protocolo de fallo existe solo en la entrega (sin fila NO ABRIR si lo demás está bien); `/status` usa `programas_para_seguridad()` y la entrega solo `[self.cycle]`. Por diseño (ESS-04), un motivo que es solo sensor sin lectura oculta la fila.

## DECISIÓN SIN CONFIRMAR

- VAP: vapor del tubo y bocanadas en todas las fases activas, también en las que no admiten vapor (HAZ-T34-VAP-01).
- Colores `deslizadorCancelar*` (rojos tomados de `cancelarArriba`/`cancelarAbajo`) y `graficaZoomIcono` (`#3A6FD8` / `#5B9BFF`).
- ZOM: umbral de 40 px × escala para escalar un eje; rueda, Ctrl+rueda y factor 1,25; la cuadrícula sigue al eje izquierdo y el derecho lleva marcas propias sin línea; el cursor se oculta si su lectura cae fuera de la ventana; el primer dedo apoyado antes que el segundo mueve el cursor un instante; `fijarVentana()` del arnés no arranca la cuenta de 20 s.
- CAN: pérdida de la advertencia NO ESTÉRIL; `textoEnDosLineas` del deslizador de cancelar (`Text.Fit`, 2 líneas) e ícono `detener.svg` al 82 % de la manija.
- ESP: decidir el texto de la barra en QML (un slot propio en `bridge/progreso_ciclo.py` sería más limpio).

## Pendiente de Cristian

- Aprobar las capturas `vap_`, `zom_`, `can_` y `esp_`.
- Decidir las diferencias `/status` frente a la entrega (ESP-02) y si se limita el vapor a las fases con vapor.
- Banco T34-01..04: tiempo de cuadro y CPU en la estación, gesto con los táctiles reales (dos monitores asociados con EST-06), arrastre de cancelar y mensaje de espera.
- Decidir el arreglo del residual BAJO de CAN (no reactivar el deslizador hasta que llegue `resultado`).

## Cierre

Suite completa hecha (7 fallos ajenos a la tanda, ver estado.md), merge a `dev` y `CERRADO.txt` hechos. Compilación pedida por Cristian el 9-nov, a continuación del cierre.

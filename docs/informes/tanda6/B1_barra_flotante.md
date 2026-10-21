# B1 — Barra inferior flotante en todas las pantallas (tanda 6)

Rama `tanda-6-b1` (desde `tanda-6`). Decisión 1.7: la exclusión por D-19 queda sin efecto para la barra.

## Estado por pantalla

| Pantalla | Antes | Ahora |
|---|---|---|
| `PantallaPreciclo.qml` | Barra dibujada a mano DENTRO del panel principal (el panel blanco llegaba a y 1900 y la barra estaba encima) | `BarraInferiorMenu` flotante (`barraInferiorPreciclo`), hija de la pantalla, en x 34 / 171 px del borde inferior (como Opciones). Izquierda: equipo (modelo, serie; abre el panel de equipo). Centro: versión. Derecha: iniciar sesión (avatar). El panel principal (`tarjetaPreciclo`) termina 10 px sobre la barra. |
| `PantallaCicloEnCurso.qml` | Igual que Preciclo | `BarraInferiorMenu` flotante (`barraInferiorCicloEnCurso`). Izquierda: equipo. Centro: iniciar sesión. Derecha: CANCELAR / CONFIRMAR (sin cambios de lógica, `botonCancelarCiclo`). Versión abajo a la derecha (la de la barra). Panel `tarjetaCicloEnCurso` termina 10 px sobre la barra. |
| Login, CambioClave, NuevoUsuario | Ya hechos (barra flotante fuera de la tarjeta) | Verificados: `tests/test_barra_inferior_flotante_qml.py` en verde y capturas. |
| MenuPrincipal, Opciones (y sus subpantallas, que se cargan dentro de Opciones) | Ya flotante | Sin cambios. |
| Instalación | Barra de acciones (Atrás/Siguiente/Instalar) | Sin cambios (instrucción). |
| IntroArranque, Reposo | Sin barra | No aplica. |

## Cambio en el componente
`Componentes/BarraInferiorMenu.qml`: nueva propiedad `personalizada` (oculta Atrás, Inicio y Cerrar sesión) y propiedad por defecto `contenido` (los hijos que declara la pantalla van a una capa encima del fondo y los separadores, con coordenadas relativas a la barra). Sin `personalizada` el comportamiento es idéntico al anterior (Menú, Opciones, Login, CambioClave y NuevoUsuario no cambian).

Preciclo gana la señal `equipoPulsado()` (ya existía en Ciclo en curso); no hay nada conectado a ella.

No se agregaron textos visibles nuevos (la versión sigue saliendo de `app.version`), así que no hubo claves i18n nuevas.

## Pruebas
- Nueva: `tests/test_b1_barra_preciclo_ciclo_qml.py` (Preciclo y Ciclo en curso, 1200×1920 offscreen): carga sin avisos; la barra no es descendiente de la tarjeta, es hija directa de la pantalla y queda por debajo; misma colocación que Opciones; cada botón de la barra (equipo, iniciar sesión, cancelar) está dentro de la barra y emite su señal (cancelar abre el diálogo de confirmación); ningún contenido cruza el borde superior de la barra; el contenido de la pantalla cabe dentro de la tarjeta.
- Ajustada: `tests/test_u2_navegacion_qml.py` (buscaba el avatar por sus coordenadas antiguas en el texto; ahora por la celda derecha de la barra).
- Ajustada: `tests/test_main_menu_principal_qml.py` buscaba `botonInicio` en toda la ventana; ahora Preciclo también tiene una `BarraInferiorMenu` (con Inicio oculto), así que se busca dentro de `barraInferiorMenu`.

Suite completa: 4631 passed, 2 skipped, 3 xfailed (la única roja de la corrida, `test_u2_navegacion_qml`, se corrigió y se volvió a correr en verde).

## Capturas (1200×1920, offscreen)
`docs/informes/tanda6/capturas/B1_PantallaPreciclo.png`, `B1_PantallaCicloEnCurso.png`, `B1_MenuPrincipal.png`, `B1_Opciones.png`, `B1_Login.png`, `B1_CambioClave.png`, `B1_NuevoUsuario.png`, `B1_Instalacion.png`.

Limitación de las capturas: el botón CANCELAR y los botones ABRIR PUERTA / INICIAR CICLO usan `layer.effect: MultiEffect` y en la captura offscreen no se dibujan. Pasa igual con la versión anterior (`HEAD`) de la pantalla: no es un efecto de este cambio. La prueba confirma que CANCELAR existe dentro de la barra y abre su diálogo. Preciclo se capturó sin backend, así que solo muestra el aviso NO ABRIR.

## Decisiones
- **DECISIÓN SIN CONFIRMAR — margen tarjeta-barra de 10 px (no 30 como en Opciones)** en Preciclo y Ciclo en curso. Los botones ABRIR PUERTA / INICIAR CICLO (Preciclo, hasta y 1725 del lienzo) y la barra de progreso (Ciclo, hasta y 1723) no se reubican porque no se debe refactorizar el resto de esas pantallas. Con 30 px quedarían fuera de la tarjeta.
- **DECISIÓN SIN CONFIRMAR — "Menú a la izquierda" del mockup = celda de equipo** (icono, modelo y serie; abre el panel de equipo con Apagar), que es la función de hoy en esa posición. El menú de engranaje sigue en la cabecera.
- **DECISIÓN SIN CONFIRMAR — versión al centro solo en Preciclo** (como pide el mockup 1). En Ciclo en curso la celda central es el avatar (función de hoy) y la versión queda abajo a la derecha, como en el resto de las barras.
- **DECISIÓN SIN CONFIRMAR — el avatar se centra en su celda** (antes estaba desplazado unos px: x 1001 en Preciclo y x 594 en Ciclo).
- La barra mide 1128 de ancho con separadores en 313 y 800 (antes 1130, en 347 y 834 sobre el lienzo): se usa la geometría del componente.

## Cómo revertir
Revertir el commit de B1 (`git revert <sha>`): toca `BarraInferiorMenu.qml`, `PantallaPreciclo.qml`, `PantallaCicloEnCurso.qml`, las dos pruebas, este informe y las capturas `B1_*`.

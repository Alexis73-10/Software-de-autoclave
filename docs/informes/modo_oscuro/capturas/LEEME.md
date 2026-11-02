# Capturas del modo oscuro (paso 7)

Generadas con `python tests/banco/osc_capturas.py` (arneses propios, datos de ejemplo; plataforma nativa de Windows, sin escalado, ventana sin marco). Nombre: `osc_<claro|oscuro>_<1080|1024>_<pantalla>.png`; 1080 = 1080x1920, 1024 = 1024x1638. 40 archivos (10 pantallas x 2 temas x 2 anchos).

Pantallas: `reposo`, `login`, `login_teclado` (teclado alfanumérico abierto), `menu` (Menú principal), `preciclo_preparado`, `preciclo_alarma` (no preparado con alarma), `ciclo_grafica` (ciclo en curso con gráfica), `fin_fallido`, `modal_cancelar` (modal de confirmación sobre el ciclo), `opciones_tema` (Configuración de la máquina con el selector Tema; sin sesión real queda deshabilitado).

## Claro contra dev (c43b9d0b)

Capturas de dev con el mismo arnés en un worktree limpio, comparadas con PIL (se ignora el reloj, que cambia con la hora). Resultado: sin diferencias de color ni de distribución en ninguna pantalla. Quedan solo diferencias de borde (suavizado de contorno) en los íconos que ahora pasan por `IconoColor` (teñido en lugar de `Image`): atrás/inicio de la barra inferior, avatar y campos del Login (usuario, ojo), chevrones de las tarjetas del menú, pantalla completa de la gráfica, ícono de estado, tecla borrar del teclado y el botón de inicio del deslizador de Preciclo. Píxeles con diferencia mayor a 32/255 (a 1080, sin reloj): Login 858, Login con teclado 509, Menú 753, Ciclo con gráfica 178, Modal 23, Preciclo preparado 316 (deslizador), el resto 0. Opciones: no comparable (dev no tiene el selector).

- OSC-17 (chevron_abajo, ojo, candado): claro sin diferencia visible (solo borde de trazo).
- OSC-18 (Login/CambioClave/NuevoUsuario): igual; ver hallazgo 1 de oscuro.
- OSC-20 (deslizador): en claro una línea fina de brillo distinta (<= 316 px en Preciclo preparado); imperceptible.
- No se corrigió ningún literal: no hubo diferencia atribuible a un literal mal mapeado.

## Oscuro contra mockups (`docs/diseno/mockups/modo_oscuro/` 01..05)

Paleta, fondos degradados, tarjetas, bordes y acentos (verde, morado, naranja, azul) coinciden con los mockups. Diferencias:

1. **Campos del Login (y recuadro de `CampoFormulario`) quedan blancos en oscuro**: son `Rectangle` sin `color` (blanco por defecto), no un literal; el claro es correcto. Lo mismo para la casilla «Recordar usuario». Falta una propiedad de Colores (fondo de campo) y asignarla. Sin corregir (fuera del alcance: solo claro).
2. **Login: íconos de los campos** (usuario, candado, ojo) y la casilla quedan de poco contraste sobre el fondo blanco del hallazgo 1; con el candado en `bordeCampo` (OSC-18) apenas se ve. El avatar sí se ve bien.
3. **Preciclo: botón «PUERTA CERRADA» deshabilitado** tiene texto e ícono azul muy oscuro sobre el fondo oscuro, casi ilegibles (el ícono de puerta no sigue el tinte de deshabilitado).
4. **Ciclo en curso**: el chevron del selector «Tiempos» queda negro sobre fondo oscuro (ícono multicolor sin tinte, ya anotado en OSC-20); el ícono blanco de fase pendiente de `CirculoFaseLiquido` no se tiñe.
5. Los mockups usan otro juego de íconos (más finos: calendario, check, gráfico de barras, información naranja) y contenidos distintos (#1248, 52 ciclos restantes); en la app se conservan los íconos y textos actuales. Las tarjetas del Menú no llevan el halo verde del mockup en «Iniciar sesión».
6. Fin de ciclo fallido: coincide con la paleta (rojo, ámbar, azul de acción); el círculo de la fase fallida es rojo muy saturado frente al resto de la paleta.

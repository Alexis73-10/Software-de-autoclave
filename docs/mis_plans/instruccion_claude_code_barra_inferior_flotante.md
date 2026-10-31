# Instrucción para Claude Code — Barra inferior flotante en todas las pantallas (20-oct-2026)

Objetivo: que todas las pantallas con navegación usen la misma barra inferior flotante (`BarraInferiorMenu`): una sola barra blanca **fuera** de la tarjeta de contenido, con tres secciones y dos separadores verticales (Atrás a la izquierda, centro vacío o Cerrar sesión, Inicio a la derecha con la versión). Decisión de Cristian, 20-oct-2026.

Esta instrucción solo cambia la presentación y el cableado de la barra. No toca lógica de seguridad, backend ni textos de otras pantallas.

## 0. Reglas
1. Responde y escribe el informe **en español**.
2. Trabaja en la rama en la que estés (`dev` o `tanda-4`); no crees ramas nuevas, no hagas commit: deja los cambios en el árbol de trabajo para que Cristian los confirme visualmente. Nunca `git add -A`.
3. No toques `data/`, `.claude/`, `*.db`, `Autoclave.spec`, firmware ni hardware. No compiles el ejecutable.
4. Ante ambigüedad elige lo más seguro y reversible, márcalo "DECISIÓN SIN CONFIRMAR" en el informe.
5. Suite de pruebas completa en verde al terminar (línea base: ejecútala antes de empezar y anótala).
6. Informe en `docs/informes/barra_inferior_flotante.md`: qué cambió por pantalla, qué pruebas se actualizaron, decisiones sin confirmar y cómo revertir.

## 1. Estado actual (levantado el 20-oct, verifícalo antes de editar)

| Pantalla | Barra hoy | Acción |
|---|---|---|
| `MenuPrincipal.qml` | `BarraInferiorMenu` flotante (fuera de la tarjeta) | Ninguna |
| `Opciones.qml` | `BarraInferiorMenu` flotante, con `cerrarSesionVisible: true` | Ninguna (es la referencia) |
| `PantallaPreciclo.qml`, `PantallaCicloEnCurso.qml` | Barra propia dibujada en la pantalla, flotante (divisores en 347 y 834 del lienzo) | Ninguna: ya es flotante y D-19 prohíbe refactorizarlas |
| `Login.qml` | `BarraInferiorMenu` **dentro del slot `pie` de `TarjetaContenido`** (línea ~435) | **T1** |
| `CambioClave.qml` | `BarraInferior` (fila de 4 iconos) dentro del slot `pie` de la tarjeta, con dos botones inactivos (`historial`, `mantenimiento`) | **T2** |
| `NuevoUsuario.qml` | Barra dibujada a mano dentro del slot `pie` de la tarjeta (atrás, divisor, centro vacío, divisor, casa, versión; `objectName: "botonAtrasNuevoUsuario"`) | **T3** |
| `Instalacion.qml` | Barra de **acciones** (Atrás / Siguiente / Instalar) dentro del `pie`; no hay sesión ni navegación | **No se toca** (ver §4) |
| `IntroArranque.qml`, `Reposo.qml` | Sin barra (arranque y espera) | No aplica |

## 2. Referencia de implementación

Componente: `ui_qml/qml/Componentes/BarraInferiorMenu.qml` (1128 × 139 en el lienzo de diseño, separadores en x 313 y 800). Propiedades: `escala`, `version`, `atrasHabilitado`, `inicioActivo`, `cerrarSesionVisible`; señales `atrasPulsado`, `inicioPulsado`, `cerrarSesionPulsado`.

Colocación de la referencia en `Opciones.qml` (~línea 286): se instancia **fuera** de la tarjeta, anclada al borde inferior (`x: m(34)`, `y` desde abajo, `escala: raiz.escala`), con `version: I18n.t("app.version", I18n.lang)`.

La tarjeta (`TarjetaContenido`) se acorta para que la barra quede por debajo con el mismo margen que en Opciones. Mira cómo `Opciones.qml` calcula el alto de su contenido (`height: barra.y - y - raiz.m(30)`) y úsalo como modelo.

Los iconos de Atrás e Inicio salen de `assets/iconos/color/` (`back_icon.svg`, `home_icon.svg`), no de `mono/`.

## 3. Tareas

**T1. Login.** Saca `BarraInferiorMenu` del slot `pie` de la tarjeta y colócala flotante debajo de ella, igual que en `Opciones.qml`. La tarjeta pasa a no tener `pie` y su alto se reduce (hoy `parent.height - 176 - 24`, que ya reserva espacio para la barra y el margen inferior: recalcula con el alto real de la barra). Conserva `objectName: "barraInferiorLogin"`, `inicioActivo: true`, las señales y la versión. `cerrarSesionVisible` queda en `false` (aún no hay sesión).

**T2. CambioClave.** Reemplaza `BarraInferior` (4 iconos) por `BarraInferiorMenu` flotante fuera de la tarjeta. Atrás e Inicio siguen abandonando el cambio de clave y siguen inactivos mientras `control.ocupado`: `atrasHabilitado: !control.ocupado`, `inicioActivo: !control.ocupado`. Elimina los botones inactivos `historial` y `mantenimiento` (no están en el diseño). Asigna `objectName: "barraInferiorCambioClave"`. Si tras el cambio `BarraInferior.qml` queda sin usos, **no lo borres**: anótalo en el informe.

**T3. NuevoUsuario.** Reemplaza la barra dibujada a mano del `pie` por `BarraInferiorMenu` flotante fuera de la tarjeta. Atrás → `raiz.pulsarAtras()`, Inicio → `raiz.pulsarInicio()` (ambos ya piden confirmar el descarte de datos). `objectName: "barraInferiorNuevoUsuario"`. La prueba que use `botonAtrasNuevoUsuario` debe seguir pasando: actualízala para que busque el `botonAtras` dentro de `barraInferiorNuevoUsuario` (el componente ya expone `botonAtras` y `botonInicio`). Mantén las mismas reglas de habilitación que hoy.

**T4. Pruebas.**
- Actualiza las pruebas QML existentes que apunten a las barras antiguas de estas tres pantallas (`tests/test_menu_principal_componentes_qml.py` y las de Login, CambioClave y NuevoUsuario que busquen botones de la barra por `objectName`).
- Añade una prueba por pantalla que verifique que la barra existe, que **no** es hija de la tarjeta de contenido (su posición queda fuera del rectángulo de la tarjeta, por debajo) y que Atrás e Inicio emiten su señal.
- Añade una prueba de que ninguna de las tres tarjetas conserva contenido en su slot `pie`.

**T5. Verificación visual y informe.** Si el entorno lo permite, captura las tres pantallas en 1200 × 1920 y compara con `docs/diseno/referencias/pantallas_1080x1920/pantalla_02_menu_principal_1080x1920.png`. Si no puedes capturar, dilo y no inventes resultados.

## 4. Decisiones sin confirmar (Cristian debe revisarlas)

- **Instalación (`Instalacion.qml`):** se deja como está. Su barra contiene botones de acción del asistente (Atrás / Siguiente / Instalar / Continuar) y no existe sesión ni navegación a la que volver. Convertirla en barra flotante implicaría meter esos botones en las tres secciones o crear una barra de acciones distinta. Queda para una decisión aparte.
- **Preciclo y Ciclo en curso:** se dejan con su barra propia por D-19. Los divisores (347 y 834 sobre el lienzo de 1200) son equivalentes a los de `BarraInferiorMenu` (313 y 800 sobre 1128); no se unifican en esta tanda.
- **Nuevas pantallas de OPCIONES › Entradas / Salidas:** ya usan la barra de `Opciones.qml`; no requieren trabajo aquí.

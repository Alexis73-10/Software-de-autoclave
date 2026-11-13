# Prompt: interfaz QML en formato horizontal (lienzo fijo 1920×1200)

Trabajo sin supervisión posible con `tools\tandas\lanzar_prompt.ps1 -Nombre horizontal`. Rama `horizontal` desde `dev` limpio. Entrega no compilada. Informe en `docs/informes/horizontal/R_informe.md`; `estado.md` al día tras cada commit; al terminar, `CERRADO.txt` (ver CLAUDE.md).

## Objetivo

**Agregar** a **todas** las pantallas de la interfaz QML (`src/autoclave/ui_qml/qml`) una disposición horizontal sobre un lienzo **fijo de 1920×1200** (8:5): mismos px de diseño, misma escala, mismos tamaños de letra, botones, márgenes y colores; solo cambia la orientación y la disposición. **No se elimina el vertical** (1200×1920, 5:8, el actual): el software soporta las dos orientaciones y sigue la configuración de pantalla de Windows. Cada ventana decide según la geometría real de su monitor: alto > ancho → lienzo vertical actual (sin ningún cambio visible); ancho ≥ alto → lienzo horizontal nuevo; y reacciona si la orientación cambia en ejecución. **Sin cambio funcional**: ninguna lógica, ruta, controlador ni texto cambia.

## Fuera de alcance (decidido por Cristian)

- Responsive a otras resoluciones o proporciones: por ahora el lienzo es fijo. No se cambia el cálculo de `Escala.factor` más allá de lo necesario para 1920×1200.
- `ui_pyside` (AutoclaveSettings.exe) no se toca.
- No se rediseña el contenido (qué se muestra), solo dónde va.
- Ticket, PDF y correo no cambian.

## Pasos

1. **Base.** `Tema/Escala.qml`: conservar las constantes verticales (1200×1920) y agregar las horizontales (1920×1200) con una propiedad `horizontal` (bool) derivada de la geometría de la ventana; `anchoDiseno`/`altoDiseno` y `factor` salen de la orientación vigente (único lugar del lienzo sigue en `Tema/`). Revisar cómo se calcula `factor` y `altoLienzo` en `Main.qml`, `InstalacionVentana.qml`, `ReposoInstalacionVentana.qml` y `NuevoUsuarioHost.qml` y adaptarlo (sin franjas deformadas). Tamaño por defecto de ventana: 600×960 vertical / 960×600 horizontal (solo para pruebas; en la estación van a pantalla completa). `Componentes/AreaFija.qml`: soporta ambas (área de alto fijo vertical, o `anchoDiseno × altoDiseno` horizontal). `app.py` sigue en `showFullScreen` en el monitor elegido; no tocar la selección de pantalla; la orientación sale de la geometría real de esa pantalla (que refleja la configuración de Windows).
   **Regla de oro:** el vertical queda idéntico al de `dev`. Las pruebas y capturas verticales existentes pasan sin modificarse; lo horizontal se prueba con pruebas y capturas nuevas. Cada pantalla/componente tiene su disposición vertical (intacta) y la horizontal (nueva), elegidas por una propiedad compartida (`states`, bindings condicionales o `Loader` con variante `*Horizontal.qml`); sin duplicar lógica ni cambiar `objectName`.
2. **Inventario.** Antes de editar, listar en `docs/informes/horizontal/inventario.md` las 26 pantallas y los componentes con medidas verticales (anchos 1200, altos 1920, pilas en `Column`, `BarraFases`, `GraficaCiclo`, `PanelTeclado`, `Tema/Teclado*.qml`, modales, `BarraSuperior`, `BarraReinicioBackend`) y la disposición horizontal propuesta de cada una.
3. **Pantallas**, de menos a más compleja, un commit por grupo: intro y arranque, asistente de instalación, Reposo, Preciclo (las dos puertas), Ciclo en curso (con `PanelFinCiclo`, `BarraFases`, `GraficaCiclo` y zoom ZOM), Menú principal, Opciones (todas las secciones), Historial y Detalle de ciclo, Reportes (dashboard y calendario), Entradas/Salidas, Reasignación, Usuarios y Nuevo usuario, Información del equipo, modales y diálogos, teclados en pantalla.
   Reglas de disposición: aprovechar el ancho con dos columnas o con el panel lateral cuando haya un listado largo; las cabeceras y barras (`BarraSuperior`, barra inferior de Ciclo en curso) van a lo ancho; nada se recorta (regla D8-5.4: letra baja hasta `Escala.fuenteMinima`, sin `elide`); zonas táctiles no menores que las actuales.
4. **Colores y tema.** Ni un literal de color fuera de `Tema/` (`tests/test_tema_oscuro.py`); los dos temas se ven bien.
5. **Capturas.** Extender los arneses de `Pruebas/` y `tests/banco/` (T21, LLF, etc.) para poder correrlos también en 1920×1200 y generar una captura horizontal por pantalla en claro y oscuro en `docs/informes/horizontal/capturas/`; las verticales siguen funcionando igual.
6. **Pruebas.** Las pruebas de layout verticales (`tests/test_t21_*`, `test_zom_*`, `test_v8b_textos.py`, `test_tema_oscuro.py` y las que apunten a `Escala`) no se modifican; agregar pruebas horizontales nuevas aparte y una que demuestre que el vertical no cambió (p. ej. mismas medidas de `Escala` con alto > ancho). Suite completa verde; si una prueba ajena falla, anotarla sin ocultarla.
7. **Cierre.** Informe con lo hecho, lo pendiente de banco (táctiles reales, gesto de dos dedos del zoom en el panel horizontal, la orientación física del monitor y su rotación en Windows) y las `DECISIÓN SIN CONFIRMAR`. Merge a `dev` solo si la suite pasa; escribir `CERRADO.txt`.

## Restricciones

- Cero cambios en backend, control, actuadores, alarmas o seguridad. El revisor de seguridad no hace falta, pero un diff fuera de `ui_qml/`, `tests/` y `docs/` debe justificarse.
- Cada pantalla debe seguir mostrando los mismos datos con los mismos `objectName` (las pruebas los usan).
- Sin `Canvas`, `Particles` ni `Effects` nuevos (decisión de la tanda 34).
- Si algo no cabe en 1920×1200 sin recortar, no inventar: anotarlo en el informe con captura y proponer opciones.

## Hecho cuando

Todas las pantallas se ven y se usan en 1920×1200 horizontal, sin franjas ni texto recortado, en los dos temas; el vertical 1200×1920 sigue idéntico; el software elige la orientación según la configuración de pantalla de Windows; suite verde; informe y capturas entregados.

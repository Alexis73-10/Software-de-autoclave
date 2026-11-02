# AJ-01 — notas de implementación

Alcance: solo apariencia de `DeslizadorInicio.qml`; colores nuevos en `Tema/Colores.qml` (`deslizadorPista`, `deslizadorPistaListo`, `deslizadorAcento`, `deslizadorAcentoListo`, `deslizadorBrillo`, `deslizadorBrilloListo`, `deslizadorTexto`, `deslizadorSombraInterior`, `deslizadorNucleo`).

## Decisiones
- Valores exactos de §13; la pista pastel se distingue del fondo blanco de la tarjeta (borde del acento al 45 %), así que NO se subió la saturación (no hay DECISIÓN SIN CONFIRMAR).
- Degradados internos: los de la pista pasan a `desl.ac(alfa)` (mismas opacidades 0,1/0,2/0,1 de antes, sobre el acento nuevo en vez de verdes oscuros mezclados).
- Manija: fondo radial en `deslizadorNucleo` al 90 %/80 % (antes verdes casi negros); borde del `thumb-core` en el núcleo al 20 %.
- Textos de pista: color fijo `deslizadorTexto`, sin sombra ni `layer` (se retiró el MultiEffect de ambos textos).
- Sin cambios: medidas, animaciones, `completado()`, enabled/visible, objectName, opacidad 0,4 deshabilitado.

## Deuda: literales preexistentes sin tocar
- Sombra exterior de la manija: `Qt.rgba(0, 0, 0, 0.5)` (negro).
- Extremos transparentes del barrido: `Qt.rgba(0, 0, 0, 0)`; centro `Qt.rgba(1, 1, 1, 0.8)` y `Qt.rgba(1, 1, 1, 0.8)` del `thumb-inner`.
- Reflejo de la pista: `Qt.rgba(1, 1, 1, 0.1)` / `0`.
- Defaults de componentes internos: `"white"`, `"transparent"`, `"#000000"` (SombraInterior.color), `"transparent"` en anillos y bordes.
- Todas las medidas/opacidades (alfas) siguen como literales en el componente.

## Capturas
`docs/informes/dashboard_reportes/capturas/aj01_{antes,despues}_{reposo,mitad,final}.png`, 1200×1920, pantalla Preciclo (equipo listo, datos vigentes) con el deslizador en reposo, a mitad de recorrido y al final.
- Se generaron con la plataforma real de Windows (`QT_QPA_PLATFORM=windows`, `QT_ENABLE_HIGHDPI_SCALING=0`, ventana sin marco): con `offscreen` los efectos de capa (MultiEffect) no se dibujan y la pista no aparece.
- Mitad y final se fijan moviendo `manijaDeslizadorInicio.x` (no hay arrastre táctil real); el resultado visual es el del arrastre, pero no se dispara `completado()`.
- Script usado (no versionado): derivado del arnés `tests/banco/cap9_capturas_banco.py` (parte preciclo) con `LISTO_PARA_CICLO` en True.

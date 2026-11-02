# Modo oscuro: informe (BORRADOR, paso 8)

Rama `modo-oscuro` (desde `dev` c43b9d0b, 2-nov-2026). Plan: `plan.md`; estado: `estado.md`; riesgo HAZ-OSC-01; requisito REQ-OSC-01.

**No se compiló la entrega; comando: `python tools/entrega/compilar_entrega.py`** (desde `dev` limpio, tras el merge).

## 1. Qué se hizo

- **Mecanismo:** `Tema/Colores.qml` con `oscuro` y cada propiedad `oscuro ? oscuro : claro` (claro = valor exacto de `dev`). Singleton `Autoclave.Apariencia` (`bridge/apariencia_qml.py`), sondeo de `GET /theme` cada 3 s, enlace en las 4 raíces de ventana.
- **Persistencia:** `core/runtime/config_tema.py` (`data/tema.json`, claro por defecto), `GET/PUT /theme` en `rutas/sistema.py` (PUT admin/ingeniero, sin bitácora), selector Tema/Claro/Oscuro en Parámetros del equipo (`fijarTema`), textos es/en.
- **Sin colores fuera de `Tema/`:** conjuntos A (chrome, fondos), B (Preciclo, Ciclo en curso, fases, gráfica, deslizador), C (comunes, modales, teclados, alarmas) y D (menú, sesión, instalación, Opciones). Íconos monocromos con `IconoColor`; fondos con `FondoGradiente`.
- **Pruebas:** `tests/test_tema_oscuro.py` (propiedades, claros contra `dev`, oscuros contra la paleta, alarmas iguales, contraste WCAG de la §8, sin literales, solo Colores nombra el tema, persistencia, `/theme`, QML en vivo).
- Ticket, PDF y correo no cambian (siempre claros). Ninguna lógica lee el tema.
- Estado a la fecha de este borrador: suite completa (paso 6) y capturas (paso 7) pendientes; ver `estado.md`.

## 2. Hallazgos

| ID | Resolución |
|---|---|
| OSC-01 (ALTA) | Claros de `deslizador*` = literales de `dev`; oscuros de la §7; `deslizadorNucleo`/`exitoFondo` claro de la §7. Riesgo de unión con `dashboard-reportes` (ver §4). |
| OSC-02 (MEDIA) | Persistencia en backend al lado del idioma; PUT solo admin/ingeniero, sin bitácora. **Por confirmar** (§4). |
| OSC-03 | Propiedades `velo`, `veloSuave`, `veloFuerte`, `sombra`, `sombraSuave`, igual valor en ambos temas. |
| OSC-04 | Grises locales de Preciclo/Ciclo asignados al token más cercano (`textoPrimario`, `textoSecundario`, `textoGuia`, `bordeDivisor`, `bordeTarjeta`). |
| OSC-05 | Series de la gráfica por posición (`serieGrafica1..3`); `entradas_mostradas.COLORES` queda sin consumidor QML, Python sin cambio. |
| OSC-06 | ~25 íconos oscuros con `Image` pasados a `IconoColor`. |
| OSC-07 | Multicolor: opción A (un solo color) donde fue posible; ver OSC-17/18/20. |
| OSC-08 | `insignia` #08C9F9 claro / #00CCFF oscuro. |
| OSC-09 | `"white"`: texto sobre acción a `textoSobreAccion`; superficies a `fondoSutil`/`fondoTarjeta` caso a caso. |
| OSC-10 | Botones de gradiente fijo (CONFIRMAR, naranja, `peligroFuerte`) con el mismo valor en ambos temas. |
| OSC-11 | Grises sueltos mapeados (`seleccionSutil`, `puertaCerradaFondo`, `fondoSeccion`, `bordeDivisor`, `bordeTarjeta`). |
| OSC-12 | `faseEtiquetaActiva`/aro activo: en claro sin cambio de píxel. |
| OSC-13 | `halo_arranque.png` y `voluta_vapor.png` se conservan sobre el gradiente; **verificar en capturas**. |
| OSC-14 | Arnés `PruebaMovimiento` pasado a `Colores`. |
| OSC-15 | PDF/exportación fuera de alcance, siempre claros. |
| OSC-16 (MEDIA) | Valores oscuros sin texto en la paleta elegidos en el paso 2; **aprobar** (§4). |
| OSC-17 (BAJA) | Conjunto C: `chevron_abajo`, `ojo_ocultar`, `candado` simplificados a un color. Riesgo residual en HAZ-OSC-01. |
| OSC-18 (BAJA) | Conjunto D: igual en Login/CambioClave/NuevoUsuario; candado (`bordeCampo` #33445A) de poco contraste en oscuro; capas de atenuación con `textoNegro` aclaran en oscuro. |
| OSC-19 (BAJA) | `<font color='#808080'>` de `OpcionesParametrosCiclo.qml:209` se conserva (lo exige `test_i4_ingles_qml`); legible en oscuro. |
| OSC-20 (BAJA) | Conjunto B: `Qt.rgba` del deslizador derivados de propiedades (verdes difieren unos puntos en claro); ícono pendiente de `CirculoFaseLiquido` y `chevron_abajo` de Tiempos sin tinte; series por posición. Riesgo residual en HAZ-OSC-01. |

## 3. Diferencias con el mockup

- En claro de las propiedades nuevas se usa siempre el literal de hoy, no la paleta (OSC-01, OSC-12): el mockup solo describe el oscuro.
- Oscuros sin valor en la paleta (OSC-16), sólido en vez de degradado en la fase activa (`faseActivaFin`), IntroArranque con el gradiente de Reposo (no el de FondoApp).
- Íconos multicolor reducidos a un color (OSC-17/18/20).
- Otras diferencias visibles: por completar con las capturas.

## 4. Preguntas abiertas para Cristian

1. **OSC-16:** ¿aprueba los colores oscuros que la paleta no define (`faseEtiqueta` #C9D2DC, `faseActivaFin` #1E5FD9, `faseChorro` #33B4F5, `graficaCursor`/`graficaIconoFase` #8C98A7, `avatarFondo`, `textoSobreAlarmaMedia` #031225)?
2. **OSC-01:** los claros del deslizador son los de `dev`, no los de la §7 (que existen solo en `dashboard-reportes`). ¿Se acepta, o prefiere unir primero `dashboard-reportes`?
3. **OSC-02:** `PUT /theme` lo hacen admin e ingeniero (como el idioma) y no se audita. ¿Se acepta o debe poder cambiarlo cualquier sesión?
4. **Unión con `dashboard-reportes`:** esa rama (por delante de `dev`) toca `Main`, `MenuPrincipal`, `SelectorPeriodo`, `CirculoFaseLiquido`, `DeslizadorInicio`, `PantallaPreciclo` y `Colores.qml`, además de 7 componentes nuevos que no pasaron por este inventario: habrá conflictos y literales de color nuevos que migrar (la prueba (a) los marcará). ¿Cuál se une primero? Además, REQ-OSC-01 deberá renumerarse (esa rama usa REQ-37..50).
5. Aprobar el mapeo de OSC-03/04/10/11 (velos, grises locales y botones fijos con el mismo valor en ambos temas).

## 5. Capturas

PENDIENTE: la llenará el director cuando el agente de capturas termine (paso 7: pantallas críticas en claro y oscuro; comprobar en claro que no hay diferencia con `dev`, y OSC-13, OSC-17/18/20).

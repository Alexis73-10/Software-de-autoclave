# W10 — Pantalla 2 durante la instalación (D10-4)

Rama `tanda-10-w10` (desde `tanda-10`, f73acf6). Sin push.

## Qué se hizo

### D10-4.1 — Reposo con aviso en la pantalla 2
- `ui_qml/app.py`: sin perfil (`requiere_instalacion()`), la puerta 1 sigue abriendo el asistente
  y la puerta 2 abre `ReposoInstalacionVentana.qml` (`_abrir_reposo_instalacion`) en lugar de
  `Main.qml`. Esa ventana no crea `BackendClient` ni puentes con backend, no pide el foco
  (el foco es del asistente) y no instala filtros de standby ni de sesión.
- `qml/ReposoInstalacionVentana.qml` (nuevo): mismo escalado que `Main.qml`/`InstalacionVentana.qml`,
  contiene `Reposo` con `tactil: false` y el aviso `instalacion.aviso_pantalla2`.
- `qml/Pantallas/Reposo.qml`: dos propiedades nuevas, `aviso` (texto bajo la fecha, oculto si
  está vacío) y `tactil` (habilita la `MouseArea`). Por defecto `""` y `true`: el Reposo de
  `Main.qml` se ve y responde igual que antes.
- i18n: `instalacion.aviso_pantalla2` = «Instalación en curso en la pantalla 1» /
  «Installation in progress on screen 1».

### D10-4.2 — Paso al flujo normal al terminar
- Ejecutable único (`exe_unico._lanzador`, el camino del equipo instalado): sin perfil y con dos
  pantallas, lanza el asistente (puerta 1) y la pantalla 2 de Reposo; al terminar el asistente
  (cualquier código) cierra la de Reposo (`_cerrar_reposo_instalacion`: `terminate`, 5 s, `kill`).
  Con código 3 sigue como hoy: backend y las dos pantallas en flujo normal, abiertas por
  `vigilar_pantallas` desde cero — es decir, la puerta 2 llega al flujo normal por el mismo
  mecanismo que la puerta 1 y ninguno de esos lanzamientos cuenta como relanzamiento por caída.
  Si el asistente se cierra sin instalar, la de Reposo también se cierra y no arranca nada
  (igual que hoy). Si la pantalla 2 de Reposo no se puede lanzar, se registra y el asistente sigue.
- `doble_pantalla` (desarrollo, backend aparte): la pantalla 2 de Reposo mira cada 2 s si ya hay
  perfil y, al haberlo, sale con `CODIGO_INSTALACION_TERMINADA`; el vigilante ya trata ese código
  como «terminada, no se relanza ni se cuenta» (TMG-02), igual que la puerta 1.
- Una sola pantalla (`--una-pantalla`): no se lanza la pantalla 2; sin cambios.
- Con perfil válido: ninguna de las dos pantallas cambia.

## Commits
- `d7ac2c3` feat(tanda10-w10): pantalla 2 en Reposo durante la instalación (D10-4)
- (este informe) docs(tanda10-w10): informe W10

## Pruebas

`autoclave.__file__` = `C:\Users\tecni\Documents\codigo_autoclave\.claude\worktrees\agent-a4be92acb8e0b641a\src\autoclave\__init__.py`

Nuevas, `tests/test_w10_pantalla2_instalacion.py` (16):
- app: sin perfil la puerta 2 abre el Reposo de instalación; la puerta 1 sigue con el asistente;
  con perfil válido las dos van al flujo normal; `reposo_sale_solo` (fuera del exe sí, bajo el exe
  no); `revisar_fin_instalacion` sale con código 3 solo con perfil.
- QML offscreen, es y en: el aviso aparece con el texto exacto, `tactil` es `false`, un clic en el
  centro no emite `tocado`, sin avisos QML; genera las capturas. Control manual: con `tactil=true`
  el mismo clic sí emite `tocado` (la prueba no es vacía). El Reposo normal sigue táctil y sin aviso.
- exe: sin perfil con dos pantallas → `ui1, ui2, backend`, la de Reposo en el monitor de la puerta 2,
  cerrada antes de vigilar, y luego puertas 1 y 2 en flujo normal; asistente cancelado → Reposo
  cerrado y nada más; `--una-pantalla` → sin Reposo; perfil válido → sin cambios; fallo al lanzar
  el Reposo → el asistente y el arranque siguen.
- doble_pantalla: dos pantallas que salen con código 3 no se relanzan.

Ajustadas (cambio de comportamiento esperado):
- `test_t9_instalacion.py::test_app_abre_el_asistente_solo_en_la_puerta_1_sin_perfil`: el caso
  `(2, True)` (puerta 2 sin perfil iba al menú) se reemplaza por `(2, False)`; el caso nuevo de la
  puerta 2 sin perfil está en W10.
- `test_p1_lanzador_primer_arranque.py`: los roles lanzados ahora incluyen la pantalla 2 de Reposo
  (`["ui", "ui", "backend"]` y `["ui", "ui"]`); `_Proc` admite `terminate`/`wait(timeout)`.

Corrida (solo módulos tocados y los que los importan):
```
tests/test_w10_pantalla2_instalacion.py tests/test_t9_instalacion.py
tests/test_p1_lanzador_primer_arranque.py tests/test_doble_pantalla.py tests/test_ui_qml_app.py
tests/test_v8b_textos.py tests/test_t8_e1_asistente_texto_final.py tests/test_url_backend_ui_qml.py
tests/test_lanzar_ui_qml.py tests/test_intro_arranque_qml.py tests/test_main_menu_principal_qml.py
tests/test_u2_navegacion_qml.py tests/test_b2_spec_excludes.py tests/test_p1_instalacion_manana.py
tests/test_e2_nombres_familia.py
225 passed in 143.76s (0:02:23)
```

Capturas (offscreen, 600x960): `docs/informes/tanda10/capturas/w10/pantalla2_instalacion_es.png`
y `pantalla2_instalacion_en.png`. Se regeneran con
`W10_CAPTURAS=<carpeta> PYTHONPATH=<worktree>/src python -m pytest tests/test_w10_pantalla2_instalacion.py -k reposo_de_instalacion`.
(En offscreen el reloj sale en la fuente de respaldo porque Tahoma es del sistema; en el equipo se ve
igual que el Reposo actual.)

## DECISIONES SIN CONFIRMAR
1. **Quién cierra la pantalla 2 bajo el ejecutable único.** La cierra el lanzador al terminar el
   asistente, no ella misma al aparecer el perfil: el perfil se escribe al pulsar «Instalar equipo»
   y el asistente sigue abierto con «Instalación completada» hasta «Continuar»; si la pantalla 2
   saliera sola, el monitor 2 quedaría vacío (escritorio) ese rato. Para distinguirlo se usa la
   variable `AUTOCLAVE_EXE_UNICO=1` que el lanzador ya pone a sus hijos (`reposo_sale_solo`).
2. **`doble_pantalla` (desarrollo).** Ahí la puerta 1, al terminar, no pasa al flujo normal (el
   vigilante la da por terminada y pide reiniciar, porque el backend se lanzó aparte y no relee el
   perfil). Se aplica a la pantalla 2 el mismo mecanismo: sale con código 3 y no se relanza. No se
   cambió `vigilar_pantallas`.
3. **Pantalla 2 de Reposo no vigilada.** Durante el asistente no se relanza si se cae (el
   asistente tampoco). Si se cae, el monitor 2 queda vacío hasta terminar la instalación.
4. **Idioma y sondeo.** La ventana usa el singleton `I18n`, que (igual que en el asistente) intenta
   leer `/language` del backend; sin backend esa consulta falla en silencio y queda el idioma local.
   No se agregó ninguna llamada nueva al backend.
5. **Aspecto del aviso.** Blanco, Montserrat medio, tamaño `campoValorTam`, 40 px de diseño bajo la
   fecha, con salto de línea. No hay referencia del diseñador para este aviso.

## PREGUNTAS PARA CRISTIAN
Ninguna: no se tocó lógica de ciclo, estado seguro ni puertas mecánicas («puerta» aquí = pantalla).

## Pendientes
- Verificación visual en el equipo de dos monitores (el aviso con la fuente real y la transición
  al terminar la instalación).

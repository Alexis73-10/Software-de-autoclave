# Informe de Fase 1 — Menú Principal (UI QML)

Plan: `docs/mis_plans/planeacion_menu_principal_ui_qml.md` (v1.2)
Fecha: 2026-10-01
Rama: `dev` (sin commit; D-10 y D-19)
Alcance de esta fase: verificación complementaria de la sección 8 (solo lectura), tema y componentes, galería en `Pruebas/`, retrabajo de D-20 (tarjetas de resumen como botón) e icono de Último ciclo.

---

## 1. Verificación complementaria (sección 8, solo lectura)

### 1.1 MP-12 — Puerta, reinicio de falla y reconocer alarma en la UI QML

| Acción | UI QML hoy | Otras UI | Backend |
|---|---|---|---|
| Abrir / cerrar puerta | Solo en `Pantallas/Ciclo.qml`: botón "Abrir/Cerrar puerta" → `Main.qml` → `comandosPuerta.alternar()` (`bridge/comandos_puerta.py`). `PantallaCicloEnCurso.qml` no tiene acción de puerta. | tkinter | `POST /doors/{name}/open`, `/close` |
| Reinicio de falla | **No existe en ninguna pantalla QML.** `bridge/ui_bridge.py` lo declara "aún no se conecta". | Solo tkinter: `ui/window/main_window.py:618` → `UIServiceBackend.reset_fault()` → `POST /fault/reset`. No existe en la app PySide. | `POST /fault/reset` |
| Reconocer alarma | **No existe en ninguna capa.** | — | No hay endpoint. `POST /cycle/acknowledge` es la confirmación del resultado del ciclo (`ui/cycle/cycle_window.py:743`), no reconocimiento de alarma. |

Además: `PantallaCicloEnCurso.qml` declara la señal `cancelarPulsado()`, pero no está conectada a nada (la cancelación de ciclo desde QML sigue sin existir, D-11).

Conclusión: si se retiran de Home, el reinicio de falla no tiene acceso desde la UI QML (solo desde tkinter, que se elimina con la migración, D-07) y la puerta solo es accesible desde `Ciclo.qml`. Reconocer alarma no existe en el sistema. Decisión pendiente de Cristian (MP-12).

### 1.2 Fuente del contador de alarmas (campana)

`UiBridge.alarms` (`bridge/ui_bridge.py`): `AlarmListModel`, alimentado cada 500 ms desde el caché de `UIServiceBackend.get_alarmas()` (campo `alarms` de `GET /status`). Expone `count`. Es la misma fuente que usa `Ciclo.qml` (`conteoNotificaciones = alarmas.count`). Cuenta todas las alarmas activas, de cualquier nivel (EMERGENCIA, FALLA y ALERTA). `EncabezadoMenu` recibe ese número en `conteoAlarmas` (`< 0` = sin fuente → sin contador, D-17); el enlace a `UiBridge` se hace en la Fase 3.

### 1.3 Fecha en la tabla `ciclos`

`fecha_inicio` y `fecha_fin` se guardan como `datetime.now().isoformat()` (`services/domain/logging/db_manager.py:190` y `:209`): **hora local del equipo, sin zona horaria** (texto ISO-8601 naive, p. ej. `2026-10-01T14:25:03.123456`). Implicaciones para la Fase 2:

- "Ciclos hoy" (desde las 00:00 local) puede calcularse comparando contra la medianoche local en el mismo formato.
- Un ajuste manual del reloj del equipo altera qué ciclos cuentan como "hoy" (dato de presentación, no de control; la regla C-01 no aplica).
- `resultado` queda `NULL` si el proceso se interrumpe antes de `cerrar_ciclo`.

### 1.4 Alto del marco del diseñador y desplazamiento de 4 px — CONTRADICE EL PLAN

- El marco del diseñador en `Ciclo.qml` es **1196 × 1917**, no 1914: lo indica el comentario de cabecera de `Ciclo.qml` ("Referencia: images/pantalla_ciclo_sin_grafica.png (1196 x 1917)") y lo confirman las dos referencias en disco (`images/pantalla_ciclo_sin_grafica.png` y `images/pantalla_ciclo_con_grafica_editada.png`, ambas 1196 × 1917).
- En ancho el recorte cuadra: 1188 + 2 × 4 = 1196. En alto no: 1906 + 2 × 4 = 1914 ≠ 1917 (faltan 3 px; el recorte vertical no sería simétrico de 4 px, o el v3 no sale de ese mismo marco).
- Tampoco cuadra en x contra la barra inferior de `Ciclo.qml`: la barra del v3 (§5) desplazada +4 queda en x 43–1171 con separadores en 356 y 843; la de `Ciclo.qml` está en x 33–1163 con separadores en 347 y 834 (diferencia de 9–10 px).
- No se puede resolver sin el v3: `docs/mockups/menu_principal_v3.png` **sigue sin estar en el repositorio**.
- Afecta solo a la ubicación absoluta en pantalla (Fase 3). Los componentes de la Fase 1 usan medidas propias (anchos, altos, radios, tamaños de fuente), no posiciones absolutas del v3.

---

## 2. Entregables de la Fase 1

| Archivo | Tipo | Contenido |
|---|---|---|
| `src/autoclave/ui_qml/qml/Tema/Colores.qml` | modificado (único archivo existente tocado) | Tokens `menuVerde #009535`, `menuVerdeTexto #0D8C2C`, `menuAzul #0361EC`, `menuNaranja #FF9720`, `menuNaranjaTexto #F26500`, `menuMorado #9827D1`, `bordeDivisor #E6E6E6` |
| `src/autoclave/ui_qml/assets/iconos/mono/ciclos_totales.svg` y `color/ciclos_totales.svg` | nuevo | Icono PROVISIONAL de ciclos totales (flechas circulares con marcas de conteo), SVG Tiny 1.2 (solo `path`, sin arcos `A`, sin CSS, texto, filtros ni degradados). Para que el diseñador entregue el definitivo. |
| `src/autoclave/ui_qml/qml/Componentes/IconoColor.qml` | nuevo | Icono SVG pintado de un color exacto (el SVG como máscara de un rectángulo del color) |
| `src/autoclave/ui_qml/qml/Componentes/TarjetaMenu.qml` | nuevo | Tarjeta de acción: título, descripción, icono con aro (gris fino o de acento), borde de acento opcional, valor opcional arriba a la derecha, flecha opcional; señal `pulsada`; estados normal, presionado y deshabilitado |
| `src/autoclave/ui_qml/qml/Componentes/TarjetaResumen.qml` | nuevo | Tarjeta del resumen: aro 106 con icono, rótulo, valor que se reduce para caber (mínimo 20 de mockup), subrótulo, ranura de contenido propio; botón (D-20) con señal `pulsada`, presionado y deshabilitado, sin flecha; opción `iconoIncluyeAro` |
| `src/autoclave/ui_qml/qml/Componentes/DetalleUltimoCiclo.qml` | nuevo | Contenido de Último ciclo: fecha y hora, "Programa:" y "Resultado:" con valor en negrita y color |
| `src/autoclave/ui_qml/qml/Componentes/EncabezadoMenu.qml` | nuevo | Logo, hora y fecha (meses de `es.json` → `fecha.meses`, sin configuración regional), campana con insignia (`conteoAlarmas`), engranaje con señal `ajustesPulsado` |
| `src/autoclave/ui_qml/qml/Componentes/BarraInferiorMenu.qml` | nuevo | Barra 1128 × 139: Salir a la izquierda (deshabilitado, D-12), Home a la derecha (inactivo), separadores en x 313 y 800 de la barra, versión abajo a la derecha |
| `src/autoclave/ui_qml/qml/Pruebas/GaleriaMenuPrincipal.qml` | nuevo | Galería con datos de ejemplo de todos los estados |
| `src/autoclave/ui_qml/prueba_menu_principal.py` | nuevo | Lanzador de la galería; `--captura archivo.png` guarda una captura de 1200 × 1920 |
| `tests/test_menu_principal_componentes_qml.py` | nuevo | 10 pruebas (ver §5) |

Los componentes son genéricos: no leen backend ni `es.json` (salvo la tabla de meses del encabezado) y solo emiten señales. Todas las medidas están en px del mockup y pasan por `m(v) = v * escala` (D-18); quien los usa pasa `escala = ancho / 1196`.

Revisión visual:

```
python -m autoclave.ui_qml.prueba_menu_principal                        (ventana 600 x 960)
python -m autoclave.ui_qml.prueba_menu_principal --captura galeria.png  (1200 x 1920)
```

Contenido de la galería (sin títulos de pantalla ni anclaje de barra, que son de la Fase 3):

- Tarjetas de menú: normal con borde verde (Iniciar sesión), deshabilitada (Historial), presionada (Reportes), título y descripción largos elididos (Información), secado sin valor "—" y secado con valor largo "120.5 min" (sin flecha).
- Tarjetas de resumen: valor largo reducido (12345678), sin dato "—", normal, contenido propio (Último ciclo), presionada y deshabilitada.
- Encabezado con insignia en 2 y barra inferior.

---

## 3. Retrabajo solicitado tras la primera entrega

### 3.1 Tarjeta de resumen como botón (D-20)

`TarjetaResumen` emite `pulsada()`, tiene estado presionado (capa negra al 8 %, igual que `TarjetaMenu`) y deshabilitado (opacidad 0.4, sin respuesta táctil), sin flecha. La galería muestra una presionada ("CICLOS HOY") y una deshabilitada ("CICLOS TOTALES"). La prueba `test_tarjetas_de_menu_y_resumen_son_botones` comprueba que la habilitada emite la señal y la deshabilitada no; se verificó que falla si la tarjeta deja de emitir. Que las cuatro queden deshabilitadas hasta que existan sus destinos (MP-14) se aplica al componer la pantalla (Fase 3).

### 3.2 Icono de Último ciclo

En la primera entrega la galería usaba `historial.svg` (reloj con flecha). **No era el del mockup**: el mockup del diseñador (`docs/diseno/referencias/pantallas_1080x1920/pantalla_02_menu_principal_1080x1920.png`, "ULTIMO CICLO") muestra un triángulo de play dentro de un aro azul, y según Cristian el v3 conserva ese triángulo. El v3 no está en el repo, así que la comprobación se hizo contra mockup-01.

Corregido: ahora usa `mono/reproducir.svg` (triángulo de play). Ese SVG, igual que `iniciar_ciclo.svg`, trae su propio aro (círculo de diámetro 40 en el viewBox de 48); dibujar otro aro encima daba un aro doble. Se agregó a `TarjetaResumen` la opción `iconoIncluyeAro`: no dibuja el aro y agranda el icono (× 48/40) para que su aro mida los mismos 106. Diferencia menor: el trazo del aro del SVG queda en unos 4.3 px de mockup frente a los 5 del aro dibujado en las otras tarjetas.

`historial.svg` también trae su propio aro. En la tarjeta de menú Historial se ve un aro fino interior dentro del aro gris; queda para revisar contra el v3 en la Fase 3 (allí el aro del SVG se pintaría de morado con `IconoColor`, no gris como en mockup-01).

---

## 4. Decisiones y diferencias con el plan y el tema

1. Tokens de color: ninguno de los colores del mockup coincide con un token existente (`#0361EC` ≠ `accionPrimario #1168F6`; `#FF9720` ≠ `advertencia #FF9933`). Se agregaron tokens nuevos con prefijo `menu`. Confirmar con el diseñador si unifica.
2. Tipografía: los estilos de `Tipografia.qml` no coinciden con el v3: `tarjeta_titulo` es 26 (v3: 28.75 en fila 1, 25 en fila 2) y `tarjeta_descripcion` es 21 (v3: 24 en fila 1, 21 en fila 2). Coinciden `kpi_valor` (46) con el valor de resumen y el de secado. Se usan los tamaños del v3 con `m()` y la familia `Tipografia.familia` (Montserrat).
3. `TarjetaContenido` (radio 28) no se usa: las tarjetas del v3 llevan radio 26 (menú) y 24 (resumen).
4. Color exacto de iconos: `colorization` de `MultiEffect` (el método de `Ciclo.qml`) da un tono aproximado (`#009535` sale `#009E38`). `IconoColor` usa el SVG como máscara y el color sale idéntico al token.
5. `MultiEffect` no se dibuja con `QT_QPA_PLATFORM=offscreen` (backend de software; probado también con d3d11, d3d12 y opengl). Las pruebas automáticas comprueban geometría y comportamiento, no color. Las capturas usan la plataforma real con una ventana sin marco (Windows recorta al monitor las ventanas con marco) y se reducen al tamaño lógico si el monitor tiene escala (125 % en este PC).
6. Disposición interna de las tarjetas PROVISIONAL, tomada de mockup-01 (aro arriba a la izquierda, título y descripción abajo, flecha abajo a la derecha) hasta medirla sobre el v3.
7. Presionado: capa negra al 8 %. Deshabilitado: opacidad 0.4 (convención ya usada en `Ciclo.qml`). Ambos provisionales, pendientes del diseñador.
8. Barra inferior: Salir deshabilitado y atenuado (D-12). Home inactivo pero sin atenuar, porque es la pantalla actual (pendiente del diseñador).
9. Encabezado: geometría copiada del encabezado inline de `Ciclo.qml` (marco de 1196). La insignia usa el color medido en `Ciclo.qml` (`#08C9F9`), que no es token.
10. Deuda técnica: el encabezado y la barra inferior quedan ahora en tres copias (`Ciclo.qml`, `PantallaCicloEnCurso.qml` y los componentes del menú). No se refactorizan (D-19); `BarraSuperior.qml` y `BarraInferior.qml` no coinciden con el mockup.

---

## 5. Pruebas

`tests/test_menu_principal_componentes_qml.py` (galería cargada a 1200 × 1920 en subproceso, offscreen):

- `test_sin_avisos_qml`: cero avisos del motor QML.
- `test_tarjetas_con_medidas_del_mockup`: anchos y altos de §5 escalados con `m()` (menú 716/350/349 × 320; resumen 230/293/206/308 × 330).
- `test_encabezado_y_barra_inferior`: 1196 × 177 y 1128 × 139.
- `test_estados`: opacidad 1.0 / 0.4 y estado presionado en tarjetas de menú y de resumen.
- `test_tarjetas_de_menu_y_resumen_son_botones`: la habilitada emite `pulsada`, la deshabilitada no (menú y resumen).
- `test_ningun_texto_desborda_su_tarjeta`: todo texto dentro de su tarjeta y su contenido dentro de su caja (se verificó que falla si se quita la reducción automática del valor).
- `test_campana_salir_y_home`: insignia visible con conteo > 0; Salir deshabilitado; Home inactivo.
- `test_fecha_con_mes_de_la_tabla_propia`: fecha `D mmm - AAAA` con mes de la tabla propia.
- `test_icono_ciclos_totales_es_svg_tiny` (mono y color): `baseProfile="tiny"`, `version="1.2"`, solo `svg` y `path`, sin arcos.

Suite completa: `python -m pytest` → ver §7.

---

## 6. Pendientes

De Cristian:

- MP-11: ¿"Tiempo adicional de secado" es `secado.tiempo_secado` o un parámetro nuevo?
- MP-12: con el resultado de §1.1, ¿se acepta que el reinicio de falla quede sin acceso desde la UI QML por ahora?
- MP-14: destinos de las tarjetas del resumen.
- Copiar `menu_principal_v3.png` a `docs/mockups/` y decidir el desplazamiento del marco (§1.4) antes de la Fase 3.
- D-19: archivos compartidos con cambios de otro trabajo (pregunta en §6.1).
- D-18 pide marcar como reemplazadas las secciones de `planeacion_menu_principal.md` (v0.3); no se tocó ese documento.

### 6.1 Pregunta D-19: archivos con cambios sin commit de otro trabajo

Las Fases 2 y 3 necesitan editar archivos que comparte otro trabajo en curso en el mismo árbol. Estado al 2026-10-02, rama `dev`, último commit `960647f`:

| Archivo | Lo necesita | Cambios ajenos sin commit |
|---|---|---|
| `src/autoclave/services/domain/logging/db_manager.py` | Fase 2: consulta de solo lectura para `GET /cycle/summary` | Sí, pendientes |
| `src/autoclave/backend/server.py` | Fase 2: endpoint `GET /cycle/summary` | Hoy no; tuvo cambios ajenos durante la sesión, ya confirmados |
| `src/autoclave/ui_qml/assets/textos/es.json` | Fase 3: textos de la pantalla (títulos, rótulos, aviso "Sin conexión con el equipo") | Hoy no; tuvo cambios ajenos el 2026-10-01, ya confirmados |
| `src/autoclave/ui_qml/qml/Main.qml` | No se toca (Fase 4 diferida) | Hoy no |

Como el otro trabajo sigue activo, cualquiera de estos archivos puede volver a tener cambios ajenos cuando llegue el momento de editarlo.

`src/autoclave/ui_qml/qml/Tema/Colores.qml` también figura como modificado, pero todos sus cambios son de este trabajo (los tokens `menu*` y `bordeDivisor`).

Pregunta: para cumplir D-19 en `src/autoclave/services/domain/logging/db_manager.py`, `src/autoclave/backend/server.py` y `src/autoclave/ui_qml/assets/textos/es.json`, ¿qué prefieres?

- a) Editar sobre el estado actual y, al hacer commit, incluir solo los bloques de este trabajo (`git add -p`), dejando los cambios ajenos sin commit.
- b) Esperar a que el otro trabajo haga commit de esos archivos antes de editarlos.
- c) Poner el código nuevo en archivos propios (por ejemplo, la consulta del resumen en un módulo nuevo en vez de `db_manager.py`, y los textos del menú fuera de `es.json`) para no tocar los archivos compartidos. Esta opción se aparta del patrón actual del proyecto.

### 6.2 Del diseñador

- SVG definitivos de usuario, ciclos totales y secado.
- Estados presionado y deshabilitado de las tarjetas (de menú y de resumen).
- Aspecto de la celda central vacía de la barra inferior y del estado de Home en el propio menú.
- Unificación de los tokens de color y de los estilos de tipografía de tarjetas.

## 7. Resultado de la suite

`python -m pytest` al cerrar el retrabajo (2026-10-01): **1419 passed**, 0 fallos (6 avisos de deprecación preexistentes en `test_storage.py`). Línea base al iniciar la Fase 1: 1291 passed; la diferencia incluye las 10 pruebas de este trabajo y pruebas agregadas en paralelo por otro trabajo en curso en el mismo árbol.

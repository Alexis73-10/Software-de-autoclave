# Informe de contexto: Opciones > Parámetros del ciclo y Sensores de temperatura (capa PySide/QML y backend)

Fecha del análisis: 2026-10-02. Repositorio: `C:\Users\tecni\Documents\codigo_autoclave`, rama `dev` (HEAD `960647f`).

Este informe complementa a `INFORME_OPCIONES_POST_LOGIN.md` [NUEVO SIN TRACKEAR], que sigue vigente; no se repite su contenido (sesión, login, standby, persistencia de `global_params.json`, hallazgos de contraseñas y del backend en `0.0.0.0`). Cuando un hecho ya está allí, solo se remite.

Convenciones:

- Etiquetas de origen: [COMMITEADO] (en HEAD de `dev` y sin cambios en el árbol de trabajo), [MODIFICADO SIN COMMIT], [NUEVO SIN TRACKEAR], y [RAMA feature/roles-sensor-temperatura] para contenido que solo existe en esa rama.
- Las rutas de código son relativas a `src/autoclave/` salvo que empiecen por `docs/`, `tests/`, `Hardware/` o el nombre de un archivo de la raíz.
- Abreviaturas de perfiles JSON: FB = `cycles/factory/bowe_dick.json`, F2 = `cycles/factory/instrumental_134.json`, UB = `cycles/user/bowe_dick.json`, U2 = `cycles/user/instrumental_134.json`, U3 = `cycles/user/instrumental_121.json`. Los cinco están [COMMITEADO].
- Ninguna afirmación sobre las imágenes del diseño se toma como dato real; los valores que muestran son ilustrativos, como indica el pedido.

---

## 0. Estado del repositorio y ramas

### 0.1 Árbol de trabajo de `dev`

- Archivos de este alcance [MODIFICADO SIN COMMIT]: `backend/server.py` (solo agrega `/cycle/summary` y `/cycle/history/{id}/graph`, líneas 332-392; no toca rutas de parámetros), `ui_pyside/main_window.py` (registra `nuevo_usuario` y el mecanismo `oculta_marco`), `ui_pyside/views/admin_menu.py` (opción "Nuevo usuario" solo admin), `services/domain/logging/db_manager.py`, `ui_qml/bridge/ui_bridge.py`, varias pantallas QML.
- Archivos de este alcance [NUEVO SIN TRACKEAR]: `ui_pyside/services/roles.py`, `ui_pyside/views/nuevo_usuario/` (vista QQuickWidget), `ui_qml/controllers/login_controller.py`, `ui_qml/qml/Componentes/VentanaFlotante.qml`, `TarjetaMenu.qml`, `BarraInferiorMenu.qml`, `EncabezadoMenu.qml`, `ui_qml/qml/Pantallas/MenuPrincipal.qml`, `NuevoUsuario.qml`, las tres imágenes del diseño en `images/opciones_*_comparativo.png`, y `INFORME_OPCIONES_POST_LOGIN.md`.
- Sin cambios [COMMITEADO]: `core/managers/cycle_manager.py`, los cinco perfiles JSON, `ui_pyside/views/params_ciclo/params_ciclo.py`, `services/domain/logging/cycle_params_audit.py`, `sensor_calibration_audit.py`, todas las fases de `state_machine/cycle_phases/`, `core/runtime/status.py`, `hal/measures/converters.py`, `config/instances/*.yaml`, `config/models/*.yaml`.

### 0.2 Ramas y worktrees locales

- `feature/roles-sensor-temperatura` (worktree en `.worktrees/roles-sensor-temperatura`): 16 commits sobre `dev`, del 2026-09-02 al 2026-09-08, último `87fca2f`. Base común `3a2e51c`; `dev` tiene 30 commits que la rama no tiene. Diferencia: 29 archivos, +2092/-54 líneas. Detalle en la sección D.1. El worktree tiene cambios sin commit, pero solo en `build/` y `src/autoclave.egg-info/` (artefactos de empaquetado, sin relevancia).
- `worktree-anuncios-voz` (worktree en `.claude/worktrees/anuncios-voz`): audio. Toca `backend/server.py` (+55) y `protocolo_fallo.py` (+3) para anuncios; no toca parámetros ni roles de sensor. Incluye `assets/audio/es/emg_sensor_ausente.wav`, relevante solo como anuncio de la emergencia `SENSOR_AUSENTE`.
- `fix/orden-descompresion-secado`: sin commits por delante de `dev`.
- `claude/competent-morse-801d88`: commits antiguos de puertas y `global_params.json`; sin relación con este alcance.
- `main`: 25 commits por detrás de `origin/main` y por detrás de `dev`; no aporta nada a este alcance.

### 0.3 Stashes

- `stash@{0}` (sobre `feat/brecha-presion-y-tolerancia-desconexion`): logs, `.pyc`, `data/last_shutdown.json` y una línea de `protocolo_fallo.py`. Sin relevancia.
- `stash@{1}` (WIP sobre `488b1cd`, 2026-08-03): toca `params_ciclo.py` (+43), perfiles JSON y `esterilizacion.py`. El cambio de `params_ciclo.py` (reemplazar la escritura directa del JSON por `PATCH /cycle/parameter`) ya está incorporado en `dev` (`params_ciclo.py:313-334`); el stash es obsoleto para este alcance.
- `stash@{2}`: logs y `.pyc` de antes de un merge a `main`. Sin relevancia.

---

## A. Parámetros del ciclo

### A.1 Fases reales en el código

Secuencia ejecutada por `CicloState` (`state_machine/states/ciclo.py`, importaciones de fases en las líneas 21-28) [COMMITEADO]:

1. PRECALENTAMIENTO, `cycle_phases/precalentamiento.py`, lee la sección JSON `precalentamiento`.
2. PRE_VACIO, `cycle_phases/prevacio.py`, lee `prevacio`.
3. CALENTAMIENTO, `cycle_phases/calentamiento.py`, lee `calentamiento`. Contiene internamente la antigua estabilización (ESTABLE_PREESTERILIZACION); no existe una fase de estabilización separada.
4. ESTERILIZACION, `cycle_phases/esterilizacion.py`, lee `esterilizacion` y `globals.F0`/`globals.F0_objetivo`.
5. DESCOMPRESION, `cycle_phases/descompresion.py`, lee `descompresion` y sus subsecciones `modo_1` a `modo_5`.
6. SECADO, `cycle_phases/secado.py`, lee `secado`.

Módulos que no son fases del flujo normal: `protocolo_fallo.py` (se ejecuta ante falla y también lee `descompresion.modo`, `modo_N.timeout` y `modo_3.presion_cambio`, líneas 78, 112 y 129) y `valvula_reposo.py`.

Secciones del JSON que no corresponden a una fase:

- `globals`: la leen `CicloState` (`ciclo.py:175-178`, presión de chaqueta), `PreparacionState` (`preparacion.py:173-174`), `PreparadoState` (`preparado.py:95-96`), `ControlLoop` (`control_loop.py:209`, F0) y `EsterilizacionFase` (`esterilizacion.py:170-171`).
- `finalizacion`: la lee `CicloState._mantener_apertura_automatica()` (`ciclo.py:256-280`).
- `estabilizacion` (en FB, UB, U2 y U3; no en F2): ningún código la lee. Búsqueda de `tiempo_estabilizacion`, `rango_temperatura_estabilizacion` y de la sección: cero resultados en `.py`. Es una sección huérfana de la fase eliminada. U3 conserva `temperatura_estabilizacion = 134.0` en un programa de 121 °C.
- `despresurizacion` (con tres parámetros en FB; vacía en UB, U2 y U3; ausente en F2): ningún código la lee.

Parámetros sin consumidor en el código (búsqueda en `.py` y `.qml`, cero resultados): `globals.ciclos_multiples` y `globals.enfriar_chaqueta_secado`.

Correspondencia con las fases del diseño (Precalentamiento, Vacío, Calentamiento, Esterilización, Descompresión, Secado): coincide con las seis fases reales si "Vacío" es `prevacio`. Las secciones `globals` y `finalizacion` contienen parámetros editables que el diseño no ubica en ninguna fase (pregunta 13).

### A.2 Metadatos disponibles por parámetro

Cada hoja del JSON tiene solo estas claves: `value`, `type`, `unit`, `min`, `max` (verificado sobre los cinco perfiles con un recorrido de todas las hojas). En consecuencia:

- Etiqueta visible: NO IMPLEMENTADO. No hay campo `label` en el JSON ni claves de parámetros en `ui_qml/assets/textos/es.json`. La UI PySide genera el nombre a partir de la clave interna (`params_ciclo.py:508-509`, `_format_param_name`: reemplaza `_` por espacio y capitaliza). El dominio QML solo nombra `temperatura_esterilizacion` y `tiempo_esterilizacion` (`ui_qml/domain/pantalla_ciclo.py`), para la pantalla de ciclo, no como catálogo de etiquetas.
- Paso (incremento): NO IMPLEMENTADO. No existe campo `step`. La UI PySide fija un decimal para todos los `float` (`params_ciclo.py:230`) y paso implícito de 1 para `int`.
- Número de decimales por parámetro: NO IMPLEMENTADO como metadato.
- Valor por defecto: NO IMPLEMENTADO como campo. Ver sección B.
- Tipo: presente salvo en los 20 parámetros de pulsos de `prevacio` (`conteo_pulso_*`, `presion_*_pulso_*`, `tiempo_adicional_*`), que no traen `type`; `Cycle.set_param` los trata como `int` por defecto (`core/managers/cycle_manager.py:54`) y la UI PySide también (`params_ciclo.py:218`).
- Rango: presente en todos los no booleanos. Es el único rango que existe; no hay rango de seguridad independiente en código. Los límites del modelo de equipo (`config/models/solids.yaml`, `limits`: presión 1-400 kPa, temperatura 0-200 °C) no se consultan al validar parámetros: búsqueda de `max_kpa` y `limits` en `.py` sin uso para esto (NO DETERMINADO si los usa otro módulo; no apareció en la búsqueda de `get_param`/`set_param`).
- Unidades: textos libres e inconsistentes entre perfiles: `sec` en F2 y en `descompresion` de todos los perfiles, `seg` en el resto; `°C`, `kPa`, `min`, `%`, `°C/min`, `kPa/min`, cadena vacía. `calentamiento.rango_calentamiento` declara `kPa`, pero según `CLAUDE.md` (sección de calentamiento, función `_duty_por_sobrepaso`) se usa también como distancia "unidades pasado el objetivo" en temperatura; NO DETERMINADO si la unidad declarada es correcta.

### A.3 Listado completo de parámetros editables por sección

Fuente: recorrido de las hojas de los cinco perfiles. "Editable" significa hoy: toda hoja con `value` es editable por `PATCH /cycle/parameter` (`backend/server.py:642-665`) y por la UI PySide si el programa es de usuario. El orden es el del JSON. "ausente" indica que la clave no existe en ese perfil.

#### Sección `globals`

- `globals.F0`: unidad «sin unidad», tipo bool, sin rango (booleano). Valores: FB=False; F2=False; UB=False; U2=False; U3=False.
- `globals.F0_objetivo`: unidad «min», tipo float, mín 0, máx 60. Valores: FB=12; F2=12; UB=12; U2=12; U3=12.
- `globals.ciclos_multiples`: unidad «sin unidad», tipo bool, sin rango (booleano). Valores: FB=True; F2=True; UB=True; U2=True; U3=True.
- `globals.enfriar_chaqueta_secado`: unidad «sin unidad», tipo bool, sin rango (booleano). Valores: FB=False; F2=False; UB=False; U2=False; U3=False.
- `globals.presion_chaqueta`: unidad «kPa», tipo int, mín 0, máx 400. Valores: FB=300; F2=300; UB=350; U2=350; U3=250.
- `globals.rango_presion_chaqueta`: unidad «kPa», tipo int, mín 0, máx 100. Valores: FB=50; F2=50; UB=25; U2=25; U3=25.

#### Sección `precalentamiento`

- `precalentamiento.tiempo_precalentamiento`: unidad «min», tipo int, mín 0, máx 3600. Valores: FB=0; F2=0; UB=0; U2=0; U3=0.
- `precalentamiento.presion_precalentamiento`: unidad «kPa», tipo int, mín 0, máx 1000. Valores: FB=350; F2=200; UB=350; U2=350; U3=250.
- `precalentamiento.timeout_precalentamiento`: unidad «min», tipo int, mín 0, máx 3600. Valores: FB=10; F2=10; UB=1; U2=10; U3=10.

#### Sección `prevacio`

- `prevacio.conteo_pulso_a`: unidad «vacía», tipo sin "type" (set_param lo trata como int), mín 0, máx 100. Valores: FB=4; F2=4; UB=4; U2=4; U3=4.
- `prevacio.presion_alta_pulso_a`: unidad «kPa», tipo sin "type" (set_param lo trata como int), mín 0, máx 1000. Valores: FB=160; F2=80; UB=140; U2=140; U3=140.
- `prevacio.tiempo_adicional_alto_a`: unidad «seg», tipo sin "type" (set_param lo trata como int), mín 0, máx 3600. Valores: FB=0; F2=0; UB=0; U2=0; U3=0. Metadatos (unidad/tipo/rango) distintos entre perfiles.
- `prevacio.presion_baja_pulso_a`: unidad «kPa», tipo sin "type" (set_param lo trata como int), mín 0, máx 1000. Valores: FB=50; F2=30; UB=20; U2=20; U3=20.
- `prevacio.tiempo_adicional_bajo_a`: unidad «seg», tipo sin "type" (set_param lo trata como int), mín 0, máx 3600. Valores: FB=0; F2=0; UB=0; U2=0; U3=0. Metadatos (unidad/tipo/rango) distintos entre perfiles.
- `prevacio.conteo_pulso_b`: unidad «vacía», tipo sin "type" (set_param lo trata como int), mín 0, máx 100. Valores: FB=0; F2=0; UB=0; U2=0; U3=0.
- `prevacio.presion_alta_pulso_b`: unidad «kPa», tipo sin "type" (set_param lo trata como int), mín 0, máx 1000. Valores: FB=160; F2=160; UB=160; U2=160; U3=160.
- `prevacio.tiempo_adicional_alto_b`: unidad «seg», tipo sin "type" (set_param lo trata como int), mín 0, máx 3600. Valores: FB=0; F2=0; UB=0; U2=0; U3=0. Metadatos (unidad/tipo/rango) distintos entre perfiles.
- `prevacio.presion_baja_pulso_b`: unidad «kPa», tipo sin "type" (set_param lo trata como int), mín 0, máx 1000. Valores: FB=110; F2=110; UB=30; U2=30; U3=30.
- `prevacio.tiempo_adicional_bajo_b`: unidad «seg», tipo sin "type" (set_param lo trata como int), mín 0, máx 3600. Valores: FB=0; F2=0; UB=0; U2=0; U3=0. Metadatos (unidad/tipo/rango) distintos entre perfiles.
- `prevacio.conteo_pulso_c`: unidad «vacía», tipo sin "type" (set_param lo trata como int), mín 0, máx 100. Valores: FB=0; F2=0; UB=0; U2=0; U3=0.
- `prevacio.presion_alta_pulso_c`: unidad «kPa», tipo sin "type" (set_param lo trata como int), mín 0, máx 1000. Valores: FB=160; F2=160; UB=160; U2=160; U3=160.
- `prevacio.tiempo_adicional_alto_c`: unidad «seg», tipo sin "type" (set_param lo trata como int), mín 0, máx 3600. Valores: FB=0; F2=0; UB=0; U2=0; U3=0. Metadatos (unidad/tipo/rango) distintos entre perfiles.
- `prevacio.presion_baja_pulso_c`: unidad «kPa», tipo sin "type" (set_param lo trata como int), mín 0, máx 1000. Valores: FB=110; F2=110; UB=110; U2=110; U3=110.
- `prevacio.tiempo_adicional_bajo_c`: unidad «seg», tipo sin "type" (set_param lo trata como int), mín 0, máx 3600. Valores: FB=0; F2=0; UB=0; U2=0; U3=0. Metadatos (unidad/tipo/rango) distintos entre perfiles.
- `prevacio.conteo_pulso_d`: unidad «vacía», tipo sin "type" (set_param lo trata como int), mín 0, máx 100. Valores: FB=0; F2=0; UB=0; U2=0; U3=0.
- `prevacio.presion_alta_pulso_d`: unidad «kPa», tipo sin "type" (set_param lo trata como int), mín 0, máx 1000. Valores: FB=160; F2=160; UB=160; U2=160; U3=160.
- `prevacio.tiempo_adicional_alto_d`: unidad «seg», tipo sin "type" (set_param lo trata como int), mín 0, máx 3600. Valores: FB=0; F2=0; UB=0; U2=0; U3=0. Metadatos (unidad/tipo/rango) distintos entre perfiles.
- `prevacio.presion_baja_pulso_d`: unidad «kPa», tipo sin "type" (set_param lo trata como int), mín 0, máx 1000. Valores: FB=110; F2=110; UB=110; U2=110; U3=110.
- `prevacio.tiempo_adicional_bajo_d`: unidad «seg», tipo sin "type" (set_param lo trata como int), mín 0, máx 3600. Valores: FB=0; F2=0; UB=0; U2=0; U3=0. Metadatos (unidad/tipo/rango) distintos entre perfiles.
- `prevacio.timeout_bajo`: unidad «min», tipo int, mín 0, máx 3600. Valores: FB=10; F2=10; UB=10; U2=10; U3=10.
- `prevacio.timeout_alto`: unidad «min», tipo int, mín 0, máx 3600. Valores: FB=10; F2=10; UB=10; U2=10; U3=10.

#### Sección `calentamiento`

- `calentamiento.temperatura_calentamiento`: unidad «°C», tipo float, mín 100, máx 140. Valores: FB=134.0; F2=134.0; UB=134.0; U2=134.0; U3=121.0.
- `calentamiento.presion_add_calentamiento`: unidad «kPa», tipo float, mín 0, máx 100. Valores: FB=11.0; F2=11.0; UB=11.0; U2=11.0; U3=11.0.
- `calentamiento.timeout_calentamiento`: unidad «min», tipo int, mín 1, máx 999. Valores: FB=60; F2=60; UB=60; U2=60; U3=60.
- `calentamiento.factor_calentamiento`: unidad «%», tipo int, mín 0, máx 100. Valores: FB=50; F2=50; UB=50; U2=50; U3=50.
- `calentamiento.rango_calentamiento`: unidad «kPa», tipo float, mín 0, máx 30. Valores: FB=2.0; F2=2.0; UB=2.0; U2=2.0; U3=2.0.
- `calentamiento.tasa_calentamiento`: unidad «°C/min», tipo float, mín 0, máx 100. Valores: FB=50.0; F2=50.0; UB=50.0; U2=50.0; U3=50.0.
- `calentamiento.tasa_presion`: unidad «kPa/min», tipo float, mín 0, máx 300. Valores: FB=100.0; F2=100.0; UB=100.0; U2=100.0; U3=100.0.
- `calentamiento.tiempo_estable_preesterilizacion`: unidad «seg», tipo int, mín 0, máx 180. Valores: FB=3; F2=3; UB=3; U2=3; U3=3.
- `calentamiento.intervalo_segmentos_calor`: unidad «seg», tipo int, mín 0, máx 30. Valores: FB=2; F2=2; UB=2; U2=2; U3=2.
- `calentamiento.escape_lento_on`: unidad «seg», tipo int, mín 0, máx 1000. Valores: FB=1; F2=1; UB=1; U2=1; U3=1.
- `calentamiento.escape_lento_off`: unidad «seg», tipo int, mín 0, máx 1000. Valores: FB=0; F2=0; UB=0; U2=0; U3=0.
- `calentamiento.escape_rapido_on`: unidad «seg», tipo int, mín 0, máx 1000. Valores: FB=0; F2=0; UB=0; U2=0; U3=0.
- `calentamiento.escape_rapido_off`: unidad «seg», tipo int, mín 0, máx 1000. Valores: FB=10; F2=10; UB=10; U2=10; U3=10.
- `calentamiento.rango_temp_estabilizacion`: unidad «°C», tipo float, mín 0, máx 10. Valores: FB=1.0; F2=1.0; UB=1.0; U2=1.0; U3=1.0.
- `calentamiento.timeout_recuperacion_estabilizacion`: unidad «min», tipo int, mín 1, máx 60. Valores: FB=5; F2=5; UB=5; U2=5; U3=5.

#### Sección `estabilizacion`

- `estabilizacion.tiempo_estabilizacion`: unidad «seg», tipo int, mín 0, máx 3600. Valores: FB=0; F2=ausente; UB=60; U2=60; U3=60.
- `estabilizacion.temperatura_estabilizacion`: unidad «°C», tipo float, mín 0, máx 200. Valores: FB=134.0; F2=ausente; UB=134.0; U2=134.0; U3=134.0.
- `estabilizacion.rango_temperatura_estabilizacion`: unidad «°C», tipo float, mín 0, máx 50. Valores: FB=0.5; F2=ausente; UB=0.5; U2=0.5; U3=0.5.
- `estabilizacion.rango_presion_estabilizacion`: unidad «kPa», tipo int, mín 0, máx 1000. Valores: FB=9; F2=ausente; UB=15; U2=15; U3=15.
- `estabilizacion.timeout_recuperacion`: unidad «seg», tipo int, mín 0, máx 3600. Valores: FB=10; F2=ausente; UB=5; U2=5; U3=5.

#### Sección `esterilizacion`

- `esterilizacion.escape_lento_on_ester`: unidad «seg», tipo int, mín 0, máx 1000. Valores: FB=1; F2=1; UB=1; U2=1; U3=1.
- `esterilizacion.escape_lento_off_ester`: unidad «seg», tipo int, mín 0, máx 1000. Valores: FB=0; F2=0; UB=0; U2=0; U3=0.
- `esterilizacion.escape_rapido_on_ester`: unidad «seg», tipo int, mín 0, máx 1000. Valores: FB=0; F2=0; UB=0; U2=0; U3=0.
- `esterilizacion.escape_rapido_off_ester`: unidad «seg», tipo int, mín 0, máx 1000. Valores: FB=400; F2=400; UB=400; U2=400; U3=400.
- `esterilizacion.temperatura_esterilizacion`: unidad «°C», tipo float, mín 100, máx 140. Valores: FB=134.0; F2=134.0; UB=134.0; U2=134.0; U3=121.0.
- `esterilizacion.tiempo_esterilizacion`: unidad «min», tipo float, mín 0, máx 9999. Valores: FB=3.5; F2=3.5; UB=3.5; U2=7.0; U3=15.0.
- `esterilizacion.factor_esterilizacion`: unidad «%», tipo int, mín 0, máx 100. Valores: FB=70; F2=70; UB=70; U2=70; U3=70.
- `esterilizacion.presion_add_esterilizacion`: unidad «kPa», tipo float, mín 0, máx 100. Valores: FB=11.0; F2=11.0; UB=9.0; U2=9.0; U3=9.0.
- `esterilizacion.intervalo_segmentos_ester`: unidad «seg», tipo int, mín 0, máx 30. Valores: FB=3; F2=3; UB=2; U2=2; U3=2.
- `esterilizacion.rango_temperatura_ester`: unidad «°C», tipo float, mín 0, máx 50. Valores: FB=3.0; F2=3.0; UB=3.0; U2=3.0; U3=3.0.
- `esterilizacion.rango_presion_ester`: unidad «kPa», tipo float, mín 0, máx 100. Valores: FB=30.0; F2=30.0; UB=30.0; U2=30.0; U3=30.0.
- `esterilizacion.brecha_segura_temperatura`: unidad «°C», tipo float, mín 0, máx 2. Valores: FB=0.3; F2=0.3; UB=0.3; U2=0.3; U3=0.3.
- `esterilizacion.brecha_error_temperatura`: unidad «°C», tipo float, mín 0, máx 2. Valores: FB=0.1; F2=0.1; UB=0.1; U2=0.1; U3=0.1.
- `esterilizacion.brecha_error_presion`: unidad «kPa», tipo float, mín 0, máx 10. Valores: FB=2.0; F2=2.0; UB=2.0; U2=2.0; U3=2.0.
- `esterilizacion.brecha_segura_presion`: unidad «kPa», tipo float, mín 0, máx 20. Valores: FB=1.5; F2=1.5; UB=1.5; U2=1.5; U3=1.5.

#### Sección `despresurizacion`

- `despresurizacion.tipo_despresurizacion`: unidad «vacía», tipo int, mín 1, máx 4. Valores: FB=1; F2=ausente; UB=ausente; U2=ausente; U3=ausente.
- `despresurizacion.tiempo_despresurizacion`: unidad «min», tipo int, mín 0, máx 3600. Valores: FB=0; F2=ausente; UB=ausente; U2=ausente; U3=ausente.
- `despresurizacion.rango_presion_despresurizacion`: unidad «kPa», tipo int, mín 0, máx 1000. Valores: FB=9; F2=ausente; UB=ausente; U2=ausente; U3=ausente.

#### Sección `secado`

- `secado.modo`: unidad «vacía», tipo int, mín 1, máx 3. Valores: FB=1; F2=1; UB=1; U2=3; U3=1.
- `secado.tiempo_secado`: unidad «min», tipo float, mín 0, máx 120. Valores: FB=2.0; F2=2.0; UB=1.0; U2=15.0; U3=10.0.
- `secado.presion_chaqueta_secado`: unidad «kPa», tipo int, mín 0, máx 500. Valores: FB=200; F2=200; UB=300; U2=300; U3=300.
- `secado.rango_chaqueta_secado`: unidad «kPa», tipo int, mín 0, máx 100. Valores: FB=30; F2=30; UB=30; U2=30; U3=30.
- `secado.presion_baja_secado`: unidad «kPa», tipo int, mín 0, máx 200. Valores: FB=20; F2=20; UB=20; U2=20; U3=20.
- `secado.presion_alta_secado`: unidad «kPa», tipo int, mín 0, máx 300. Valores: FB=80; F2=80; UB=50; U2=50; U3=80.
- `secado.timeout_pulso`: unidad «seg», tipo int, mín 1, máx 600. Valores: FB=10; F2=10; UB=120; U2=180; U3=10.

#### Sección `descompresion`

- `descompresion.modo`: unidad «vacía», tipo int, mín 0, máx 5. Valores: FB=1; F2=1; UB=1; U2=1; U3=1.
- `descompresion.tiempo_pre_despresurizacion`: unidad «sec», tipo int, mín 0, máx 3600. Valores: FB=0; F2=0; UB=0; U2=0; U3=0.
- `descompresion.modo_1.timeout`: unidad «min», tipo int, mín 1, máx 3600. Valores: FB=10; F2=10; UB=10; U2=10; U3=10.
- `descompresion.modo_2.timeout`: unidad «min», tipo int, mín 1, máx 3600. Valores: FB=30; F2=30; UB=30; U2=30; U3=30.
- `descompresion.modo_3.presion_cambio`: unidad «kPa», tipo int, mín 0, máx 500. Valores: FB=150; F2=150; UB=150; U2=150; U3=150.
- `descompresion.modo_3.timeout`: unidad «min», tipo int, mín 1, máx 3600. Valores: FB=30; F2=30; UB=30; U2=30; U3=30.
- `descompresion.modo_4.presion_camara_enfriamiento`: unidad «kPa», tipo int, mín 0, máx 500. Valores: FB=200; F2=200; UB=200; U2=200; U3=200.
- `descompresion.modo_4.temperatura_enfriamiento`: unidad «°C», tipo float, mín 0, máx 150. Valores: FB=80; F2=80; UB=80; U2=80; U3=80.
- `descompresion.modo_4.tiempo_apertura_chaqueta`: unidad «sec», tipo int, mín 1, máx 3600. Valores: FB=5; F2=5; UB=5; U2=5; U3=5.
- `descompresion.modo_4.tiempo_cierre_chaqueta`: unidad «sec», tipo int, mín 0, máx 3600. Valores: FB=10; F2=10; UB=10; U2=10; U3=10.
- `descompresion.modo_4.timeout`: unidad «min», tipo int, mín 1, máx 3600. Valores: FB=120; F2=120; UB=120; U2=120; U3=120.
- `descompresion.modo_5.presion_camara_enfriamiento`: unidad «kPa», tipo int, mín 0, máx 500. Valores: FB=200; F2=200; UB=200; U2=200; U3=200.
- `descompresion.modo_5.temperatura_enfriamiento`: unidad «°C», tipo float, mín 0, máx 150. Valores: FB=80; F2=80; UB=80; U2=80; U3=80.
- `descompresion.modo_5.tiempo_apertura_chaqueta`: unidad «sec», tipo int, mín 1, máx 3600. Valores: FB=5; F2=5; UB=5; U2=5; U3=5.
- `descompresion.modo_5.tiempo_cierre_chaqueta`: unidad «sec», tipo int, mín 0, máx 3600. Valores: FB=10; F2=10; UB=10; U2=10; U3=10.
- `descompresion.modo_5.timeout`: unidad «min», tipo int, mín 1, máx 3600. Valores: FB=120; F2=120; UB=120; U2=120; U3=120.

#### Sección `finalizacion`

- `finalizacion.tiempo_espera_apertura`: unidad «seg», tipo int, mín 0, máx 3600. Valores: FB=60; F2=60; UB=60; U2=60; U3=60.
- `finalizacion.temp_max_apertura`: unidad «°C», tipo float, mín 0, máx 150. Valores: FB=80.0; F2=80.0; UB=100.0; U2=100.0; U3=100.0.
- `finalizacion.timeout_temperatura`: unidad «min», tipo int, mín 1, máx 120. Valores: FB=30; F2=30; UB=30; U2=30; U3=30.
- `finalizacion.apertura_automatica`: unidad «vacía», tipo bool, sin rango (booleano). Valores: FB=False; F2=False; UB=False; U2=False; U3=False.

### A.4 Valores de respaldo en código (no son "valores por defecto" del programa)

Las fases leen cada parámetro con `get_param(...) or <constante>` o con `get_param(..., default=<constante>)` [COMMITEADO]. `default=` solo actúa si la clave falta (`cycle_manager.py:27-33`); `or` actúa además cuando el valor es 0, `0.0` o `False`. Constantes encontradas:

- Precalentamiento (`precalentamiento.py:38-40`): `tiempo_precalentamiento` 0, `presion_precalentamiento` 0, `timeout_precalentamiento` 10 min.
- Prevacío (`prevacio.py:95, 128, 147, 162, 176, 196, 211, 244`): `conteo_pulso_*` 0, `timeout_bajo` 10, `presion_baja_pulso_*` 15 kPa, `tiempo_adicional_bajo_*` 0, `timeout_alto` 10, `presion_alta_pulso_*` 180 kPa, `tiempo_adicional_alto_*` 0.
- Calentamiento (`calentamiento.py:203-217`): `temperatura_calentamiento` 134.0, `timeout_calentamiento` 60, `rango_temp_estabilizacion` 1.0, `timeout_recuperacion_estabilizacion` 5; el resto 0.
- Esterilización (`esterilizacion.py:155-171`): `temperatura_esterilizacion` 134.0, `tiempo_esterilizacion` 3.5; el resto 0.
- Descompresión (`descompresion.py:14, 26, 47, 117, 143, 155-156, 179`): `modo` 0, `tiempo_pre_despresurizacion` 0, `modo_N.timeout` 60, `presion_cambio` 150, `presion_camara_enfriamiento` 200, `tiempo_apertura_chaqueta` 5, `tiempo_cierre_chaqueta` 10, `temperatura_enfriamiento` 80.0.
- Secado (`secado.py:27, 32, 37, 60-61, 107, 119, 125`): `tiempo_secado` 0, `modo` 1, `timeout_pulso` 10, `presion_chaqueta_secado` 200, `rango_chaqueta_secado` 30, `presion_baja_secado` 20, `presion_alta_secado` 80.
- Globals (`ciclo.py:175-178`): `presion_chaqueta` cae a `global_params.presion_chaqueta` y luego a 320; `rango_presion_chaqueta` cae a `global_params.rango_presion_chaqueta` y luego a 50. Nota: `global_params.json` no contiene esas claves (lista de claves verificada), así que el segundo nivel nunca aporta valor.
- Finalización (`ciclo.py:256-280`): `apertura_automatica` False, `tiempo_espera_apertura` 60, `temp_max_apertura` 80.0 (después se toma el mínimo con `global_params.temp_max_apertura`, hoy 120), `timeout_temperatura` 30.

Consecuencia (ver OPC-05): varios parámetros admiten 0 en su rango JSON, pero 0 nunca llega a la lógica porque se reemplaza por la constante. Ejemplos: `tiempo_esterilizacion` (mín 0) con 0 dura 3.5 min; `timeout_precalentamiento` y `timeout_bajo`/`timeout_alto` (mín 0) con 0 valen 10 min; `presion_baja_secado` (mín 0) con 0 vale 20 kPa.

### A.5 Origen de los datos

- Parámetros de programa: exclusivamente los JSON de `cycles/factory/` y `cycles/user/`, sección `parameters` [COMMITEADO].
- Parámetros globales: `config/global_params.json` vía `ConfigManager` (`core/managers/config_manager.py:10-25`) [COMMITEADO]. Claves: `temp_max`, `presion_admosferica`, `rango_presion_atm`, `temp_max_apertura`, `presion_empaque`, `vacio_empaque`, `timeout_puerta`, `tipo_puerta`, `temp_segura_drenaje`, `rango_temp_drenaje`, `intervalo_impresion`, `intervalo_imprecion_esterilizacion`, `tiempo_estable_alarma`, `tiempo_standby`. Ninguna coincide con una clave de programa salvo por concepto (`temp_max_apertura` existe en ambos con significados combinados por mínimo, `ciclo.py:273-277`).
- Atributos de programa fuera de `parameters`: `cycle_id`, `cycle_number`, `display_name`, `cycle_icon`, `cycle_temperature_sensors` (ver D.4).
- No hay otra fuente (ni base de datos, ni YAML) para parámetros de programa.

### A.6 Resolución del parámetro efectivo

- `CycleManager.load_all_cycles()` (`cycle_manager.py:79-84`) carga primero `factory/` y después `user/` en un diccionario indexado por `cycle_id` (`:129`). Si un archivo de usuario tiene el mismo `cycle_id` que uno de fábrica, el de usuario reemplaza por completo al de fábrica: no hay fusión por parámetro.
- Hoy los dos programas de fábrica (`bowe_dick`, `134_instrumental`) tienen copia de usuario con el mismo `cycle_id`, así que en memoria del backend solo existen las tres versiones de usuario. Ningún objeto `source="factory"` queda cargado.
- `Cycle.get_param` (`cycle_manager.py:27-33`) devuelve `value` del programa; si falta la clave, el `default` del llamador. No consulta fábrica ni globales.
- Precedencia efectiva: valor del JSON de usuario (o de fábrica si no hay usuario homónimo) → constante en código (A.4). Solo `globals.presion_chaqueta` y `globals.rango_presion_chaqueta` intercalan `global_params` (sin efecto, A.4), y `finalizacion.temp_max_apertura` se recorta con el global.
- Un archivo JSON que no se puede leer se descarta en silencio, solo con `print` (`cycle_manager.py:131-132`); el programa desaparece de la lista.

### A.7 Programas y numeración

- Programas en disco: B&D (`cycle_number` 1, FB y UB), instrumental 134 (`cycle_number` 2, F2 y U2), Instrumental 121 °C (`cycle_number` 3, solo U3). Nombres visibles: "Bowe & Dick" (sic, no "Bowie-Dick"), "instrumental 134" (minúscula), "Instrumental 121°C".
- `cycle_number` se lee y valida (`_numero_de_ciclo`, `cycle_manager.py:12-15`; números repetidos se anulan en `:86-99`), introducido en `2242a63` (2026-09-29) [COMMITEADO]. El hallazgo B-12 de `planeacion_menu_principal.md` (que dice que no existe número) está parcialmente superado: el número existe, pero no el atributo de origen del programa ni la regla 1-10 / desde 11.
- Regla "1 a 10 fábrica, desde 11 usuario, números no reutilizables" (`planeacion_menu_principal.md` §6.5) [COMMITEADO como documento]: NO IMPLEMENTADO. Hoy el 3 es un programa que solo existe en `user/`. No existe ningún programa 11 o superior, ni función para crear, duplicar o eliminar programas.
- Atributo de origen: `cycle.source` (`cycle_manager.py:125`) indica la carpeta de la que se leyó el archivo, no el origen del programa. Como el usuario reemplaza a fábrica, B&D y 134 aparecen con `source="user"`.
- `GET /cycles` (`server.py:208-213`) devuelve `id`, `name`, `source`, sin `number` ni orden. `GET /cycle` (`:193-205`) sí devuelve `number`. `POST /cycle/select` (`:220-233`) rechaza programas con `source != "user"`.
- El backend arranca con `bowe_dick` seleccionado (`backend/context.py:36`).
- La UI PySide lista solo `source == "user"` y ordena por nombre, no por número (`params_ciclo.py:435-449`).

---

## B. Valor por defecto y asterisco

### B.1 Lo que existe hoy

- El único "valor por defecto" que el código muestra es el de la UI PySide: `_load_factory_params()` (`params_ciclo.py:473-479`) [COMMITEADO] busca un archivo con el mismo nombre de archivo en la carpeta hermana `factory/` y toma el `value` de la misma sección y clave (`_get_factory_value`, `:496-505`). Se muestra como "Por defecto:" en el diálogo (`:246-251`); si no hay archivo, muestra "—".
- La correspondencia es por nombre de archivo, no por `cycle_id` ni por número. Hoy coinciden (`bowe_dick.json`, `instrumental_134.json`), pero nada lo garantiza.
- Comparación valor actual frente a por defecto (base del asterisco): NO IMPLEMENTADO. Ni la UI ni el backend comparan. Es el hallazgo B-13 de `planeacion_menu_principal.md` [COMMITEADO], que sigue vigente.
- Botón o acción "restablecer al valor por defecto": NO IMPLEMENTADO en ninguna capa.
- El backend no expone el valor de fábrica: no hay ruta que devuelva el perfil de fábrica cuando existe uno de usuario homónimo (el de fábrica ni siquiera queda en memoria, A.6).

### B.2 Cómo podría determinarse hoy, con lo que existe (sin decidir)

- Programas con archivo homónimo en `factory/` (B&D y 134): leyendo ese archivo, como hace `params_ciclo.py:473-479`. La comparación tendría que tolerar diferencias de tipo (`int` frente a `float`, por ejemplo `134` frente a `134.0`) y de metadatos (`sec` frente a `seg`).
- Diferencias reales actuales entre usuario y fábrica (recorrido por parámetro):
  - UB frente a FB: 19 parámetros distintos, incluidos `globals.presion_chaqueta` (350 frente a 300), `secado.timeout_pulso` (120 frente a 10), `finalizacion.temp_max_apertura` (100 frente a 80), y la sección `despresurizacion` vacía en UB.
  - U2 frente a F2: 28 diferencias, entre ellas `esterilizacion.tiempo_esterilizacion` (7.0 frente a 3.5), la sección `estabilizacion` (presente solo en U2) y los cambios de unidad `sec`/`seg` en `prevacio`.
  - Si el asterisco se calculara hoy, B&D y 134 mostrarían varios asteriscos desde el primer arranque.
- Parámetros que existen en usuario y no en fábrica (sección `estabilizacion` en U2): no tienen valor de fábrica; NO DETERMINADO cómo tratarlos.

### B.3 Caso crítico: programas de usuario (11 en adelante)

- Hoy no existe ningún programa 11 o superior. El caso más parecido es U3 (Instrumental 121 °C, número 3), que no tiene archivo de fábrica: la UI PySide muestra "—" como valor por defecto en todos sus parámetros.
- No existe plantilla, programa base, ni registro de "programa del que se copió". El JSON de usuario no guarda ninguna referencia a un origen.
- Habría que definir (pregunta 1): de dónde sale el valor por defecto de un programa creado por el usuario (copia congelada del programa base al crearlo, valor del programa de fábrica del que se derivó, plantilla genérica por tipo de equipo, o ningún valor por defecto con el botón deshabilitado). El diseño ya prevé el caso "no se puede determinar" (botón deshabilitado), lo que es compatible con la última opción, pero la decisión es suya.

---

## C. Auditoría

### C.1 Esquemas

- `cycle_params_audit` (`services/domain/logging/cycle_params_audit.py:8-19`) [COMMITEADO], en `data/autoclave.db`: `id INTEGER PK AUTOINCREMENT`, `cycle_id TEXT NOT NULL`, `fase TEXT NOT NULL`, `param TEXT NOT NULL` (ruta unida con punto, por ejemplo `modo_3.presion_cambio`), `valor_anterior TEXT`, `valor_nuevo TEXT NOT NULL`, `usuario TEXT NOT NULL`, `timestamp TEXT NOT NULL`. Sin índices ni claves foráneas. Sin columna de rol, de motivo, de origen de la acción (edición o restablecimiento) ni de equipo/pantalla.
- `sensor_calibration_audit` (`sensor_calibration_audit.py:8-24`) [COMMITEADO]: `tipo`, `sensor`, puntos bajo/alto mostrados y reales, ganancia y offset anteriores y nuevos, `usuario`, `timestamp`.
- Columnas de auditoría de usuarios (`creado_por`, `creado_en`, `codigo_creacion`) en `db_manager.py` [MODIFICADO SIN COMMIT], ya descritas en el informe previo.
- No existe tabla de auditoría para roles de sensor, ni en `dev` ni en la rama.

### C.2 Formato y escritura

- Sello de tiempo: `datetime.now().strftime("%Y-%m-%d %H:%M")` (`cycle_params_audit.py:37`), hora local de pared, sin segundos ni zona. Dos cambios en el mismo minuto empatan; el orden lo resuelve `id DESC` (`:51`).
- Quién escribe: el cliente PySide, no el backend. `_ParamEditDialog._on_save` (`params_ciclo.py:309-359`) llama primero a `PATCH /cycle/parameter` y, si responde bien, inserta en la tabla desde el proceso de la UI (`:355-357`). El backend no audita cambios de parámetros (`server.py:642-665` no escribe auditoría). En cambio, la calibración sí la audita el backend (`server.py:95-99`), con el usuario que manda el cliente en el cuerpo (`:73`, por defecto "Desconocido").
- Identidad registrada: `SessionManager.current_user()["nombre"]` (nombre completo, no `usuario`), o "Desconocido" si no hay sesión o si falla la consulta (`params_ciclo.py:344-352`). El diseño muestra un identificador tipo usuario ("jperez"); NO DETERMINADO cuál se quiere.
- `valor_anterior` es el valor que tenía la copia en memoria de la UI (`:311`), cargada al mostrar la vista (`:426-428`). Si otro cliente cambió el valor entretanto, el valor anterior auditado no es el real.
- Si el `PATCH` funciona y el `INSERT` falla (base bloqueada, disco), la excepción no se captura en `_on_save`: el cambio queda aplicado y persistido sin registro de auditoría.

### C.3 Última modificación por parámetro, fase y programa

- Existe: `CycleParamsAuditDB.get_last_change(cycle_id, fase, param)` (`cycle_params_audit.py:46-54`) devuelve `usuario` y `timestamp` del último registro. La usa la UI PySide al abrir el diálogo (`params_ciclo.py:260-265`).
- Falta: una ruta del backend que la exponga (la UI QML no debería abrir la base directamente si se quiere que el backend sea la autoridad); el valor anterior y nuevo en la respuesta; y la clave por número de programa (hoy es por `cycle_id`).
- Caso de borde: si un programa cambia de `cycle_id` o de nombre de archivo, su historial queda desvinculado.

### C.4 Restablecer y sensores

- Restablecer al valor por defecto: NO IMPLEMENTADO; no hay registro específico. Si se implementara reutilizando el mismo camino, quedaría como una edición normal sin distinguirse.
- Auditoría de cambios de configuración de sensores (roles): NO IMPLEMENTADO en `dev` (no existe la función) ni en la rama (el endpoint `PATCH /cycle/sensor-roles` y la vista no escriben auditoría; el único registro es el commit automático de git, ver D.1).
- Registro adicional existente: `_save_cycle_json` hace `git add` y `git commit` del JSON tras cada guardado (`server.py:668-685`, `utils/git_autocommit.py:10-41`). Es un rastro de versión, no una auditoría: no registra usuario de la aplicación, y en el equipo instalado depende de que exista un repositorio git y el ejecutable `git`.

---

## D. Sensores

### D.1 Rama `feature/roles-sensor-temperatura`

Commits (2026-09-02 a 2026-09-08), en orden: `58fdb8e` Cycle expone roles y entradas exhibidas; `0785c5d` migra `cycle_temperature_sensors` a formato sensor→rol y agrega `cycle_display_slots`; `dea40f9` BaseFase resuelve sensor principal/referencia/control; `27b7c37` Calentamiento controla por referencia y valida saturación del principal; `0674dcb` Esterilización controla PWM por referencia y falla por principal; `6b5db35` F0 acumula contra el principal; `58fdd88` el ticket imprime la temperatura del principal en ESTERILIZACION; `d4918be` endpoints `PATCH /cycle/sensor-roles` y `/cycle/display-slots`; `de931d2` submenú de parámetros del ciclo; `b05899e` pantalla Sensores de Temperatura; `6a6ef22`, `e19c280`, `02dbf86`, `7ac8c3b` correcciones; `ca8832c` pantalla Entradas Exhibidas; `87fca2f` documentación y dos pruebas.

Qué agrega [RAMA feature/roles-sensor-temperatura]:

- Modelo: `Cycle.sensor_roles` (diccionario sensor→rol), `get_principal_sensor()` (devuelve `temp_camara` si no hay principal), `get_referencia_sensor()` (o `None`), `set_sensor_roles()` con validación: sensor en `EstadoAutoclave.map_temp`, rol en `{principal, referencia, no_en_uso}`, como máximo un principal y como máximo una referencia (`02dbf86`). No exige que haya un principal.
- Perfiles: los cinco JSON pasan de `{"1": "temp_camara", "2": "temp_ref"}` a `{"temp_camara": "principal", "temp_2_camara": "no_en_uso", "temp_ref": "no_en_uso"}` y agregan `cycle_display_slots: [null, null, null]`.
- Control: `BaseFase._temp_principal()`, `_temp_referencia()`, `_temp_control()` (referencia si existe, si no principal). Calentamiento controla con `_temp_control()` y no completa hasta que el principal esté en saturación. Esterilización usa `_temp_control()` para RECUPERACION/PWM y `_temp_principal()` para las cuatro fallas de temperatura; si cualquiera de los dos es `None`, devuelve `EN_CURSO`.
- F0: `ControlLoop._acumular_f0()` usa el principal; elimina el `min(temp_camara, temp_2_camara)` por capacidad de líquidos.
- Ticket: en fase "S" imprime la temperatura del principal.
- Backend: `PATCH /cycle/sensor-roles` y `PATCH /cycle/display-slots`, que persisten en el JSON (solo programas de usuario) y hacen commit automático. Sin verificación de rol, de estado de la máquina ni auditoría.
- UI PySide: `params_ciclo_menu.py` (submenú Sensores / Entradas exhibidas / Fases), `sensores_temperatura.py` (una fila por sensor con tres botones de radio), `entradas_exhibidas.py` (tres casillas de sensor visibles por ciclo). `admin_menu.py` redirige "Parámetros del ciclo" a `params_ciclo_menu`.
- Pruebas: siete archivos nuevos o ampliados (`test_cycle_sensor_roles.py`, `test_base_fase_sensor_roles.py`, `test_backend_cycle_sensor_config_endpoints.py`, `test_sensores_temperatura_view.py`, `test_entradas_exhibidas_view.py`, `test_params_ciclo_menu_view.py`, `test_cycle_manager_carga_roles_de_sensor.py`) y cambios en las de calentamiento, esterilización, F0 y ticket. No se ejecutaron en este análisis (solo lectura).

Comportamiento de la vista de la rama (`sensores_temperatura.py`):

- Candidatos: `temp_camara` y `temp_ref` siempre; `temp_2_camara` solo si el perfil de instalación tiene `has_liquid_sensor` (`:40-52`, `:193-197`). Se agregan los sensores con rol activo que el filtro dejaría fuera, marcados "No disponible en este equipo" (`:211-215`).
- Cada clic guarda de inmediato con `PATCH` (`:227-271`); no hay botón Guardar ni Cancelar. Al marcar principal o referencia, el otro sensor con ese rol pasa a `no_en_uso`.
- Usa `http://localhost:8000` (`:25`); `dev` cambió a `127.0.0.1` en `dcb3cf3`.
- Lista solo programas de usuario, ordenados por nombre.

Qué le falta respecto al diseño: botón Guardar con validación del conjunto y detección de cambio; 0-2 referencias; principal obligatorio; lectura actual por sensor; contador Principal/Referencia/No en uso; texto de última modificación; auditoría; permisos por rol; bloqueo por estado; integración con `dev` (base 30 commits atrás).

Conflictos previsibles al integrar (por inspección de los diffs, no se intentó el merge): `cycle_manager.py` (la rama cambia la firma de `Cycle.__init__`; `dev` agregó `number` y `_numero_de_ciclo`), `admin_menu.py` y `main_window.py` (modificados sin commit en `dev` por Nuevo Usuario), `server.py`, los cinco JSON y `CLAUDE.md`.

### D.2 Modelo de roles: rama frente a diseño

- Nombres: la rama usa `principal`, `referencia`, `no_en_uso`, igual que el diseño.
- Cantidad de referencias: rama, como máximo 1 (`set_sensor_roles`, commit `02dbf86`); diseño, de 0 a 2.
- Principal: rama, opcional (si falta, se usa `temp_camara`); diseño, exactamente 1.
- Cambio de principal: rama, al marcar otro principal el anterior pasa a `no_en_uso` y se guarda en el acto; diseño, igual degradación, pero sin guardar hasta pulsar Guardar.
- Semántica: en la rama, "principal" es la sonda de carga (fallas de temperatura, F0, saturación final de calentamiento, ticket) y "referencia" es la sonda de control del vapor (si existe, el lazo de control la usa en lugar del principal). El diseño no define qué hace cada rol. Con dos referencias, el modelo de la rama no tiene definido cuál controla (pregunta 4).
- No hay roles con los nombres `T_control_vapor` ni `T_carga` en el código de `dev` ni de la rama (búsqueda sin resultados); el concepto existe en la rama como "control" (`_temp_control`) y "principal".
- En `dev` no existe ningún modelo de roles. `cycle_temperature_sensors` (formato `{"1": "temp_camara", "2": "temp_ref"}`) está en los cinco JSON pero ningún código lo lee (búsqueda sin resultados en `.py` y `.qml`).

### D.3 Lista de sensores "conectados"

- Nombres lógicos fijos en código: `EstadoAutoclave.map_temp` (`core/runtime/status.py:12-19`) [COMMITEADO]: `temp_camara` (canal 0), `temp_2_camara` (1), `temp_ref` (2), `temp_chaqueta` (3), `temp_drenaje_cam` (4), `temp_drenaje` (5).
- Lectura: la tarjeta ESP32 (`Hardware/Comunocacion_esclava_ESP32_V2/.../Comunicacion_esclava_ESP32_V2.ino`) multiplexa 16 canales analógicos con un PCF8575 que conmuta el MUX (`:13`, `:156-167`); el nombre `CD74HC4067` y `KC868` no aparecen en el código del repositorio (búsqueda sin resultados), por lo que el modelo concreto de MUX y placa es NO DETERMINADO desde el código. `converters.convert_temperatures` (`hal/measures/converters.py:154-191`) procesa 8 canales y devuelve `None` si el ADC crudo es 0 o mayor o igual a 4095 ("sensor desconectado", `:169-174`). `EstadoAutoclave.update` (`status.py:120-128`) asigna por índice.
- Configuración por equipo: `config/instances/ACV-2026-001.yaml` (`io_enabled.AI`) lista `temp_camara`, `temp_referencia`, `temp_drenaje_camara`, `temp_drenaje`; los modelos (`config/models/solids.yaml`, `solids_liquids.yaml`) declaran `io_contract.AI` y capacidades (`sensors.temperature.chamber.supported_count`). Ningún código Python lee `io_enabled` (búsqueda sin resultados) y sus nombres no coinciden con `map_temp` (`temp_referencia` frente a `temp_ref`, `temp_drenaje_camara` frente a `temp_drenaje_cam`, `temp_camara_2` frente a `temp_2_camara`). En `solids_liquids.yaml:10-11` `supported_count` está al mismo nivel que `chamber:` (indentación incorrecta: `chamber` queda nulo).
- Capacidades usadas: solo `EquipmentCapabilities.has_liquid_sensor` (`installation/equipment.py:13-55`), que hoy usa F0 en `dev` (`control_loop.py:224`) y la vista de la rama.
- Detección en vivo: solo implícita (lectura `None`). No hay ruta que diga "estos sensores existen en este equipo". `GET /status` publica las seis temperaturas con claves `camara`, `camara_2`, `ref`, `chaqueta`, `drenaje`, `drenaje_camara` (`server.py:129-134`).
- Nombres visibles: no hay catálogo. La vista PySide de temperaturas usa sus propios alias (`ui_pyside/views/entrdas_salidas/io_temp.py:64-69`); la rama usa `_format_name` de `_io_base.py`. Los nombres del diseño ("Cámara 1", "Cámara 2", "Referencia", "Sensor de cámara", "Sensor de referencia") no existen en código.
- Posición física de cada sensor: NO DETERMINADO desde el código.

### D.4 Persistencia de la asignación

- `dev`: no hay asignación de roles; solo el campo sin uso `cycle_temperature_sensors` en cada JSON de programa.
- Rama: en el JSON de cada programa de usuario, clave `cycle_temperature_sensors`, es decir, por programa. Programas cuyo origen sea `factory/` no se persisten (el endpoint solo escribe si `source == "user"`). Es coherente con "configuración por programa" del diseño.
- Se escribe con el mismo patrón no atómico que los parámetros (D.1, OPC-04).

### D.5 Uso actual de cada sensor en `dev`

- Control de vapor y fallas en CALENTAMIENTO y ESTERILIZACION: `temp_camara` (`calentamiento.py:223, 237`; `esterilizacion.py:190`, fallas en `:196-214`).
- F0: `temp_camara`, o `min(temp_camara, temp_2_camara)` si `has_liquid_sensor` (`control_loop.py:198-230`).
- Sensor crítico de ciclo: `_SENSORES_TEMP_CRITICOS = ["temp_camara"]` (`ciclo.py:32`). Si falta (lectura `None`) en cualquier tick, `CicloState` dispara de inmediato `SENSOR_AUSENTE` como `EMERGENCIA` no recuperable y ejecuta el protocolo de fallo (`ciclo.py:439-459`). Sin debounce. No se encontró cómo se comporta CALENTAMIENTO/ESTERILIZACION ante `None`: devuelven `EN_CURSO`, pero `CicloState` ya cortó antes por `SENSOR_AUSENTE` (NO DETERMINADO el orden exacto dentro del tick sin leer todo `run()`).
- Pérdida de comunicación serial: `FALLO_CONEXION` tras `_TOLERANCIA_DESCONEXION_SEG = 5.0` (`control_loop.py:37, 124`; `ciclo.py:523-540`).
- Puertas: el servicio de puertas usa `temp_camara` (`services/domain/puertas/ser_puertas.py:51-53`); la apertura automática también (`ciclo.py:269`).
- Drenaje: `temp_drenaje` (`ciclo.py:193`, `preparacion.py:262`, `preparado.py:169`).
- Registro: `lecturas` guarda `temp_camara` y `temp_ref` (`cycle_logger.py:318-319`, tabla en `db_manager.py:77`); el ticket usa `temp_camara` (`cycle_logger.py:379`).
- Alarmas de sensor en PREPARACION/PREPARADO: `verificar_sensores` (`preparacion.py:102-140`, `preparado.py:248-260`) dispara `ERROR_AI_<SENSOR>` (tipo `ALERTA`) solo si la lectura es exactamente `0`. Como el convertidor entrega `None` (no 0) para un sensor desconectado, la alarma no se dispara por desconexión (OPC-09). Revisa los seis sensores de temperatura, existan o no en el equipo.
- Estados de falla de sensor existentes: `None` (sin señal por ADC 0 o saturado), `SENSOR_AUSENTE` (emergencia en ciclo, solo `temp_camara` y `pres_camara`), `ERROR_AI_*` (alerta con valor 0), `FALLO_CONEXION`. Fuera de rango (lectura plausible pero fuera de 0-200 °C) y deriva entre sensores: NO IMPLEMENTADO.

### D.6 Sensores de referencia

- `dev`: `temp_ref` se lee, se publica en `/status`, se grafica (`server.py:324, 387`) y se guarda en `lecturas`, pero no participa en control, fallas, F0 ni puertas. No existe el concepto de rol "referencia".
- Rama: "referencia" es la sonda de control del lazo de vapor (D.2). El diseño parece usar "Referencia" como sensor de comparación/registro (permite dos); la diferencia de significado es la pregunta 4 y el hallazgo OPC-06.

---

## E. Permisos y estado de la máquina

### E.1 Roles

- Definidos en `ui_pyside/services/roles.py:10-19` [NUEVO SIN TRACKEAR]: `admin`, `tecnico`, `biomedico`, `ingeniero`. El valor por defecto de la columna `rol` es `operador` (informe previo), que no está en la lista.
- Verificaciones de rol que existen: calibración de sensor, `_ROLES_PERMITIDOS = ("admin", "tecnico")` (`calibracion_sensor.py:37, 176-179`) [COMMITEADO], solo en la vista; opción "Nuevo usuario" solo admin (`admin_menu.py`, `_SOLO_ADMIN`) [MODIFICADO SIN COMMIT].
- Parámetros del ciclo: sin verificación de rol en ninguna capa. `params_ciclo.py` solo usa la sesión para el nombre de auditoría.
- QML: `LoginController` (`ui_qml/controllers/login_controller.py:31-92`) [NUEVO SIN TRACKEAR] autentica y emite `sesionIniciada(usuario, rol)`, pero no hay en QML ninguna regla de permiso por rol (búsqueda de `rol` en `ui_qml/bridge`: sin uso para permisos).
- Backend: ninguna ruta recibe ni verifica identidad o rol (informe previo, H-03). La única tabla de permisos del backend es la de puertas por pantalla (`services/domain/puertas/permissions.py:5-21`, roles de instalación `OPERATOR_FRONT`, `OPERATOR_BACK`, `SERVICE`), que no son roles de usuario.
- Conflicto con el pedido: el diseño excluye a admin de cambiar sensores; la calibración hoy permite admin y excluye biomédico e ingeniero (OPC-14).

### E.2 Estado de las rutas de edición

- `PATCH /cycle/parameter` (`server.py:642-665`) [COMMITEADO]: valida que el programa exista, que la ruta exista y el rango del propio JSON (`Cycle.set_param`, `cycle_manager.py:35-71`). No verifica rol. No verifica estado de la máquina (CICLO, FALLA, EMERGENCIA). No audita. Edita cualquier programa cargado, incluido el activo. Persiste solo si `source == "user"`; si fuera de fábrica, el cambio queda solo en memoria hasta reiniciar.
- `PATCH /cycle/parameters` (`server.py:591-639`) [COMMITEADO]: solo `secado` del programa seleccionado, con tabla de rangos propia en código (`:599-607`) que duplica los del JSON. Mismas carencias de rol, estado y auditoría. Valida rango antes de comprobar que la clave exista y asigna a medida que recorre: si el segundo parámetro falla, el primero ya quedó cambiado en memoria (`:612-626`).
- `PATCH /cycle/sensor-roles` [RAMA]: mismas carencias.
- Validación de tipo: `set_param` convierte con `int()`/`float()`/`bool()`; `bool("false")` es `True` (`cycle_manager.py:56-57`), así que un cliente que mande texto para un booleano lo activa. NaN e infinito: `float("nan")` pasa las comparaciones de rango (NO DETERMINADO si Pydantic los admite en el cuerpo `object`; no se probó).
- Concurrencia: el `Cycle` editado es el mismo objeto que usa la máquina de estados (`ControlLoop.set_active_cycle` asigna la referencia, `control_loop.py:290-311`; el backend selecciona por referencia desde el mismo diccionario, `server.py:222-232`). No hay bloqueo entre el hilo HTTP que escribe y el hilo de control que lee.
- Efecto en caliente: las fases releen los parámetros en cada tick (`esterilizacion.py:155-171`, `calentamiento.py:203-217`, `descompresion.py`, `secado.py`, `protocolo_fallo.py:78, 112, 129`). Un cambio durante CICLO o durante el protocolo de fallo modifica de inmediato consignas y umbrales de falla (OPC-01). Solo el timer de esterilización y el timeout de calentamiento se fijan al entrar a la fase (`esterilizacion.py:178-182`, `calentamiento.py:222-226`).

### E.3 Máquina de estados y cómo consultarla

- Estados globales: `GlobalState` (`state_machine/machine/enum_global.py:3-9`): `PREPARACION`, `PREPARADO`, `CICLO`, `FALLA`, `EMERGENCIA`, `HIBERNACION`.
- Consulta en backend: `context.estado.get_machine_state()`; ya se usa como guardia en `POST /cycle/abort` (`server.py:487`), `POST /cycle/acknowledge` (`:535`), `POST /fault/reset` (`:500`) y `ControlLoop.set_active_cycle` (`control_loop.py:302`, bajo `_sm_lock`). Es el patrón disponible para bloquear la edición en backend.
- Consulta desde la UI: `GET /status` devuelve `machine_state` (`server.py:110-114, 168`) y la lista de alarmas activas.
- Matiz: tras terminar un ciclo, el estado sigue en `CICLO` mientras espera la confirmación del operador (`server.py:525-550`); y la `fase_ciclo` puede ser `FALLO_*` o `EMERGENCIA` dentro de `CICLO`. "Ciclo en ejecución, falla o emergencia" requiere definir si ese tramo cuenta (pregunta 10).

---

## F. Reutilización en QML

### F.1 Componentes existentes

- Navegación por pila: `StackView` `pila` en `Main.qml:99-105` [MODIFICADO SIN COMMIT], con `push`/`pop`; cierra el teclado al cambiar de pantalla.
- Teclado numérico: `PanelTeclado.qml` (167 líneas) y `TecladoNumerico.qml` (176 líneas) [COMMITEADO], con reglas en `ui_qml/domain/teclado_numerico.py` (punto decimal, signo, rango, decimales). API `abrirNumerico(titulo, unidad, valorInicial, minimo, maximo, decimales, alConfirmar, siguiente)` (`PanelTeclado.qml:56`). Diferencias con el diseño: el panel entra desde el borde de la ventana, no dentro de la ventana flotante; distribución 7-8-9 / 4-5-6 / 1-2-3 / -,0,. con columna CANCELAR/BORRAR/CONFIRMAR (`TecladoNumerico.qml:9-13`) frente a la del diseño (punto, 0 y borrar en la última fila; Cancelar y Guardar abajo, sin tecla de signo). Reutilizable la lógica de dominio; NO DETERMINADO si se reutiliza el panel o se crea un teclado embebido (pregunta 19).
- Ventanas modales: `VentanaFlotante.qml` [NUEVO SIN TRACKEAR] (solo visualización, título y cierre arriba; tocar el fondo cierra), `PanelModal.qml` y `DialogoConfirmacion.qml` [COMMITEADO, ambos marcados PROVISIONAL]. Ninguna tiene la anatomía de la ventana de ajuste (cuatro tarjetas, campo, Cancelar/Guardar), y en las tres tocar el fondo cierra, lo que en una ventana con cambios pendientes podría descartar la edición.
- Tarjetas y listas: `TarjetaMenu.qml`, `TarjetaResumen.qml` [NUEVO SIN TRACKEAR], `TarjetaContenido.qml` [COMMITEADO]. No existe una fila genérica "etiqueta, valor, unidad, chevron" ni un componente de lista desplazable genérico; `ListView`/`Repeater` solo aparecen dentro de componentes concretos (barra de fases, notificaciones, teclados, Nuevo Usuario).
- Control segmentado (Principal / Referencia / No en uso): NO IMPLEMENTADO (búsqueda sin resultados).
- Desplegable de programa: NO IMPLEMENTADO en QML (no hay `ComboBox` en `ui_qml/qml`).
- Barra inferior: `BarraInferiorMenu.qml` [NUEVO SIN TRACKEAR], salir e inicio, con salir deshabilitado por `TODO(MP-03)`.
- Encabezado: `EncabezadoMenu.qml` [NUEVO SIN TRACKEAR].
- Navegación lateral de Opciones: NO IMPLEMENTADO en QML.
- Marco "pantalla completa tipo Nuevo Usuario": `ui_pyside/views/nuevo_usuario/vista.py:14-24` [NUEVO SIN TRACKEAR] aloja QML en un `QQuickWidget` con `oculta_marco = True`, y `main_window.py` oculta encabezado y pie para esas vistas [MODIFICADO SIN COMMIT]. Es el patrón disponible para alojar estas pantallas dentro de PySide con su `SessionManager`.

### F.2 Estado actual de las pantallas de Parámetros del ciclo

- QML: NO IMPLEMENTADO. No hay pantalla, ruta, puente ni textos (búsqueda de `params_ciclo` y "Parámetros del ciclo" en `ui_qml`: sin resultados).
- PySide en `dev`: `ParametrosCicloView` (`params_ciclo.py`) [COMMITEADO], ruta `params_ciclo` (`main_window.py:195`), entrada desde "Parámetros del ciclo" en `admin_menu.py`. Nueve pestañas (`params_ciclo.py:54-64`): "Pre-calentamiento", "Crear pulso", "Calentamiento", "Estabilización" (subconjunto de `calentamiento`), "Esterilización", "Escape" (`descompresion`), "Secado", "Finalización", "Global". Tarjetas en rejilla de 3 columnas, diálogo con `QSpinBox`/`QDoubleSpinBox`/`QCheckBox`, mínimo, máximo, por defecto y última modificación. Las secciones `estabilizacion` y `despresurizacion` del JSON no se muestran. Los programas cargados por la UI son una copia propia (`CycleManager()` nuevo en `:432-434`), no los del backend.
- Ruta `params_ciclo_menu`: solo en la rama (`params_ciclo_menu.py`, submenú Sensores de temperatura / Entradas exhibidas / Fases del ciclo). En `dev`: NO IMPLEMENTADO.

### F.3 Tamaños táctiles

- Documentado: D-17 de `docs/mis_plans/planeacion_ui_dual_pantalla.md:68` [COMMITEADO]: objetivo mínimo 48 px "Operación sin guante, panel capacitivo". El sistema de diseño (`docs/files UI Especifika/sistema-diseno-especifika-v1.html:176, 1215, 1406`) [COMMITEADO] dice que puede operarse con guante de nitrilo delgado, define `--touch-min: 48px` y `--touch-process: 64px`, y anota que con guante grueso el mínimo pasaría a 64 px. El pedido dice que el equipo puede operarse con guantes: hay contradicción documental (pregunta 18, OPC-16).
- En código: teclas del teclado 96 × 88 px de diseño (`Tema/Teclado.qml:9-10`); teclas del numérico 206 × 120 (`Tema/TecladoProvisional.qml:56-57`); botones de PySide de 36 px de alto en el diálogo de parámetros (`params_ciclo.py:278, 287`) y 40 × 40 el botón atrás (`:379`), por debajo de 48 px a escala 1. No hay constante global de objetivo táctil en `Tema/` (búsqueda sin resultados). Revisión exhaustiva de todos los botones QML: NO DETERMINADO (no se midió cada pantalla).

### F.4 Componentes que habría que crear (inventario, sin diseño)

Pantalla Programa y fase con navegación lateral; selector de programa; fila de parámetro con asterisco; pantalla Parámetros de la fase; ventana de ajuste con tarjetas Valor actual / Por defecto (botón) / Mínimo / Máximo, línea de última modificación y campo Nuevo valor; teclado embebido o adaptación del panel; control segmentado de tres estados con estado deshabilitado por opción; tarjeta de sensor con lectura actual e insignia "Sin guardar"; resumen de conteo de roles; puente/controlador Python para programas, parámetros, auditoría y roles; textos en `es.json`.

---

## G. Riesgos

### G.1 Dónde habría que forzar las reglas en backend

- Bloqueo por estado: en las rutas de escritura (`PATCH /cycle/parameter`, `PATCH /cycle/parameters` y la futura de roles), con `estado.get_machine_state()` y bajo el mismo `_sm_lock` que usa `set_active_cycle` (`control_loop.py:301`), para que el chequeo no se cruce con un `START_CICLO`. También en `POST /cycle/select`, que ya bloquea en CICLO.
- Rol: hoy imposible en backend porque no hay identidad en las peticiones (informe previo, H-03). Requiere un mecanismo de sesión o credencial hacia el backend; la verificación solo en QML o PySide se evita con cualquier cliente HTTP.
- Reglas de roles de sensor (1 principal, 0-2 referencias, sensor existente en el equipo): en `Cycle.set_sensor_roles` (rama) o equivalente, invocado por el backend; la rama ya valida "máximo 1 principal y 1 referencia", no "exactamente 1 principal" ni la existencia física.
- Rangos: `Cycle.set_param` ya valida contra el JSON; faltaría decidir rangos de seguridad independientes del JSON editable (el JSON de usuario es a la vez dato y límite: quien edita el archivo cambia el rango), y rechazar NaN/infinito y textos en booleanos.
- Auditoría: en el backend, en la misma operación que el cambio, para que ningún cliente pueda cambiar sin registrar.
- Persistencia: escritura atómica (archivo temporal y reemplazo) en el backend.

### G.2 Hallazgos con código y severidad

Ver la lista completa en el Cierre (2).

---

## Cierre

### (1) Preguntas abiertas

1. Para un programa de usuario (11 en adelante), ¿de dónde sale el valor por defecto: copia congelada del programa base al crearlo, el programa de fábrica del que derivó, una plantilla por tipo de equipo, o no hay valor por defecto (botón deshabilitado)?
2. Para los programas 1 a 10, ¿el valor por defecto es el del archivo de `factory/` homónimo? ¿Se mantiene el esquema actual de "copia de usuario que reemplaza a fábrica" o el programa de fábrica pasa a ser uno solo con valores modificados encima?
3. Restablecer un valor por defecto, ¿se audita como una edición normal o con una marca distinta? ¿Hace falta "restablecer todo el programa" o solo por parámetro?
4. ¿Qué hace cada rol de sensor? ¿Se adopta la semántica de la rama (Principal = sonda de carga para fallas, F0, saturación final y ticket; Referencia = sonda del lazo de control)? Si hay dos referencias, ¿cuál controla, o la referencia es solo registro y comparación?
5. ¿Qué sensores son elegibles para cada rol? ¿Solo los de cámara y el de referencia, o también chaqueta y drenaje? ¿Un sensor de referencia puede ser Principal?
6. Si el Principal no es `temp_camara`, ¿deben seguirlo `SENSOR_AUSENTE`, el interlock de puertas, la apertura automática y el registro de `lecturas`?
7. ¿Qué es un sensor "realmente conectado": el declarado en la configuración de instalación (`io_enabled` del YAML, hoy sin uso y con otros nombres), el que da lectura válida en ese momento, o ambos? ¿Se muestra un sensor declarado que no da lectura?
8. La rama `feature/roles-sensor-temperatura`, ¿se integra, se rehace sobre `dev` o se toma solo como referencia? ¿"Entradas exhibidas" entra en este alcance?
9. ¿Los parámetros de fase los pueden editar los mismos roles que los sensores (biomédico, técnico, ingeniero)? ¿Admin ve Parámetros del ciclo en solo lectura o no lo ve? ¿Y el rol `operador`?
10. El bloqueo de edición, ¿aplica también mientras el ciclo terminó y espera confirmación (estado CICLO), en HIBERNACION, con alarma activa o con puerta abierta? ¿Bloquea todos los programas o solo el activo?
11. ¿Se pueden editar los programas de fábrica (1 a 10)? Hoy la UI PySide los muestra en solo lectura y el backend no persiste cambios en ellos.
12. ¿Se muestran todos los parámetros del JSON o una lista curada por fase? ¿Dónde se definen etiqueta, paso y decimales de cada uno (JSON, `es.json`, catálogo en código)?
13. ¿Dónde aparecen los parámetros de `globals` (F0, presión de chaqueta) y de `finalizacion` (apertura automática), que el diseño no ubica en ninguna de las seis fases? ¿Qué se hace con las secciones huérfanas `estabilizacion` y `despresurizacion` y con `ciclos_multiples` y `enfriar_chaqueta_secado`, que no tienen efecto?
14. ¿Se revisan los rangos actuales (por ejemplo `tiempo_esterilizacion` 0-9999 min, presiones 0-1000 kPa con equipo de 400 kPa)? ¿Quién los aprueba y deben existir límites de seguridad no editables?
15. El valor 0, que hoy se sustituye por una constante en varias fases, ¿debe permitirse, prohibirse en el rango o respetarse en la lógica?
16. En la auditoría, ¿se registra el usuario de login o el nombre completo? ¿Con segundos? ¿Se requiere motivo del cambio?
17. Los dos equipos/pantallas (puerta 1 y puerta 2), ¿pueden editar a la vez? ¿Qué pasa si dos usuarios editan el mismo parámetro?
18. ¿El objetivo táctil es 48 px (D-17, sin guante) o 64 px (guante grueso, sistema de diseño)?
19. ¿Se reutiliza `PanelTeclado` (que entra desde el borde) o se crea un teclado embebido en la ventana como en el diseño? ¿Se omite la tecla de signo?
20. ¿Opciones se implementa en QML puro (con login QML) o alojada en PySide con `QQuickWidget` como Nuevo Usuario?
21. ¿Tocar el fondo de la ventana de ajuste debe cerrarla (como `VentanaFlotante` y `PanelModal`) aun con un valor escrito?
22. En la pantalla de sensores, ¿Cancelar descarta todo lo no guardado y salir con cambios pendientes pide confirmación?

### (2) Hallazgos

- OPC-01 (Crítica). Edición en caliente del programa activo. `PATCH /cycle/parameter` (`server.py:642-665`) y `PATCH /cycle/parameters` (`:591-639`) no verifican el estado de la máquina y modifican el mismo objeto `Cycle` que usa el lazo de control (`control_loop.py:305`), sin bloqueo entre hilos. Las fases releen parámetros en cada tick (`esterilizacion.py:155-171`, `calentamiento.py:203-217`, `protocolo_fallo.py:78, 112, 129`). Durante CICLO o el protocolo de fallo se pueden cambiar consigna y umbrales de falla de la esterilización en curso. Hoy cualquier cliente puede hacerlo (también la UI PySide durante un ciclo, informe previo E.2).
- OPC-02 (Alta). Sin control de acceso en backend para parámetros y roles de sensor. Ninguna ruta de escritura (`/cycle/parameter`, `/cycle/parameters`, `/cycle/sensor-roles` de la rama) verifica identidad ni rol; el backend escucha en `0.0.0.0` (informe previo). La restricción "biomédico, técnico, ingeniero; no admin" no puede forzarse hoy fuera de la UI.
- OPC-03 (Alta). Auditoría dependiente del cliente. El registro de `cycle_params_audit` lo escribe la UI PySide después del `PATCH` (`params_ciclo.py:343-357`), no el backend. Otro cliente (QML, HTTP directo) cambia sin auditar; un fallo del `INSERT` deja el cambio aplicado sin registro; se acepta "Desconocido"; el valor anterior sale de la copia local; el sello no tiene segundos (`cycle_params_audit.py:37`). Los roles de sensor (rama) no tienen auditoría.
- OPC-04 (Alta). Persistencia no atómica. `_save_cycle_json` (`server.py:668-685`) y los equivalentes de la rama reescriben el JSON abriendo en modo `"w"`; un corte de energía puede dejarlo truncado. Al reiniciar, `cycle_manager.py:131-132` descarta el archivo en silencio y el programa desaparece; si es homónimo de uno de fábrica, reaparece el de fábrica con otros valores sin aviso. Además ejecuta `git` en el hilo de la petición (`utils/git_autocommit.py`).
- OPC-05 (Alta). Rangos y valor 0. Los rangos JSON admiten 0 en parámetros donde la lógica sustituye 0 por una constante (A.4): el valor mostrado y auditado no es el que se aplica (ejemplo: `tiempo_esterilizacion` 0 aplica 3.5 min). Los rangos son amplios y no se contrastan con los límites del modelo (`solids.yaml`, `limits`); el rango vive en el mismo archivo editable.
- OPC-06 (Alta). Semántica de roles de sensor no definida y distinta entre rama y diseño. La rama limita a una referencia, permite cero principales (cae a `temp_camara`) y usa la referencia como sonda de control del vapor; el diseño pide 0 a 2 referencias y exactamente un principal sin definir su efecto en control, fallas y F0. Asignar un rol cambia qué sensor gobierna el vapor y cuál decide la falla (D.1, D.2).
- OPC-07 (Alta, aplica a la rama y a cualquier diseño que mueva el Principal). Sensor crítico y puertas fijos a `temp_camara`. `SENSOR_AUSENTE` (`ciclo.py:32, 439-459`), el interlock del servicio de puertas (`ser_puertas.py:51-53`) y la apertura automática (`ciclo.py:269`) no siguen al Principal. En la rama, si el Principal es otro sensor y su lectura es `None`, ESTERILIZACION devuelve `EN_CURSO` sin fin (amplía el riesgo aceptado documentado en `CLAUDE.md`), mientras la emergencia solo vigila `temp_camara`.
- OPC-08 (Media). No existe una fuente confiable de "sensores conectados". `map_temp` es fijo (`status.py:12-19`); `io_enabled` del YAML de instancia no se usa y tiene nombres distintos; `solids_liquids.yaml:10-11` está mal indentado; no hay nombres visibles ni posiciones físicas. Una pantalla que liste sensores podría ofrecer uno inexistente para Principal.
- OPC-09 (Media). Alarma de sensor desconectado inefectiva fuera de ciclo. `verificar_sensores` compara con `0` (`preparacion.py:120-140`, `preparado.py:253-260`), pero un sensor desconectado se lee como `None` (`converters.py:169-174`). La condición "sensor sin señal" no se informa en PREPARACION/PREPARADO; revisa además sensores que el equipo puede no tener.
- OPC-10 (Media). Valor por defecto frágil. Se obtiene por coincidencia de nombre de archivo entre `user/` y `factory/` (`params_ciclo.py:473-479`), no por identidad del programa; el perfil de fábrica no está en memoria del backend cuando hay uno de usuario homónimo (`cycle_manager.py:129`); no hay comparación (B-13). Un asterisco o un "Por defecto" basados en esto pueden mostrar un valor que no corresponde al programa.
- OPC-11 (Media). Persistencia perdida en el ejecutable. `AutoclaveBackend.spec:18` empaqueta `cycles/` en un EXE de un solo archivo y `CycleManager` resuelve la carpeta desde `__file__` (`cycle_manager.py:9`); los cambios se escribirían en la carpeta temporal de extracción y se perderían al reiniciar (mismo mecanismo que C.3 del informe previo para `global_params.json`). NO DETERMINADO si el despliegue real usa ese spec.
- OPC-12 (Media). `PATCH /cycle/parameters` aplica parcialmente. Asigna parámetro por parámetro y aborta con 422 a mitad (`server.py:612-626`): los anteriores quedan cambiados en memoria y no se persisten. Además, su tabla de rangos en código (`:599-607`) duplica la del JSON y puede divergir.
- OPC-13 (Media). Rama desfasada y con modelo de guardado incompatible con el diseño. 30 commits detrás de `dev`, conflictos previsibles en `cycle_manager.py`, `admin_menu.py`, `main_window.py`, `server.py` y los JSON; guarda cada clic sin botón Guardar ni validación del conjunto; usa `localhost` (revertido en `dev`).
- OPC-14 (Media). Permisos incoherentes entre funciones de sensores. La calibración permite `admin` y `tecnico` y excluye `biomedico` e `ingeniero` (`calibracion_sensor.py:37`); el diseño de roles de sensor permite biomédico, técnico e ingeniero y excluye admin. El rol por defecto de la tabla, `operador`, no figura en `roles.py`.
- OPC-15 (Media). Parámetros sin efecto presentados como editables. `estabilizacion.*`, `despresurizacion.*`, `globals.ciclos_multiples` y `globals.enfriar_chaqueta_secado` no tienen consumidor; editarlos genera auditoría de un cambio que no actúa. U3 conserva `temperatura_estabilizacion = 134.0` en un programa de 121 °C.
- OPC-16 (Baja). Contradicción documental sobre guantes: D-17 (48 px, sin guante) frente al sistema de diseño (guante de nitrilo; 64 px con guante grueso) y al pedido (operable con guantes). Botones PySide actuales de 36-40 px.
- OPC-17 (Baja). Metadatos inconsistentes: unidades `sec`/`seg`, 20 parámetros de `prevacio` sin `type`, `rango_calentamiento` declarado en kPa con uso en temperatura (NO DETERMINADO), sin etiquetas ni paso. `bool("false")` es `True` en `set_param` (`cycle_manager.py:56-57`).
- OPC-18 (Baja). Alcance del bloqueo ambiguo: tras finalizar, el estado permanece en `CICLO` esperando confirmación, y una falla de ciclo se representa como `fase_ciclo = FALLO_*` dentro de `CICLO`, no necesariamente como `GlobalState.FALLA` (`server.py:525-550`). Un bloqueo basado solo en `GlobalState` debe considerar ambos casos.

### (3) Archivos que debe revisar directamente

- `src/autoclave/images/opciones_flujo_comparativo.png`, `opciones_ajuste_comparativo.png`, `opciones_sensor_comparativo.png` (diseño aprobado).
- `src/autoclave/cycles/factory/*.json` y `src/autoclave/cycles/user/*.json`.
- `src/autoclave/core/managers/cycle_manager.py` (`:27-71`, `:79-132`).
- `src/autoclave/backend/server.py` (`:193-233`, `:591-685`) y `src/autoclave/backend/context.py` (`:31-36`).
- `src/autoclave/utils/git_autocommit.py`.
- `src/autoclave/ui_pyside/views/params_ciclo/params_ciclo.py` (completo).
- `src/autoclave/services/domain/logging/cycle_params_audit.py` y `sensor_calibration_audit.py`.
- `src/autoclave/state_machine/cycle_phases/esterilizacion.py` (`:155-250`), `calentamiento.py` (`:200-260`), `precalentamiento.py`, `prevacio.py`, `descompresion.py`, `secado.py`, `protocolo_fallo.py`, `base_fase.py`.
- `src/autoclave/state_machine/states/ciclo.py` (`:32-33`, `:170-200`, `:256-280`, `:439-459`, `:523-540`), `preparacion.py` (`:102-140`), `preparado.py` (`:248-260`).
- `src/autoclave/services/domain/loop/control_loop.py` (`:198-230`, `:290-311`).
- `src/autoclave/core/runtime/status.py` (`:11-25`, `:92-128`) y `src/autoclave/hal/measures/converters.py` (`:154-191`).
- `src/autoclave/config/instances/ACV-2026-001.yaml`, `config/models/solids.yaml`, `config/models/solids_liquids.yaml`, `src/autoclave/installation/equipment.py`.
- `src/autoclave/services/domain/puertas/ser_puertas.py` (`:45-53`) y `permissions.py`.
- `src/autoclave/ui_pyside/services/roles.py`, `session_manager.py`, `ui_pyside/views/entrdas_salidas/calibracion_sensor.py` (`:37`, `:176-179`), `ui_pyside/views/admin_menu.py`, `ui_pyside/main_window.py`, `ui_pyside/views/nuevo_usuario/vista.py`.
- `src/autoclave/ui_qml/qml/Main.qml`, `Componentes/PanelTeclado.qml`, `TecladoNumerico.qml`, `VentanaFlotante.qml`, `PanelModal.qml`, `DialogoConfirmacion.qml`, `BarraInferiorMenu.qml`, `EncabezadoMenu.qml`, `Tema/Teclado.qml`, `Tema/TecladoProvisional.qml`, `ui_qml/domain/teclado_numerico.py`, `ui_qml/controllers/login_controller.py`.
- Rama `feature/roles-sensor-temperatura`: `git diff dev...feature/roles-sensor-temperatura`, en especial `core/managers/cycle_manager.py`, `state_machine/cycle_phases/base_fase.py`, `esterilizacion.py`, `calentamiento.py`, `backend/server.py` y `ui_pyside/views/params_ciclo/sensores_temperatura.py`.
- `docs/mis_plans/planeacion_menu_principal.md` (§6.5, §11, §12), `docs/mis_plans/planeacion_ui_dual_pantalla.md` (D-17), `docs/files UI Especifika/sistema-diseno-especifika-v1.html` (A2, operación con guante, `--touch-min`), `CLAUDE.md` (secciones de ESTERILIZACION y F0).
- `AutoclaveBackend.spec` (`:18-19`, `:43-47`).

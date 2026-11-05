# Prompt: tanda 27 — depuración del repositorio y retiro total del ESP32

Trabajo sin supervisión. Rama propia `tanda27` desde `dev` limpio. Informes, comentarios y mensajes de commit en español. Máximo 4 subagentes a la vez; los subagentes no corren la suite completa (solo sus pruebas); revisor de seguridad en el paso 6 y revisor final sobre el diff. Lleva `docs/informes/tanda27/estado.md` (paso → Hecho/Pendiente, último commit) al día tras cada commit y, al reanudar, sigue desde el primer paso pendiente. Sin push. Hallazgos numerados con severidad (`DEP-NN`). Lo que decidas sin confirmación de Cristian se marca `DECISIÓN SIN CONFIRMAR`.

Objetivo de la depuración: quitar lo que ya no se usa (pantallas, rutas del backend, módulos, herramientas, pruebas, claves i18n, dependencias) y todo rastro del ESP32 en el código y en la documentación vigente. **No hay cambio funcional.** El 1-dic se entrega un equipo funcional: ante la duda, no se borra.

La tanda tiene dos partes en este orden: **Parte A** (4 ajustes funcionales, con sus pruebas) y luego la depuración (pasos 0 a 7), que no cambia comportamiento. La línea base de la depuración se toma **después** de la Parte A.

## Parte A — ajustes funcionales (Cristian, 5-nov)

Commits propios con prefijo `A1`..`A4`, pruebas por punto y hallazgos `AJ27-NN`. Informe `docs/informes/tanda27/A_informe.md`.

- **A1. Unidades en las dos pantallas.** Si se cambian las unidades en una pantalla, la otra no se entera. Con el idioma sí funciona: `i18n_qml.py` sondea `GET /language`. Lo que se vio en el código: el singleton `ui_qml/bridge/unidades_qml.instancia` se crea con `sondear=False`. Confirma la causa en las dos ventanas (`app.py`, `doble_pantalla.py`) y haz que unidades siga al backend igual que el idioma y el tema (`Apariencia`, `GET /theme` cada 3 s): el cambio debe verse en la otra pantalla en menos de 3 s, sin reiniciar, y si la respuesta falta o es inválida se conservan las unidades vigentes. Prueba: el cambio hecho desde la ventana 1 se aplica en la 2, y una respuesta inválida no cambia nada.
- **A2. Sin suspensión (standby) en modo prueba.** `ui_qml/bridge/standby.py`: con `test_mode_active` (en `/status`) ninguna de las dos pantallas entra a standby, y entrar al modo prueba cuenta como actividad. Prueba incluida.
- **A3. Sin botón INICIAR en la otra pantalla con modo prueba activo.** Mientras el modo prueba esté activo, el botón o deslizador de inicio de ciclo desaparece (no solo se deshabilita) en las dos pantallas: Preciclo, Reposo y donde más exista. La pantalla muestra la fila «Modo prueba» que ya existe. Vuelve al salir del modo prueba. Confirma que el backend ya rechaza el inicio en modo prueba; si no lo hace, recházalo con un código propio y su texto. Pruebas de UI y de backend.
- **A4. Ninguna salida de mantener (decisión de Cristian: interruptor sin tope).**
  - `abrir_puerta_1/2`, `cerrar_puerta_1/2` y `bomba_vacio` dejan de ser momentáneas en el modo prueba y pasan a interruptor, como las demás salidas, para que una sola persona pueda hacer las pruebas.
  - `SALIDAS_MOMENTANEAS` queda vacío o se retira. También se retiran los temporizadores de caducidad de `rutas/io.py` (`_armar_momentanea`/`_caducar_momentanea`), el botón «Mantener» y la renovación de 500 ms de `OpcionesEntradasSalidas.qml`, y el parámetro `momentanea` del cuerpo. Si se conserva por compatibilidad, se acepta y se ignora con aviso en el log.
  - Las sostenidas nuevas entran en la orden pendiente de SMP (tanda 26).
  - Se conservan sin cambio:
    - las protecciones ESG-02: no abrir ni desbloquear con la cámara fuera de la presión atmosférica o sin lectura, y no dar vapor con una puerta abierta;
    - el apagado de todo al salir del modo prueba, al cerrar sesión, con el paro, al cortarse la conexión y con la vigilancia MOD-08;
    - el bloqueo del encendido sin modo prueba confirmado.
  - Agrega una regla de enclavamiento (`DECISIÓN SIN CONFIRMAR`): encender `abrir_puerta_N` apaga `cerrar_puerta_N` en la misma orden, y al revés, para no alimentar el motor en los dos sentidos a la vez.
  - Riesgo nuevo HAZ-IO-07, **aceptado por Cristian el 5-nov**: movimiento de puerta y bomba de vacío sin pulsador de hombre muerto en el modo prueba, con posible atrapamiento si nadie vigila. El control es el acceso por rol, el modo prueba explícito, las protecciones ESG-02 y el apagado al salir. Reemplaza los controles de P-ES-3 y SAF-01 de la tanda 7 que dependían de la renovación.
  - Pruebas: encender una puerta queda encendido sin renovar; los enclavamientos abrir/cerrar; las ESG-02 siguen rechazando y cortando; todo se apaga al salir del modo prueba; ninguna salida muestra «Mantener».
- Al terminar la Parte A: suite completa en verde y commit `docs(tanda27): parte A`. Después sigue con el paso 0.

## Decisiones cerradas por Cristian (5-nov)
1. **ESP32:** se elimina de `src/`, `tests/`, `tools/`, `packaging/`, i18n, `CLAUDE.md`, `pyproject.toml`, `requirements*.txt` y la documentación vigente. Se conservan, marcados como obsoletos, los registros históricos que exige IEC 62304: `docs/informes/tanda*/`, los planes de tandas cerradas en `docs/mis_plans/`, `docs/versiones/HISTORIAL_VERSIONES.md`, las entradas del registro de riesgos y de la trazabilidad, y los códigos `TARJETA_*` guardados en bases y bitácoras (el catálogo debe seguir mostrando las filas viejas del historial).
2. **`ui_pyside` (AutoclaveSettings.exe):** se retira solo si cada pantalla tiene su equivalente en QML. Si falta alguna, no se borra nada de `ui_pyside`: se reporta qué falta.
3. **Regla de borrado estricta:** solo se borra lo que cumple **todos** los criterios del paso 2. Lo dudoso va a `docs/informes/tanda27/dudosos.md` para que Cristian lo apruebe.

## 0. Requisito previo y línea base
- Requisito: la tanda 26 cerrada en `dev`, con `docs/informes/tanda26/CERRADO.txt` sin `BLOQUEADO:` y su merge hecho. Si no está, escribe `CERRADO.txt` con `BLOQUEADO: la tanda 26 no está cerrada en dev` y termina.
- Etiqueta local `respaldo-pre-depuracion` sobre `dev`.
- Línea base en `docs/informes/tanda27/base/`:
  - suite (`pytest tests -n auto -q`; las rojas se repiten en serie con `--lf`);
  - rutas y OpenAPI (la base de `docs/informes/tanda15/base/` que fija `tests/test_t15_rutas_equivalentes.py`);
  - lista de archivos de `src/` y de `assets`;
  - lista de las pantallas QML que cargan los arneses existentes;
  - compilación de los `.spec`. Si CMP de la tanda 26 dejó pendiente el K_t, no compiles; anótalo y compara el TOC con `pyi-archive_viewer` cuando sea posible.

## 1. Inventario (sin borrar nada)
Escribe `docs/informes/tanda27/inventario.md`: una lista corta por categoría, cada elemento con su evidencia de uso o de falta de uso.
- **ESP32 / serial:** todo `esp32`, `ESP32`, `serial`, `pyserial`, `trama`, `CRC`, `ADC`, `.ino`, `Comunicacion_esclava`, `calibration.yaml` (serial), `enlace_io.json`, `ALARMAS_SOLO_SERIAL`, `device_reset`, «tarjeta» en el sentido de hardware, `respaldo-serial-pre-t20`. Ya se vieron en el código: comentarios en `prevacio.py`, `ciclo.py`, `protocolo_fallo.py`, `modbus_link.py`, `modbus_link_config.py`, `rutas/sistema.py`, `rutas/respaldo.py`; `protocols/enlace.ALARMAS_SOLO_SERIAL`; `docs/plan_modificaciones_adc_ino.md`; unas 66 referencias en `tools/`, `packaging/` y `docs/`. No confundas «trama AI vencida» del Modbus (vigente) con las tramas del serial.
- **Código Python sin uso:** grafo de importación desde los puntos de entrada reales:
  - `exe_unico.py` y cada `--rol`;
  - `backend/main.py` y `autoclave.backend.server:app`;
  - `simulador/__main__.py`;
  - `ui_qml/app.py` y `lanzar.py`;
  - `ui_pyside/app.py`;
  - los scripts de `tools/` que nombran `CLAUDE.md` o la documentación vigente;
  - `hiddenimports` y `datas` de los `.spec`.

  Completa el grafo con `vulture` (instálalo solo en tu entorno, no en el lock) para funciones y clases muertas dentro de módulos vivos.
- **QML sin uso:** archivos no referenciados por nombre de tipo, por `Loader.source`/`Qt.createComponent`/cadenas, por `qmldir` ni por los arneses de `tests/banco/`. Busca también propiedades y señales sin lector.
- **Rutas del backend sin cliente:** rutas de `backend/rutas/*.py` que no llama `cliente/`, `ui_qml/`, `ui_pyside/`, `simulador/`, `tools/` ni ningún script del Setup o de la estación.
- **i18n:** claves sin uso (`tools/claves_sin_uso_i18n.py`), cuidando las claves que se arman dinámicamente (`"sistema.estado_seguro_causa_" + causa`, `reasignacion.motivo_<motivo>`, etc.).
- **Herramientas de `tools/`:** `ensayo_actualizacion_*.py`, `demos_qml/`, `medir_contador_ciclos.py`, `declarar_*`, `asignar_programas_tuttnauer.py`, `importar_ciclo_tuttnauer.py`, `registro_pruebas/` y demás, cada una con su uso vigente o no. El generador (`tools/generador`), la entrega, la estación, los secretos y las tandas son vigentes.
- **Pruebas** que solo prueban código sin uso, y **dependencias** del `pyproject.toml` y del lock que nadie importa.
- **`ui_pyside`:** para cada vista (`admin_menu`, `ciclos`, `entrdas_salidas`, `home`, `impresion_menu`, `login`, `nuevo_usuario`, `params_ciclo`, `secado`, `_teclado_pantalla`, `services`) indica qué hace, quién la abre (`ui_qml/bridge/lanzador_ajustes.py`, `exe_unico.py`), su equivalente en QML con la evidencia (pantalla, controlador, ruta) o «sin equivalente». Revisa también quién importa `ui_pyside` desde fuera: `cliente/session_manager.py`, `auth/roles.py`, `auth/validacion_usuario.py`, `ui_qml/app.py`, `ui_qml/exportacion/correo.py`, `config_correo.py` y `bridge/acciones_ciclos.py`.

## 2. Criterios de borrado (todos deben cumplirse)
a. Ninguna importación ni referencia estática desde un punto de entrada vivo.
b. No figura en `.spec`, `qmldir`, el script del Setup (Inno) ni los scripts de la estación.
c. Su nombre no aparece como cadena en código vivo, QML, JSON o YAML (carga dinámica).
d. Ningún proceso vigente lo nombra (`CLAUDE.md`, `docs/README.md`, la hoja de pruebas de banco, las instrucciones de entrega).
e. Si lo prueba una prueba con marcador `req(id)` o lo cita la trazabilidad o el registro de riesgos, no se borra: va a dudosos con el requisito afectado.

Lo que falle cualquier criterio, o lo que no puedas comprobar, va a `dudosos.md` con el motivo.

## 3. Retiro del ESP32
- **Código:** quita los comentarios y las ramas muertas que hablan del serial o del ESP32. Donde el comentario explica una regla vigente heredada (p. ej. la discrepancia MOD-11 o el piso de prevacío), reescríbelo describiendo la regla sin nombrar el ESP32.
- **`ALARMAS_SOLO_SERIAL`:** pasa a `ALARMAS_RETIRADAS_HISTORIAL`. Las entradas del catálogo de esos códigos se conservan para mostrar filas viejas, con textos neutros y sin «ESP32» ni «serial».
- **`calibracion_otro_enlace`:** el rechazo de un respaldo con calibración ajena a Modbus se conserva (es una protección: cuentas del ADC no son µA ni décimas). Cambian solo el comentario y el texto, que dejan de mencionar el ESP32; el código del rechazo no cambia.
- **Datos persistidos:** no se renombra ni se borra nada guardado. Siguen igual `tarjeta_conectada`, `tarjeta_es`, `board_id`, los `TARJETA_*` y el MES-04.
- **Documentación vigente:**
  - `CLAUDE.md`: deja la sección «Enlace de E/S Modbus» sin el párrafo histórico del serial salvo una línea: «enlace serial retirado en la tanda 20; histórico en `docs/informes/tanda20/`».
  - `docs/arquitectura/`, `docs/referencia/`, `docs/README.md`, `docs/catalogo_alarmas.md`, `docs/instalacion/` y la hoja de pruebas de banco: quita el ESP32.
  - `docs/plan_modificaciones_adc_ino.md` y los planes de firmware (`planeacion_firmware_1_5.md` y similares) pasan a `docs/referencia/obsoleto/` con una nota de cabecera «Obsoleto: hardware ESP32 retirado en la tanda 20».
- **Registro de riesgos y trazabilidad:** las entradas del serial se marcan «Obsoleto (tanda 20, retirado en la 27)»; no se borran.
- **Ramas y etiquetas:** no borres ramas ni etiquetas de git, ni la copia de `G:\Respaldos_autoclave`.

## 4. `ui_pyside`
- Si el inventario muestra equivalencia completa:
  - retira `src/autoclave/ui_pyside/`, `packaging/AutoclaveSettings.spec`, `ui_qml/bridge/lanzador_ajustes.py` y el botón o entrada que lo abre;
  - quita sus referencias en `exe_unico.py`, `Autoclave.spec` (`hiddenimports`), `GeneradorCodigos.spec`, el Setup, `compilar_entrega.py`, `verificar_entrega_neutra.py` y las pruebas;
  - mueve a `auth/`, `cliente/` o `ui_qml/` lo que los módulos vivos tomen de ella, sin cambiar el comportamiento.
- Quita del `pyproject.toml` y del lock las dependencias que solo usaba (p. ej. `PySide6-Fluent-Widgets`). Actualiza la **lista SOUP** con el motivo (IEC 62304 §8.1.2) y el riesgo si aplica.
- Si falta alguna equivalencia: no toques `ui_pyside`. Lista las faltantes como `DEP-NN` en el informe.

## 5. Resto de la depuración
- Borra lo que cumple los criterios del paso 2, en commits por categoría (QML, rutas, módulos, herramientas, i18n, pruebas, dependencias). Cada mensaje de commit lista lo borrado.
- **Rutas:** al retirar una, actualiza la base de `docs/informes/tanda15/base/` y `test_t15_rutas_equivalentes.py` en un commit propio, con la lista de rutas retiradas. Ninguna otra diferencia en rutas u OpenAPI.
- **Lock:** regenéralo según su propia cabecera (venv limpio, `pip freeze`). Si en este entorno no se puede, quita solo las líneas de los paquetes retirados y de sus dependencias exclusivas, y anótalo.
- **Directorios de control** (`state_machine/`, `protocols/`, `core/runtime/`, `devices/`, `hal/`, `services/domain/loop/`): solo comentarios y funciones o constantes muertas comprobadas por los criterios. Ningún cambio de lógica, umbral, orden de ejecución ni tiempos.

## 6. Verificación de equivalencia
- Suite completa en verde. Las pruebas borradas se listan con el código que probaban.
- Rutas y OpenAPI iguales a la base, salvo las retiradas.
- Todas las pantallas QML que cargaba la base siguen cargando sin advertencias nuevas (arneses de `tests/banco/`, `QT_QPA_PLATFORM=offscreen`), en claro y en oscuro.
- Simulador: arranque, login, un ciclo simulado completo y Reportes.
- Compilación de los `.spec` que queden (si hay K_t). Compara el TOC con la base: solo deben faltar los módulos retirados. Si no se puede compilar, dilo.
- `rg -i "esp32|pyserial|serial_link|\.ino\b"` sobre `src/`, `tests/`, `tools/`, `packaging/`, `CLAUDE.md` y los docs vigentes no devuelve nada fuera de `ALARMAS_RETIRADAS_HISTORIAL` y sus textos de historial. Agrega esa búsqueda como prueba (`tests/test_t27_sin_esp32.py`), con su lista de excepciones explícita.
- **Revisor de seguridad** sobre todo cambio en los directorios de control y en `rutas/respaldo.py`: comprueba que solo cambian comentarios o se retira código muerto.

## 7. Documentación y cierre
- `CLAUDE.md`: actualiza la estructura del repositorio y quita lo retirado. `docs/README.md` y `tests/README.md` si cambian.
- Registro de riesgos: entrada corta HAZ-DEP-01 (retiro de código que resulta vigente; control: criterios del paso 2, equivalencia del paso 6, etiqueta de respaldo).
- `CLAUDE.md`: actualiza las reglas de modo prueba (sin salidas momentáneas, enclavamiento de puertas, sin standby, INICIAR oculto) y de unidades sincronizadas. Registra HAZ-IO-07 y la trazabilidad de A1 a A4.
- Informe `docs/informes/tanda27/R27_informe.md`, corto, con un apartado para la Parte A: qué se retiró por categoría (con número de archivos y de líneas), qué quedó en dudosos, el resultado de `ui_pyside`, los cambios de dependencias y SOUP, y las diferencias con la base.
- Revisor final sobre el diff. Une `tanda27` a `dev` con merge, sin push.
- **No compiles la entrega.** Dilo en el informe y deja el comando `python tools/entrega/compilar_entrega.py`.
- Último acto: `docs/informes/tanda27/CERRADO.txt` con fecha, commit del merge, resultado de la suite y número de dudosos. Si te bloquea algo que necesita a Cristian, escríbelo igual con `BLOQUEADO:` y el motivo en la primera línea.

## Restricciones
- Fuera de la Parte A: sin funciones nuevas ni cambios de comportamiento, textos visibles (salvo los que nombran el ESP32), parámetros, alarmas, umbrales o datos persistidos.
- No borrar registros históricos de 62304, ramas, etiquetas ni respaldos.
- No tocar secretos, K_t, vectores ni la versión.

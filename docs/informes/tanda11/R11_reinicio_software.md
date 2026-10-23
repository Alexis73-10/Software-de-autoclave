# R11 — Reinicio del software al cambiar la impresora (tanda 11)

Rama `tanda-11-r11` (parte de `tanda-11`, 1b3ec0d). Fuente: D11-1 de `docs/mis_plans/decisiones_tanda_11.md`.

## Qué se hizo, por punto

### D11-1.1 — Diálogo de confirmación; con Cancelar no se guarda nada
- `OpcionesParametrosEquipo.qml`: tocar la fila "Impresora habilitada" ya no envía nada. Abre `dialogoReinicioImpresora` con "Se reiniciará el software para aplicar el cambio." y, debajo, "Si el software no vuelve a abrir en 1 minuto, apague y encienda el equipo." Botones: Reiniciar / Cancelar.
- Si se pulsa Cancelar o se toca el fondo, se descarta el valor pendiente y no se envía nada al backend.

### D11-1.2 — Guardar con auditoría y luego reiniciar solo
- Al confirmar, `ParametrosEquipoController.fijarImpresoraYReiniciar()` envía `PUT /printer/config {"habilitada": X, "reiniciar": true}`.
- Backend (`server.py`). La secuencia es guardar → cerrar → relanzar:
  1. Guarda la bandera.
  2. Vuelve a comprobar el estado bajo `_sm_lock` y, en ese mismo bloque, llama a `iniciar_apagado()`, igual que "Apagar equipo" (desde ahí ningún tick puede pasar a CICLO).
  3. Audita `impresora_configurada` (como hoy) y después `software_reiniciado`.
  4. Lanza el hilo `ReiniciarSoftware`. Ese hilo corre `_secuencia_apagado(apagar_windows=False)`, que es la MISMA secuencia de cierre de "Apagar equipo": `control_loop.stop` (ALL_OFF y cierre del puerto), historial de alarmas, vaciado de la escritura del ciclo y cierre de la base. La única diferencia es que no se apaga Windows.
  5. Pide a uvicorn que se detenga. El backend termina con el código nuevo `CODIGO_REINICIO_SOFTWARE = 76` (`backend/reinicio.py`; el 75 de R8 no cambia).
- Lanzador (`exe_unico.py`): ante el código 76, `vigilar_reinicios` avisa al lanzador. `vigilar_pantallas(detener=...)` (`doble_pantalla.py`) cierra las pantallas sin relanzarlas. Cuando el backend ya terminó, `relanzar_software()` vuelve a abrir el mismo comando, desligado del proceso (DETACHED_PROCESS) y en la misma sesión de usuario.
- La bandera se aplica al volver a abrir el software. Con reinicio NO se llama a `aplicar_config_impresora()`, porque lanzaría la verificación de la impresora en pleno cierre.
- No se cambió la lógica de estado seguro. Se reutilizan tal cual `iniciar_apagado`, `control_loop.stop` y la secuencia de pasos con tope. Solo se agregó el parámetro `apagar_windows` (por defecto `True`, así que "Apagar equipo" no cambia; hay una prueba que lo confirma).
- El lifespan de uvicorn ya no vuelve a llamar a `control_loop.stop()` si el cierre ordenado del reinicio ya corrió. Antes habría hecho un segundo ALL_OFF sobre el puerto cerrado, que solo deja errores en el log. Bandera `_cierre_ordenado_hecho`.

### D11-1.3 — Rechazado en CICLO; permitido en PREPARACION, PREPARADO y FALLA
- `PUT /printer/config` ahora pasa por `guard_estado(DISTINTO_DE_CICLO)`, con o sin `reiniciar`. En CICLO responde 409 `estado_no_permitido`, y la pantalla muestra "Con ciclo en curso los parámetros del equipo no se pueden cambiar.".
- Carrera: puede empezar un ciclo entre el guardado y el cierre (por ejemplo, desde la otra pantalla). En ese caso, la segunda comprobación bajo el lock lo rechaza (409) y la bandera se devuelve a su valor anterior, como `_guardar_y_reiniciar` de R8.
- Los demás estados distintos de CICLO también lo permiten, igual que "Apagar equipo".

### D11-1.4 — Mecanismo reutilizable, auditado y con una sola instancia
- Funciones públicas en `server.py`:
  - `reiniciar_software(motivo, sesion, entidad=, detalle=, deshacer=)` = `bloquear_para_reinicio` + `lanzar_reinicio`.
  - `comprobar_reinicio_disponible(entidad, sesion)`: devuelve 409 `apagado_en_curso` si ya se está apagando o reiniciando, y 503 `reinicio_no_disponible` si ningún lanzador va a relanzar el software. Se comprueba ANTES de guardar.
- Auditoría `software_reiniciado` con `detalle = {"motivo": "impresora_configurada", "estado": "<estado>", "habilitada": X}`, más usuario y rol de la sesión. Tiene texto en la bitácora (es/en) y está agregado a `bitacora.EVENTOS`.
- Una sola instancia:
  - El comando relanzado lleva `--esperar-pid <lanzador> --esperar-pid <backend>`.
  - Antes de arrancar, la instancia nueva corre `esperar_instancia_anterior()`: espera a que esos procesos terminen (psutil) Y a que nada escuche en 127.0.0.1:8000. Tope: 60 s.
  - Si vence el tope, lo registra y sigue con la lógica de siempre: si un backend responde se usa ese y no se arranca otro, así que nunca quedan dos backends escuchando.
- En desarrollo (`sys.frozen` falso) se relanza `python -m autoclave.exe_unico <mismos argumentos>`, es decir, el mismo comando con que arrancó el lanzador. Congelado: `Autoclave.exe <mismos argumentos>`. Los `--esperar-pid` anteriores se quitan del comando para no acumularlos.

### D11-1.5 — Fallo del relanzamiento y aviso al operador
- Si `relanzar_software` falla al lanzar el proceso, queda en `data/lanzador.log` como ERROR, con el comando y "apague y encienda el equipo".
- Antes del cierre, el operador ve el aviso en dos momentos:
  - en el diálogo de confirmación;
  - después de confirmar, en la capa `avisoReinicioSoftware` ("Reiniciando el software…" + "Si el software no vuelve a abrir en 1 minuto, apague y encienda el equipo."). Esta capa bloquea los toques hasta que el lanzador cierra la pantalla.

## Commits (rama `tanda-11-r11`)
- `e83151e` feat(tanda11-r11): reiniciar_software en el backend y PUT /printer/config con reinicio
- `febef44` feat(tanda11-r11): el lanzador cierra pantallas y relanza Autoclave con una sola instancia
- `80e1a34` feat(tanda11-r11): confirmación y aviso de reinicio al cambiar la impresora
- (este informe, en el commit siguiente)

## Pruebas
`autoclave.__file__` = `C:\Users\tecni\Documents\codigo_autoclave\.claude\worktrees\agent-af1cb65d74e7fdf5b\src\autoclave\__init__.py` (con `PYTHONPATH=<worktree>/src`).

Pruebas nuevas, todas en verde (ningún proceso real se lanza ni se reinicia: los hilos de cierre se capturan, y uvicorn y `Popen` están simulados):
- `tests/test_r11_reinicio_software.py` (17; 26 tras la revisión): confirmar con el orden exacto `guardar → iniciar_apagado → auditar impresora_configurada → auditar software_reiniciado → detener_lazo → cerrar_base → solicitar(76)` y sin shutdown de Windows; la auditoría con motivo y estado; que con reinicio no se aplica en caliente; permitido en PREPARACION/PREPARADO/FALLA; rechazado en CICLO sin guardar nada (con y sin `reiniciar`); la carrera con un ciclo deshace la bandera; sin lanzador → 503 sin guardar; apagado en curso → 409; operador → 403; el flujo sin `reiniciar` (menú PySide) igual que antes; la secuencia sigue aunque fallen pasos; el lifespan no repite el stop; "Apagar equipo" sigue apagando Windows; el texto del evento en la bitácora.
- `tests/test_r11_relanzamiento.py` (14; 15 tras la revisión): código de salida 76 frente a 75; el vigilante no relanza solo el backend ante el 76; las pantallas se cierran sin relanzarse; el comando en desarrollo y congelado; el fallo de relanzamiento queda en el log; la espera a PID y puerto, y su tope; el lanzador completo con el orden `pantallas → pantallas cerradas → backend terminado → relanzar` y con los PID del lanzador y del backend; sin reinicio no hay relanzamiento; la instancia nueva no lanza el backend hasta que el puerto se libera; con el puerto todavía ocupado al vencer el tope NO lanza un segundo backend; `--esperar-pid` repetible.
- `tests/test_r11_reinicio_ui.py` (6; 9 tras la revisión): el controlador envía `reiniciar` y queda "reiniciando" sin releer; los rechazos (CICLO, sin lanzador, apagado en curso) muestran su motivo; textos es/en; pantalla QML real (offscreen): el diálogo con los dos textos, Cancelar no envía ningún PUT ni muestra el aviso, Confirmar envía el PUT con `reiniciar` y muestra el aviso, sin avisos QML.

Corrida de los módulos tocados y de los que los importan (`pytest -n auto`, 39 archivos, entre ellos los r11, t7/t8 de apagado, r8 de reinicio, b5/p2/o2a/c1b/p9 de impresora y Parámetros del equipo, p1/w10/t9/doble_pantalla/lanzar_ui_qml del lanzador, bitácora, i18n y v8b): **798 passed, 1 warning in 103.46s**. Tras la revisión de seguridad, la misma corrida: **811 passed, 1 warning in 72.98s**. La advertencia es un `UnicodeDecodeError` en el hilo lector de un `subprocess` de otra prueba (salida de consola en cp1252); no es de este cambio.

Pruebas existentes que se ajustaron: los dobles de `vigilar_pantallas` en `test_p1_lanzador_primer_arranque.py` y `test_w10_pantalla2_instalacion.py` aceptan ahora el argumento `detener` (una línea cada uno).

## Revisión de seguridad (hallazgo → qué se hizo)
Commits `bfad8e0` (SAF-01 a SAF-03) y `a71623e` (SAF-04).

- **SAF-01 (MEDIA)** — El bloqueo solo rechazaba CICLO. Se agregó `_motivo_no_reiniciable()` en `server.py`, que toma el criterio de R8 (`_motivo_bloqueo`) y lo amplía. Responde 409 en tres casos:
  - `modo_prueba_activo`: modo prueba activo, o el ALL_OFF de su salida aún sin confirmar (`_salidas_sin_confirmar_pendiente`).
  - `confirmacion_pendiente`: `estado_seguro.activo` con `requiere_confirmacion`. Sin este rechazo, la confirmación de D9-1.2 se perdería al reiniciar.
  - `estado_seguro_activo`: `estado_seguro.activo` en cualquier otro caso (actuando, pausado por el paro o sin datos). Es más estricto que `_estado_seguro_en_marcha()`, que deja pasar el caso "pausado".

  Se comprueba antes de guardar nada y otra vez bajo `_sm_lock`, en el mismo bloque que `iniciar_apagado()`. Si el segundo chequeo rechaza, la bandera vuelve a su valor anterior. FALLA solo se permite con `estado_seguro.activo` falso. La pantalla muestra un mensaje para cada caso (`opciones.equipo_err_reinicio_estado_seguro`, `_confirmacion` y `_modo_prueba`, en es y en). Pruebas: los cinco casos parametrizados (FALLA con estado seguro actuando, con confirmación pendiente, pausado por el paro, en modo prueba y con salidas sin confirmar); FALLA con el estado seguro terminado, que se permite; la nueva comprobación bajo el lock con su reversión; y los mensajes del controlador.
- **SAF-02 (BAJA)** — `PUT /printer/config` corre entero bajo un cerrojo propio, `_reinicio_lock`. El orden de cerrojos es siempre este primero y después `_sm_lock`. Leer, guardar y bloquear ya no se intercalan con otra solicitud. Prueba: la primera solicitud queda detenida entre guardar y bloquear. La segunda espera; después se rechaza (`apagado_en_curso`) sin tocar el archivo. Archivo y bitácora quedan de acuerdo: una sola `impresora_configurada`, con el valor escrito.
- **SAF-03 (BAJA)** — Si el bloqueo se rechaza y además no se puede devolver la bandera, ahora queda en la bitácora: `impresora_configurada` con el valor que quedó escrito y `detalle = {"reinicio": "rechazado", "reversion_fallida": true}`, además del log. Prueba: se simula un `OSError` al revertir.
- **SAF-04 (BAJA)** — En el `finally` del lanzador también cuenta como reinicio el caso en que el backend terminó con `CODIGO_REINICIO_SOFTWARE`, aunque el vigilante no lo haya visto porque las pantallas cerraron por su cuenta a la vez. Prueba con lanzador simulado.
- **SAF-06 (BAJA)** — **Pendiente.** No es un cambio acotado. La otra pantalla no consulta hoy ningún indicador del backend fuera del flujo de apagado: `GET /system/shutdown/estado` solo se consulta tras pedir el apagado desde la puerta 1. Mostrar el aviso allí exigiría un sondeo nuevo y una capa en la ventana principal (`app.py`/`Main.qml`), que son puntos de choque. Además, el backend se cierra pocos segundos después de confirmar, así que el aviso se vería muy poco tiempo. Por ahora el aviso solo lo ve la pantalla que pidió el cambio; la otra se cierra al reiniciar.
- **SAF-05 (nota)** — Si el ALL_OFF del reinicio quedó confirmado o no, queda solo en el log del backend. `control_loop.stop()` lo reintenta una vez y, si sigue sin confirmar, escribe el ERROR "ALL_OFF sin confirmar al detener; queda el watchdog de la tarjeta". No va en el detalle de `software_reiniciado`: esa auditoría se escribe antes de la secuencia, con la base aún abierta, y `stop()` no devuelve el resultado. Llevarlo a la bitácora exigiría cambiar `control_loop.stop`, que no se tocó.
- **SAF-07 (nota)** — psutil es dependencia declarada en `pyproject.toml` (`"psutil"`) y está fijada en `requirements.lock.txt` (`psutil==7.2.2`). `Autoclave.spec` no lo excluye. PyInstaller lo empaqueta por análisis de imports, igual que ya se usa en `core/runtime/estado_red.py` dentro del mismo exe. Si faltara, `_pid_vivo` devuelve False y decide solo la comprobación del puerto, sin arrancar nunca un segundo backend.

## DECISIONES SIN CONFIRMAR
1. **Una sola llamada en lugar de dos.** El reinicio va dentro de `PUT /printer/config` (campo `reiniciar`) y no en un `POST /system/restart` aparte. Así guardar y reiniciar se validan juntos, y si no se puede reiniciar no se guarda nada (con dos llamadas, la bandera podía quedar guardada sin reinicio). `reiniciar_software` sigue siendo una función reutilizable del backend; no tiene endpoint propio.
2. **Sin lanzador, 503 sin guardar.** Si el backend no fue lanzado por `Autoclave.exe` (desarrollo con `python -m autoclave.backend.main` o `ui_qml.lanzar`, o un backend ajeno ya escuchando), la pantalla responde 503 `reinicio_no_disponible`, no guarda nada y muestra "No se puede reiniciar el software desde esta pantalla: el cambio no se guardó.". Alternativa: guardar y pedir "reinicie a mano", que contradice el SUPUESTO de D11-1.2.
3. **CICLO también sin reinicio.** `PUT /printer/config` sin `reiniciar` (menú de ajustes PySide) ahora también se rechaza en CICLO, para cumplir D11-1.3 ("igual que las otras acciones de Parámetros del equipo"). Antes se permitía.
4. **Pantallas cerradas con `terminate()`.** El lanzador las cierra con `terminate()` y, si no cierran en 5 s, con `kill()`, igual que el Ctrl+C de `vigilar_pantallas`. Las pantallas no tienen salidas ni base: solo hablan con el backend por HTTP.
5. **Tope de 60 s para la instancia anterior.** Coincide con el "1 minuto" del aviso. Si vence, la instancia nueva sigue y usa el backend que responda; nunca lanza un segundo.

## PREGUNTAS PARA CRISTIAN
- Ninguna bloqueante. Riesgo residual a observar en el equipo: si algún hilo no daemon del backend impidiera que el proceso termine tras `sys.exit(76)`, el lanzador no vería el código y no relanzaría. El equipo quedaría con las salidas ya apagadas y la pantalla con el aviso "apague y encienda el equipo". Es el mismo camino de salida que el reinicio de R8, que ya existía.

## Pendientes
- Verificarlo en el equipo de pruebas con la próxima compilación: cambiar la impresora en PREPARADO, ver que el software se cierra y vuelve a abrir solo en menos de 1 minuto, y revisar en `lanzador.log` las líneas "El backend pidió reiniciar el software", "Autoclave relanzado" e "Instancia anterior terminada y puerto del backend libre".
- Puntos de choque tocados: `i18n/es.json` y `i18n/en.json` (6 claves `opciones.equipo_reinicio*`/`equipo_err_reinicio*` y `bitacora.ev/tipo.software_reiniciado`), `backend/server.py`, `ui_qml/doble_pantalla.py`, `exe_unico.py`, `OpcionesParametrosEquipo.qml`.

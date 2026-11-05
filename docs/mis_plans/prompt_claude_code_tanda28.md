# Prompt: tanda 28 — ajustes funcionales A7, A9, A10, A11, A12 y A13

Trabajo sin supervisión. Trabajas en el worktree `C:\Users\tecni\Documents\codigo_autoclave_t28`, rama `tanda28`, creada desde la punta de `tanda27` (la tanda 27 aún no está unida a `dev` y sigue corriendo en otra carpeta: NO toques `C:\Users\tecni\Documents\codigo_autoclave`, ni la rama `tanda27`, ni `dev`). Corre todo (pytest, QML, scripts) desde esta carpeta con `PYTHONPATH=<worktree>\src`. La suite de la 27 puede estar corriendo a la vez: no uses el puerto 8000 en las pruebas ni compiles (PyInstaller) en esta tanda. Al terminar NO unas a `dev`: deja la rama `tanda28` lista y escribe `CERRADO.txt` con el último commit; la unión (rebase sobre `tanda27`/`dev` una vez unida la 27) la hace el director. Informes, comentarios y mensajes de commit en español. Máximo 4 subagentes a la vez; los subagentes no corren la suite completa (solo sus pruebas); revisor de seguridad donde se indica y revisor final sobre el diff. Lleva `docs/informes/tanda28/estado.md` (paso → Hecho/Pendiente, último commit) al día tras cada commit y, al reanudar, sigue desde el primer paso pendiente. Sin push. Hallazgos numerados con severidad (`AJ28-NN`). Lo que decidas sin confirmación de Cristian se marca `DECISIÓN SIN CONFIRMAR`. Commits propios `A7`, `A9`, `A10`, `A11`, `A12`, `A13`; informe `docs/informes/tanda28/A_informe.md` con una sección por punto.

**No hay depuración en esta tanda.** Los puntos vienen de Cristian (5-nov). Orden: A7, A10, A9, A13, A11, A12. Al terminar: suite completa en verde y `docs/informes/tanda28/CERRADO.txt` (fecha, último commit de la rama, resultado de la suite). Una fila por punto en la hoja de banco T28. Donde abajo dice «hoja de banco T27» léase T28.

- **A7. Mensaje de incoherencia equivocado en Parámetros del equipo (Cristian, 5-nov).** Commit propio `A7`, sección en `A_informe.md`, junto con A6 y antes de la depuración.
  - Síntoma: al cambiar `presion_suministro_vapor` el rechazo dice «La presión de empaque debe quedar al menos 20 kPa sobre la atmosférica y el vacío de empaque al menos 10 kPa por debajo», que no corresponde.
  - Causa: `ConfigManager._incoherencia` y `_incoherencia_limites` devuelven el mismo código `"incoherente"`, y `parametros_equipo_controller._MENSAJES` lo traduce siempre a `opciones.equipo_err_empaque`.
  - Corrección:
    1. Backend: códigos distintos por regla, con detalle en la respuesta 422:
       - `incoherente_empaque`, con `presion_empaque`, `vacio_empaque`, `presion_atmosferica` y los márgenes;
       - `incoherente_limites`, con `regla` (`suministro_bajo_alivio` | `alivio_bajo_fondo` | `corte_bajo_alivio_chaqueta`) y los valores vigentes y propuestos de fondo, suministro, alivio de cámara, alivio de chaqueta y `presion_max_chaqueta_control`.
       - Revisa `backend/rutas/sistema.py:752`, el texto del 422 y `sesion_backend.codigos_conocidos`. Mantén `"incoherente"` solo si algún cliente lo necesita, y anótalo.
    2. UI: texto i18n es/en propio por regla, con los valores en las unidades vigentes. Ejemplo: «La presión de suministro de vapor debe quedar por debajo de los alivios de cámara ({alivio_camara}) y de chaqueta ({alivio_chaqueta}).» El mensaje se ve dentro de la ventana de ajuste (misma corrección que A6), sin `elide`.
    3. La ventana de ajuste muestra el rango válido efectivo de los parámetros acoplados (suministro, alivios, fondo, `presion_max_chaqueta_control`, empaque, vacío, atmosférica), calculado por el backend con la misma función que valida (`min_efectivo`/`max_efectivo` en la lectura de los parámetros del equipo), no repetida en QML.
    4. Pruebas:
       - cada regla devuelve su código y su texto;
       - suministro ≥ alivio da el texto de límites, nunca el de empaque;
       - el rango efectivo coincide con la validación;
       - cobertura por AST de todas las causas de `PUT /global_params` con texto es/en.
  - No cambies las reglas ni los márgenes. Fila en la hoja de banco T27.
- **A10. El estado seguro no termina tras corregir un parámetro (Cristian, 5-nov).** Commit propio `A10`, sección en `A_informe.md`, junto con A9.
  - Síntoma en el equipo: el estado seguro se activó con `rango_presion_atm` muy estrecho; Cristian lo amplió en Parámetros del equipo y, con la cámara ya dentro del nuevo rango, el estado seguro no se apaga.
  - Lo visto en el código: `ProtocoloEstadoSeguro.tick` evalúa `camara_segura.evaluar` con `self.config` = `ConfigManager` (valores vivos) y termina con 3 ticks seguros seguidos. En teoría el cambio rige. Encuentra por qué no terminó.
  1. Diagnóstico con una prueba que reproduzca el caso: protocolo en curso por sobrepresión o vacío con rango 1 kPa; durante el protocolo, `PUT /global_params` `rango_presion_atm` a 5 con la presión dentro de la nueva banda. Prueba y documenta cada candidato:
     - (a) el protocolo pausado por el modo prueba (no cuenta ticks, ESG-02);
     - (b) la temperatura por encima de `min(temp_max_apertura` global, del programa seleccionado y del programa del protocolo`)`;
     - (c) `_ai_vigente()` falso o una sonda sin lectura (ESS, ESG-01);
     - (d) un valor cacheado: `ProtocoloFallo`, `camara_segura` o la UI usan una copia del rango (revisa `protocolo_fallo.py:700`, el bloque que recorre `presion_admosferica`/`rango_presion_atm`, y si `ConfigManager.get` devuelve el valor nuevo tras fijar);
     - (e) el `ConfirmadorApagado` o el venteo del protocolo mantienen el estado aunque la cámara ya sea segura;
     - (f) el `ESTADO_SEGURO` de la UI sale de un campo de `/status` que no se recalcula.
  2. Corrección según la causa:
     - si es (d), (e) o (f), es un defecto: el protocolo y la UI siguen siempre el valor vigente y terminan a los 3 ticks seguros;
     - si es (a), el protocolo no cuenta en modo prueba (decidido), pero la fila de estado seguro debe decir «En pausa: modo prueba activo» (texto es/en, detalle ALD) y terminar sola al salir del modo prueba si la cámara ya es segura;
     - si es (b) o (c), es correcto: el detalle de la fila debe nombrar el motivo pendiente con su valor y su límite (p. ej. «Temperatura 92 °C, límite 80 °C»), para que no parezca colgado.
  3. Pruebas:
     - cambiar el rango durante el protocolo lo termina en 3 ticks si la cámara queda dentro;
     - en modo prueba se muestra la pausa y termina al salir;
     - con la temperatura alta, no termina y el detalle lo dice;
     - ningún valor del rango ni de la atmosférica se cachea en el protocolo.
  - No cambies el criterio de cámara segura ni los 3 ticks. Fila en la hoja de banco T27.
- **A9. Arranque con la cámara no segura sin protocolo activo (Cristian, 5-nov).** Commit propio `A9`, sección en `A_informe.md`, antes de la depuración. Si la línea base del paso 0 ya se tomó, rehazla después de la Parte A. Revisor de seguridad sobre A9 antes de seguir.
  - Contexto: lo normal es que un equipo encienda con la cámara en vacío o con algo de presión si se apagó con las puertas cerradas. En ese caso no se activa el protocolo de estado seguro. PREPARACION lo resuelve en segundo plano, como ya hace en `igualar_presion_camara` (aire atmosférico con vacío; venteo con presión, por la lenta en líquidos, vía `aplicar_venteo`/T1).
  - Hoy `services/domain/loop/control_loop.py:471` llama a `estado_seguro.iniciar(protocolo, origen="arranque")` cuando la cámara no está segura al arrancar (S9, tanda 9, D9-1.1/1.2).
  - Regla nueva:
    1. Encendido normal (el último ciclo terminó, o no hay ciclo) con la cámara no segura: NO se inicia `ProtocoloEstadoSeguro`. La máquina pasa a PREPARACION como siempre (tras la liberación del arranque, tanda 26), y PREPARACION iguala la presión y drena con sus reglas actuales.
       - En la UI no aparecen «Estado seguro en curso», la causa «arranque» ni el botón «Confirmar y llevar a estado seguro».
       - Sí siguen: «NO ABRIR» y el bloqueo de apertura e inicio mientras la cámara no sea segura (cámara segura no cambia), y los avisos PRE-03/PRE-04 de PREPARACION con su nivel actual.
    2. Arranque tras un ciclo interrumpido (el arranque marcó como interrumpido un ciclo sin fecha de fin): se conserva el protocolo de estado seguro de arranque tal como está, con las reglas del programa de ese ciclo (en líquidos, nunca la rápida con la carga caliente; modos 4/5).
       - Dentro del protocolo, reemplaza el origen «arranque» por «ciclo_interrumpido», con su texto es/en en la causa (`sistema.estado_seguro_causa_ciclo_interrumpido`) y el detalle ALD de la tanda 26.
       - Si no se puede saber si hubo un ciclo interrumpido (base no disponible, modo sin BD), trátalo como interrumpido (fail-safe) y anótalo.
    3. Busca y ajusta todo lo que dependía del origen «arranque»:
       - el texto `sistema.estado_seguro_causa_arranque` y los arneses QML;
       - la bitácora;
       - ARQ-04 de la tanda 26 (el estado seguro de arranque diferido hasta la liberación sigue igual en el caso 2);
       - `estado_seguro_silencioso` (ESS) y ESG-01/02;
       - el modo prueba (pausa del protocolo);
       - las pruebas de S9 y de la tanda 26.
       - Ninguna prueba de seguridad se relaja: las que fijaban el protocolo en un arranque normal se reescriben para fijar que no corre y que PREPARACION iguala; las del caso 2 quedan igual.
    4. Pruebas nuevas:
       - arranque normal con vacío: sin protocolo, PREPARACION abre `aire_atmosferico_camara` y la cámara llega a segura;
       - arranque normal con sobrepresión y programa sólido: venteo de PREPARACION;
       - arranque con un ciclo interrumpido de líquidos: el protocolo corre, solo por la lenta mientras la carga siga caliente, y causa «ciclo_interrumpido»;
       - sin base: se trata como interrumpido;
       - en todos los casos, NO ABRIR mientras no sea segura y ninguna salida antes de la liberación de la tanda 26.
    5. Riesgo: actualiza el control de S9 y HAZ-ARQ-01 en el registro de riesgos (D9-1.1 reemplazada por esta decisión de Cristian del 5-nov), la trazabilidad, CLAUDE.md (secciones de estado seguro y arranque) y una fila en la hoja de banco T27: encender con la cámara en vacío y con presión residual, y tras un corte en pleno ciclo de líquidos.
- **A13. Secado corto tras un ciclo fallido (Cristian, 5-nov).** Commit propio `A13`, sección en `A_informe.md`. Cambio de proceso clase C: revisor de seguridad obligatorio. Va después de A9 (comparte ProtocoloEstadoSeguro) y antes de A11/A12.
  - Motivo: tras un fallo la cámara llega a presión atmosférica, pero queda vapor de agua a alta temperatura. Abrir la puerta así es un riesgo de quemadura. Con carga sólida se hace un minuto de secado (vacío) para retirar el vapor residual antes de dar la cámara por segura.
  - Comportamiento (`ProtocoloFallo` / `ProtocoloEstadoSeguro`):
    1. Cuándo corre:
       - FALLO de un ciclo con carga sólida (`globals.tipo_carga == "solido"` exacto; ilegible = líquida, SAF-03);
       - el equipo tiene `bomba_vacio` y `vacio_camara` instaladas en el perfil;
       - el programa tiene secado (sección `secado` con modo distinto de 0).
       - CANCELADO y el estado seguro tras un ciclo interrumpido (punto A9) siguen la misma regla (`DECISIÓN SIN CONFIRMAR`: el vapor residual es el mismo).
    2. Cuándo NO corre (sin secado, el protocolo sigue como hoy y se anota la observación en el ciclo):
       - carga líquida;
       - paro activo;
       - datos del módulo E/S no vigentes;
       - presión de cámara o sonda Principal sin lectura;
       - alguna puerta instalada no confirmada cerrada;
       - modo prueba (pausa, como hoy);
       - fallo del propio sistema de vacío (alarmas o fallos de la bomba de vacío, del agua de la bomba, timeout de vacío del prevacío o del secado);
       - alivio por sobrepresión o cámara sellada D8-2.10 en curso.
    3. Secuencia: cuando el protocolo llega a presión normal (cámara en la banda atmosférica), antes de contar los ticks seguros:
       - (a) `SECADO_FALLO`: `bomba_vacio` + `vacio_camara` (y `agua_bomba` / `agua_intercambiador` como en la fase SECADO, con el mismo escalonado de apagado `_STAGGER_APAGADO_VACIO`), con todo vapor cerrado, durante `secado_tras_fallo_s`;
       - (b) `RUPTURA`: bomba y vacío apagados y `aire_atmosferico_camara` abierta hasta la banda atmosférica (con tiempo límite; al vencer, se sigue con el protocolo normal y aviso).
       - Con eso, la cuenta de 3 ticks seguros de siempre. Durante (a) y (b): «NO ABRIR», apertura e inicio bloqueados, fila de estado seguro con el texto «Secando vapor residual» (es/en, detalle ALD).
    4. Parámetro del equipo `secado_tras_fallo_s` (submenú Cámara segura, defecto 60, rango 0–300, 0 lo desactiva), con validación, i18n y auditoría como los demás.
    5. Ticket, PDF e historial del ciclo fallido: línea «Secado tras fallo: N s» u «omitido (motivo)».
    6. Pruebas:
       - FALLO sólido con equipo completo: vacío 60 s, ruptura con aire, estado seguro solo después;
       - líquido: no corre;
       - sin bomba en el perfil: no corre;
       - fallo de la bomba de vacío: no corre;
       - un paro durante el secado lo corta (todo OFF) y no se reanuda solo;
       - una puerta que se abre lo corta;
       - el parámetro en 0 lo desactiva;
       - el estado seguro no se da por alcanzado antes de terminar (b);
       - CANCELADO igual que FALLO;
       - las pruebas existentes del protocolo siguen en verde sin relajarse.
    7. Riesgo HAZ-SFF-01 en el registro (vapor residual al abrir; riesgo nuevo: vacío con la cámara aún caliente, que se mitiga solo con carga sólida), trazabilidad, `CLAUDE.md` (protocolo de fallo y estado seguro) y una fila en la hoja de banco T28.
- **A11. Card del cursor de la gráfica sobre la línea (Cristian, 5-nov).** Commit propio `A11`.
  - En la gráfica del ciclo (`GraficaCiclo.qml` y su lógica en Python), la card que acompaña al deslizador o cursor queda encima de las curvas y tapa la lectura.
  - La card se coloca donde no cubra ninguna serie: en la mitad vertical opuesta a los puntos de las curvas en el rango horizontal que ocupa la card. Si no cabe, va al costado del cursor, del lado con espacio.
  - Nunca sale del área de la gráfica y no tapa el cursor.
  - La posición la calcula una función pura en Python (`ui_qml/domain/`), probada con curvas altas, bajas, cruzadas y cerca de los bordes; QML solo dibuja.
  - Colores solo de `Tema/Colores.qml`; sin `elide`. Capturas en los dos temas.
- **A12. Prevacío atascado entre escape y vacío (Cristian, 5-nov).** Commit propio `A12`. Revisor de seguridad sobre A12.
  - Síntoma: según los parámetros de los pulsos, en el paso DECOMPRESION de un pulso (`prevacio.py`, `_ejecutar_paso`) la presión no baja de `atm + rango_presion_atm`. No entra vapor y la bomba de vacío no arranca, porque el cambio a VACIO_BAJO exige `pres <= atm + rango_presion_atm`. Ese rango es el de cámara segura (1–10 kPa) y el paso no tiene tiempo límite.
  - Corrección:
    1. Parámetro nuevo de programa en la sección `prevacio`: `presion_inicio_vacio` (clase «diferencia», kPa sobre la atmosférica; defecto 10, rango 0–30, `DECISIÓN SIN CONFIRMAR`). DECOMPRESION pasa a VACIO_BAJO con `pres <= atm + presion_inicio_vacio`. Ya no usa `rango_presion_atm`.
    2. Tiempo límite del paso: `timeout_descompresion` (min, defecto 5, rango 1–30, `DECISIÓN SIN CONFIRMAR`). Al vencer, FALLO con código y texto propios (es/en, detalle ALD) y protocolo normal. No se arranca la bomba a ciegas con la cámara a presión.
    3. Agrega los dos parámetros a todos los perfiles de `factory/` y `user/`, con migración al cargar (`migrar_parametros` de `cycle_manager.py`, defecto si falta, con auditoría como las migraciones anteriores) y validación en guardar y cargar. Etiquetas y descripciones i18n es/en en Parámetros del ciclo › Prevacío.
    4. Revisa en la misma fase cualquier otra comparación de prevacío contra `rango_presion_atm` o contra la atmosférica sin margen que pueda atascarse igual (p. ej. el cambio de VAPOR_ALTO a HOLD_ALTO con una `presion_alta_pulso` subatmosférica). Documéntala y corrígela con el mismo criterio, sin cambiar la secuencia de pasos, el escalonado `_STAGGER_APAGADO_VACIO` ni los timeouts existentes.
    5. Pruebas:
       - un pulso con la presión estancada en atm + 6 kPa y rango 5 pasa a vacío con `presion_inicio_vacio` 10;
       - el `timeout_descompresion` da FALLO con su código;
       - un programa sin los parámetros nuevos se migra con los defectos;
       - las validaciones;
       - las pruebas existentes de prevacío siguen en verde sin relajarse.
    6. Es un cambio de proceso (clase C): riesgo HAZ-PRV-01 en el registro de riesgos, trazabilidad, `CLAUDE.md` (secciones de fases) y una fila en la hoja de banco (repetir el ciclo con los parámetros de pulsos que se atascaban).

## Restricciones

- Sin cambio funcional fuera de lo descrito. Ninguna prueba de seguridad se relaja.
- Suite completa con `pytest tests`. Sin push. Cualquier duda de seguridad: se anota `DECISIÓN SIN CONFIRMAR` y se sigue con la opción más conservadora.

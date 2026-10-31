# Instrucción para Claude Code — Etapas E0 y E1 (fin de ciclo y puertas manuales)

Rama `dev`. Spec de referencia: `docs/mis_plans/planeacion_fin_de_ciclo_y_puertas.md` (v3). Informe base: `docs/informes/informe_verificaciones_fin_de_ciclo.md`.
**Responde y escribe el informe en español.** No hagas commit: Cristian confirma visualmente antes. El árbol tiene cambios ajenos sin confirmar (`docs/catalogo_alarmas.md` y otros): no los toques.

## Reglas
1. Antes de cada cambio: lee el código afectado y, si algo es ambiguo o contradice el informe, **detente y pregunta** (numerado y breve).
2. Pruebas primero: escribe la prueba que falla, luego el cambio. Ejecuta la suite completa **antes** (línea base) y **después**, y reporta ambos conteos. Comando: `python -m pytest -q -p no:cacheprovider`.
3. No ejecutes nada que pueda accionar hardware. No cambies versiones de dependencias.
4. No cambies **cuándo** se dispara ninguna alarma existente ni su identificador (la Parte A del catálogo de alarmas sigue pendiente), salvo lo indicado aquí.
5. Todo temporizador usa `time.monotonic()`.
6. Comentarios breves en español en las líneas clave.

## Evaluación previa (NTC-IEC 62304, Clase C)
Solicitudes de cambio: **CR-FC-01** (E0) y **CR-FC-02** (E1). Tocan funciones de seguridad (sensores, puertas, suministros, paro). Peligros relacionados: HAZ-FC-02 y HAZ-FC-04 (spec §10), PF-14 a PF-16 y PF-21 (§18). SOUP: sin cambios.

---

## E0 — Robustez ante lecturas inválidas (PF-15, V-07)

**Objetivo:** que ninguna lectura `None` provoque una excepción ni pase como válida en PREPARACION y PREPARADO.

E0-1. Crea una función pura y probada, por ejemplo `lectura_valida(valor)`, que devuelva False para `None` y para valores no finitos (NaN, inf). Úsala en `verificar_sensores()` de `preparacion.py` (`:130-138`) y de `preparado.py` (`:256-261`) para **temperaturas**: una temperatura `None` es un error de sensor igual que hoy lo es un 0 (misma alarma `ERROR_AI_<SENSOR>`, mismo comportamiento bloqueante). Las presiones conservan su comparación `== 0`.

E0-2. `temp_drenaje` en `preparacion.py` (`:261`→`:265`) y `preparado.py` (`:169`→`:173`): con `None` no debe lanzarse `TypeError`. Comportamiento: replicar el de `CicloState._mantener_drenaje()` ante `None` (léelo y dime cuál es). Además: alarma de sensor, el equipo **no queda listo**, y `esta_preparado()` no debe fallar. Reporta qué decidió ese método antes de copiar el comportamiento.

E0-3. `pres_chaqueta` y `pres_camara` en `preparacion.py` (`:171`, `:216`) y `preparado.py` (`:94`, `:136`): antes del primer dato válido (`None`) no se emiten órdenes de válvulas y el equipo no queda listo, sin excepción.

E0-4. **No cambies la estructura de `ControlLoop.run()`** (el `try/except` que captura la excepción del tick). Solo infórmame qué opciones hay para que una excepción en la máquina de estados no impida F0, el registro del ciclo ni el buzzer. Entra en el informe como propuesta.

**Pruebas E0:** para cada línea citada, una prueba con `None` que verifique: sin excepción, alarma correcta, equipo no listo y ninguna orden de válvula basada en el `None`. Incluye una temperatura `None` en cada sensor que hoy se revisa.

---

## E1 — Puertas manuales y entradas de suministro por perfil (PF-14, PF-16, PF-21, V-05, V-08)

### E1-1 Entradas de suministro declaradas por perfil
Hoy las cinco entradas (`agua_bomba`, `agua_generador`, `aire_comprimido`, `vapor_suministro`, `suministro_electrico`) se leen siempre, y una sin cablear (lee 0) bloquea el equipo (PF-16).

- Agrega al perfil de instalación (`sa/installation/profile.py` y su almacenamiento) un campo `supply_inputs`: diccionario con las cinco claves y valor booleano "el equipo tiene esta entrada cableada".
- **Valor por defecto si el campo falta: todas en True** (falla cerrada; un perfil existente sigue exigiéndolas todas).
- Una entrada declarada en False es "no aplica": se omite en `verificar_suministros()` de PREPARACION y PREPARADO, en `esta_preparado()`, en `SuministroElectrico.update()` / `control_loop.py:191-194` y en `ciclo.py:214-225`. **No** se trata como "presente y sana": no genera alarma, no apaga la chaqueta y no bloquea.
- Efecto concreto sobre `vapor_suministro` en False: `vapor_chaqueta` se controla solo por presión (se elimina la orden OFF forzada y su alarma `SUMINISTRO_VAPOR`). Esto debe resolver el conflicto ON/OFF del mismo tick en PRECALENTAMIENTO (`ciclo.py:517` contra `precalentamiento.py:74,88`); confírmalo con una prueba.
- Expón en `/status` la lista `entradas_no_monitoreadas` y escribe un `logger.warning` al arrancar con esa lista (aparecerá en Información del sistema).
- **No edites** el `installation_profile.json` real de Cristian (está `locked`). Entrega el procedimiento exacto (comando o script) para declarar para este equipo: solo `aire_comprimido` en True y las otras cuatro en False. Revisa también el asistente de instalación (`wizard.py`) para que permita fijarlas.

### E1-2 Puertas según el perfil
- `preparado.puertas_cerradas()` y `CicloState._verificar_puertas()` iteran sobre las puertas que declara el perfil (`door_count`), no sobre dos fijas.
- Para `door_type = simple`: **sin revisión de empaque** (`pres_empaque_*`) en `ciclo.py:184-204` ni en `verificar_sensores()` de PREPARACION (`preparacion.py:105-110`, `:120-128`).
- Para `door_type = advanced`: comportamiento idéntico al actual (pruebas de regresión que lo demuestren).
- Identificadores de alarma sin cambios: `PUERTA_N_ABIERTA` y `FALLO_PUERTA_N_ABIERTA`.

### E1-3 Lectura inválida de puerta
`SimpleDoor.update()` (`:58-62`) hoy no cambia el estado si la entrada es `None`. Debe tratarse como **puerta abierta** (posición segura). Si `DoorState` tiene un estado de error o desconocido, dime cuál y propón su uso antes de aplicarlo.

### E1-4 Apertura automática
- Con una puerta sin actuador (`tiene_actuador = False`), `finalizacion.apertura_automatica` no se muestra en Opciones (localiza dónde se arma esa lista de parámetros).
- En `CicloState._mantener_apertura_automatica()` (`ciclo.py:294-390`): si la puerta no tiene actuador, sale sin reintentos y **sin** generar `APERTURA_AUTOMATICA_DENEGADA`, aunque el JSON diga `true`.

### E1-5 Paro de emergencia con lógica de seguridad intrínseca (D-16)
- `EmergencyStop.update()` interpreta ahora el valor invertido: **paro = entrada en 0**, y también **sin datos** de la tarjeta (antes del primer cuadro). Entrada en 1 = sin paro.
- `preparacion.py:63` debe usar el flag `PARO_EMERGENCIA` en vez del DI crudo.
- Busca todo lugar que lea el DI del paro y reporta cuáles encontró. Actualiza el simulador y las pruebas que asumen 1 = paro.
- Aviso: con el cableado actual (contacto NO, lee 1 al pulsar) el equipo mostrará paro permanente hasta que Cristian cambie el cableado a NC. Es el fallo deseado; déjalo escrito en el informe y en el mensaje de la alarma.

**Pruebas E1:** perfil de una y de dos puertas; `simple` sin sensores de empaque inicia ciclo; `advanced` sin cambios; puerta `None` = abierta; cada combinación de `supply_inputs` (incluyendo campo ausente = todas requeridas); `vapor_suministro` en False no apaga la chaqueta; `suministro_electrico` en False permite `LISTO_PARA_CICLO`; apertura automática silenciosa sin actuador; paro con 0, con 1 y sin datos.

---

## Fuera de alcance de esta instrucción
El selector de fuente de vapor del menú de instalación (generador interno, caldera externa o mixto) y las salidas de vapor por fuente van en una etapa aparte (E1b). No modifiques esas salidas ahora.

---

## Entrega (informe en `docs/informes/informe_e0_e1.md`, en español)
1. Lista de archivos modificados, con una línea por cambio.
2. Conteo de pruebas antes y después, y pruebas nuevas por requisito.
3. Respuestas a E0-2 (qué hace `_mantener_drenaje` ante `None`) y E0-4 (opciones).
4. Procedimiento para declarar `supply_inputs` en este equipo.
5. Qué no pudiste verificar y las preguntas pendientes.
6. Recordatorio: sin commit. Cristian confirma visualmente.

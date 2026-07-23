# PREPARACION en paralelo (en vez de secuencial por pasos)

## Contexto

Hoy `preparacion_state` (`preparacion.py`) usa `self.step` (0-5) como
secuenciador: `ejecutor()` es una cadena `if/elif self.step == N` donde cada
paso solo llama a su función de verificación cuando le toca, y solo avanza al
siguiente paso si esa función retorna `True` (`preparacion.py:79-120`). Esto
bloquea condiciones que no dependen entre sí: por ejemplo
`igualar_presion_camara()` (paso 3) nunca se evalúa mientras la chaqueta
(paso 2) no haya llegado a su banda de presión, aunque ambas cosas podrían
resolverse en paralelo.

`preparado_state` (`preparado.py`) ya resuelve el problema análogo sin usar
step: `ejecutor()` llama las tres funciones de mantenimiento
(`mantener_chaqueta`, `mantener_presion_camara`, `mantener_drenaje`) sin
condicionar una a la otra (`preparado.py:75-82`), y `esta_preparado()`
calcula el "listo" como un AND de sus resultados, recalculado cada tick
(`preparado.py:205-220`).

Pedido del usuario: convertir PREPARACION al mismo patrón que PREPARADO. Las
verificaciones y condiciones (bandas de presión, lecturas de sensores,
salidas activadas) **no cambian** — solo cambia la forma de ejecutarlas, de
secuencial-bloqueante a paralela-continua.

## Conflicto detectado: válvula compartida `descompresion_rapida`

`igualar_presion_camara()` (paso 3) y `drenar_camara()` (paso 4) escriben la
misma salida (`set_do.descompresion_rapida_on()/off()`):

- `igualar_presion_camara()`: la activa cuando `pres_camara` está **por
  encima** de `presion_admosferica ± rango_presion_atm` (venteo/vacío);
  la desactiva (junto con `aire_admosferico_camara`) cuando está en banda o
  baja.
- `drenar_camara()`: la activa cuando hay agua residual
  (`agua_camara` DI activo); la desactiva cuando no hay agua.

Como hoy nunca corren en el mismo tick (pasos distintos), no hay conflicto.
Al paralelizar, si ambas llaman a `set_do` directamente, la que se ejecute
después en el código gana el tick — con orden fijo tipo `preparado.ejecutor()`,
`drenar_camara()` correría después de `igualar_presion_camara()` y la
sobreescribiría. Caso problemático: presión de cámara alta **sin** agua
residual → `drenar_camara()` fuerza la válvula cerrada cada tick,
`igualar_presion_camara()` nunca logra ventear, y PREPARACION queda
bloqueada indefinidamente (no hay timeout en este estado).

**Decisión (confirmada con el usuario):** combinar por OR. La válvula se abre
si *cualquiera* de las dos condiciones la necesita, y solo se cierra cuando
*ninguna* la necesita. Es físicamente correcto porque ambas comparten la
misma vía de alivio de presión/agua.

## Cambios

### 1. `preparacion.py` — quitar `self.step`, ejecutar las 4 condiciones cada tick

`ejecutor()` deja de ser una cadena `if/elif self.step`. Pasa a llamar, sin
condicionar unas a otras, en cada tick:

```python
def ejecutor(self):
    chaqueta_lista = self.suministrar_vapor_chaqueta()
    presion_ok, quiere_rapida_presion = self.igualar_presion_camara()
    drenaje_ok, quiere_rapida_drenaje = self.drenar_camara()
    temp_ok = self.verificar_temperatura_drenaje()

    if quiere_rapida_presion or quiere_rapida_drenaje:
        self.set_do.descompresion_rapida_on()
    else:
        self.set_do.descompresion_rapida_off()

    return chaqueta_lista and presion_ok and drenaje_ok and temp_ok
```

`run()` ya no resetea ningún step; simplemente retorna lo que `ejecutor()`
retorne cuando `supervisor()` pasa:

```python
def run(self):
    if self.estado.sensores_di["paro_emergencia"]:
        self.set_do.reset_all_outputs()
        self.alarm("PARO_EMERGENCIA", AlarmType.EMERGENCIA)
        self.set_do.buzer_emergencia()
        return False
    else:
        self.set_do.buzer_off()
        self.alarm_manager.clear("PARO_EMERGENCIA")

    if not self.supervisor():
        return False

    return self.ejecutor()
```

(El chequeo de emergencia se mueve del interior de `ejecutor()` al inicio de
`run()`, igual que en `preparado.run()` — confirmado con el usuario. Corrige
además que hoy, si sensores fallan a la vez que hay una emergencia,
`supervisor()` retorna `False` antes de llegar a `ejecutor()` y el manejo de
emergencia — `reset_all_outputs`, `buzer_emergencia` — nunca se ejecuta.)

`self.__init__` quita `self.step = 0`. `reset()` queda vacío (no se elimina:
`state_machine.py:38` lo sigue llamando al entrar a `GlobalState.PREPARACION`
y no hay razón para tocar ese wiring).

### 2. `igualar_presion_camara()` — retorna `(ok, quiere_rapida)`

Mismas condiciones y mismas salidas para `aire_admosferico_camara` y
`descompresion_lenta` que hoy. Solo cambia que ya no llama
`descompresion_rapida_on()/off()` directamente — en su lugar retorna si la
necesita:

```python
def igualar_presion_camara(self):
    presion_camara = self.estado.sensores_pres["pres_camara"]
    presion_atmosferica = self.config.get("presion_admosferica")
    rango_presion_atmosferica = self.config.get("rango_presion_atm")
    pres_cam_min = presion_atmosferica - rango_presion_atmosferica
    pres_cam_max = presion_atmosferica + rango_presion_atmosferica

    if pres_cam_min <= presion_camara <= pres_cam_max:
        self.set_do.aire_admosferico_camara_off()
        self.set_do.descompresion_lenta_off()
        self.alarm_manager.clear("PRESION_CAMARA_BAJA")
        self.alarm_manager.clear("PRESION_CAMARA_ALTA")
        return True, False

    if presion_camara < pres_cam_min:
        self.set_do.aire_admosferico_camara_on()
        self.alarm("PRESION_CAMARA_BAJA", AlarmType.ALERTA)
        return False, False

    # presion_camara > pres_cam_max
    self.set_do.aire_admosferico_camara_off()
    self.alarm("PRESION_CAMARA_ALTA", AlarmType.ALERTA)
    return False, True
```

### 3. `drenar_camara()` — retorna `(ok, quiere_rapida)`

```python
def drenar_camara(self):
    agua_residual = self.estado.sensores_di["agua_camara"]
    if not agua_residual:
        self.alarm_manager.clear("AGUA_RESIDUAL_CAMARA")
        return True, False

    self.alarm("AGUA_RESIDUAL_CAMARA", AlarmType.ALERTA)
    return False, True
```

### 4. `suministrar_vapor_chaqueta()` y `verificar_temperatura_drenaje()`

Sin cambios — no comparten salidas con nadie más, siguen retornando `bool`
como hoy y se llaman igual en cada tick.

### 5. `verificar_sensores()` / `verificar_suministros()`

Sin cambios de contenido. Se mantienen como están (listas fijas), no se
adopta la iteración genérica de `preparado.py` — eso sería una unificación
aparte, fuera de este alcance.

## Fuera de alcance

- No se toca `preparado.py` — el patrón ya es el deseado ahí, se usa solo
  como referencia.
- No se agrega debounce de alarmas (`generar_alarma_temporizada` /
  `tiempo_estable_alarma`) a PREPARACION. Las alarmas siguen siendo
  inmediatas, igual que hoy — el usuario pidió mantener las condiciones
  iguales, solo cambiar la forma de ejecución.
- No se agrega `puertas_cerradas()` a PREPARACION — ese chequeo es exclusivo
  de PREPARADO hoy y sigue siéndolo.
- No se unifica `verificar_sensores`/`verificar_suministros` entre
  `preparacion.py` y `preparado.py` pese a la duplicación ya señalada en el
  código (`preparado.py:222`).
- No se agrega timeout nuevo a PREPARACION.

## Pruebas

Tests existentes a revisar (referencian `self.step` o el orden secuencial y
van a necesitar actualizarse):
`tests/test_preparacion_suministro.py`, `tests/test_preparacion_chaqueta.py`,
`tests/test_preparacion_alarm_wording.py`.

Casos nuevos a cubrir:

- Chaqueta fuera de banda Y presión de cámara fuera de banda al mismo tiempo
  → ambas condiciones se evalúan y actúan en el mismo tick (antes, la
  segunda ni se llamaba hasta que la primera terminara).
- Presión de cámara alta (quiere `descompresion_rapida` abierta) sin agua
  residual (quiere `descompresion_rapida` cerrada) → la válvula queda
  abierta (gana el OR); `PRESION_CAMARA_ALTA` se resuelve sin bloquear por
  `drenar_camara`.
- Agua residual sin presión de cámara fuera de banda → válvula abierta por
  `drenar_camara`, `igualar_presion_camara` no la fuerza a cerrar.
- Ninguna de las dos necesita la válvula → queda cerrada.
- Las 4 condiciones se cumplen en el mismo tick → PREPARACION retorna `True`
  y la máquina transiciona a PREPARADO (sin pasar por steps intermedios).
- Falla de `verificar_sensores`/`verificar_suministros` (supervisor) →
  `ejecutor()` no se llama, ninguna salida cambia ese tick (comportamiento
  sin cambios respecto a hoy, salvo que ya no hay `step` que resetear).
- Paro de emergencia simultáneo con falla de sensores → el manejo de
  emergencia (`reset_all_outputs`, `buzer_emergencia`) se ejecuta igual,
  porque ahora el chequeo está antes de `supervisor()` (antes no se
  ejecutaba en este caso — bug corregido como parte de este cambio).

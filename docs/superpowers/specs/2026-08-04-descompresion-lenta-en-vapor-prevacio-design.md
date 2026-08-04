# Descompresión lenta activa durante pulsos de vapor en PRE_VACIO

**Fecha:** 2026-08-04
**Fase afectada:** `src/autoclave/state_machine/cycle_phases/prevacio.py`

## Problema

Durante los pulsos de tipo vapor de PRE_VACIO (pasos `VAPOR_ALTO` y `HOLD_ALTO`, donde
`vapor_camara` se energiza para llevar la cámara de vacío a `presion_alta_pulso_{tipo}`
y sostenerla), la válvula `descompresion_lenta` permanece cerrada. Debe estar activa
durante estos pulsos, igual que ya ocurre en otras fases (`esterilizacion.py`,
`calentamiento.py`).

## Diseño

`descompresion_lenta` se controla como espejo directo de `vapor_camara` dentro de
`prevacio.py`, sin temporizador propio ni parámetros nuevos en el JSON de ciclo (a
diferencia del patrón de dos estados usado en `esterilizacion.py` para su
`escape_lento_on_ester`/`off_ester`, que aquí no aplica porque el pedido es "activa
durante el pulso", no un duty cycle independiente).

Puntos de la máquina de pasos a modificar (`_ejecutar_paso`):

1. **`_PASO_VAPOR_ALTO`** — junto a `self.set_do.vapor_camara_on()`, agregar
   `self.set_do.descompresion_lenta_on()`.
2. **`_PASO_HOLD_ALTO`** — junto a `self.set_do.vapor_camara_on()`, agregar
   `self.set_do.descompresion_lenta_on()`.
3. **Fin de `HOLD_ALTO`** (cuando se cumple el hold y se llama
   `self.set_do.vapor_camara_off()` antes de `_avanzar_pulso()`), agregar
   `self.set_do.descompresion_lenta_off()`.
4. **Timeout de `VAPOR_ALTO`** (camino a `FaseResult.FALLO`, donde ya se llama
   `self.set_do.vapor_camara_off()`), agregar `self.set_do.descompresion_lenta_off()`.

Resultado: `descompresion_lenta` queda encendida en todo el tramo en que
`vapor_camara` está energizada dentro de un pulso (ramp-up + hold), y se apaga en el
mismo tick en que `vapor_camara` se apaga, sea por éxito o por fallo. No afecta los
pasos `DECOMPRESION`, `VACIO_BAJO` ni `HOLD_BAJO`.

## Fuera de alcance

- No se añaden parámetros nuevos a `parameters.prevacio` en los JSON de ciclo.
- No se toca el patrón de `descompresion_rapida` (ya maneja su propio ciclo en
  `DECOMPRESION`).
- No se modifican otras fases.

## Testing

Extender/crear pruebas para `PrevacioFase` verificando:
- `descompresion_lenta_on()` se invoca durante `VAPOR_ALTO` y `HOLD_ALTO`.
- `descompresion_lenta_off()` se invoca al completar `HOLD_ALTO` (transición a
  siguiente pulso/tipo/COMPLETADO) y al fallar por timeout en `VAPOR_ALTO`.
- No se invoca `descompresion_lenta_on()` durante `DECOMPRESION`, `VACIO_BAJO` ni
  `HOLD_BAJO`.

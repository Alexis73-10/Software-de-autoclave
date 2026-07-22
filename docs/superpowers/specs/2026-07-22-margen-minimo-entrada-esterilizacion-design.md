# Margen mínimo (hardcoded) de entrada a Esterilización

## Contexto

La fase `ESTERILIZACION` (`src/autoclave/state_machine/cycle_phases/esterilizacion.py`)
falla instantáneamente y sin tolerancia si la temperatura de cámara cae por debajo del
setpoint (`temp < t_est` → `FALLO ESTERILIZACION_TEMP_BAJA`, línea 75). La única
protección contra que la inercia del sensor o una lectura puntual errónea disparen ese
fallo en el primer tick es la condición de completación de la fase previa,
`CALENTAMIENTO` (`calentamiento.py:126-148`), que hoy exige:

```python
margen_ester = self.cycle.get_param("calentamiento", "margen_entrada_esterilizacion") or 0.5
t_completar = t_obj + margen_ester
```

Este margen es enteramente configurable vía el JSON del ciclo (ej.
`src/autoclave/cycles/user/bowe_dick.json`), sin ningún piso mínimo. Además, la
condición de completación actual **no valida presión en absoluto** — solo temperatura.

## Objetivo

Garantizar que Calentamiento nunca se dé por completado (y por tanto nunca se entre a
Esterilización) con temperatura o presión demasiado cerca del setpoint, sin depender de
que el JSON del ciclo esté bien configurado. El valor de margen mínimo debe estar
quemado en el código, no ser un parámetro editable, para que no pueda reducirse o
eliminarse por error de configuración.

## Diseño

### 1. Constante de seguridad no configurable

En `src/autoclave/state_machine/machine/parametros_globales.py`, que ya es el lugar
establecido en el proyecto para constantes de seguridad no editables (ej.
`TEMP_DRENAJE`), se añade:

```python
class ParametrosGlobales:
    ...
    MARGEN_MINIMO_ENTRADA_ESTERILIZACION = 0.2  # °C — piso no configurable
```

### 2. Piso sobre el margen de temperatura

En `calentamiento.py`, el margen leído del JSON se combina con el piso vía `max()`, de
modo que el JSON puede exigir un margen mayor pero nunca uno menor:

```python
margen_ester = max(
    self.cycle.get_param("calentamiento", "margen_entrada_esterilizacion") or 0.5,
    parametros_globales.MARGEN_MINIMO_ENTRADA_ESTERILIZACION,
)
t_completar = t_obj + margen_ester
```

### 3. Piso de presión derivado de la curva de saturación

Se añade una condición de presión a la sección de completación (hoy solo compara
temperatura), reutilizando `p_saturacion_kpa` (ya importado en el archivo):

```python
p_completar = p_saturacion_kpa(t_completar)
```

y se exige `pres >= p_completar` como condición adicional para declarar `COMPLETADO`,
tanto en la rama con sensor de líquido (`self.cap.has_liquid_sensor`) como en la rama
sin él. No se introduce un segundo número de margen en kPa: el único valor fuente de
verdad es el `0.2` en °C, convertido a su presión de saturación equivalente.

Como la presión pasa a ser parte de la condición de completación, se añade el guard
correspondiente (`if pres is None: return FaseResult.EN_CURSO`) antes de evaluarla,
análogo al guard ya existente para `temp is None` (línea 69-70).

### 4. Alcance

- Cambia únicamente la condición de completación de `CALENTAMIENTO` (sección 5 del
  método `update()`). No se toca el control de rampa (sección 6), ni la lógica de
  checkpoint (sección 4), ni ningún archivo de `esterilizacion.py`.
- `esterilizacion.py` no requiere cambios: su comportamiento sin tolerancia en el
  límite inferior es intencional y documentado en su cabecera; este diseño refuerza
  la garantía de que se entra a esa fase con colchón suficiente.
- No se agrega ningún parámetro nuevo a los JSON de ciclo.

## Pruebas

- Test unitario de `CalentamientoFase.update()`: con `margen_entrada_esterilizacion`
  del JSON en 0 (o ausente), verificar que la fase NO se completa hasta que
  `temp >= t_obj + 0.2` y `pres >= p_saturacion_kpa(t_obj + 0.2)`.
- Test unitario: con `margen_entrada_esterilizacion` del JSON en un valor mayor
  (ej. 1.0°C), verificar que se respeta ese margen mayor (el piso no lo recorta hacia
  abajo).
- Test unitario: rama con sensor de líquido — ambos sensores de temperatura deben
  cumplir el piso.
- Test unitario: si `pres is None`, la fase permanece en `EN_CURSO` sin lanzar
  excepción.

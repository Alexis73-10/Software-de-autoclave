# Corrección de polaridad de señal de atrapamiento de puertas

## Contexto

El sensor físico de atrapamiento de las puertas avanzadas (`DoorType.ADVANCED`) es un
contacto normalmente cerrado (NC). Físicamente:

- `0` = puerta atrapada
- `1` = operación normal (no atrapada)

El código actual en `src/autoclave/devices/puertas/advanced_door.py` interpreta la señal
al revés: `atrapamiento() == 1` se trata como "atrapada". Con esta polaridad invertida,
el sistema nunca detecta un atrapamiento real y puede entrar al estado `ATRAPADA`
exactamente cuando el sensor indica normalidad.

## Alcance

Solo afecta a puertas `ADVANCED`, que son las únicas que tienen el sensor de
atrapamiento configurado (ver `factory.py:_build_door_cfg`, `has_sensor`). Las puertas
`simple_door.py` no tienen este sensor.

Único punto de lectura de la señal en todo el código: `advanced_door.py`, método
`atrapamiento()` (líneas 199-203), consumido en un solo sitio: `_from_cerrando()`
(línea 478).

`status.py` (mapa crudo de entradas digitales `map_di` / `sensores_di`) no se toca:
es un passthrough genérico de bits de hardware sin inversión de polaridad para ningún
canal, y debe seguir siéndolo — la inversión es una interpretación de dominio específica
de esta señal, no una propiedad general de la capa de I/O.

## Cambio

1. **`atrapamiento()`** pasa de devolver el bit crudo del sensor a devolver un booleano
   semántico: `True` cuando el valor crudo es `0` (atrapada), `False` en cualquier otro
   caso, incluida la ausencia de sensor configurado o de dato disponible. Se agrega un
   comentario corto indicando que la señal es NC y por eso está invertida (no es obvio
   a partir del nombre del método).

2. **Sitio de uso** (`_from_cerrando`, línea 478): `if self.atrapamiento() == 1:` pasa a
   `if self.atrapamiento():`.

3. **`tests/test_advanced_door_safe_mode.py`**: el fixture `_make_door` fija
   `"atrapamiento_puerta_1": 0`. Bajo la semántica actual (antes del fix) eso significa
   "no atrapada", que es lo que las pruebas de `_from_cerrando` necesitan para ejercer
   el resto de su lógica (bomba de vacío, alarmas de modo seguro, umbral atmosférico).
   Tras el fix, `0` pasa a significar "atrapada", lo que rompería esas pruebas por una
   razón ajena a lo que verifican. Se actualiza el fixture a `1` (no atrapada) para
   preservar la intención original de esas pruebas.

4. **Test nuevo**: se agrega un test que verifica explícitamente la polaridad corregida:
   - `atrapamiento_puerta_1 = 0` durante `_from_cerrando()` → transiciona a
     `DoorState.ATRAPADA`.
   - `atrapamiento_puerta_1 = 1` durante `_from_cerrando()` → no transiciona a
     `DoorState.ATRAPADA`.

## Fuera de alcance

- `status.py` / mapa crudo de DI (sin cambios, ver justificación arriba).
- `simple_door.py` (no tiene sensor de atrapamiento).
- Cualquier otro canal de I/O NC/NO: no se detectó ningún otro punto del código con
  este mismo problema de polaridad invertida.

## Testing

- Ajuste del fixture existente en `tests/test_advanced_door_safe_mode.py`.
- Test nuevo de polaridad (descrito arriba) en el mismo archivo o en
  `tests/test_door_from_profile.py`, el que resulte más natural al implementar.
- Suite completa de tests debe seguir pasando (`pytest`).

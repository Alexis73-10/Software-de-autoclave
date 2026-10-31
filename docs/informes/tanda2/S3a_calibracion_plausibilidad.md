# S3a — Límites de plausibilidad de la calibración (pendiente T3 SAF-03 a)

Instrucción: `instruccion_claude_code_tanda_2.md` §2 S3: "agrega límites de plausibilidad por canal al catálogo y rechaza/avisa fuera de ellos (decide valores conservadores, anótalos)".

## Qué se hizo

- **Catálogo** (`core/managers/catalogo_parametros.py`): `CALIBRACION_PLAUSIBLE` (por tipo), `CALIBRACION_PLAUSIBLE_CANAL` (ajustes por sensor), `limites_calibracion()` y `evaluar_calibracion(tipo, puntos, sensor)`. Devuelve normal, aviso o rechazo con el motivo.
- **`PATCH /calibration/{tipo}/{sensor}`:** antes de tocar el archivo:
  - rechazo → 422 `CALIBRACION_IMPLAUSIBLE`;
  - aviso → 409 `CALIBRACION_REQUIERE_CONFIRMACION`, salvo `confirmar_fuera_de_rango: true` (se compara con `is True`, así que `"false"` no confirma);
  - un aviso confirmado queda en `audit_log` (`detalle.plausibilidad`: nivel, motivo, confirmado).
  - La confirmación **nunca salta un rechazo**: el rechazo se evalúa antes y no depende de ella.
- **Vista PySide de calibración** (`calibracion_sensor.py`): antes mostraba cualquier error como "inténtalo de nuevo". Ahora:
  - un 422 muestra el motivo;
  - un 409 de confirmación abre un diálogo ("¿Guardar de todos modos?") y, si el técnico acepta, reenvía con la confirmación;
  - un 409 o 503 de otro tipo muestra su detalle.
- La UI QML no tiene pantalla de calibración todavía (Opciones › Mantenimiento está pendiente); la confirmación solo está en la vista PySide y en la API.

## Reglas (valores conservadores; DECISIÓN SIN CONFIRMAR D-S3a-1)

Sobre los 4 puntos (mostrado y patrón, bajo y alto) y la recta resultante:

| Regla | Temperatura | Presión |
|---|---|---|
| Rango físico de los puntos | 0 a 200 °C | −10 a 450 kPa |
| Separación mínima de los dos puntos, **en lo mostrado y en el patrón** | 20 °C | 50 kPa |
| Pendiente (patrón / mostrado) ≤ 0 | rechazo | rechazo |
| Ganancia relativa fuera de… (aviso / rechazo) | 0,95–1,05 / 0,8–1,25 | 0,8–1,25 / 0,6–1,7 |
| Corrección en los puntos **y en los extremos del rango operativo** (0–150 °C; 0–350 kPa) | aviso > 5, rechazo > 15 | aviso > 25, rechazo > 90 |
| Desviación **acumulada** de la calibración resultante respecto de la neutra (1, 0), en los extremos operativos | aviso > 12, rechazo > 25 | aviso > 90, rechazo > 120 |

**Ajustes por canal:**
- Cámara de temperatura (Cámara 1, Cámara 2 y Referencia): aviso > 3 °C y rechazo > 10 °C.
- Drenaje: rango 0–150 °C y operativo 0–130 °C.
- Presión de cámara: rechazo > 50 kPa (el aviso queda en 25 kPa).
- Chaqueta y empaques usan los valores por tipo: sus calibraciones de campo corrigen hasta 49 kPa.
- Las ranuras temperature[3] (retirada) y temperature[5] (sin sensor) no tienen nombre en `map_temp`, así que no llegan al endpoint.

**Calibraciones reales de `calibration.yaml`** (todas deben seguir siendo aplicables; lo verifica una prueba):

| Canal | Puntos (mostrado → patrón) | Resultado |
|---|---|---|
| temp_camara | 60→60 y 134,5→135,7 | normal |
| temp_camara | 20→20 y 131,3→132,5 | normal |
| pres_camara | 20→20 y 307→318 | normal |
| pres_camara | 12→9,54 y 322→300 | normal |
| pres_chaqueta | 105→75 y 316→365 | aviso: pide confirmar |
| pres_empaque | 55→10 y 296→337 | aviso: pide confirmar |

## Pruebas

- Nueva `tests/test_s3_calibracion_plausibilidad.py` (39, con las de la revisión): normales, avisos, rechazos, pendiente invertida o amplificada, extrapolación a los extremos, cámara más estricta que chaqueta, drenaje, NaN/inf, calibraciones reales, el endpoint (rechazo sin tocar el archivo, confirmación, auditoría y que confirmar no salva un rechazo).
- `tests/test_calibracion_sensor_view.py`: 3 nuevas (rechazo mostrado y sin reintento, confirmación que reenvía, confirmación cancelada).
- Ajustadas: ninguna de las existentes (las 169 relacionadas pasan sin cambios).

## Revisión (safety-reviewer sobre el código)

Sin Críticos. Cubiertos desde el primer pase: pendiente ≤ 0 y amplificada, extrapolación a los extremos, límites por canal, confirmación en la UI PySide, que confirmar no salta un rechazo, NaN/inf, y que ninguna calibración real del YAML se rechaza.
- **S3a-01 (Alto):** una serie de calibraciones "normales" (p. ej. pasos de 2,9 °C) podía sumar una deriva ilimitada, porque cada una se mide contra lo mostrado, que ya lleva la calibración vigente. **Corregido:** se mide también cuánto se aparta la calibración **resultante** (ganancia y offset) de la neutra (1, 0) en los extremos operativos. Es aviso confirmable sobre 12 °C o 90 kPa y rechazo sobre 25 °C o 120 kPa. Las de `calibration.yaml` (hasta 75 kPa y 6 °C) caben. Prueba: pasos repetidos de 2,9 °C piden confirmar y después se rechazan.
- **S3a-04 (Medio):** un canal con **polinomio vigente** no estaba cubierto. **Corregido:** pide confirmación explícita, porque la recta nueva lo reemplaza fuera de los puntos.
- **S3a-03 (Medio):** margen de 0,7 kPa en chaqueta y empaques (la extrapolación a 0 kPa llega a ≈ 69 kPa). **Corregido:** `correccion_max` de presión por tipo sube de 70 a 90 kPa (la cámara conserva 50).
- **S3a-05 (Bajo):** el rango de presión admite hasta −10 kPa, para calibrar el cero de un manómetro con offset.
- **S3a-02 (Medio): ACEPTADO como riesgo.** El servidor no contrasta lo "mostrado" con la lectura viva: el técnico toma los dos puntos en momentos distintos (dos mesetas), así que no hay una sola lectura con la que compararlos. Queda auditado el dato declarado; la desviación acumulada y la pendiente acotan el daño posible. Para el expediente 62304.

## Pendientes y notas

- **Polinomios (`poly`):** hoy ninguna calibración de usuario del YAML es polinómica. Si apareciera una, pide confirmación (ver arriba); el rango operativo se sigue evaluando sobre la recta nueva.
- Si en campo hacen falta correcciones mayores (p. ej. sustituir una sonda), el límite se ajusta en el catálogo; hoy esa operación exigiría reemplazar la calibración de fábrica.

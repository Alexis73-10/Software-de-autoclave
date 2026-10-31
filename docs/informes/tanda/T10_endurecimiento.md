# T10 — Endurecimiento remanente

Instrucción: tanda 2026-10-14 §2 T10 con §1.6 y §1.2 (`tipo_carga`); borrador `planeacion_endurecimiento_backend_parametros.md` (rev 3, con adenda).

## 1. Estado de RB-01 a RB-09 (verificado antes de implementar)

| Requisito | Antes de T10 | En T10 |
|---|---|---|
| RB-01 Bloqueo por estado y exclusión con el inicio | Vigente: `guard_estado(DISTINTO_DE_CICLO, excepcion_ingeniero)` comprueba y cambia en memoria bajo `_sm_lock`, así que un cambio no se aplica después del inicio (T-17) | Sin cambios. No se agregó un `_param_lock` aparte (D-1 de la tanda prevalece) |
| RB-02 Identidad y rol | Vigente con token de sesión (autenticación v7) | Sin cambios |
| RB-03 Auditoría | `audit_log` (v1), pero un fallo de la bitácora no deshacía el cambio | **Atómica**: si `registrar_auditoria` falla, se revierten la memoria (incluidos los vinculados), el JSON y, si se había aplicado, la copia del ciclo en curso; responde 503 `BASE_OCUPADA`. Sin base, 503 de entrada. **Triggers de solo anexar** en `audit_log` (migración v4) |
| RB-04 Persistencia atómica | Temporal + fsync + `os.replace` (T3) | **Copia `<nombre>.json.bak`** antes de reemplazar. Un programa fuera del catálogo al cargar se recupera del `.bak` o queda **dañado**: no se selecciona, no se inicia ni se edita (409 `PROGRAMA_NO_EDITABLE`). `.bak` agregado a `.gitignore` |
| RB-05 Validación | Rango del propio JSON; coerción laxa (`bool("false")` daba `True`, `int(2.5)` daba 2, se aceptaban cadenas) | **Catálogo** `core/managers/catalogo_parametros.py` con rango efectivo = catálogo ∩ JSON. **Tipos estrictos** (bool, int, float sin NaN ni infinito, enum, sin cadenas numéricas). 422 `VALOR_INVALIDO`. Validación al cargar |
| RB-06 Concurrencia | No existía | `valor_anterior_esperado` **opcional**; si no coincide, 409 `VALOR_CAMBIO` con `valor_actual` |
| RB-07 Errores normalizados | Parcial (`RechazoApi`: `detail` + `codigo`) | Nuevos códigos: `VALOR_INVALIDO`, `VALOR_CAMBIO`, `PROGRAMA_NO_EDITABLE`, `BASE_OCUPADA` |
| RB-08 Servicio único | Hay una sola ruta (`PATCH /cycle/parameters` no existe en el backend) | Sin cambios |
| RB-09 Clientes | La vista PySide no envía token (dejó de funcionar con la autenticación) | Pendiente (se retira en la Fase 5) |

## 2. Otros cambios

- **`globals.tipo_carga`** (enum `solido | liquido`, por defecto `solido`) en los 5 programas. Regla: con `liquido`, la descompresión debe ser modo 4 o 5. Se valida al editar cualquiera de los dos parámetros (si no se cumple, nada cambia) y al cargar.
- **Límites del catálogo** (§1.6):
  - presión de 1 a 400 kPa;
  - temperatura de 1 a 200 °C;
  - tiempos con mínimo 1, salvo los que admiten 0 (Anexo A.3);
  - mínimos mayores que 0 para el Anexo A.1.
  - Ningún valor actual se rechaza; una prueba lo verifica sobre todos los JSON.
  - Tabla aplicada: `docs/informes/limites_catalogo.md`.
- **Permisos (1.6)**:
  - `PATCH /cycle/parameter` pasa de "solo ingeniero" a técnico + ingeniero (el técnico, fuera de CICLO, por el guard existente).
  - `permisos_opciones.py`: Conectividad para admin, técnico e ingeniero; Usuarios para admin e ingeniero; las cinco secciones técnicas para técnico e ingeniero.
  - `ESTADOS_EDICION` queda alineado con el backend: todo estado distinto de CICLO.
- Adenda en `planeacion_endurecimiento_backend_parametros.md`.

## 3. Pruebas

- `tests/test_t10_endurecimiento.py`. Cubre:
  - catálogo sobre todos los programas;
  - límites y tipos estrictos;
  - coherencia de `tipo_carga`;
  - `set_param` con el catálogo;
  - programa dañado;
  - endpoint: técnico, `VALOR_INVALIDO`, `VALOR_CAMBIO`, auditoría atómica, `.bak`, programa dañado, sin base;
  - permisos;
  - triggers.
- Ajustadas a la política nueva:
  - `test_cycle_set_param` (bool estricto);
  - `test_permisos_opciones`, `test_opciones_controller`, `test_opciones_qml` (Conectividad y estados);
  - `test_db_audit_log`, `test_t6_arranque_seguro` (esquema v4).

## 4. DECISIONES SIN CONFIRMAR

- D-T10-1: `valor_anterior_esperado` es opcional (la spec lo pide en toda petición), para no romper clientes. La UI QML nueva (T12) debe enviarlo siempre.
- D-T10-2: temperatura del modelo de 1 a 200 °C. El texto del Anexo B dice "0 a 200"; el mínimo 1 evita el 0 del Anexo A.2.
- D-T10-3: un programa de usuario dañado se registra como dañado y no se sustituye por el de fábrica homónimo (RB-04.4).
- D-T10-4: `ESTADOS_EDICION` incluye FALLA, EMERGENCIA e HIBERNACION, como el guard `DISTINTO_DE_CICLO` del backend.

## 5. PENDIENTES

- Directorio de datos persistente para `cycles/user` (RB-04.5) y migración de los 3 archivos actuales.
- RB-09 en clientes PySide: `params_ciclo.py` audita por su cuenta y no envía token. Se retira en la Fase 5.
- Mínimos del catálogo para los parámetros sin fila (escapes, factores, brechas, deltas, tasas): especificación 3.
- Revisores: T10 no figura en la lista de etapas de seguridad de la regla 7; no se ejecutaron.

## 6. Comprobaciones manuales de Cristian

- Como técnico, cambiar un parámetro desde la UI nueva cuando exista (T12). Con ciclo en curso debe rechazarse.
- Editar a mano un JSON de usuario con `presion_chaqueta: 0` y arrancar:
  - con `.bak` válido, el programa se recupera de la copia;
  - sin `.bak`, queda dañado y no se puede seleccionar.
- Revisar la tabla `docs/informes/limites_catalogo.md` y aprobar o ajustar los límites.

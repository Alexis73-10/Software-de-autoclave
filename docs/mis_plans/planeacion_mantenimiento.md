# Planeación — Registro y reportes de mantenimiento (preventivo / correctivo)

Software de Autoclave — Especifika S.A.S.
Versión 1 — 2026-10-20
Estado: **borrador para revisión de Cristian**

---

## 0. Alcance

**Incluye**

- Registro en el equipo de **mantenimiento preventivo** con un formulario definido por fábrica.
- Registro en el equipo de **mantenimiento correctivo** con acciones (repuestos, solicitudes, ajustes).
- Reporte PDF de cada mantenimiento: se ve en pantalla, queda guardado y se puede enviar por correo.
- Corrección del contador: solo el preventivo lo reinicia.

**Fuera de alcance (versión posterior)**

- Mantenimiento predictivo (contadores por componente: horas o ciclos). Tendrá su propia sesión de planeación.
- Seguimiento de estado de las solicitudes de repuesto (pendiente → recibido → instalado).
- Bloqueo de ciclos por mantenimiento. Todo es **solo informativo**.

---

## 1. Decisiones de Cristian (2026-10-20)

| ID | Decisión |
|---|---|
| D-1 | El equipo genera sus propios reportes de mantenimiento, para trazabilidad y auditoría. |
| D-2 | **Solo el preventivo reinicia el contador** de mantenimiento (días y ciclos). Ningún otro tipo lo reinicia. |
| D-3 | Plantilla del preventivo **por equipo**, armada con **grupos genéricos** que aplican o no según la construcción del equipo (por ejemplo, los pasos del generador solo si tiene generador). |
| D-4 | El formato del preventivo lo **define fábrica** y **no se puede modificar en el equipo**: es lo que el fabricante dice que se tiene que hacer. |
| D-5 | Calibración **solo desde la pantalla Sensores**. Se elimina como tipo de mantenimiento. |
| D-6 | Mantenimiento solo informativo por el momento. Un correctivo abierto tampoco bloquea ciclos. |
| D-7 | Reporte: se visualiza en pantalla, se guarda y se puede enviar por correo. |
| D-8 | Componentes para el predictivo: se definen en una sesión dedicada. |
| D-9 | Registran **técnico e ingeniero**. **Admin** solo consulta y reenvía reportes. |
| D-10 | Solicitud de repuesto en esta versión: **solo anotación**, sin estados. Sale en el PDF y en el correo. |
| D-11 | **El preventivo también puede generar solicitudes**: de repuesto, o de revisión o mantenimiento específico (por ejemplo, bomba de vacío o pistones neumáticos). |
| D-12 | Correo: mismos destinatarios que los reportes de ciclo (`correo.json`), o un correo escrito a mano, igual que en Historial de ciclos. |
| D-13 | Verificación de sensores dentro del preventivo: se registran el valor del patrón y la lectura del equipo. Si la diferencia supera la tolerancia, el punto queda "No cumple" y remite a Sensores. **El preventivo nunca calibra.** |

---

## 2. Hallazgos en el código actual (rama `tanda-5`)

| ID | Severidad | Hallazgo | Archivo |
|---|---|---|---|
| MNT-01 | **Alta** | `ultimo_mantenimiento()` devuelve el registro más reciente **de cualquier tipo**, así que hoy un correctivo, una calibración u "otro" reinician el contador. Contradice D-2: un correctivo podría ocultar un preventivo vencido. | `services/domain/logging/db_manager.py:465` |
| MNT-02 | Media | `calibracion` es un tipo válido de mantenimiento. Contradice D-5. | `core/runtime/servicio_mantenimiento.py:24` |
| MNT-03 | Baja | La tupla `TIPOS` está duplicada en el controlador QML. Se pueden desincronizar. | `ui_qml/controllers/mantenimiento_controller.py:17` |
| MNT-04 | Baja | `GET /maintenance/records` exige técnico o ingeniero. Según D-9, admin también consulta. | `backend/server.py` |
| MNT-05 | Baja | Las filas históricas de tipo `calibracion` no se pueden borrar (la tabla es de solo anexar). La UI y el PDF deben mostrarlas como "Calibración (histórico)" y nunca ofrecer ese tipo para un registro nuevo. | UI / i18n |

Lo que ya existe y se reutiliza:

- Tabla `mantenimientos` de solo anexar, con triggers que impiden UPDATE y DELETE.
- Protección de reloj: no se sella ningún registro con reloj atrasado o adelantado.
- Aviso no bloqueante `MANTENIMIENTO_VENCIDO`.
- `audit_log`.
- Generación de PDF (`ui_qml/exportacion/pdf_*.py`).
- Envío SMTP (`ui_qml/exportacion/correo.py`).

---

## 3. Modelo de datos (nueva migración)

Todas las tablas nuevas son de **solo anexar**, con triggers de UPDATE y DELETE igual que `mantenimientos`. Una corrección es un registro nuevo que apunta al corregido.

### 3.1 `mantenimientos` (existente; se agregan columnas con `ALTER TABLE ... ADD COLUMN`)

| Columna nueva | Tipo | Uso |
|---|---|---|
| `plantilla_version` | TEXT | Versión de la plantilla del preventivo usada (NULL en correctivo). |
| `plantilla_sha256` | TEXT | Hash del archivo de plantilla. Prueba qué formato exacto se aplicó. |
| `resultado` | TEXT | `conforme` / `no_conforme` (preventivo: si algún punto quedó "No cumple"). |
| `sintoma` | TEXT | Correctivo: falla o síntoma reportado. |
| `diagnostico` | TEXT | Correctivo: diagnóstico del técnico. |
| `ciclo_id` / `alarma_id` | INTEGER / TEXT | Correctivo: ciclo o alarma relacionados (opcionales). |
| `corrige_id` | INTEGER | Si este registro corrige a otro, el id del original. |
| `pdf_sha256` | TEXT | Hash del PDF guardado al cerrar el registro. |

Tipos válidos: `preventivo`, `correctivo`, `otro` (ver P-3). `calibracion` sale de `TIPOS` (MNT-02).

**Regla del contador (MNT-01):** la base del cálculo es el último registro con `tipo = 'preventivo'`. Un preventivo que corrige a otro (`corrige_id` no nulo) no mueve la base. La fecha base sigue siendo la del preventivo original.

### 3.2 `mantenimiento_items` (nueva): respuestas del preventivo

| Columna | Tipo |
|---|---|
| `id` | INTEGER PK |
| `mantenimiento_id` | INTEGER NOT NULL (FK) |
| `grupo_id` / `item_id` | TEXT NOT NULL (ids estables de la plantilla) |
| `respuesta` | TEXT: `cumple` / `no_cumple` / `na` |
| `valor` / `valor_patron` | REAL (mediciones y verificación de sensores) |
| `unidad` | TEXT |
| `observacion` | TEXT |

### 3.3 `mantenimiento_acciones` (nueva): acciones del correctivo y solicitudes del preventivo

| Columna | Tipo |
|---|---|
| `id` | INTEGER PK |
| `mantenimiento_id` | INTEGER NOT NULL (FK) |
| `tipo_accion` | TEXT: `cambio_repuesto` / `solicitud_repuesto` / `solicitud_revision` / `ajuste_fisico` / `otro` |
| `componente` | TEXT |
| `referencia` | TEXT |
| `cantidad` | INTEGER |
| `serial_retirado` / `serial_instalado` | TEXT (solo `cambio_repuesto`) |
| `urgencia` | TEXT: `normal` / `urgente` (solo solicitudes) |
| `descripcion` | TEXT |

- En un **preventivo** solo se permiten `solicitud_repuesto` y `solicitud_revision` (D-11).
- En un **correctivo**, todas.

### 3.4 Atomicidad

El encabezado, los ítems, las acciones y la fila de `audit_log` (`mantenimiento_registrado`) se escriben en **una sola transacción**. Si cualquiera falla, no queda nada (misma regla que RB-03.5: sin bitácora no hay cambio).

---

## 4. Plantilla del preventivo (definida por fábrica)

### 4.1 Ubicación y protección

- El archivo vive en `src/autoclave/config/mantenimiento/plantilla_preventivo.json` y viaja con el paquete de software.
- No hay endpoint ni pantalla que la escriba.
- Cambiar la plantilla = nueva versión del software. Queda bajo control de cambios (IEC 62304 §6 y §8).
- El registro guarda `plantilla_version` y `plantilla_sha256`.
- Al arrancar se valida (esquema, ids únicos, expresiones `aplica_si` conocidas). Si es inválida:
  - el **preventivo queda no disponible** con un mensaje claro (falla cerrada);
  - el correctivo sigue funcionando;
  - el evento queda en `audit_log`.

### 4.2 Estructura propuesta

```json
{
  "version": "1.0.0",
  "grupos": [
    {
      "id": "bomba_vacio",
      "titulo": {"es": "Bomba de vacío", "en": "Vacuum pump"},
      "aplica_si": "has_vacuum",
      "items": [
        {"id": "bv_ruido", "tipo": "check", "obligatorio": true,
         "texto": {"es": "Verificar ruido y vibración anormales", "en": "Check for abnormal noise and vibration"}},
        {"id": "bv_vacio_max", "tipo": "medicion", "unidad": "kPa", "min": -95, "max": -80,
         "texto": {"es": "Vacío máximo alcanzado", "en": "Maximum vacuum reached"}}
      ]
    },
    {
      "id": "sensores",
      "titulo": {"es": "Verificación de sensores", "en": "Sensor verification"},
      "aplica_si": "siempre",
      "items": [
        {"id": "vs_temp_camara", "tipo": "verificacion_sensor", "sensor": "temp_camara",
         "unidad": "°C", "tolerancia": 0.5,
         "texto": {"es": "Temperatura de cámara contra patrón", "en": "Chamber temperature vs. reference"}}
      ]
    }
  ]
}
```

Los textos de ejemplo son **marcadores de posición**. El contenido real de cada grupo lo define Cristian (P-1).

### 4.3 Tipos de ítem

| Tipo | Captura | "No cumple" automático |
|---|---|---|
| `check` | Cumple / No cumple / N.A. | — |
| `medicion` | Valor numérico (teclado numérico) | Si el valor queda fuera de `[min, max]` |
| `verificacion_sensor` | Valor del patrón + lectura del equipo (la lectura se toma en vivo, con opción de digitarla) | Si la diferencia supera `tolerancia`; muestra "Calibrar desde Sensores" (D-13) |
| `texto` | Texto libre (teclado alfanumérico) | — |

| `comparacion_manometro` | Lectura del manómetro (digitada) + lectura en vivo del transductor convertida a manométrica | Si la diferencia supera `tolerancia` |

Campos adicionales de ítem (2026-10-21):

| Campo | Uso |
|---|---|
| `si_no_cumple` | Texto de guía que aparece al marcar "No cumple". Puede precargar una acción sugerida (solicitud de repuesto o de revisión con el componente ya lleno). |
| `por_puerta` | El ítem se repite para Puerta 1 y Puerta 2 en equipos de dos puertas (las dos puertas son siempre del mismo tipo: el perfil tiene un único `door_type`). |
| `advertencia` | Riesgo para el técnico, mostrado antes de ejecutar el paso. |
| `frecuencia` | Por defecto, cada preventivo. Se define ítem por ítem a medida que se completa la plantilla (D-14). |
| `unidad_fija` / `referencia` | Ver §4.6. |

Reglas:

- Elegir **N.A.** o **No cumple** exige observación.
- Un ítem `obligatorio` sin respuesta impide cerrar el preventivo.

### 4.4 Condiciones `aplica_si` (lista cerrada, sin expresiones libres)

| Condición | Fuente en el código |
|---|---|
| `siempre` | — |
| `has_vacuum` | `EquipmentCapabilities` |
| `has_full_jacket` | `EquipmentCapabilities` |
| `has_liquid_sensor` | `EquipmentCapabilities` |
| `dos_puertas` | `profile.door_count >= 2` |
| `puerta_abatible` | `profile.door_type` ∈ {SIMPLE, LOCKING, MOTORIZED, MOTORIZED_LOCKING} (empaque de compresión) |
| `puerta_motorizada` | `profile.door_type` ∈ {MOTORIZED, MOTORIZED_LOCKING} (abatible con brazo motorizado) |
| `puerta_bloqueo` | `profile.door_type` ∈ {LOCKING, MOTORIZED_LOCKING} |
| `puerta_guillotina` | `profile.door_type` = ADVANCED (guillotina neumática, único tipo con empaque inflable) |
| `generador_interno` | `profile.vapor_source` ∈ {generator, mixed} |
| `caldera_externa` | `profile.vapor_source` ∈ {boiler, mixed} |
| `enfriamiento` | `profile.cooling_level > 0` |
| `impresora` | impresora habilitada |
| `neumatica` | **no existe en el perfil**, ver P-2 |

Una condición desconocida en la plantilla la invalida (§4.1). Nunca se asume que "aplica" ni que "no aplica" por un nombre mal escrito.

### 4.5 Grupos genéricos propuestos (Cristian ajusta, P-1)

1. General / cámara
2. Sello y puerta manual
3. Puertas automáticas (`puerta_motorizada`)
4. Chaqueta (`has_full_jacket`)
5. Generador interno (`generador_interno`)
6. Línea de vapor externa (`caldera_externa`)
7. Bomba de vacío (`has_vacuum`)
8. Neumática: pistones y actuadores (`neumatica`)
9. Válvulas y filtros
10. Válvula de seguridad
11. Intercambiador / agua (`enfriamiento`)
12. Verificación de sensores
13. Eléctrico / tablero
14. Impresora (`impresora`)

### 4.6 Unidades (D-15)

- **Válvulas de seguridad:** unidad fija **psi manométrico** (`unidad_fija: "psi_man"`), porque así viene marcada la válvula.
- **Resto de mediciones** (vacío, verificación de sensores, comparación de manómetros): se capturan y muestran en la **unidad seleccionada en el equipo**.
- **Almacenamiento:** canónico en kPa, con `referencia` explícita (`absoluta` o `manometrica`) en cada medición de presión. El sistema trabaja en presión absoluta y los manómetros leen presión manométrica. La conversión usa la presión atmosférica local configurada, y el valor de atmosférica usado queda guardado en el registro para que la comparación sea reproducible.

---

## 5. Flujo en pantalla (Opciones › Mantenimiento)

Pestañas:

- **Estado**: lo que existe hoy (próximo vencimiento, ciclos restantes, intervalos).
- **Preventivo**
- **Correctivo**
- **Historial**

**Preventivo**

1. Asistente grupo por grupo. Solo se muestran los grupos que aplican al equipo. Hay un indicador de avance (grupo n de N).
2. Al final de cada grupo se pueden agregar solicitudes de repuesto o de revisión (D-11).
3. Pantalla de resumen: puntos "No cumple", solicitudes y observación general → **Confirmar y registrar**.
4. Si hubo "No cumple", se ofrece abrir un correctivo enlazado. No es obligatorio.
5. Se reinicia el contador y se muestra el PDF.

**Correctivo**

1. Síntoma, diagnóstico, y ciclo o alarma relacionados (opcional).
2. Lista de acciones: agregar cambio de repuesto, solicitud, ajuste físico u otro.
3. **Confirmar y registrar** → PDF. **No toca el contador.**

**Historial**

- Lista con filtro por tipo.
- Abrir un registro muestra su PDF, con dos acciones: **Enviar por correo** y **Registrar corrección** (crea un registro nuevo con `corrige_id`).

**Reglas comunes**

- Se puede registrar en cualquier estado **distinto de CICLO** (regla general de escritura).
- El formulario en curso vive **solo en memoria**. Si se cancela, o si la sesión expira antes de confirmar, no queda nada registrado ni ningún borrador (ver P-6).
- Bilingüe español/inglés: los textos de la plantilla traen `es` y `en`, y el resto va por el catálogo i18n.

---

## 6. Reporte PDF y correo

**Contenido del PDF**

- Encabezado del equipo: modelo, serie, `machine_id`, clase.
- Tipo, fecha y hora del registro, técnico (usuario de la sesión) y contador de ciclos.
- Preventivo: versión de la plantilla y, por grupo, cada ítem con su respuesta, valor y observación; resultado conforme / no conforme.
- Correctivo: síntoma, diagnóstico y tabla de acciones.
- Solicitudes de repuesto y de revisión.
- Observación general.
- Espacio de firma del técnico y de "recibido por" (cliente), para firmar en papel.
- Si el registro corrige a otro: "Corrige el registro N.º X".

**Guardado**

- Al confirmar se genera el PDF y se guarda en `data/reportes_mantenimiento/MNT-<id>-<fecha>.pdf`.
- Su SHA-256 se registra en `pdf_sha256`.
- Reabrir desde Historial muestra el archivo guardado. Si falta o su hash no coincide, se regenera desde la base y el evento queda en `audit_log`.

**Correo**

- Mismo módulo `correo.py` y mismos destinos de `correo.json`, o una dirección escrita a mano (D-12).
- Asunto: `Mantenimiento <tipo> — <modelo> <serie> — <fecha>`.
- El envío (exitoso o fallido) queda en `audit_log`. Un fallo de envío no afecta el registro.

---

## 7. Roles (D-9)

| Acción | Técnico | Ingeniero | Admin |
|---|---|---|---|
| Registrar preventivo o correctivo | ✔ | ✔ | — |
| Registrar corrección | ✔ | ✔ | — |
| Ver historial y PDF | ✔ | ✔ | ✔ |
| Reenviar por correo | ✔ | ✔ | ✔ |
| Editar intervalos (existente) | ✔ | ✔ | — |
| Modificar la plantilla | — | — | — (solo fábrica, con una versión nueva del software) |

---

## 8. Impacto normativo y riesgos

- **Integridad del registro:** solo anexar, correcciones con referencia, hash de plantilla y de PDF, y protección de reloj. Cubre trazabilidad de registros de mantenimiento (soporta 62304 §9 / ISO 13485 §7.5.4 servicio).
- **Riesgo asociado a MNT-01:** un aviso de mantenimiento suprimido indebidamente lleva a un equipo sin preventivo y a una degradación no detectada (sello, válvula de seguridad, sensores). Es indirecto, pero hay que registrarlo en el fichero de gestión de riesgos (ISO 14971) con la corrección como medida de control y su prueba como verificación.
- **Clasificación:** el módulo no actúa sobre salidas ni bloquea ciclos. Mientras no exista una justificación de segregación documentada (62304 §4.3), se trata con la clase del sistema (C): requisitos, pruebas unitarias y trazabilidad.
- **Plantilla como configuración de fábrica:** su contenido es un requisito del fabricante. Cada versión debe quedar en la lista de configuración del release.

---

## 9. Etapas de implementación (para Claude Code)

| Etapa | Contenido | Criterio de terminado |
|---|---|---|
| E1 | MNT-01, MNT-02, MNT-03 y MNT-05 (detalle en §10) | Pruebas nuevas y existentes en verde |
| E2 | Migración: columnas nuevas, `mantenimiento_items` y `mantenimiento_acciones`, triggers, escritura atómica | Pruebas de migración sobre una base existente; UPDATE y DELETE abortan |
| E3 | Cargador y validador de plantilla, condiciones `aplica_si`, armado del formulario por equipo | Pruebas por cada clase de equipo y cada combinación de perfil; una plantilla inválida deja el preventivo no disponible |
| E4 | Endpoints: `GET /maintenance/form`, `POST /maintenance/preventive`, `POST /maintenance/corrective`, `POST /maintenance/records/{id}/correction`, `GET /maintenance/records/{id}/pdf`, `POST /maintenance/records/{id}/email`; MNT-04 | Roles según §7; rechazo en CICLO |
| E5 | Pantallas QML (§5), con teclados existentes e i18n | Revisión visual de Cristian |
| E6 | PDF y correo (§6) | PDF revisado por Cristian; envío real de prueba |
| E7 | Plantilla v1.0.0 con el contenido real (P-1) y prueba en banco | Hoja de banco firmada |

E1 puede ir ya. E3–E7 dependen de P-1 y P-2 para el contenido, pero no para el código.

---

## 10. Instrucción para Claude Code — Etapa E1

> Responde y reporta en español.
>
> Contexto: `docs/mis_plans/planeacion_mantenimiento.md`, §2 y §3.1.
>
> 1. **MNT-01.** En `db_manager.py`, `ultimo_mantenimiento()` debe devolver el último registro con `tipo = 'preventivo'`, ordenado por `fecha DESC, id DESC`. Agrega un parámetro opcional `tipo: str | None = "preventivo"` para no romper a otros llamadores; revisa todos los usos con grep. `ServicioMantenimiento._ultimo()` y `reloj_no_confiable()` usan ese valor. Ojo: `reloj_no_confiable()` compara contra la fecha del último mantenimiento. Decide y deja comentado si esa comparación debe usar el último registro de **cualquier** tipo (para la protección del reloj sí conviene, porque ningún registro nuevo puede quedar con fecha anterior al último registro existente). Agrega `ultimo_registro()` sin filtro para ese uso.
> 2. **MNT-02.** Quita `"calibracion"` de `TIPOS` en `servicio_mantenimiento.py`. Un `POST /maintenance/records` con `tipo="calibracion"` debe dar 422 `validacion`.
> 3. **MNT-03.** El controlador QML importa `TIPOS` del servicio en vez de duplicarlo. Si eso trae dependencias indeseadas a la UI, muévelo a un módulo de constantes compartido.
> 4. **MNT-05.** La UI y el historial deben mostrar las filas existentes de tipo `calibracion` como "Calibración (histórico)" / "Calibration (historical)" en el catálogo i18n, sin ofrecerlo como opción nueva.
> 5. Pruebas, en `tests/test_m1_mantenimiento_*.py` o en un archivo nuevo:
>    - preventivo → correctivo: la base sigue siendo el preventivo (días y ciclos);
>    - correctivo y "otro" no resuelven `MANTENIMIENTO_VENCIDO`;
>    - un preventivo sí lo resuelve;
>    - sin ningún preventivo, la base es la instalación aunque haya correctivos;
>    - el registro de `calibracion` es rechazado;
>    - una fila histórica de `calibracion` no afecta el contador.
> 6. Corre toda la suite. No hagas commit hasta que yo confirme.
>
> No toques `state_machine.py` (tiene cambios locales sin commit).

---

## 11. Pendientes

| ID | Pendiente | Responsable |
|---|---|---|
| P-1 | Contenido de cada grupo: ítems, tipos, rangos, tolerancias, obligatoriedad. Confirmar o ajustar la lista de §4.5. | Cristian |
| P-2 | Pistones neumáticos: el perfil de instalación no tiene ningún campo que diga si el equipo tiene neumática. ¿Se deriva del tipo de puerta, o se agrega un campo al perfil (y al asistente de instalación)? | Cristian |
| P-3 | ¿Se conserva el tipo `otro`? Propuesta: eliminarlo. Todo lo que no es preventivo es correctivo, y el correctivo ya tiene la acción "otro". | Cristian |
| P-4 | Predictivo: sesión dedicada (D-8). | Cristian + Claude |
| P-5 | Seguimiento de solicitudes de repuesto (estados). | Versión posterior |
| P-7 | **Discrepancia:** ajuste de la válvula de seguridad de cámara. El registro de construcción física dice 40 psi; Cristian indicó 45 psi el 2026-10-21. Confirmar el valor real de placa. | Cristian |
| P-8 | Tolerancia de la comparación manómetro contra transductor (cámara, chaqueta, empaque). | Cristian |
| P-9 | Presión a la que se hace el accionamiento manual de la válvula de cámara (ver §12.1, nota). | Cristian |
| P-10 | Confirmar el ítem propuesto `vs_precinto` (precinto o sello del ajuste intacto, placa legible). | Cristian |
| P-6 | Confirmar que no se guarda borrador del formulario en curso (§5). Un preventivo largo en pantalla táctil podría perderse si la sesión expira; la alternativa es un borrador local no auditado que se descarta al confirmar. | Cristian |

---

## 12. Contenido de la plantilla v1 — equipos de piso (PISO y PISO_LAB)

Decisiones adicionales (2026-10-21):

| ID | Decisión |
|---|---|
| D-14 | Las frecuencias por ítem no están registradas; se definen a medida que se completa la plantilla. Por defecto, cada preventivo. |
| D-15 | Unidades según §4.6. |
| D-16 | Las válvulas de seguridad **no** se recertifican con un tercero: no hay registro de certificado. |
| D-17 | Válvulas de seguridad: cámara **45 psi** (ver P-7), chaqueta **45 psi**, generador interno **75 psi**. La del generador va en este grupo, con condición `generador_interno`. |
| D-18 | Las válvulas descargan al ambiente (sin tubería); se revisa que la salida no esté obstruida. |
| D-19 | Manómetros en equipos de piso: cámara (uno por puerta), chaqueta (uno por puerta), empaques (uno por puerta) y generador interno (visible desde la puerta de mantenimiento). |
| D-20 | Presión de empaque: se verifican las dos lecturas, el sensor del equipo y el manómetro de la unidad de mantenimiento. |
| D-21 | Lubricante: grasa de silicona grado alimentario NSF H1, compatible con empaques de silicona (VMQ), resistente a vapor y hasta 150 °C, apta para superficies de deslizamiento hasta 40 psi; en su defecto, grafito como lubricante seco. |
| D-22 | Las puertas abatibles (simple, con bloqueo, motorizada, motorizada con bloqueo) tienen empaque de **compresión**; solo la guillotina (avanzada) tiene empaque inflable. |

Los grupos 1 y 2 se hacen en **cada preventivo** (Cristian, 2026-10-20).

### 12.1 Grupo 1 — Válvulas de seguridad (`siempre`)

Se repite por válvula:

| Válvula | Ajuste |
|---|---|
| Cámara | 45 psi man (P-7) |
| Chaqueta | 45 psi man |
| Generador (`generador_interno`) | 75 psi man |

| id | Tipo | Texto | Si no cumple |
|---|---|---|---|
| vs_fugas | check | Sin evidencia de fugas de vapor en la válvula ni en sus conexiones | Solicitud de revisión o reemplazo de la válvula |
| vs_accionamiento | check | Accionamiento manual con la palanca, con el recipiente presurizado: la válvula descarga y vuelve a asentar sin goteo | Solicitud de reemplazo de la válvula |
| vs_salida | check | Salida de descarga libre, sin obstrucción | Despejar la salida antes de operar |
| vs_precinto | check | Precinto o sello del ajuste intacto y placa legible **(propuesto, P-10)** | Solicitud de revisión: el ajuste pudo haberse alterado |

`advertencia` de `vs_accionamiento`: *"Descarga de vapor a alta temperatura directamente al ambiente: usar EPP y verificar que no haya personas frente a la salida antes de accionar."*

**Nota técnica (P-9):** la práctica habitual de los fabricantes de válvulas es accionar la palanca con el recipiente a no menos de ~75 % de la presión de ajuste. Con ajuste de 45 psi, eso es ~34 psi man.
- La **chaqueta** (regulada a 40 psi) cumple.
- El **generador** (60–80 psi) cumple.
- La **cámara** a 134 °C en vapor saturado está a ~30 psi man (~67 %), por debajo de ese criterio. Hay que definir a qué presión se acciona la válvula de cámara y dejarla escrita en el texto del ítem.

### 12.2 Grupo 2 — Puertas y empaques

**Todas las puertas** (`siempre`, `por_puerta`)

| id | Tipo | Texto | Si no cumple |
|---|---|---|---|
| pe_empaque | check | Empaque sin fisuras, roturas ni deformación | Solicitud de repuesto: empaque |
| pe_superficie | check | Superficie metálica de sello sin golpes ni rayones profundos | Solicitud de revisión |
| pe_apertura_cierre | check | Apertura y cierre completos sin trabas | Solicitud de revisión |

**Abatibles** (`puerta_abatible`, `por_puerta`)

| id | Tipo | Texto | Condición extra |
|---|---|---|---|
| pa_bisagras | check | Sin holgura en bisagras | — |
| pa_brazo | check | Estado del brazo motorizado | `puerta_motorizada` |
| pa_bloqueo | check | Prueba de bloqueo: bloquea y desbloquea correctamente | `puerta_bloqueo` |

**Guillotina** (`puerta_guillotina`, `por_puerta`)

| id | Tipo | Texto | Si no cumple |
|---|---|---|---|
| pg_empaque_servicio | check | Desmonte, lubricación (D-21) y reinstalación del empaque | — |
| pg_limpieza | check | Limpieza de la zona de la puerta donde sella el empaque | — |
| pg_rieles | check | Lubricación de rieles guía (D-21) | — |
| pg_cilindros | check | Sin fugas en cilindros neumáticos: el escape por la solenoide opuesta se escucha durante el movimiento y cesa al terminar el cierre y la apertura | Solicitud de revisión: cilindros neumáticos |
| pg_presion_empaque_sensor | medicion (unidad del equipo, absoluta) | Con el empaque bloqueado, el sensor de empaque alcanza `presion_empaque` | "Verificar suministro de aire comprimido y regulación de la unidad de mantenimiento" |
| pg_presion_empaque_manometro | comparacion_manometro | Manómetro de empaque contra sensor de empaque (P-8) | Solicitud de revisión: manómetro o sensor |
| pg_manometro_estable | check | Manómetro de la unidad de mantenimiento estable, sin vibración | Solicitud de repuesto: empaques ("la vibración indica fuga de aire por los empaques") |

### 12.3 Ítems derivados de D-19 (ubicación por confirmar)

| id | Tipo | Texto | Condición |
|---|---|---|---|
| mn_camara | comparacion_manometro, `por_puerta` | Manómetro de cámara contra transductor de cámara | `siempre` |
| mn_chaqueta | comparacion_manometro, `por_puerta` | Manómetro de chaqueta contra transductor de chaqueta | `has_full_jacket` |
| mn_generador | check | Manómetro del generador legible, sin daño, con aguja en reposo sin presión (no hay transductor contra el cual comparar: solo presostato) | `generador_interno` |

Ubicación propuesta: grupo 12 "Verificación de sensores e instrumentos". La comparación necesita el equipo presurizado, así que conviene hacerla en la misma prueba en que se accionan las válvulas de seguridad.

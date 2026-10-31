# Planeación: Soporte bilingüe español / inglés (i18n)

Software de Autoclave — Especifika S.A.S.
Versión: v3 (con resultados de F0 y decisiones del 8-oct) — 2026-10-08
Estado: **solo planeación, no se escribe código hasta aprobar este documento**
Normas relacionadas: IEC 62304 (Clase C), IEC 62366-1, IEC 60601-1-8
Documentos relacionados: `inventario_cadenas_i18n.md` y `.csv` (F0), `planeacion_opciones.md` v4, `planeacion_backend_parametros.md`, `planeacion_anuncios_voz.md`

Cambios respecto a v2:
- Integra el inventario F0 (1072 cadenas dentro del alcance, 562 fuera).
- Cierra I18N-05 e I18N-08 y aprueba R-06.
- Incorpora las decisiones D-11 a D-25 (respuesta a P-01 a P-11 y a los hallazgos I18N-12 a I18N-23).
- Reescribe F1, F2 y F6; añade §3.8 a §3.11 (alarmas, puertas, resultados de ciclo, formatos).

---

## 1. Requisito

Por normativa el software debe estar como mínimo en el idioma nativo (español) y en inglés.

- Idioma por defecto: **español**.
- Cambio a inglés desde Opciones.
- Estructura lista para agregar un tercer idioma sin tocar la lógica.

Esto reincorpora a V1.0 el selector de idioma, que estaba fuera del panel General del mockup (ver `planeacion_opciones.md`).

---

## 2. Decisiones

### 2.1 Cerradas

| # | Tema | Decisión |
|---|------|----------|
| D-01 | Superficies bilingües | UI QML, reportes PDF y ticket, correo de ciclos, mensajes de alarma y falla, bitácora (`audit_log`), textos almacenados en BD/JSON (nombres de programas y fases). Los logs de desarrollo se rigen por D-25 |
| D-02 | Alcance por archivo (precisado) | **Dentro:** todo lo que la UI QML importa y muestra, incluidos `service_ui`, `ui_pyside/views/nuevo_usuario/puente.py` y `ui_pyside/services/roles.py`. **Fuera:** vistas PySide de configuración y UI tkinter |
| D-03 | Ámbito del idioma | Una sola configuración **por equipo**. Las dos UI del equipo de dos puertas comparten idioma |
| D-04 | Permisos | Cualquier rol puede cambiarlo; requiere sesión iniciada (no se cambia antes del login) |
| D-05 | Reportes e históricos | Se muestran en el **idioma vigente** al ver o generar |
| D-06 | Alcance normativo | Solo el software (no manual, etiquetas ni documentación) |
| D-07 | Extensibilidad | Estructura lista para un tercer idioma |
| D-08 | Voz | Voz en inglés **variante US**, además de la española (ver D-16) |
| D-09 | Formato de fecha/hora (precisado) | Registros (tickets, PDF, panel de Información del equipo, auditoría): `dd/MM/yyyy HH:mm`, 24 h, igual en ambos idiomas. Se eliminan ISO y `ENE…DIC` en estos. Relojes de pantalla y rótulos de periodo del Historial conservan nombres de mes, resueltos desde el catálogo. Separador decimal sin cambio |
| D-10 | Bitácora | `audit_log` guarda código + parámetros; el texto se resuelve en la vista de Bitácora (alcance ampliado por D-25) |
| D-11 | UI entregada en V1.0 | **QML.** La UI tkinter se retira (migración total sin coexistencia). `AutoclaveUI.spec` empaqueta tkinter y no incluye `ui_qml/assets`: queda desactualizado; es tarea de empaquetado aparte, fuera de este plan |
| D-12 | Ticket de arranque y aviso `ui-ready` | Hoy solo los dispara tkinter. Debe encargarse **un solo proceso** (backend o launcher), no cada UI. Se resuelve en el plan de arranque/migración, no aquí. Este plan exige únicamente separar estado de rótulo (I18N-18) |
| D-13 | Catálogo | Paquete neutral `src/autoclave/i18n/` con `es.json` (movido desde `ui_qml/assets/textos/`) y `en.json`. Backend y UI cargan los mismos archivos. Se **conservan las claves actuales** (`seccion.clave`, 277 entradas) sin renombrar; las nuevas siguen la misma convención. El singleton reemplaza las ~17 copias de `tx()` y la `_tx` de `AccionesCiclos` |
| D-14 | Nombres de ciclo | Ciclos de fábrica: `nombre_clave` (catálogo). Ciclos creados en el hospital: texto libre único mostrado igual en ambos idiomas (I18N-05). El Historial resuelve el nombre de fábrica por `cycle_id`, no por la copia congelada en `ciclos.nombre_ciclo`. `instrumental_121` es de fábrica y falta su archivo en `cycles/factory/` |
| D-15 | Conteo de anuncios de voz | **32** (tablas e implementación coinciden). Se corrige el "33" en `planeacion_anuncios_voz.md` y en este plan |
| D-16 | Cierre de la voz | Plan propio (unir rama `worktree-anuncios-voz`, locuciones reales con Piper en es y en-US, textos con tildes). Este plan solo exige manifiesto por idioma y texto desde el catálogo (§3.7) |
| D-17 | Enums del panel de Información | `equipment_class` y `door_type` se muestran con etiquetas de catálogo por valor de enum |
| D-18 | Teclado alfanumérico | Distribución QWERTY con `ñ` igual en ambos idiomas; solo las etiquetas (p. ej. "espacio") salen del catálogo |
| D-19 | Claves sin uso | F1 incluye un script que detecta y lista las claves sin uso (incluidas las de uso dinámico). **No se borra ninguna sin autorización de Cristian** |
| D-20 | "Puerta 1" / "Puerta 2" | El identificador de la API no cambia en V1.0 (no se toca el interlock). **Nunca** se usa como texto visible: el texto sale del catálogo con parámetro de número ("Puerta {n}" / "Door {n}"). Alarmas con el nombre en el código (`ABRIENDO_MODO_SEGURO_Puerta N`) pasan a código fijo + parámetro |
| D-21 | Tickets | Entran los formateadores del backend (ciclo, resumen, arranque, conectividad). Queda fuera `ui_pyside/views/impresion_menu.py` |
| D-22 | Alarmas y puertas | Un texto por código (no por estado); motivos de denegación de puerta con código + parámetros; **unificar las familias de códigos** (`EMERGENCIA` ↔ `PARO_EMERGENCIA`, `FALLO_SUMINISTRO` ↔ `FALLO_SUMINISTRO_ELECTRICO`) ahora, porque no hay base instalada. Es cambio de seguridad (§3.8) |
| D-23 | Unidades | Lista cerrada de símbolos: `°C`, `kPa`, `%`, `min`, `s`, `°C/min`, `kPa/min`. `seg` y `sec` pasan a `s`. Verificar si el ticket imprime `C` por la codificación cp437 |
| D-24 | Cambio con ciclo en curso | Permitido (R-04); queda en `audit_log` |
| D-25 | Logs | `audit_log` y las líneas de alarma usan código + parámetros. Los **logs de desarrollo y soporte** (`logger.*`, ~300 mensajes) quedan en un solo idioma (español, como hoy) y se documentan como tales |
| R-01 | Cambio en caliente | Aprobada |
| R-02 | Catálogo único propio, sin Qt Linguist | Aprobada |
| R-03 | Solo códigos en backend/BD | Aprobada |
| R-04 | Cambio permitido con ciclo en curso | Aprobada (incluye la excepción a "solo en reposo" para `idioma`) |
| R-05 | Fallback a español + advertencia | Aprobada |
| R-06 | No habilitar inglés en campo hasta cerrar la voz | Aprobada. Aplica a la liberación; el desarrollo puede ir por fases |
| V-01 | Validación de traducciones | Esquema aprobado (§6). Revisor lingüístico: persona del departamento de ingeniería (nombre por registrar) |

### 2.2 Fundamento de las recomendaciones de diseño

**R-01 — Cambio en caliente.**
1. Con dos UI y un launcher, reiniciar implica reiniciar tres procesos; inaceptable con un ciclo en curso.
2. Las dos UI ya consultan el backend por polling. Basta que lean `idioma` y re-evalúen.
3. No toca lógica de control, solo presentación.

**R-02 — Catálogo propio.**
1. Reportes, correo y tickets se generan en el backend, sin `QApplication`. Con Linguist habría dos sistemas que sincronizar.
2. No introduce SOUP nuevo.
3. Ya existe un `es.json` en uso (277 entradas) que se reutiliza.

Contrapartida: se pierde la herramienta gráfica de Linguist. Se compensa con la prueba de paridad.

**R-03 — Solo códigos en backend.** Hace posible D-05: el texto se resuelve al mostrar.

**R-05 — Fallback.** Español + advertencia en log; nunca clave cruda ni vacío en una alarma. Hoy el comportamiento es el contrario (I18N-13).

---

## 3. Diseño

### 3.1 Almacenamiento y propagación

- Parámetro del equipo `idioma` en la tabla de parámetros del equipo (BD), valores `es` | `en`, defecto `es`. Valor de fábrica en el JSON de fábrica.
- Se aplica **sin reiniciar y sin condición de reposo** (R-04).
- Cada cambio genera registro en `audit_log` (usuario, fecha/hora, valor anterior y nuevo).
- Las dos UI, el backend y el subsistema de voz leen el mismo valor. Una UI que aún no refrescó muestra el idioma anterior hasta su siguiente polling.
- Login y pantalla de espera/arranque muestran el idioma **vigente del equipo**. Solo cambiarlo exige login.

### 3.2 Catálogo

```
src/autoclave/i18n/es.json   (movido desde ui_qml/assets/textos/es.json)
src/autoclave/i18n/en.json
```

Claves:
- Se conservan las existentes (`seccion.clave`; listas `fecha.meses` y `sensores[]`; tercer nivel en `opciones.secciones.*`).
- Las nuevas siguen la misma convención, por dominio: `alarma.<codigo>`, `puerta.<motivo>`, `resultado.<codigo>`, `voz.<id>`, `ticket.<campo>`, `ciclo.<cycle_id>.nombre`.

Reglas:
- Claves **estables e inmutables** una vez liberadas (renombrar = cambio controlado). Nunca se usa el texto en español como clave.
- Placeholders con nombre (`{numero}`), nunca posicionales. Los actuales ya cumplen.
- Sin plurales gramaticales: redactar de forma neutra.
- Unidades según D-23; no se traducen.
- Códigos de alarma/evento **no se traducen y siempre se muestran junto al texto** en alarmas, reportes y bitácora.

### 3.3 Módulo Python

Módulo único `i18n` dentro del paquete (nombre exacto a fijar en la especificación de F1):

- Carga ambos catálogos y valida que existan.
- `t(clave, **params) -> str` con idioma explícito o el vigente.
- Si falta la clave: devuelve el texto en español, o la clave si tampoco existe, y **registra advertencia** (R-05).
- Usado por: PDF, ticket, correo, bitácora, mensajes del backend y generación de los WAV.

### 3.4 QML

El mismo módulo se expone a QML como singleton (`I18n`) con la propiedad `lang`. Reemplaza las ~17 funciones `tx()` locales.

Patrón obligatorio para que los bindings se re-evalúen al cambiar el idioma:

```qml
text: I18n.t("opciones.idioma.etiqueta", I18n.lang)
```

Pasar `I18n.lang` como argumento hace que QML re-evalúe la expresión cuando cambia. Sin él, el texto queda congelado en el idioma de arranque. Se verifica en F3.

### 3.5 Textos almacenados en BD/JSON

| Tipo de texto | Tratamiento |
|---------------|-------------|
| Ciclos y fases de fábrica | `nombre_clave` en el perfil → catálogo (`ciclo.<cycle_id>.nombre`) |
| Ciclos creados en el hospital | Texto libre único (D-14) |
| Perfil de usuario con el mismo `cycle_id` que uno de fábrica | Conserva `nombre_clave`; si no la tiene, se muestra su `display_name` |
| Historial (`ciclos.nombre_ciclo`) | Fábrica: se resuelve por `cycle_id` + clave. Hospital: texto guardado |
| Roles (`admin`/`tecnico`/`ingeniero`), enums de equipo, sensores | Etiquetas de catálogo por valor (D-17) |
| Resultados y motivos de fallo | Código + parámetros (§3.10) |
| `audit_log.detalle` | JSON estructurado (código + parámetros), sin texto español libre |

### 3.6 Selector en Opciones

- Sección **Idioma** visible para **todos los roles**, en el cajón de navegación, junto a Fecha y hora.
- Dos opciones (Español / English), cada una rotulada en su **propio idioma**, para poder revertir si la UI queda en un idioma que el usuario no entiende.
- Aplica al instante. Sin botón "Guardar" ni reinicio.
- Es la única parte del panel General del mockup que entra en V1.0.

### 3.7 Voz bilingüe

Estado real (F0 §7): el subsistema existe **solo en la rama `worktree-anuncios-voz`** (17 commits, último `786c735`, sin unir a `dev`). Los WAV son un tono de 440 Hz provisional; no hay modelo Piper ni versión registrados; son **32** anuncios; el manifiesto trae los textos sin tildes; `load_manifest` siempre carga `es`.

Alcance de este plan (el cierre de la voz va en su plan propio, D-16):

1. **Texto fuente en el catálogo** (`voz.<id>`), en es y en en. Los WAV se generan **desde el catálogo**: lo que dice la voz coincide con lo que muestra la pantalla. Corrige además los textos sin tildes.
2. **WAV por idioma**: `audio/es/<id>.wav` y `audio/en/<id>.wav`. El manifiesto ya admite varios idiomas; `backend/context.py` debe pasar el `idioma` vigente a `load_manifest`.
3. **Cambio en caliente**: el anuncio que suena termina en su idioma; los siguientes de la cola salen en el nuevo.
4. **Prueba de paridad de audio**: cada clave de voz tiene WAV en ambos idiomas, no vacío.
5. **Tiempos**: las duraciones en inglés no deben alterar la cola de prioridad (P0-P5), los cooldowns ni la interrupción por prioridad.
6. **Modelo en inglés (US)**: registrar modelo y versión como SOUP igual que el español, y **verificar la licencia del modelo para uso comercial** antes de adoptarlo.
7. **Revisión auditiva** de los 32 anuncios por la persona definida en §6.
8. **Aviso `ui-ready`** (anuncio `sys_bienvenida`): hoy lo envía la ventana PySide/tkinter; ver D-12.

### 3.8 Alarmas

Estado actual (F0 §3): `Alarm(alarm_id, alarm_type, source_state, description, recoverable, blocks_operation)`; `description` es texto libre en español armado en el punto de disparo; no existe catálogo de alarmas; la UI muestra el texto, no el código.

Diseño:

1. **Catálogo de alarmas**: una entrada por código con nivel, texto es/en y parámetros esperados. Es la única fuente del texto.
2. `Alarm.description` deja de ser el texto: viaja el código y los parámetros; la UI resuelve el texto del catálogo y muestra **texto + código**.
3. **Un texto por código**, no por estado. El estado ya viaja en `source_state`. `PARO_EMERGENCIA` pasa de 5 textos a 1; **Cristian valida el texto único** antes de redactar `en.json`.
4. Códigos dinámicos (`ERROR_AI_{SENSOR}`, `SUMINISTRO_*`, `FALLO_<fase>`, `*_MODO_SEGURO`) se resuelven con código base + parámetro (sensor, fase, número de puerta).
5. Textos que hoy incrustan el código ("Alerta: CHAQUETA_FRIA en PREPARACION.") se eliminan; no se derivan textos del código por transformación de cadena.
6. Alarma y `motivo_fallo` con parámetros (`APERTURA_AUTOMATICA_DENEGADA`, `CONFIGURACION_INVALIDA`, `SENSOR_AUSENTE`): los parámetros viajan por separado.
7. **Familias de códigos unificadas**: el código de cierre de ciclo (`fase_ciclo` → `ciclos.resultado`) y el código de alarma son el mismo para el mismo evento. `ESTERILIZACION_TIMEOUT_F0`, que hoy existe solo dentro del texto, pasa a código real.
8. El log de alarma (`alarm_manager.py`) registra código + parámetros (D-25).

Es cambio de seguridad: solicitud de cambio, análisis de riesgo (ISO 14971) y regresión de todas las alarmas en F5.

### 3.9 Motivos de denegación de puerta

Estado actual (I18N-12): viajan solo como texto español, sin código, por `ser_puertas.py` → `server.py` (`HTTPException.detail`) → `door_command_service.py` → `comandos_puerta.py` → `PantallaPreciclo.qml`. Es el interlock de puerta (función de seguridad).

Diseño:
- Cada motivo tiene código y parámetros (p. ej. presión en kPa, temperatura en °C), con claves `puerta.<motivo>` en el catálogo.
- El backend responde con `RechazoApi` (que ya lleva `codigo`) en lugar de `HTTPException(detail=texto)`. Esto cubre también los ~25 `HTTPException` del backend que hoy solo llevan texto.
- El identificador de la puerta no cambia (D-20); el texto lleva `{numero}`.
- Se incluye en la prueba de alarmas de F5 con el mismo rigor que las alarmas.

### 3.10 Resultado y motivo de fallo del ciclo

Estado actual: `ciclos.resultado` guarda un código; `ciclos.motivo_fallo` guarda texto español con los valores medidos incrustados ("Temperatura baja: 133.8°C < 133.9°C"), y ese texto va al ticket y al PDF.

Diseño (a detallar en la especificación de F2):
- `motivo_fallo` guarda un **código**; los valores medidos se guardan por separado como parámetros (JSON).
- El ticket, el PDF y el Historial resuelven el texto del catálogo con esos parámetros.
- Los códigos de resultado se muestran **con texto traducido y código**, no el código crudo como único dato (hoy: `resultado_detalle`, "Causas de fallo", `Estado:` del ticket).
- Sin base instalada no se requiere migración (I18N-09): el esquema se cambia directamente.

### 3.11 Fechas, números, unidades y tickets

- Fechas según D-09; unidades según D-23.
- Los meses abreviados en español fijados en `BarraSuperior.qml` pasan al catálogo (`fecha.meses`).
- Los rótulos de periodo del Historial (`resumen_sistema.py`, días y meses en español) pasan al catálogo.
- Decimales: único formateador `formato_numerico.py` en la UI; los motivos de fallo ya no incrustan números en texto (§3.10).
- Ticket de arranque: la decisión "Sistema listo" / "FALLO EN ARRANQUE" **no puede comparar contra el texto mostrado** (`"FALLO"`, `"ERROR"`, `"Sin datos"`). Se separa estado (código) de rótulo (catálogo) antes de traducir (I18N-18).
- Tickets térmicos: verificar que los caracteres de ambos idiomas existen en cp437 (impresora). Textos del catálogo para tickets se redactan sin caracteres fuera de esa codificación.

---

## 4. Hallazgos

Estado: **Resuelto** = decisión tomada y sin trabajo restante; **Definido** = decisión tomada, queda implementarlo en la fase indicada.

| Código | Sev. | Estado | Hallazgo (resumen) | Resolución |
|--------|------|--------|--------------------|------------|
| I18N-01 | Alta | Definido (F2) | Alarmas y fallos se emiten y guardan como texto libre en español; el código ya viaja con la alarma | §3.8, §3.10 |
| I18N-02 | Alta | Definido (F6) | UI en inglés con voz de alarma en español | R-06 aprobada + voz en inglés (§3.7, D-16) |
| I18N-03 | Media | Resuelto | Clave faltante en un idioma | R-05 + prueba de paridad (F1) |
| I18N-04 | Baja | Resuelto | Vistas PySide y tkinter quedan fuera | D-02, D-11; las secciones no migradas muestran "Próximamente" (cadena en el catálogo) |
| I18N-05 | Media | Resuelto | Nombre de ciclo creado en el hospital | D-14 (texto libre único) |
| I18N-06 | Media | Resuelto | Formato de fecha/número | D-09 |
| I18N-07 | Media | Abierto (F3, F5) | Desbordamiento de texto en botones, tarjetas y barra inferior | Probar ambos idiomas en pantalla real de 12.1" táctil; elide controlado; nunca texto cortado en alarmas |
| I18N-08 | Media | Resuelto | Validación de traducciones | §6 aprobado; falta registrar el nombre del revisor |
| I18N-09 | Baja | Resuelto | Registros históricos con texto ya redactado | No aplica: software no instalado |
| I18N-10 | Baja | Resuelto | `idioma` se aplica sin reposo | R-04 |
| I18N-11 | Media | Abierto (F6) | Licencia y calidad del modelo Piper en inglés | §3.7 punto 6 |
| I18N-12 | Alta | Definido (F2) | Motivos de denegación de puerta solo como texto, sin código | §3.9 |
| I18N-13 | Media | Definido (F1) | ~17 `tx()` devuelven `""` si falta clave; `_tx` devuelve la clave cruda; sin advertencia | D-13, §3.3, R-05 |
| I18N-14 | Media | Definido (F2) | Misma alarma con textos distintos por estado; textos que incrustan el código; `PARO_EMERGENCIA` con 5 textos | §3.8 (texto único por código; Cristian lo valida) |
| I18N-15 | Media | Definido (F2) | Códigos de cierre y de alarma no coinciden para el mismo evento | D-22, §3.8 punto 7 |
| I18N-16 | Media | Definido (F2, F4) | Textos derivados del código por transformación de cadena; códigos crudos mostrados como texto | §3.8 punto 5, §3.10 |
| I18N-17 | Media | Definido (F3, F4) | Formatos de fecha inconsistentes (ISO, meses en español fijos) | D-09, §3.11 |
| I18N-18 | Media | Definido (F4) | Ticket de arranque compara contra texto mostrado; solo lo imprime tkinter | §3.11 (estado ≠ rótulo); D-12 para quién imprime |
| I18N-19 | Alta | Definido (plan de voz) | Voz en rama sin unir, tonos provisionales, 32 anuncios, sin modelo Piper | D-15, D-16 |
| I18N-20 | Baja | Definido (F2, F4) | Unidades inconsistentes (`sec`/`seg`, `C`/`°C`) | D-23 |
| I18N-21 | Baja | Definido (F3) | Enums crudos (`piso`, `advanced`) en el panel de Información | D-17 |
| I18N-22 | Baja | Definido (F2) | Nombres de ciclo de fábrica: texto libre copiado al iniciar; un perfil de usuario con el mismo `cycle_id` reemplaza al de fábrica | D-14, §3.5 |
| I18N-23 | Media | Resuelto | Límite de D-02 no era limpio | D-02 precisado por archivo |
| I18N-24 | Baja | Definido (F2) | `audit_log.detalle` guarda texto español libre | §3.5 |
| I18N-25 | Baja | Definido (F3) | Literales fijos en `Login.qml` (8), `NuevoUsuario.qml` (8, varios `PLACEHOLDER`) y "V: 1.0" duplicado | F3 |
| I18N-26 | Media | **Fuera de este plan** | El ticket del ciclo podría no imprimir filas periódicas en precalentamiento, prevacío, secado y descompresión, y mide el intervalo con `time.time()` en vez de `time.monotonic()` | Verificar en ejecución con el simulador y abrir plan propio (el registro de ciclo es evidencia de esterilización). Está relacionado con la regla de reloj monotónico (C-01) |

---

## 5. Plan por fases

Cada fase termina con confirmación visual de Cristian antes del commit (rama `dev`). Los planes van en `docs\mis_plans\`.

**F0 — Inventario (completada)**
Entregables: `inventario_cadenas_i18n.md` y `.csv`.

**F1 — Infraestructura**
- Paquete `src/autoclave/i18n/`; mover `es.json`; crear `en.json` (borrador generado por Claude, §6).
- Módulo `i18n` con fallback y advertencia (R-05).
- Singleton QML `I18n`; reemplazar las ~17 `tx()` y `AccionesCiclos._tx`.
- Pruebas automáticas: **paridad** de claves y placeholders entre es y en, cadenas no vacías; toda clave referenciada en el código existe en el catálogo, **incluidas las claves dinámicas**.
- Script de claves sin uso (D-19); solo lista, no borra.

**F2 — Backend y datos**
- Parámetro `idioma`, endpoint de lectura/escritura con autenticación (H-03), registro en `audit_log`.
- Catálogo de alarmas; `Alarm` con código + parámetros; unificación de familias de códigos (§3.8).
- Motivos de puerta con código + parámetros; `RechazoApi` en lugar de `HTTPException` con texto (§3.9).
- `motivo_fallo` como código + parámetros (§3.10); `audit_log.detalle` estructurado.
- Ciclos de fábrica con `nombre_clave`; archivo de fábrica de `instrumental_121`; etiquetas de roles y enums por catálogo.
- Unidades según D-23.
- Cambio de seguridad: solicitud de cambio, riesgo (ISO 14971) y regresión de alarmas y puertas.

**F3 — UI QML, pantalla por pantalla**
Orden: espera/arranque → login → ciclo → Opciones (incluye selector) → resto.
- Reemplazar cadenas fijas por `I18n.t(...)` con el patrón de §3.4.
- Literales de `Login.qml` y `NuevoUsuario.qml`; meses de `BarraSuperior.qml`; textos que Python entrega a QML (días/meses, roles, panel de Información, resultados).
- Etiquetas del teclado desde el catálogo (D-18).
- Prueba de cambio en caliente en **ambas UI** del equipo de dos puertas.

**F4 — Salidas del backend**
- PDF (ciclo, resumen, consolidado), correo, tickets (ciclo, resumen, arranque, conectividad).
- Formatos de fecha D-09; unidades D-23; separar estado de rótulo en el ticket de arranque.
- Idioma vigente al generar (D-05).
- Dependencia: D-12 (quién imprime el ticket de arranque) se resuelve en el plan de arranque.

**F5 — Verificación y documentación 62304**
- Revisión de traducciones por el responsable definido en §6.
- Recorrido visual completo en ambos idiomas (I18N-07).
- Prueba de alarmas y de motivos de puerta: cada código se dispara y se verifica en es y en en.
- Actualizar: requisitos de software (nuevo requisito de idioma), archivo de gestión de riesgos, plan de pruebas, matriz de trazabilidad requisito–riesgo–prueba.

**F6 — Voz**
- Lo ejecuta el plan propio de cierre de la voz (D-16). Este plan define solo los requisitos de §3.7.
- Es condición para habilitar el inglés en campo (R-06).

**Fuera de este plan (dependencias)**
- Plan de arranque/migración: ticket de arranque y aviso `ui-ready` (D-12).
- Empaquetado de la UI QML y actualización de `AutoclaveUI.spec` (D-11).
- Verificación y plan del ticket del ciclo (I18N-26).

---

## 6. Validación de traducciones (aprobado)

Un término mal traducido en una alarma o en un reporte de esterilización es un riesgo de seguridad y de trazabilidad, no solo de idioma.

1. **Borrador**: lo genera Claude (`en.json`), usando los términos de las propias normas (ISO 17665, IEC 60601-1-8) cuando existan.
2. **Revisión técnica**: Cristian valida cada término técnico (cámara, chaqueta, fase, descompresión, etc.).
3. **Revisión lingüística**: una persona del departamento de ingeniería con buen inglés revisa alarmas, mensajes de seguridad y los 32 anuncios de voz. Nombre por registrar.
4. **Registro**: archivo `revision_traducciones.md` con clave o grupo, revisor, fecha y resultado. Es evidencia para IEC 62304 / IEC 62366-1.
5. **Compuerta de liberación**: ninguna cadena de alarma o seguridad pasa a producción sin la revisión registrada.

---

## 7. Criterios de aceptación

1. Con `idioma = es` ninguna cadena visible o audible aparece en inglés, y con `en` ninguna aparece en español, salvo los nombres libres de ciclos creados en el hospital, los logs de desarrollo (D-25) y las vistas PySide fuera de alcance.
2. El cambio se refleja en ambas UI y en la voz sin reiniciar.
3. Toda alarma y todo motivo de denegación de puerta muestran texto + código en ambos idiomas.
4. La prueba de paridad (texto y audio) pasa en la integración continua.
5. Un reporte o ticket de un ciclo antiguo, generado tras cambiar el idioma, sale en el idioma vigente, incluido su motivo de fallo.
6. El cambio de idioma queda en `audit_log`.
7. Toda cadena de alarma o seguridad tiene revisión registrada (§6).
8. Una clave faltante genera advertencia en el log y nunca texto vacío ni clave cruda en una alarma.
9. El modo inglés no se habilita en equipos de campo hasta cerrar la voz (R-06).

---

## 8. Pendientes

1. Registrar el nombre del revisor lingüístico (§6).
2. Verificar la licencia del modelo Piper en inglés US (I18N-11), en el plan de voz.
3. Cristian valida el texto único de cada alarma en la especificación de F2, en especial `PARO_EMERGENCIA`.
4. Aprobar esta v3 para pasar a la instrucción de F1 y a la especificación detallada de F2 (catálogo de alarmas, esquema de `motivo_fallo`).

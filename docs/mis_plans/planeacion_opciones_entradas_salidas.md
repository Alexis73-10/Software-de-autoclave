# Planeación — Opciones › Entradas / Salidas (v1)

**Fecha:** 2026-10-20
**Estado:** borrador para revisión de Cristian. Las decisiones D-ES-xx están aprobadas; los supuestos y pendientes están marcados.
**Reemplaza:** `docs/superpowers/specs/2026-06-17-entradas-salidas-design.md` (obsoleto, ver ES-01).
**Complementa:** `planeacion_opciones.md` v4 (§2, §3.3, §5, §8, R-01 a R-03) y `planeacion_backend_autenticacion.md`.
**Mockup:** artefacto "Mockup Entradas/Salidas" (4 pantallas, 1080×1920). Las pantallas de este documento se numeran como en el mockup.

---

## 1. Alcance

La sección Entradas / Salidas de Opciones (QML puro, dentro del cajón de navegación) tiene cuatro vistas de diagnóstico y una pantalla de calibración:

| # | Vista | Función |
|---|---|---|
| 1 | Entradas digitales | Estado en vivo, solo lectura |
| 2 | Salidas digitales | Estado en vivo y modo de prueba (accionamiento manual) |
| 3 | Temperatura | Lectura en vivo de los sensores y acceso a calibración |
| 4 | Calibración de un sensor | Calibración por puntos o directa; se abre desde Temperatura o Presión |
| — | Presión | Mismo formato que Temperatura (kPa absolutos); no tiene mockup propio |

Fuera de alcance: reasignación de E/S (R-03, queda en Opciones avanzadas), calibración de presión atmosférica (Mantenimiento, `planeacion_opciones.md` §5), revisión de 2 frente a 3 puntos y de sensores polinomiales (OPC-04 sigue aceptado temporalmente: V1 usa el método actual de dos puntos).

---

## 2. Decisiones aprobadas (20-oct-2026)

| Id | Decisión |
|---|---|
| D-ES-01 | Una sola zona de contenido con selector de 4 segmentos (Entradas, Salidas, Temperatura, Presión), sin pantallas apiladas. La calibración es una vista de detalle con flecha de regreso al segmento de origen. |
| D-ES-02 | Se listan solo los canales habilitados en `io_enabled` del equipo. Requiere resolver los nombres canónicos (P-9, ES-02) antes de la lista final. |
| D-ES-03 | Cada canal muestra el nombre i18n y, en texto pequeño, su id físico (`DI 03`, `DO 07`, canal del sensor). |
| D-ES-04 | Entradas digitales: nivel crudo (ACTIVO/INACTIVO). Sin datos vigentes de la tarjeta se muestra "Sin datos", nunca 0. |
| D-ES-05 | Temperatura y presión en unidades base fijas (°C y kPa absolutos), independientes de la unidad de usuario. Se muestra el valor calibrado junto a las cuentas ADC crudas. |
| D-ES-06 | La calibración entra en esta planeación con el método actual de dos puntos, accesible con un botón "Calibrar" en la fila de cada sensor. Manda el backend: técnico e ingeniero (se corrige la v4 §2). |
| D-ES-07 | Modo prueba permitido en los estados que acepta el backend (PREPARACION, PREPARADO y FALLA). La UI refleja al backend, que es la autoridad. |
| D-ES-08 | El modo prueba se cierra (todas las salidas a OFF) al abandonar la sección, al cerrar sesión y tras 5 min de inactividad. |
| D-ES-09 | Las salidas de movimiento de puerta (`abrir_puerta_*`, `cerrar_puerta_*`) y `bomba_vacio` funcionan en modo "mantener pulsado" (momentáneo). El resto usa Activar/Apagar sostenido. |
| D-ES-10 | La reasignación de E/S (R-03) queda en Opciones avanzadas, fuera de esta sección. |
| D-ES-11 | La lectura de entradas y sensores se permite en cualquier estado, incluido ciclo en curso. Modo prueba y calibración se bloquean según rol y estado. Admin no tiene acceso a la sección. |
| D-ES-12 | Lectura en vivo cada 1 s, solo mientras la sección está visible. |
| D-ES-13 | En la calibración, la lectura del equipo de cada punto se puede **escribir a mano o capturar**. La bitácora guarda los cuatro valores y el origen (capturada o escrita) de cada lectura. |
| D-ES-14 | Barra inferior de la sección: la barra flotante existente (`BarraInferiorMenu`, igual que Menú Principal y OPCIONES): una sola barra blanca fuera de la tarjeta, con tres secciones y dos separadores. **Atrás** a la izquierda (sube un nivel; no cierra sesión), **Cerrar sesión** al centro (solo OPCIONES) e **Inicio** a la derecha con "V: 1.0". Corrige la versión anterior del mockup, que ponía "Salir" a la izquierda. |
| D-ES-15 | **En modo prueba se permiten todas las salidas.** El técnico o ingeniero debe saber operar el equipo, así que R-02 (presión atmosférica y puertas cerradas) no se aplica en modo prueba y las lecturas de sensores no condicionan el accionamiento. Esto reemplaza lo aprobado en la v4 (R-02) y se registra como aceptación de riesgo (ver ES-09 y §6.2). |
| D-ES-16 | **Única protección que se mantiene en las puertas: el seguro de atrapamiento.** Si la entrada de atrapamiento de la puerta está activa y el usuario pulsa cerrar, la orden que llega a la tarjeta es abrir esa puerta. |

---

## 3. Permisos

**T** = técnico, **I** = ingeniero. **L** = lectura, **E** = lectura y escritura, **-** = sin acceso. Admin: sin acceso a toda la sección.

| Elemento | T | I | Regla en backend (ya existe) |
|---|---|---|---|
| Entradas digitales | L | L | `GET /status` |
| Temperatura y presión (lectura) | L | L | `GET /status` |
| Salidas digitales (lectura) | L | L | `GET /status` |
| Modo prueba y accionamiento de salidas | E | E | Token T/I, estado distinto de CICLO e HIBERNACION, sesión dueña para encender. Rechazo con paro de emergencia activo. Sin R-02 (D-ES-15) |
| Calibración de sensores | E (solo fuera de CICLO) | E (también en CICLO, aplica de inmediato) | `PATCH /calibration/{tipo}/{sensor}` |

R-01 se cumple en el backend: con ciclo en curso el técnico no puede calibrar ni entrar a modo prueba; el ingeniero solo conserva la excepción de calibración.

La UI (`permisos_opciones.py`) debe replicar esta tabla. Hoy no coincide con la v4 (OPC-28).

---

## 4. Estructura y navegación

- **Entrada del cajón:** "Entradas / Salidas", visible para técnico e ingeniero (ya existe, muestra "Próximamente").
- **Archivos nuevos (propuesta de nombres):** `ui_qml/qml/Pantallas/OpcionesEntradasSalidas.qml`, `ui_qml/qml/Pantallas/OpcionesCalibracionSensor.qml`, `ui_qml/controllers/entradas_salidas_controller.py`. Sigue el patrón de `OpcionesParametrosCiclo.qml` y `OpcionesMantenimiento.qml`.
- **Retirada de PySide:** las vistas `ui_pyside/views/entrdas_salidas/*` (carpeta con errata) se retiran en la Fase 5 de la migración, no antes.
- **Encabezado:** flecha de regreso, botón hamburguesa (abre el cajón) y título "ENTRADAS / SALIDAS".
- **Selector:** cuatro segmentos con el segmento activo en azul claro y borde azul. El estado de cada vista se conserva al cambiar de segmento.
- **Barra inferior:** la barra flotante existente (`BarraInferiorMenu`, con `cerrarSesionVisible: true` como en `Opciones.qml`): una sola barra blanca fuera de la tarjeta, tres secciones y dos separadores. **Atrás** sube un nivel dentro de la sección (Calibración → Temperatura o Presión; desde un segmento sale de Entradas/Salidas a la pantalla previa de OPCIONES) y no cierra sesión. **Cerrar sesión** (centro) pide confirmación si el modo prueba está activo (se apagarán las salidas, §6.5). **Inicio** (derecha) conserva la sesión. Salir de la sección con cualquiera de los tres cierra el modo prueba (D-ES-08). Con la calibración en curso y valores sin aplicar, Atrás e Inicio piden confirmar el descarte, como el resto de OPCIONES (U-13).
- **Lectura en vivo:** una sola consulta a `GET /status` cada 1 s, compartida por los cuatro segmentos, con un temporizador que corre solo si la sección está visible. Si el backend o la tarjeta no responden, todos los valores pasan a "Sin datos" y el indicador de enlace cambia.

---

## 5. Pantallas (referencia: mockup)

### 5.1 Entradas digitales (pantalla 1)

- Título de sección "ENTRADAS DIGITALES", chips "N CANALES" y "SOLO LECTURA".
- Cuadrícula de 2 columnas, una tarjeta por entrada de `io_enabled.DI`: nombre, id físico y estado.
- Estado: ACTIVO (verde, punto lleno) o INACTIVO (gris). El texto siempre acompaña al color.
- Es el nivel crudo de la entrada. Entradas normalmente cerradas (paro de emergencia, atrapamiento) muestran ACTIVO en reposo; la UI no interpreta el significado.
- Línea de estado inferior: enlace con la tarjeta de E/S y periodo de actualización.

Canales del equipo ACV-2026-001 (13): aire comprimido, presión de agua, puerta 1 cerrada/abierta, puerta 2 cerrada/abierta, atrapamiento puerta 1/2, agua bomba, agua generador, paro de emergencia, agua cámara, suministro de vapor.

### 5.2 Salidas digitales (pantalla 2)

- Mismo formato de tarjetas, 2 columnas. Cada tarjeta: nombre, id físico, estado ON/OFF y un botón.
- Fuera de modo prueba: los botones se muestran deshabilitados y el encabezado ofrece "Habilitar modo prueba".
- En modo prueba: banner naranja "MODO PRUEBA ACTIVO" con la regla de cierre y botón rojo "Salir del modo prueba".
- Botones: Activar / Apagar (sostenido) o Mantener (momentáneo, ver §6.4).
- Una salida bloqueada por configuración (`salida_bloqueada`, p. ej. fuente de vapor que el equipo no usa) se muestra deshabilitada con su motivo. Se mantiene (confirmado). En ACV-2026-001 (generador interno) `Vapor generador` (DO 01) aparece deshabilitada: el mockup la dibuja habilitada.
- Con el seguro de atrapamiento activo, la tarjeta de `cerrar_puerta_N` indica que la orden se convierte en abrir (ver §6.7).

Canales del equipo ACV-2026-001 (18): vapor generador, vapor chaqueta, vapor cámara, descompresión rápida, descompresión chaqueta, vacío cámara, desbloqueo puerta 1/2, bloqueo puerta 1/2, aire atmosférico cámara, agua intercambiador, agua bomba, bomba de vacío, abrir puerta 1/2, cerrar puerta 1/2.

### 5.3 Temperatura y Presión (pantalla 3)

- Una tarjeta por sensor de `io_enabled.AI`: nombre, canal, valor calibrado grande (54 px, cifras tabulares), unidad, cuentas ADC, ganancia/offset vigentes y última calibración (fecha y usuario, o "De fábrica").
- Botón "Calibrar" por sensor.
- Sin lectura válida: valor "---" en naranja, aviso "Sin lectura válida: revise el cableado del sensor" y las cuentas ADC en naranja. El botón Calibrar permanece disponible solo si la lectura es válida (ver §7.3).
- Presión: igual, en kPa absolutos. Sensores de `io_enabled.AI`: `pres_camara`, `pres_chaqueta`, `pres_empaque_1`, `pres_empaque_2`.

### 5.4 Calibración de un sensor (pantalla 4)

Orden de los bloques:

1. Encabezado con ruta (`ENTRADAS / SALIDAS › TEMPERATURA`) y título "CALIBRAR · <sensor>".
2. Lectura en vivo: valor, canal y cuentas ADC.
3. Tabla ganancia/offset: **Actual**, **Último guardado**, **Por defecto**.
4. Selector de método: **Por puntos de referencia** | **Ganancia y offset directos**.
5. Punto bajo y punto alto (método por puntos): valor real de referencia (campo), lectura del equipo (campo editable) y botón **Capturar**.
6. Resultado: ganancia y offset calculados y nivel de plausibilidad.
7. Última calibración: fecha/hora, usuario y vencimiento.
8. Acciones: Restaurar último, Restaurar por defecto, **Aplicar calibración**.

Método directo: dos campos (ganancia y offset), con la misma validación de plausibilidad y la misma bitácora. Los coeficientes polinomiales siguen ignorando ganancia y offset (restricción de `planeacion_opciones.md` §8); si el canal tiene polinomio vigente, la UI avisa y exige confirmación (el backend ya lo hace).

**Supuesto a confirmar (S-ES-1):** "Actual" = valores vigentes; "Último guardado" = valores previos a la última modificación (para deshacer); "Por defecto" = calibración neutra (ganancia 1.000, offset 0.0).

---

## 6. Modo prueba de salidas

### 6.1 Entrada

1. El usuario pulsa "Habilitar modo prueba".
2. Diálogo de advertencia (el mockup no lo dibuja): título "MODO PRUEBA — PRECAUCIÓN"; texto: apaga todas las salidas activas, permite control manual de todas las salidas **sin verificar presión de cámara ni estado de las puertas**, solo el seguro de atrapamiento sigue activo, y debe usarse únicamente con conocimiento del sistema; botones Cancelar y Continuar.
3. Al continuar: `POST /io/test/enter` (el backend apaga todas las salidas y pausa la máquina de estados). Si responde 409, se muestra el motivo del backend y no se entra.
4. Se muestra el banner y se habilitan los botones.

### 6.2 Reglas (todas verificadas en el backend)

- Estados: PREPARACION, PREPARADO y FALLA. Rechazado en CICLO, HIBERNACION, EMERGENCIA.
- Configuración inválida o sin datos vigentes de la tarjeta: rechazado.
- Sesión dueña: solo la sesión que entró puede encender; apagar queda abierto a cualquier sesión de prueba.
- **Se retira R-02 de la ruta de prueba (D-ES-15):** ya no se exige presión de cámara en la banda atmosférica ni puertas cerradas, ni se consulta ningún sensor para permitir una salida. Se permiten todas las salidas, incluidas las de puertas, vapor y vacío, en cualquier combinación.
- **Se mantiene** el seguro de atrapamiento (§6.7).
- **Se mantienen** (confirmado el 20-oct): el rechazo con paro de emergencia activo (apagar siempre se permite) y el bloqueo de salidas de una fuente de vapor que el equipo no tiene, `fuente_vapor_no_instalada` (con generador interno, DO1/DO2 deshabilitadas).
- Apagar siempre se permite dentro del modo prueba.
- Compensación del riesgo retirado: el diálogo de entrada lo explicita, solo técnico e ingeniero acceden, y la bitácora registra cada entrada, salida y accionamiento. Debe quedar anotado en el fichero de gestión de riesgos como riesgo aceptado (ES-09).

### 6.3 Actualización de estado

El estado de cada tarjeta lo manda el poll de 1 s. La UI puede mostrar el cambio de forma optimista al pulsar, pero se corrige con el estado real; si el backend rechaza la orden, se revierte y se muestra el motivo.

### 6.4 Salidas momentáneas (mantener pulsado)

Aplica a `abrir_puerta_1/2`, `cerrar_puerta_1/2` y `bomba_vacio`.

- La salida está ON solo mientras el dedo está sobre el botón. Al soltar, salir de la pantalla o perder el toque, la UI envía OFF.
- **Propuesta de Claude (P-ES-3, confirmar):** como el OFF depende de la UI, el backend debe apagar por su cuenta una salida momentánea si no recibe renovación. La UI reenvía `value: true` con `momentanea: true` cada 500 ms mientras se mantiene pulsado; el backend apaga la salida si pasan 1.5 s sin renovación. Esto cubre un bloqueo de la UI o un corte del enlace con el motor encendido.

### 6.4 bis Protección de atrapamiento (§6.7)

Ver §6.7: aplica también a las salidas momentáneas de puerta.

### 6.5 Cierre del modo prueba (D-ES-08)

Cualquiera de estas causas ejecuta `POST /io/test/exit` (todas las salidas a OFF, se reanuda la máquina de estados):

| Causa | Quién lo dispara |
|---|---|
| Botón "Salir del modo prueba" | UI |
| Cambio de segmento, regreso, Inicio o abandono de la sección | UI |
| Cierre de sesión | UI y backend (ver ES-08) |
| 5 min sin actividad del usuario en la sección | UI |
| Pérdida de enlace de la UI con el backend | Backend (**propuesta P-ES-4**: sin ninguna petición de la sesión dueña durante 90 s, el backend sale del modo prueba; la UI envía un keepalive cada 30 s mientras la sección está visible) |

La confirmación de Cerrar sesión (barra inferior) con modo prueba activo advierte que las salidas se apagarán.

### 6.6 Bitácora

Ya existen `modo_prueba_entra` y `salida_prueba` (con salida y valor). Se añaden `modo_prueba_sale` (con la causa de la tabla anterior), el registro de la renovación solo en el primer y último pulso de una salida momentánea (no un registro por renovación) y `atrapamiento_orden_invertida` (§6.7).

### 6.7 Seguro de atrapamiento en modo prueba (D-ES-16)

- **Regla:** si la entrada de atrapamiento de la puerta N está activa y llega la orden de encender `cerrar_puerta_N`, el backend no la envía a la tarjeta: apaga `cerrar_puerta_N` y enciende `abrir_puerta_N`.
- **Polaridad:** el sensor es un contacto normalmente cerrado: el valor crudo `0` = puerta atrapada, `1` = normal (`planeacion`/spec `2026-07-15-fix-polaridad-atrapamiento`). La regla usa la interpretación semántica, no el bit crudo (ES-11).
- **Dónde:** en el backend, en la ruta de modo prueba, antes de `setdo.set_output`. La UI no decide nada; solo refleja el estado.
- **Alcance:** puertas con sensor de atrapamiento configurado (puertas avanzadas). En puertas sin sensor la orden pasa sin cambio.
- **Por qué hace falta implementarlo aquí:** con el modo prueba activo la máquina de estados está pausada y la lógica de atrapamiento de `advanced_door.py` no corre (ES-12; verificar que el servicio de puertas también queda detenido).
- **Mientras se mantiene pulsado cerrar con el atrapamiento activo:** la salida de apertura se mantiene. Si la señal se libera mientras el dedo sigue pulsado, el cierre **no** se reanuda: hay que soltar y volver a pulsar (confirmado).
- Cada inversión se registra en bitácora (`atrapamiento_orden_invertida`, puerta y usuario) una sola vez por pulsación.

---

## 7. Calibración

### 7.1 Flujo

1. El usuario pulsa "Calibrar" en la fila de un sensor (solo con lectura válida).
2. La pantalla carga ganancia/offset vigentes (`GET /calibration/{tipo}/{sensor}`) y la lectura en vivo.
3. Método por puntos: para cada punto el usuario escribe el valor real de referencia y la lectura del equipo (escribiéndola o con Capturar, que copia la lectura en vivo al campo; el campo sigue editable).
4. La UI calcula y muestra el resultado antes de aplicar (misma fórmula del backend: `fit_two_point` sobre la salida de fábrica).
5. "Aplicar calibración" envía `PATCH /calibration/{tipo}/{sensor}`.
6. Si el backend responde 409 `CALIBRACION_REQUIERE_CONFIRMACION`, la UI muestra el motivo y un diálogo de confirmación; al aceptar reenvía con `confirmar_fuera_de_rango: true`. Si responde 422 `CALIBRACION_IMPLAUSIBLE`, muestra el motivo y no permite continuar.
7. La calibración se aplica sin reiniciar (`reload_calibration`).

### 7.2 Reglas

- Técnico solo fuera de CICLO; ingeniero también en CICLO (aplica de inmediato). El backend ya lo exige; la UI oculta o deshabilita la acción según rol y estado.
- La calibración de usuario (`ganancia × valor + offset`) se aplica sobre la salida de la calibración de fábrica, no sobre el ADC crudo.
- Los sensores de presión absoluta permanecen en absoluta.
- Sin base de datos o sin auditoría no hay calibración (503): el backend ya lo hace y restaura el archivo previo.

### 7.3 Lectura escrita a mano (D-ES-13)

- Los cuatro valores de la calibración por puntos (real bajo, lectura baja, real alto, lectura alta) viajan en el cuerpo y quedan en `audit_log.detalle.puntos` (ya existe).
- **Nuevo:** el cuerpo incluye `origen_lectura: {bajo: "capturada" | "escrita", alto: "capturada" | "escrita"}`. El backend lo valida (solo esos dos valores, obligatorio) y lo guarda en `detalle`. Una lectura capturada que el usuario edita después se registra como "escrita".
- Una lectura escrita no se compara contra la lectura en vivo (el usuario puede llevar la referencia de otro instrumento), pero el resultado pasa por la misma plausibilidad y desviación acumulada del backend.
- Sin lectura válida del sensor, la calibración por puntos con lectura escrita sigue permitida: la lectura del equipo no tiene que ser la del sensor averiado. El botón Capturar queda deshabilitado, el aviso de cableado se mantiene y el resultado conserva la confirmación de plausibilidad. **(Supuesto S-ES-2, confirmar.)**

### 7.4 Restaurar

- **Restaurar por defecto:** calibración neutra (ganancia 1.0, offset 0.0).
- **Restaurar último:** valores previos a la última modificación (S-ES-1).
- Ambas son escrituras de calibración: mismo rol, mismo estado permitido, confirmación explícita (R-04 por analogía) y registro en bitácora con `detalle.accion = "restaurar_ultimo" | "restaurar_defecto"`.
- No existe endpoint para esto (ES-06).

### 7.5 Información añadida

Usuario y fecha de la última calibración (ya devuelve `last_change`) y **fecha de vencimiento**. El intervalo de vencimiento no está definido (P-ES-5); mientras no exista, la pantalla muestra "—".

---

## 8. Cambios de backend

| Id | Cambio | Tipo |
|---|---|---|
| B-ES-1 | Exponer cuentas ADC por sensor (`GET /status` o `GET /calibration/{tipo}/{sensor}`). Hoy no se exponen. | Nuevo |
| B-ES-2 | Lector de `io_enabled` y módulo de nombres canónicos (`io_names`): lista de DI, DO y AI del equipo con id físico, clave i18n y tipo (sostenida o momentánea). | Nuevo (P-9, OPC-15) |
| B-ES-3 | `origen_lectura` en el cuerpo del PATCH de calibración, validado y guardado en `detalle`. | Cambio |
| B-ES-4 | `POST /calibration/{tipo}/{sensor}/restaurar` con `destino: "ultimo" | "defecto"`, mismas reglas y auditoría. | Nuevo |
| B-ES-5 | Salidas momentáneas: campo `momentanea` en `PATCH /io/test/output/{name}`, caducidad de 1.5 s sin renovación, lista de salidas momentáneas del lado del backend. | Cambio (P-ES-3) |
| B-ES-6 | Keepalive del modo prueba y salida automática a los 90 s sin actividad de la sesión dueña. | Nuevo (P-ES-4) |
| B-ES-7 | Cierre de sesión o invalidación del token de la sesión dueña con modo prueba activo: apagar salidas y salir del modo prueba. Verificar el comportamiento actual (ES-08). | Verificar / cambio |
| B-ES-8 | Auditar `modo_prueba_sale` con la causa. | Cambio |
| B-ES-9 | Retirar `_motivo_r02` de la ruta de `PATCH /io/test/output/{name}` (D-ES-15) y añadir la inversión de atrapamiento (§6.7) en esa ruta. Conservar `_motivo_r02` solo si otro código lo usa. | Cambio |
| B-ES-10 | Clave de configuración `presion_admosferica` → `presion_atmosferica` (errata ya decidida en la v4); `_motivo_r02` la lee. | Cambio (coordinar con el backend de parámetros) |

---

## 9. i18n

- Cada canal tiene clave estable, no derivada del nombre en español: `io.di.<nombre_canonico>`, `io.do.<nombre_canonico>`, `io.ai.<nombre_canonico>`.
- Textos de interfaz bajo `io.ui.*`: segmentos, chips, banner, diálogos, avisos, etiquetas de calibración.
- El nombre en español de los mockups es el valor por defecto. El nombre en inglés lo completa el trabajo de i18n (`planeacion_i18n.md`).
- Se retira la conversión snake_case → Title Case del diseño anterior.

---

## 10. Hallazgos

| Id | Severidad | Hallazgo | Resolución |
|---|---|---|---|
| **ES-01** | Media | La spec del 17-jun está obsoleta: 6 sensores de temperatura (incluye `temp_chaqueta`, retirado; hoy son 4), presión en bar, nombres en snake_case, endpoint `POST /io/test/reset_all` que ya no existe, modo prueba sin token ni reglas. | Este documento la reemplaza. Marcarla como reemplazada. |
| **ES-02** | Alta | `EstadoAutoclave.map_*` no coincide con `io_enabled` ni en cantidad ni en nombres. DI: 14 contra 13 (`suministro_electrico` no está habilitada). DO: 24 contra 18 (`vapor_caldera`, `descompresion_lenta`, `aire_comprimido_*`, `agua_chaqueta`, `buzer_alarma` no están habilitadas). AI: `temp_ref` contra `temp_referencia`, `temp_drenaje_camara` ya no existe, `temp_2_camara` no está habilitada en este equipo. `aire_admosferico_camara` (map_do) contra `aire_atmosferico_camara` (YAML). | B-ES-2. Una sola fuente de nombres (P-9, OPC-15). |
| **ES-03** | Media | Permisos de calibración contradictorios: la v4 §2 dice solo ingeniero; el backend (tanda 2026-10-14 §1.1, C-5) permite técnico e ingeniero. | D-ES-06: manda el backend. Corregir v4 §2 y §3.3. |
| **ES-04** | Media | No se exponen cuentas ADC en ninguna API; la pantalla de calibración las necesita (v4 §8, punto 1). | B-ES-1. |
| **ES-05** | Media | La calibración no registra si la lectura del equipo fue capturada o escrita, y ahora puede ser escrita (D-ES-13). | B-ES-3. |
| **ES-06** | Media | No existen operaciones "restaurar último" ni "restaurar por defecto" (v4 §8, punto 3). | B-ES-4. |
| **ES-07** | Alta | Las salidas de movimiento de puerta y la bomba de vacío en ON sostenido pueden quedar energizadas si la UI falla antes de enviar OFF. El interlock de puerta es solo por software y no tiene redundancia mecánica (R-02, OPC-02). | D-ES-09, B-ES-5 y B-ES-6. Pendiente confirmar si las puertas automáticas tienen finales de carrera por hardware (P-ES-1). |
| **ES-08** | Media | No está verificado qué pasa con el modo prueba si la sesión dueña cierra sesión o su token se invalida: `_token_modo_prueba` queda guardado. | B-ES-7. Verificarlo con una prueba antes de implementar. |
| **ES-09** | Alta | `_motivo_r02` se evaluaba en cada orden de encendido y exigía todas las puertas cerradas, por lo que tras `abrir_puerta_N` la puerta no se podía volver a cerrar. Cristian decide retirar R-02 de la ruta de prueba (D-ES-15). Riesgo residual: con la regla retirada se puede abrir una puerta con la cámara bajo presión, abrir vapor a la cámara con puertas abiertas o accionar vacío y vapor a la vez. OPC-02 y la v4 R-02 pasan de "bloqueo" a "operador competente + advertencia + bitácora". | Aceptado por Cristian. Registrar como riesgo aceptado en el fichero de gestión de riesgos (ISO 14971, IEC 62304 Clase C) y actualizar R-02 y OPC-02 en la v4. B-ES-9. |
| **ES-11** | Media | Atrapamiento y paro de emergencia son contactos NC: el valor crudo `0` es la condición activa. La tarjeta de Entradas digitales muestra el nivel crudo (D-ES-04), así que "INACTIVO" en atrapamiento significa puerta atrapada. | Mostrarlo así en V1 (decisión D-ES-04); evaluar una etiqueta de significado para estas dos entradas. |
| **ES-12** | Alta | En modo prueba la máquina de estados está pausada: la protección de atrapamiento de `advanced_door.py` (transición a ATRAPADA y apertura) no corre. | §6.7: implementar la inversión en la ruta de prueba. Verificar si el servicio de puertas queda detenido en modo prueba. |
| **ES-10** | Baja | `server.py` lee `presion_admosferica` (errata). La v4 ya renombra la clave. | B-ES-10. |

---

## 11. Pruebas

**Backend**
- `origen_lectura`: ausente, valor inválido y válido; queda en `audit_log.detalle`.
- Restaurar por defecto y último: roles, estados, auditoría y falla de auditoría (se revierte el archivo).
- Salidas momentáneas: caducidad a 1.5 s sin renovación; renovación mantiene ON; OFF explícito apaga.
- Keepalive: sin actividad 90 s sale del modo prueba y apaga todo; con keepalive no sale.
- Cierre de sesión con modo prueba activo: salidas OFF y modo prueba inactivo.
- Cuentas ADC presentes y coherentes con el valor calibrado.
- Modo prueba sin R-02: con cámara presurizada y puertas abiertas se aceptan las órdenes de encendido de cualquier salida.
- Atrapamiento: con la entrada activa, `cerrar_puerta_N` enciende `abrir_puerta_N` y deja `cerrar_puerta_N` apagada; con la entrada normal, `cerrar_puerta_N` pasa sin cambio; puerta sin sensor, sin cambio; polaridad NC (crudo 0 = atrapada); un registro de bitácora por pulsación.

**UI (QML)**
- Lista de canales = `io_enabled` del equipo (13 DI, 18 DO, 3 AI de temperatura y 4 de presión en ACV-2026-001).
- "Sin datos" cuando falla el backend o la tarjeta; nunca 0.
- Visibilidad por rol y estado (admin sin acceso; técnico sin modo prueba ni calibración en CICLO).
- Cierre automático del modo prueba por cada causa de §6.5.
- Mantener pulsado: ON al pulsar, OFF al soltar, al perder el toque y al salir de la pantalla.
- Calibración: lectura editable y capturada, diálogo de confirmación fuera de rango, rechazo por plausibilidad, restaurar con confirmación.
- Los cuatro segmentos conservan su estado al cambiar entre ellos.

**Banco (equipo de pruebas, tras instalar)**
- Cada DI cambia de estado al accionar físicamente la entrada.
- Cada DO accionado en prueba energiza la carga correspondiente (verificar con la hoja de pruebas de banco).
- Calibración de un sensor contra un patrón de referencia, con registro en bitácora.

---

## 12. Fases de implementación

| Fase | Contenido | Depende de |
|---|---|---|
| **ES-F0** | B-ES-2 (nombres canónicos y lector de `io_enabled`) y B-ES-10. | P-9 |
| **ES-F1** | Lectura: segmentos Entradas, Temperatura y Presión; B-ES-1 (ADC). | ES-F0 |
| **ES-F2** | Salidas y modo prueba: pantalla, diálogo de entrada, cierres automáticos, inversión de atrapamiento (§6.7), B-ES-5, B-ES-6, B-ES-7, B-ES-8, B-ES-9. | ES-F0, P-ES-1, P-ES-3, P-ES-4 |
| **ES-F3** | Calibración: pantalla 4, B-ES-3, B-ES-4. | ES-F1, P-ES-5 |
| **ES-F4** | Cableado en `permisos_opciones.py`, retiro de "Próximamente" de la entrada y actualización de documentos (§14). | ES-F1 a ES-F3 |

Orden sugerido para el equipo de pruebas: ES-F0 y ES-F1 primero (diagnóstico de banco), después ES-F3 y por último ES-F2 (el equipo de pruebas tiene puertas manuales y no usa las salidas de movimiento de puerta).

---

## 13. Pendientes

| Id | Pendiente |
|---|---|
| **P-ES-1** | ¿Las puertas automáticas tienen finales de carrera por hardware? Sin ellos, un motor en ON sostenido no tiene freno. Queda sin responder. |
| **P-ES-2** | Cerrado por D-ES-15: en modo prueba se permiten todas las salidas. |
| **P-ES-3** | Confirmar caducidad de salidas momentáneas (renovación 500 ms, caducidad 1.5 s). |
| **P-ES-4** | Confirmar keepalive de 30 s y salida automática del backend a los 90 s. |
| **P-ES-5** | Intervalo de vencimiento de la calibración (¿12 meses?). Mientras no exista, la pantalla muestra "—". |
| **P-ES-6** | Cerrado (20-oct): el paro de emergencia activo sigue rechazando el encendido; apagar siempre se permite. |
| **P-ES-7** | Cerrado (20-oct): se mantiene el bloqueo `fuente_vapor_no_instalada`. |
| **P-ES-8** | Cerrado (20-oct): con el atrapamiento liberado y el dedo aún pulsado el cierre no se reanuda; hay que soltar y volver a pulsar. |
| **S-ES-1** | Confirmar el significado de "Actual / Último guardado / Por defecto" (§5.4). |
| **S-ES-2** | Confirmar que la calibración por puntos con lectura escrita se permite aunque el sensor no tenga lectura válida (§7.3). |

---

## 14. Cambios a otros documentos

- `planeacion_opciones.md` v4 §2: calibración de sensores técnico y ingeniero (técnico solo fuera de ciclo). §3.3: reemplazar el texto por la referencia a este documento. §8: marcar como incorporada al flujo de este documento (lo definido aquí: método de dos puntos, lectura escrita, restaurar). OPC-04 sigue abierto.
- `planeacion_opciones.md` §4 R-02: aclarar que no aplica en modo prueba de salidas (D-ES-15; solo se mantiene el seguro de atrapamiento). §7 OPC-02: actualizar la resolución (la mitigación pasa a token, bind local, operador competente, advertencia y bitácora). §7: añadir ES-02, ES-07, ES-09 y ES-12 a los hallazgos de Opciones.
- Fichero de gestión de riesgos: nueva entrada de riesgo aceptado por el accionamiento manual sin verificación de presión ni puertas.
- `docs/superpowers/specs/2026-06-17-entradas-salidas-design.md`: marcar como "Reemplazado por `planeacion_opciones_entradas_salidas.md`".
- `permisos_opciones.py`: matriz de §3 (OPC-28).

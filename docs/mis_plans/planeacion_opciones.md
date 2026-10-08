# Planeación — Opciones (configuración)

**Proyecto:** Software de Autoclave (Especifika S.A.S.)
**Alcance:** estructura, permisos y reglas de la configuración posterior al login (QML puro)
**Estado:** borrador v4 — la calibración de sensores queda **por definir** (sección 8); parámetros del sistema alineados con el código existente (informe de revisión del 7-oct); backend especificado en `planeacion_backend_autenticacion.md` y `planeacion_backend_parametros.md`
**Ubicación sugerida en el repo:** `docs\mis_plans\planeacion_opciones.md`
**Documentos relacionados:** `planeacion_menu_principal.md`, `planeacion_idiomas.md` (pendiente de redactar)

---

## 1. Decisiones base

1. **Roles de acceso:** admin, técnico e ingeniero. "Biomédico" no es un rol: es un usuario con rol técnico.
2. **Navegación:** las entradas de menú van en un cajón lateral que se abre con botón hamburguesa. Barra inferior: **Salir** (cierra sesión, con confirmación si hay cambios sin guardar) e **Inicio** (conserva la sesión).
3. **Formato visual:** el del mockup-01. El contenido sale de lo que existe en PySide; el mockup solo es referencia de formato.
4. **Secciones no migradas** muestran "Próximamente". QML no abre vistas PySide de configuración.
5. **Panel General del mockup** (brillo, espera de pantalla, tema) queda fuera de V1.0. Solo se incluye el selector de idioma (español por defecto, inglés seleccionable, requisito normativo).
6. **Nomenclatura:** todo texto visible se resuelve por clave i18n estable. El texto visible nunca es identificador.

---

## 2. Matriz de permisos

**A** = admin, **T** = técnico, **I** = ingeniero. **E** = lectura y escritura, **L** = solo lectura, **-** = sin acceso.

| Sección / elemento | A | T | I |
|---|---|---|---|
| Parámetros del ciclo: sensores de temperatura (por programa) | - | E | E |
| Parámetros del ciclo: entradas mostradas | - | E | E |
| Parámetros del ciclo: fases (incluye "Global") | - | L | E |
| Parámetros del ciclo: programas (habilitar/deshabilitar, duplicar, borrar personalizados) | - | E | E |
| Parámetros del sistema | L | E | E |
| Entradas y salidas: entradas digitales | - | L | L |
| Entradas y salidas: salidas digitales y modo de prueba | - | E | E |
| Entradas y salidas: lectura de sensores de temperatura y presión | - | L | L |
| Entradas y salidas: **calibración de sensores** (por definir) | - | - | E |
| Mantenimiento (contadores, calibración atmosférica, impresora) | - | E | E |
| Opciones avanzadas (configuración de máquina, funcionalidad de E/S, respaldo/restauración) | - | - | E |
| Usuarios (incluye operadores) | E | - | - |
| Conectividad (wifi, direcciones IP, correo) | E | - | - |
| Fecha y hora | E | E | E |
| Bitácora de auditoría | L | L | L |
| Información del sistema | L | L | L |

---

## 3. Contenido por sección

### 3.1 Parámetros del ciclo
- **Sensores de temperatura (por programa, no por fase):** lista los sensores realmente conectados. Cada uno se configura como Principal, Referencia o No en uso. Restricciones: exactamente 1 Principal, de 0 a 2 Referencias.
- **Entradas mostradas (por programa; cambian al cambiar de ciclo):** una sola selección de 1 a 3 entradas analógicas. Las mismas se muestran en preciclo y ciclo y se grafican. Se eligen entre las habilitadas en `io_enabled.AI` del equipo, no entre las 10 del mapa de ejecución. Los nombres canónicos son los del mapa de ejecución (`temp_ref`, `temp_drenaje_cam`, `temp_2_camara`) y el YAML se alinea. Hoy están fijas en código (temperatura de cámara, temperatura de referencia, presión de cámara). La gráfica histórica se guarda como (ciclo, tiempo, entrada, valor) con todas las habilitadas, y cada ciclo guarda la selección vigente al ejecutarse.
- **Programas:** habilitar/deshabilitar, duplicar, borrar personalizados. Los programas de fábrica (1–10) no se pueden borrar. Los números nunca se reutilizan.
- **Fases del ciclo:** una pantalla por fase, incluye la fase "Global". Flujo: programa → fase → parámetros de la fase → ventana de ajuste del parámetro.
- **Ventana de ajuste:** valor actual, valor por defecto (la tarjeta "Por defecto" es el botón de restaurar), mínimo, máximo, usuario y fecha/hora de la última modificación, campo de nuevo valor (el teclado aparece solo al tocarlo). Los parámetros modificados respecto a fábrica se marcan con asterisco solo en esta pantalla.

### 3.2 Parámetros del sistema

Estado actual: existen en `src/autoclave/config/global_params.json` y solo se leen al arrancar (sin escritura, sin auditoría, mín/máx sin aplicar). Esta sección define el objetivo. Las claves de código conservan el español existente y se corrigen las erratas, porque el software no está instalado en ningún equipo y no hay compatibilidad que romper.

| Nombre visible | Clave en código | Unidad | Defecto | Rango | Notas |
|---|---|---|---|---|---|
| Tiempo límite de chaqueta | `timeout_chaqueta` (nueva; distinta de `timeout_precalentamiento`, que es por ciclo) | min | 60 | 10–180 (propuesta, P-13) | Tiempo máximo para que la chaqueta se considere caliente (`pres_chaqueta` alcanza `presion_chaqueta`), por ejemplo al encender el equipo. Al vencer muestra una alerta que impide iniciar ciclo |
| Tasa de impresión (general) | `intervalo_impresion` | s | 60 | 10–3600 | 0 no permitido |
| Tasa de impresión (esterilización) | `intervalo_impresion_esterilizacion` (corrige la errata `imprecion`) | s | 30 | 10–3600 | 0 no permitido |
| Suspensión | `tiempo_standby` | min | 10 | 0–60 | 0 = desactivada (ver sección 6) |
| Contador de ciclos para servicio | `ciclos_servicio` (nueva) | ciclos | 1000 | 10–1000 | Cuenta ciclos iniciados desde el último reinicio, incluye cancelados y fallidos. Aviso no bloqueante al llegar al límite |
| Contador de tiempo para servicio | `dias_servicio` (nueva) | días | 365 | 10–365 | Días calendario desde la fecha de mantenimiento. Aviso no bloqueante al vencer |
| Banda de presión atmosférica (±) | `rango_presion_atm` | kPa | 5 | 1–10 | decide cuándo se considera la cámara a presión atmosférica para abrir puerta |
| Tiempo límite de puerta | `timeout_puerta` | s | 60 | 5–600 | 0 no permitido; usa `time.monotonic()` |
| Temperatura segura de apertura de puerta | `temp_max_apertura` | °C | 80 | 40–120 | techo de 120 °C intencional para pruebas |
| Temperatura segura de drenaje | `temp_segura_drenaje` | °C | 70 | 40–90 | |
| Presión de empaque | `presion_empaque` | kPa | 300 | 100–400 | |
| Vacío de empaque | `vacio_empaque` | kPa | 30 | 0–100 | |
| Rango de temperatura de drenaje | `rango_temp_drenaje` | °C | 5 | 1–20 | |
| Tiempo de estabilidad para alarma | `tiempo_estable_alarma` | s | 5 | 1–60 | |

**Solo lectura (no editable por ningún rol):** presión atmosférica de referencia (`presion_atmosferica`, corrige la errata `admosferica`). Solo la actualiza la calibración automática de la sección 5. Se elimina el valor de respaldo 101.3 del código: si la clave falta, el arranque falla con alarma.

**Se eliminan** (tras confirmar que no tienen referencias): `temp_max` (nadie lo lee y choca de nombre con el de calibración) y `tipo_puerta` (duplica `door_type` del perfil del equipo).

Todos los parámetros editables usan la ventana de ajuste de 3.1. Se elimina el respaldo en código de cada valor por defecto: la única fuente de valores de fábrica es el archivo de fábrica (ver sección 10).

### 3.3 Entradas y salidas
- **Entradas digitales:** estado en tiempo real.
- **Salidas digitales:** estado en tiempo real y modo de prueba (ver regla R-02).
- **Sensores de temperatura y de presión:** lectura en tiempo real y acceso a calibración (sección 8).

### 3.4 Mantenimiento
- **Contadores:** reiniciar ciclos de mantenimiento y fecha de mantenimiento.
- **Calibración de presión atmosférica:** automática, ver sección 5.
- **Impresora:** página de prueba.
- **Imprimir ganancias y compensaciones** de todos los sensores.

### 3.5 Opciones avanzadas (solo ingeniero)
- **Configuración de la máquina:** idioma, unidades de temperatura, unidades de presión, número de serie, nombre de modelo.
- **Funcionalidad de E/S:** reasignación de entradas y salidas ante daño de un puerto (regla R-03).
- **Respaldo y restauración:** exportar e importar configuración, restaurar valores de fábrica (regla R-04).

### 3.6 Usuarios (solo admin)
Crear, desactivar y restablecer contraseña de usuarios. Gestión de operadores (tabla `operadores`, separada de `usuarios`, identificados por nombre sin contraseña).

### 3.7 Conectividad (solo admin)
Wifi, direcciones IP y correo (relay de envío y destinatarios por equipo). Ver hallazgo OPC-01.

### 3.8 Fecha y hora (todos los usuarios)
Ajuste de reloj y zona horaria. Cambio con ciclo en curso bloqueado (R-01) y registrado en bitácora. Los temporizadores de proceso usan `time.monotonic()`, por lo que un salto de reloj no los afecta. Solo cambian las marcas de tiempo de los registros.

### 3.9 Bitácora de auditoría (lectura para todos los roles)
Tabla general `audit_log` con: fecha/hora, usuario, rol, evento, entidad, valor anterior, valor nuevo y detalle. Las tablas existentes `cycle_params_audit` y `sensor_calibration_audit` no se migran en V1. El visor las unifica con una consulta, sin tocar registros existentes. Hoy solo se auditan los cambios de parámetros de ciclo (desde PySide) y la calibración de sensores, y no se registra ninguno de los eventos siguientes. Eventos mínimos:
- cambio de parámetros de ciclo y de sistema;
- cambios de sensores y entradas mostradas;
- reinicio de contadores;
- calibraciones (de sensores y atmosférica, éxito o aborto);
- reasignación de E/S;
- pruebas de salidas;
- cambio de fecha y hora;
- restauración de fábrica, importación de respaldo;
- entrada y salida de suspensión.

### 3.10 Información del sistema (solo lectura)
Versión de software y de firmware, estado de comunicación con el ESP32, número de serie, modelo.

---

## 4. Reglas transversales

| Id | Regla |
|---|---|
| **R-01** | Con ciclo en curso queda bloqueado todo cambio de configuración: parámetros, ruteo de E/S, calibraciones, reinicio de contadores, fecha y hora, restauración y respaldo. |
| **R-02** | **Modo de prueba de salidas:** solo con equipo en reposo, sin presión en cámara y con puertas cerradas. El interlock de puerta es solo por software y no tiene redundancia mecánica. Una salida accionada en prueba puede abrir una puerta bajo presión. |
| **R-03** | **Reasignación de E/S:** reautenticación del usuario, doble confirmación con alerta de criticidad, detección de conflicto (dos funciones en el mismo puerto), la función de interlock de puerta es caso especial con confirmación reforzada, registro en bitácora y reinicio del backend para aplicar. |
| **R-04** | **Reinicio de contadores y restauración de fábrica:** confirmación explícita y registro en bitácora, no solo control por rol. |
| **R-05** | Toda escritura de configuración registra usuario y fecha/hora en bitácora. |

---

## 5. Calibración de presión atmosférica

Acceso: técnico e ingeniero. La ejecuta el equipo de forma automática.

**Precondiciones (todas, durante toda la ventana):**
- puerta abierta (en equipos de doble puerta basta cualquiera de las dos);
- temperatura de cámara menor a 80 °C;
- sin ciclo en curso;
- lectura válida del sensor de presión y del sensor de cámara.

**Procedimiento:**
1. Ventana **continua** de 2 min con muestreo cada 5 s: 24 muestras.
2. La ventana se mide con `time.monotonic()`.
3. Si en cualquier muestra se pierde una precondición, o si hay una lectura inválida: **aborta**, conserva el valor anterior y registra en bitácora el motivo. No reintenta de forma automática. La decisión es abortar para que un fallo no deje el proceso intentando indefinidamente.
4. Al completar las 24 muestras se calcula el promedio y se valida (ver abajo).
5. Si la validación pasa, el promedio pasa a ser la presión atmosférica de referencia, en presión **absoluta**. No se resta atmósfera en ninguna capa.
6. Registro en bitácora: valor anterior, valor nuevo, usuario, fecha/hora, número de muestras y dispersión.

**Validación (propuesta, constantes del sistema, no parámetros de usuario):**

| Criterio | Valor |
|---|---|
| Plausibilidad del promedio | 60 a 106 kPa absolutos |
| Estabilidad de la ventana | máximo menos mínimo de las 24 muestras menor o igual a 1.0 kPa |

Justificación: el equipo se puede instalar a distintas alturas, así que el rango no se ancla a una ciudad. 60 kPa cubre instalaciones cerca de 4000 m y 106 kPa cubre el máximo realista a nivel del mar con alta presión. El criterio de estabilidad detecta una puerta no del todo abierta, una corriente de aire o un sensor inestable, que un solo rango de plausibilidad no detecta. Si la validación falla, no se guarda y se muestra el motivo.

**Sin edición manual:** la presión atmosférica de referencia solo se actualiza por esta calibración. No hay valor de respaldo en código.

**UI durante la calibración:**
- Todo bloqueado excepto **Cancelar**.
- Cancelar aborta con el mismo tratamiento que el paso 3.
- Barra de progreso o contador de muestras y de tiempo restante.
- La lectura de sobrepresión y el paro de emergencia siguen activos.

---

## 6. Suspensión

Parámetro `tiempo_standby` (hoy en el JSON con defecto 5 min y rango 1–60; la validación actual solo descarta valores menores o iguales a 0).

| Propiedad | Valor |
|---|---|
| Unidad | minutos |
| Defecto | 10 |
| Rango | 0 a 60 (0 = desactivada) |
| Semántica | tiempo de inactividad tras el cual el software entra en suspensión; con 0 nunca entra |

**Al entrar en suspensión:**
1. Apaga todas las salidas. La desenergización es el estado seguro de todas ellas (confirmado).
2. La UI pasa a la pantalla de arranque/espera.
3. Sigue leyendo los sensores críticos, para identificar sobrepresión y paro de emergencia.
4. No genera alarma por falta de suministros mientras esté suspendido.
5. Registra el evento en bitácora.

**Al salir de suspensión:** regresa a la pantalla de **preciclo**.

**No entra en suspensión** con ciclo en curso ni durante una calibración; el temporizador de inactividad no corre en esos estados.

**Sobrepresión o paro de emergencia durante la suspensión:** sale de suspensión y presenta la alarma.

**Salida:** un toque en pantalla regresa a preciclo, sin login. El token de sesión ya se invalida al entrar en suspensión; el login solo hace falta para Opciones.

**Implementación:** hoy la suspensión vive en el puente QML (`standby.py`) y el estado HIBERNACION del backend nunca se alcanza. El apagado de salidas y la lectura de sensores críticos deben hacerse en el backend, con HIBERNACION como estado real (OPC-25).

---

## 7. Hallazgos

| Id | Severidad | Hallazgo | Resolución propuesta |
|---|---|---|---|
| **OPC-01** | Crítica | Habilitar Conectividad reactiva H-03: la API no tiene autenticación en los endpoints de actuadores y el backend escucha en todas las interfaces. | Cerrar H-03 (autenticación y escucha restringida) antes de exponer cualquier configuración de red. |
| **OPC-02** | **Crítica** | El interlock de puerta es solo por software. `PATCH /io/test/output/{name}` no comprueba que el modo de prueba esté activo y el backend escucha en `0.0.0.0` sin autenticación: cualquier equipo de la red puede accionar salidas en cualquier estado. | Regla R-02 verificada en backend, guard de `test_mode_active`, token y bind a `127.0.0.1` (`planeacion_backend_autenticacion.md`). |
| **OPC-03** | Alta | La reasignación de E/S puede dejar una función crítica (interlock) en un puerto equivocado. | Regla R-03. Validar conflicto y criticidad en backend. |
| **OPC-04** | Media | Calibración de sensores sin definir: la referencia anterior usa 2 puntos, pero nuestro hallazgo exige 3 capturas para verificar linealidad. Los sensores con coeficientes polinomiales ignoran ganancia y compensación. | Pendiente (sección 8). |
| **OPC-05** | Media | En suspensión las salidas están apagadas. Si el sensor crítico detecta sobrepresión, el software no tiene actuadores que accionar. | Definir la acción (ver pendiente P-3). Propuesta: salir de suspensión y presentar la alarma. |
| **OPC-07** | Alta | Los valores de respaldo del código difieren de los del JSON: banda atmosférica 20 contra 5 kPa, atmosférica 101.3 contra 75 kPa, impresión 180/60 contra 60/30 s, suspensión 5 min. Si falta una clave, el comportamiento cambia sin aviso. Es grave en `rango_presion_atm`, que interviene en la lógica de apertura de puerta. | Eliminar los respaldos en código. Una sola fuente de valores de fábrica, y fallo con alarma si falta una clave. |
| **OPC-08** | Alta | `timeout_puerta` y el intervalo de impresión usan `time.time()`, lo que incumple la regla de `time.monotonic()` para temporizadores de proceso. | Corregir en la implementación; auditar el resto de temporizadores de proceso. |
| **OPC-09** | Media | No existe ruta de escritura de parámetros del sistema. El JSON se lee una sola vez, los mín/máx no se validan y no hay auditoría. | Backend de edición nuevo (sección 10). |
| **OPC-11** | Alta | `ServicioPuertas` copia `presion_atmosferica`, `rango_presion_atm` y `temp_max_apertura` al arrancar. La calibración atmosférica no tendría efecto sobre la apertura de puerta hasta reiniciar. | Lectura en vivo (backend de parámetros, sección 6). |
| **OPC-12** | Media | `ConfigManager` no tiene lock: carrera entre el hilo de control y el de FastAPI al escribir. | `RLock` y escritura sobre el mismo objeto. |
| **OPC-13** | Media | Los respaldos `or 101.3` y `or 20.0` convierten un 0 válido en el valor por defecto. | Eliminar los respaldos. |
| **OPC-14** | Media | La auditoría de parámetros de ciclo la escribe el cliente PySide directo en la base de datos; el backend no recibe usuario. | Pasa al backend con el usuario del token. |
| **OPC-15** | Media | Nada en Python lee `io_enabled` ni `io_contract`; hay cuatro juegos de nombres para las mismas entradas. | Módulo `io_names` y spec aparte de perfil de equipo (P-9). |
| **OPC-10** | Media | La temperatura segura de apertura permite hasta 120 °C, intencional para pruebas. Defecto 80 °C. | Registrar en bitácora todo cambio de este parámetro. Evaluar restringir valores sobre el defecto a ingeniero. |
| **OPC-06** | Baja | Con 24 muestras y una sola ventana, un sensor de presión desviado pero estable pasa la validación si cae en 60–106 kPa. No hay sensor de presión de referencia independiente. | Aceptado en V1.0. La mitigación es la calibración periódica del sensor de cámara (sección 8) y el historial en bitácora. |

---

## 8. Calibración de sensores — por definir

**Estado:** V1 mantiene el método actual (dos puntos, ganancia y compensación, como la referencia anterior). La revisión de dos frente a tres puntos y de los sensores polinomiales queda para después; OPC-04 se acepta temporalmente. Acceso: solo ingeniero.

**Información que debe contener la pantalla** (tomada de la referencia anterior, no de su diseño):
1. Nombre del sensor, valor actual en unidades de ingeniería y cuentas ADC. Para presión, referencia cruzada con la lectura de cámara.
2. Ganancia y compensación (offset): actual, último guardado y por defecto.
3. Acciones: ajustar según el valor por defecto, restaurar último, restaurar por defecto.
4. Método manual por puntos de referencia (valor ingresado y lectura capturada).
5. Método explícito (ganancia y compensación directos).
6. Botón de confirmación y barra inferior (salir, inicio).

**Campos añadidos:** usuario y fecha de la última calibración, fecha de vencimiento, registro en bitácora.

**Restricciones técnicas ya fijadas:**
- La calibración de usuario (`ganancia × valor + offset`) se aplica sobre la salida de la calibración de fábrica, no sobre el ADC crudo.
- Los coeficientes polinomiales ignoran ganancia y compensación.
- La calibración de dos puntos exige tres capturas de referencia para verificar linealidad.
- Los sensores de presión absoluta permanecen en absoluta.

**Decisiones abiertas:** número de puntos (2 o 3), tratamiento de sensores polinomiales (fuera de UI o método manual oculto), requisito de simplicidad frente a precisión.

---

## 9. Pendientes

| Id | Pendiente |
|---|---|
| **P-1** | Calibración de sensores (sección 8). V1 mantiene el método actual; revisión posterior si hace falta. |
| **P-13** | Tiempo límite de chaqueta: confirmar el rango 10–180 min. |
| **P-9** | Spec de perfil de equipo (`io_enabled`), por redactar. |

Cerrados en v4: contadores de servicio sin desactivación (un equipo no puede quedar sin mantenimiento); suspensión (P-2, P-3, P-4), rangos de temperatura y drenaje (P-6c, P-6d), contadores (P-6b, valores), validación atmosférica (P-7), instancia ACV-2026-001 correcta (sin `temp_chaqueta`; un solo sensor de cámara salvo equipos de laboratorio), rama de alarmas (renombre después de unirla), sin sensor de referencia (OPC-06 aceptado), calibración atmosférica con cualquier puerta, modo quiosco con AnyDesk (ver spec de autenticación). Antes: HIBERNACION es la suspensión; operadores sin token; entradas mostradas por programa; rango de suspensión 0–60; respaldos de código eliminados.

---

## 10. Backend de parámetros y almacenamiento

El detalle vive en dos specs:
- `planeacion_backend_autenticacion.md`: token, roles, guard de estado y de modo de prueba, bind local. Va primero.
- `planeacion_backend_parametros.md`: tabla `system_params`, `ConfigManager`, endpoints, `audit_log`, calibración atmosférica en backend, entradas mostradas y gráfica, migraciones y renombres.

Resumen de decisiones:
1. Los parámetros pasan a una tabla; el JSON queda como valores de fábrica.
2. Los cambios se aplican en memoria al guardar y solo en PREPARADO.
3. Validación de rol, rango y estado en el backend, no solo en la UI.
4. `audit_log` general, con las tablas viejas como históricas.
5. `timeout_puerta`, intervalo de impresión, ticket y zumbador pasan a `time.monotonic()`.
6. Gráfica histórica como (ciclo, tiempo, entrada, valor), con la selección de entradas guardada por ciclo.

---

## 11. Dependencias

- `planeacion_backend_autenticacion.md` antes que `planeacion_backend_parametros.md`.
- Especificación de sensores del ciclo.
- Plan de idiomas (claves i18n).
- Spec de perfil de equipo (`io_enabled`).

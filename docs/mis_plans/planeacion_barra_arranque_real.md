# Planeación — Barra de arranque real (conexión de la intro con el arranque por etapas)

Estado: borrador v1 · 12-oct-2026 · Software de Autoclave (Especifika). Sin código: especificación para aprobación antes de instruir a Code.
Documentos relacionados:
- `planeacion_arranque_y_modo_sin_bd.md` (§3 y §4: etapas, ARR-01, fase B) — **fuente de las etapas**.
- `planeacion_animacion_arranque.md` (§6: interfaz `progresoArranque`, ARR-03) — **consumidor**.

## 1. Objetivo
Reemplazar `SimuladorProgresoArranque` (`ui_qml/bridge/progreso_arranque.py`, timers fijos) por un progreso que refleje el arranque real, sin cambiar `IntroArranque.qml`. Este documento no redefine las etapas ni la clasificación de fallos (ya aprobadas); define el contrato entre ambos y lo que falta para conectarlos.

## 2. Decisión
| # | Decisión |
|---|---|
| B-01 | **Opción (a):** el backend abre el puerto desde t = 0 y construye `BackendContext` por etapas después, publicando cada una. Es el ARR-01 del plan de arranque. Se descarta la opción (b) (que cada proceso publique lo suyo): dejaría varias fuentes de verdad y dos criterios de fallo. |
| B-02 | Las etapas 1 y 2 (antes de que exista el backend) las publica el lanzador; ver §4. |
| B-03 | La barra solo avanza (monótona). Un reintento no la hace retroceder. |
| B-04 | La intro sigue sin condicionar nada: solo lee. |

## 3. Qué falta (dependencias)
1. **Fase B del plan de arranque:** sacar `context = BackendContext()` del import de `server.py` (línea 53) a una función de arranque por etapas con registro de etapas. Sin esto la barra real es imposible: el puerto 8000 no responde hasta que todo está construido.
2. **Endpoint de arranque** (§5).
3. **Publicación de las etapas del lanzador** (§4).
4. **Cliente QML/Python** que reemplaza al simulador (§6).
5. **Textos** `arranque.<clave>` en `es.json` y `en.json` para las etapas finales (las del simulador son de ejemplo).
6. **Pesos medidos** en el PC industrial (§7).

## 4. Etapas 1–2 (antes del backend)
Etapa 1 (perfil y reloj) y 2 (liberar procesos previos) ocurren en el lanzador, antes de que el puerto 8000 exista.
Propuesta: el lanzador escribe `data/arranque_lanzador.json` (escritura atómica: temporal + `os.replace`) con `{etapa, estado, codigo}`; las UI lo leen mientras `/arranque` no responda. Alternativa: pasar el estado por argumento/variable de entorno al lanzar cada UI (no sirve para actualizaciones posteriores).
**D-A: aprobada (12-oct-2026).** Archivo `data/arranque_lanzador.json`.

## 5. Contrato del endpoint `GET /arranque`
Disponible desde t = 0, sin token (D-C aprobada: es solo lectura de estado de arranque, sin datos de proceso).
```
{
  "terminado": false,
  "falloBloqueante": false,
  "etapaActual": "verificando_sensores",
  "etapas": [
    {"clave": "cargando_configuracion", "estado": "ok|en_curso|pendiente|degradado|fallo", "codigo": null, "peso": 1.0}
  ]
}
```
- `estado=degradado`: la etapa falló pero el arranque continúa (p. ej. base de datos); cuenta como completada para la barra.
- `fallo`: bloqueante; `falloBloqueante=true`.
- `terminado=true` solo cuando todas las etapas están `ok` o `degradado`.
- Hasta que el backend responde, `terminado=false` y la UI usa lo de §4.

## 6. Cliente en la UI
Clase nueva `ProgresoArranqueReal` (misma interfaz QML que el simulador: `fraccion`, `proceso`, `terminado`, `falloBloqueante`).
- Consulta `/arranque` cada 200–250 ms (mismo polling aceptado en la migración a QML), con timeout corto.
- `fraccion = Σ peso(etapas completadas) / Σ peso(todas)`, más fracción parcial de la etapa en curso solo si la etapa informa subprogreso (§7).
- `proceso` = clave `arranque.<etapa>` (idioma por `assets/textos/<idioma>.json`).
- Backend sin respuesta: se conserva el último valor y se corre el temporizador de 20 s del plan de animación (§5.4). Al agotarlo, `falloBloqueante=true` con código `ARR_SIN_BACKEND`.
- `AUTOCLAVE_INTRO_SIMULACION` se conserva para probar los criterios §10.3 y §10.4 de la animación.
- Las dos UI usan el mismo endpoint; la etapa 9 "Preparando interfaz" la completa cada UI localmente.

## 7. Etapas, textos y pesos (propuesta)
Pesos iniciales **provisionales**: se calibran con tiempos medidos en el Ryzen real (criterio: peso ∝ duración típica, para que la barra avance a ritmo uniforme).
| # | Etapa (plan de arranque §4) | Clave de texto | Origen | Peso inicial | Falla |
|---|---|---|---|---|---|
| 1 | Verificando instalación | `verificando_instalacion` | Lanzador | 1 | Bloqueante |
| 2 | Liberando procesos previos | `liberando_procesos` | Lanzador | 1 | Bloqueante |
| 3 | Iniciando servicios | `iniciando_servicios` | Lanzador/backend | 2 | Bloqueante |
| 4 | Cargando configuración y ciclos | `cargando_configuracion` | Backend | 1 | Bloqueante / degradable (ciclo corrupto) |
| 5 | Verificando calibración | `verificando_calibracion` | Backend | 1 | Bloqueante |
| 6 | Abriendo base de datos | `abriendo_base_datos` | Backend | 1 | Degradable |
| 7 | Conectando con módulos de E/S | `conectando_modulos_es` | Backend | 2 | Bloqueante (sin E/S verificadas no hay ciclo) |
| 8 | Verificando sensores | `verificando_sensores` | Backend | 2 | Bloqueante (canales críticos) / degradable |
| 9 | Preparando interfaz | `preparando_interfaz` | UI | 1 | Bloqueante (`es.json`) / degradable / informativa |

Subprogreso (opcional): las etapas 6 (3 reintentos), 7 y 8 pueden reportar `{intento, total}` o fracción para que la barra no se detenga durante esperas largas. **D-B: resuelta el 12-oct-2026, no por ahora** (se agrega después si en las pruebas la barra se queda quieta demasiado tiempo).
Etapa 7: queda abstracta hasta que existan los módulos M31-U (Modbus TCP); hoy corresponde al serial/ESP32.

## 8. Reglas de comportamiento
1. Fallo bloqueante: `falloBloqueante=true` → la capa de alarma se superpone a la intro (plan de animación §5.3). El código de falla viene de la etapa.
2. Fallo degradable: la barra avanza; la alarma (p. ej. `OPERANDO_SIN_BD`) la publica el backend, no la intro.
3. Etapas reintentables (módulos de E/S, sensores): `estado=en_curso` con reintentos; la barra no retrocede.
4. **Sin módulos de E/S (D-E, aprobada 12-oct-2026):**
   - La barra se detiene en la etapa 7, con su nombre y el código `ARR_SIN_ES`, mientras reintenta.
   - A los 15 s el equipo pasa a la pantalla de espera con alarma específica e INICIAR deshabilitado; la intro no queda congelada.
   - Las etapas 8 y siguientes no corren hasta tener E/S verificadas en estado seguro (sin E/S no hay verificación de sensores).
   - Al conectarse las E/S, el arranque retoma desde la etapa 7 sin reiniciar el software.
   - Esto resuelve la diferencia entre "bloqueante: el splash no avanza" (`planeacion_arranque_y_modo_sin_bd.md` §4) y D-02 de `planeacion_protocolo_serial_esp32.md` §10: gana D-02, y ese plan debe actualizarse para decir que el splash se libera a los 15 s.
5. Tiempo mínimo del splash y de la intro (3,5 s): ya definidos; el progreso real nunca se retrasa por ellos, solo la salida.

## 9. Hallazgos
| Código | Severidad | Hallazgo | Recomendación |
|---|---|---|---|
| BAR-01 | Alta | Mientras `BackendContext` se construya al importar `server.py`, no hay progreso real posible. | Fase B del plan de arranque (ARR-01) como prerequisito. |
| BAR-02 | Media | Las etapas 1–2 no tienen canal hacia las UI (§4). | Decidir D-A. |
| BAR-03 | Media | El simulador tiene 4 etapas de ejemplo; el arranque real tiene 9. Las claves de texto del simulador no coinciden. | Reemplazar al activar el cliente real; actualizar `es.json`/`en.json`. |
| BAR-04 | Baja | Si el arranque es muy rápido, la barra salta de 0 a 100 % antes de 3,5 s. | Aceptado: la animación de 250 ms entre valores y el tiempo mínimo cubren el caso. |
| BAR-05 | Info | `/arranque` expone el estado del equipo sin token. | Aprobado sin token (D-C); no contiene datos de proceso. |

## 10. Criterios de aceptación
1. Con arranque normal, la barra avanza según las etapas reales; no hay temporizadores fijos en el flujo normal.
2. Una etapa lenta (retraso inducido) detiene la barra en ese punto, no más.
3. Fallo bloqueante inducido en cada etapa: la intro muestra el nombre de la etapa y el código en menos de 200 ms desde que el backend lo publica.
4. Base de datos no disponible: barra completa, alarma `OPERANDO_SIN_BD`, sin bloqueo.
5. Backend que no abre el puerto: fallo a los 20 s.
6. Las dos UI muestran la misma etapa en cada instante (±1 ciclo de polling).
7. Con `en.json` activo, los nombres de etapa salen en inglés.
8. La barra nunca retrocede.

## 11. Orden de implementación
Ver §13 (plan de ejecución completo).

## 12. Decisiones por confirmar
- D-A: RESUELTA el 12-oct-2026, archivo `data/arranque_lanzador.json`.
- D-B: RESUELTA el 12-oct-2026, sin subprogreso en la primera versión.
- D-C: RESUELTA el 12-oct-2026, `/arranque` sin token.
- D-E: RESUELTA el 12-oct-2026, sin E/S el splash pasa a la pantalla de espera con alarma a los 15 s (§8.4).
- D-D: pesos iniciales (§7) provisionales hasta medir en el PC industrial (pendiente de confirmación de Cristian).

## 13. Plan de ejecución completo (barra 100 % funcional)

### 13.1 Estado al 12-oct-2026
| Pieza | Estado |
|---|---|
| Backend por etapas, `GET /arranque` sin token, códigos `ARR_*`, `ARR_SIN_ES` (D-E) | Implementado, sin commit (`informe_fase_b_arranque_backend.md`, `informe_fase_b_cierre.md`). Suite: 2656 pasan. |
| Registro con las 9 etapas y pesos provisionales (`backend/arranque/registro.py`) | Implementado. |
| Etapas 1–3 en el backend | Triviales: el hilo solo arranca con el puerto ya enlazado, así que `liberando_procesos` e `iniciando_servicios` se marcan `ok` sin comprobar nada. Valen solo para cuando el backend ya responde. |
| Etapa 8 (sensores) | **Provisional: siempre `ok`** con un aviso en el log. No verifica nada. |
| Lanzador único (UI primero, backend como subproceso, `arranque_lanzador.json`) | No existe. `ui_qml/lanzar.py` en modo `real` no arranca el backend; el que lo arranca es `main.py` (tkinter, a retirar). |
| `ProgresoArranqueReal`, etapa 9 local, textos | No existen. `app.py` sigue usando `SimuladorProgresoArranque`; `es.json` tiene las 4 claves del simulador. |
| Modo sin BD (§7 del plan de arranque) | No existe. Provisional: `/cycle/start` responde 409 sin BD. |
| Pesos medidos | No. Los registra el log de cada transición (`t_inicio`). |

### 13.2 Definición de "100 % funcional"
La barra es funcional cuando se cumplen todas:
1. Avanza solo con etapas reales completadas; no queda ningún temporizador falso en el flujo normal.
2. Cada una de las 9 etapas hace una comprobación real o no aparece en la barra (ver BAR-06).
3. Las dos pantallas muestran la misma etapa en cada instante (±1 ciclo de polling).
4. Cubre el arranque completo, desde antes de que exista el backend (etapas 1–2 del lanzador) hasta que cada UI termina de cargar (etapa 9).
5. Un fallo bloqueante, uno degradable y la falta de E/S se comportan como en §8 (incluida D-E).
6. Los pesos están medidos en el PC donde se instala el equipo.
7. Se cumplen los criterios de §10 de este documento y de `planeacion_animacion_arranque.md`.
8. La matriz de cumplimiento de IEC 62304 incluye los cambios.

### 13.3 Hallazgos nuevos
| Código | Severidad | Hallazgo | Recomendación |
|---|---|---|---|
| BAR-06 | Alta | La etapa 8 muestra "Verificando sensores" pero hoy no verifica nada. En un equipo médico, una barra que dice que verificó algo que no verificó es engañosa. | Hacer real la etapa 8 (F3) o, mientras no exista, no mostrarla en la barra ni en el log de operador. No instalar con el texto activo y la verificación falsa. |
| BAR-07 | Media | Las etapas 1–2 se marcan `ok` en el backend sin comprobar nada (el hilo ya arrancó). La comprobación real debe estar en el lanzador. | F1: el lanzador comprueba perfil, reloj y procesos previos y publica el resultado. |
| BAR-08 | Media | `lanzar.py real` y `esperar_backend` usan `GET /status`, que ahora responde 503 mientras arranca. Nadie lo trata como "arrancando". | F1: usar `GET /arranque` para esperar el backend. |
| BAR-09 | Media | `ui_qml/assets/textos/` solo tiene `es.json`; no hay `en.json`. Los textos en inglés de las etapas dependen del plan i18n. | F2 agrega las claves en español; el inglés se agrega al implementar el plan i18n. |
| BAR-10 | Baja | Las claves del simulador (`conectando_tarjeta`, etc.) no coinciden con las 9 reales. | F2 las reemplaza y conserva `fallo_titulo`, `fallo_bloqueante` y `sin_progreso`. |

### 13.4 Fases
Tamaño relativo: S pequeño, M mediano, L grande.

| Fase | Contenido | Tam. | Depende de | Prompt |
|---|---|---|---|---|
| F0 | Cierre de la fase B: commits separados (E0/E1, fase B, ARR-01, docs), suite verde en cada uno | S | — | P1 |
| F1 | Lanzador único: perfil/reloj, limpieza de procesos previos, backend como subproceso, UI primero, supervisión, `data/arranque_lanzador.json` | L | F0 | P2 |
| F1b | Migrar el asistente de instalación (hoy tkinter, `installation/wizard.py`, 297 líneas, 4 pasos) a QML. Antes: propuesta de diseño | M | F0 | P2b |
| F2 | `ProgresoArranqueReal`: lee archivo del lanzador y `/arranque`, fusiona (monótono), etapa 9 local, plazo de 20 s, textos, reemplazo del simulador | M | F0 (F1 para probar el flujo completo) | P2 |
| F3 | (después del 19-oct, D-G) Etapa 8 real: `validar_canal()`, SEN-01, SEN-03, umbrales en configuración, clasificación bloqueante/degradable (§6 del plan de arranque) | L | F0 | P3 |
| F4 | Modo sin base de datos (§7 del plan de arranque): `CycleLogger` protegido, respaldo, contador, login sin base, `OPERANDO_SIN_BD`. **Entra antes del 19-oct (D-H)** | L | F0 | P4 |
| F5 | Pesos medidos, pruebas de integración y manual, criterios §10, matriz 62304 | M | F1–F3 | P5 |

F1b pide su propio plan (pantallas, validación del código de activación, qué perfil se escribe) porque el asistente decide el perfil de instalación del equipo, que es código de seguridad. F1 y F2 se pueden pedir juntos: F2 se puede probar con el backend real aunque el lanzador sea provisional, pero la barra completa solo se ve al terminar F1.

### 13.5 Detalle por fase
**F1 — Lanzador único**
- Comprueba perfil de instalación y reloj (`ClockTamperedError` → `ARR_RELOJ`, `ARR_PERFIL`), libera procesos previos (`backend_guard.cleanup_stale_backend`) y publica cada etapa en `data/arranque_lanzador.json` (escritura atómica: temporal, `fsync` y `os.replace`). Campos: `etapa`, `estado`, `codigo`.
- Abre las dos pantallas primero y luego lanza el backend como subproceso independiente; espera con `GET /arranque`, no con `/status`.
- Si el backend termina, lo informa en el archivo (`ARR_SIN_BACKEND`); no lo reinicia.
- Si una pantalla se cierra, la relanza hasta 3 veces con 5 s de espera (D-04); el backend nunca se reinicia por eso.
- Mientras F1b no esté hecha, y solo de forma transitoria, el lanzador invoca el asistente tkinter cuando falta el perfil. La salida definitiva es F1b (D-F).
- Fuera de F1: heartbeat de `last_shutdown.json`, ticket de arranque y retiro de tkinter (fase E del plan de arranque, ARR-02).

**F2 — `ProgresoArranqueReal`**
- Misma interfaz QML que el simulador: `fraccion`, `proceso`, `terminado`, `falloBloqueante`.
- Fuente: `GET /arranque` cada 200–250 ms cuando responde; si no, `arranque_lanzador.json`. `fraccion = max(anterior, nueva)`.
- Etapa 9: la completa cada UI cuando carga `es.json`, fuentes e interfaz; se informa a sí misma, no al backend.
- Sin respuesta de ninguna fuente durante 20 s: `falloBloqueante` con código `ARR_SIN_BACKEND` (ya lo implementa `IntroArranque.qml`).
- Textos `arranque.<clave>` de las 9 etapas en `es.json`. `AUTOCLAVE_INTRO_SIMULACION` se conserva solo para pruebas.
- `terminado` de `/arranque` excluye la etapa 9; la UI lo combina con el suyo.

**F3 — Etapa 8 real**
- `validar_canal()` única, usada en el arranque y en la supervisión continua (criterios a–d de §6 del plan de arranque). Corrige SEN-01 (`None` como falla) y SEN-03 (`evaluar_banda` con `None`).
- Clasificación de canales ya aprobada (§6). Umbrales de crudo por canal en configuración, valores pendientes de la prueba de banco.
- Riesgo residual R-ARR-04 sigue abierto en presión hasta la prueba de banco; se documenta.
- Esta fase toca código de seguridad: evaluar el impacto normativo con la skill de 62304 antes de implementar.

**F4 — Modo sin BD**
- Según §7 del plan de arranque (7.1 a 7.8). Necesario para que "degradable" sea cierto en la etapa 6: hoy, sin BD, el equipo no corre ciclos.

**F5 — Cierre**
- Medir duración de cada etapa en el PC de instalación con el log de transiciones; pesos ∝ duración típica. Dejar los pesos en una tabla de configuración, no en código.
- Pruebas de integración: lanzador + backend + dos UI contra el simulador de fallos; criterios de aceptación de §10 y de la animación (§10.3 y §10.4).
- Prueba manual con y sin tarjeta, sin BD y con el puerto 8000 ocupado.
- Actualizar la matriz de cumplimiento 62304 (`ARR_*`, `/arranque`, `validar_canal`, riesgos R-ARR-01 a R-ARR-05).

### 13.6 Decisiones por confirmar
- **D-F: RESUELTA el 12-oct-2026.** El asistente de instalación se migra a QML (F1b). Hasta entonces, el lanzador lo invoca en tkinter de forma transitoria.
- **D-G: RESUELTA el 12-oct-2026, oculta por el momento.** Para la instalación del 19-oct la etapa 8 no se muestra en la barra (BAR-06). Consecuencias:
  - El equipo arranca sin verificación de sensores al inicio; la supervisión continua actual sigue igual, con SEN-01 y SEN-03 sin corregir. Ese riesgo residual se escribe en el informe de instalación.
  - La etapa 8 no se borra del registro: queda marcada como oculta, sin peso en la barra y sin texto, hasta que F3 la haga real. El texto "Verificando sensores" no debe aparecer en ninguna pantalla mientras no verifique nada.
  - F3 sigue siendo necesaria después del 19-oct; al completarla se reactiva la etapa y se recalculan los pesos (F5).
- **D-H: RESUELTA el 12-oct-2026.** F4 (modo sin BD) entra antes del 19-oct.
- **D-I:** los textos en inglés de las etapas esperan al plan i18n (BAR-09).
- **D-D:** pesos provisionales hasta F5.

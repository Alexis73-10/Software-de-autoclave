# Planeación — Fin de ciclo, fallos y puertas manuales

> **Adenda 2026-10-14 (tanda, T3):** el §17 (sensores) queda reemplazado por `instruccion_claude_code_tanda_noche.md` §1.1: el sensor Principal del programa decide temperatura de apertura, cámara segura, "NO ABRIR" y apertura automática; lectura `None` del Principal = cámara NO segura. Implementado en `core/runtime/sensores_ciclo.py` y `ser_puertas.py`.

**Versión:** borrador v3 · **Fecha:** 2026-10-12 · **Rama base:** `dev`
**Equipo objetivo:** autoclave de **piso de laboratorio**, 2 puertas abatibles manuales, con chaqueta, fuente de vapor **por confirmar** (generador interno, caldera externa o mixto; aún no está definido si este equipo lleva generador) y sin presostato de suministro de vapor ni entrada de suministro eléctrico en esta versión, bomba de vacío de anillo líquido y todos los tipos de secado. Instalación objetivo 2026-10-19. Programas: Bowie & Dick, Instrumental 134, Instrumental 121 y Líquidos (el quinto no está definido y no sale). Se instala como equipo demo en un laboratorio donde tendrá uso real después de las pruebas de seguridad y la validación del proceso (ver §14).
**Estado:** pendiente de aprobación. Sin código escrito. Los puntos marcados **S-xx** son supuestos por confirmar y **V-xx** son verificaciones que debe hacer Claude Code en solo lectura antes de implementar.

---

## 1. Objetivo y alcance

Definir de forma cerrada: (a) cómo termina un ciclo según su causa, (b) a dónde lleva cada fallo y cómo vuelve el equipo a servicio sin personal técnico presente, (c) cuándo el software considera la cámara segura para abrir, y (d) cómo se comporta el software con puertas **manuales** (solo detección de posición).

Fuera de alcance: voz (se deja para el final), bilingüe (diferido para este equipo), puertas automáticas, nuevas alarmas de las Partes B y C (solo lo que toque este plan), autenticación de la tarjeta (ver §9).

## 2. Decisiones confirmadas por Cristian (11-oct)

| ID | Decisión |
|---|---|
| D-01 | El equipo tiene 2 puertas abatibles, **manuales**, con un solo sensor de "cerrada" por puerta. El software solo detecta posición: no bloquea ni actúa. |
| D-02 | Las puertas tienen enclavamiento **mecánico** por presión de cámara. El software no puede saber si está enclavado. |
| D-03 | Puerta detectada abierta con ciclo en curso = **FALLO** (protocolo de fallo, igual que hoy). |
| D-04 | Al terminar un ciclo (éxito, cancelación o fallo) se muestra "NO ABRIR" hasta que la cámara esté segura (presión en rango y temperatura ≤ `temp_max_apertura`), y ese mismo criterio impide iniciar un ciclo nuevo. |
| D-05 | La cancelación por el operador sigue yendo a PREPARADO, con protocolo de fallo y la misma condición de cámara segura. |
| D-06 | **Ningún fallo exige rol técnico o ingeniero para reiniciar.** La pérdida momentánea de comunicación o de suministro eléctrico no puede dejar el equipo fuera de servicio hasta que llegue soporte. El operador reconoce y el equipo vuelve a PREPARACION, que vuelve a verificar. |
| D-07 | El paro de emergencia es un botón físico: apaga el generador de vapor (si lo tiene), corta la energía de las salidas DO y avisa al software. |
| D-08 | Corte de energía o reinicio del PC en pleno ciclo: nunca se reanuda, se arranca en estado seguro y se registra el ciclo como interrumpido. |
| D-09 | Firmware de la tarjeta: se etiqueta **1.5**. |
| D-10 | Voz al final. |
| D-11 | Apertura automática: no aparece en el menú con puerta manual y queda desactivada por defecto. |
| D-12 | Paro de emergencia = contacto normalmente cerrado en entrada propia. Confirmó también que bloquear el inicio de ciclo hasta `temp_max_apertura` es aceptable. |
| D-13 | El reemplazo de la tarjeta ESP32 siempre lo hace un técnico o ingeniero. Emparejamiento dividido: v1.0 con aviso, bloqueo y autenticación en versión posterior (§9). |
| D-14 | Sin aviso de fallo recurrente. |
| D-15 | Sin documentos del SGC de Especifika por ahora: se trabaja directamente contra la NTC-IEC 62304. |
| D-16 | Paro de emergencia a **lógica de seguridad intrínseca**: hoy el DI lee 1 pulsado y 0 sin pulsar; se invierte (paro = DI en 0, o sin datos) y el cableado de la señal pasa a contacto NC. Un desajuste entre cableado y software siempre cae en "paro", nunca en "sin paro". |
| D-17 | Entradas de suministro de este equipo: solo **aire comprimido**. No se cablean agua de bomba, agua de generador, vapor ni suministro eléctrico. |
| D-18 | Líquidos **sale en la instalación** (equipo demo de laboratorio). No tiene que funcionar perfecto el 19: la Fase A incluye las pruebas físicas y las correcciones. |
| D-19 | La descompresión rápida debe poder usarse en ciclos de sólidos, también en el estado seguro. En líquidos nunca. |
| D-20 | "Apagar equipo" **sí apaga Windows** desde el software (es posible sin diálogo de Windows; la confirmación es la propia del software). Se retiran "Reanudar" y el requisito del lanzador. |
| D-21 | El latido (`HB`) hacia la tarjeta solo se envía mientras el lazo de control haya ejecutado un tick reciente. |
| D-23 | El menú de instalación debe permitir elegir la fuente de vapor del equipo (generador interno, caldera externa o suministro mixto) para **cualquier** equipo, incluido este. El generador tiene todos sus controles, protecciones y sensores propios. |
| D-22 | Protocolo de estado seguro (§15) común a todo fallo, cancelación y paro. |

## 3. Hallazgos del código

| ID | Hallazgo | Evidencia |
|---|---|---|
| PF-01 | `installation_profile.json` declara `door_count: 2`, `door_type: advanced`. Este equipo es `simple`. | `installation_profile.json` |
| PF-02 | `_verificar_puertas()` fija dos puertas y revisa el empaque `pres_empaque_*`. Una entrada digital ausente se lee como 0 y da `FALLO_PUERTA_n_ABIERTA` al instante. | `state_machine/states/ciclo.py:184-203` |
| PF-03 | `puertas_cerradas()` de PREPARADO también fija las dos puertas y los avisos son `PUERTA_1_ABIERTA` / `PUERTA_2_ABIERTA`. | `state_machine/states/preparado.py:206-221` |
| PF-04 | `SimpleDoor.update()` retorna sin cambiar el estado si la entrada es `None`: conserva el último estado conocido. | `devices/puertas/simple_door.py:58-62` |
| PF-05 | `_mantener_apertura_automatica()` reintenta cada 5 s y avisa `APERTURA_AUTOMATICA_DENEGADA` a los 60 s si la puerta no se mueve. Con puertas sin actuador y `apertura_automatica=true` se genera ese aviso en cada ciclo. | `ciclo.py:294-390` |
| PF-06 | `/cycle/acknowledge` no revisa presión ni temperatura. Con puerta manual, "Confirmar" no protege nada. La protección es la señal "NO ABRIR" y el bloqueo de inicio. | `backend/server.py:1092-1130` |
| PF-07 | `GlobalState.EMERGENCIA` no se asigna en ningún punto del código. `emergencia_run()` es código muerto (solo hace `print`). El paro se trata como bandera dentro de cada estado. | `state_machine.py:135`, `emergencia.py` |
| PF-08 | `esta_preparado()` no incluye ninguna condición de temperatura de cámara. D-04 la agrega. | `preparado.py:227-241` |
| PF-09 | Al salir de FALLA se ejecuta `Alarmas_activas.clear()`. | `state_machine.py:122` (lo resuelve la Parte A de alarmas) |

**V-01** Confirmar que si el operador reconoce un FALLO con la cámara aún presurizada, PREPARACION reanuda la despresurización (el protocolo de fallo deja de ejecutarse cuando `CicloState` deja de correr).
**V-02** Verificar qué guarda la tabla `ciclos` cuando el proceso muere a mitad de ciclo (¿hay fila sin cierre?) y qué hace el arranque con ella.
**V-03** Verificar que al conectar la tarjeta el software envía ALL_OFF y que el firmware arranca con las salidas en 0, y si ya existe un apagado de salidas por falta de tramas.
**V-04** ¿Existe hoy una función de apagado del equipo? ¿Qué tan acotado es agregar la de §16? ¿El lanzador relanza el backend si este se cierra?
**V-08** Con el perfil sin presostato de vapor ni entrada de suministro eléctrico, ¿qué alarmas o bloqueos aparecen por esas entradas ausentes?
**V-09** ¿`installation_profile` admite varios tipos de secado a la vez? ¿Dónde se elige y qué fases usa cada uno?
**V-10** Estado del ciclo de Líquidos en el código (roles de sondas, calentamiento, esterilización, descompresión).

## 4. Matriz de fin de ciclo

Todas las filas terminan con la secuencia ya existente: el resultado queda pendiente, el operador lo ve y confirma, y la máquina sigue. La diferencia está en qué hace el equipo y a dónde va.

| Causa | Acción sobre salidas | Resultado | Tras confirmar | Aviso / registro |
|---|---|---|---|---|
| Ciclo completado | Válvula de reposo + drenaje (como hoy). Sin apertura automática (§6.4) | `exitoso` | PREPARADO | Ticket y registro del ciclo |
| Cancelación del operador | Protocolo de fallo | `cancelado` | PREPARADO | Ticket marcado cancelado |
| Fallo de fase (timeout, presión, temperatura) | Protocolo de fallo | `fallo` | FALLA → PREPARACION | Ticket marcado fallo, con motivo |
| Puerta detectada abierta o sensor inválido (D-03) | Protocolo de fallo | `fallo` | FALLA → PREPARACION | Motivo con el número de puerta |
| Sensor crítico ausente | Protocolo de fallo | `fallo` | FALLA → PREPARACION | PREPARACION lo detecta de nuevo y bloquea el inicio mientras persista |
| Pérdida de comunicación mayor a 5 s | Protocolo de fallo (reintenta ALL_OFF hasta ACK) | `fallo` | FALLA → PREPARACION | Igual; se registra la duración de la pérdida |
| Fallo de suministro eléctrico | Protocolo de fallo | `fallo` | FALLA → PREPARACION | Igual |
| Paro de emergencia | Protocolo de fallo y ALL_OFF continuo mientras esté activo (§7) | `fallo` | Solo tras soltar el paro y reconocer de nuevo | Ticket marcado emergencia |

**Regla de reinicio (D-06):** el rol no condiciona el reinicio. Lo condiciona el estado físico. Si la causa persiste, PREPARACION mantiene la alarma y no habilita PREPARADO. Si la causa desapareció, el equipo queda disponible. Así una pérdida momentánea no deja el equipo fuera de servicio, y un sensor dañado sí impide iniciar sin necesidad de bloquear por rol.

**S-01** (opcional) Si el mismo fallo se repite 3 veces seguidas, mostrar un aviso no bloqueante "Fallo recurrente: avisar a soporte". No bloquea la operación.

## 5. Cámara segura y señal "NO ABRIR"

Condición `camara_segura` (se calcula en el backend y se publica en `/status`):

```
camara_segura = presión de cámara en [atm − rango_presion_atm, atm + rango_presion_atm]
                Y temp_camara ≤ temp_max_apertura
```

- **Falla cerrada:** si falta alguna de las dos lecturas, `camara_segura = false`.
- Se muestra "NO ABRIR" en las pantallas previa al ciclo y de ciclo, en **cualquier** estado (no solo al terminar un ciclo), mientras `camara_segura` sea falso.
- Cuando pasa de falso a verdadero tras un ciclo, suena el aviso existente (`BEEP_FALLO` para fallos; para éxito se define en el plan de voz/avisos).
- `esta_preparado()` agrega `camara_segura` como condición de inicio (D-04).
- `temp_max_apertura`: defecto 80 °C con techo de 120 °C intencional para pruebas (decisión previa). No cambia.

**S-02** Confirmar que bloquear el inicio por temperatura es aceptable para ciclos consecutivos: el siguiente ciclo solo arranca cuando la cámara baja a `temp_max_apertura`.

## 6. Puertas manuales

### 6.1 Perfil
`door_type = "simple"`, `door_count = 2`. `installation_profile.json` queda `locked`; lo cambia el ingeniero con el procedimiento de instalación, no el operador.

### 6.2 Lectura y posición segura
- La posición de cada puerta se toma del servicio de puertas, no de claves fijas en cada estado.
- Entrada ausente o `None` = puerta **abierta** (falla cerrada). Se corrige PF-04: una lectura inválida deja de conservar el último estado.
- Sin empaque: se elimina la revisión de `pres_empaque_*` para `door_type=simple`.

### 6.3 Comportamiento por estado

| Estado | Puerta abierta |
|---|---|
| PREPARACION / PREPARADO | Aviso `PUERTA_n_ABIERTA`; impide iniciar |
| CICLO | FALLO (D-03) |
| Esperando confirmación (éxito) | Esperado: no genera alarma |
| FALLA | Sin efecto |

### 6.4 Apertura automática (D-11)
Con puerta sin actuador, `finalizacion.apertura_automatica` **no se muestra en Opciones**, los perfiles de este equipo salen con `false` y el código ignora el valor aunque un JSON viejo lo traiga en `true`. Se corrige PF-05.

### 6.5 Procedimiento obligatorio de instalación
Como el software no puede ver el enclavamiento mecánico, la instalación incluye una **prueba física** del enclavamiento con cámara presurizada (según el procedimiento del fabricante de las puertas) y su registro. Sin ese registro no se libera el equipo.

## 7. Paro de emergencia

- Se mantiene como bandera `PARO_EMERGENCIA`, leída desde una entrada digital propia, contacto normalmente cerrado (cable roto = paro) (D-12). **Lógica invertida (D-16):** paro = entrada en 0 o sin datos de la tarjeta. La lectura cruda de PREPARACION se reemplaza por la bandera. Antes de la instalación, el cableado de la señal pasa a NC y se prueba pulsando el botón y desconectando el cable.
- Mientras el paro esté activo: el software envía ALL_OFF de forma continua hasta recibir ACK. **Al soltar el botón vuelve la energía a las salidas DO; ninguna salida puede quedar en ON dentro de la tarjeta.**
- Soltar el paro **no** restablece nada: se exige un reconocimiento nuevo (ya implementado, OPC-23).
- Se retira el estado `GlobalState.EMERGENCIA` y `emergencia_run()` (código muerto, PF-07), o se documenta como reservado. Recomendación: retirarlos.
- El generador de vapor apagado por el botón se reinicia manualmente según su procedimiento. El software no lo rearma.

## 8. Pérdida de comunicación, energía y reinicio

- Pérdida de comunicación: se conserva la tolerancia de 5 s (`_TOLERANCIA_DESCONEXION_SEG`). Superada, aborta el ciclo y sigue la matriz del §4.
- Al arrancar, el software comprueba (V-02) si el último ciclo quedó sin cierre y lo marca `INTERRUMPIDO` sin reanudarlo. Envía ALL_OFF al conectar (V-03). Si la cámara no es segura, "NO ABRIR" aparece desde el primer momento.
- **Sin UPS** en esta versión (opción futura). El equipo no detecta el corte de energía: la protección es la recuperación al reiniciar. Apagado del equipo: ver §16.

## 9. Firmware ESP32 (tarea separada)

- Versión **1.5**: al arrancar, la tarjeta envía por serial su versión y su identificador único (MAC del chip). La trama lleva el CRC v2 ya existente.
- El software muestra la versión en Información del sistema y la guarda en el registro.
- **Versión 1.0 (D-13):** en la primera conexión un ingeniero asocia el identificador al número de serie del equipo (`installation_profile.json`). Si después llega un identificador distinto, se muestra un aviso **no bloqueante** y se registra en `audit_log`.
- **Versión posterior:** impedir el inicio de ciclos hasta que un técnico o ingeniero inicie sesión y confirme el reemplazo; nunca aborta un ciclo en curso y solo bloquea tras lecturas consecutivas del mismo ID distinto. Motivo del diferimiento: es otra compuerta de seguridad sobre el inicio de ciclo, la ESP32 será reemplazada por módulos Modbus M31-U en las próximas semanas, y el tiempo hasta la instalación es corto.
- Requisitos para el firmware 1.5: las salidas arrancan en 0 y siguen ahí hasta recibir una orden válida; **si dejan de llegar tramas válidas del PC durante unos segundos, apaga todas las salidas** (cubre cuelgue de Windows, reinicio por actualización o apagado abrupto).
- El sketch actual se llama `Comunicacion_esclava_ESP32_V2`; la etiqueta de versión es 1.5 y debe quedar escrita en el propio sketch.

## 10. Impacto IEC 62304 (Clase C) y riesgos

No existe archivo de gestión de riesgos ISO 14971 en el proyecto. Se proponen estos peligros como entrada inicial; se numeran `HAZ-FC-nn`.

| ID | Peligro | Mitigación | Verificación |
|---|---|---|---|
| HAZ-FC-01 | Apertura con cámara presurizada o caliente | Enclavamiento mecánico (hardware) + "NO ABRIR" + bloqueo de inicio. El software **no** puede verificar el enclavamiento. | Prueba física de instalación (§6.5); prueba de `camara_segura` |
| HAZ-FC-02 | Sensor de puerta inválido o ausente | Se trata como abierta | Prueba unitaria |
| HAZ-FC-03 | Ciclo en marcha con puerta abierta | FALLO + protocolo de fallo | Prueba de integración con simulador |
| HAZ-FC-04 | Salidas activas al soltar el paro | ALL_OFF continuo + firmware con salidas en 0 | Prueba en banco con la tarjeta real |
| HAZ-FC-05 | Reanudar un ciclo tras corte de energía | Nunca se reanuda | Prueba de arranque con ciclo sin cierre |
| HAZ-FC-06 | Reconocer un fallo con presión residual y soltar el control (V-01) | Por verificar | Prueba con simulador |
| HAZ-FC-07 | Usar carga de un ciclo fallido o cancelado como esterilizada | Ticket y pantalla marcan el resultado | Revisión del ticket |
| HAZ-FC-08 | Bomba de anillo líquido sin agua y generador sin nivel, porque no hay entradas de agua cableadas (D-17) | Protecciones por hardware (confirmadas por Cristian el 12-oct): el generador tiene controles, protecciones y sensores propios; la bomba de agua tiene flotador que interrumpe la bobina del contactor | Revisión del esquema; prueba física |

Riesgo residual a registrar: la protección contra apertura bajo presión depende de un elemento mecánico fuera del alcance del software.

## 11. Pruebas mínimas

1. Con `door_type=simple`, 2 puertas y sin `pres_empaque`: el ciclo inicia con ambas cerradas y no genera `FALLO_PUERTA_*`.
2. Puerta 1 o 2 abierta en CICLO: FALLO con motivo correcto.
3. Entrada de puerta `None`: tratada como abierta.
4. `camara_segura` con cada combinación de presión y temperatura, incluyendo lecturas ausentes.
5. Cada fila de la matriz del §4: resultado, destino y registro.
6. Reinicio tras fallo sin rol técnico: vuelve a PREPARACION y bloquea si la causa persiste.
7. Paro de emergencia: ALL_OFF continuo, reconocimiento nuevo, ninguna salida en ON al liberar (banco con la tarjeta real).
8. Arranque con ciclo sin cierre: queda `INTERRUMPIDO` y no reanuda.
9. `apertura_automatica` no aparece en el menú ni genera avisos con puerta sin actuador.
10. Firmware: salidas en 0 al arrancar y apagado de salidas al perder las tramas del PC (banco con la tarjeta real).
11. Perfil sin presostato de vapor ni entrada de suministro eléctrico: ninguna alarma ni bloqueo espurio (V-08).

## 12. Etapas de implementación

| Etapa | Contenido | Origen |
|---|---|---|
| E0 | Robustez ante lecturas inválidas (`None` de temperatura, `temp_drenaje`) en PREPARACION y PREPARADO | V-07 |
| E1 | Perfil de puertas manuales; sin revisión de empaque; capacidades por perfil para los DI de suministro que el equipo no tiene | V-05, V-08 |
| E1b | Selector de fuente de vapor en la instalación (generador interno, caldera externa, mixto) y salidas de vapor según la fuente | D-23 |
| E2 | `camara_segura` en `/status`, "NO ABRIR" y condición de inicio | §5 |
| E3 | Protocolo de estado seguro común (§15) y matriz de fin de ciclo | V-01 |
| E4 | Arranque seguro: ALL_OFF al conectar, cierre de ciclos interrumpidos y cierre inmediato del COMPLETADO | V-02, V-03 |
| E5 | UI: "NO ABRIR", barra inferior del login, "Apagar equipo" | §16 |
| E6 | Firmware 1.5 con CRC, versión e ID, y watchdog sobre tramas válidas; heartbeat ligado a la salud del lazo de control | V-03 |
| E7 | Pruebas en banco con la tarjeta real | E0 a E6 |
| E8 | Líquidos (§17) | V-10 |

## 13. Supuestos por confirmar

Todos los supuestos S-01 a S-05 quedaron resueltos (ver D-11 a D-14 y §8, §9). Pendiente: definir la fuente de vapor de este equipo (generador, caldera o mixto) y su selector en el menú de instalación (etapa E1b).

## 14. Liberación en dos fases (uso demo con uso real posterior)

- **Fase A, banco y validación:** sin uso real. Incluye todas las pruebas del §11, la prueba física del enclavamiento (§6.5) y la validación del proceso de esterilización con los indicadores y el protocolo que defina Cristian.
- **Fase B, uso real en laboratorio:** solo se autoriza con (1) la Fase A completa y registrada, (2) archivo de riesgos mínimo con los HAZ-FC del §10 y sus verificaciones, y (3) la lista de limitaciones conocidas entregada al laboratorio.
- Sin los documentos del SGC, el criterio de "listo" se apoya directamente en la NTC-IEC 62304 (Clase C).

## 15. Protocolo de estado seguro (aprobado con observación el 12-oct; común a todo fallo, cancelación y paro, D-22)

1. **Paro activo:** ALL_OFF continuo hasta recibir ACK; la pantalla muestra "PARO DE EMERGENCIA, NO ABRIR" con presión y temperatura; los sensores se siguen leyendo.
2. **Paro liberado:** las salidas siguen en 0, sin avance automático. La pantalla pide verificar que no hay fuga y ofrece "Confirmar y llevar a estado seguro" (cualquier operador, sin rol), fusionado con el reconocimiento del resultado del ciclo.
3. **Confirmado:** exige comunicación y sensores válidos; el paro se revisa en cada tick (si se vuelve a pulsar, se regresa al paso 1). Cámara presurizada: se usa el modo de descompresión del programa activo; en **sólidos** puede ser la rápida (D-19) y, si vence el tiempo, escala como el protocolo de fallo actual; en **líquidos** nunca la rápida (enfriamiento o lenta, §17); sin programa activo o con la presión desconocida, la lenta y sin escalar. El protocolo apaga al terminar toda válvula que haya abierto (hoy `descompresion_chaqueta` queda enclavada, PF-10). Cámara en vacío: aire atmosférico hasta quedar en rango. La chaqueta no se ventea sola (solo se muestra su presión). El generador no se rearma.
4. **Estado seguro:** presión en rango y temperatura ≤ `temp_max_apertura` → aviso sonoro, se retira "NO ABRIR" y se pasa a PREPARACION. Registro en `audit_log`: paro activado, liberado, confirmado y estado seguro alcanzado, con la duración.

## 16. Apagar equipo (D-20)

Botón con confirmación del propio software. Condición de uso: **cámara segura** (§5) y estado distinto de CICLO y del protocolo del §15; sin la condición, el botón no actúa y muestra el motivo. Secuencia: ALL_OFF, cierre de la base de datos (`DbManager.close()`, que hoy nadie llama), cierre del puerto serial y apagado de Windows con `shutdown /s`. Windows permite este apagado sin diálogo propio a una aplicación de usuario estándar; la confirmación es la del software. Solo el proceso de la ventana principal lo ejecuta (la secundaria no). Tras apagar, el PC se enciende al volver la energía o con su botón. La tarjeta apaga las salidas por watchdog (D-21).

## 17. Líquidos (L1 a L6 adoptadas como valores de trabajo de la Fase A, por validar en banco)

Spec propia `planeacion_ciclo_liquidos.md`. Resueltas: roles de sondas (AI1 y AI2 dentro del líquido, AI3 de referencia), activación de una o dos, apertura con doble condición y continuación con una sonda caída con alarma. Valores de trabajo: L1 lazo de vapor contra la referencia y `tipo_carga` como parámetro del ciclo; L2 F0 sobre la sonda de carga más baja; L3 `delta_t_max_choque` 25 °C configurable, a validar en banco con vidrio real; L4 par propio de tasas de calentamiento y presión (10 kPa/min); L5 entrada a esterilización con carga ≥ temperatura de esterilización sostenida 10 s; L6 enfriamiento y descompresión de líquidos en la misma spec, sin descompresión rápida.

## 18. Resultados de las verificaciones (12-oct)

Informe completo: `docs/informes/informe_verificaciones_fin_de_ciclo.md`.

| ID | Hallazgo | Gravedad | Etapa |
|---|---|---|---|
| PF-10 | Tras reconocer un FALLO nadie continúa el protocolo de fallo. PREPARACION ventea solo con `descompresion_rapida` y solo si pasan sensores y suministros; nunca apaga `descompresion_chaqueta` (modos 4/5). | Alta | E3 |
| PF-11 | El `.ino` del repositorio no entiende el CRC del PC: todo `SET … ON*HHHH` queda en OFF y las tramas del firmware salen sin CRC. El firmware v2 con CRC no está en el repositorio. | Crítica | E6 |
| PF-12 | El watchdog de la ESP32 se reinicia con cualquier línea y solo se arma tras la primera. El `HB` lo envía un hilo independiente, así que un lazo de control colgado sigue alimentándolo. | Alta | E6 |
| PF-13 | El PC no envía ALL_OFF al conectar (parámetros definidos y sin usar). | Alta | E4 |
| PF-14 | PREPARACION, PREPARADO y CICLO exigen siempre las dos puertas y los dos sensores de empaque. Sin sensores de empaque PREPARACION se bloquea. | Alta | E1 |
| PF-15 | Temperaturas inválidas (`None`) pasan como válidas (se compara `== 0`) y `temp_drenaje=None` lanza `TypeError`, que corta el tick (F0, registro y buzzer incluidos). | Alta | E0 |
| PF-16 | Sin presostato de vapor la chaqueta nunca se calienta (y PRECALENTAMIENTO envía ON y OFF en el mismo tick). Sin entrada de suministro eléctrico PREPARADO nunca queda listo. | Alta | E1 |
| PF-17 | No existe el cierre de ciclos interrumpidos al arrancar. Un ciclo COMPLETADO solo se cierra al confirmarse. | Media | E4 |
| PF-18 | Apagado: solo hay botón en tkinter; no cierra la base de datos (`DbManager.close()` nunca se llama). | Media | E5 |
| PF-19 | No existe ciclo de líquidos: calentamiento y esterilización ignoran la sonda de carga y no hay perfil. El protocolo de fallo omite el enfriamiento de los modos 4/5. | Alta | E8 |
| PF-20 | Falta `factory/instrumental_121.json`; el tipo de secado es parámetro del ciclo (`secado.modo` 1 a 3), no del perfil. | Baja | — |
| PF-21 | El paro se lee del DI 10 como 1 = paro. Con el firmware, una entrada sin conectar lee 0. Si el cableado es normalmente cerrado, un cable cortado no se detectaría. | Por confirmar | E4 |

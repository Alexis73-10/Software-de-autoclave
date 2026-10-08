# Planeación: sensores de temperatura del ciclo (roles Principal, Referencia y No en uso)

Estado: BORRADOR, revisión 2 (corregida con `INFORME_VERIFICACION_SPECS_PARAMETROS_SENSORES.md`). Pendiente de aprobación de Cristian. No hay código escrito ni se debe escribir hasta que este documento sea aprobado.
Ubicación prevista: `docs\mis_plans\planeacion_sensores_ciclo.md`
Depende de: `planeacion_endurecimiento_backend_parametros.md` (en particular RB-01 a RB-04 y el servicio único de RB-08).
Fuente de los hechos: `INFORME_OPCIONES_PARAMETROS_SENSORES.md` (secciones D, E y G) e `INFORME_VERIFICACION_SPECS_PARAMETROS_SENSORES.md` (secciones D, E, F, G e I) y el diseño aprobado (imágenes `opciones_sensor_comparativo.png`). Las referencias `archivo:línea` provienen del informe y deben verificarse al implementar.
Norma de referencia: IEC 62304 Clase C, ISO 14971.

---

## 1. Propósito y alcance

Define el modelo de datos, las reglas y el efecto en el ciclo de la asignación de roles a los sensores de temperatura, por programa. Es la segunda de tres especificaciones; la tercera (`planeacion_opciones_parametros_ciclo.md`) cubre las pantallas QML.

Hallazgos que cubre: OPC-06, OPC-07, OPC-08, OPC-09, OPC-13, OPC-14 (parte de sensores), OPC-20, OPC-21, OPC-29, OPC-31, OPC-32 y OPC-33.
Hallazgos relacionados que NO cubre y que Cristian debe priorizar aparte: OPC-24 (flujo de FALLA) y OPC-25 (interlock de puertas con sensor `None`).
Fuera de alcance: interfaz gráfica, calibración de sensores, "Entradas exhibidas" de la rama, sensores de chaqueta y drenaje, sensores de presión.

---

## 2. Decisiones adoptadas

Tomadas de las respuestas de Cristian y de las recomendaciones aceptadas. Si alguna es incorrecta, corregir antes de aprobar.

- S-1. El sensor Principal es el decisor del ciclo: control de vapor en CALENTAMIENTO y ESTERILIZACION, las cuatro fallas de temperatura de esterilización, la saturación final de calentamiento y la temperatura que imprime el ticket. Por omisión el Principal es el sensor de cámara (`temp_camara`), coherente con el comportamiento actual y con la indicación de que el control de vapor se hace con el sensor de cámara. No existe una sonda de carga separada.
- S-2. Reglas de asignación: exactamente 1 Principal, de 0 a 2 Referencias, el resto No en uso.
- S-3. Sensores elegibles: tres, a saber `temp_camara`, `temp_2_camara` y `temp_ref`. Cualquiera puede tomar cualquier rol, incluido Principal. Chaqueta y drenaje no son elegibles.
- S-4. La asignación es por programa, no por fase. Se guarda en el JSON del programa de usuario.
- S-5. Pueden cambiarla `biomedico`, `tecnico` e `ingeniero`; no `admin` ni `operador`. Solo en PREPARACION o PREPARADO (D-1 y D-2 de la especificación 1).
- S-6. La asignación se guarda como un conjunto completo, con botón Guardar y validación de todo el conjunto. No se guarda por clic. Al asignar un nuevo Principal desde la interfaz, el anterior pasa a No en uso (comportamiento de la interfaz; el backend solo valida el resultado final).
- S-7. La rama `feature/roles-sensor-temperatura` no se integra: se rehace sobre `dev` tomándola como referencia (sección 7).
- S-8. La vigilancia de `SENSOR_AUSENTE`, el interlock de puertas y la apertura automática siguen usando siempre `temp_camara`, aunque el Principal sea otro sensor. ADVERTENCIA (OPC-25): hoy el interlock de puertas omite la verificación y permite abrir si `temp_camara` o `pres_camara` es `None` (`ser_puertas.py:139-157`). S-8 mantiene el comportamiento actual; no lo mejora, y por eso no debe leerse como una garantía de seguridad. Su corrección se trata aparte, con prioridad alta.
- S-9. Un sensor "conectado" es el que está declarado por la instalación Y tiene lectura válida. La declaración sale del perfil de instalación (`installation_profile.json`, clase de equipo) ya leído por el backend; los YAML de `config/instances` y `config/models` hoy no los lee ningún código (OPC-31) y quedan fuera hasta que se corrijan (pregunta C-6). Un sensor declarado sin lectura se muestra como "Sin señal" y solo admite No en uso.
- S-10. Los sensores que se muestran en la pantalla de ciclo son los que están en uso: el Principal y las Referencias. Esto implementa "solo los críticos" sin una segunda configuración (ver pregunta C-2).

Nombres visibles PROVISIONALES (a confirmar con las posiciones físicas, pregunta C-4): `temp_camara` = "Cámara 1", `temp_2_camara` = "Cámara 2", `temp_ref` = "Referencia". Como "Referencia" es también un rol, se recomienda renombrar la sonda cuando se confirme su posición física.

---

## 3. Estado actual relevante (resumen verificado en el informe)

- `dev` no tiene modelo de roles. El campo `cycle_temperature_sensors` (`{"1": "temp_camara", "2": "temp_ref"}`) existe en los cinco JSON pero ningún código lo lee.
- Instalación actual: `installation_profile.json` declara `equipment_class = "piso"`, es decir `has_liquid_sensor = False`; solo `mesa_b_lab` y `piso_lab` lo tienen. Con esa instalación `temp_2_camara` no existe.
- Control de vapor y fallas: `temp_camara` (`calentamiento.py:223, 237`; `esterilizacion.py:190, 196-214`). F0: `temp_camara`, o el mínimo entre `temp_camara` y `temp_2_camara` si el equipo tiene sensor de líquidos (`control_loop.py:198-230`). Sensor crítico: `_SENSORES_TEMP_CRITICOS = ["temp_camara"]` (`ciclo.py:32`); con lectura `None` en cualquier tick se emite `SENSOR_AUSENTE` sin debounce. Tratamiento real (OPC-24): alarma de tipo EMERGENCIA con `recoverable=False`, pero el resultado es `FALLO` y el estado global pasa a FALLA; `RESET_FALLA` vuelve a PREPARACION y vacía TODAS las alarmas, incluidas las no recuperables (`state_machine.py:106-124`, `falla.py:33-36`). Ningún código lleva el estado global a EMERGENCIA. Orden del tick (verificado): la vigilancia (`ciclo.py:440-460`) se ejecuta antes de `fase.update()` (`:474-475`) y después de refrescar las lecturas; no existe prueba que lo verifique.
- `temp_ref` se lee, se publica en `/status`, se grafica y se guarda en `lecturas_grafica` (no en `lecturas`), pero no participa en control, fallas, F0, puertas ni ticket. Se revisa en `verificar_sensores` de PREPARACION y PREPARADO.
- Sensores: `EstadoAutoclave.map_temp` fijo (`status.py:12-19`): `temp_camara` (canal 0), `temp_2_camara` (1), `temp_ref` (2), `temp_chaqueta` (3), `temp_drenaje_cam` (4), `temp_drenaje` (5). Un ADC en 0 o mayor o igual a 4095 se convierte en `None` (`converters.py:169-174`).
- Configuración: `io_enabled` del YAML de instancia y `io_contract` de los modelos listan sensores pero ningún código Python los lee (OPC-31); sus nombres difieren de `map_temp` (`temp_referencia`/`temp_ref`, `temp_drenaje_camara`/`temp_drenaje_cam`, `temp_camara_2`/`temp_2_camara`), omiten `temp_chaqueta` y `temp_2_camara` en la instancia, y `solids_liquids.yaml:10-11` tiene una indentación incorrecta. `has_liquid_sensor` sale de la clase de equipo del perfil de instalación (`equipment.py`) y solo se consume en `control_loop.py:224`. En la UI y la documentación los nombres son "Temp cámara", "Temp referencia" y "Segunda sonda de temperatura de la cámara"; la posición física de las tres sondas NO consta en ningún archivo del repositorio.
- Alarma de sensor: `verificar_sensores` (`preparacion.py:102-140`, `preparado.py:248-260`) dispara `ERROR_AI_<SENSOR>` solo si la lectura es exactamente `0`; un sensor desconectado se lee como `None`, así que la alarma no se dispara (OPC-09). Además, con `None` las comparaciones de banda lanzan `TypeError` en cada tick de PREPARACION y PREPARADO (`control_banda.py:18-25`, `preparado.py:143`, `preparacion.py:223`; `ControlLoop.run` solo registra un aviso y corta el tick: sin F0, registro ni buzzer) (OPC-29, inferencia de lectura).
- F0 no se persiste: no hay columna ni campo en `/status`; solo se imprime en el pie del ticket y se escribe en el log (OPC-33). F0 solo acumula en CALENTAMIENTO, ESTABILIZACION y ESTERILIZACION y con `globals.F0` verdadero; con `temp_camara` `None` el intervalo se pierde. La fórmula usa 121.1 °C y z = 10 fijos (`letalidad.py:4-11`).
- La rama modela principal, referencia y no en uso con otra semántica: la Referencia es la sonda de control del vapor, máximo 1 referencia, Principal opcional con caída a `temp_camara`, guardado por clic, sin auditoría ni permisos.

---

## 4. Modelo

### 4.1 Catálogo de sensores

Módulo único en código (nombre propuesto `catalogo_sensores`) con, por sensor: identificador interno, canal de `map_temp`, nombre visible (provisional), tipo físico (`camara` o `referencia`) y su correspondencia con la configuración de instalación. Corrige de una vez la divergencia de nombres con los YAML mediante un mapeo explícito y corrige la indentación de `solids_liquids.yaml`.

### 4.2 Formato en el JSON del programa

```
"cycle_temperature_sensors": {
  "temp_camara": "principal",
  "temp_2_camara": "no_en_uso",
  "temp_ref": "no_en_uso"
}
```

Valores permitidos: `principal`, `referencia`, `no_en_uso`. Es el formato de la rama, así que sus conceptos son reutilizables. Una clave ausente equivale a `no_en_uso`.

Migración perezosa: un programa que tenga el formato antiguo (`{"1": ..., "2": ...}`) o no tenga el campo se interpreta como `temp_camara` Principal y el resto No en uso, que es el comportamiento real de hoy. El archivo no se reescribe hasta el primer guardado explícito de la asignación, y la interpretación por omisión se registra como advertencia.

### 4.3 Invariantes (validadas en el backend)

1. Exactamente un sensor con rol `principal`.
2. Como máximo dos sensores con rol `referencia`.
3. Todo sensor de la asignación pertenece al catálogo y es elegible (S-3).
4. Todo sensor con rol `principal` o `referencia` está declarado por la instalación y tiene lectura válida en el momento de guardar (S-9).
5. Rol dentro de {`principal`, `referencia`, `no_en_uso`}.

### 4.4 Resolución en tiempo de ejecución

El Principal siempre está definido. Si el JSON de un programa viola las invariantes 1 a 3 (cero o dos principales, sensor desconocido), el programa se considera no ejecutable: el inicio de ciclo se bloquea con el código `ASIGNACION_SENSORES_INVALIDA`. No se cae en silencio a `temp_camara`, a diferencia de la rama.

---

## 5. Requisitos

### RS-01. Catálogo, disponibilidad y estados (OPC-08)

1. Estados por sensor: `disponible` (declarado y con lectura), `sin_senal` (declarado, lectura `None`), `no_instalado` (no declarado por la instalación).
2. Nueva ruta de solo lectura, nombre propuesto `GET /cycle/sensors?programa=N`, que devuelve por sensor: identificador, nombre visible, tipo, estado, lectura actual y rol asignado en ese programa.
3. Los sensores `no_instalado` no se listan, salvo que el programa tenga un rol activo (principal o referencia) asignado a uno de ellos: en ese caso se listan marcados como no disponibles y obligan a reasignar antes de poder guardar y antes de iniciar un ciclo.
4. La declaración sale del perfil de instalación (clase de equipo, `EquipmentCapabilities`), que el backend ya lee, combinada con la lectura en vivo; no de una lista fija ni de los YAML (que ningún código lee, OPC-31). Con la clase `piso` el catálogo declara `temp_camara` y `temp_ref`; con `mesa_b_lab` o `piso_lab`, además `temp_2_camara`. Cristian confirma esta correspondencia (pregunta C-6). Los YAML se corrigen o se retiran en un cambio aparte.

### RS-02. Escritura de la asignación (servicio único de la especificación 1)

1. Una sola ruta de escritura, nombre propuesto `PUT /cycle/sensor-roles`, que recibe el conjunto completo de la asignación de un programa (todo o nada), más `asignacion_anterior_esperada` para el control de concurrencia.
2. Pasa por el mismo flujo de RB-01 a RB-06: bloqueo por estado, identidad y rol, auditoría en la misma operación, escritura atómica, respuesta 409 si la asignación anterior no coincide.
3. Auditoría: `accion = 'ROLES_SENSOR'`, `param = 'cycle_temperature_sensors'`, `valor_anterior` y `valor_nuevo` con el JSON de la asignación serializado de forma canónica (orden de claves fijo).
4. Códigos de error nuevos: `ASIGNACION_INVALIDA` (422, con la regla violada en el cuerpo) y `SENSOR_NO_DISPONIBLE` (422).
5. Solo se persisten programas de usuario; los perfiles de fábrica son inmutables (D-7 de la especificación 1).

### RS-03. El ciclo usa el Principal (OPC-06)

1. Resolución central de sensores en `BaseFase` (`_temp_principal()` y, si aplica, `_temp_referencias()`), a partir de la asignación del programa cargado al iniciar el ciclo.
2. Con el Principal se controlan el vapor y las fallas de temperatura en ESTERILIZACION, la saturación final de CALENTAMIENTO y la temperatura del ticket. Se sustituyen los usos directos de `temp_camara` en esas rutas (`calentamiento.py:223, 237`, `esterilizacion.py:190, 196-214`, ticket en `cycle_logger.py:379`).
3. Las Referencias no gobiernan el vapor (S-1). Participan en F0 (RS-04, sujeto a C-1) y en la vigilancia de RS-05, y se registran (RS-08).
4. La asignación se toma como una instantánea al iniciar el ciclo: un cambio posterior no afecta a un ciclo en curso (queda bloqueado por RB-01).

### RS-04. Base de F0 (OPC-20, SUJETO A LA DECISIÓN C-1)

Hoy el F0 de equipos con sensor de líquidos acumula contra el mínimo entre `temp_camara` y `temp_2_camara`, es decir, contra el punto más frío. Con un único Principal (modelo de la rama) esa protección se pierde. Hasta que Cristian apruebe C-1, la implementación de esta parte no debe iniciarse.

### RS-05. Sensores ausentes durante el ciclo (OPC-07)

1. La vigilancia de `SENSOR_AUSENTE` cubre siempre `temp_camara` (S-8) y además todo sensor con rol Principal o Referencia en el ciclo en curso. Una lectura `None` en cualquiera de ellos dispara `SENSOR_AUSENTE` con el mismo tratamiento que hoy (alarma tipo EMERGENCIA, resultado FALLO, estado global FALLA). Esta especificación NO cambia ese flujo: su revisión (qué significa "no recuperable" frente a `RESET_FALLA`) es el hallazgo OPC-24 y se trata aparte.
2. Verificado: la vigilancia se ejecuta antes de `fase.update()` en cada tick. Falta la prueba: se exige una que compruebe que, con `None` en el Principal, la fase no se ejecuta. Mientras el Principal esté vigilado, las ramas `None` de las fases no se alcanzan (CALENTAMIENTO sin inicializar y ESTERILIZACION quedarían en `EN_CURSO` indefinido si se alcanzaran).
3. Fallas fuera de rango plausible y deriva entre sensores no existen hoy y quedan fuera de esta especificación; se registra como mejora futura.

### RS-06. Verificación al iniciar el ciclo

Antes de la transición a CICLO se valida la asignación del programa y la lectura de todos los sensores en uso. Si falla, el ciclo no inicia y la interfaz recibe el motivo (`ASIGNACION_SENSORES_INVALIDA` o `SENSOR_NO_DISPONIBLE`).

### RS-07. Puertas y apertura automática

Permanecen en `temp_camara` (S-8) y así se documenta en el código, porque la temperatura mostrada (Principal) puede diferir de la que decide la apertura (OPC-21). Sin cambio de comportamiento; el defecto del interlock con `None` (OPC-25) queda fuera de esta especificación.

### RS-08. Registro y trazabilidad (OPC-32, OPC-33)

1. Hechos verificados: `lecturas` solo tiene `temp_camara` y `pres_camara`; `lecturas_grafica` tiene `temp_camara`, `temp_ref` y `pres_camara`; `ciclos` no guarda el número de programa ni F0; el ticket imprime `temp_camara` en todas las filas y las fases DESCOMPRESION y SECADO no tienen código ni filas periódicas.
2. El registro de cada ciclo guarda la asignación de sensores vigente al inicio como columna nueva de `ciclos` (JSON canónico), de modo que un reporte posterior sepa qué sensor fue el Principal. Las rutas de reporte devuelven la fila completa de `ciclos`, así que la columna nueva aparecerá en `/cycle/history/{id}/readings` y `/ticket`; Claude Code verifica que no rompa a los consumidores.
3. Se guarda también el F0 final del ciclo y el número de programa en `ciclos` (recomendación aceptada, pregunta C-7), con migración aditiva según el patrón de `_migrate()`.
4. Las lecturas del Principal se registran en `lecturas` (columna nueva, nombre propuesto `temp_principal`) y las lecturas gráficas incluyen `temp_2_camara` cuando existe. Claude Code propone el diseño exacto y la compatibilidad con los reportes.
5. El ticket usa la temperatura del Principal en sus filas. Cualquier cambio visible del formato (por ejemplo, identificar el sensor Principal) requiere aprobación de Cristian.

### RS-09. Alarma de sensor desconectado fuera de ciclo (OPC-09)

`verificar_sensores` debe tratar `None` como sin señal, no solo `0`, y limitarse a los sensores declarados por la instalación (`temp_chaqueta` hoy se revisa sin figurar en ningún YAML). Mantiene el tipo de alarma actual (`ERROR_AI_<SENSOR>`, tipo ALERTA). Se corrige además la excepción por `None` en las comparaciones de banda de PREPARACION y PREPARADO (OPC-29): con lectura o parámetro `None` debe producirse una alarma y no un `TypeError` en cada tick (pregunta cerrada por recomendación).

### RS-10. Permisos (OPC-14, parte de sensores)

La verificación de rol de RB-02 aplica también a la asignación. La calibración de sensores hoy permite `admin` y `tecnico` y excluye `biomedico` e `ingeniero` (`calibracion_sensor.py:37`); su alineación es la pregunta C-5.

---

## 6. Reglas de interfaz que dependen del backend (para la especificación 3)

- El segmento del sensor Principal tiene deshabilitadas las otras dos opciones; para cambiar de Principal se asigna Principal a otro sensor y el anterior pasa a No en uso.
- La opción Referencia se deshabilita en los demás sensores cuando ya hay dos.
- Un sensor `sin_senal` solo muestra habilitado No en uso.
- Guardar se habilita solo con un conjunto válido y distinto del guardado; la validación final es siempre del backend.
- Contadores Principal 1/1, Referencia n/2 y No en uso.
- Mensajes de error por código en `es.json`.

---

## 7. La rama `feature/roles-sensor-temperatura`

Decisión: no se integra. Está 30 commits por detrás de `dev`, con conflictos previsibles en `cycle_manager.py`, `admin_menu.py`, `main_window.py`, `server.py` y los cinco JSON, y su modelo difiere del aprobado.

Se reutiliza como referencia, sin merge: el formato `sensor → rol` del JSON, el esquema de resolución en `BaseFase` (`_temp_principal`, `_temp_referencia`, `_temp_control`), la idea de snapshot de F0 y las siete suites de pruebas relacionadas, adaptándolas al modelo nuevo.

Se descarta de la rama: el guardado por clic, el máximo de una referencia, el Principal opcional con caída a `temp_camara`, la Referencia como sonda de control del vapor, el uso de `localhost` y la ausencia de auditoría, permisos y bloqueo por estado.

---

## 8. Pruebas requeridas

- Invariantes: cero Principal, dos Principales, tres Referencias, rol inválido, sensor desconocido, sensor `no_instalado` o `sin_senal` como Principal o Referencia.
- Escritura: bloqueo por estado, rol, 409 por asignación desfasada, auditoría `ROLES_SENSOR` con valores anterior y nuevo, escritura atómica, todo-o-nada.
- Control: una fase simulada con Principal = `temp_2_camara` controla y evalúa fallas con ese sensor.
- Vigilancia: `None` en cada sensor en uso dispara `SENSOR_AUSENTE`; con `temp_camara` en No en uso sigue vigilándose; la vigilancia precede al `run()` de la fase.
- Inicio de ciclo: bloqueado con asignación inválida y con sensor sin señal.
- Trazabilidad: instantánea de la asignación en el registro del ciclo; `lecturas` con los sensores en uso.
- Alarma fuera de ciclo con `None`.
- Migración perezosa: programa con formato antiguo se interpreta con la asignación por omisión sin reescribir el archivo.
- Regresión: puertas y apertura automática siguen en `temp_camara`.

---

## 9. Riesgos y hallazgos

- OPC-20 (alta, nuevo). F0 en ciclos de líquidos: el mínimo entre dos sondas de cámara protege contra el punto más frío; el modelo de un solo Principal lo elimina. Requiere decisión C-1 y entrada en el análisis de riesgos (ISO 14971).
- OPC-21 (media, nuevo). La temperatura mostrada y registrada como Principal puede diferir de `temp_camara`, que sigue decidiendo puertas, apertura automática y `SENSOR_AUSENTE` (S-8). Es deliberado, pero debe quedar documentado y visible en el registro.
- OPC-24 (alta, fuera de esta especificación). "No recuperable" no se cumple: `RESET_FALLA` vacía todas las alarmas, incluidas las de `recoverable=False`. Afecta a `SENSOR_AUSENTE` y a toda alarma de emergencia.
- OPC-25 (alta, fuera de esta especificación). El interlock de puertas permite abrir con `temp_camara` o `pres_camara` en `None`. Recomendación: corrección aparte y pronta (negar la apertura con lectura ausente), por el mismo criterio que OPC-01.
- Nombre "Referencia": sensor y rol comparten nombre; riesgo de confusión del operador (sección 2).
- Los nombres y posiciones físicas de los sensores son provisionales hasta la respuesta C-4; el repositorio solo los describe como "Segunda sonda de temperatura de la cámara" y "Temperatura de referencia".

---

## 10. Criterios de aceptación

1. Todo programa ejecutable tiene exactamente un Principal y como máximo dos Referencias, validado en el backend.
2. Control de vapor, fallas de temperatura, saturación final y temperatura del ticket usan el Principal.
3. Una lectura `None` de cualquier sensor en uso, o de `temp_camara`, detiene el ciclo con `SENSOR_AUSENTE`.
4. Un ciclo no inicia con asignación inválida ni con sensores en uso sin lectura.
5. Todo cambio de asignación queda auditado por el backend con asignación anterior y nueva.
6. El registro de cada ciclo guarda la asignación usada.
7. Puertas y apertura automática siguen en `temp_camara`.
8. La decisión C-1 está aprobada y reflejada antes de tocar F0.

---

## 11. Preguntas abiertas (responder por número; sin respuesta se adopta la recomendación)

- C-1 (BLOQUEANTE para F0). Base de F0 con varios sensores en uso. Hechos: hoy F0 usa `temp_camara`, o el mínimo entre `temp_camara` y `temp_2_camara` solo si el equipo tiene sensor de líquidos; la instalación actual (`piso`) no lo tiene. Recomendación: el mínimo entre el Principal y las Referencias en uso, que conserva el comportamiento conservador de los equipos con sensor de líquidos. Alternativas: solo el Principal (modelo de la rama, pierde la protección) o solo sensores de tipo cámara. Debe respaldarla el análisis de riesgos.
- C-2. Pantalla de ciclo: mostrar el Principal y las Referencias, sin configuración aparte de "sensores visibles". Recomendación: sí.
- C-3. Ausencia de un sensor de Referencia durante el ciclo. Recomendación: mismo tratamiento que el Principal (`SENSOR_AUSENTE` con el flujo actual de FALLA). Alternativa: alerta sin detener el ciclo.
- C-4. Nombres y posiciones físicas reales de los sensores. Dato que debe aportar Cristian (hoy provisionales: Cámara 1, Cámara 2, Referencia).
- C-5. Calibración de sensores: alinear los roles permitidos a biomédico, técnico e ingeniero (sin admin). Recomendación: sí, como cambio aparte.
- C-6. Fuente de la declaración de sensores (OPC-31): el perfil de instalación (clase de equipo) en lugar de los YAML. Recomendación: sí, con la correspondencia de RS-01.4.
- C-7. Guardar F0 final y número de programa en `ciclos` junto con la asignación de sensores. Recomendación: sí.
- C-8. Prioridad de OPC-24 y OPC-25 (flujo de FALLA e interlock de puertas con `None`): fuera de esta especificación; recomendación: abrir una especificación o corrección aparte de seguridad de puertas y alarmas, antes de liberar la interfaz de configuración.

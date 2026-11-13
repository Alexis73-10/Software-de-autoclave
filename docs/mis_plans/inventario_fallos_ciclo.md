# Inventario de fallos de ciclo: qué muestra el equipo y qué debería decir

Fecha: 6-nov-2026 · Base: `dev` en `41992c81` (1.0.0-alpha.17) · Para revisión de Cristian

Origen: el 5-nov falló la válvula de aire atmosférico de cámara. En el secado modo 3, la cámara no salió del vacío y el ciclo terminó en CIC-06. El motivo era correcto («no se alcanzó la presión alta de aire a tiempo»), pero la acción recomendada mandaba a revisar la bomba de vacío. Además, el estado seguro no pudo romper el vacío y la puerta se abrió a mano.

Cómo se arma hoy el mensaje de un fallo de ciclo:

- Título y acción: salen de la alarma (`state_machine/alarms/catalogo.py` y `i18n/<idioma>.json`, clave `alarmas.<código>`). Hay **una sola acción por alarma**.
- Descripción: en CIC-01 a CIC-06 es el motivo que deja la fase (`core/runtime/motivos_fase.py`, textos en `motivos_fase.<código>`). Las demás alarmas tienen descripción fija con valores.
- Estado de la carga: todo resultado distinto de COMPLETADO imprime «*** CARGA NO ESTÉRIL ***» en el ticket (`ticket_formatter.py` ~449). En pantalla, `PanelFinCiclo.qml` muestra «CARGA NO ESTÉRIL».
- Precedente útil: CIC-10 ya tiene una segunda acción (`accion_sin_presion`) que se elige según el caso. El mismo mecanismo sirve para elegir la acción según el motivo.

Cómo revisar este documento: en cada fallo, corrige la «Acción propuesta» y las «Causas probables» con tu criterio de campo. Si estás de acuerdo, déjalo como está. Lo marcado `PREGUNTA` necesita tu respuesta.

---

## 1. Hallazgos

**FAL-01 (ALTA): acción única por fase, que manda al componente equivocado.**
CIC-02, CIC-04 y CIC-06 recomiendan la misma acción para fallos con causas físicas opuestas. Ejemplos: el caso del 5-nov; un prevacío que no llega a la presión alta de vapor y recibe «revise la bomba»; una esterilización con temperatura **alta** que recibe «revise el suministro de vapor». El técnico pierde tiempo y puede cambiar una pieza buena.
Propuesta: acción por código de motivo (`motivos_fase.<código>.accion` en es/en), usando la acción de la alarma como respaldo si el motivo no tiene una propia. Las alarmas con descripción fija se quedan como están.

**FAL-02 (ALTA, seguridad del paciente): estado de la carga cuando falla el secado.**
Hoy un fallo de secado imprime «CARGA NO ESTÉRIL». Tu decisión (6-nov): la carga es estéril, porque la exposición terminó completa, pero puede salir húmeda o mojada, y eso debe decirse en pantalla y en el ticket.
Conflicto que hay que resolver antes de implementar: las guías de esterilización hospitalaria (AAMI ST79, Anexo de evaluación de humedad) tratan el paquete húmedo como comprometido. La humedad deja pasar microorganismos a través del empaque (efecto mecha). Por eso el paquete húmedo se reprocesa completo, y con dos o más paquetes húmedos la carga no se libera. Si el ticket dice solo «CARGA ESTÉRIL», el operador puede liberar paquetes húmedos.
Texto recomendado (no dice «estéril» a secas):
- Pantalla, título: «EXPOSICIÓN COMPLETA — SECADO INCOMPLETO» (color ámbar, como Observaciones; no rojo).
- Pantalla, cuerpo: «La esterilización se completó, pero el secado no terminó. La carga puede salir húmeda o mojada. No libere paquetes húmedos: reprocéselos según su procedimiento.»
- Ticket: «*** EXPOSICIÓN COMPLETA - SECADO INCOMPLETO ***» y la línea «Carga posiblemente húmeda: no libere paquetes húmedos.»
Impacto colateral (lo decides tú): hoy el resultado es FALLO y eso define el calendario del dashboard (`sin_exito`), el Bowie & Dick, el resumen de fallos, la apertura automática y la bitácora. Hace falta un resultado nuevo o una marca sobre FALLO. Ver la PREGUNTA 1.

**FAL-03 (ALTA): el estado seguro no tiene cómo romper el vacío si falla la válvula de aire atmosférico.**
`protocolo_fallo.py` (~963–970): con la cámara en vacío cierra las descompresiones y solo abre `aire_admosferico_camara`. No hay segunda vía ni alarma que diga «el vacío no se rompe». La cámara queda en vacío indefinidamente y la puerta solo se abre a mano, que es lo que pasó el 5-nov.
Propuesta: una alarma propia «La cámara no sale del vacío», que se active cuando la presión siga bajo `atm − rango` después de X s con el aire atmosférico abierto. Acción: «Revise la válvula de aire atmosférico de cámara y su filtro. No fuerce la puerta: la cámara está en vacío.» Sobre si debe existir una segunda vía (por ejemplo, aire comprimido a la cámara), ver la PREGUNTA 3.

**FAL-04 (MEDIA): tres fallos terminan sin motivo.**
El timeout de vacío bajo del prevacío (`prevacio.py` ~167), el timeout de presión alta de vapor del prevacío (~215) y el timeout de precalentamiento (`precalentamiento.py` ~60) no dejan `motivo_fallo`. En pantalla y en el ticket sale «La fase terminó en fallo; el motivo detallado aún no se registra.»
Propuesta: tres motivos nuevos con valores (ver §3).

**FAL-05 (MEDIA): el estado de la carga cuando falla la descompresión.**
CIC-05 ocurre después de la exposición, igual que el secado. Hoy dice «CARGA NO ESTÉRIL». Ver la PREGUNTA 2.

**FAL-06 (BAJA): los motivos del secado modo 3 no traen valores.**
`sec_modo3_vacio_bajo` y `sec_modo3_aire_alto` no dicen a qué presión llegó la cámara ni cuál era el objetivo. Con el valor, el técnico distingue «la válvula no abrió», donde la presión no se movió, de «abrió poco», donde se quedó corta.
Propuesta: agregar `pres` (última lectura), `pres_objetivo` y `segundos` (`timeout_pulso`).

---

## 2. Fallos de fase (CIC-01 a CIC-06): motivo por motivo

Formato: **Muestra** (título · descripción) / **Acción actual** / **Causas probables** / **Acción propuesta** / **Carga**.

### CIC-01 Precalentamiento

1. Timeout sin alcanzar la presión de chaqueta (sin motivo, FAL-04)
   - Muestra: «Fallo en precalentamiento» · «La fase terminó en fallo; el motivo detallado aún no se registra.»
   - Acción actual: «Revise el suministro de vapor de la chaqueta.»
   - Causas probables: suministro de vapor bajo o cortado, válvula de vapor de chaqueta que no abre, trampa de chaqueta pegada abierta, sensor de presión de chaqueta.
   - Motivo propuesto `pre_tiempo_limite`: «No se alcanzó la presión de chaqueta {pres_objetivo} en {minutos} min (última lectura {pres})».
   - Acción propuesta: «Revise el suministro de vapor, la válvula de vapor de chaqueta y la trampa de chaqueta.»
   - Carga: NO ESTÉRIL (no ha empezado la exposición).
2. Timeout durante el sostenimiento alargado por tramos sin datos: misma situación, causa de comunicación.
   - Acción propuesta: «Revise el cable de red y la alimentación del módulo E/S.»

### CIC-02 Prevacío

1. Timeout de vacío bajo (sin motivo, FAL-04)
   - Muestra: «Fallo en prevacío» · texto genérico.
   - Acción actual: «Revise la bomba de vacío y su agua de sello.»
   - Causas probables: bomba o agua de sello; válvula de vacío de cámara que no abre; **válvula de aire atmosférico pegada abierta** (da los mismos síntomas que la bomba); fuga por el empaque de puerta o por las descompresiones.
   - Motivo propuesto `prev_vacio_bajo`: «Pulso {pulso}: la presión no bajó a {pres_objetivo} en {minutos} min (última lectura {pres})».
   - Acción propuesta: «Revise la bomba de vacío y su agua de sello, la válvula de vacío de cámara, que la válvula de aire atmosférico cierre y el empaque de la puerta.»
   - Carga: NO ESTÉRIL.
2. Timeout de presión alta de vapor del pulso (sin motivo, FAL-04)
   - Acción actual: «Revise la bomba de vacío…» (incorrecta).
   - Causas probables: suministro de vapor, válvula de vapor de cámara que no abre, descompresión lenta con demasiado escape, sensor de presión de cámara.
   - Motivo propuesto `prev_vapor_alto`: «Pulso {pulso}: la presión no subió a {pres_objetivo} en {minutos} min (última lectura {pres})».
   - Acción propuesta: «Revise el suministro de vapor y la válvula de vapor de cámara. La bomba de vacío no interviene en este paso.»
   - Carga: NO ESTÉRIL.
3. CIC-20 (descompresión del pulso sin terminar): ya tiene alarma, texto y acción propios. Sin cambios.

### CIC-03 Calentamiento

Acción actual común: «Revise el suministro de vapor y la presión del generador.»
1. `cal_tiempo_limite`: «Tiempo límite de calentamiento: no se alcanzó el objetivo en {minutos} min»
   - Causas probables: vapor insuficiente, válvula de vapor (cámara o chaqueta según el modo), condensado sin drenar, carga muy pesada.
   - Acción propuesta: la actual, más «y el drenaje de condensado de la cámara».
2. `cal_tiempo_limite_sostenimiento`: causa de comunicación.
   - Acción propuesta: «Revise el cable de red y la alimentación del módulo E/S.»
3. `cal_no_sostuvo`: «No se logró sostener condición estable en {minutos} min»
   - Causas probables: oscilación de la regulación; en carga sólida también puede ser la **coherencia temperatura-presión** (aire en la cámara), y el texto no lo dice.
   - Motivo propuesto: distinguir por subcausa. Si fue por coherencia T–P: «Temperatura y presión no coinciden con vapor saturado (posible aire en la cámara)».
   - Acción propuesta (coherencia): «Revise la eliminación de aire: prevacío, prueba de Bowie & Dick y fugas de la cámara.»
4. CIC-15/16 en calentamiento: ya tienen acción propia. Sin cambios.
- Carga: NO ESTÉRIL en todos los casos.

### CIC-04 Esterilización

Acción actual común: «La carga NO está estéril. Revise el suministro de vapor y repita el ciclo.»
1. `est_temp_alta`
   - Causas probables: vapor sobrecalentado, chaqueta por encima de la cámara, sonda Principal.
   - Acción propuesta: «La carga NO está estéril. Revise la presión de chaqueta y la sonda Principal (calibración). Repita el ciclo.»
2. `est_temp_baja`
   - Causas probables: vapor insuficiente, condensado acumulado (trampa o drenaje de cámara), carga muy pesada.
   - Acción propuesta: «La carga NO está estéril. Revise el suministro de vapor y el drenaje de condensado de la cámara. Repita el ciclo.»
3. `est_pres_alta`
   - Causas probables: válvula de vapor de cámara pegada abierta, escape obstruido, sensor de presión.
   - Acción propuesta: «La carga NO está estéril. Revise la válvula de vapor de cámara, los escapes y el sensor de presión de cámara. Repita el ciclo.»
4. `est_pres_baja`
   - Causas probables: suministro de vapor, escape lento con demasiada fuga, empaque de puerta.
   - Acción propuesta: «La carga NO está estéril. Revise el suministro de vapor, la válvula de descompresión lenta y el empaque de la puerta. Repita el ciclo.»
5. `est_timeout_f0`
   - Acción propuesta: «La carga NO está estéril. La letalidad F0 no se alcanzó: revise la temperatura de esterilización del programa y el suministro de vapor.»
6. CIC-11 a CIC-14, CIC-17 y CIC-19: ya tienen alarma y acción propias, coherentes. Sin cambios.
- Carga: NO ESTÉRIL en todos los casos.

### CIC-05 Descompresión

`desc_tiempo_limite`: «Tiempo límite de {etapa} del modo {modo} (T=…, P=…)». Acción actual: «No abra la puerta hasta confirmar presión atmosférica. Revise las válvulas de escape.»
Acción por etapa propuesta:
- `rapida` / `lenta` / `descompresion`: «No abra la puerta hasta confirmar presión atmosférica. Revise la válvula de descompresión {rápida|lenta} y el escape.»
- `enfriamiento` (modos 4/5): «No abra la puerta. Revise el agua de enfriamiento de chaqueta y el aire comprimido de contrapresión.»
- Carga: PREGUNTA 2.

### CIC-06 Secado

Acción actual común: «Revise la bomba de vacío. La carga puede salir húmeda.»
1. `sec_sin_vacio` (modos 1/2): la presión no bajó del umbral a tiempo.
   - Causas probables: bomba o agua de sello, válvula de vacío de cámara, aire atmosférico pegada abierta, empaque de puerta.
   - Acción propuesta: «Revise la bomba de vacío y su agua de sello, la válvula de vacío de cámara y que la válvula de aire atmosférico cierre.»
2. `sec_vacio_perdido` (modos 1/2): había vacío y se perdió.
   - Causas probables: en el modo 1, fuga (aire atmosférico que no cierra, empaque, descompresiones) o bomba que se detuvo. En el modo 2 el aire atmosférico está abierto a propósito, así que puede ser una entrada de aire excesiva (válvula o restrictor).
   - Acción propuesta: «Revise el empaque de la puerta, las válvulas de aire atmosférico y de descompresión, y la bomba de vacío.»
3. `sec_termino_sin_vacio`: misma acción que el punto 1.
4. `sec_modo3_vacio_bajo`: misma acción que el punto 1; agregar valores (FAL-06).
5. `sec_modo3_aire_alto` **(caso del 5-nov)**
   - Causas probables: válvula de aire atmosférico que no abre (bobina, cableado, salida del módulo E/S), filtro de aire obstruido.
   - Motivo propuesto: «Secado modo 3: la presión no subió a {pres_objetivo} en {segundos} s con el aire atmosférico abierto (última lectura {pres})».
   - Acción propuesta: «Revise la válvula de aire atmosférico de cámara, su filtro y su salida en el módulo E/S. La bomba de vacío no interviene en este paso. La cámara puede seguir en vacío: no fuerce la puerta.»
- Carga en todos: según FAL-02 («Exposición completa — secado incompleto»).

---

## 3. Otros fallos que abortan el ciclo (revisión de texto y acción)

Muestran causa y acción coherentes; no propongo cambios: SIS-01 (paro), SUM-01 (corte eléctrico), PUE-02 (puerta abierta), PUE-03 (empaque), SEN-02, SEN-04, SEN-05, SEN-08 (sensores sin lectura), COM-02 y COM-03 (comunicación o módulo E/S), CIC-10 (estado seguro detenido, con sus dos acciones), DISCREPANCIA_SALIDAS, TARJETA_WATCHDOG, TARJETA_SALIDAS_NO_APAGADAS y TARJETA_EXPANSOR_FUERA_DE_LINEA.

Observación sobre el estado de la carga: todas imprimen «CARGA NO ESTÉRIL». Si una de ellas ocurre en DESCOMPRESION o SECADO, la exposición ya se completó. Ver la PREGUNTA 2.

---

## 4. Preguntas para Cristian

1. Sobre FAL-02: ¿aceptas el texto «EXPOSICIÓN COMPLETA — SECADO INCOMPLETO» con «no libere paquetes húmedos», en lugar de «CARGA ESTÉRIL» a secas? Y para el registro: ¿un ciclo así cuenta como **éxito con observación** (como hoy las observaciones ámbar: calendario `exito`, sin protocolo de fallo) o sigue siendo **FALLO** con una marca nueva (calendario `sin_exito`)? Recomiendo FALLO con marca: el equipo sí tuvo una falla y el protocolo de estado seguro debe seguir corriendo.
2. Sobre FAL-05: un fallo después de la exposición (descompresión, o un sensor o comunicación perdidos en DESCOMPRESION o SECADO), ¿lleva el mismo tratamiento que el secado («exposición completa»), o lo dejamos solo para CIC-06? Recomiendo solo CIC-06 por ahora. En la descompresión la cámara puede seguir presurizada y la prioridad del mensaje es «no abra la puerta».
3. Sobre FAL-03: ¿el equipo tiene otra vía física para meter aire a la cámara en vacío (por ejemplo, `aire_comprimido_camara` en los equipos que lo traen)? ¿Quieres que el estado seguro la use si el aire atmosférico no rompe el vacío en X s? ¿Y cuánto vale X (propongo 60 s)?
4. El 5-nov, mientras la cámara estuvo en vacío después del fallo, ¿qué mostraba la pantalla: «NO ABRIR», CIC-10 u otra cosa? Lo necesito para definir dónde va la alarma de FAL-03.

# Ciclos múltiples (`globals.ciclos_multiples`) — plan, 9-nov-2026

Plan previo a la tanda que conecte el parámetro `ciclos_multiples`. No hay código en este documento: faltan las decisiones de la sección 5, que son de Cristian. Hasta entonces el parámetro sigue sin efecto (su descripción en pantalla ya lo dice).

## 1. Objetivo

Poder iniciar un ciclo a continuación de otro **sin abrir la puerta entre los dos**, cuando el programa lo permita. El parámetro es 0/1 (en el JSON es `bool`, `{"value": true, "type": "bool"}`).

## 2. Estado actual (verificado en el código, 9-nov)

- `ciclos_multiples` existe en `globals` de los 6 programas de fábrica y de usuario, y vale `true` en todos. Ningún módulo del control lo lee (se comprobó por nombre en `src/`, `tests/` y `tools/`).
- Lo único que hoy **exige abrir la puerta** entre un ciclo y el siguiente es el vaciado de chaqueta: tras confirmar un ciclo COMPLETADO de carga líquida con descompresión modo 4 o 5, `CicloState._armar_vaciado_chaqueta` deja `estado.vaciado_chaqueta` en PENDIENTE, `vapor_chaqueta` y `descompresion_chaqueta` en OFF, y `PreparadoState` es el único dueño de `vapor_chaqueta` hasta ver una puerta abierta (3 ticks seguidos con DI vigente). Mientras está pendiente la chaqueta no queda lista y no se puede iniciar otro ciclo. Eso es lo que pasó el 9-nov y quedó aceptado en HAZ-VCC-01. Desde el 9-nov la pantalla lo avisa («Ciclo terminado: abra la puerta de descarga para vaciar la chaqueta»).
- Los ciclos de sólidos (modos de descompresión 0 a 3) no arman ese vaciado, así que hoy ya se puede iniciar otro ciclo sin abrir la puerta, siempre que se cumplan las condiciones normales de PREPARADO: puertas confirmadas cerradas, lazos de chaqueta, presión de cámara y drenaje en banda, sin paro, sin alarma que bloquee el inicio y cámara segura (`PreparadoState.esta_preparado`).
- Además, antes de poder confirmar un ciclo hay que esperar la «entrega de la cámara» (ENT-01..12): cámara segura con 3 tramas seguidas, más `tiempo_espera_apertura` tras COMPLETADO. Eso no cambia.

Consecuencia: el parámetro, en la práctica, sería el interruptor del vaciado de chaqueta para ciclos de líquidos 4/5. Si Cristian quiere que haga algo más, hay que decirlo en la sección 5.

## 3. Diseño propuesto (a confirmar con las decisiones de la sección 5)

Regla base: con `ciclos_multiples = 1` en el programa del ciclo que termina, un COMPLETADO confirmado **no arma** el vaciado de chaqueta. La chaqueta sigue bajo `mantener_chaqueta` y el equipo vuelve a PREPARADO sin pedir apertura de puerta. Con `ciclos_multiples = 0` todo queda como hoy (vaciado pendiente hasta abrir la puerta; aviso en pantalla).

Cambios previstos:

- `CicloState._armar_vaciado_chaqueta`: no armar si `globals.ciclos_multiples` es verdadero (falla cerrada: ausente, ilegible o no booleano se trata como 0, es decir, como hoy).
- Catálogo (`catalogo_parametros.py`): el parámetro es booleano; el 0/1 de la interfaz se muestra como interruptor. Sin límites numéricos nuevos.
- Aviso «abrir la puerta de descarga» (hecho el 9-nov): ya depende de que el vaciado esté PENDIENTE; con `ciclos_multiples = 1` no se arma, así que no aparece. No requiere cambio.
- `/status`: publicar `ciclos_multiples` del programa en curso solo si la pantalla lo necesita (por ejemplo para mostrar «ciclo encadenado» en el ticket). Sin ruta nueva.
- Trazabilidad del ciclo: dejar constancia en el ticket, el PDF, el registro y el historial de que el ciclo se inició sin apertura de puerta desde el anterior (campo `encadenado` y la línea «Ciclo encadenado: sin apertura de puerta desde el ciclo N»). Alcance a decidir (pregunta 5).
- i18n es/en: reemplazar la descripción «Sin efecto en esta versión» por la real, y agregar los textos del ticket.
- Migración: ver la pregunta del valor por defecto.

Sin cambio: entrega de la cámara y su espera, CONFIRMAR, NO ABRIR, cámara segura, protocolos de fallo, VCH-AIS, D-CHQ, cascada de chaqueta y todo lo de seguridad de la cámara.

## 4. Riesgos e impacto normativo (software Clase C, NTC-IEC 62304)

Es un cambio de comportamiento de seguridad (puerta, chaqueta, carga), por lo que lleva solicitud de cambio, riesgo, requisito y pruebas trazables. Riesgos a registrar en `docs/riesgos/registro_riesgos.md` (IDs provisionales, HAZ-CMU-xx):

- **CMU-01, chaqueta sin vaciar.** Hoy el vaciado se hace con la puerta abierta, con un tiempo fijo de 30 s y con pulsos de `descompresion_chaqueta`. Omitirlo deja la chaqueta cargada con el agua o el vapor del ciclo de líquidos anterior; el ciclo siguiente parte de esa chaqueta. Hay que saber por qué existe el vaciado (¿evitar que la chaqueta quede presurizada o caliente al descargar?) para decidir si se puede omitir solo cuando no se abre la puerta.
- **CMU-02, carga reprocesada.** Si no se abre la puerta, la carga del ciclo anterior sigue dentro. Un ciclo nuevo sobre una carga ya esterilizada es coherente solo para ciertos usos (por ejemplo, un ciclo de prueba o una segunda exposición); para otros, es un error de operación. Hay que impedir que el operador crea que cargó material nuevo.
- **CMU-03, trazabilidad.** Dos ciclos consecutivos sobre la misma carga deben quedar enlazados en el registro (ticket, base, respaldo, PDF, correo, historial), con el número del ciclo anterior.
- **CMU-04, valor por defecto.** Hoy vale `true` en todos los programas. Activarlo cambiaría el comportamiento de todos los programas de golpe, incluidos los ya instalados.
- **CMU-05, encadenar tras un ciclo no exitoso.** Un FALLO o una CANCELACIÓN dejan la carga como NO ESTÉRIL: encadenar otro ciclo sin abrir la puerta no debería permitirse sin una decisión explícita.

Verificación prevista: pruebas unitarias del armado del vaciado con y sin el parámetro (incluida la falla cerrada), pruebas de migración del valor por defecto, pruebas del ticket y del registro, y un bloque de banco (ciclo de líquidos 4/5 con `ciclos_multiples` en 1 y en 0, y un segundo ciclo inmediato). Definición de terminado: suite completa en verde, riesgos registrados y aceptados por Cristian, trazabilidad REQ actualizada y banco ejecutado.

## 5. Decisiones pendientes de Cristian (no se asume nada; el código espera estas respuestas)

1. **¿Qué cuenta como «sin abrir puerta»?** ¿Solo se quiere omitir el vaciado de chaqueta de los líquidos 4/5 (lo único que hoy lo impide), o hay otra condición entre ciclos que también debe relajarse, como la espera de apertura o la entrega de la cámara?
2. **¿El parámetro se lee del programa que termina o del que va a iniciar?** Propuesta: del que termina (decide si se arma el vaciado). Si debe decidir el siguiente, el diseño cambia.
3. **¿Solo tras un ciclo COMPLETADO?** Propuesta: sí; tras FALLO o CANCELADO no se encadena (CMU-05).
4. **Valor por defecto.** Hoy `true` en todos. Propuesta: migrar a `false` (0) en los 6 programas de fábrica y en los de usuario, con auditoría y `.bak`, y activarlo programa por programa. Si debe quedar en 1, hay que aceptar el riesgo CMU-04.
5. **¿Hay un máximo de ciclos seguidos sin abrir la puerta?** ¿Cuál?
6. **¿Qué programas pueden encadenarse con cuáles?** Por ejemplo, ¿un Bowie & Dick seguido de un ciclo de instrumental, o repetir el mismo programa?
7. **Vaciado omitido: ¿se hace al final de la cadena?** Es decir, al abrir por fin la puerta tras el último ciclo, ¿debe ejecutarse el vaciado de chaqueta pendiente? Propuesta: sí, se arma en el último ciclo de la cadena y no en los intermedios; hay que definir cómo sabe el equipo cuál es el último (el operador no lo declara hoy).
8. **Trazabilidad en el ticket y el registro.** ¿Basta la línea «Ciclo encadenado» o se quiere un identificador de carga común a la cadena?
9. **Permisos.** ¿Quién puede cambiar `ciclos_multiples` (hoy, el rol que edita parámetros del ciclo)?

## 6. Etapas de la tanda (cuando estén las decisiones)

1. Registrar solicitud de cambio, requisito y riesgos CMU-01..05; correr la skill de auditoría IEC 62304 sobre el cambio.
2. Pruebas primero (armado del vaciado con y sin parámetro, falla cerrada, migración, ticket).
3. Código: `_armar_vaciado_chaqueta`, migración del valor por defecto, textos es/en, ticket y registro.
4. Revisión de seguridad independiente y suite completa.
5. Bloque de banco y aceptación de riesgos por Cristian.
6. Entrega (`tools/entrega/compilar_entrega.py` desde `dev` limpio) solo con todo lo anterior cerrado.

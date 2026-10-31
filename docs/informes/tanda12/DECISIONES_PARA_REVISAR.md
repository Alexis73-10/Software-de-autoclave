# Tanda 12: decisiones para revisar

Este documento reúne las DECISIONES SIN CONFIRMAR y las PREGUNTAS PARA CRISTIAN de la tanda 12 (24-oct). Cada una tiene su detalle en el informe de su etapa (`J12_*`, `P12_*`, `E12_*`, `L12_*`, `V12_*`). Primero van las que más pueden afectar a los ciclos del lunes 26-oct.

## Urgentes para el banco del lunes

1. **Techo frente a la histéresis de salida de RECUPERACION a 134 °C.** Lo encontró L12, lo confirmaron J12 y E12 y V12 lo registró como SAF-04. Con `brecha_segura_temperatura` 1,0 más 0,3 de histéresis, para pasar a PWM hacen falta 135,3 °C. Pero `Tsat(P_control_max)` vale 135,0 °C con `presion_add_esterilizacion` 9 y 135,2 °C con 11. Con vapor saturado, la fase nunca sale de RECUPERACION.
   - **DECISIÓN SIN CONFIRMAR (sesión principal, aplicada por E12):** se agregó una histéresis de 2 kPa al corte por techo en RECUPERACION (`_HIST_TECHO_KPA`). La válvula se apaga al llegar al techo y no vuelve a abrir hasta que la presión baja 2 kPa. Así no conmuta en cada tick. Esta histéresis solo reduce el vapor.
   - **PREGUNTA:** ¿se acepta así? Las alternativas son subir `presion_add_esterilizacion` a 12 o más en los programas de 134, bajar la brecha a 134 °C, o permitir la salida a PWM cerca del techo.
2. **Los programas de usuario del equipo conservan `brecha_segura_temperatura` 0,3.** J12 hizo la pregunta 2 y el ensayo G → H lo confirmó. La actualización conserva `cycles/user` del sitio, y la migración solo agrega las claves que faltan y corrige `presion_add` > 30. **DECISIÓN SIN CONFIRMAR (sesión principal):** no se migra la brecha automáticamente, porque así no se toca un ajuste de usuario y porque con 0,3 el control PWM sí se alcanza (ver el punto 1). La hoja de banco (bloque T12) dice cómo cambiarla a mano si se quiere probar C-07.1. **PREGUNTA:** ¿se migra a 1,0 en una próxima compilación?
3. **Referencia más fría que el Principal en CALENTAMIENTO (P12, pregunta 1).** Con C-01, el Principal queda apenas 0,1 a 0,2 K sobre T_obj. Una Referencia que lea de forma sostenida un poco menos nunca entra en consigna, y el ciclo falla con `cal_no_sostuvo`. **PREGUNTA:** ¿se quiere una tolerancia para las Referencias en la ventana?
4. **La marca NO CONFORME no se ve en la pantalla final (V12 SAF-02, E12 pregunta 3).** Hoy la marca va al ticket y al registro, y la alarma SEN-11 es no bloqueante. El resultado sigue siendo COMPLETADO. **PREGUNTA:** ¿se agrega un resultado o una bandera visible en la pantalla y el historial, se pide un reconocimiento al confirmar, o se pone «CARGA NO ESTÉRIL» en el ticket?

## Sesión principal
- **SIS-06 en `alarms/catalogo.py` lo agregó J12**, como excepción a la regla 6 de propiedad de archivos. Los códigos CIC-12, CIC-13, CIC-14 y SEN-11 se asignaron a E12 antes de lanzar las etapas, para evitar choques. La unión quedó sin conflictos.
- **J12 se unió en dos partes.** Primero hasta 8354776 y después `c059dd3`, con la brecha 1.0, una vez unida E12. La brecha 1.0 sin el techo en RECUPERACION rompía 53 ensayos de simulador.
- **C-13.7:** la sesión principal pasó `exposicion_restante_s` a `armar_progreso` en `GET /cycle/current/progress` (`server.py`, sin dueño en la tabla), con prueba.
- **Correcciones de V12 que no eran bloqueantes, aplicadas igual:** SAF-01, SAF-03, SAF-06, SAF-07 y SAF-08 (ver `V12_revision_seguridad.md`).

## J12 (parámetros, validación y chaqueta)
1. Después de auditar la migración, el JSON de usuario migrado se reescribe y la versión anterior queda en `.bak`. Así la migración no se repite en cada arranque. V12 agregó que un reintento no duplica la auditoría y que los programas dañados se omiten.
2. Un programa sin los datos para calcular la consigna controla la chaqueta con `presion_chaqueta ± rango`, como antes.
3. La advertencia del suministro salta con `> 350`. Exactamente 350 (300 + 50 de fábrica) no avisa.
4. Al guardar, PATCH devuelve solo las advertencias del parámetro editado. El log al iniciar el ciclo las registra todas.
5. La auditoría usa el evento `param_ciclo_cambio` con usuario `sistema`.
6. SIS-06 queda activo hasta reiniciar o reconocer. Como el programa se reescribe (decisión 1), no reaparece en el siguiente arranque.
7. Los valores por defecto del hospital (`cycles/defecto`) se migran solo en memoria, sin auditoría ni aviso.

## P12 (CALENTAMIENTO)
1. Con aire en la cámara, la fase pasa a sostenimiento pero queda fuera de banda: la ventana no arranca y el vapor queda en 0. Termina en `cal_no_sostuvo` si no se corrige.
2. Un `tipo_carga` ausente o desconocido se trata como sólido y se exige la coherencia. Es lo seguro.
3. Si Tsat(P) no se puede calcular, la lectura se toma como incoherente.
- PREGUNTA 2: la ventana puede oscilar en el borde Psat − 2 por la fuga del escape lento. Hay que observarlo en el banco.

## E12 (ESTERILIZACION)
1. La histéresis del techo: ver «Urgentes», punto 1.
2. Una Referencia sin lectura marca el ciclo NO CONFORME en cualquier fase del CICLO.
3. Sin lectura del Principal o de la presión, el debounce de las fallas queda congelado.
4. Si una Referencia con una excursión ya confirmada pierde la lectura, la exposición sigue detenida y su tiempo límite (CIC-14) sigue corriendo. V12 hace la misma pregunta.
5. La exposición no termina con una Referencia fuera de banda, aunque la excursión todavía no esté confirmada.
6. El tiempo límite de la excursión se cuenta desde la primera lectura fuera de banda.
7. SEN-11 es un aviso no bloqueante, con despeje manual.
8. Un `tipo_carga` desconocido se trata como sólido (C-03 se vigila).
- PREGUNTA 2 (y V12): sin F0 no hay límite total. Las excursiones repetidas pueden reiniciar la exposición sin fin. ¿Se pone un tope?

## V12 (revisión de seguridad)
- PREGUNTA 3: con el debounce de «5 s continuos», una señal que oscila alrededor del umbral nunca se confirma, y es fácil que pase con `brecha_error_temperatura` en 0,1 K y el ruido de la PT100. ¿Se acepta, o se usa un criterio acumulado?
- Quedan pendientes SAF-05 (como máximo un tick acreditado antes de perder la lectura) y SAF-09 (recorte de la chaqueta en ejecución y `try` en el registro de la consigna).

## L12 (especificación de líquidos y banco)
1. Rol de sensor nuevo `vapor`, solo para líquidos, con `temp_ref` por defecto.
2. Un programa de líquidos sin sonda de vapor no puede iniciar.
3. Sonda de vapor sin lectura: código SEN-12, que es una propuesta y no está implementado, y la marca NO CONFORME.
4. A 8: ver el informe. Las 11 preguntas de la §10 de `planeacion_liquidos_dos_lazos.md` siguen abiertas; las más urgentes son el umbral de purga en Bogotá, qué salida drena el fondo y dónde está físicamente `temp_ref`.
- La hoja de banco se editó en el `.md`. `pruebas.py` y el `.html` quedan desactualizados (deuda heredada).

## Pendientes registrados (no se implementan en esta tanda)
- **PRG-01:** al cargar un programa, validar que cada rol asignado (Principal o Referencia) corresponda a una sonda cableada en el perfil.
- **DEU-01:** los límites de presión (fondo de escala, suministro y alivios) deben salir del perfil de instalación o de Parámetros del equipo. El suministro en presión absoluta depende de la atmósfera del sitio.

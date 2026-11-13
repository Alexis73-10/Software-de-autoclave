# Planeación: control del generador de vapor por software (V1.1.0)

Estado: PLANEACIÓN. No implementar en la 1.0.0 (funcionalidades congeladas desde el 9-nov). Se abre al iniciar la 1.1.0, en rama propia.
Fecha: 13-nov-2026. Fuente: conversación con Cristian (12 y 13-nov).
Convención: lo marcado DECISIÓN SIN CONFIRMAR es propuesta de Claude pendiente de aprobación; lo marcado PENDIENTE requiere un dato o una decisión de Cristian.

## 1. Situación actual

El generador interno (resistencias eléctricas) es independiente del software. El equipo solo sabe si tiene generador o no (perfil de instalación).

Cadena de las resistencias (hardware, en serie, alimenta la bobina del contactor):
relé del control de nivel (electrodo de mínimo) → termostato de las resistencias → presostato de control (punto de ajuste y diferencial, mínimo 5 psi) → presostato de corte (70 psi) → contactor único (dos contactores sobre 27 kW). Última barrera: válvula de seguridad mecánica a 75 psi.

Agua: electrodo de máximo (llenado al 70 %) → interruptor de nivel del tanque de reserva → contactor de la bomba. Bomba de diafragma (hasta 150 psi) con presostato interno de autoprotección. Recorrido físico: bomba → válvula de asiento inclinado → check → generador (en todos los generadores). Tres electrodos: común, mínimo y máximo.

Resistencias: de 9 kW con 3 elementos monofásicos (casi siempre en triángulo, 208/220 V) o individuales de unos 3 kW (por ejemplo, 18 kW = 6 × 3 kW). Las fases siempre se instalan balanceadas.

Presión de trabajo actual: unos 60 psi manométricos.

Drenaje: válvula de bola manual, se usa solo en cada mantenimiento preventivo. Descarga al mismo drenaje de rechazo de la cámara.

Sin sensores analógicos en el generador.

## 2. Objetivos (Cristian)

- GEN-OBJ-1: menor desgaste de resistencias y contactores fuera de ciclo (una sola resistencia, con rotación).
- GEN-OBJ-2: control más preciso de la presión del generador.
- GEN-OBJ-3: purga automática para reducir incrustaciones (purga de fondo corta y vaciado completo).
- GEN-OBJ-4: precalentar el agua del tanque de reserva con el drenaje de la cámara (recuperación de calor por intercambio).
- GEN-OBJ-5: diagnóstico y contadores de mantenimiento del generador.

Nota de Claude: para sostener una presión fija las pérdidas por aislamiento son las mismas con una resistencia o con todas; usar una sola reduce desgaste y mejora la estabilidad, pero el ahorro de energía real solo vendría de bajar la presión de espera o apagar por horario (ver GEN-12, opcional).

## 3. Decisiones registradas

- GEN-D1 (Cristian, 13-nov): control por escalones con contactores independientes, no proporcional.
- GEN-D2 (Cristian, 13-nov): escalón mínimo = grupo balanceado. En resistencias de 9 kW, la resistencia completa; en resistencias de 3 kW, un grupo de tres (una por fase), 9 kW.
- GEN-D3 (Cristian, 13-nov): fuera de ciclo se mantiene una sola presión de trabajo (unos 60 psi) con un solo grupo, rotando qué grupo enciende cada vez.
- GEN-D4 (Cristian, 13-nov): con demanda de vapor en ciclo entran todos los grupos, para no quedarse sin vapor.
- GEN-D5 (Cristian, 13-nov): se instala un transductor de presión en el generador.
- GEN-D6 (Cristian, 13-nov): la cadena de seguridad (nivel mínimo, termostato, presostato de corte) sigue cableada por hardware e independiente del software.
- GEN-D7 (Cristian, 13-nov; recomendación de Claude): el presostato de control se conserva en serie como respaldo, calibrado sobre el punto de trabajo del software. Escalonamiento: software 60 psi < presostato de control unos 65 psi < presostato de corte 70 psi < válvula de seguridad 75 psi. Márgenes de 5 psi: exigen calibración cuidadosa.
- GEN-D8 (Cristian, 13-nov): sin PT100 en el agua del generador. La redundancia del transductor es el presostato de control.
- GEN-D9 (Cristian, 13-nov): dos tipos de purga, programables por hora y fecha en Opciones › Mantenimiento, con bloqueo del inicio de ciclo y aviso «Generador en purga».
- GEN-D10 (Cristian, 13-nov): la válvula de bola manual de drenaje se reemplaza por una de asiento inclinado (soporta 250 °C).
- GEN-D11 (Cristian, 13-nov): recuperación de calor por intercambio: la tubería de drenaje pasa por dentro del tanque de reserva sin mezclarse. El tanque tiene tapa pero no está sellado (abierto a la atmósfera).
- GEN-D12 (Cristian, 13-nov): si faltan salidas se agrega un módulo de expansión.

## 4. Arquitectura de seguridad (GEN-01)

Principio: el software solo puede encender algo que el hardware ya permite.

- La cadena (relé de nivel mínimo → termostato → presostato de control → presostato de corte) deja de alimentar directamente el contactor y pasa a alimentar una línea común de permiso.
- De esa línea salen las bobinas de los contactores de cada grupo, cada una a través de una salida digital del software.
- Si la cadena abre, todas las bobinas se quedan sin energía, haga lo que haga el software.
- El paro de emergencia sigue cortando la energía del generador por hardware.
- La vigilancia del lazo del enlace Modbus (MOD-08) apaga las salidas si el control deja de responder: falla segura (generador apagado).

DECISIÓN SIN CONFIRMAR (GEN-01b): contactor general aguas arriba, en serie con los de grupo y alimentado por la misma cadena. Motivo: un contactor de grupo con los contactos soldados no se abre al quitarle la bobina; hoy ese caso solo lo detiene la válvula de seguridad. Con el contactor general hay dos elementos en serie. Implica costo y espacio de tablero (PENDIENTE de presupuesto).

PENDIENTE (GEN-P6): selector físico de respaldo «manual» que, ante una falla del software o del transductor, permita operar el generador como hoy, con el presostato de control. Mantiene el equipo disponible; hay que definir cómo se señaliza y quién puede usarlo.

## 5. Hardware nuevo o modificado

- Transductor de presión del generador (GEN-D5). PENDIENTE (GEN-P4): rango. Los QDW90A de 0-4 bar no alcanzan: 75 psi manométricos ≈ 517 kPa más la atmosférica local (≈ 74,6 kPa en Bogotá) ≈ 592 kPa absolutos. Hace falta como mínimo 0-10 bar absolutos. Impacto en software: hoy la calibración nominal de todas las entradas de presión es 4-20 mA → 0-400 kPa y el fondo de escala es de equipo (400 kPa); el canal del generador necesita su propio rango y su propia calibración.
- Un contactor por grupo balanceado (más el general si se aprueba GEN-01b).
- Válvula de asiento inclinado para purga/drenaje (GEN-D10).
- Contactos auxiliares de los contactores de grupo cableados a entradas digitales (retroalimentación).
- Recuperación de calor: serpentín del drenaje dentro del tanque (GEN-D11). Puede requerir cambiar la bomba (ver GEN-P2).
- Opción futura (no en la 1.1.0): relés de estado sólido con cruce por cero para control proporcional (ver §12).

## 6. Entradas y salidas (propuesta, DECISIÓN SIN CONFIRMAR)

Salidas:
- Una DO por grupo de resistencias (N grupos según el generador).
- Bomba de agua.
- Válvula de ingreso de agua (asiento inclinado).
- Válvula de purga/drenaje.

Entradas digitales:
- Permiso de la cadena de seguridad presente.
- Nivel mínimo (contacto del control de nivel).
- Nivel máximo (contacto del control de nivel).
- Nivel bajo del tanque de reserva.
- Retroalimentación de cada contactor de grupo (contacto auxiliar).
- Opcional, si se puede separar en el cableado: termostato disparado y presostato de corte disparado (para diagnóstico).

Entradas analógicas:
- Presión del generador (AI libre del grupo de presión; AI 09-16 están libres y con calibración nominal).

El enlace lee 32 salidas (DO 01-32; buzzer en DO 25). PENDIENTE (GEN-P3): contar las salidas libres en el perfil de E/S máximo y decidir si hace falta otra expansión (GEN-D12).

Todas las funciones nuevas entran al esquema de asignación de E/S (asignacion_io), a Reasignación y a Entradas/Salidas del modo prueba. Un equipo sin generador interno las deja deshabilitadas en el perfil, como hoy.

## 7. Control de presión (GEN-02)

El software trabaja en kPa absolutos (convención del proyecto). Los 60 psi manométricos se convierten con la presión atmosférica local configurada.

Parámetros del equipo propuestos (DECISIÓN SIN CONFIRMAR, valores a ajustar en banco):
- presion_generador_trabajo: unos 60 psi manométricos convertidos a kPa abs.
- banda_generador: diferencial de reencendido (5 psi como el presostato de hoy, ≈ 34 kPa).
- tiempo_minimo_encendido_grupo y tiempo_minimo_apagado_grupo: 30 s, para evitar conmutaciones cortas.
- retardo_entrada_grupos: 2 s entre la entrada de un grupo y el siguiente, para limitar la corriente de arranque.

Lógica:
- Fuera de ciclo (GEN-D3): presión ≤ trabajo − banda → enciende un grupo; presión ≥ trabajo → apaga. El grupo se elige por rotación (el de menos horas acumuladas o el siguiente en orden). Si la presión sigue cayendo con un grupo encendido (por ejemplo, más de X kPa bajo la banda o más de Y minutos sin recuperar), entra otro grupo. DECISIÓN SIN CONFIRMAR los valores X e Y.
- Con demanda (GEN-D4): presión ≤ trabajo − banda → entran todos los grupos, escalonados por retardo_entrada_grupos; salen al llegar a trabajo. PENDIENTE (GEN-P14): qué cuenta como demanda: solo el estado CICLO, o también PREPARACION/PREPARADO mientras la chaqueta está pidiendo vapor, y si se anticipa al pulsar INICIAR.
- Sobrepresión de software: presión ≥ trabajo + margen (por debajo del presostato de control) → todos los grupos apagados y aviso. Valor DECISIÓN SIN CONFIRMAR.
- Sin lectura del transductor o lectura fuera de rango → todos los grupos apagados (falla cerrada) y alarma. En CICLO, la falta de vapor la detectan las fallas propias del ciclo; ver HAZ-GEN-05.
- Presostato de control abierto mientras el software pide calor (permiso ausente con presión de software bajo trabajo) → alarma de diagnóstico «transductor del generador desviado».

Estimación de maniobras (orden de magnitud con supuestos de Claude: unos 40 L de agua, pérdidas de unos 1 kW, banda 55-60 psi): fuera de ciclo un grupo de 9 kW enciende menos de 1 min y apaga unos 6 min, unas 8 a 10 maniobras por hora; con rotación entre 3 grupos, unas 3 por hora por contactor (≈ 25.000 al año en 24/7). Un contactor AC-1 aguanta del orden de un millón de maniobras eléctricas. PENDIENTE (GEN-P1): volumen real de agua y pérdidas para confirmar.

Arranque y estados del software:
- El generador respeta el arranque retenido: no enciende hasta la liberación del arranque.
- Apagado del equipo: grupos, bomba y purga en OFF.
- Paro de emergencia: corte por hardware; tras soltarlo, no reenciende hasta la confirmación del paro, como las demás salidas.
- Modo prueba: los grupos, la bomba y las válvulas se pueden accionar a mano con las protecciones de §8 y §9 (sin cadena de permiso no enciende nada).

## 8. Control de agua (GEN-03)

Propuesta (DECISIÓN SIN CONFIRMAR):
- El software comanda la bomba y la válvula de ingreso con la señal de nivel máximo: sin agua en el electrodo de máximo → válvula de ingreso abierta y bomba ON; con agua → bomba OFF y válvula cerrada.
- Por hardware se conservan en serie con la bomba el interruptor de nivel del tanque de reserva y el presostato interno de la bomba.
- Orden de maniobra: abrir la válvula de ingreso antes de arrancar la bomba; apagar la bomba antes de cerrar la válvula.
- Tiempo máximo de llenado: si no se llega al nivel máximo, alarma (fuga, bomba o válvula). Valor DECISIÓN SIN CONFIRMAR.
- Nivel mínimo perdido: la cadena de hardware ya apaga las resistencias; el software además lo registra y alarma.
- Durante la purga o el vaciado el llenado se bloquea hasta que la válvula de purga esté cerrada.

## 9. Purgas (GEN-04)

Dos programas en Opciones › Mantenimiento (GEN-D9), programables por hora y fecha:

Purga de fondo corta:
- Apertura de unos segundos de la válvula de purga con el generador en presión, para sacar lodos. No vacía el generador.
- Solo fuera de ciclo. Bloquea el inicio de ciclo mientras dura y muestra «Generador en purga».
- Después se repone el agua por la lógica normal de llenado.
- PENDIENTE (GEN-P9): frecuencia y duración (por ejemplo, diaria, 3 a 5 s).

Vaciado completo:
- Resistencias apagadas, drenaje completo, rellenado y recalentamiento hasta la presión de trabajo.
- Bloquea el inicio de ciclo desde que empieza hasta que la presión vuelve a trabajo − banda; aviso con el tiempo transcurrido.
- PENDIENTE (GEN-P8): vaciar con presión (salida rápida, más revaporizado en el drenaje) o esperar a una presión baja (más tiempo).
- Programado de preferencia en la noche.

Comunes:
- El agua de purga sale a temperatura de saturación (unos 150 °C a 60 psi). Descarga al drenaje de rechazo de la cámara; aplica el enfriamiento de drenaje existente (temp_segura_drenaje / agua_intercambiador). PENDIENTE (GEN-P11): confirmar que la purga entra aguas arriba del intercambiador y del sensor de drenaje.
- No se ejecuta con modo prueba activo, con el paro activo ni durante un ciclo; si llega la hora durante un ciclo, se aplaza hasta que el equipo quede libre. DECISIÓN SIN CONFIRMAR.
- Registro: bitácora (inicio y fin), contador de purgas, ticket o reporte de mantenimiento.

## 10. Recuperación de calor (GEN-05)

- El drenaje de la cámara (y el escape) pasa por un serpentín dentro del tanque de reserva, sin mezclarse (GEN-D11).
- Riesgo: el agua del tanque se calienta y una bomba de diafragma tiene una temperatura máxima de fluido; con agua muy caliente puede cavitar en la succión.
- PENDIENTE (GEN-P2): temperatura máxima admisible de la bomba actual o selección de otra.
- PENDIENTE (GEN-P15): si hace falta medir la temperatura del tanque (PT100 o termostato) para proteger la bomba. Esto es distinto de GEN-D8, que se refiere al agua del generador.

## 11. Interfaz y registros (GEN-06)

- Pantalla del generador (alcance previo: diagnóstico): se amplía con el estado de control. Estados aprobados: Apagado, Llenando, Calentando, Operando, Purga y Falla. Esquema visual animado. Ubicación en el menú PENDIENTE.
- Contadores: horas de encendido por grupo, maniobras por contactor, número de purgas cortas y vaciados, fecha de la última descalcificación.
- Aviso «Generador en purga» en Preciclo y en la campana, con el inicio de ciclo bloqueado.
- Parámetros del generador en Opciones › Parámetros del equipo (rol ingeniero/admin), con su bitácora de cambios.
- Textos es/en (requisito de idiomas).

## 12. Opción futura: control proporcional

No entra en la 1.1.0 (GEN-D1). Si se decide más adelante:
- Relés de estado sólido trifásicos con conmutación en cruce por cero, modulando por ráfagas de pocos segundos (no por ángulo de fase, que genera armónicos).
- Contactor general obligatorio aguas arriba, alimentado por la cadena: un SSR falla normalmente en corto y la cadena no podría apagarlo.
- Disipación del orden de 1 a 1,5 W por amperio por fase (unos 25 A por línea en 9 kW a 208 V): disipador y ventilación del tablero.
- Esquema híbrido sugerido: escalones con contactor para la carga base y un solo grupo sobre SSR para el ajuste fino.
- Verificar si las salidas del módulo son de relé o de transistor (el SSR se comanda en continua).

## 13. Riesgos preliminares (para el registro de riesgos al abrir la 1.1.0)

- HAZ-GEN-01 Sobrepresión por transductor que lee bajo. Mitigación: presostato de control en serie (GEN-D7), presostato de corte, válvula de seguridad, alarma de diagnóstico de §7.
- HAZ-GEN-02 Resistencias en seco. Mitigación: electrodo de mínimo y termostato en la cadena de hardware (GEN-D6).
- HAZ-GEN-03 Contactor de grupo soldado. Mitigación: retroalimentación por contacto auxiliar (alarma) y contactor general en serie (GEN-01b, pendiente).
- HAZ-GEN-04 Descarga de purga a alta temperatura (quemaduras, daño de tubería). Mitigación: enfriamiento de drenaje, purga solo fuera de ciclo.
- HAZ-GEN-05 Falta de vapor en ciclo por falla del control del generador. Mitigación: todos los grupos con demanda (GEN-D4), selector manual de respaldo (GEN-P6); el ciclo falla por sus propias condiciones, sin carga declarada estéril.
- HAZ-GEN-06 Daño o cavitación de la bomba por agua caliente del tanque. Mitigación: GEN-P2 y GEN-P15.
- HAZ-GEN-07 Inicio de ciclo durante una purga. Mitigación: bloqueo del inicio en el backend (falla cerrada) además de la pantalla.
- HAZ-GEN-08 Desbalance de fases. Mitigación: grupos balanceados fijos en el perfil (GEN-D2); el software nunca acciona elementos sueltos.
- HAZ-GEN-09 Falla de software que deja un grupo encendido. Mitigación: MOD-08, cadena de hardware, presostatos y válvula de seguridad.

Clasificación: el control del generador influye en la disponibilidad y en la presión de un recipiente a presión; tratarlo como Clase C dentro del sistema, con la cadena de hardware como medida de control de riesgo externa al software.

## 14. Pendientes de Cristian

- GEN-P1 Volumen de agua del generador y pérdidas aproximadas (para confirmar maniobras y tiempos).
- GEN-P2 Temperatura máxima de la bomba o cambio de bomba (recuperación de calor).
- GEN-P3 Salidas digitales libres en el perfil máximo; necesidad de expansión.
- GEN-P4 Rango del transductor del generador (mínimo 0-10 bar abs).
- GEN-P5 Presupuesto y aprobación de los cambios de tablero (contactores por grupo, auxiliares, transductor, válvula de purga).
- GEN-P6 Selector físico de respaldo «manual».
- GEN-P7 Contactor general en serie (GEN-01b).
- GEN-P8 Vaciado completo con presión o a presión baja.
- GEN-P9 Frecuencia y duración de la purga corta.
- GEN-P10 Medición de conductividad (idea previa, sin definir).
- GEN-P11 Punto de entrada de la purga respecto al intercambiador y al sensor de drenaje.
- GEN-P12 Ubicación de la pantalla del generador en el menú.
- GEN-P13 Control proporcional con SSR (futuro, §12).
- GEN-P14 Qué cuenta como «demanda» para encender todos los grupos.
- GEN-P15 Medición de temperatura del tanque de reserva.
- GEN-P16 Relación con el presostato de suministro de vapor ya previsto (antes del regulador de 40 psi): si sigue haciendo falta con el transductor del generador o solo para caldera externa y circuito mixto.

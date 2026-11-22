# Planeación: mejora del secado y precalentamiento de la carga

Fecha: 20-nov-2026. Estado: borrador para revisión de Cristian. Sin implementación.
Alcance: revisión física del equipo desde el ingreso de vapor hasta el secado, mejoras de software y una fase de precalentamiento de la carga al inicio del ciclo.
Equipos objetivo: equipos de piso (chaqueta, bomba de anillo líquido). Los de mesa se tratan aparte.

## 0. Problema y criterio de éxito

Hoy, con contenedores rígidos e instrumental pesado, el secado validado es de 30 min. Con 20 min la carga sale húmeda y los contenedores gotean al girarlos. El agua del sello entra a 20-24 °C, viene de la red, pasa por un tanque y va a drenaje. El intercambiador del vacío se enfría con agua de red.

Aclaración de Cristian (20-nov): los 12 kPa medidos en el secado con carga corresponden a la bomba usada del equipo de pruebas y no representan un equipo nuevo; no se usan como dato de diseño. Aun con una bomba nueva, el secado es la etapa que más alarga el ciclo. Por eso el plan apunta a mejoras generales (calor a la carga, condensación, pulsos, precalentamiento y fin por criterio) y no solo a corregir una bomba.

Criterio de éxito: bajar el tiempo de secado sin cambiar la exposición, con la carga patrón seca. Carga seca significa:
- humedad residual de 0,2 % como máximo en metal (EN 285),
- contenedores sin agua visible ni goteo al girarlos.

Todo tiempo nuevo exige revalidar el programa.

## 1. Teoría de base (resumen)

Secar es evaporar el agua y sacar el vapor. Lo limita lo más débil de tres cosas:
- cuánta agua hay en la carga,
- cuánto calor le llega a esa agua (unos 2300 kJ por kg),
- qué tan rápido sale el vapor (a 12 kPa, 1 kg de vapor ocupa unos 12 m³; lo saca sobre todo el condensador, no la bomba).

Cómo leer la curva del secado:
- La presión se queda alta con la carga caliente: el límite es sacar el vapor (condensador, línea o bomba).
- La presión baja rápido pero la carga sigue mojada: el límite es el calor (la carga se enfrió).

La carga no aprovecha su propio calor por debajo de la temperatura de ebullición del vacío alcanzado (unos 49 °C a 12 kPa y unos 33 °C a 5 kPa). Aun con un vacío profundo, en cargas pesadas el límite final es el calor: sin aporte de la chaqueta la carga se enfría y la evaporación se detiene.

## 1b. Contenedores rígidos: el caso crítico

Aclaración de Cristian (20-nov): los textiles secan rápido; el problema son los contenedores rígidos con instrumental pesado.

Por qué cuestan más:
- Mucha masa metálica dentro de una caja casi cerrada: se forma mucho condensado y se acumula en el fondo y en la tapa.
- El vapor solo sale por el filtro o la válvula del contenedor. Con vacío continuo, cuando la presión de adentro iguala la de la cámara, el intercambio casi se detiene y el vapor sale lento por difusión.
- El agua acumulada en el fondo recibe poco calor: el aire de adentro aísla y en vacío no hay convección.
- Los contenedores de polímero guardan poco calor y secan peor que los de aluminio.

Qué ataca cada punto:
- Pulsos de presión (modo 3) son la medida principal. Cada vacío saca el vapor de adentro por el filtro y cada ruptura mete aire nuevo y seco. El contenedor "respira" en cada pulso. El vacío continuo no logra esto.
- Aire caliente en las rupturas (serpentín): el aire que entra al contenedor le lleva calor al interior en vez de enfriarlo.
- Chaqueta caliente durante el secado (S1): calienta las paredes del contenedor por radiación y, con aire, por convección.
- Precalentamiento de la carga (sección 5): menos condensado de entrada.
- Prácticas de carga: contenedores en los niveles de abajo y sin apilar, absorbente no tejido en el fondo, instrumental repartido en bandejas perforadas, peso máximo por set. Seguir las instrucciones de uso del fabricante del contenedor (tiempo mínimo de secado, tipo de filtro).
- Después del ciclo: dejar enfriar la carga en un carro de malla, lejos de superficies frías y corrientes de aire acondicionado, para evitar que vuelva a condensar.

Programa propio: un programa «Contenedores» con secado pulsado, chaqueta caliente y precalentamiento, separado del de textiles. Así los textiles mantienen su secado corto y el tiempo largo solo lo pagan los contenedores. El software ya permite parámetros de secado por programa; el programa nuevo requiere validación propia.

## 1c. El problema es de la industria, no de un equipo

Aclaración de Cristian (20-nov): en los equipos de otros fabricantes a los que les ha hecho mantenimiento, sin importar la marca ni la antigüedad, pasa lo mismo con los contenedores, aunque ya hacen pulsos de vacío y tienen la chaqueta cerca de 380 kPa.

Lectura: el límite está dentro del contenedor, no en la cámara.
- El agua del fondo solo recibe calor de las paredes del contenedor. En vacío casi no hay convección, y cada pulso de evaporación enfría esas paredes.
- La única entrada de gas es el filtro, lo que limita el intercambio.
- Meter vapor durante el secado para recalentar no sirve: el agua que condensa es la misma que su calor puede evaporar después; el balance es cero.
- Los fabricantes de contenedores suelen indicar tiempos de secado de 20 a 30 min. Los 30 min validados están en ese rango.

Palancas que sí cambian el balance (a probar en el banco, sin prometer cifras):
- Prevenir el condensado: precalentamiento de la carga (sección 5). Es la única que reduce el agua en lugar de sacarla.
- Recalentar entre vacíos con tiempo: rupturas con aire caliente y un sostenimiento en la presión alta, para que la convección recaliente las paredes del contenedor antes del siguiente vacío. Los perfiles habituales pasan muy poco tiempo en la parte alta del pulso.
- Calor por conducción en el fondo: estantes o bandejas calentados con vapor de la chaqueta, para dar calor justo donde se acumula el agua. Es una idea a evaluar; los contenedores apoyan en patas pequeñas, lo que limita el contacto.
- Última ruptura con vacío profundo y aire caliente: evita que el vapor que queda dentro del contenedor condense al final.
- Fin del secado por criterio: la carga pesada seguirá necesitando su tiempo, pero las demás no pagarán ese tiempo.
- Verificar si el agua que gotea se formó durante el ciclo o después, al enfriarse la carga en el carro (recondensación). Las dos tienen solución distinta.

## 2. Medición base (antes de cambiar nada)

El pesaje no es para cada carga. Se hace solo en las pruebas de banco y de validación, con una carga patrón que representa el peor caso (contenedores rígidos e instrumental pesado). Lo que esas pruebas demuestran queda fijo en los parámetros del programa. En la operación diaria la verificación es general y automática (ver 2.1).

M1. Definir una carga patrón por modelo: número y tipo de contenedores rígidos, masa del instrumental, posición en la cámara. Se usa igual en todas las pruebas.

M2. Pesar cada contenedor antes del ciclo y al sacarlo, siempre en el mismo tiempo después de abrir.

M3. Datalogger durante todo el ciclo:
- presión de cámara;
- presión justo antes de la bomba de vacío (después de la válvula y del intercambiador);
- presión de chaqueta;
- temperatura del agua del sello a la entrada y a la salida de la bomba;
- temperatura del agua de enfriamiento del intercambiador a la entrada y a la salida, y su caudal (con un balde y un cronómetro basta);
- temperatura en el fondo de un contenedor (termopar dentro de la carga).

M4. Correr el ciclo validado con 30 min de secado y otro con 20 min. Registrar la curva de presión del secado y los pesos.

M5. Vacío final con la cámara vacía y fría (sin carga) y prueba de fugas (vacío sostenido; criterio EN 285: 0,13 kPa/min como máximo).

Estos datos dicen qué límite manda en cada modelo y sirven de base para los cálculos de dimensionamiento.

### 2.1 Verificación de rutina, sin pesar

- **Automática:** al final del secado, el equipo aísla la cámara entre 30 y 60 s y mide la subida de presión. Una carga mojada sigue evaporando y la presión sube; una seca casi no la mueve. El umbral se fija una vez por modelo en el banco, comparándolo con el pesaje de la carga patrón. Después corre solo en cada ciclo, queda en el registro y en el ticket, y da un aviso si no cumple. Es la misma medición de S5, primero solo como verificación y más adelante como criterio de fin.
- **Automática:** vacío mínimo alcanzado en el secado contra el valor de referencia del modelo (S6 y S7).
- **Del operador:** inspección visual al descargar (sin gotas en los contenedores ni en el empaque, envolturas sin manchas de humedad). Es la práctica normal de la central de esterilización.

## 3. Revisión del equipo, en el orden del recorrido del vapor

### 3.1 Suministro de vapor (caldera o generador)

- Calidad del vapor. Referencia EN 285: sequedad de 0,95 como mínimo, gases no condensables de 3,5 % como máximo, sobrecalentamiento de 25 K como máximo. El vapor húmedo moja la carga desde la esterilización.
- Separador de humedad con trampa en la entrada del equipo, antes del regulador de 40 psi. Revisar si existe y si su trampa descarga.
- Trampas y purgas de la línea de alimentación; línea aislada; tramos largos sin purga.
- Generador interno: verificar arrastre de agua (nivel de llenado al 70 %, espuma por agua con mucha conductividad o sin purga).

### 3.2 Chaqueta

- La trampa de la chaqueta descarga condensado y no deja pasar vapor vivo.
- Aislamiento completo, sin tramos expuestos.
- Presión real contra el transductor (calibración de pres_chaqueta, ya pendiente por HAZ-CAS-02).
- Termografía de las paredes de la cámara en el secado, para encontrar zonas frías (marco de la puerta, bridas, soportes).

### 3.3 Ingreso de vapor a la cámara (vapor_camara se toma de la chaqueta)

- El punto de toma está en la parte alta de la chaqueta y no arrastra condensado.
- Hay un deflector a la entrada de la cámara para que el chorro no golpee la carga directo.

### 3.4 Cámara

- Piso con pendiente hacia el drenaje, y drenaje en el punto más bajo.
- Drenaje de la cámara con trampa durante la exposición, para que el condensado salga y no se acumule bajo la carga. Revisar cómo está hoy.
- Puerta y marco aislados (confirmado por Cristian); revisar empaque y marco como superficies frías.
- Bandejas y rieles: preferir malla; las bandejas lisas acumulan agua.

### 3.5 Línea de vacío

- Diámetro de la tubería, longitud, codos y Kv de la válvula de asiento inclinado del vacío.
- Comparar la presión de cámara con la presión antes de la bomba durante el secado. Una diferencia grande indica que la línea o la válvula son el cuello de botella.

### 3.6 Intercambiador o condensador del vacío

- Tipo (de superficie), área, caudal y temperatura del agua de red. El calor que se lleva sale de la diferencia de temperatura del agua de enfriamiento por su caudal.
- Confirmado por Cristian (20-nov): es un solo intercambiador físico para el vacío y para el drenaje (en software, la salida agua_intercambiador, AJ-02). Su capacidad se reparte entre condensar el vapor del vacío y enfriar el drenaje, y probablemente se dimensionó para el drenaje. Conviene verificar en un equipo nuevo si limita la velocidad de evacuación en el secado.
- Prueba que lo confirma o lo descarta: temperatura del agua de enfriamiento a la salida durante el secado. Si sale caliente (más de unos 40 °C), el intercambiador está saturado. Si sale fría y la presión sigue alta, el límite está en la línea o en la bomba.
- Opciones: un condensador propio para la línea de vacío, separado del drenaje, o el condensador de mezcla descrito abajo.
- Alternativa o complemento: condensador de mezcla, es decir, inyección de agua fría rociada en la línea de vacío antes de la bomba. Es barato y muy efectivo; consume más agua.

### 3.7 Bomba de vacío de anillo líquido

- Confirmado por Cristian (20-nov): el tanque del sello recibe solo agua de red. El sello entra frío y no es la causa principal del vacío pobre; falta confirmar la temperatura de salida y el caudal.
- Temperatura del agua del sello a la entrada y a la salida, y caudal del sello contra el que pide el fabricante.
- Vacío final con la cámara vacía (M5). Con agua a unos 20 °C debería llegar a 3-5 kPa.
- Estado de la bomba: desgaste, ruido de cavitación, incrustaciones.
- Opcional: un eyector de aire antes de la bomba para un vacío más profundo, o una bomba de mayor caudal para el volumen de la cámara.

### 3.8 Ingreso de aire (rupturas de vacío)

- Filtro bacteriológico: ubicación, tipo (membrana PTFE, temperatura admisible, esterilizable con vapor), pérdida de carga y frecuencia de cambio.
- Propuesta: serpentín de calentamiento del aire en contacto con la chaqueta, sin consumo eléctrico. Recorrido: toma de aire, serpentín, filtro, check, cámara.
  - El filtro va después del serpentín y lo más cerca posible de la cámara. Así el vapor de la cámara lo esteriliza en cada ciclo y el aire caliente lo mantiene seco.
  - El aire aporta poco calor propio. Su valor es permitir la convección pared → carga sin enfriar la carga en cada pulso.

### 3.9 Carga (manual de uso)

- Contenedores pesados en los niveles de abajo.
- Absorbente no tejido dentro de los contenedores.
- Peso máximo por set (referencia habitual: unos 11 kg).
- Canastas de malla, sin apilar contenedores sin separación.

## 4. Mejoras de software

### S1. Chaqueta a temperatura de esterilización en el secado (hallazgo)

Hoy los 6 programas de fábrica tienen presion_chaqueta_secado en 200 kPa y rango_chaqueta_secado en 30. _tick_chaqueta solo enciende bajo 170 kPa, es decir, unos 115 °C de saturación. En un ciclo de 134 °C la chaqueta queda más fría que la carga.

Propuesta: en el secado, consigna de chaqueta igual a la del ciclo (consigna_chaqueta, la misma de CicloState._mantener_chaqueta) o un parámetro con un defecto ligado a T_est, con una banda de ±10 kPa. Siempre bajo D-CHQ (presion_max_chaqueta_control) y respetando el corte de chaqueta.

PRECALENTAMIENTO tiene el mismo defecto de 200 kPa.

### S2. Modo de secado pulsado (modo 3) para cargas pesadas

- Hoy todos los programas usan el modo 1 (vacío continuo). El modo 3 no se ha usado en campo.
- timeout_pulso por defecto vale 10 s. Con carga mojada, bajar a presion_baja_secado (20 kPa) en 10 s es poco probable y daría FALLO sec_modo3_vacio_bajo. Revisar el defecto y medirlo.
- Agregar tiempos de sostenimiento en vacío y en aire, para dar tiempo a la evaporación y a la convección.
- Ajustar en el banco la profundidad del vacío, la presión de ruptura y el número de pulsos con la carga patrón.

### S3. Empalme descompresión → secado en sólidos

Medir cuánto tarda hoy DESCOMPRESION en sólidos. Entrar al vacío con la carga lo más caliente posible: descompresión rápida y paso inmediato al secado.

### S4. Precalentamiento de la carga (ver sección 5)

### S5. Fin del secado por criterio (secado adaptativo, candidato de la v1.1)

- Con tiempo mínimo y tiempo máximo, aislar la cámara entre 30 y 60 s y medir la subida de presión. Si sube menos que un umbral, la carga está seca.
- Requiere validación propia. El tiempo fijo se conserva para los programas validados así.

### S6. Registro del secado

Guardar en cada ciclo, y mostrarlos en el reporte:
- la curva de presión del secado,
- el vacío mínimo alcanzado,
- la subida medida en la prueba de aislamiento.

### S7. Tendencia del vacío para mantenimiento

Llevar la tendencia del vacío mínimo del prevacío y del secado. Si empeora, dar un aviso de mantenimiento (bomba, sello, fuga, intercambiador). Se conecta con el mantenimiento predictivo.

### S8. Agua del intercambiador

El intercambiador es el mismo del drenaje. Hoy el agua solo abre con vacio_camara abierta o por la petición del drenaje. En el secado pulsado conviene mantenerla abierta durante todo el secado, para que el intercambiador esté frío al empezar cada vacío. Si se agrega un condensador propio, tendría su propia salida.

## 5. Precalentamiento de la carga al inicio del ciclo

Objetivo: que la carga entre más caliente al primer pulso de vapor, para que condense menos agua. El condensado es proporcional a T_est menos la temperatura inicial de la carga. A 134 °C, una carga que entra a 60 °C en vez de 25 °C condensa cerca de un 32 % menos.

Base existente: la fase PRECALENTAMIENTO ya existe, pero hoy solo calienta la chaqueta. Está desactivada (tiempo_precalentamiento = 0) y su presión por defecto es de 200 kPa.

### 5.1 Propuesta funcional

1. Con la puerta sellada y antes del primer vacío, llevar la chaqueta a la presión de esterilización del programa.
2. Sostener un tiempo de calentamiento de carga con la cámara cerrada y aire a presión atmosférica, sin vapor a la cámara. La carga se calienta por radiación y por convección natural desde las paredes.
3. Variante a probar: pulsos suaves de aire caliente durante el precalentamiento (vacío poco profundo y ruptura con aire del serpentín). Renuevan el aire dentro de los contenedores y calientan el interior por convección forzada. Es una hipótesis: hay que medirla.

### 5.2 Limitaciones

- El aire aísla. El interior de los contenedores rígidos se calienta lento. Hay que medir, con el termopar en el fondo del contenedor, cuánto sube en 5, 10 y 15 min.
- El aire de la cámara cerrada se expande al calentarse: de 20 a 100 °C sube la presión cerca de un 27 % (en Bogotá, de 75 a unos 95 kPa abs). Hay que decidir si la cámara queda cerrada o con el escape lento abierto.
- Se suma al tiempo total. Solo vale si cada minuto de precalentamiento ahorra más de un minuto de secado (o mejora la sequedad con el mismo tiempo).

### 5.3 Cambios de software (cuando se decida)

- Defecto de presion_precalentamiento ligado a T_est en lugar de 200 kPa.
- Parámetro nuevo: tiempo de calentamiento de carga, contado desde que la chaqueta llega a la consigna.
- Sin vapor_camara en esta fase; respetar D-CHQ y el corte de chaqueta.
- Publicar la fase en la barra de fases y en el ticket.
- Bowie & Dick y prueba de fugas sin precalentamiento de carga.

### 5.4 Normativa

Es un cambio del ciclo validado. Requiere solicitud de cambio (IEC 62304), análisis de riesgo, actualización de la trazabilidad y revalidación de los programas que lo usen.

## 6. Orden de ejecución propuesto

- Etapa A. Medición base (sección 2) en el equipo de pruebas.
- Etapa B. Correcciones baratas: S1 (chaqueta en el secado), agua del sello fría y de un solo paso, trampas y separador, prácticas de carga. Repetir la medición.
- Etapa C. Pruebas de banco: modo 3 ajustado (S2), empalme (S3) y precalentamiento de carga (sección 5), cada uno por separado contra la base.
- Etapa D. Hardware según lo que muestren las mediciones: condensador de mezcla o intercambiador más grande, línea de vacío, serpentín de aire caliente, drenaje con trampa en la cámara.
- Etapa E. Secado adaptativo (S5) y registro (S6, S7), para la v1.1.
- Etapa F. Revalidación de los programas con los tiempos nuevos.

## 7. Preguntas abiertas para Cristian

P1. Resuelta (20-nov): el sello usa solo agua de red.
P2. Resuelta (20-nov): un solo intercambiador para el vacío y el drenaje.
P3. ¿La cámara tiene drenaje con trampa en el punto más bajo durante la exposición?
P4. ¿En qué punto de la chaqueta se toma el vapor de la cámara, y la entrada a la cámara tiene deflector?
P5. ¿Qué tipo de filtro bacteriológico se usa (material, temperatura admisible) y dónde está?
P6. Por modelo: volumen de la cámara, caudal y modelo de la bomba, y la carga patrón para las pruebas.

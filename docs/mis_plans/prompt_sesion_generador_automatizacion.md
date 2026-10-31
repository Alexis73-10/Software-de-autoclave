# Prompt para la sesión del generador: instalación por «automatización»

**Para pegar en la sesión que trabaja en el generador de códigos.** Solo preguntas y lectura: no modifiques nada todavía.

## Contexto

Hoy el equipo se instala en una sola modalidad: equipo fabricado por Especifika. Ahora se agrega una segunda, **automatización**: se toma el equipo de **otro fabricante**, se le instala nuestro software y hardware, y **se conservan la serie y el modelo originales del fabricante**.

Lo que sé del software del autoclave (ya verificado en el código):

- `puente_instalacion.construir_perfil` toma la serie de la pantalla (`strip().upper()`), exige que no esté vacía y llama a `validate_installation_code(serie, codigo)`. **No hay verificación de formato de la serie**; solo «no vacía» y que el código de activación coincida.
- `machine_id` se arma como `ACV-<año>-<serie>`.
- El modelo **no se escribe**: `installation/modelo.calcular_modelo(clase, capacidad_litros, tipo_carga, door_count)` lo calcula con la regla `SPK-SAT <capacidad><V|H>[2][-LAB]`, y el instalador ignora el `model_id` de la pantalla. Además `validate_profile_data` rechaza un perfil si `model_id` no es igual al calculado (`'model_id' inconsistente`). Por eso, con un equipo de otro fabricante, el modelo original no entra hoy.
- `desglosar_modelo` (cabecera del PDF) devuelve `None` si el nombre no sigue la regla; es solo informativo.
- La serie y el modelo se muestran en el ticket de arranque, el PDF, la bitácora (`equipo_instalado`), Información del equipo y `/status`.

## Preguntas sobre el generador (responde con archivo y línea)

1. **Cómo se genera hoy el código de activación**: ¿qué entradas usa (serie, modelo, clase, otras)? ¿Algoritmo (HMAC, clave, truncado, alfabeto, longitud)? ¿Dónde vive la clave y cómo se comparte con `validate_installation_code` del instalador?
2. **Qué valida el generador sobre la serie**: ¿formato, longitud, prefijo, unicidad en `generador.db`? ¿Puede registrar una serie arbitraria de otro fabricante (con guiones, minúsculas, espacios, caracteres especiales, más de N caracteres)?
3. **Qué guarda la base**: columnas de la tabla de equipos/códigos (serie, modelo, clase, fecha, estado). ¿Hay restricción de unicidad por serie? ¿Dos fabricantes podrían repetir serie?
4. **El modelo en el generador**: ¿se calcula con la misma regla `SPK-SAT …` o se escribe a mano? ¿Va dentro del código de activación o solo se registra?
5. **Pantalla y flujo**: describe los campos de «Nuevo equipo» y qué pasaría hoy si se intentara registrar un equipo con serie y modelo ajenos.
6. **Impresión y entregables**: ¿el generador produce etiquetas, certificados o PDF con serie/modelo? ¿Cuáles tendrían que cambiar para automatización?
7. **Respaldo y seguridad** (`respaldo_generador.py`, `seguridad_generador.py`): ¿algo depende del formato de la serie o del tipo de instalación?
8. **Compatibilidad hacia atrás**: ¿los códigos ya emitidos deben seguir validando igual? ¿Qué se rompería si el código pasara a incluir el tipo de instalación?

## Preguntas de diseño (da tu recomendación, sin implementar)

A. ¿Cómo distinguir los dos tipos? Opciones a evaluar: (1) campo `tipo_instalacion` (`fabricacion` | `automatizacion`) dentro del código de activación, de modo que el instalador sepa qué reglas aplicar; (2) un prefijo del código; (3) un código distinto con otra clave. Indica cuál es más segura y cuál rompe menos.

B. En automatización, ¿el generador debe pedir **serie original**, **modelo original** y además un **identificador propio de Especifika** (para no depender de que la serie ajena sea única o tenga buen formato)? Si sí, ¿cuál sería el identificador y cómo se vincularía con `machine_id`?

C. Qué debe quedar firmado en el código para que el instalador pueda comprobar que el modelo (texto libre del fabricante) no fue alterado en la pantalla: ¿el código cubre `serie + modelo`?

D. Cómo evitar que un código de automatización se use para instalar un equipo de fabricación propia y al revés.

E. Riesgos que ves (trazabilidad, duplicados de serie entre fabricantes, normativa: el equipo mantiene la placa del fabricante original pero el software es nuestro).

## Formato de la respuesta

Un informe corto en español, con referencias `archivo:línea`, una tabla «hoy / necesario para automatización» y tu recomendación para A–D. No edites archivos ni hagas commits.

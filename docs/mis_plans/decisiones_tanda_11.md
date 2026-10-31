# Decisiones — Tanda 11 (ajustes del equipo de pruebas, 23-oct)

Fuente de verdad de la tanda 11. Respuestas de Cristian del 23-oct (16:50). Lo marcado "SUPUESTO" lo dedujo el asistente de las respuestas y está pendiente de que Cristian lo corrija.

## D11-1. Reinicio del software al cambiar la impresora
1. Al **habilitar o deshabilitar** la impresora en Parámetros del equipo: diálogo de confirmación ("Se reiniciará el software para aplicar el cambio"). Con "Cancelar", no se guarda nada.
2. Al confirmar: guardar la bandera con auditoría (como hoy) y luego **reiniciar el software solo**: cierre ordenado igual que "Apagar equipo" (ALL_OFF, cerrar BD y puertos, cerrar backend y UI) pero **sin** apagar Windows, y volver a abrir `Autoclave.exe` en la misma sesión de usuario. SUPUESTO: es automático, no un aviso de "reinicie manualmente".
3. Rechazado en CICLO, igual que las otras acciones de Parámetros del equipo (mensaje en la UI). Permitido en PREPARACION, PREPARADO y FALLA.
4. El reinicio es un mecanismo reutilizable (`reiniciar_software`), auditado (`software_reiniciado`, con motivo). Una sola instancia: el relanzamiento espera a que el proceso anterior y el backend hayan terminado (puerto liberado) antes de arrancar.
5. Si el relanzamiento falla, se registra en el log; el operador ve antes del cierre el mensaje "Si el software no vuelve a abrir en 1 minuto, apague y encienda el equipo".

## D11-2. Retiro de la salida `aire_comprimido_chaqueta`
1. Ningún equipo tendrá aire comprimido a la chaqueta. Fue la decisión desde el inicio; en la planeación se cambió por error.
2. Se retira la función por completo: `io_enabled` de instancias y modelos YAML, `set_io` (`aire_comprimido_chaqueta_on/off`), `_SALIDAS_ENERGIA`, catálogo de funciones de asignación de E/S, Entradas/Salidas (modo prueba), i18n es/en y la documentación de E/S que la liste.
3. **La numeración física de las salidas no cambia**: el canal que ocupaba (índice 12 de `map_do`, DO 13) queda libre/reservado. No se corren las demás salidas, no cambia la trama con la ESP32 ni el firmware. Si el canal sigue existiendo en la trama, se envía siempre en 0.
4. `aire_comprimido_camara` (contrapresión de Líquidos, modo 4, y protocolo de fallo) **no se toca**.
5. Un YAML o asignación de E/S antigua que aún traiga `aire_comprimido_chaqueta` se acepta y se ignora con una advertencia en el log (no impide arrancar).

## D11-3. SEN-03 solo para sensores en uso
1. En PREPARACION y PREPARADO, la alerta SEN-03 (sensor de temperatura del ciclo sin señal) solo se activa para los sensores **en uso** (Principal + Referencias) de los programas seleccionados en ese momento. Con dos pantallas, es la unión de los programas de ambas (la misma lista `programas()` que ya usa PREPARACION).
2. Un sensor que quede "No en uso" en todos esos programas resuelve su SEN-03 (si estaba activa) y no se vigila.
3. Al seleccionar un programa que sí lo usa, la alerta vuelve a evaluarse en el siguiente tick. El bloqueo de inicio (RS-06, `verificar_inicio`) no cambia.
4. Sin programa seleccionado: se aplica la misma regla del Principal (último ciclo ejecutado; sin ninguno, la asignación de fábrica).
5. `temp_drenaje` y los transductores de presión no cambian.

## D11-4. Instalador: Actualizar o Instalación limpia
1. Si hay una versión instalada **igual o más vieja**, el Setup muestra una página con:
   - **Actualizar (conserva los datos)**, marcada por defecto: el flujo actual de actualizar.
   - **Instalación limpia**: borra perfil de instalación, calibración, base de datos, usuarios y demás datos de `%ProgramData%\Especifika\Autoclave`.
   - Con la **misma** versión se conservan además Reparar y Desinstalar de la página de mantenimiento actual; la opción "Reinstalar" de hoy se reemplaza por "Instalación limpia".
2. Instalación limpia: **doble confirmación** (la segunda dice explícitamente que se borran los ciclos registrados y los usuarios). Antes de borrar, se **respalda** la carpeta de datos completa en `%ProgramData%\Especifika\Autoclave_respaldos\AAAAMMDD-HHMMSS\` (fuera de la carpeta que se borra). Si el respaldo falla, no se borra nada y se cancela.
3. Tras una instalación limpia, el primer arranque abre el menú de instalación (no hay perfil).
4. Con una versión instalada más nueva, se sigue negando (sin cambios).

## D11-5. Asociación de los táctiles con las pantallas
1. Con dos paneles idénticos, la asociación táctil↔monitor no se puede deducir: requiere un toque en cada pantalla, una vez. Windows la guarda por puerto USB.
2. Nuevo paso de la estación `06_asociar_tactiles.ps1` (con su `06_revertir_...`), ejecutado por el Setup en "Configurar este PC como estación del autoclave", marcado por defecto, **solo si hay 2 o más monitores**. Abre la herramienta de Windows (`%windir%\System32\MultiDigitizer.exe`, "Configuración de Tablet PC → Configurar → Entrada táctil"), que pide tocar la pantalla que muestra el mensaje y pasar a la siguiente.
3. Al terminar, verifica cuántas asociaciones quedaron (`HKLM\SOFTWARE\Microsoft\Wisp\Pen\Digimon`) y lo escribe en `estacion.log`. Si quedan menos de 2, lo avisa al final del Setup ("Repita la asociación de pantallas táctiles"), sin fallar la instalación.
4. El revertir borra las asociaciones creadas por el paso. `LEEME.md` de la estación: marcar los puertos USB de cada táctil, porque cambiar un cable de puerto deshace la asociación.
5. SUPUESTO: la estación sigue en Windows 11 Pro.

## D11-6. Cuentas Admin e Ingeniero
1. Las dos cuentas semilla pasan a llamarse **`Admin`** e **`Ingeniero`**, tanto en el usuario de inicio de sesión como en el nombre que se muestra.
2. **Solo esas 2 cuentas** quedan protegidas: no se pueden desactivar, borrar, cambiar de rol ni renombrar (usuario y nombre). Se identifican con una marca persistente en la BD (p. ej. columna `cuenta_sistema`), no por el texto del usuario. Sí se puede cambiar o restablecer su contraseña.
3. La UI no ofrece esas acciones para esas cuentas (controles ocultos o deshabilitados) y el backend las rechaza igual (409, con auditoría del intento).
4. El inicio de sesión **no distingue mayúsculas** para ningún usuario (SUPUESTO: aplica a todos, para que nadie quede bloqueado por escribir "admin"). Consecuencia: al crear un usuario se rechaza un nombre que solo difiera en mayúsculas de uno existente. La regla del "último ingeniero activo" se conserva.
5. Migración al arrancar sobre la BD existente: `admin`→`Admin` e `ingeniero`→`Ingeniero` (solo las filas semilla, `creado_por='semilla'`), con la marca de cuenta del sistema, conservando contraseña, `debe_cambiar_clave` y sesiones. Los registros históricos (auditoría, ciclos) no se reescriben; se agrega una fila de auditoría `usuario_renombrado` por cuenta. La migración es idempotente. Si ya existiera otro usuario que choque sin distinguir mayúsculas, no se renombra: se registra en el log y queda como PREGUNTA PARA CRISTIAN.
6. Las BD nuevas nacen con `Admin`/`Ingeniero` y la marca. Las contraseñas iniciales no cambian.

## D11-7. Entradas mostradas: solo sensores en uso y selector por fila
Contexto: los 4 programas no tienen `sensores` en su JSON, así que usan la asignación de fábrica (Principal = Cámara 1, resto No en uso). Por eso Preciclo y Ciclo muestran "—" en la Referencia. Para verla, hay que asignarle el rol Referencia en el programa (Opciones → Parámetros del ciclo → roles de sensor). Esa configuración no la hace Code.
1. **Un sensor de temperatura "No en uso" en el programa no se puede mostrar.** No aparece en el selector, el backend lo rechaza (`PUT /cycle/display-inputs`, 422 `SENSOR_NO_EN_USO`) y Preciclo, Ciclo y la gráfica no lo muestran (desaparece la fila con "—"). Las entradas que no son sensores del ciclo (presión de cámara, chaqueta, drenaje, etc.) siguen disponibles si están habilitadas en el equipo.
2. **Selector por fila** en Opciones → Parámetros del ciclo: tres filas "Entrada 1:", "Entrada 2:" y "Entrada 3:", cada una con un desplegable con las entradas disponibles.
   - La Entrada 1 es obligatoria.
   - Las Entradas 2 y 3 admiten "Ninguna".
   - Una entrada elegida en una fila no aparece en las otras.
   - Se guarda con el botón de guardar existente (sigue el límite de 1 a 3, sin repetir, con auditoría).
   - Mismas reglas táctiles que el resto de Opciones (64 px). Textos en es/en.
3. **Cambio de rol a "No en uso"** de un sensor que el programa está mostrando: se quita de `entradas_mostradas` de ese programa en la misma operación, con auditoría. Si la lista queda vacía, se pone la entrada del Principal.
4. **Programa sin selección propia** (o con un JSON viejo que traiga un sensor No en uso): al presentarlo se filtran los No en uso. La omisión pasa a ser [AI del Principal, primera Referencia si la hay, `pres_camara`], hasta 3. Es la propuesta del asistente y Cristian puede corregirla.
5. Los programas de fábrica siguen sin poder editarse (`editable=false`), pero también se les aplica el filtro de presentación.

# Instrucción para Claude Code — Verificación de I18N-26 (ticket del ciclo)

Pega el bloque siguiente en Claude Code, en `C:\Users\tecni\Documents\codigo_autoclave\`, rama `dev`.

Esta tarea **no cambia código**. El hallazgo I18N-26 no es de idiomas: el ticket del ciclo es registro de esterilización. Conviene ejecutarla **antes** de F1 (no a la vez, para no probar código a medio migrar).

---

```
Tarea: verificar en ejecución el hallazgo I18N-26 (impresión periódica del ticket del ciclo). Es de SOLO LECTURA sobre el repositorio.

Reglas
- No modifiques ningún archivo existente del repositorio, de configuración ni de datos. No hagas commit.
- Responde y redacta todo en español.
- Puedes crear scripts temporales SOLO fuera del repositorio (carpeta temporal del sistema). El único archivo nuevo dentro del repo es el entregable.
- NO envíes nada a una impresora real ni a un puerto serie real. Usa el simulador o dobles (stubs) para la impresora. Si no logras evitar la impresora o el puerto real, detente y pregúntame antes de ejecutar.
- No escribas en la base de datos de desarrollo ni en data\ del repo: usa una copia o una ruta temporal. Si el simulador no permite aislar los datos, detente y pregúntame.
- No toques backend/server.py ni serial_link.py (cambios locales ajenos).
- No asumas: lo que no puedas comprobar ejecutando, márcalo como "no verificado" con el motivo.

Contexto (del inventario F0, hallazgo I18N-26, a verificar, no a dar por cierto)
- cycle_logger.py:70-82: _INTERVALO_PARAM / _INTERVALO_DEFAULT usan las claves W/H/S/E.
- cycle_logger.py:47-56: _FASE_A_CODIGO produce PH/PV/H/S/E/F, y SECADO/DESCOMPRESION dan " ".
- Consecuencia posible: en precalentamiento, prevacío, secado y descompresión no habría intervalo definido, y solo se imprimiría una fila al cambiar de fase o subestado (cycle_logger.py:357-359).
- cycle_logger.py:362 mide el intervalo con time.time(), contra la regla de CLAUDE.md de usar time.monotonic().
- ticket_formatter.py:55 alinea a 1 carácter códigos de 2.
- db_manager.py:57 documenta el esquema como W / H / S / E.

Qué verificar

1. Requisito esperado
   - Busca en docs\ (planes y especificaciones) y en CLAUDE.md qué se espera del ticket: intervalo de impresión por fase y parámetro que lo gobierna. Cita archivo y línea. Si no hay requisito escrito, dilo.

2. Hipótesis H1: filas periódicas por fase
   - Ejecuta un ciclo completo con el simulador (o simula la llamada a cycle_logger con un reloj controlado) pasando por TODAS las fases: PRECALENTAMIENTO, PRE_VACIO, CALENTAMIENTO, ESTERILIZACION, DESCOMPRESION, SECADO y el cierre.
   - Captura las filas que se envían al ticket (con una impresora falsa) y, por cada fase, cuenta cuántas filas se emitieron y cada cuánto tiempo (en segundos del reloj del ciclo).
   - Compara con el intervalo configurado en cada fase. Resultado esperado del informe: tabla fase / intervalo configurado / filas emitidas / intervalo observado / ¿coincide?

3. Hipótesis H2: reloj
   - Confirma qué reloj usa realmente el intervalo (cycle_logger.py:362) y todos los lugares del módulo que miden tiempo.
   - Con un script temporal, simula un salto del reloj del sistema hacia atrás y hacia adelante (por ejemplo, parcheando time.time en el script, no en el repo) y describe el efecto sobre la impresión: filas omitidas, ráfagas o bloqueo.

4. Hipótesis H3: formato
   - Imprime en pantalla/archivo temporal el texto de las filas de ticket de cada fase y verifica si el código de fase de 2 caracteres (PH, PV) rompe la alineación de columnas (ticket_formatter.py:55). Incluye el texto de ejemplo.

5. Coherencia
   - Revisa si el comentario del esquema (db_manager.py:57) y las claves de intervalo coinciden con los códigos que realmente se guardan en lecturas.fase_codigo (PH, PV, H, S, E, F).

Entregable (único archivo nuevo dentro del repo)
docs\mis_plans\verificacion_ticket_ciclo.md, con:
- Requisito encontrado (o ausencia).
- Resultado de H1, H2 y H3 con la evidencia (salidas de la ejecución, no solo lectura de código).
- Qué quedó "no verificado" y por qué.
- Severidad propuesta para cada confirmación, con el formato de hallazgos del proyecto (código I18N-26a, I18N-26b, …).
- Opciones de corrección en lenguaje de planeación (qué habría que cambiar y el riesgo), SIN escribir código ni parches.
- Preguntas abiertas para Cristian.

Informe en el chat (en español): resumen de dos o tres frases por hipótesis (confirmada / refutada / no verificada) y la ruta del entregable.
```

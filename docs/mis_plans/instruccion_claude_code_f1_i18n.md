# Instrucción para Claude Code — F1: Infraestructura de idiomas (i18n)

Pega el bloque siguiente en Claude Code, en `C:\Users\tecni\Documents\codigo_autoclave\`, rama `dev`.

Esta es la **primera fase que modifica código**. No cambia ningún texto visible en español, no agrega selector de idioma y no toca alarmas ni backend (eso es F2 y F3).

---

```
Tarea: F1 del plan de idiomas (español/inglés): infraestructura de catálogo y módulo i18n.

Reglas
- Lee primero docs\mis_plans\planeacion_i18n.md (v3): §2 (decisiones D-13, D-18, D-19, R-05), §3.2 a §3.4 y §5 (F1). Lee también docs\mis_plans\inventario_cadenas_i18n.md, secciones 2 y 9.
- Responde y redacta todo en español.
- NO hagas commit: los cambios quedan en el árbol de trabajo de la rama dev hasta que Cristian confirme visualmente.
- Antes de empezar ejecuta `git status` y repórtame los cambios locales previos. No toques `backend/server.py` ni `serial_link.py` (tienen cambios locales ajenos a esta tarea).
- No agregues dependencias nuevas.
- No asumas: si algo no se puede determinar leyendo el código, detente y hazme la pregunta antes de seguir con esa parte.

Fuera de alcance de F1 (no hacer)
- Parámetro `idioma` en BD, endpoint o selector en Opciones (F2/F3).
- Alarmas, motivos de puerta, motivo_fallo, audit_log (F2).
- Literales fijos de Login.qml, NuevoUsuario.qml y los meses de BarraSuperior.qml (F3).
- Vistas PySide de configuración y UI tkinter.
- Empaquetado (AutoclaveUI.spec).

Orden de trabajo

1. Línea base de comportamiento (antes de cambiar nada)
   - Lee las ~17 copias de tx() y txRuta() en QML y AccionesCiclos._tx en Python. Documenta si son idénticas o difieren (sustitución de placeholders, arrays como fecha.meses, objetos como sensores[], claves de tres niveles como opciones.secciones.*).
   - Escribe pruebas que fijen el comportamiento actual en español: resolución de clave, placeholders con nombre, arrays y objetos. Deben pasar con el código actual antes de migrar.

2. Paquete y catálogo
   - Crea el paquete neutral src/autoclave/i18n/.
   - Mueve es.json desde src/autoclave/ui_qml/assets/textos/ a ese paquete SIN cambiar su contenido ni sus claves (se conservan las 277 claves actuales).
   - Actualiza todos los lugares que lo cargan (ui_qml/app.py:63 y :89-91 y cualquier otro). Lista cualquier módulo fuera de alcance (PySide, tkinter) que lo lea para confirmar que no se rompe.

3. Módulo Python `i18n`
   - Carga es.json y en.json al arrancar y valida que existan.
   - Función `t(clave, idioma=None, **params)`: resuelve el texto del idioma indicado o del vigente.
   - Idioma vigente: estado simple del módulo (por defecto "es") con get/set. En F1 NO se conecta a la BD.
   - Si falta la clave: devuelve el texto en español; si tampoco existe en español, devuelve la clave. En ambos casos registra una advertencia en el log, una sola vez por clave. Nunca devuelve cadena vacía (R-05).
   - Maneja placeholders con nombre, arrays y objetos igual que hoy.

4. en.json (borrador)
   - Crea en.json con exactamente las mismas claves, la misma estructura (arrays con la misma longitud, objetos con las mismas claves) y los mismos placeholders que es.json.
   - Es un BORRADOR sin revisar. Usa los términos de ISO 17665 e IEC 60601-1-8 cuando existan. Unidades y símbolos no se traducen. fecha.meses con abreviaturas en inglés.
   - Crea docs\mis_plans\revision_traducciones.md con una tabla por grupo de claves (alarmas/seguridad, ciclo y fases, Opciones, reportes y correo, Menú, resto) con las columnas: grupo, nº de claves, estado ("borrador sin revisar"), revisor técnico, revisor lingüístico, fecha, observaciones. Marca como "requiere revisión explícita" las claves de alarma y seguridad (el inventario identifica ~20) y anota en observaciones cualquier término técnico dudoso.

5. Singleton QML `I18n`
   - Regístralo siguiendo cómo app.py registra hoy tipos y propiedades. Elige el URI/nombre coherente con el proyecto y dime cuál elegiste.
   - Propiedad `lang` con señal de cambio. Función `t(clave, lang, params)` invocable desde QML (params como objeto JS opcional) y los equivalentes que hagan falta para arrays y objetos, según lo que encuentres en el paso 1.
   - Patrón de uso obligatorio: `text: I18n.t("seccion.clave", I18n.lang)`. Pasar I18n.lang como argumento hace que el binding se re-evalúe al cambiar el idioma.
   - El singleton usa el mismo módulo i18n de Python (una sola lógica).

6. Migración mecánica
   - Reemplaza las ~17 funciones tx()/txRuta() locales en QML por el singleton, y AccionesCiclos._tx por el módulo Python.
   - El texto resultante en español debe ser IDÉNTICO al actual. No renombres claves ni cambies textos.
   - El propio JSON de textos ya no se pasa como propiedad inicial `textosJson` si deja de hacer falta; si algún componente aún lo usa, dilo y déjalo funcionando.

7. Pruebas automáticas
   - Paridad: es.json y en.json con las mismas claves, mismos placeholders, misma estructura y ninguna cadena vacía.
   - Claves referenciadas: toda clave citada literalmente en QML (tx, txRuta) y en Python (t, _tx) existe en es.json y en en.json.
   - Claves dinámicas: para cada familia (estados.*, fases.*, opciones.secciones.*, textoDeResultado, ResumenPeriodo.tx(modelData.clave), sesion.*, validacion.*, usuarios.*, exportacion.*), enumera los sufijos posibles leyendo el código o los enums y comprueba que existen. Lista en el informe los que no pudiste enumerar.
   - Fallback: clave faltante en en → texto en español + advertencia; clave inexistente → la clave + advertencia; nunca vacío.
   - Binding QML: prueba en modo offscreen (QT_QPA_PLATFORM=offscreen) que cambie `lang` entre es y en y verifique que un binding `I18n.t(..., I18n.lang)` se re-evalúa. Si no es viable en este entorno, dilo y por qué.
   - Ejecuta también toda la suite de pruebas existente y reporta cualquier fallo, indicando si ya fallaba antes de tus cambios.

8. Script de claves sin uso (D-19)
   - tools\claves_sin_uso_i18n.py: lista las claves de es.json que no se referencian ni por uso literal ni por familia dinámica.
   - Solo lista. NO borra ninguna clave. Guarda el resultado en docs\mis_plans\claves_sin_uso_i18n.md y no lo agregues a las pruebas automáticas.

Condiciones de parada (detente y repórtame, no sigas)
- Si las pruebas de comportamiento del paso 1 no pasan antes de migrar.
- Si tras la migración el texto en español de alguna clave cambia.
- Si necesitas modificar archivos fuera del alcance indicado.

Informe final (en español, en el chat)
1. Resultado de git status inicial.
2. Archivos creados, movidos y modificados (lista completa).
3. Diferencias encontradas entre las copias de tx().
4. API final del módulo Python y del singleton QML, y el nombre/URI elegido.
5. Resultado de cada prueba (paridad, referencias, dinámicas, fallback, binding, suite existente).
6. Claves dinámicas que no pudiste enumerar.
7. Claves de en.json donde dudaste de la traducción.
8. Decisiones que tuviste que tomar por ambigüedad.
9. Preguntas abiertas y cualquier hallazgo de seguridad o inconsistencia, con código I18N-xx continuando desde I18N-27.
```

---

## Verificación visual de Cristian (después del informe)

Con el idioma en español, abre cada pantalla y confirma que el texto es el mismo de antes de F1:

1. Arranque y espera
2. Login y cambio de clave
3. Menú Principal (tarjetas, resumen, Historial y detalle de ciclo)
4. Preciclo
5. Ciclo en curso (incluye gráfica)
6. Opciones
7. Nuevo usuario
8. Teclados numérico y alfanumérico
9. Exportación a PDF y vista previa del correo

Si todo coincide, confirmas y hacemos el commit.

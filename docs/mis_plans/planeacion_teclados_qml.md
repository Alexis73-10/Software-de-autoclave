# Planeación: teclados en pantalla QML (numérico y alfanumérico), versión 2.1

Destino en el repositorio: `docs/mis_plans/planeacion_teclados_qml.md` (reemplaza la versión 2).
Ejecutor: Claude Code. Responsable de la aprobación visual: Cristian.
Estado: Paso 0b completado. Listos los Pasos 1a y 1b.

## 1. Objetivo

Construir en QML dos teclados táctiles en pantalla, uno numérico y uno alfanumérico, genéricos y reutilizables, más un panel contenedor que los muestra al pie de la pantalla cuando se activa un campo de entrada.

Primer consumidor previsto: el diálogo de identificación de operador de la pantalla de Inicio. La integración con ese diálogo no forma parte de este plan.

## 2. Cambios respecto a versiones anteriores

Versión 2:
- TEC-D01 (versión 1) queda anulada: ya existía lógica de teclado en Python, con pruebas (commit 23d9466). Se reutiliza y se ajusta.
- Se incorporan especificaciones del diseñador no contempladas antes: animación de apertura, tiempo mínimo de tecla presionada, alto máximo, encabezado de contexto, borrado total por pulsación larga.

Versión 2.1:
- El punto decimal rige en toda la interfaz, entrada y presentación. Se revocan D-18 y D-19 del plan `planeacion_ui_dual_pantalla.md` (decisión de Cristian). Nuevo Paso 1b.
- Medidas de tecla 96 x 88 px usadas tal cual con `Escala` de 1200 (verificado en el Paso 0b).
- `PanelTeclado` es un componente propio en `Main.qml`. No se reutiliza `PanelModal`.
- Se agrega la sección 5 de valores provisionales, aprobados por Cristian mientras el diseñador no responde.
- La lógica de teclado se amplía sin romper contratos ajenos: fuera de sus pruebas, ningún código usa hoy los controladores.

## 3. Arquitectura

- Lógica de entrada en Python puro (`domain/`), con pruebas automáticas. Ahí viven las reglas de la sección 7.
- Controladores QObject (`controllers/`, registrados como `Autoclave.Controllers 1.0`) que exponen esa lógica a QML.
- QML solo presenta y transmite toques. Componentes: `Tecla`, `TecladoNumerico`, `TecladoAlfanumerico`, `PanelTeclado`.
- Sin Qt Quick Test en el repositorio. La verificación combina pytest de dominio y controlador, la prueba existente que carga `Main.qml` sin avisos, y verificación manual en pantalla real.
- Componentes QML propios, sin Qt Virtual Keyboard, para no añadir un SOUP en Clase C.
- `PanelTeclado` se declara en `Main.qml` después del `StackView`, dentro del `Item` escalado y recortado, con `z` mayor, y se inyecta como propiedad `teclado` a cada pantalla, igual que ya se inyectan `textosJson` y `puente`. Los campos llaman `teclado.abrirNumerico(...)` o `teclado.abrirAlfanumerico(...)`. Cada ventana (una por puerta) tiene su propia instancia.
- `PanelModal` no se usa: tapa el campo activo, se cierra tocando el fondo (un Cancelar implícito), no tiene animación ni señales, y adaptarlo rompería `PanelNotificaciones` y `PanelEquipo`.
- Fuera de alcance de archivos: `.worktrees/roles-sensor-temperatura/` contiene una copia anterior de `TecladoNumerico.qml` con coma. No se toca ni se reutiliza.

## 4. Decisiones confirmadas

- TEC-D02. Teclado numérico: dígitos 0-9, tecla de signo, punto decimal, Borrar, Cancelar y Confirmar. Sin coma.
- TEC-D03. Teclado alfanumérico:
  - Letras A-Z incluida la Ñ, sin tildes, con tecla de cambio Aa.
  - Dígitos 0-9.
  - Símbolos (11): `@ . _ - ( ) ? + * / =`
  - Barra espaciadora, Borrar, Cancelar y Confirmar.
  - Tres capas: letras, dígitos (123) y símbolos (@._).
- TEC-D04. Cada tecla tiene estado normal y estado presionado, sin hover. Presionado: relleno `#E2ECFD` y borde `#1168F6`, visible al menos 90 ms. No existe estado deshabilitado.
- TEC-D05. Tecla Aa de un solo uso: un toque pone en mayúscula solo la siguiente letra y luego vuelve a minúscula. Estado inicial: mayúscula. Afecta solo a letras. Mientras está armada, la tecla se muestra marcada.
- TEC-D06. Panel anclado al pie, visible solo al activarse un campo. La posición es una propiedad configurable. Apertura de 400 ms con `cubic-bezier(0.2,0,0,1)`, entrando desde el borde inferior. Alto máximo: 45 % de la pantalla. El panel expone `alturaOcupada` para que cada pantalla se desplace y deje el campo activo por encima del teclado.
- TEC-D07. Cancelar descarta lo escrito y cierra sin entregar valor. Ubicación: numérico, la celda vacía sobre Borrar; alfanumérico, ver PROV-03. Estilo neutro (gris, sin rojo ni azul).
- TEC-D08. Numérico: el campo entrega `minimo`, `maximo` y `decimales`, además de `titulo` y `unidad`. Se bloquean entradas inválidas mientras se escribe. Confirmar fuera de rango no cierra el panel y muestra el rango. Nunca se entrega un valor inválido. El backend mantiene su validación de rango como barrera final.
- TEC-D09. Alfanumérico: `longitudMaxima` como propiedad; al alcanzarla no se agregan más caracteres. Confirmar entrega el texto tal cual, incluido vacío. Cada pantalla valida su contenido.
- TEC-D10. Teclados genéricos. En esta etapa solo se prevé el diálogo de operador (nombre de hasta 30 caracteres). Los demás campos se conectan en sus propios planes.
- TEC-D11. Separación entre teclas: 14 px en ambos teclados (el diseñador dibujó 12 px y 10 px). Tamaño de tecla 96 x 88 px, radio 12 px, usados tal cual con `Escala` de 1200. Reescalarlos por 1200/1080 haría que la fila 2 del alfanumérico (1108 px con 14 px de separación) no cupiera.
- TEC-D12. Borrar: un toque elimina el último carácter. Mantenido 600 ms elimina todo el campo, una sola vez. Sin autorepetición.
- TEC-D13. Encabezado visible sobre el teclado. Numérico: nombre del parámetro, valor que se escribe, unidad y rango. Alfanumérico: nombre del campo y valor.
- TEC-D14. Punto decimal en toda la interfaz, en entrada y en presentación. Se revocan D-18 (coma en la entrada numérica) y D-19 (coma en presentación). La persistencia, la API y el JSON siguen usando punto, como hasta ahora. La revocación se anota en `docs/mis_plans/planeacion_ui_dual_pantalla.md`.
- TEC-D15. Las reglas de la sección 7 se implementan y prueban en el dominio Python. QML no contiene reglas de validación.

## 5. Valores provisionales (aprobados por Cristian, pendientes del diseñador)

Se centralizan en un único lugar, marcados `PROVISIONAL`, para reemplazarlos con un cambio puntual cuando responda el diseñador. Code reporta dónde los centralizó.

- PROV-01. Tipografía de las teclas: reutilizar el estilo de botón que ya exista en `Tipografia` (Code reporta cuál), con texto de 28 px como mínimo. No se define un estilo nuevo.
- PROV-02. Aspecto de Aa activa: reutilizar el estilo de estado presionado (relleno `#E2ECFD`, borde `#1168F6`) mientras la tecla esté armada.
- PROV-03. Cancelar en el alfanumérico: fila 4, entre `@._` y el espacio, y el espacio cede el ancho necesario. Aa, 123, `@._`, Borrar y Confirmar quedan donde el diseñador los puso. Estilo gris neutro. Code reporta los anchos resultantes de la fila y Cristian aprueba visualmente.
- PROV-04. Mensaje de valor fuera de rango: `Rango: {mínimo} a {máximo} {unidad}`, en `es.json`, marcado como pendiente. Los números se muestran con punto.

## 6. Restricciones heredadas del proyecto

- Lienzo de diseño 1200 x 1920 px. Todas las medidas pasan por `Escala.px()`.
- Área táctil mínima 68 x 68 px. Operación con dedo desnudo.
- Texto mínimo 22 px, normal 28 px. Usar `pixelSize`, nunca `pointSize`.
- Colores, tipografía (Montserrat) y radios salen de `Colores`, `Tipografia` y `Escala` (en `qml/Tema/`) y de la especificación del diseñador. No se codifican valores sueltos.
- SVG Tiny 1.2: atributos de presentación, texto convertido a trazos, sin filtros ni CSS incrustado.
- Textos desde `assets/textos/es.json`. No hay cadenas fijas en los `.qml`.
- El teclado no modifica ningún valor hasta que Confirmar lo entrega. Cancelar no entrega nada.
- No se toca backend, login PySide, vistas PySide ni código tkinter. Excepción: los archivos que el Paso 1b nombra expresamente.

## 7. Reglas de comportamiento

Numérico:
- La tecla de signo alterna el signo del valor completo. Con el campo vacío deja un `-` pendiente. Está bloqueada si `minimo` es mayor o igual a 0.
- Un solo punto decimal, y solo si `decimales` es mayor que 0. La coma no se acepta.
- No se acepta un dígito que exceda `decimales` posiciones tras el punto.
- Se permiten valores intermedios que luego resulten válidos (por ejemplo `-` o `1` de camino a `-100`). La comprobación de rango se hace sobre el valor completo al confirmar.
- Confirmar con texto vacío, parcial (`-`, `.`, `-.`) o fuera de `[minimo, maximo]`: no cierra, no entrega valor y muestra el rango.

Alfanumérico:
- Aa según TEC-D05. Ñ y ñ siguen la misma regla que las demás letras. Sin tildes.
- Longitud limitada por `longitudMaxima`.
- El cambio de capa no altera el texto ni la señal de confirmación.

Ambos:
- Borrar según TEC-D12: el toque se resuelve al soltar si duró menos de 600 ms. La pulsación larga dispara el borrado total al cumplirse 600 ms y no genera además un borrado de un carácter. La temporización se modela como función pura con marcas monotónicas para poder probarla.

## 8. Interfaz propuesta

Propiedades de entrada:
- Numérico: `titulo`, `unidad`, `valorInicial`, `minimo`, `maximo`, `decimales`.
- Alfanumérico: `titulo`, `valorInicial`, `longitudMaxima`.
- Panel: `posicion` (por defecto, pie de pantalla).

Salidas:
- `confirmado(valor)`: solo con Confirmar y valor válido.
- `cancelado()`.
- Panel: `alturaOcupada`.

## 9. Pasos para Claude Code

Regla general: rama `dev`, sin push, sin commit hasta que Cristian confirme visualmente. Reportar y esperar al final de cada paso. Si aparece un conflicto con este plan, detenerse y reportar. No inventar distribución ni estilos fuera de la sección 5.

Paso 0b. Completado. Su informe se incorporó en las secciones 3, 4 y 10.

Paso 1a. Dominio y controladores sin tocar el separador decimal.
- Primero actualizar las pruebas a las reglas de la sección 7 y verificar que fallen donde corresponde.
- Alfanumérico: Aa de un solo uso con inicio en mayúscula; tres capas modeladas como conjuntos de caracteres (dígitos y los 11 símbolos), no como filas; eliminar `# $ % & ! , ; :`; `longitudMaxima`, `titulo`, `valorInicial`; Confirmar emite `confirmado(texto)` con el texto tal cual.
- Numérico: signo que alterna el valor completo; Confirmar inválido sin emisión y con mensaje de rango; `titulo`, `unidad`, `valorInicial`.
- Ambos: borrado por pulsación larga como función pura.
- No tocar `agregar_coma`, `parsear_decimal`, `formatear_decimal`, `decimales` ni `domain/formato_numerico.py`.
- Ejecutar `python -m pytest -q -p no:cacheprovider` y reportar.

Paso 1b. Separador decimal: punto en entrada y presentación (TEC-D14).
- Archivos autorizados por nombre: `domain/formato_numerico.py`, `domain/pantalla_ciclo.py`, `bridge/ui_bridge.py`, `tests/test_formato_numerico.py`, `tests/test_pantalla_ciclo.py`, más los de dominio y controlador numérico de teclado.
- Antes de editar, buscar en `src/`, `tests/` y `assets/textos/es.json` cualquier otra dependencia de coma decimal. Si aparece alguna fuera de la lista, detenerse y reportarla sin modificarla.
- Actualizar primero las pruebas: `parsear_decimal` acepta punto y rechaza coma; `formatear_decimal` presenta con punto (`134.0`); la prueba `test_temperatura_con_un_decimal_y_coma` se reemplaza por su equivalente con punto.
- Agregar `decimales` y la tecla de punto al numérico según la sección 7.
- Anotar la revocación de D-18 y D-19 en `docs/mis_plans/planeacion_ui_dual_pantalla.md`, sin reescribir el resto del documento.
- Ejecutar pytest y reportar.

Paso 2. `Tecla`: estados normal y presionado (90 ms mínimo), medidas de la sección 6, texto o ícono por propiedad. Agregar a `es.json` las cadenas nuevas (Borrar, Cancelar, etc.) sin duplicar las existentes. Aplicar PROV-01.

Paso 3. `TecladoNumerico` con encabezado (TEC-D13), distribución completa del diseñador (Cancelar en la celda sobre Borrar, Confirmar en dos filas), conectado al controlador.

Paso 4. `TecladoAlfanumerico`, capa de letras, conectado al controlador. Aplicar PROV-02 y PROV-03. Dejar preparada la estructura de capas sin colocar caracteres en 123 y @._.

Paso 5. `PanelTeclado` en `Main.qml`: anclaje al pie con `posicion`, animación de 400 ms, alto máximo 45 %, `alturaOcupada`, señales `confirmado` y `cancelado`, un teclado activo a la vez, inyección como propiedad `teclado` a las pantallas existentes.

Paso 6. Pantalla de prueba desechable con un campo numérico y uno alfanumérico, marcada como prueba y sin enlace a la navegación de producción. Ejecutar pytest y la prueba de carga de `Main.qml`. Esperar la confirmación visual de Cristian antes de cualquier commit.

Paso 7 (bloqueado hasta recibir las mesas del diseñador). Capas 123 y @._ del alfanumérico con la posición exacta de cada carácter. El alfanumérico no se da por terminado sin este paso.

## 10. Casos de verificación en pantalla real

Numérico (mínimo -100, máximo 400, decimales 1):
1. `134.5` y Confirmar: entrega `134.5`.
2. Segundo punto: no se agrega. Segundo decimal (`134.55`): no se agrega. La coma no existe como tecla.
3. Tecla de signo con valor escrito: invierte el signo del valor completo. Con campo vacío: deja `-` pendiente.
4. `500` y Confirmar: no cierra, muestra el rango. `-` solo y Confirmar: no cierra.
5. Con mínimo 0: la tecla de signo no actúa.
6. Toque corto en Borrar: quita un carácter. Mantener 600 ms: vacía el campo. Un toque corto no vacía el campo.
7. Cancelar: cierra sin señal `confirmado`.
8. El encabezado muestra parámetro, valor, unidad y rango, con punto decimal.

Alfanumérico (longitud máxima 30):
1. Al abrir, la primera letra sale en mayúscula y las siguientes en minúscula.
2. Aa armada: solo la siguiente letra en mayúscula, y la tecla se ve marcada mientras está armada.
3. Ñ/ñ según estado. No existen teclas con tilde.
4. Dígitos y símbolos de TEC-D03 escriben el carácter correcto (tras el Paso 7).
5. Al llegar a 30 caracteres no se agregan más.
6. Espacio, Borrar (corto y largo), Cancelar y Confirmar funcionan. Confirmar con texto vacío entrega texto vacío.
7. Cambio de capa conserva el texto escrito.

General:
1. Ninguna tecla mide menos de 68 x 68 px ni queda a menos de 14 px de otra, comprobado con regla en la pantalla real.
2. Estado presionado visible al menos 90 ms en cada tecla.
3. Animación de apertura de 400 ms y alto del panel no superior al 45 % de la pantalla.
4. Prueba con dedo desnudo y toques rápidos sucesivos.
5. `alturaOcupada` correcto: el campo de prueba queda por encima del teclado.
6. Coherencia del separador: la pantalla de ciclo muestra temperatura y presión con punto (`134.0`), igual que el teclado.

## 11. Riesgos y puntos abiertos

- R-01 (resuelto por diseño). El desplazamiento de la pantalla al abrir el teclado lo define el diseñador y se implementa con `alturaOcupada`. Cada pantalla consumidora debe aplicarlo al integrarse.
- R-02. Capas 123 y @._ sin posición de caracteres. Bloquea el Paso 7.
- R-03. Regresión por el cambio de separador. Se acota con la búsqueda previa del Paso 1b y con pruebas actualizadas antes que el código. Si alguien lee un valor con coma desde otro lugar no listado, el Paso 1b lo reporta.
- R-04. Separación de 14 px frente a 12 y 10 px del diseño. Notificar al diseñador; si objeta, decide Cristian.
- R-05. Cancelar no está en el diseño. Su ubicación en el alfanumérico (PROV-03) es provisional.
- R-06. `medidas.csv` fija el objetivo táctil mínimo en 96 x 96 px (110 px en pantalla de 7"). Las teclas de 96 x 88 cumplen el mínimo de 68 px de este proyecto pero no el del diseñador. Pendiente de aclarar con él.
- R-07. El dibujo de la capa de letras no cumple sus propias cotas (Aa más angosta que una tecla, espacio de unas 4.4 teclas en lugar de 5, anchos de teclas especiales sin acotar). Se resuelve con la aprobación visual y con la mesa del diseñador.
- P-01. Tipografía, peso y tamaño del texto de las teclas: pendiente del diseñador (PROV-01).
- P-02. Aspecto de la tecla Aa activa: pendiente del diseñador (PROV-02).
- P-03. Texto completo del mensaje de valor fuera de rango: pendiente del diseñador (PROV-04).
- P-04. Posición definitiva del panel: puede cambiar tras discusión con el diseñador; la propiedad `posicion` lo permite.

## 12. Pendientes del diseñador

1. Mesas de las capas 123 y @._ con la posición de cada carácter.
2. Tipografía, peso y tamaño del texto de las teclas.
3. Ubicación y estilo definitivos de CANCELAR en ambos teclados.
4. Aspecto de la tecla Aa activa.
5. Texto completo del mensaje de valor fuera de rango.
6. Aviso de que la separación se implementa en 14 px.
7. `medidas.csv` fija 96 x 96 como objetivo táctil y las teclas miden 96 x 88: ¿se mantiene 88 de alto?

## 13. Fuera de alcance

- Integración con el diálogo de operador o con cualquier otra pantalla.
- Cambios en backend, sesión, login, permisos.
- Migración de las vistas PySide de configuración.
- Registro de operadores y su tabla.
- Cambios en `.worktrees/`.

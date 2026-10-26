# LEEME — Instalación en el equipo de pruebas (compilación I, 2026-10-24)

Lista de comprobación para Cristian. Hoy solo se hace:
1. la instalación con el asistente;
2. la verificación de Entradas/Salidas;
3. la calibración de sensores.

Los ciclos NO se corren hasta el lunes 26-oct.

Lo marcado **[verificar en sitio]** no se pudo comprobar sin el equipo: se revisó en el código y con el simulador, sin tarjeta ni PC industrial.

> **Tanda 17 (26-oct), desde la 1.0.0-alpha.2: carpetas nuevas (INS-02) y zona horaria en el Setup (INS-01).** Ver la sección **«1.0 Instalar con el Setup (alpha.2 en adelante)»**. En el resto de este documento, que describe compilaciones anteriores:
> - donde dice `C:\ProgramData\Especifika\Autoclave`, lea **`X:\Especifika\Autoclave\datos`**;
> - donde dice `C:\Program Files\Especifika\Autoclave`, lea **`X:\Especifika\Autoclave\programa`**;
> - donde dice `C:\ProgramData\Especifika\Autoclave_respaldos`, lea **`X:\Especifika\Autoclave_respaldos`**;
>
> con `X:` la unidad elegida en el Setup (p. ej. `D:`). La ruta exacta queda en el registro: `reg query HKLM\SOFTWARE\Especifika\Autoclave /v RutaDatos` (y `/v RutaPrograma`). **Un equipo con la I o anterior (o la alpha.1) no se actualiza:** el Setup se detiene y pide desinstalar primero; los datos anteriores quedan en `C:\ProgramData\Especifika\Autoclave` y no se trasladan (ver 1.0).

Versión de este documento: P1 de la tanda 7 (actualizada en la tanda 17, s1, con la sección 1.0 y las carpetas nuevas), completada en K2 (22-oct, 08:10) con la sección "A frente a B", en K8 de la tanda 8 (22/23-oct) con las secciones "Actualizar un equipo ya instalado (B → C)" (8b) y "B frente a C", y en K9 de la tanda 9 (23-oct) con "B frente a D" y la sección 8c (B → D con el Setup), y en la compilación E (23-oct) con "Cambios respecto a la D" y la sección 8d (Instalar con el Setup E, página "Autoclave ya está instalado"), y en K10 de la tanda 10 (23-oct) con "Cambios respecto a la E" y la sección 8e (E → F y D → F con el Setup), y en K11 de la tanda 11 (23-oct) con "Cambios respecto a la F" y la sección 8f (F → G con el Setup, página «Actualizar / Instalación limpia»), y en K12 de la tanda 12 (24-oct) con "Cambios respecto a la G" y la sección 8g (G → H con el Setup), y en K13 de la tanda 13 (24-oct) con "Cambios respecto a la H" y la sección 8h (H → I y G → I con el Setup).

> **Tanda 13 (2026-10-24, noche): instale la compilación I (`entrega/2026-10-24_i/`, etiqueta `inst-2026-10-24-i`) con `Autoclave_Setup_1.0.0-i.exe` EN LUGAR DE LA H, siguiendo la sección 8h (H → I, o G → I si el equipo sigue en la G; deje marcada «Actualizar (conserva los datos)»), antes de los ciclos del lunes 26-oct.** La I es la H más VAP-01: la presión de saturación del vapor pasa a las tablas IAPWS-IF97 (304,2 kPa a 134 °C; la H calculaba 302,3, unos 2 kPa de menos), y además trae la Licencia L0 de abajo. Tabla «Cambios respecto a la H». Las cifras del bloque T12 de la hoja de banco ya están recalculadas para la I.

> **Licencia L0 (24-oct, incluida desde la compilación I; la H no la tiene).**
> - **Secretos de activación rotados.** Los secretos con que se generaban el código de instalación y la clave de fábrica estaban en el código, y el repositorio fue público: se consideran **comprometidos** y quedan en el historial de git (no se reescribe). A partir de la siguiente compilación salen de un archivo fuera del repositorio (`%USERPROFILE%\Documents\especifika_secretos\activacion.json`), que Cristian crea con `python tools\secretos\generar_secretos.py`. **Los códigos del generador anterior dejan de servir**: el autoclave y `GeneradorCodigos.exe` se compilan con el mismo archivo nuevo, y sin él ninguno de los dos se compila o arranca. La huella de 8 caracteres que muestra la compilación debe coincidir con la de la página **Usuarios** del generador.
> - **Contraseñas en el asistente.** El asistente trae un paso nuevo, **Contraseñas** (antes del resumen, también al reinstalar): se fijan las de `Admin` e `Ingeniero`, cada una con confirmación, distintas de las de fábrica y entre sí. Con eso ya no piden cambio en el primer ingreso y la sección 5 deja de aplicar a un equipo instalado así.
> - **Equipo ya instalado** que conserve una contraseña de fábrica: aviso no bloqueante **SIS-07** en la bandeja de Preciclo y la campana, visible solo con sesión de técnico o ingeniero. Se quita solo al cambiar la contraseña.
> Detalle: `docs/informes/licencia/L0_secretos_y_contrasenas.md`.

> **Tanda 12 (2026-10-24): instale la compilación H (`entrega/2026-10-24_h/`, etiqueta `inst-2026-10-24-h`) con `Autoclave_Setup_1.0.0-h.exe`, siguiendo la sección 8g («Actualizar G → H»: deje marcada «Actualizar (conserva los datos)»), antes de los ciclos del lunes 26-oct.** La H es la G más las correcciones de proceso de CALENTAMIENTO, ESTERILIZACION y chaqueta pedidas el 24-oct (C-01 a C-13, tabla «Cambios respecto a la G»). Lo que hay que observar el lunes está en el bloque T12 de la hoja de banco.

> **Tanda 11 (2026-10-23): instale la compilación G (`entrega/2026-10-23_g/`, etiqueta `inst-2026-10-23-g`) con `Autoclave_Setup_1.0.0-g.exe`, siguiendo la sección 8f («Actualizar F → G»: en la página nueva deje marcada «Actualizar (conserva los datos)»), sin copiar archivos a mano.** La G es la F más los ajustes pedidos el 23-oct tras usar la F (tabla «Cambios respecto a la F»). Las cuentas `admin`/`ingeniero` pasan solas a `Admin`/`Ingeniero` con la misma contraseña.

> **Tanda 10 (2026-10-23): instale la compilación F (`entrega/2026-10-23_f/`, etiqueta `inst-2026-10-23-f`) con `Autoclave_Setup_1.0.0-f.exe`, siguiendo la sección 8e («Actualizar E → F», y D → F si el equipo aún tiene la D), sin copiar archivos a mano.** La F es la E más las correcciones vistas en el equipo el 23-oct (tabla «Cambios respecto a la E»). La letra E ya estaba usada por la compilación de esta mañana, por eso esta se llama F.

> **Compilación E (23-oct): la D falló en el PC de pruebas (ver "Cambios respecto a la D"). Instale la E (`entrega/2026-10-23_e/`, etiqueta `inst-2026-10-23-e`, commit cafb06e) con `Autoclave_Setup_1.0.0-e.exe`: siga la sección 8c con el Setup E en lugar del de la D, y lea la 8d.** El código del programa es el de la D más las 2 correcciones; todo lo dicho de la D vale para la E.

## Cambios respecto a la H

| | Compilación H (`2026-10-24_h`) | Compilación I (`2026-10-24_i`) |
|---|---|---|
| Suite en ese código | 7531 passed, 10 skipped, 3 xfailed | **7817 passed, 10 skipped, 3 xfailed** (7808 con -n auto + 9 que pasan en serie; 2 rojas ajenas del PC de desarrollo, `test_config_correo`, igual que en L0) |
| Presión de saturación (VAP-01, tanda 13) | Ecuación de Antoine: `Psat(121) = 204,3`, `Psat(134) = 302,3`, `Psat(140) = 359,0` kPa (≈ 2 kPa de menos en la zona de trabajo) | **IAPWS-IF97, región 4** (la tabla de vapor de referencia): `Psat(121) = 205,0`, `Psat(134) = 304,2`, `Psat(134,5) = 308,7`, `Psat(140) = 361,5` kPa |
| Lo que cambia por eso (a 134 °C, `presion_add` 9) | Falla por presión baja de esterilización bajo 300,3 kPa; techo 311,3 kPa; consigna de chaqueta ≈ 326,3 kPa; entrada a sostener con P ≥ 300,3 kPa | Falla por presión baja bajo **302,2 kPa**; techo **313,2 kPa**; consigna de chaqueta **≈ 328,2 kPa**; entrada a sostener con P ≥ **302,2 kPa**. Igual corren ≈ +2 kPa las bandas de PWM, la coherencia T–P, la detección de aire (CIC-12/13), las validaciones 350/385 kPa, la contrapresión de líquidos y la consigna de presión de la gráfica del PDF (304,2 kPa a 134 °C). F0 no cambia |
| Programas | — | Sin cambios: sus parámetros son temperaturas y diferencias. Los de fábrica, los de usuario del repositorio y los del equipo (G y G → H) se validan con la tabla nueva sin errores |
| Licencia L0 | No | Sí: secretos de activación rotados, paso **Contraseñas** en el asistente y aviso **SIS-07** si una cuenta conserva la contraseña de fábrica (aviso de L0 arriba) |
| Versión del Setup | `1.0.0-h` (`AppVerNum` 1.0.0.8) | `1.0.0-i` (`AppVerNum` 1.0.0.9) |

## Cambios respecto a la G

| | Compilación G (`2026-10-23_g`) | Compilación H (`2026-10-24_h`) |
|---|---|---|
| Suite en ese código | 7218 passed, 10 skipped, 3 xfailed | **7531 passed, 10 skipped, 3 xfailed (7522 con -n auto + 9 que pasan en serie)** |
| CALENTAMIENTO (C-01, C-02, C-09) | El objetivo de presión sumaba `presion_add_calentamiento`; techo en 2×`presion_add`; corte por calidad de vapor en el 97 % de la temperatura | `presion_add_calentamiento` es solo techo: entra a sostener con `T ≥ T_obj` y `P ≥ Psat(T_obj) − 2 kPa`; techo `Psat(T_obj) + presion_add`; con sólidos exige que la presión corresponda a vapor saturado (`|Tsat(P) − T| ≤ 1 K`); corte por calidad de vapor desde `T_obj − 3 K` |
| ESTERILIZACION: fallas (C-07, C-03) | 3 lecturas seguidas | **5 s continuos**. Nuevas, solo con sólidos: CIC-12 (aire o gases no condensables, `Tsat(P) − T > 2 K`) y CIC-13 (vapor sobrecalentado o falla de la sonda, `< −2 K`) |
| ESTERILIZACION: control (C-08) | RECUPERACION ↔ PWM podía conmutar en cada lectura; en RECUPERACION, sin techo | Salida de RECUPERACION con histéresis (+0,3 K y +1 kPa); en RECUPERACION el vapor se corta en el techo y no vuelve a abrir hasta bajar 2 kPa |
| Referencias en la exposición (C-13) | Una Referencia fuera de rango solo daba aviso (CIC-09); una Referencia sin lectura abortaba el ciclo | Fuera de banda más de 5 s: el conteo se detiene y al volver **reinicia desde cero** (F0 no); sin volver en `timeout_excursion_referencia` (5 min) → FALLO CIC-14; cada excursión en el ticket. **Sin lectura:** el ciclo sigue, aviso SEN-11 y ticket y registro con «NO CONFORME: punto de referencia sin verificar»; sin apertura automática |
| Sin lectura del Principal o de la presión (C-10) | FALLO SEN-02 / SEN-04 | Igual; además, la fase no cuenta ese tiempo como exposición y corta el vapor |
| Chaqueta en CICLO (C-05) | `presion_chaqueta ± rango_presion_chaqueta` | Consigna calculada del programa: `max(Psat(T_est + 1,5), Psat(T_est) + presion_add_esterilizacion + 15)`, banda ±10 kPa (134 °C/9 → ≈ 326,3 kPa). En PREPARADO sigue `presion_chaqueta` |
| Validación de programas (C-04, C-05.9) | `presion_add_*` hasta 100 | Máximo 30 kPa; se rechaza un programa con techo de cámara, consigna de chaqueta + 10 o `presion_chaqueta + rango` ≥ 385 kPa (alivio); por encima de 350 kPa (suministro) solo advertencia |
| Bowie & Dick de usuario (C-04.4) | `presion_add_calentamiento` 99 | Al abrir la H baja **a 9**, con fila en la bitácora de auditoría (origen «migración tanda 12»), aviso no bloqueante **SIS-06** en Preciclo y en la campana, y el archivo anterior en `bowe_dick.json.bak` |
| `brecha_segura_temperatura` (C-07.1) | 0,3 | 1,0 en los programas nuevos y de fábrica. **Los programas de usuario del equipo conservan 0,3** (ver 8g y hoja de banco T12) |
| Versión del Setup | `1.0.0-g` (`AppVerNum` 1.0.0.7) | `1.0.0-h` (`AppVerNum` 1.0.0.8) |

## Cambios respecto a la F

| | Compilación F (`2026-10-23_f`) | Compilación G (`2026-10-23_g`) |
|---|---|---|
| Suite en ese código | 6993 passed, 10 skipped, 3 xfailed | **7218 passed, 10 skipped, 3 xfailed (7216 con -n auto + 2 que pasan en serie)** |
| Impresora en Parámetros del equipo (D11-1) | El cambio se guardaba pero no se aplicaba hasta reiniciar a mano | Al habilitarla o deshabilitarla pide confirmar («Se reiniciará el software para aplicar el cambio»); con Cancelar no se guarda nada. Al confirmar guarda, cierra el software de forma ordenada (todas las salidas apagadas, sin apagar Windows) y lo vuelve a abrir solo. Rechazado en CICLO, con el estado seguro actuando o con una confirmación pendiente. Si no vuelve a abrir en 1 minuto: apagar y encender el equipo |
| Salida `aire_comprimido_chaqueta` (D11-2) | Aparecía en Entradas/Salidas (DO 13) | Retirada por completo. **DO 13 queda libre** y siempre en 0; las demás salidas conservan su número, la trama con la tarjeta y el firmware no cambian. `aire_comprimido_camara` (DO 14) sin cambios |
| SEN-03 en Preciclo (D11-3) | Saltaba para cualquier sonda de temperatura sin señal, aunque el programa no la usara | Solo para las sondas **en uso** (Principal y Referencias) de los programas vigentes; una sonda «No en uso» desconectada no da aviso. El bloqueo de inicio (RS-06) no cambia |
| Setup sobre una instalación existente (D11-4) | Reparar / Reinstalar / Desinstalar | Con versión igual o más vieja: **Actualizar (conserva los datos)**, marcada, o **Instalación limpia** (borra perfil, calibración, base de datos y usuarios, con doble confirmación y respaldo previo en `C:\ProgramData\Especifika\Autoclave_respaldos\<fecha>\`). Con la misma versión, además Reparar y Desinstalar. Con una versión más nueva se sigue negando |
| Táctiles con dos pantallas (D11-5) | Sin asociación táctil↔pantalla | Paso 06 de la estación: abre la herramienta de Windows para tocar cada pantalla (solo con la casilla de estación marcada y 2 o más monitores; **en el equipo de pruebas la casilla sigue desmarcada**) |
| Cuentas iniciales (D11-6) | `admin` / `ingeniero` | **`Admin` / `Ingeniero`** (misma contraseña), protegidas: no se pueden desactivar, borrar, cambiar de rol ni renombrar. El usuario no distingue mayúsculas al iniciar sesión |
| Entradas mostradas (D11-7) | Lista de casillas; Preciclo y Ciclo mostraban «—» para sondas «No en uso» | Opciones › Parámetros del ciclo: filas «Entrada 1/2/3» con desplegable (la 1 obligatoria, 2 y 3 admiten «Ninguna»). Una sonda «No en uso» en el programa no se ofrece ni se muestra en Preciclo, Ciclo ni la gráfica |
| Versión del Setup | `1.0.0-f` (`AppVerNum` 1.0.0.6) | `1.0.0-g` (`AppVerNum` 1.0.0.7) |

## Cambios respecto a la E

| | Compilación E (`2026-10-23_e`) | Compilación F (`2026-10-23_f`) |
|---|---|---|
| Suite en ese código | — (la E es la D, 6606 passed, más 2 correcciones de empaquetado) | **6993 passed, 10 skipped, 3 xfailed (6990 con -n auto + 3 que pasan en serie)** |
| Código de activación (D10-2) | Rechazaba `FR4QAXQ3043N` (cero) cuando el generador mostraba `FR4QAXQ3O43N` (letra O) | Acepta el código con 0/O, 1/I y 8/B confundidos, sin espacios ni guiones; un código de otro día sigue siendo inválido. El generador muestra los códigos en letra monoespaciada que distingue O de 0 |
| CIC-10 sin sensor de presión de cámara (D10-3) | La acción pedía revisar la sonda Principal | Motivo y acción dicen que sin el sensor de presión de cámara no se puede llevar la cámara a estado seguro y piden revisar su conexión o llamar a servicio técnico (es y en). **Mismo comportamiento** que la D/E (NO ABRIR, sin bloquear login, modo prueba, cambio de programa ni apagado) |
| Pantalla 2 durante la instalación (D10-4) | La pantalla 2 iba al menú y mostraba ARR_PERFIL | Muestra Reposo con «Instalación en curso en la pantalla 1» y pasa sola al flujo normal al terminar el asistente. Una sola pantalla: sin cambios |
| Textos que no caben (D10-1) | Se encogían o se cortaban (tarjeta de Ciclo/Preciclo, alarmas, Reportes, Historial) | Lo que no cabe se abrevia (p. ej. «Temp. ester.», «Pres. chaqueta»); lo que cabe se muestra completo. Las alarmas de Preciclo y la campana salen en el idioma de la interfaz y el motivo largo de CIC-10 se ve completo en varias líneas |
| Versión del Setup | `1.0.0-e` (`AppVerNum` 1.0.0.5) | `1.0.0-f` (`AppVerNum` 1.0.0.6) |

## Cambios respecto a la D

| | Compilación D (`2026-10-23_d`) | Compilación E (`2026-10-23_e`) |
|---|---|---|
| Arranque del backend | **Falla**: `ModuleNotFoundError: No module named 'autoclave.backend.server_reasignacion'`. `server.py` carga ese módulo con `importlib.import_module` y PyInstaller no lo empaquetó | Corregido: el módulo va como *hidden import* en `packaging/Autoclave.spec` y `packaging/AutoclaveBackend.spec`, verificado en el archivo PYZ del `.exe` y con la prueba de humo |
| Paso 05 de la estación (plan de energía) | **Falla** en equipos sin el valor `HibernateEnabled` en el registro (lectura con `StrictMode 2.0`) | Corregido: si el valor no existe se respalda como vacío y el paso sigue |
| Setup sobre una instalación existente | Solo actualizar | Página "Autoclave ya está instalado" (Reparar / Reinstalar / Desinstalar) y bloqueo de versiones más viejas (sección 8d) |
| Versión del Setup | `1.0.0-d` | `1.0.0-e` (`AppVerNum` 1.0.0.5) |

> **Tanda 9 (23-oct): la C NO se instala. El equipo de pruebas pasa de la B a la compilación D (`entrega/2026-10-23_d/`) con el Setup `Autoclave_Setup_1.0.0-d.exe`: siga la sección 8c («Actualizar B → D»), sin copiar archivos a mano.** En un PC nuevo, la D se instala con el mismo Setup (secciones 1 a 6, usando el Setup en lugar de abrir `Autoclave.exe`).

## B frente a D

**Instale la D** (`entrega/2026-10-23_d/`, etiqueta `inst-2026-10-23-d`, `dev` 4357217) antes de los ciclos del lunes 26-oct. La D incluye todo lo de la C (tabla «B frente a C», más abajo) y además:

| | Compilación B (`2026-10-22_b`) | Compilación D (`2026-10-23_d`) |
|---|---|---|
| Suite en ese código | 5405 passed, 3 skipped, 3 xfailed | **6606 passed, 10 skipped, 3 xfailed** |
| Arranque con la cámara no segura (D9-1) | Pide «Confirmar y llevar a estado seguro» con el texto «paro liberado» aunque no hubo paro; sin presión de cámara bloquea modo prueba, cambio de programa y apagado, y saca del inicio de sesión | El estado seguro corre solo, sin confirmación (solo la lenta con presión; aire atmosférico con vacío). La confirmación se pide solo tras un paro real. Sin presión de cámara: CIC-10 + SEN-06 y NO ABRIR, sin bloquear inicio de sesión, modo prueba, cambio de programa ni apagado |
| Puerta abierta con presión fuera de la atmosférica (D9-1.6) | — | Alarma nueva SEN-10, bloquea el inicio de ciclo |
| Modo prueba con el estado seguro activo o la cámara no segura | — | **No deja abrir ni desbloquear puertas** desde Entradas/Salidas (ni rápida, chaqueta, vapor de cámara, aire comprimido de cámara ni vapor de generador o caldera con el estado seguro). En el equipo sin sensores la cámara nunca es segura: las puertas no se accionan desde Entradas/Salidas |
| Paro de emergencia y zumbador (D9-9) | Se encienden un instante salidas activas al pulsar el paro | ALL_OFF inmediato con ACK; con el paro, el PC no ordena encender nada salvo el zumbador (caso de banco B-13) |
| Niveles de alarma (D9-2) | SEN-01/03/06/07 y CIC-10 como aviso | Como alarma (requieren reconocimiento) |
| Bitácora (D9-6) | Rechazos, suspensión, órdenes de puerta, selección de programa, pruebas de correo e impresora | Solo seguridad, configuración y sesión |
| Puertas simples (D9-3) | Muestra apertura automática y grupos Puerta y Empaque | Los oculta; grupo nuevo «Cámara segura» |
| Entradas NC (D9-5) | Nivel crudo | Estado interpretado (paro y atrapamiento) y nivel crudo al lado |
| Manejo de ciclos (D9-10) | En Parámetros del ciclo | En Opciones avanzadas (técnico e ingeniero) |
| Ticket y motivos de fallo en inglés (D9-13.4) | En español | En el idioma vigente |
| Actualización | (C: copia a mano de 2 archivos) | **Sin copias a mano** (D9-13.1): el programa refresca sus archivos de fábrica con respaldo |
| Entrega | Correo y programas de usuario del banco | Correo neutro y solo programas de fábrica (D9-7) |

> **Tanda 8 (23-oct): el equipo de pruebas ya tiene la B. Para pasarlo a la compilación C (`entrega/2026-10-23_c/`), siga la sección 8b, no la 1.2.** En un PC nuevo, la C se instala igual que la B (secciones 1 a 6).

## B frente a C

**Instale la C** (`entrega/2026-10-23_c/`, etiqueta `inst-2026-10-23-c`, `dev` 5a4b0df) antes de los ciclos del lunes 26-oct. La B queda de respaldo (vuelta atrás en la sección 8b).

| | Compilación B (`2026-10-22_b`) | Compilación C (`2026-10-23_c`) |
|---|---|---|
| Suite en ese código | 5405 passed, 3 skipped, 3 xfailed | **6201 passed, 7 skipped, 3 xfailed** |
| Transductor de presión sin señal (SEN-01, D8-1) | Lee 0,0 kPa como lectura válida | Detecta el lazo abierto o en corto: «—», FALLO propio en ciclo con venteo solo por la lenta, inicio bloqueado y «NO ABRIR» |
| Transiciones del ciclo (D8-2.6 a 2.16) | Preguntas abiertas de la tanda 7 | Pausa de la exposición sin datos, tope de pausas (CIC-11), 3 tramas DI distintas, líquidos sellados al perder el Principal, ALL_OFF con reintentos, reimpresión idéntica, «CARGA NO ESTÉRIL» en la pantalla de resultado |
| Canales de E/S | Del YAML (había que agregar a mano Cámara 2, `descompresion_lenta`…) | Del perfil de instalación (D8-3.17) |
| Aire atmosférico en modo prueba | Se abre con la cámara presurizada | Rechazado con presión en la cámara o sin lectura (D8-3.19) |
| Calibración que viaja con el programa | Valores del banco | **Neutra** (D8-3.18), verificada en el build |
| Interfaz | — | Hospitalario/Laboratorio, Atrás con historial en Opciones, Cerrar sesión lleva a Login, tipo de carga Sólido/Líquido, modos en lista, sin abreviaturas ni mezcla de idiomas, Reportes por tipo de fallo |
| Opciones avanzadas | Técnico e ingeniero | Solo ingeniero: reasignación de E/S |
| Mantenimiento | «Último mantenimiento» | «Último preventivo»; sin tipo «Otro»; historial para el administrador |
| Dependencias | Entorno completo del PC (2942 archivos) | Entorno limpio solo del producto (2297 archivos; D8-3.26) |
| Prueba de humo en el PC de la oficina | Asistente, paso 1 de 8 | Asistente, paso 1 de 8, sin errores en los registros |

---

## 0. Antes de salir (en el PC de la oficina)

- [ ] **Generar el código de activación del día** (sección 2). Solo vale el día en que se genera.
- [ ] Copiar a la USB la carpeta de la entrega que se va a instalar (ver "A frente a B"): `Autoclave/` completa, o el `.zip`, más `SHA256SUMS.txt`.
- [ ] **NO copiar `GeneradorCodigos.exe` al PC del equipo.** Contiene los secretos de activación y corre solo en el PC de Especifika.
- [ ] Llevar el número de serie exacto del equipo, tal como va a quedar en el perfil.

## 1. Qué copiar y dónde

Contenido de la entrega (`entrega/2026-10-22_a/`; la B tiene la misma forma):

| Archivo | Para qué |
|---|---|
| `Autoclave/` | El programa: `Autoclave.exe` y `_internal/`. Hay que copiar la carpeta **completa**; el `.exe` solo no arranca. |
| `Autoclave_2026-10-22_a.zip` | La misma carpeta comprimida. |
| `SHA256SUMS.txt` | Huellas para comprobar que la copia llegó bien. |
| `MANIFIESTO_CARPETA_Autoclave.sha256` | Huella de cada archivo de la carpeta. |
| `GeneradorCodigos.exe` | Generador de códigos. Solo para el PC de Especifika. |
| `entorno_build.txt` | Versiones exactas con las que se compiló (trazabilidad). |

### 1.1 Comprobar la copia
En el PC del equipo, abrir una consola (`cmd`) en la carpeta de la USB:

```
certutil -hashfile Autoclave_2026-10-22_a.zip SHA256
certutil -hashfile Autoclave\Autoclave.exe SHA256
```

El resultado debe ser igual a la línea del mismo archivo en `SHA256SUMS.txt`. `certutil` imprime la huella con espacios o en mayúsculas según la versión de Windows: compare solo los caracteres. Si no coincide, vuelva a copiar.

Si llevó el zip, descomprímalo antes. **No ejecute el programa desde dentro del zip.**

### 1.0 Instalar con el Setup (alpha.2 en adelante; tanda 17, INS-01 e INS-02)
Se instala con `Autoclave_Setup_<versión>.exe` (doble clic, cuenta administradora, aceptar el UAC). Detalle completo en `tools/instalador/LEEME.md`. Páginas propias de esta versión:

1. **Unidad de instalación** (INS-02). Lista **solo los discos fijos** (no USB, removibles ni unidades de red), con etiqueta, sistema de archivos y espacio libre. Viene marcado el primer disco fijo distinto del de Windows que sirva; si no hay otro, el de Windows (`C:`). Exige NTFS (o ReFS) y un mínimo libre de **tamaño del programa + 2 GB** (la cifra exacta, en MB, aparece en la página; la calcula el Setup al compilarse). Crea:

   | Carpeta | Contenido | Permisos (explícitos, sin herencia de la raíz del disco) |
   |---|---|---|
   | `X:\Especifika\Autoclave\programa` | `Autoclave.exe`, `_internal\`, `estacion\` (scripts) | Administradores y SYSTEM control total; Usuarios **solo lectura y ejecución** |
   | `X:\Especifika\Autoclave\datos` | perfil, base de datos, calibración, logs, tickets, programas de usuario, `estacion\` | Administradores y SYSTEM control total; Usuarios **Modificar** |
   | `X:\Especifika\Autoclave\datos\estacion` | log y respaldos de la estación | solo Administradores y SYSTEM |
   | `X:\Especifika`, `X:\Especifika\Autoclave` | — | sin escritura para Usuarios |

   Si no puede fijar los permisos, el Setup **se detiene sin instalar** (un programa modificable por un usuario sin privilegios no es aceptable en Clase C). También se detiene si alguna de esas carpetas es un enlace o una unión de Windows, o si `programa` ya existe con archivos y no hay una instalación anotada. Escribe `HKLM\SOFTWARE\Especifika\Autoclave` con `RutaPrograma` y `RutaDatos` (64 bits); con eso el programa encuentra sus datos.
2. **Zona horaria** (INS-01). Lista de zonas de Windows ordenada por desfase, con la zona actual marcada y la fecha y hora actuales del PC. Para Colombia: **(UTC-05:00) Bogotá, Lima, Quito…** (identificador `SA Pacific Standard Time`; el nombre visible depende del idioma de Windows). Se aplica al terminar (`tzutil /s`) y se comprueba (`tzutil /g`); si falla, avisa con el procedimiento manual y la instalación sigue. **La hora en sí** (reloj) se sigue revisando a mano en Windows (sección 3). La página aparece también al actualizar o reparar.

**Actualizar** con un Setup más nuevo sobre una instalación hecha así: la página de unidad muestra la unidad ya usada, **sin poder cambiarla** (para cambiarla: desinstalar e instalar de nuevo; los datos quedan en la carpeta `datos` anterior).

**Equipo con la disposición anterior** (compilación I o anterior, o alpha.1: programa en `C:\Program Files\Especifika\Autoclave`): el Setup **se detiene** y pide desinstalarla primero (Configuración › Aplicaciones › Autoclave Especifika). **No hay migración**: los datos anteriores quedan en `C:\ProgramData\Especifika\Autoclave` y el equipo se instala en limpio (asistente de instalación, contraseñas, calibración). Si se necesitan, respaldar antes esa carpeta.

**Sin asistente** (`/SILENT` o `/VERYSILENT`): toma la unidad preseleccionada y la zona actual; `/ZONA=<id>` fija otra zona (el identificador de `tzutil /l`, p. ej. `/ZONA="SA Pacific Standard Time"`); si no existe en ese Windows, el Setup se detiene sin instalar.

### 1.2 Instalar desde la carpeta (compilación I y anteriores)
1. Ajustar primero en Windows la **fecha, la hora y la zona horaria (Bogotá, UTC-5)** del PC del equipo. Ver el aviso de la sección 3. (Desde la alpha.2, la zona se elige en el Setup, sección 1.0.)
2. Doble clic en `Autoclave\Autoclave.exe`, desde la USB o desde la carpeta copiada.
3. Pregunta **"¿Instalar Autoclave en este PC?"**. Responder **Sí** y aceptar el aviso de permisos de administrador (UAC).
4. El programa queda en `C:\Program Files\Especifika\Autoclave` y crea accesos directos "Autoclave" en el Escritorio público y en el menú Inicio. Se abre solo, ya desde la copia instalada. En la USB no se escribe nada.
5. Los datos quedan en `C:\ProgramData\Especifika\Autoclave` (carpeta oculta: escriba la ruta en la barra de direcciones del Explorador):

| Ruta dentro de `C:\ProgramData\Especifika\Autoclave` | Contenido |
|---|---|
| `installation_profile.json` | Perfil de instalación (bloqueado) |
| `data\autoclave.db` | Base de datos: usuarios, historial, bitácora, presión atmosférica calibrada |
| `data\calibration.yaml` | Calibración de sensores (ganancia y offset por canal) |
| `programa\autoclave\config\` | Parámetros del equipo y lista de canales de E/S (`instances\ACV-2026-001.yaml`) |
| `programa\autoclave\cycles\` | Programas de ciclo de usuario y de fábrica |
| `data\*.log` | Registros: `lanzador.log`, `backend.log`, `ui_puerta1.log`, `ui_puerta2.log` |

### 1.3 Alternativa portátil (sin instalar)
Para correr en sitio sin copiar a Archivos de programa, cree un acceso directo a `Autoclave.exe` con el argumento `--portable`. En modo portátil, los datos quedan **junto al `.exe`** (`installation_profile.json` y `data\`). La carpeta tiene que ser escribible: no sirve desde una USB protegida contra escritura (sin poder escribir `data\calibration.yaml`, el backend no arranca).

### 1.4 Reinstalar o actualizar el programa: ¿qué pasa con los datos?
- Abrir otra versión de `Autoclave.exe` desde fuera de Archivos de programa pregunta **"Ya hay un Autoclave instalado en este PC. ¿Actualizarlo con esta versión?"**. Al responder Sí, se reemplaza solo `C:\Program Files\Especifika\Autoclave`.
- **Los datos se conservan**: perfil, base de datos (usuarios, historial), calibración, presión atmosférica, parámetros y ciclos de usuario. Esto está comprobado con una prueba que simula el ejecutable instalado.
- Los ciclos de **fábrica** sí se refrescan desde el programa nuevo.
- Los archivos de configuración que ya existen en `programa\` (parámetros globales, lista de canales de E/S) **no** se reemplazan. Si una versión nueva trae cambios en ellos, no llegan a un equipo ya instalado.
- Antes de actualizar, **cierre Autoclave** (todas las ventanas). Si está abierto, la copia falla con un aviso y deja la versión anterior.

### 1.5 Una pantalla o dos
El acceso directo abre **las dos pantallas**: puerta 1 en el monitor 0 y puerta 2 en el monitor 1. Si el PC del equipo tiene **un solo monitor**, la ventana de la puerta 2 se abre a pantalla completa encima de la de la puerta 1.

El programa **no detecta** cuántos monitores hay (decisión D8-3.20 de la tanda 8): en un PC con un solo monitor hay que usar el argumento `--una-pantalla`, que abre solo la pantalla de la puerta 1 (con el backend, como siempre).

Acceso directo de ejemplo (un solo monitor):

1. Clic derecho en el escritorio > **Nuevo** > **Acceso directo**.
2. En "Escriba la ubicación del elemento" pegue, **con las comillas**:
   ```
   "C:\Program Files\Especifika\Autoclave\Autoclave.exe" --una-pantalla
   ```
3. **Siguiente**; nombre: `Autoclave (una pantalla)`; **Finalizar**.
4. Use ese acceso directo en lugar del normal (puede borrar el otro para no confundirse). Para arrancar solo al encender el PC, copie el acceso directo a la carpeta que abre `Win + R` > `shell:startup`.

Variantes del mismo destino:

| Caso | Destino del acceso directo |
|---|---|
| Un monitor, programa instalado | `"C:\Program Files\Especifika\Autoclave\Autoclave.exe" --una-pantalla` |
| Un monitor, modo portátil (1.3) | `"<carpeta>\Autoclave.exe" --portable --una-pantalla` |
| Un monitor que Windows no numera 0 | `"C:\Program Files\Especifika\Autoclave\Autoclave.exe" --una-pantalla --monitor-puerta1 1` |

Notas:
- Con `--una-pantalla` no se abre la pantalla de la puerta 2. En un equipo de dos puertas, la puerta 2 queda sin pantalla en este PC.
- Si hay dos monitores y las ventanas salen cambiadas, use `--monitor-puerta1 1 --monitor-puerta2 0` en el acceso directo normal (sin `--una-pantalla`).
- El asistente de instalación (sección 3) siempre se abre solo en la pantalla de la puerta 1; el argumento no cambia nada ahí.

**[verificar en sitio]** cuántos monitores tiene el PC y cuál es el 0.

## 2. Código de activación del día (`GeneradorCodigos.exe`, en el PC de Especifika)

1. Doble clic en `GeneradorCodigos.exe` (no abre consola). Arranca un servidor local y abre el navegador en `http://localhost:8080`. Si ya estaba abierto, solo abre el navegador.
2. **Primera vez en ese PC:** se crea el usuario `admin` con una contraseña temporal. Está en `C:\ProgramData\Especifika\Generador\CLAVE_INICIAL_ADMIN.txt`. El generador la pide cambiar en el primer ingreso y entonces borra el archivo.
3. Ingrese y escriba el **número de serie del equipo** en "Número de serie del equipo". Pulse **Generar**.
4. Resultado:
   - **Serie nueva:** muestra el "Código de instalación" (12 caracteres) y la "Clave de fábrica". Para el asistente se usa el **Código de instalación**.
   - **Serie a la que ya se le generó un código** (por ejemplo, en una prueba anterior): muestra solo la "Clave de fábrica" y el botón **"Solicitar reinstalación"**. Púlselo para obtener el "Código de reinstalación". El asistente lo acepta igual: es el mismo código.
5. Los códigos son **válidos solo el día de hoy**: lo dice la página ("Válidos solo el día de hoy: AAAA-MM-DD"). El equipo los valida contra **su propia fecha local**. Si el PC del equipo tiene otra fecha, el código se rechaza ("Código de activación incorrecto o expirado").
6. Las mayúsculas y los espacios de los extremos no importan, ni en la serie ni en el código. Un espacio o un guion **dentro** de la serie sí importa: debe escribirse igual en el generador y en el asistente.

Datos del generador: `C:\ProgramData\Especifika\Generador\` (base, `config.json` con el puerto, respaldos y log).

## 3. Primer arranque y asistente de instalación

> **Fecha y hora primero.** El perfil guarda la fecha de instalación. Si se instala con el reloj del PC **adelantado** y luego se corrige, el programa no vuelve a arrancar: muestra el fallo de reloj ARR_RELOJ hasta que llegue esa fecha. Para salir de eso hay que reinstalar el perfil (sección 7). Ajuste fecha, hora y zona antes de abrir el asistente.

Sin perfil, el programa abre **solo el asistente**, en la pantalla de la puerta 1 y sin backend: es normal que todavía no haya lecturas. La compilación A tiene **7 pasos**.

| Paso | Qué pide | Qué poner en este equipo |
|---|---|---|
| 1. Activación | Número de serie + código de 12 caracteres | La serie exacta y el código del día (sección 2) |
| 2. Tipo de equipo | Clase | **Piso** o **Piso Laboratorio**, según el equipo. **[verificar en sitio]** En la A también aparecen las clases de Mesa: no elegirlas. |
| 3. Puertas | Número de puertas, tipo de puerta y puerta que gestiona este PC | Según el equipo. Con 2 puertas, este PC gestiona la **Puerta 1**. El tipo (Simple / Motorizada / Con bloqueo / Motorizada con bloqueo / Avanzada) define si el software controla el cerrojo y vigila el empaque; el resumen lo advierte. **[verificar en sitio]** |
| 4. Enfriamiento | Nivel | **0** (sin enfriamiento), salvo que el equipo lo tenga |
| 5. Fuente de vapor | Generador / Caldera / Mixto | **Generador interno**. Con esta opción, las salidas DO1 y DO2 quedan bloqueadas en E/S: el generador tiene su propio control. |
| 6. Datos del equipo | Modelo (texto libre, solo en la A), entradas de suministro y sondas | **Suministros:** activar **solo "Aire comprimido"** y desactivar los demás (agua de la bomba, agua del generador, presostato de vapor, suministro eléctrico). Una entrada desactivada no se vigila: no da alarma ni bloqueo. **Sondas:** Cámara 1 (fija, no se puede quitar), **Cámara 2**, **Referencia** y **Drenaje**, las cuatro activas. **Modelo (A):** escribir el nombre con la nomenclatura oficial, p. ej. `SPK-SAT 80H2` (máximo 18 caracteres para el ticket). |
| 7. Resumen | Revisión | Revise todo. Al instalar, el perfil queda **bloqueado**: solo se cambia reinstalando el perfil (sección 7). |

Al confirmar, aparece **"Instalación completada"**. Pulse **Continuar**. El texto dice "Reinicie el software", pero **no hace falta**: el programa sigue solo con el arranque normal (backend y pantallas). Esto está comprobado con prueba.

**Compilación B (solo si entró la etapa M1 de esta noche).** El asistente cambia así:
- en el paso 2 aparecen solo **Piso** y **Piso laboratorio**;
- después de Puertas hay un paso nuevo, **Cámara**: capacidad nominal en litros (entero de 20 a 2000) y tipo de carga **Vertical (V)** u **Horizontal (H)**;
- el nombre del modelo **se calcula solo**, como `SPK-SAT <litros><V|H>[2][-LAB]`: el `2` va si tiene 2 puertas y `-LAB` si es Piso laboratorio. Ejemplos: `SPK-SAT 45V`, `SPK-SAT 45V2-LAB`;
- el campo libre "Modelo" desaparece del paso de datos;
- el resto es igual.

## 4. Arranque con perfil

- Se ve la intro "del vapor a la precisión" y luego la pantalla principal.
- **Con la tarjeta desconectada**, el equipo debe mostrar **"tarjeta desconectada"** (alarma COM-01 "Tarjeta de E/S desconectada"). **No** debe decir "paro de emergencia" ni mostrar valores inventados: temperatura y presión salen como "—"/"---". Se puede ingresar y navegar igual.
- El backend espera la tarjeta 15 s y da el arranque por terminado igual (ARR_SIN_ES); reintenta solo cuando se conecta.
- Si la intro muestra un fallo de arranque porque el backend tardó más de 20 s la primera vez (antivirus, PC lento), **ya no queda trabada**: sigue en cuanto el backend responde (cambio P1). Si el fallo no se retira en un minuto, cierre y vuelva a abrir, y revise `data\backend.log`.
- Los fallos bloqueantes de verdad (reloj alterado, calibración ilegible, perfil inválido) dejan la intro detenida con la alarma. Ver la sección 7 y los logs.

## 5. Primer usuario

La base nueva trae dos cuentas del sistema. Las dos exigen cambiar la contraseña en el primer ingreso (8 a 64 caracteres, distinta de la actual):

| Usuario | Contraseña inicial | Rol |
|---|---|---|
| `Ingeniero` | `ingeniero1234` | ingeniero |
| `Admin` | `admin1234` | administrador |

El usuario **no distingue mayúsculas**: `Ingeniero`, `ingeniero` o `INGENIERO` entran a la misma cuenta (la contraseña sí las distingue). Al actualizar desde una versión anterior, las cuentas `admin` e `ingeniero` pasan solas a `Admin` e `Ingeniero` y conservan su contraseña.

Estas dos cuentas **no se pueden desactivar, borrar, cambiar de rol ni renombrar**; su contraseña sí se cambia o se restablece.

1. Toque el avatar e ingrese como **`Ingeniero` / `ingeniero1234`**. **No use `Admin`:** el administrador no ve Entradas/Salidas, calibración ni Mantenimiento.
2. El sistema lleva a **cambiar la contraseña**. Anote la nueva en un lugar seguro.
3. En OPCIONES › Usuarios › Nuevo usuario, cree su usuario **técnico** (o ingeniero). Comprobado con prueba: Ingeniero → cambio de clave → crea técnico → el técnico entra al modo prueba. No se acepta un usuario que solo difiera en mayúsculas de uno existente.
4. Cinco intentos fallidos bloquean ese usuario 5 minutos.
5. Cambie también la contraseña de `Admin` antes de entregar el equipo.

## 6. Orden de verificación

### 6.1 Entradas/Salidas (OPCIONES › Entradas / Salidas)
Requisitos:
- usuario técnico o ingeniero;
- equipo en PREPARACIÓN, PREPARADO o FALLA;
- **tarjeta conectada**;
- **paro de emergencia liberado.** Con el paro activo, OPCIONES no abre y el modo prueba se rechaza.

Orden sugerido:
1. **Entradas:** cada una muestra Activa / Inactiva, o "Sin datos" si no hay enlace. Accione cada sensor físico (puerta cerrada/abierta, atrapamiento, aire comprimido, paro…) y vea el cambio.
2. **Temperatura** y **Presión:** valores vivos y cuentas ADC. Sin tarjeta muestran "---" y "Sin enlace con la tarjeta de E/S".
3. **Salidas:** pulse **Habilitar modo prueba** y acepte el aviso. Al entrar, todas las salidas se apagan.
   - **Salidas sostenidas** (válvulas): un toque las activa y otro las apaga. Verifique cada una en campo.
   - **Salidas momentáneas** (abrir/cerrar puerta 1 y 2, bomba de vacío): se activan **mientras se mantiene pulsado** "Mantener pulsado" y se apagan al soltar. Si la orden se pierde, el backend las apaga solo a los 1,5 s. **Corregido en P1:** antes la pulsación se cortaba a los 1-2 s.
   - `aire_atmosferico_camara` antes respondía error y no se movía. **Corregido en P1.**
   - Con generador interno, `vapor_generador` sale como **bloqueada**: es lo esperado.
4. **Salida del modo prueba.** Pruebe todos los caminos; en cada uno las salidas deben quedar apagadas:
   - botón **Salir del modo prueba**;
   - cambiar a otro segmento (Entradas / Temperatura / Presión);
   - salir de la pantalla (Atrás o Inicio);
   - cerrar sesión;
   - 5 minutos sin tocar la sección;
   - sesión vencida o cerrada en otra parte. **Corregido en P1:** el vigilante de este caso moría a los pocos segundos.
   - El backend también sale solo tras 90 s sin órdenes ni avisos (por ejemplo, si la pantalla se cierra de golpe).
5. **Desconexión de la tarjeta durante el modo prueba:** las salidas no se pueden accionar ("rechazó la orden") y "Salir" sigue funcionando. Salga y vuelva a entrar al reconectar.

**PROBLEMA CONOCIDO — canales que no aparecen en E/S.** La lista sale de `io_enabled` del archivo del equipo (`ACV-2026-001.yaml`). Hoy **no** incluye:
- en salidas: `descompresion_lenta`, `vapor_caldera`, `aire_comprimido_camara`, `agua_chaqueta` ni `buzer_alarma`;
- en temperatura: la sonda **`temp_2_camara` (Cámara 2)**;
- en entradas: `suministro_electrico`.

Así, desde la pantalla no se pueden probar ni calibrar. Rodeo, con Autoclave **cerrado**:
1. Edite `C:\ProgramData\Especifika\Autoclave\programa\autoclave\config\instances\ACV-2026-001.yaml` (en portátil: `<carpeta del exe>\programa\autoclave\config\instances\`).
2. Agregue los nombres que el equipo tenga cableados bajo `io_enabled:` → `DO:` / `AI:` / `DI:`, con la misma sangría que los demás. Por ejemplo, `    - descompresion_lenta` bajo `DO:` y `    - temp_2_camara` bajo `AI:`.
3. Vuelva a abrir Autoclave.

En el modo prueba, el backend ya acepta cualquier salida del mapa: solo cambia lo que muestra la pantalla. **[verificar en sitio]** qué salidas y sondas tiene cableadas el equipo.

### 6.2 Calibración de sensores (Temperatura / Presión › Calibrar)
- **Orden: primero presión, después temperatura.** La presión atmosférica (6.3) se calcula con la presión de cámara calibrada: si recalibra la presión después, repita la 6.3.
- Requisitos: técnico (fuera de ciclo) o ingeniero, y **tarjeta conectada**. Sin lectura válida, el botón "Calibrar" está deshabilitado.
- **Dos puntos.** En cada punto, "lo que muestra el equipo" contra "lo que marca el patrón". La lectura del equipo se puede **capturar** del valor vivo o **escribir a mano**; la bitácora guarda cuál de las dos fue. Luego **Aplicar**.
- **Límites que conviene conocer:**

| | Temperatura | Presión |
|---|---|---|
| Separación mínima entre puntos (en lo mostrado Y en el patrón) | 20 °C | **50 kPa** |
| Rango de los 4 valores | 0–200 °C | −10 a 450 kPa (absolutos) |
| Corrección máxima (cámara, cámara 2 y referencia / cámara) | 10 °C | 50 kPa |

  Una corrección grande pide confirmación y queda auditada. Una imposible se rechaza con el motivo. Ejemplo práctico: la atmósfera en Bogotá (~75 kPa abs) y 120 kPa están a solo 45 kPa y **se rechazan**. El punto alto debe estar a ≥ 125 kPa abs. **[verificar en sitio]** cómo se obtiene ese punto hoy (calibrador de presión o chaqueta presurizada).
- **La sonda de Referencia** antes no se podía calibrar desde la pantalla (error). **Corregido en P1.**
- **La calibración que trae el programa** (`data\calibration.yaml` de un equipo nuevo) **no es neutra**: lleva los valores del banco de Especifika (julio/agosto), por ejemplo presión de cámara con ganancia 1,364 y offset −75,35. **[verificar en sitio]** si son de este mismo equipo. Si las lecturas no cuadran o la corrección se rechaza por desviación acumulada, use primero **"Restaurar por defecto"** en ese sensor (ganancia 1, offset 0) y calibre desde ahí.
- **Guardar y comprobar que se conserva:**
  1. aplique la calibración;
  2. cierre Autoclave;
  3. ábralo de nuevo;
  4. en E/S › Calibrar del mismo sensor, la ganancia y el offset deben ser los nuevos (con fecha y usuario de la última calibración).

  Se guarda en `C:\ProgramData\Especifika\Autoclave\data\calibration.yaml`, con un `.bak` del anterior. Comprobado con prueba (reinicio y actualización).
- **Rodeo si la pantalla táctil no deja calibrar:** el menú de ajustes PySide (`"C:\Program Files\Especifika\Autoclave\Autoclave.exe" --rol ajustes`, con el programa principal abierto) tiene calibración con valores escritos, para todos los sensores del mapa. El engrane de la pantalla ya no lo abre. **[verificar en sitio]**. Ese menú corta la espera a 0,8 s: si dice "No se pudo guardar", **revise la ganancia y el offset vigentes antes de reintentar**, porque pudo haberse guardado.

### 6.3 Presión atmosférica (OPCIONES › Mantenimiento › Calibrar presión atmosférica)
- Requisitos:
  - tarjeta conectada con datos vigentes;
  - **una puerta ABIERTA**;
  - cámara por debajo de 80 °C;
  - fuera de ciclo;
  - base de datos disponible.
- Mide 120 s. El promedio debe quedar entre 60 y 105 kPa, con dispersión ≤ 1,5 kPa.
- Si el resultado difiere en más de 5 kPa del valor vigente (75 kPa de fábrica), pide **Confirmar** dentro de 5 minutos; si no, se descarta.
- Se guarda en la base de datos (`data\autoclave.db`) y se conserva al reiniciar y al actualizar. **Un respaldo restaurado no lo trae**: si restaura un respaldo, recalibre.

### 6.4 Información del sistema (OPCIONES › Información del sistema)
- Muestra:
  - modelo, número de serie y fecha de instalación;
  - fuente de vapor;
  - versión del software (la A dice **0.5.0**);
  - firmware e id de la tarjeta;
  - ciclos, mantenimiento, idioma, unidades, impresora y red.
- Sin tarjeta, firmware e id salen "—" y los ciclos en 0: es normal.
- El pie del asistente dice "V: 1.0" (texto fijo); no coincide con la versión real.

### 6.5 Apagar el equipo (botón Apagar equipo, solo en la pantalla de la puerta 1)
- En el programa instalado **apaga Windows de verdad** (`shutdown /s /t 0`). Antes apaga las salidas, detiene el control y cierra la base de datos.
- Se rechaza con un ciclo en curso.
- Si Windows rechaza el apagado (política del PC), el control ya quedó detenido y el PC sigue encendido. Desde P1, el motivo queda en `data\backend.log` ("Windows rechazó el apagado"). En ese caso, cierre Autoclave y apague Windows a mano.
- **[verificar en sitio]** que el usuario de Windows del equipo pueda apagar.

## 7. Si el perfil queda mal: reinstalar el perfil

El perfil está bloqueado y el programa no lo sobrescribe si es válido. Para rehacerlo:
1. **Cierre Autoclave por completo**: todas las ventanas. En el Administrador de tareas no debe quedar ningún `Autoclave.exe`.
2. Abra `C:\ProgramData\Especifika\Autoclave\` (portátil: la carpeta del `.exe`).
3. **Renombre** `installation_profile.json`, p. ej. a `installation_profile.json.mal-2026-10-22`. **No lo borre**: queda como evidencia.
4. Genere un código del día para la serie. Si la serie ya tenía código, use **"Solicitar reinstalación"** (sección 2).
5. Abra Autoclave: sin perfil vuelve a abrir el asistente. Complete los pasos.
6. **Se conservan:** usuarios, historial, calibración, presión atmosférica, parámetros y ciclos. Solo cambia el perfil.

Lo mismo sirve si el arranque queda en **ARR_RELOJ** porque se instaló con el reloj adelantado: corrija primero la hora de Windows y luego reinstale el perfil.

Si el perfil está **dañado** (ilegible o inválido), el asistente se abre solo y aparta el archivo viejo como `installation_profile.json.invalido-<fecha>`.

## 8. Volver a la compilación A si la B falla

1. Cierre Autoclave por completo.
2. Desde la USB o carpeta de la **A**, abra `Autoclave\Autoclave.exe`. Pregunta "Ya hay un Autoclave instalado… ¿Actualizarlo con esta versión?": responda **Sí**.
3. Queda instalada la A **con los mismos datos**: perfil, usuarios, calibración.
   - Un perfil hecho con la B (con capacidad y tipo de carga) se lee en la A sin problema, porque la A ignora los campos que no conoce.
   - Si la B migró la base de datos a una versión más nueva, la A la abre sin bajarla de versión. **[verificar en sitio]** que la A arranque bien después de la B.
4. Si la A no arranca con esos datos, reinstale el perfil (sección 7) antes de tocar la base.

## 8b. Actualizar un equipo ya instalado (B → C)

> **La C no se instala (tanda 9). Para la D use la sección 8c, sin copias a mano.** Esta sección queda como referencia.

Para pasar el equipo de pruebas, instalado el 22-oct con la **B**, a la **C** (`entrega/2026-10-23_c/`) sin perder nada. Se comprobó en el PC de la oficina con una copia simulada del equipo instalado: perfil del equipo de pruebas, base de datos de la B con un usuario y un parámetro cambiado, y calibración propia. El detalle está en `docs/informes/tanda8/K8_compilacion_c.md`.

**Qué hace el programa al actualizar** (leído en `instalador_exe.py`, `utils/resources.py` y `utils/paths.py`):
- reemplaza solo `C:\Program Files\Especifika\Autoclave` (`Autoclave.exe` y `_internal\`);
- en `C:\ProgramData\Especifika\Autoclave` no borra ni reemplaza nada, salvo los programas de **fábrica** (`programa\autoclave\cycles\factory\`), que siempre se refrescan;
- los archivos de configuración que ya existen en `programa\autoclave\config\` **no se reemplazan**. Por eso hay dos que se copian a mano (paso 6).

**Orden, con el software cerrado:**
1. **Cierre Autoclave por completo** (las dos pantallas). En el Administrador de tareas no debe quedar ningún `Autoclave.exe`.
2. **Respaldo:** copie la carpeta completa `C:\ProgramData\Especifika\Autoclave` a la USB (por ejemplo, `respaldo_B_2026-10-23`). Es la vuelta atrás.
3. Compruebe la copia de la C con `SHA256SUMS.txt` (sección 1.1).
4. Abra `Autoclave\Autoclave.exe` de la C desde la USB. Pregunta "Ya hay un Autoclave instalado en este PC. ¿Actualizarlo con esta versión?": responda **Sí** y acepte el aviso de administrador.
5. Al terminar, el programa se abre solo. **Ciérrelo otra vez por completo** (paso 1).
6. **Reemplace estos dos archivos** de `C:\ProgramData\Especifika\Autoclave\programa\autoclave\config\` por los de la C, que están en `C:\Program Files\Especifika\Autoclave\_internal\autoclave\config\`:

| Archivo | Por qué hay que reemplazarlo |
|---|---|
| `instances\ACV-2026-001.yaml` | En la C es la lista de **todos** los canales físicos, y el perfil decide cuáles se muestran (D8-3.17). Con el archivo de la B **no aparecen** Cámara 2, `descompresion_lenta`, el aire comprimido de chaqueta y de cámara, el agua de chaqueta ni el zumbador. Si el 22-oct se agregaron canales a mano (sección 6.1), el archivo de la C ya los trae: no hay que volver a editarlo. |
| `global_params.json` | Trae dos parámetros del equipo nuevos: pausa máxima en esterilización (30 s) y espera sellada sin sonda (30 min). Reemplazarlo es seguro: los valores vigentes de los parámetros del equipo se guardan en la base de datos, no en este archivo, y se conservan. |

7. Abra Autoclave con el acceso directo. En el primer arranque, la base de datos se actualiza sola a la versión 10.
8. Compruebe:
   - Información del sistema: versión y número de serie;
   - que los usuarios entran;
   - Parámetros del equipo: los valores de antes y los dos nuevos;
   - Entradas/Salidas: Cámara 2 y `descompresion_lenta` visibles.

**NO toque** (se conservan solos):

| Ruta en `C:\ProgramData\Especifika\Autoclave` | Contenido |
|---|---|
| `installation_profile.json` | Perfil de instalación (bloqueado) |
| `data\calibration.yaml` | **Calibración del equipo.** La C trae una calibración neutra (D8-3.18), pero solo se usa en un equipo nuevo: la del equipo no se reemplaza |
| `data\autoclave.db` | Usuarios, historial, bitácora, parámetros del equipo, presión atmosférica calibrada y mantenimiento |
| `programa\autoclave\cycles\user\` | Programas de ciclo del usuario |
| `programa\autoclave\config\serial_link.json` | Puerto de la tarjeta |
| `programa\autoclave\config\correo.json` | Correo (la contraseña está en el almacén de credenciales de Windows) |
| `programa\autoclave\config\active_instances.yaml`, `calibration.yaml` y `models\` | Sin cambios entre la B y la C |

**Volver a la B si la C falla:**
1. Cierre Autoclave.
2. Abra el `Autoclave.exe` de la B, responda Sí a "¿Actualizarlo?" y ciérrelo cuando se abra.
3. **Reemplace la carpeta completa** `C:\ProgramData\Especifika\Autoclave` por el respaldo del paso 2. Es necesario porque la C deja la base de datos en la versión 10, que la B no conoce.

## 8c. Actualizar el equipo de pruebas de la B a la D (con el Setup)

Para pasar el equipo de pruebas, instalado el 22-oct con la **B**, a la **D** sin perder nada y **sin copiar archivos a mano**. La C no se instala. Se ensayó en el PC de la oficina con una copia simulada del equipo (perfil del equipo de pruebas, base de datos de la B con un usuario y un parámetro cambiado, calibración y correo propios) y el `_internal` real de la D: `docs/informes/tanda9/K9_compilacion_d.md`.

**Qué hace la D al actualizar:**
- el Setup reemplaza solo `C:\Program Files\Especifika\Autoclave` (borra antes `_internal\`);
- en `C:\ProgramData\Especifika\Autoclave` el Setup no copia ni borra nada; solo da permiso de Modificar a Usuarios;
- en el primer arranque, el programa refresca solo sus archivos de configuración **de fábrica** (`programa\autoclave\config\instances\*.yaml` y `global_params.json`), con copia de respaldo con fecha en `programa\respaldos_configuracion\<fecha>\`, y los programas de fábrica (`cycles\factory\`). Así aparecen Cámara 2, `descompresion_lenta` y los parámetros nuevos del equipo;
- la base de datos se actualiza sola a la versión 10.

**Orden:**
1. **Cierre Autoclave por completo** (las dos pantallas). En el Administrador de tareas no debe quedar ningún `Autoclave.exe`. Si queda abierto, el Setup ofrece cerrarlo.
2. **Respaldo:** copie la carpeta completa `C:\ProgramData\Especifika\Autoclave` a la USB (por ejemplo, `respaldo_B_2026-10-23`). Es la vuelta atrás.
3. Compruebe el Setup con `SHA256SUMS.txt` de la USB (PowerShell: `Get-FileHash .\Autoclave_Setup_1.0.0-d.exe` y comparar con la línea del Setup).
4. Ejecute `Autoclave_Setup_1.0.0-d.exe` y acepte el aviso de administrador.
5. En «Tareas adicionales»:
   - «Iniciar Autoclave automáticamente al iniciar sesión en Windows»: **marcada**;
   - «Configurar este PC como estación del autoclave»: **DESMÁRQUELA** en el equipo de pruebas hasta haber hecho la lista de verificación de `tools/instalador/LEEME.md` en un PC de prueba (D9-11: se valida primero en un PC de prueba). Viene marcada por defecto;
   - «Arranque sin logo de Windows…»: desmarcada.
6. Termine el Setup. Abra Autoclave con el acceso directo.
7. Compruebe:
   - Información del sistema: versión y número de serie;
   - que los usuarios entran;
   - Parámetros del equipo: los valores de antes, los dos nuevos (pausa máxima en esterilización 30 s, espera sellada sin sonda 30 min) y el grupo «Cámara segura»;
   - Entradas/Salidas: Cámara 2 y `descompresion_lenta` visibles; el paro y el atrapamiento muestran el estado interpretado;
   - sin sensores de presión: tarjeta de alarmas con SEN-06 y CIC-10 («Estado seguro detenido»), **sin** botón de confirmación ni «paro liberado»; el inicio de sesión, el modo prueba, el cambio de programa y el apagado funcionan (casos C-05 a C-05h de la hoja de banco).
8. **Programas de usuario:** la actualización no toca `programa\autoclave\cycles\user\`, así que el equipo conserva los programas de la B, que traían valores del banco (el Bowie & Dick con modo 4 y 134,5 °C, entre otros). Revíselos en Parámetros del ciclo antes de los ciclos del lunes (PREGUNTA E9-P1).

**NO toque** (se conservan solos): `installation_profile.json` (perfil), `data\calibration.yaml` (calibración del equipo), `data\autoclave.db` (usuarios, historial, bitácora, parámetros), `data\asignacion_io.json` (asignación de E/S vigente), `programa\autoclave\cycles\user\` y `cycles\defecto\`, y en `programa\autoclave\config\`: `correo.json`, `serial_link.json`, `calibration.yaml` y `active_instances.yaml`. No hace falta copiar nada desde `Program Files`.

**Volver a la B si la D falla:**
1. Cierre Autoclave.
2. Abra el `Autoclave.exe` de la B desde la USB, responda Sí a «¿Actualizarlo?» y ciérrelo cuando se abra.
3. **Reemplace la carpeta completa** `C:\ProgramData\Especifika\Autoclave` por el respaldo del paso 2 (la D deja la base de datos en la versión 10, que la B no conoce).

## 8d. Instalar con el Setup E (`Autoclave_Setup_1.0.0-e.exe`)

Se usa igual que el de la D (sección 8c): compruebe el Setup con `Get-FileHash .\Autoclave_Setup_1.0.0-e.exe` contra la línea del Setup en `SHA256SUMS.txt`, ejecútelo y acepte el aviso de administrador. Lo nuevo es lo que hace el Setup cuando ya hay un Autoclave instalado **con un Setup** (lo detecta por la clave de desinstalación de Windows; la versión numérica instalada queda anotada en `HKLM\SOFTWARE\Especifika\Autoclave\Instalacion\VersionNum`):

| Instalado en el PC | Qué hace el Setup E |
|---|---|
| Nada, o la B (instalada con `Autoclave.exe`, sin Setup) | Instalación normal con el asistente completo |
| **La D** (instalada con el Setup D) | **Actualiza** con el asistente completo: tareas, y si deja marcada la casilla de la estación, **vuelve a pedir la contraseña de la cuenta de la estación** (inicio de sesión automático). La D no anotaba `VersionNum`, así que el Setup la trata como más vieja por su `DisplayVersion` |
| **La E** (misma versión) | Página **"Autoclave ya está instalado"**, con tres opciones (abajo) |
| Una versión más nueva que la E | **Se niega a instalar** con un aviso y no cambia nada: hay que desinstalar primero desde Configuración › Aplicaciones (no se baja de versión) |

La página de mantenimiento **solo aparece al correr el Setup E sobre la E ya instalada**; sobre la D, el Setup E actualiza.

**Página "Autoclave ya está instalado"** (Reparar viene marcada):
- **Reparar**: vuelve a copiar el programa (borra antes `_internal\`), recrea la tarea de arranque si estaba elegida y vuelve a aplicar los pasos de la estación 04, 05 y 02 que ya estaban aplicados. No muestra las tareas ni la página de la cuenta. **No reaplica el inicio de sesión automático (paso 01)**: queda como estaba, y la tarea de arranque se recrea para la misma cuenta. Un Setup silencioso (`/SILENT`, `/VERYSILENT`) de la misma versión hace Reparar.
- **Reinstalar**: ejecuta el desinstalador (revierte la configuración de Windows de la estación, borra el programa y la tarea) y espera a que termine (máx. 120 s); después sigue con el asistente completo, como una instalación nueva (vuelve a pedir la contraseña si se marca la estación). Si la desinstalación no termina, no instala.
- **Desinstalar**: abre el desinstalador normal (con su confirmación) y cierra el Setup.
- En las tres se conservan los datos de `C:\ProgramData\Especifika\Autoclave` (perfil, calibración, base de datos, usuarios).

La casilla «Configurar este PC como estación del autoclave» sigue **DESMARCADA en el equipo de pruebas** hasta validarla en un PC de prueba (sección 8c, paso 5; lista de `tools/instalador/LEEME.md`, que ahora incluye la verificación de Reparar / Reinstalar / Desinstalar).

## 8e. Actualizar el equipo de pruebas a la F (E → F, o D → F) con el Setup

Es la sección 8c con el Setup F. **Sin pasos de copia a mano.** Se ensayó en el PC de la oficina sobre una copia simulada del equipo (perfil del equipo de pruebas, base de datos con un usuario y un parámetro cambiado, calibración y correo propios) con el código y el `_internal` de la E y luego de la F: `docs/informes/tanda10/K10_compilacion_f.md`.

1. **Cierre Autoclave por completo** (las dos pantallas).
2. **Respaldo:** copie `C:\ProgramData\Especifika\Autoclave` completa a la USB (por ejemplo, `respaldo_E_2026-10-23`).
3. Compruebe el Setup: `Get-FileHash .\Autoclave_Setup_1.0.0-f.exe` contra la línea del Setup en `SHA256SUMS.txt`.
4. Ejecute `Autoclave_Setup_1.0.0-f.exe` y acepte el aviso de administrador. Sobre la E o la D, **actualiza** con el asistente completo (sección 8d). Sobre la F misma aparecería la página «Autoclave ya está instalado».
5. En «Tareas adicionales», igual que en la 8c: inicio automático **marcada**; «Configurar este PC como estación del autoclave» **DESMARCADA** en el equipo de pruebas hasta validarla en un PC de prueba (DECISIÓN SIN CONFIRMAR K9-1, se mantiene); arranque sin logo desmarcada.
6. Abra Autoclave y compruebe, además de lo de la 8c paso 7:
   - Ciclo y Preciclo, en español y en inglés: las etiquetas de la tarjeta de parámetros y sensores se leen completas o abreviadas, sin letra encogida ni cortes;
   - sin sensor de presión de cámara: CIC-10 dice que sin ese sensor no se puede llevar la cámara a estado seguro (tarjeta de Preciclo y campana), y las filas de alarma salen en el idioma de la interfaz;
   - el código de activación (si se reinstala el perfil) se acepta aunque se teclee 0 en lugar de O.
7. La base de datos y la configuración de fábrica no cambian de la E a la F: el primer arranque no hace respaldos nuevos en `programa
espaldos_configuracion\` (es lo esperado).

**NO toque** lo mismo que en la 8c. **Volver a la E si la F falla:** cierre Autoclave, ejecute `Autoclave_Setup_1.0.0-e.exe` de la USB (si se niega por ser más vieja, desinstale primero desde Configuración › Aplicaciones; los datos de `ProgramData` se conservan) y, solo si algo de los datos quedó mal, reemplace `C:\ProgramData\Especifika\Autoclave` por el respaldo del paso 2.

## 8f. Actualizar el equipo de pruebas a la G (F → G) con el Setup

Es la sección 8e con el Setup G. **Sin pasos de copia a mano.** Se ensayó en el PC de la oficina sobre una copia simulada del equipo (perfil del equipo de pruebas, base de datos de la F con `admin`/`ingeniero` y un usuario propio, un parámetro cambiado, calibración y correo propios) con el código y el `_internal` de la F y luego de la G: `docs/informes/tanda11/K11_compilacion_g.md`.

1. **Cierre Autoclave por completo** (las dos pantallas).
2. **Respaldo:** copie `C:\ProgramData\Especifika\Autoclave` completa a la USB (por ejemplo, `respaldo_F_2026-10-23`). La G migra la base de datos (versión 10 → 11, cuentas del sistema).
3. Compruebe el Setup: `Get-FileHash .\Autoclave_Setup_1.0.0-g.exe` contra la línea del Setup en `SHA256SUMS.txt`.
4. Ejecute `Autoclave_Setup_1.0.0-g.exe` y acepte el aviso de administrador. Sobre la F aparece la página nueva con **«Actualizar (conserva los datos)»** marcada: **déjela así**. **NO elija «Instalación limpia»** en el equipo de pruebas: borra el perfil, la calibración, los ciclos registrados y los usuarios (se prueba antes en un PC de prueba, casos A-N11 de la hoja de banco).
5. En «Tareas adicionales», igual que en la 8e: inicio automático **marcada**; «Configurar este PC como estación del autoclave» **DESMARCADA** (K9-1 se mantiene; por eso el paso 06 de asociación de táctiles no corre en el equipo de pruebas); arranque sin logo desmarcada.
6. Abra Autoclave y compruebe, además de lo de la 8c paso 7:
   - inicio de sesión con **`Ingeniero`** (o `ingeniero`) y la contraseña que ya tenía en la F; en OPCIONES › Usuarios, `Admin` e `Ingeniero` sin la acción Desactivar;
   - OPCIONES › Entradas / Salidas: sin «aire comprimido de chaqueta»; DO 13 libre;
   - OPCIONES › Parámetros del ciclo: las filas «Entrada 1/2/3»; Preciclo y Ciclo sin filas «—»;
   - con una sonda «No en uso» desconectada (p. ej. la Referencia en un programa de fábrica), Preciclo no muestra SEN-03;
   - en PREPARADO, habilitar o deshabilitar la impresora: confirmar, el software se cierra y vuelve a abrir solo en menos de 1 minuto con el cambio aplicado.
7. El primer arranque respalda el YAML de la instancia (`programa
espaldos_configuracion\<fecha>utoclave\config\instances\ACV-2026-001.yaml`) porque la G le quita `aire_comprimido_chaqueta`: es lo esperado.

**NO toque** lo mismo que en la 8c. **Volver a la F si la G falla:** cierre Autoclave, desinstale desde Configuración › Aplicaciones (el Setup F se niega sobre la G por ser más vieja; los datos de `ProgramData` se conservan), ejecute `Autoclave_Setup_1.0.0-f.exe` y **reemplace `C:\ProgramData\Especifika\Autoclave` por el respaldo del paso 2** (la base ya migrada a la versión 11, con `Admin`/`Ingeniero`, no se ensayó con la F: vuelva siempre al respaldo).

## 8g. Actualizar el equipo de pruebas a la H (G → H) con el Setup

Es la sección 8f con el Setup H. **No hay pasos de copia a mano.** Se ensayó en el PC de la oficina sobre una copia simulada del equipo (perfil del equipo de pruebas, base de datos y programas de usuario de la G con el Bowie & Dick en 99, un usuario propio, un parámetro cambiado, calibración y correo propios), primero con el código y el `_internal` de la G y luego con los de la H: `docs/informes/tanda12/K12_compilacion_h.md`.

1. **Cierre Autoclave por completo** (las dos pantallas).
2. **Respaldo:** copie `C:\ProgramData\Especifika\Autoclave` completa a la USB (por ejemplo, `respaldo_G_2026-10-24`). La H reescribe el programa de usuario Bowie & Dick (el anterior queda en `.bak`).
3. Compruebe el Setup: `Get-FileHash .\Autoclave_Setup_1.0.0-h.exe` contra la línea del Setup en `SHA256SUMS.txt`.
4. Ejecute `Autoclave_Setup_1.0.0-h.exe`. Deje marcada **«Actualizar (conserva los datos)»** y **no elija «Instalación limpia»**. Las tareas adicionales van igual que en la 8f (la casilla de estación queda DESMARCADA).
5. Abra Autoclave y compruebe, además de lo de la 8f paso 6:
   - en Preciclo y en la campana aparece el aviso **SIS-06** del Bowie & Dick (de 99 a 9 kPa), que no bloquea el inicio. En OPCIONES › Parámetros del ciclo › Bowie & Dick › Calentamiento, `presion_add_calentamiento` vale 9. En la bitácora de auditoría aparece la fila con el origen «migración tanda 12» (caso A-T12-01 de la hoja de banco);
   - la chaqueta 350/25 de los programas de usuario se conserva;
   - **anote `brecha_segura_temperatura`** (Esterilización) de los programas de usuario: sigue en 0,3, porque la actualización no toca ajustes de usuario válidos. Si quiere probar el 1,0 de C-07.1, cámbielo a mano (técnico o ingeniero) y lea antes la observación del techo en E-T12-03.
6. Para los ciclos del lunes, siga el bloque T12 de la hoja de banco (`docs/mis_plans/hoja_pruebas_banco_equipo_pruebas.md`), con el log del backend del día a mano.

**NO toque** lo mismo que en la 8c. **Volver a la G si la H falla:** cierre Autoclave, desinstale desde Configuración › Aplicaciones (el Setup G se niega sobre la H porque es más viejo; los datos de `ProgramData` se conservan), ejecute `Autoclave_Setup_1.0.0-g.exe` y **reemplace `C:\ProgramData\Especifika\Autoclave` por el respaldo del paso 2**. La G no conoce las claves nuevas de los programas: no se ensayó con un programa reescrito por la H, así que vuelva siempre al respaldo.

## 8h. Actualizar el equipo de pruebas a la I (H → I, o G → I) con el Setup

Es la sección 8g con el Setup I. **No hay pasos de copia a mano.** Se ensayaron los dos caminos en el PC de la oficina sobre una copia simulada del equipo (perfil, base de datos y programas de usuario de la G con el Bowie & Dick en 99, un usuario propio, un parámetro cambiado, calibración y correo propios): G → H → I y G → I, con el código y el `_internal` reales de cada compilación (`docs/informes/tanda13/K13_compilacion_i.md`).

1. **Cierre Autoclave por completo** (las dos pantallas).
2. **Respaldo:** copie `C:\ProgramData\Especifika\Autoclave` completa a la USB (por ejemplo, `respaldo_H_2026-10-26` o `respaldo_G_2026-10-26`).
3. Compruebe el Setup: `Get-FileHash .\Autoclave_Setup_1.0.0-i.exe` contra la línea del Setup en `SHA256SUMS.txt`.
4. Ejecute `Autoclave_Setup_1.0.0-i.exe`. Deje marcada **«Actualizar (conserva los datos)»** y **no elija «Instalación limpia»**. Las tareas adicionales van igual que en la 8f (la casilla de estación queda DESMARCADA).
5. Abra Autoclave y compruebe, además de lo de la 8f paso 6:
   - **desde la H:** ningún programa de usuario aparece dañado; el Bowie & Dick sigue en `presion_add_calentamiento` 9 y **no** aparece un aviso SIS-06 nuevo (la migración ya la hizo la H);
   - **desde la G:** lo mismo que en la 8g paso 5 (SIS-06 del Bowie & Dick de 99 a 9, fila de auditoría «migración tanda 12», `.bak`);
   - en los dos casos: la chaqueta 350/25 de los programas de usuario se conserva y `brecha_segura_temperatura` sigue en 0,3 (anótela, como en la 8g);
   - si alguna cuenta (`Admin`, `Ingeniero`) conserva la contraseña de fábrica, aparece el aviso **SIS-07** (no bloquea; se quita al cambiar la contraseña). Es de L0, no de VAP-01.
6. En el primer ciclo, compruebe en el log del backend: «consigna de chaqueta 328.2 kPa» para el Instrumental 134 de usuario (con la H decía 326.3). Siga el bloque T12 de la hoja de banco, que ya trae las cifras de la I.

**NO toque** lo mismo que en la 8c. **Volver a la H si la I falla:** cierre Autoclave, desinstale desde Configuración › Aplicaciones (el Setup H se niega sobre la I porque es más viejo; los datos de `ProgramData` se conservan), ejecute `Autoclave_Setup_1.0.0-h.exe` y **reemplace `C:\ProgramData\Especifika\Autoclave` por el respaldo del paso 2**. La I no cambia el formato de los programas ni de la base de datos respecto de la H, pero vuelva siempre al respaldo.

## A frente a B

**Instale la B** (`entrega/2026-10-22_b/`). La A queda solo como respaldo (sección 8).

| | Compilación A (`entrega/2026-10-22_a/`) | Compilación B (`entrega/2026-10-22_b/`) |
|---|---|---|
| Etiqueta / commit | `inst-2026-10-22-a` (18eb429) | `inst-2026-10-22-b` (23e76e2) |
| Suite en ese código | 5020 passed, 2 skipped, 3 xfailed | 5405 passed, 3 skipped, 3 xfailed |
| Asistente | 7 pasos, con clases de Mesa y campo libre "Modelo" | 8 pasos: solo Piso y Piso laboratorio, paso **Cámara** (litros y V/H) y nombre del modelo calculado (`SPK-SAT …`) (M1) |
| Correcciones de la instalación de hoy (P1) | No | Sí (lista abajo) |
| Correo a una dirección escrita a mano (C2) | Falla: dice "enviado" y no llega | Corregido: el resultado sale de lo que aceptó el servidor, por destinatario |
| Mantenimiento E1 (M2) | No | Sí: solo el preventivo reinicia el contador; la calibración deja de contar como mantenimiento |
| Decisiones 1.3 sobre el ciclo (Q1) | No | Sí, con revisión de seguridad. **No afecta lo de hoy** (no se corren ciclos hasta el lunes) |
| Lock de dependencias en UTF-8 (L1) | No | Sí (solo documentación del build) |
| Prueba de humo en el PC de la oficina | Arranca y abre el asistente (7 pasos) | Arranca y abre el asistente (8 pasos), sin traceback |
| Recomendada | Solo si la B falla al arrancar | **Sí** |

**Por qué la B:** trae las correcciones que estorbaban justo lo de hoy (E/S en modo prueba, calibración de la Referencia, la intro trabada) y el asistente con el modelo calculado que Cristian aprobó. Toda la B pasó la suite completa después de cada unión.

**Verificar en sitio con la B:** el recorrido completo del asistente en la pantalla real (en el PC de la oficina la pantalla es de 1536×864 y el teclado en pantalla queda fuera de la vista, así que la prueba de humo llegó solo al paso 1; el recorrido por los 8 pasos está cubierto por las pruebas QML de M1 y sus capturas en `docs/informes/tanda7/capturas/`).

Correcciones de P1 que **no** están en la A (afectan el trabajo de hoy):
- salidas momentáneas (puertas, bomba de vacío) que se cortaban a los 1-2 s en modo prueba;
- `aire_atmosferico_camara` que no se podía accionar;
- la sonda de Referencia que no se podía calibrar desde la pantalla táctil;
- el vigilante que saca del modo prueba cuando vence la sesión dueña, que moría a los pocos segundos;
- la intro que quedaba trabada si el backend tardaba más de 20 s;
- la tarjeta de sensor sin enlace, que culpaba al cableado.

**Rodeos en la A:**
- momentáneas: pulsar repetidamente en lugar de mantener;
- referencia: menú de ajustes (`--rol ajustes`);
- `aire_atmosferico_camara`: menú de ajustes;
- intro trabada: cerrar y volver a abrir.

## 9. Registros, por si algo falla
`C:\ProgramData\Especifika\Autoclave\data\`:
- `lanzador.log`
- `backend.log`
- `ui_puerta1.log`
- `ui_puerta2.log`
- `ajustes.log`

Si algo falla, lleve copia de esa carpeta (sin `autoclave.db` si no hace falta).

Desde la etapa VER, la primera línea de cada uno de esos logs dice qué versión corre (`Autoclave 1.0.0-alpha.N (<commit>)`).

## 10. Para quien compila: entregas `1.0.0-alpha.N` (etapa VER)
Desde la etapa VER (25-oct-2026) las entregas ya no se nombran por letra: la que sigue a la I es la **`1.0.0-alpha.1`**. Todo lo hace un solo comando, desde `dev` y con el árbol limpio:

```
python tools\entrega\compilar_entrega.py            (agregar --con-generador si la entrega lleva GeneradorCodigos.exe)
```

- **Antes:** estar en `dev` (con la rama de la tanda ya unida), sin cambios versionados y sin archivos sin versionar en `src/`, `packaging/`, `tools/instalador/` ni `Hardware/` (p. ej. los `.bak` de `src/autoclave/config/` o `i18n/`: moverlos fuera). Se necesitan el archivo de secretos de L0, el entorno de compilación (`..\_venv_t8_producto` o `AUTOCLAVE_PYTHON_COMPILACION`, o `--python-compilacion`) e Inno Setup 6 (`%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe`, o `--iscc`).
- **Qué hace:** corre la suite (las rojas de la corrida en paralelo se repiten en serie), calcula N (mayor etiqueta `v1.0.0-alpha.K` + 1), hace el commit `chore(ver): 1.0.0-alpha.N` (con la entrada de `docs/versiones/HISTORIAL_VERSIONES.md`), compila, verifica que la entrega sea neutra y que el `.exe` reporte `1.0.0-alpha.N`, genera `Autoclave_Setup_1.0.0-alpha.N.exe` y deja todo en `entrega\v1.0.0-alpha.N_<fecha>\` (con `usb\` listo para copiar). Al final crea la etiqueta anotada `v1.0.0-alpha.N`.
- **Si algo falla** (sale con 1): el commit se deshace, no queda etiqueta y N no se gasta; la carpeta incompleta queda como `...fallida-<hora>`. Si sale con 2, no se tocó nada: leer las líneas `BLOQUEA:`.
- **No hace push:** al final imprime `git push origin dev v1.0.0-alpha.N`, que se ejecuta a mano.
- El Setup compara `AppVerNum` = `1.0.0.<etapa × 1000 + N>` (alpha.1 = 1.0.0.1001, mayor que el 1.0.0.9 de la I): la alpha.1 actualiza una I instalada.
- **Compilaciones de verificación** (PyInstaller a mano, sin el script): no gastan N y se ven como `1.0.0-alpha.(N+1).dev+g<commit>` (con `.sucio` si había cambios sin commit), así que no se confunden con una entrega. Desde fuente se ve `1.0.0-alpha.N+fuente`.
- Dónde se ve la versión: Información del sistema, ticket de arranque, registro y ticket de cada ciclo, respaldos, `GET /system/info` y la primera línea de cada log. El firmware conserva su propia numeración.

# Planeación — Licencia por pago, código de activación y registro de equipos

Versión: borrador v3 (24-oct-2026). Reemplaza la v2. Estado: **pendiente de aprobación de Cristian** (quedan P-L3 y P-L9, que no bloquean). Implementación: después de los ciclos de validación del equipo de pruebas; condición para liberar la 1.0.0.

Dos partes:
- **Parte A**: software del autoclave (módulo de licencia, pantallas, estado seguro).
- **Parte B**: generador de códigos v2 y registro de equipos en el servidor físico de Especifika.

---

## 0. Decisiones confirmadas (24-oct)

| ID | Decisión |
|---|---|
| DL-01 | Código de activación **corto y tecleado** (~20 caracteres), no archivo ni firma larga. |
| DL-02 | Plazo y gracia **editables por equipo**, según el contrato. Defecto 60 + 10 días. |
| DL-03 | Se cuentan **días calendario** desde la fecha de instalación. |
| DL-04 | Existe **código de emergencia**: 72 h, máximo 3 por equipo. |
| DL-05 | Equipo bloqueado: arranca y **solo pide el código**. Para el usuario no hace nada más. Por dentro sigue el lazo de control (ver §2.4). |
| DL-06 | Equipos pagados de contado y el equipo de pruebas: **licencia permanente** desde la instalación, sin contador. |
| DL-07 | La clave final se emite con un **rol específico** y requiere **aprobación de 2 personas**, cada una con **TOTP** en su teléfono. |
| DL-08 | El contrato de venta incluirá la cláusula del bloqueo. |
| DL-09 | El registro y el generador viven en un **servidor físico propio** en la empresa (básico, 4 TB). Especifika usa **Siigo** para clientes y facturación. |
| DL-10 | El bloqueo **nunca interrumpe un ciclo en curso**. La pantalla de bloqueo lleva una **franja fija de estado de cámara y paro**. |
| DL-11 | El código de emergencia lo autoriza **un solo aprobador** con su TOTP. |
| DL-12 | Existe el **código de extensión** de plazo para renegociaciones del contrato, con **doble aprobación**. |
| DL-13 | La pantalla de bloqueo permite **Apagar equipo**, con confirmación y sin iniciar sesión. |
| DL-14 | Los 2 aprobadores son **los dueños de la empresa**. |
| DL-15 | El generador y el registro son un **software aparte**, en su propio repositorio privado (§3.6). |
| DL-16 | Mientras la empresa compra el servidor, el generador corre en el **PC de Cristian**, para pruebas y para los primeros equipos de 2026 (máximo 10). |
| DL-17 | El **código de instalación** (y el de reinstalación) también requiere **doble aprobación** con TOTP. La **clave de fábrica no**. |
| DL-18 | El rol Cartera (marcar "pago completo") lo ejerce **contabilidad**. |
| DL-19 | La interfaz web del generador conserva la **identidad de Especifika**: similar a su página web (https://especifika.com/), con sus transiciones y efectos. |
| DL-20 | El código de instalación aprobado vale para una **ventana de instalación de 7 días** fijada en la solicitud. |
| DL-21 | La clave de fábrica la puede emitir **cualquier técnico de la empresa** con cuenta en el generador, sin aprobación y con auditoría. |

---

## 1. Hallazgos previos (bloquean la 1.0.0)

**LIC-01 (CRÍTICO).** `src/autoclave/installation/activation.py` contiene en claro `_SECRET_INSTALL` y `_SECRET_FACTORY`, y el repositorio de GitHub es **público**. Cualquiera puede generar códigos de instalación y claves de fábrica válidos. El generador importa los mismos secretos.
- Acción inmediata (Cristian): pasar el repositorio a privado.
- Pasarlo a privado **no** borra el historial que alguien ya haya descargado o bifurcado. Los dos secretos actuales se consideran **comprometidos para siempre** y se rotan.
- Rotar no afecta a los equipos instalados: el código de instalación solo se valida en el asistente (`puente_instalacion.py`), no en cada arranque.
- Ningún secreto vuelve a estar en el código fuente (ver §2.2).

**LIC-02 (ALTO).** Las contraseñas semilla de `Admin` e `Ingeniero` son públicas (están en el repositorio) y solo se cambian en el **primer inicio de sesión**. Si en un equipo nadie entra nunca como `Ingeniero`, la contraseña pública sigue válida en campo, con el rol de mayor privilegio. Propuesta: el asistente de instalación obliga a fijar ambas contraseñas antes de terminar.

**LIC-03 (MEDIO).** `parametros_software.accdb` está versionado en el repositorio público. Hay que revisar su contenido.

---

## 2. Parte A: software del autoclave

### 2.1 Estados de licencia

```
PERMANENTE  ── (fin) nunca cambia
PLAZO       ── hoy <= instalacion + P            → uso normal + aviso con días restantes en Información del sistema
GRACIA      ── instalacion + P < hoy <= ... + G   → aviso al encender; al iniciar ciclo pide código; si no, espera 5 min y deja iniciar
BLOQUEADO   ── hoy > instalacion + P + G          → solo pantalla de bloqueo (ver 2.4)
EMERGENCIA  ── código de emergencia vigente (72 h) → uso normal con aviso; al vencer vuelve al estado que corresponda
```
- `P` (plazo) y `G` (gracia) en días, enteros: P de 1 a 365, G de 0 a 60. Viajan autenticados dentro del código de instalación (§2.3).
- La evaluación ocurre **solo al arrancar y al pedir el inicio de un ciclo**. Un cambio de estado nunca afecta a un ciclo en curso (DL-10).
- Un código de activación final válido → PERMANENTE, irreversible.
- Emergencia (DL-04, DL-11): se puede usar desde GRACIA o BLOQUEADO. Hay 3 en toda la vida del equipo. Cada una dura 72 h desde que se ingresa; no se suman ni se apilan.
- Extensión (DL-12): reemplaza P por un valor nuevo, siempre contado desde la fecha de instalación original. Se puede usar en PLAZO, GRACIA o BLOQUEADO; si el nuevo plazo cubre la fecha de hoy, el equipo vuelve a PLAZO. Un equipo PERMANENTE la rechaza.

### 2.2 Secretos y vinculación al PC
- **Secreto maestro**: solo en el servidor (Parte B). Nunca en el software.
- **Secreto de equipo** `K_e` (128 bits, aleatorio, uno por equipo): lo genera el servidor al dar de alta el equipo y se entrega al técnico dentro del código de instalación (§2.3). El software lo guarda cifrado con **Windows DPAPI (ámbito de máquina)**, así que copiar los archivos a otro PC no sirve.
- Si se filtra el `K_e` de un equipo, solo queda comprometido ese equipo.
- El módulo de licencia se compila con Cython y el lanzador verifica su hash al arrancar. El objetivo realista es disuadir: con acceso físico y conocimientos, cualquier verificación puede parchearse. Es un riesgo aceptado, cubierto por el contrato.

### 2.3 Formatos de código (Base32 sin 0/1/8/9, agrupados de a 4, con la normalización actual de `normalizar_codigo`)

| Código | Quién lo teclea | Contenido | Longitud |
|---|---|---|---|
| Instalación v2 | Técnico, una vez | `K_e` + tipo (permanente/plazo) + fecha de instalación + P + G, autenticado con el secreto de transporte | ~40 caracteres (aceptable una sola vez, en el asistente) |
| Solicitud | Lo muestra el equipo | serial + contador de solicitud + estado | ~8 caracteres |
| Activación final | Cliente o técnico | MAC_Ke(serial, solicitud, "FINAL") | 20 |
| Emergencia | Cliente | MAC_Ke(serial, solicitud, "EMERG", n.º 1–3) | 20 |
| Extensión | Técnico | MAC_Ke(serial, solicitud, "EXT", nuevo P) | 20 + 4 |

- La respuesta va ligada al código de solicitud vigente: no sirve en otro equipo ni se puede reutilizar.
- 20 caracteres Base32 = 100 bits de MAC. Tras 5 intentos fallidos, el ingreso se bloquea 15 min (contra la fuerza bruta).
- **Secreto de transporte** del código de instalación: tiene que ir dentro del software, porque es la única forma de descifrar `K_e` sin red. Quien lo extraiga y además vea un código de instalación obtiene ese `K_e`. Mitigación: el código de instalación lo teclea el técnico y no se le entrega al cliente.

### 2.4 Pantalla de bloqueo (DL-05, DL-10, DL-13)
- Muestra el serial, el código de solicitud, el campo del código y el teléfono de Especifika.
- Botón **Apagar equipo**: pide confirmación, no exige sesión y sigue el mismo flujo de apagado actual (ALL_OFF, cierre de BD y puertos, shutdown de Windows).
- **Franja fija de seguridad**, siempre visible: "NO ABRIR" / "Cámara segura", estado del paro de emergencia y aviso de tarjeta desconectada.
- **El backend sigue funcionando completo**: lazo de control, PREPARACION y estado seguro al arrancar, paro, ALL_OFF y alarmas de seguridad. Solo se rechazan `/cycle/start`, el login y toda la navegación.
- En la pantalla 2 (equipos de dos puertas) se muestra la misma pantalla de bloqueo.

### 2.5 Reloj
- Se guarda la **fecha más alta vista** en tres lugares: la BD, un archivo protegido con DPAPI y el registro de Windows (HKLM). Se toma la mayor de las tres.
- Si la fecha de Windows es menor que esa marca menos 1 día, se usa la marca y se audita `reloj_atrasado`. El conteo nunca retrocede.
- Si la fecha salta hacia adelante por error, los días se consumen; el remedio es el código de emergencia o el de extensión.
- Si el estado de licencia está ilegible o borrado en un equipo con PLAZO → BLOQUEADO. Es falla cerrada solo para la licencia; la seguridad del proceso no depende de esto.
- Instalación limpia o reinstalación: exige un código de instalación nuevo. El servidor lo emite con la **fecha de instalación original** y el mismo P/G, así que reinstalar no reinicia el plazo.

### 2.6 Auditoría (bitácora del equipo)
Eventos: `licencia_estado` (cada cambio), `licencia_codigo_aceptado` (tipo, sin el código), `licencia_codigo_rechazado`, `licencia_emergencia` (n.º y vencimiento), `licencia_extension` (P anterior y nuevo), `reloj_atrasado`. Textos en es y en.

### 2.7 Gestión de riesgos (para el fichero ISO 14971)
- **HAZ-LIC-01**: el bloqueo impide esterilizar en un hospital → retraso en la atención. Controles: aviso con días restantes, gracia de G días, 3 códigos de emergencia (un solo aprobador, DL-11), extensión de plazo, cláusula contractual y teléfono en pantalla.
- **HAZ-LIC-02**: bloqueo tras un corte de energía con la cámara presurizada o caliente → apertura insegura. Controles: §2.4 (lazo de control activo, franja fija, estado seguro al arrancar).
- **HAZ-LIC-03**: un fallo del módulo de licencia bloquea un equipo ya pagado. Controles: PERMANENTE irreversible, emergencia y reinstalación con código nuevo.
- Clasificación: el módulo de licencia no ejecuta funciones de seguridad, pero comparte proceso con el backend. Queda en **Clase C** salvo que se justifique la segregación (IEC 62304 §5.3.5).

---

## 3. Parte B: generador v2 y registro de equipos

### 3.1 Servidor físico (DL-09)
Mínimo recomendado. Con 4 TB sobra: la base ocupará megabytes, y el espacio sirve además para los respaldos de la empresa.
- 4 núcleos, 16 GB de RAM y **2 discos de 4 TB en RAID 1** (espejo), no un solo disco de 4 TB.
- UPS dedicada con apagado ordenado.
- Sistema operativo de servidor con soporte largo (P-L3, por definir).
- Solo red local + **VPN** (WireGuard o Tailscale) para los técnicos en campo. Nunca expuesto directamente a internet.
- Respaldo cifrado diario **fuera del sitio** (otra sede o almacenamiento en la nube), con prueba de restauración trimestral.

### 3.1b Etapa provisional en el PC de Cristian (DL-16)
Aceptable para un máximo de 10 equipos, con estos controles mínimos **desde el primer día**:
- Disco cifrado con BitLocker y cuenta de Windows con contraseña; bloqueo de pantalla automático.
- Respaldo cifrado diario de la base y del secreto maestro en dos lugares fuera del PC: un disco USB que no quede conectado y una nube.
- **Custodia del secreto maestro (§3.5) antes de emitir el primer código real**: los 2 sobres sellados con los dueños. Es el control más importante: si el PC se daña o se lo roban sin esa copia, los equipos a plazos no se pueden activar nunca.
- Acceso solo desde la red local de la oficina; sin VPN en esta etapa, así que los técnicos en campo piden los códigos por teléfono a la oficina.
- La base y el secreto se diseñan para **exportarse e importarse** al servidor (L3) sin cambiar ningún código ya emitido.
- Riesgo aceptado mientras dure: disponibilidad atada a que el PC esté encendido y Cristian disponible.

### 3.2 Roles y personas
| Rol | Quién | Puede |
|---|---|---|
| Administrador del sistema | Cristian | Usuarios y respaldos; **no** aprueba códigos |
| Técnico | Técnicos de instalación | Alta del equipo, código de instalación, solicitudes y consulta |
| Cartera | Contabilidad (DL-18) | Registrar abonos y marcar "pago completo" |
| Aprobador (×2) | Los dos dueños de la empresa (DL-14) | Aprobar claves finales y extensiones (los dos) y emergencias (uno) |

### 3.3 Flujo de emisión con aprobación
1. El cliente lee el código de solicitud del equipo y un usuario crea la solicitud en el generador (serial, tipo, motivo).
2. Para la clave final, el sistema exige que Cartera haya marcado "pago completo".
3. Aprobaciones con **TOTP** (6 dígitos, app en el teléfono), cada aprobador desde su propia sesión, dentro de 30 min:

| Tipo de código | Aprobaciones |
|---|---|
| Instalación / reinstalación (DL-17) | 2, de personas distintas |
| Activación final | 2, de personas distintas |
| Extensión de plazo | 2, de personas distintas |
| Emergencia | 1 (DL-11) |
| Clave de fábrica (DL-17) | Ninguna aprobación; la emite cualquier técnico con cuenta (DL-21) y queda auditada |

- Código de instalación: como hoy va ligado a la fecha del día, la aprobación tiene que darse el mismo día de la instalación, y el técnico queda esperando a los dos dueños. Decidido (DL-20): la aprobación vale para una **ventana de instalación de 7 días** (DL-20) fijada en la solicitud, y el código acepta cualquier día dentro de esa ventana.
- La clave de fábrica no puede alterar el estado de licencia (P, G, PERMANENTE): si pudiera, sería una forma de saltarse la doble aprobación.

4. Se emite el código, se muestra una sola vez al solicitante y se registra.
5. Todo queda en una auditoría de solo-adición encadenada por hash: quién solicitó, quién aprobó, cuándo, serial, tipo y motivo.
- TOTP con la biblioteca `pyotp`. Es una SOUP nueva **del generador**, no del autoclave.
- Si un dueño pierde el teléfono: el administrador revoca su TOTP y le reenrola uno nuevo, con constancia en la auditoría. Mientras tanto no se pueden emitir claves finales ni extensiones.

### 3.4 Registro de equipos
Datos por equipo:
- serial, modelo (`SPK-SAT …`), familia y fecha de fabricación;
- **cliente por NIT** (enlace a Siigo, sin duplicar la facturación), sede, dirección y contacto;
- fecha de venta, n.º de contrato, tipo de licencia, P, G y estado de pago;
- fecha de instalación y técnico instalador;
- versión de software y de firmware, e ID de la tarjeta;
- códigos emitidos y mantenimientos.

Sirve además para IEC 62304 §6 (saber qué versión hay en cada equipo) y para la tecnovigilancia del INVIMA (avisos de seguridad y retiros).
- Datos personales de los contactos: política de tratamiento según la Ley 1581 de 2012 (revisión legal pendiente).

### 3.5 Custodia del secreto maestro
- Se genera en el servidor y se guarda cifrado.
- La copia de recuperación se divide en **2 partes** (cada una inútil sola), impresas y en sobre sellado, una por cada dueño.
- Sin el secreto maestro no se pueden emitir códigos para ningún equipo: si se pierde, los equipos a plazos quedan bloqueados para siempre.

### 3.6 Software aparte (DL-15)
- Repositorio privado propio (por ejemplo `generador-especifika`), con versiones y ciclo de vida independientes del software del autoclave.
- Hoy `tools/generador` importa `autoclave.installation.activation`. Esa dependencia se corta: el único punto en común es el **formato de los códigos**, que se fija en un documento de interfaz con **vectores de prueba** (entradas y códigos esperados) que ambos repositorios verifican en sus pruebas.
- El software del autoclave solo lleva la parte de **verificación**. La parte de **emisión**, el secreto maestro y el registro viven solo en el generador.
- Marco normativo: el generador no es parte del dispositivo médico (no aplica IEC 62304), pero es una herramienta del sistema de calidad que afecta la disponibilidad del equipo: requiere validación de software según ISO 13485 §4.1.6.
- Aplicación web en Python (FastAPI, como hoy) con SQLite; pasar a PostgreSQL solo si el servidor lo justifica.
- Interfaz (DL-19): colores, tipografía, logo, transiciones y efectos tomados de la página web de Especifika (P-L9). Se arma primero un mockup visual para aprobación antes de programar las pantallas. Restricción: los efectos no pueden retrasar ni ocultar las confirmaciones de aprobación ni los códigos emitidos.

---

## 4. Etapas

| Etapa | Qué | Cuándo |
|---|---|---|
| L0 | Repositorio privado (Cristian). Sacar los secretos del código, rotarlos y hacer que el generador lea el secreto de un archivo fuera del repo. LIC-02 (contraseñas en el asistente). | **Ya**, independiente del resto |
| L1 | Parte A completa (módulo, estados, códigos, pantallas, reloj, auditoría, i18n), con un simulador de fecha para las pruebas | Tras los ciclos de validación |
| L2 | Generador v2 en su repositorio aparte: registro, roles, aprobaciones TOTP (instalación, final, extensión, emergencia), clave de fábrica sin aprobación, auditoría encadenada, exportar/importar y controles de §3.1b. Corre en el PC de Cristian hasta que llegue el servidor | En paralelo con L1 |
| L3 | Puesta en marcha del servidor: RAID, UPS, VPN, respaldos, migración del generador y custodia del secreto | Cuando llegue el servidor |
| L4 | Procedimiento del SGC para la emisión de licencias | Antes de vender un equipo a plazos |

---

## 5. Pruebas de aceptación (resumen)
- PLAZO → GRACIA → BLOQUEADO en los días exactos, con P/G de prueba. PERMANENTE nunca cambia.
- Vencimiento a mitad de ciclo: el ciclo termina COMPLETADO y el bloqueo aplica en el siguiente arranque o inicio de ciclo.
- Arranque en BLOQUEADO con la cámara a presión simulada: el estado seguro actúa, la franja "NO ABRIR" se ve y las salidas siguen PREPARACION.
- Apagar equipo desde la pantalla de bloqueo: ALL_OFF, cierre de BD y shutdown.
- Reloj atrasado 30 días: el conteo sigue con la marca más alta y se audita `reloj_atrasado`.
- Un código válido para otro serial o para otra solicitud se rechaza. Tras 5 errores, espera de 15 min.
- La 4.ª emergencia se rechaza. Al vencer una emergencia, el equipo vuelve al estado correcto.
- Extensión: en BLOQUEADO con un nuevo P que cubre hoy → PLAZO. En PERMANENTE → rechazada.
- Instalación limpia de un equipo con PLAZO: el código nuevo conserva la fecha original.
- Copiar la carpeta de datos a otro PC: `K_e` no se descifra y no instala.
- Generador: la clave final o la extensión con una sola aprobación no se emite; el mismo aprobador dos veces no emite; la emergencia sale con 1 aprobación; un TOTP vencido se rechaza; la clave final sin "pago completo" se rechaza.

---

## 6. Preguntas abiertas
- **P-L3:** sistema operativo del servidor (Ubuntu Server LTS o Windows Server). Por definir; no bloquea L0 a L2.
- **P-L9:** archivos de marca (logo vectorial, colores exactos, tipografías). Si no se tienen, se extraen de https://especifika.com/ y Cristian los valida en el mockup.

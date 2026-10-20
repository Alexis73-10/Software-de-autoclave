# Planeación — Generador de códigos de instalación y claves de fábrica

Estado: diseño a futuro (G1, tanda 2, 19-oct-2026). **Nada de este documento está implementado.** Lo implementado en G1 es el generador local con usuarios individuales; ver `docs/informes/tanda2/G1_generador_codigos.md`.

## 1. Situación actual (después de G1)

- El generador corre **solo en el PC de Cristian**: `tools/generador/`, ejecutable `GeneradorCodigos.exe`. Tiene su propia base (`C:\ProgramData\Especifika\Generador\generador.db`).
- Los usuarios entran por navegador desde la red local. Cada uno tiene cuenta propia con rol admin o usuario, contraseña con hash PBKDF2, bloqueo por intentos, sesión con expiración y respaldo diario.
- **Códigos** (`src/autoclave/installation/activation.py`): HMAC-SHA256 truncado sobre `serial + fecha` con dos secretos simétricos (instalación y fábrica) escritos en el código.
  - El generador los usa para generar.
  - **El software instalado en cada autoclave los usa para validar.**

## 2. Problema principal: los secretos viajan con el software

Con HMAC, quien valida tiene la misma clave que quien genera. Los dos secretos están dentro del código del software que se instala en cada equipo de cliente. Cualquiera con acceso al ejecutable o al código del autoclave puede extraerlos y **falsificar** códigos de instalación y claves de fábrica, para cualquier serial y cualquier día.

Mientras eso no cambie:
- el código del generador (y su ejecutable) no debe salir del PC de Cristian;
- **el ejecutable del generador no debe copiarse a ningún PC de cliente.**

## 3. Diseño propuesto: firmas asimétricas (Ed25519)

- **Clave privada** solo en el generador (servidor central, §4). Nunca en el software del autoclave ni en el repositorio.
- **Clave pública** embebida en el software del autoclave: solo puede **verificar**, no generar.
- **Código** = firma Ed25519 de un mensaje canónico, por ejemplo `v2|tipo|serial|fecha_desde|fecha_hasta|equipo_id`. Va codificado en Base32 sin ambigüedades (sin 0/O, 1/I) y en grupos para dictarlo por teléfono.
  - Una firma Ed25519 tiene 64 bytes: unos 103 caracteres Base32, demasiado para dictarlo.
  - Alternativas:
    - (a) QR o archivo de licencia en vez de código dictado;
    - (b) firma truncada (pierde la garantía criptográfica: descartado);
    - (c) código corto de **desafío-respuesta en línea** contra el servidor central, cuando el equipo tiene red.
  - Recomendación: archivo/QR firmado como vía principal y código corto en línea como respaldo.
- **Rotación:** el mensaje lleva la versión de la clave (`kid`) y el software admite varias claves públicas para poder cambiar la privada.
- **Compatibilidad:** durante la transición el software acepta el formato HMAC v1 (los códigos del día) y el firmado v2. Después, se retira v1 y con él los secretos simétricos.

## 4. Servidor central

- Un servidor de Especifika (VPS o servidor interno con VPN), no el PC de Cristian.
- **HTTPS** obligatorio (certificado válido; nunca HTTP fuera de la red local).
- Usuarios individuales con **MFA** para los administradores. Bitácora inmutable (solo anexar) de cada código emitido: quién, cuándo, serial, motivo y desde qué IP.
- **Respaldos automáticos cifrados** fuera del servidor (otra ubicación), con prueba periódica de restauración.
- La clave privada en un almacén de secretos: HSM o KMS en la nube, o como mínimo un archivo cifrado con la clave fuera del disco. Nunca en el código ni en el repositorio.
- API para el software del autoclave (activación en línea, §3 c) con límite de peticiones.

## 5. Secretos fuera del código

- Mientras siga el HMAC v1, mover los secretos a una variable de entorno o un archivo protegido **en el generador**. El software del autoclave igual necesita el secreto para validar, así que esto no resuelve el problema de fondo del §2. Solo con v2 desaparece el secreto del equipo.
- Revisar el historial del repositorio: los secretos actuales están en él. Considerarlos comprometidos y rotarlos al pasar a v2.

## 6. Relación con licencia y activación por pago

- El mismo esquema firmado sirve para **licencias**. Una licencia firmada con serial, vigencia, opciones habilitadas (F0, Líquidos, número de programas) y `kid` reemplaza al código de instalación del día.
- El servidor central emite la licencia al confirmarse el pago. El software verifica la firma localmente y no necesita red salvo para renovar.
- Queda fuera de alcance de la tanda 2 (licencia/activación, §3 de la instrucción) y va en su propio plan.

## 7. Pasos sugeridos

1. Decidir la vía de entrega del código v2 (archivo/QR, código corto en línea o ambas).
2. Servidor central con HTTPS, usuarios y MFA; migrar `generador.db` (usuarios y bitácora).
3. Generar el par Ed25519 en el almacén de secretos; embeber la clave pública en el software (verificación v1 + v2).
4. Emitir v2 en paralelo y retirar v1 en una versión posterior; rotar o retirar los secretos HMAC.
5. Licencias por pago sobre el mismo esquema.

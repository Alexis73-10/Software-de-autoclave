# Instalador tipo Setup (Inno Setup 6)

`autoclave.iss` arma un solo `.exe` de instalación a partir de una carpeta `Autoclave\` **ya compilada y verificada** (la de una entrega, p. ej. `entrega/2026-10-22_b/Autoclave/`). No recompila el programa.

## GUID (AppId)

```
{81C9DAB1-5CF8-4AD2-A7BE-15053E6ED43F}
```

Se generó una sola vez el 2026-10-22. **No se cambia nunca.** Gracias a él, Windows reconoce el Setup de la versión C como el mismo producto que la B y la actualiza en su lugar, en vez de instalar una segunda copia al lado.

## Cómo compilar

1. Inno Setup 6 (`winget install --id JRSoftware.InnoSetup -e --source winget`). En el PC de desarrollo quedó instalado por usuario en `%LOCALAPPDATA%\Programs\Inno Setup 6\`.
2. Verificar la carpeta `Autoclave\` de la entrega contra su `MANIFIESTO_CARPETA_Autoclave.sha256`.
3. Compilar:

   ```
   "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" /DEntrega=C:\ruta\a\entrega\2026-10-22_b tools\instalador\autoclave.iss
   ```

   Sin `/DEntrega`, usa `entrega\2026-10-22_b` del repositorio. El Setup sale en esa misma carpeta: `Autoclave_Setup_<versión>.exe`.
4. Calcular el SHA-256 del Setup y agregarlo a `SHA256SUMS.txt` de la entrega.
5. **No ejecutar el Setup en el PC de desarrollo**: instalaría el programa ahí.

## Qué hace el Setup

- Instala `Autoclave.exe` y `_internal\` juntos en `C:\Program Files\Especifika\Autoclave` (64 bits). La carpeta no se puede elegir: el programa solo guarda sus datos en `C:\ProgramData\Especifika\Autoclave` cuando corre bajo `%ProgramFiles%` (`utils/resources.raiz_datos_exe`). Además, solo se reconoce como instalado en esa ruta exacta (`instalador_exe.esta_instalado_aqui`); en otra, vuelve a ofrecer instalarse.
- Al actualizar, borra antes `_internal\` de la instalación, para no mezclar archivos de dos compilaciones.
- Crea accesos directos "Autoclave" en el menú Inicio y en el Escritorio común.
- Tarea opcional, marcada por defecto: "Iniciar Autoclave automáticamente al iniciar sesión en Windows". La crea `tarea_arranque.ps1`, que se extrae a un temporal y se borra al terminar. Usa el mismo mecanismo y el mismo nombre de tarea (`Especifika Autoclave - Arranque`) que `tools/estacion/03_tarea_autoclave.ps1`. Si después se ejecuta ese script, reemplaza la tarea y nunca quedan dos arranques. La única diferencia es la cuenta: el Setup usa la que tiene la sesión abierta al instalar; el script 03 usa `operador`. El desinstalador borra la tarea.
- `C:\ProgramData\Especifika\Autoclave`: solo crea la carpeta si falta y da permiso de Modificar a Usuarios, igual que el autoinstalador del exe. **Nunca** copia, sobrescribe ni borra archivos ahí (perfil, calibración, base de datos, usuarios). El desinstalador no la toca y avisa que los datos se conservan.
- No incluye `GeneradorCodigos.exe`, el perfil de instalación ni `data/`.
- Pide administrador. El asistente está en español, con inglés disponible.

## Cómo hacer la versión C

1. Compilar la carpeta C, verificarla y generar su manifiesto, como en la B.
2. En `autoclave.iss`, cambiar solo:
   - `#define AppVer "1.0.0-c"`
   - `#define AppVerNum "1.0.0.3"` (la letra de la compilación es el último número: b = 2, c = 3)
   - la ruta por defecto de `Entrega` (o pasar `/DEntrega=...`).
3. **No tocar `AppId`.** Compilar, calcular el SHA-256 y agregarlo a `SHA256SUMS.txt`.
4. En la estación, el Setup de la C se ejecuta con doble clic sobre la B ya instalada. La actualiza en el mismo lugar y conserva los datos de `ProgramData`. Si Autoclave está abierto, el Setup ofrece cerrarlo.

## Lo que el Setup NO hace

Los ajustes de la estación Windows van aparte, a mano, con los scripts de `tools/estacion/`:
- cuenta con inicio de sesión automático (01);
- arranque sin logo (02);
- notificaciones, actualizaciones y gestos (04);
- plan de energía (05).

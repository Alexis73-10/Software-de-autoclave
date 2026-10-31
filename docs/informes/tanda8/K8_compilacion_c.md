# K8 — Compilación C (tanda 8)

Fecha: 22/23-oct-2026, sesión principal (hora de Bogotá). **Hay compilación C y se recomienda instalarla** antes de los ciclos del lunes 26-oct, siguiendo la sección 8b del LEEME (actualizar un equipo ya instalado, B → C).

## Origen
- `tanda-8` unida a `dev` con `--no-ff`: 5a4b0df, "Merge tanda-8 en dev (S1, S2a, S2b, N8, R8, V8a, E1, E2, M8, U8, L8, D8, V8b, D8-3.18)". `git merge-base --is-ancestor tanda-8 dev`: OK. `git diff tanda-8 dev` vacío.
- Etiqueta `inst-2026-10-23-c` → 5a4b0df.
- Suite en ese código (unión de V8b, 1f5fa71; lo que sigue es solo documentación): **6201 passed, 7 skipped, 3 xfailed** (26 min), `suites/integ_v8b_final.log`.
- Compilado en un worktree limpio desprendido de la etiqueta (`C:\Users\tecni\Documents\_build_c`), con `git status` vacío.

## Entorno (D8-3.26, L8)
- Entorno virtual limpio de L8: `C:\Users\tecni\Documents\_venv_t8_producto` (Python 3.14.3, solo `requirements.lock.txt` + `requirements-dev.txt`). Se desinstaló de él el paquete editable `autoclave`, que apuntaba al worktree de L8; el `.spec` toma `src` de la carpeta de compilación (`pathex=['src']`).
- PyInstaller 6.20.0. `pip freeze` exacto: `entrega/2026-10-23_c/entorno_build.txt`.
- **Compilado desde PowerShell, con las rutas de Git quitadas del PATH**, por el hallazgo de L8 (la OpenSSL de Git Bash entraba en el paquete). Comprobado: `_internal` no tiene `libssl-3-x64.dll` ni `libcrypto-3-x64.dll`.

## Comandos
`python -m PyInstaller --noconfirm Autoclave.spec` (salida 0, 191 s) y `python -m PyInstaller --noconfirm GeneradorCodigos.spec` (salida 0, 33 s).

## Advertencias del build (ninguna bloqueante)
- Hidden imports opcionales no encontrados: `tzdata`, `importlib_resources.trees` y `scipy.special._cdflib`.
- 3 bibliotecas de macOS ignoradas.
- El "Logging error" interno de PyInstaller (el mismo de K2).
- Aviso de Pydantic V1 con Python 3.14 (de una dependencia; el programa usa Pydantic 2).

## D8-3.18: calibración neutra
Ninguna etapa lo había hecho; lo hizo la sesión principal en `tanda-8` (3b13992):
- plantilla `src/autoclave/config/plantillas/calibration_neutra.yaml`: la sección `factory` es idéntica a la del repositorio y la de usuario está en ganancia 1,0 y offset 0,0 en los 16 sensores, como "Restaurar por defecto";
- `Autoclave.spec` la empaqueta como `autoclave/config/calibration.yaml`;
- `tools/verificar_calibracion_neutra.py <dist>` compara byte a byte y sale con 1 si difiere o falta;
- `tests/test_t8_k8_calibracion_neutra.py` (7 pruebas): plantilla neutra, fábrica alineada con el repositorio, `.spec` y verificador.

Resultado sobre la C: `OK: calibración neutra empaquetada (sha256 4f13c26f…8347162)`.

DECISIÓN SIN CONFIRMAR: ver SP-3 en `DECISIONES_PARA_REVISAR.md`.

## Contenido verificado
- `Autoclave/`: 305 MB y 2297 archivos (la B tenía 2942). Primer nivel: `Autoclave.exe` y `_internal/`.
- Frente a la B faltan `cryptography`, `_cffi_backend`, `tzdata`, `websockets` y las DLL de OpenSSL de Git. Ninguno lo importa `src/autoclave` (comprobado con `grep`); el entorno limpio de L8 importa los 241 módulos del producto.
- Recursos en `_internal/autoclave/`:
  - `config/`, con `plantillas/` e `instances/ACV-2026-001.yaml` (máximo físico de canales + `io_ports` de R8);
  - `cycles/factory` (4 programas);
  - `i18n` (es, en), `images` (sin los mockups, que D8 movió a `docs/diseno/`) y `ui_qml`.
- No están `installation_profile.json*`, `data/`, `*.db` ni `.claude/`.

## Prueba de humo
Copia en `C:\Users\tecni\t8tmp\humo_c`, borrada al terminar:
- `Autoclave.exe --portable`: a los 60 s corren el lanzador y `--rol ui --door 1 --screen 0`.
- Ventana "Autoclave" con **INSTALACIÓN DEL EQUIPO, Paso 1 de 8 · Activación**. Captura, solo de la ventana del programa: `entrega/2026-10-23_c/prueba_humo_asistente.png`.
- Sin `Traceback`, `ERROR` ni `CRITICAL` en `lanzador.log` ni en `ui_puerta1.log`.
- Sin perfil no arranca el control, así que no se abrió ningún puerto COM.
- Procesos cerrados.

## Actualización B → C (ensayo sobre una copia)
Guion `C:\Users\tecni\Documents\_t8_tools\actualizacion_b_c.py`, fuera del repositorio. Simula el ejecutable instalado con `sys.frozen`/`_MEIPASS` y un ProgramFiles/ProgramData de prueba, igual que `tests/test_p1_rutas_build_congelado.py`.

1. **Con el código de la etiqueta B y el `_internal` de `entrega/2026-10-22_b`:**
   - siembra `programa/`;
   - perfil del equipo de pruebas (Hospitalario, 2 puertas abatibles simples, cámara 1 y 2, referencia y drenaje, solo aire comprimido, generador);
   - BD v9 con un usuario `cristian` y `temp_max_apertura` = 75;
   - calibración del equipo marcada.
2. **Con el código de la C y el `_internal` de `entrega/2026-10-23_c`**, programa reemplazado y datos sin tocar:
   - el perfil se lee;
   - la BD migra a v10 con sus usuarios y el parámetro en 75;
   - la calibración del equipo queda intacta: no la pisa la neutra;
   - los programas de fábrica se refrescan.
   - **Hallazgo:** con el `instances\ACV-2026-001.yaml` de la B, en E/S **no aparecen** `temp_2_camara`, `descompresion_lenta`, aire comprimido de chaqueta y de cámara, `agua_chaqueta` ni `buzer_alarma`. El programa no reemplaza un archivo de configuración que ya existe (diseño de `utils/resources.py`). Los dos parámetros nuevos del equipo tampoco existen.
3. **Tras reemplazar a mano `instances\ACV-2026-001.yaml` y `global_params.json`** (paso 6 del LEEME):
   - aparecen todos los canales que declara el perfil;
   - los parámetros nuevos valen 30 s y 30 min;
   - `temp_max_apertura` sigue en 75, porque el valor vigente vive en la BD.

Resultado: `OK: sin errores`. Salida completa en `C:\Users\tecni\Documents\_t8_tools\ensayo_b_c.txt`.

Rutas leídas en el código: `utils/paths.app_root` y `calibration_path`, `utils/resources.raiz_datos_exe`/`_sembrar` (solo `cycles/factory` se refresca) e `instalador_exe._copiar_programa` (reemplaza solo Archivos de programa).

LEEME (`docs/instalacion/LEEME_INSTALACION.md`, copiado a `entrega/` y a `entrega/2026-10-23_c/`):
- sección **8b**: orden con el software cerrado, respaldo, qué reemplazar, qué NO tocar y vuelta atrás;
- cabecera con la tabla **B frente a C**.

PREGUNTA (SP-5): ¿el instalador debería refrescar `instances\` al actualizar?

## Entrega (`entrega/2026-10-23_c/`, no versionada)
`Autoclave/`, `Autoclave_2026-10-23_c.zip` (zip hecho con Python: `Compress-Archive` falló porque un archivo estaba bloqueado por otro proceso; zip comprobado con `testzip`), `GeneradorCodigos.exe`, `SHA256SUMS.txt`, `MANIFIESTO_CARPETA_Autoclave.sha256`, `entorno_build.txt`, `LEEME_INSTALACION.md` y la captura.

```
7306ab7f81691bdf09b66b75c213c9912c1ed6812ee861e67a91295221164647 *Autoclave_2026-10-23_c.zip
9d4e9240c4fcc4cf3ac741094d554932165234b2acdcd198a9f27497177ee7e7 *GeneradorCodigos.exe
d3315ee17ef5b940248571f8d57d0b88e6809a9e758315a2e37e96f44ed6ef51 *Autoclave/Autoclave.exe
f07daef0a361de1cd0c84d53f0c6b64dd1936edab6dc438157e7ae900f5bb58b  CARPETA Autoclave/ (manifiesto ordenado de 2297 archivos)
```

## Verificar en sitio
- La actualización real B → C en el equipo, con la sección 8b.
- Que con la C la tarjeta conecta y las E/S muestran los canales del perfil.
- Las cuentas ADC de la prueba de banco de D8-1 (D-38), que fijan los umbrales de SEN-01.
- El menú de ajustes (`--rol ajustes`) con el entorno limpio. L8 verificó que sus módulos (qfluentwidgets, scipy) importan, pero no se abrió en esta prueba de humo.

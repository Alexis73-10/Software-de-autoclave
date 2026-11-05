# CMP — por qué no compila (5-nov, HEAD 47dd1e6e)

## Causa raíz (CMP-01, severidad ALTA, bloquea la entrega)
Falta el archivo de transporte v2 `C:\Users\tecni\Documents\especifika_secretos\activacion_v2.json`
(y no hay variable `ESPECIFIKA_TRANSPORTE`). Esa carpeta solo tiene `activacion.json` (v1, del 24-oct).
Los 3 `.spec` llaman a `secretos.entrada_compilacion_transporte()` (Autoclave.spec:160, AutoclaveBackend.spec:95,
AutoclaveSettings.spec:59), que hace `SystemExit` al no encontrarlo. Es lo que añadió la automatización (K_t v2, AUT-R3).

Evidencia (ver `cmp_pyinstaller_Autoclave.log`, `..._AutoclaveBackend.log`, `..._AutoclaveSettings.log`; las tres iguales):
- línea ~240: `LIC-01: compilación sin transporte de activación v2 (no existe ...\especifika_secretos\activacion_v2.json). Exporte el transporte desde el generador a ...`
- línea ~242: los secretos v1 sí se leen (solo huellas).
El fallo llega al final del análisis (tras ~7 min), por eso parece que "se cuelga" antes de fallar.

## Causas candidatas descartadas
- Secretos v1: presentes y válidos.
- Suite: en verde en worktree limpio de HEAD: 10789 passed, 11 skipped, 7 xfailed, 0 rojas (840 s). `suite_base.txt`.
  Los commits del 4-nov (vectores INSA/REIA, test_t12_c05, modo prueba) no rompen nada.
- Árbol/rama: `cmp_previas.log`: único error es estar en `tanda26` (la entrega exige `dev`); `dev` local = 47dd1e6e. Sin archivos versionados sucios.
- hiddenimports/excludes y `_build_info.py`: el análisis de los 3 `.spec` terminó sin error de módulos; no se pudo
  comprobar el empaquetado final porque el `SystemExit` ocurre antes. Pendiente de confirmar tras recibir el K_t.

## Acción pendiente de Cristian (no se puede hacer desde el código)
1. En el generador de códigos (donde está el K_t real): ejecutar `exportar-transporte` (formato v2, no el de prueba).
2. Guardar el resultado como `C:\Users\tecni\Documents\especifika_secretos\activacion_v2.json` (o apuntar
   `ESPECIFIKA_TRANSPORTE` a otra ruta). Debe ser versión 2 y distinto del K_t de prueba (§7.1) o la compilación se detiene.
3. Copiar `vectores_formato_v2.json` del generador si aún no está (AUT-R3; las pruebas ya corren en verde).
4. Reintentar: `python tools/entrega/compilar_entrega.py` desde `dev` limpio.

## Estado de los `.spec`
No compilan en este equipo hasta tener el archivo (los 3 fallan con LIC-01). `verificar_entrega_neutra.py` y
`verificar_calibracion_neutra.py` no se pudieron correr con sentido sin `dist/` (`cmp_entrega_neutra.log`,
`cmp_calibracion_neutra.log`: solo reflejan la ausencia de `dist`). Reconfirmar tras la acción 1-2.
No se generó, copió ni inventó ningún secreto; no se usó el K_t de prueba; sin cambios de código ni etiquetas.

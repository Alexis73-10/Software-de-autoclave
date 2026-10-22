# K2 — Compilación B (con lo de esta noche)

Fecha: 22-oct-2026, 08:01–08:10 (hora de Bogotá). Sesión principal. **Lista antes del plazo de las 13:45.**

## Origen
- `tanda-7` unida a `dev` con `--no-ff` (23e76e2, "Merge tanda-7 en dev (L1, P1, M1, C2, M2, Q1)"); `git merge-base --is-ancestor tanda-7 dev` = OK.
- Etiqueta `inst-2026-10-22-b` → 23e76e2.
- Suite en ese código (unión de Q1, 8a4a63d; lo siguiente es solo documentación): **5405 passed, 3 skipped, 3 xfailed** (19 min 59 s).
- Compilado en un worktree limpio desprendido de la etiqueta (`C:\Users\tecni\Documents\_build_b`), sin archivos sin commit (`git status` vacío).
- D2 NO está en esta compilación (regla 8).

## Entorno
- Python 3.14.3 (sistema), PyInstaller 6.20.0 (el mismo de K1).
- `entrega/2026-10-22_b/entorno_build.txt` (150 paquetes). Frente a K1 cambian solo dos líneas: el commit del paquete editable `autoclave` y `vulture==2.16`, que D2 instaló en el Python del usuario para buscar código muerto. `vulture` no lo importa la aplicación ni entra en el ejecutable.

## Comandos
`python -m PyInstaller --noconfirm Autoclave.spec` (salida 0, ~3 min) y `python -m PyInstaller --noconfirm GeneradorCodigos.spec` (salida 0, ~40 s).

## Advertencias del build
Las mismas 7 de K1 (hidden imports opcionales `pycparser.lextab`/`yacctab`, `importlib_resources.trees`, `scipy.special._cdflib`; 3 bibliotecas de macOS ignoradas), más un "Logging error" interno de PyInstaller durante el análisis (un mensaje de un hook con formato mal armado; no detiene el build ni cambia el resultado; también salió en la compilación de ensayo).

## Contenido verificado
- `Autoclave/`: 329 MB, 2942 archivos; primer nivel `Autoclave.exe`, `_internal/`.
- Recursos en `_internal/autoclave/`: `config/`, `cycles/` (4 programas de fábrica), `i18n/` (es, en), `images/`, `ui_qml/` (`qml`, `assets`).
- `Instalacion.qml` empaquetada trae el paso Cámara (claves `instalacion.paso_camara`, `carga_V`…).
- Ausentes (comprobado con `find`): `installation_profile.json*`, `data/`, `*.db`, `.claude/`, logs.
- `GeneradorCodigos.exe`: 18 MB.

## Prueba de humo (copia en `C:\Users\tecni\t7tmp\humo_b`, borrada al final)
1. `Autoclave.exe --portable` (como en K1, para no instalar nada en este PC): a los ~45 s corren el lanzador y `--rol ui --door 1 --screen 0`. Ventana "INSTALACIÓN DEL EQUIPO, **Paso 1 de 8** · Activación": es el asistente nuevo (con el paso Cámara; la A tenía 7).
2. Sin traceback ni líneas ERROR/CRITICAL en `lanzador.log`, `ui_puerta1.log` y `autoclave.log`. Sin perfil no arranca el control, así que no se abrió ningún puerto COM.
3. **Prueba adicional pedida (solo Piso y Piso laboratorio; paso Cámara):** no se pudo recorrer en la ventana, porque los campos solo aceptan el teclado en pantalla y este PC tiene una pantalla de 1536×864 (la interfaz es de 1200×1920): el teclado y el botón Siguiente quedan fuera de la vista, y el teclado físico no escribe en esos campos. Se comprobó en cambio, con el código de la etiqueta: `PuenteInstalacion().clases` = solo `piso` y `piso_lab`; `calcular_modelo('piso_lab', 2000, 'H', 2)` = `SPK-SAT 2000H2-LAB`. El recorrido visual está cubierto por `tests/test_m1_asistente_qml.py` y las capturas de M1. **Verificar en sitio.**
4. Procesos cerrados y copia borrada.

## Entrega
`entrega/2026-10-22_b/`: `Autoclave/`, `Autoclave_2026-10-22_b.zip`, `GeneradorCodigos.exe`, `SHA256SUMS.txt`, `MANIFIESTO_CARPETA_Autoclave.sha256`, `entorno_build.txt` y `LEEME_INSTALACION.md`. Copia del LEEME también en `entrega/LEEME_INSTALACION.md`.

```
d0fd4b6b9e24bb24fdfd77bcd3fe1a80d50dcaa7a9c31d466a960a9b17032cd6 *Autoclave_2026-10-22_b.zip
cb4306e630e65956d14585447d572f30277e7b200b0feafd3c791b6330af4d35 *GeneradorCodigos.exe
a22ffec8046194324ba2de0084bd1878727f24d4d42d6ebddb40f74002de56ff *Autoclave/Autoclave.exe
56fc24aa6f3ef6f2708f38ec480b4878db775bd98867a5150af28068635dd947  CARPETA Autoclave/ (manifiesto ordenado de 2942 archivos)
```

## Recomendación
**Instalar la B.** Ver la tabla "A frente a B" del LEEME.

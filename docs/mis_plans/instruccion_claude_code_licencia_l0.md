# Instrucción para Claude Code — Licencia, etapa L0 (secretos fuera del código y contraseñas al instalar)

**Fuente de verdad:** `docs/mis_plans/planeacion_licencia_pago.md` v3 (aprobada 24-oct), §1 (LIC-01 a LIC-03) y §4 (L0). Lee esas dos secciones completas; el resto de la especificación (L1, L2) **no** se implementa aquí.

**Modo:** sesión única, **sin subagentes**. Todo en español (código, comentarios, informe). Prioridad: velocidad. Rama `licencia-l0` desde `dev`. Informe: `docs/informes/licencia/L0_secretos_y_contrasenas.md`. Decisiones sin confirmar: sección propia del informe.

**No ejecutar en paralelo con otra tanda sobre este repositorio.**

## 0. Reglas
1. Nunca `main`, `--force`, `git add -A`, `git push --delete` ni reescritura de historial (`filter-repo`, `rebase` de commits publicados). No toques `stash@{0}`. No commitees `data/`, `.claude/`, `*.db`, `installation_profile.json*`, `dist/`, `build/`, `entrega/`.
2. **Secretos:** nunca escribas, imprimas, registres en log ni copies a un informe un valor de secreto real. No leas el archivo de secretos real (§1.1). Las pruebas usan secretos de prueba fijos, inyectados.
3. Prohibido: hardware, puertos COM, ejecutar `.ps1` o el Setup, instalar software del sistema. Autorizado: PyInstaller e `ISCC.exe` solo para comprobar que compila, si hace falta.
4. Ante ambigüedad: lo más seguro y reversible, como "DECISIÓN SIN CONFIRMAR". Nada fuera de este alcance: la lógica de ciclo, estado seguro y puertas no se toca.
5. Une a `dev` con `--no-ff` solo con la suite completa en verde (`pytest -n auto`; lo que falle solo en paralelo, repetir en serie, como en las tandas). Push de `dev` y `licencia-l0` al terminar.

## 0b. Inicio
Crea la rama `licencia-l0` desde `dev` y haz un primer commit `docs(licencia)` con `docs/mis_plans/planeacion_licencia_pago.md` y esta instrucción. Si la rama ya existe, reanuda desde lo que falte según el informe.

## 1. LIC-01 — Secretos fuera del código y rotación

### 1.1 Archivo de secretos
- Formato JSON: `{"version": 1, "instalacion": "<64 hex>", "fabrica": "<64 hex>"}` (32 bytes aleatorios cada uno).
- Ubicación por defecto: `%USERPROFILE%\Documents\especifika_secretos\activacion.json`, fuera del repositorio. Se puede cambiar con la variable de entorno `ESPECIFIKA_SECRETOS` (ruta completa al archivo).
- Nuevo `tools/secretos/generar_secretos.py`: crea el archivo con `secrets.token_bytes(32)`; **se niega** si el archivo ya existe; no imprime los valores, solo la ruta y una huella corta (los primeros 8 hex de SHA-256 de cada secreto) para comparar entre el generador y la compilación. **No lo ejecutes: lo ejecuta Cristian** (paso 3 de §4).
- Agrega `especifika_secretos/` y `activacion.json` a `.gitignore` por si alguien lo copia dentro del repo.

### 1.2 Software del autoclave
- `src/autoclave/installation/activation.py`: elimina `_SECRET_INSTALL` y `_SECRET_FACTORY` del código y su comentario. Los secretos se cargan, en este orden:
  1. el recurso empaquetado `config/activacion_secretos.json` (vía `resource_path`, solo en el ejecutable);
  2. el archivo de §1.1 (desarrollo).
- Sin secretos disponibles: **falla cerrada**. `validate_installation_code` y `validate_factory_key` devuelven `False` y se registra una advertencia una sola vez ("compilación sin secretos de activación"). Nunca hay un secreto por defecto.
- API pública intacta (`generate_*`, `validate_*`, `normalizar_codigo`) para no romper llamadas; añade la inyección de secretos para pruebas (parámetro o función `configurar_secretos(...)` usada solo por los tests).
- **Compilación:** `Autoclave.spec` y `AutoclaveBackend.spec` leen el archivo de §1.1 y lo agregan a `datas` como `config/activacion_secretos.json`. Si el archivo no existe, la compilación **se detiene con error** (no se produce un ejecutable que rechace todos los códigos sin que nadie lo note).
- El ejecutable sigue conteniendo el secreto: riesgo aceptado hasta L1 (secreto por equipo). Anótalo en el informe.

### 1.3 Generador (`tools/generador`)
- Sigue importando `activation.py` en esta etapa (el corte de la dependencia es L2), pero obtiene los secretos del archivo de §1.1.
- Sin archivo: el generador **no arranca** y muestra el motivo en la consola y en la página.
- `GeneradorCodigos.spec`: no empaqueta el archivo de secretos; el ejecutable del generador lo lee de §1.1 en el PC donde corre. Actualiza el comentario de la línea 15.
- Muestra en la página de administración la huella corta (8 hex) del secreto de instalación, para que Cristian compruebe que coincide con la de la compilación.

### 1.4 Historial
- No se reescribe el historial. Los secretos antiguos quedan en commits viejos y se consideran comprometidos; la rotación los invalida. Explícalo en el informe y en el LEEME de entrega (§3).

## 2. LIC-02 — Contraseñas de Admin e Ingeniero en la instalación
- Nuevo paso **obligatorio** en el asistente de instalación QML (`Pantallas/Instalacion.qml` y `puente_instalacion.py`), antes de terminar: fijar la contraseña de `Admin` y la de `Ingeniero`, cada una con confirmación.
- Reglas: las mismas del backend para contraseñas nuevas (reutiliza la validación existente, no dupliques reglas); además, distintas de las contraseñas semilla y distintas entre sí.
- Al terminar el asistente: hash guardado y `debe_cambiar_clave` = falso para esas dos cuentas; fila de auditoría `contrasena_fijada_instalacion` (sin la contraseña). Si el guardado falla, el asistente no termina.
- El paso no se puede saltar ni en reinstalación.
- Equipos ya instalados (migración de una compilación anterior): no se fuerza nada, pero si alguna de las dos cuentas conserva la contraseña semilla, aviso no bloqueante SIS-07 (o el siguiente código libre) en la bandeja de Preciclo y en la campana, visible solo para técnico e ingeniero, con textos es/en. DECISIÓN SIN CONFIRMAR si hace falta.
- Quita del código fuente los comentarios que dicen la contraseña semilla en claro (`db_manager.py`).

## 3. LIC-03 y LIC-04 — Solo revisión, sin cambios
- **LIC-03:** inspecciona `parametros_software.accdb` (tablas y tipo de datos, sin copiar valores sensibles al informe) y di si contiene información que no debería estar en el repositorio. No lo borres ni lo saques del índice.
- **LIC-04:** `validate_factory_key` no se usa en ningún lugar del software del autoclave (no hay diálogo de clave de fabricante, decisión 1.7 en `puente_instalacion.py`). Confírmalo y lista dónde se genera. No se cambia nada; es una pregunta para Cristian.

## 4. Cierre
1. Pruebas nuevas, todas con secretos de prueba:
   - con secretos: generar → validar OK; código de otro serial, otro día u otro secreto → rechazado;
   - sin secretos: validar devuelve `False` y advierte una sola vez;
   - el `.spec` falla sin el archivo de secretos (prueba de la función que lo lee, sin compilar);
   - generador sin archivo: no arranca;
   - asistente: no termina sin las dos contraseñas; rechaza la semilla, contraseñas iguales y la confirmación distinta; guarda el hash, apaga `debe_cambiar_clave` y audita;
   - aviso SIS-07 con contraseña semilla, y sin aviso cuando ya se cambió.
2. Ajusta las pruebas existentes que dependían de los secretos fijos y lístalas en el informe.
3. En el informe, una sección **"Pasos para Cristian"**, en este orden:
   1. ejecutar `python tools\secretos\generar_secretos.py`;
   2. guardar una copia del archivo de secretos fuera del PC (USB que no quede conectado) hasta que exista la custodia definitiva;
   3. comprobar que la huella del generador coincide con la de la compilación;
   4. la siguiente compilación del autoclave y el generador deben usar ese mismo archivo; los códigos del generador anterior dejan de servir.
4. Suite en verde, unión a `dev`, push, informe commiteado.

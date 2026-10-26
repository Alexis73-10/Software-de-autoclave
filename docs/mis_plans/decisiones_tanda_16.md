# Decisiones — Tanda 16 combinada (pendientes de la 14 + control de vapor por chaqueta + PRG-01 + DEU-01), 26-oct

**Fuentes de verdad, COMPLETAS:**
- `docs/mis_plans/planeacion_control_vapor_chaqueta.md` (especificación VCH, aprobada el 25-oct).
- `docs/mis_plans/planeacion_tanda_14_pendientes.md` (P1 a P10).
- Este archivo, que agrega lo decidido y prevalece si hay conflicto.

La tanda 14 nunca se lanzó: su contenido se ejecuta aquí. La numeración queda en 16.

## Decisiones de Cristian (no reabrir)

### VCH (25-oct)
- D1–D7 de VCH §2:
  - en equipos con chaqueta, CALENTAMIENTO y ESTERILIZACIÓN controlan `vapor_chaqueta`;
  - `vapor_camara` queda abierta desde el inicio de CALENTAMIENTO hasta el fin de ESTERILIZACIÓN;
  - ante sobrepresión se cierra `vapor_camara`;
  - el golpe inicial se acepta tal cual;
  - los equipos de mesa conservan el control con `vapor_camara`.
- D8. Se descarta un modo de barrido con vacío para líquidos (no se implementa).

### Tanda 14 (26-oct)
- D-14.1, D-14.3, D-14.6: se aplica la recomendación **R** sin esperar los datos del banco, con valores configurables y marcados DECISIÓN SIN CONFIRMAR; se reajustan con el banco.
  - P1: regla de coherencia con margen 0,3 K; programas de fábrica de 134 °C con `presion_add_esterilizacion` = 15.
  - P3: en la ventana de estabilidad, `T_ref ≥ T_obj − brecha_error_temperatura`.
  - P6: `DebounceAcumulado`, se confirma con 5 s acumulados fuera de rango dentro de una ventana de 10 s.
- D-14.2: se migra `brecha_segura_temperatura` 0,3 → 1,0 en los programas de usuario.
  - Si con eso el programa no cumple P1, también se sube `presion_add_esterilizacion` al mínimo.
  - Si entonces la consigna de chaqueta + 10 llega al alivio, no se migra nada y se avisa.
  - Va con auditoría, SIS-06 y `.bak`.
- D-14.4: R con el texto **«NO CONFORME»**.
  - Franja roja en la pantalla final.
  - Confirmar exige un reconocimiento explícito, que se audita con el usuario.
  - «NO CONFORME» va en el encabezado del historial y del ticket.
  - El resultado técnico sigue siendo COMPLETADO (no hay resultado nuevo).
- D-14.5: tope por cantidad, `max_reinicios_exposicion` (programa, sección `esterilizacion`, int, defecto 3, rango 0–10). La siguiente excursión confirmada después del tope da FALLO con un CIC nuevo.
- D-14.7: rangos de plausibilidad: temperatura 0–200 °C y presión −10–450 kPa. Fuera de rango, la lectura pasa a `None`, con un log del valor crudo una vez por episodio.
- D-14.8: R en SAF-05 y SAF-09. Una Referencia con excursión confirmada que pierde la lectura mantiene la exposición detenida y CIC-14 sigue corriendo.
- D-14.9 (P9): **ya hecho** en la etapa VER (`_version.py`). No se toca.
- D-14.10: R.
  - Etiquetas `archivo/<rama>` para las 3 ramas viejas.
  - Limpieza de worktrees y ramas unidas, solo con `-d`.
  - `main` solo se informa.
  - Las remotas `origin/tanda-*` solo se listan: las borra Cristian.
  - `/data/` va al `.gitignore`.

### Unificación de la protección de chaqueta (26-oct)
- D-CHQ: un solo corte de chaqueta para SAF-09 y VCH-CHQ.
  - `presion_max_chaqueta_control` lleva defecto **375 kPa abs** y rango **300 a (alivio de chaqueta − 10)**.
  - Esto reemplaza el 390 / 300–399 de VCH §5, que quedaba por encima del alivio mecánico (385).
  - Con DEU-01, el alivio sale de Parámetros del equipo.
  - Un mismo corte rige siempre (SAF-09) y en modo chaqueta (VCH-CHQ). En CALENTAMIENTO y ESTERILIZACIÓN con modo chaqueta, además, lleva la alarma no bloqueante de VCH-CHQ.

### Alcance extra (26-oct)
- PRG-01: validar que cada rol de sensor corresponda a una sonda activa del perfil de instalación.
- DEU-01: límites de presión desde Parámetros del equipo.
- Fuera de la tanda: líquidos C-11/C-12 (siguen abiertas las 11 preguntas de su §10).

### Ejecución
- Ejecución: **hasta 5 subagentes a la vez** (Cristian, 26-oct), en worktrees separados.

## Decisiones de diseño (Claude, chat). DECISIÓN SIN CONFIRMAR salvo que se diga otra cosa

### Fases
- D10. Los defectos de VCH §5 (salvo D-CHQ) son configurables y se reajustan con datos reales (VCH-01).
- D11. La lógica de decisión de CALENTAMIENTO y ESTERILIZACIÓN no cambia por VCH: solo cambian la salida actuadora según el modo, el aislamiento (VCH-AIS) y sus fallas.
  - El modo cámara debe quedar idéntico al actual, salvo los cambios de la tanda 14, que aplican a los dos modos.
- D12. El techo de RECUPERACION con histéresis de 2 kPa (C-08.3) se reemplaza por el aislamiento **solo en modo chaqueta**.
- D13. Las pruebas existentes de las dos fases se fijan explícitamente en modo cámara, sin tocar sus aserciones.
  - Excepción: las pruebas cuyo resultado cambia por una decisión de la tanda 14 (P1, P3, P5, P6, P7). En ese caso se actualiza la aserción, citando la decisión en el código de la prueba y en el informe.

### DEU-01
- D-DEU-1. Cuatro parámetros de equipo en `global_params.json`, junto a `pausa_max_esterilizacion_s`:
  - `presion_fondo_escala` (400);
  - `presion_suministro_vapor` (350);
  - `presion_alivio_camara` (385);
  - `presion_alivio_chaqueta` (385).
- Están en kPa abs, y el valor entre paréntesis es el defecto: la constante actual.
- Coherencia al guardar: suministro < alivio ≤ fondo de escala. Rango de cada uno: 100–1000.
- Si falta un parámetro o no es válido, se usa el defecto (mismo patrón de recorte).
- Las constantes de `catalogo_parametros.py` quedan solo como defectos. Todo lo que hoy las usa lee el valor del equipo.
- Los edita el mismo rol que hoy edita los demás parámetros del equipo. Cada cambio se audita con valor anterior y nuevo.
- Bajar un alivio puede volver incoherente un programa ya instalado. La regla de carga existente (`errores_programa`) lo rechaza al cargar, con el mismo mensaje de hoy.

### PRG-01
- D-PRG-1. Se valida en dos puntos:
  1. Al asignar roles de sensor (backend, `rutas/programas.py`, auditoría `ROLES_SENSOR`): se rechaza un rol que apunte a una sonda no activa en el perfil de instalación, con un mensaje es/en.
  2. Al iniciar el ciclo: si un rol apunta a una sonda no activa, el ciclo no inicia. Se reutiliza el aviso o bloqueo de sensor ausente existente con un motivo propio, o se crea un código nuevo si no hay uno adecuado.

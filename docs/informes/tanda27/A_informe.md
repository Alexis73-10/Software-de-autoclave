# Tanda 27 — Parte A: ajustes funcionales (5-nov)

Commits: `db21cafc` (A1+A2), `0f62f79a` (A3), `81c221b4` (A4). Suite: 10964 pasadas, 11 omitidas, 7 xfail; 1 roja preexistente (test_t26_ald_detalle_alarmas, codificación del subproceso en la prueba; falla igual en la base), corregida con encoding="utf-8" en la prueba (12 pasan). Ver `suite_parteA.txt`.

## A1 — Unidades en las dos pantallas
- Causa: el singleton `Unidades` solo arrancaba su sondeo de `GET /units` en su fábrica, que corre únicamente si un QML importa `Autoclave.Unidades` (solo 4 pantallas de Opciones). Idioma y tema no tienen el problema porque `Main.qml` los usa siempre.
- Arreglo: `unidades_qml.iniciar_sondeo()` idempotente, llamado desde `app.py` en las dos ventanas. Respuesta ausente o inválida conserva las unidades vigentes.
- Pruebas: `tests/test_t27_a1_unidades_sync.py`.
- AJ27-A1-01 (baja): `UnidadesQml.aplicar` no descarta respuestas viejas con una consulta en vuelo (idioma y tema sí); se corrige con la siguiente consulta (≤ 3 s).
- AJ27-A1-02 (baja): la prueba de `app.py` revisa el texto fuente; el arranque real de la 2.ª ventana queda para el banco.

## A2 — Sin standby en modo prueba
- `Standby._seguridad_pendiente` incluye `test_mode_active is True`; entrar al modo prueba cuenta como actividad. Pruebas: `tests/test_t27_a2_standby_modo_prueba.py`.
- AJ27-A2-01 (baja, DECISIÓN SIN CONFIRMAR): salir del modo prueba también reinicia el conteo de inactividad (coherente con TMG-04).

## A3 — INICIAR oculto con modo prueba
- Único control de inicio: `DeslizadorInicio` en `PantallaPreciclo.qml` (usada por las dos puertas); Reposo no tiene ninguno. `UiBridge.inicioCicloVisible` sale de `pantalla_ciclo.inicio_ciclo_visible` (falla cerrada: solo `modo_prueba is False` lo muestra). `comandos_ciclo` no envía `/cycle/start` con modo prueba (segunda defensa).
- El backend ya rechazaba (409 `modo_prueba_activo`, `rutas/ciclo.py`); sin cambios de rutas.
- AJ27-A3-01 (baja): el texto del 409 está solo en español y en el código (la UI hoy no lo muestra).
- AJ27-A3-02 (baja): `tests/banco/osc_capturas.py` usa un puente falso sin `inicioCicloVisible`; el deslizador no saldrá en esas capturas.
- DECISIÓN SIN CONFIRMAR: cerrar la confirmación «sin registro» cuando el control desaparece.

## A4 — Ninguna salida de mantener
- `abrir/cerrar_puerta_1/2` y `bomba_vacio` pasan a interruptor sin tope; retirados `SALIDAS_MOMENTANEAS`, los temporizadores de caducidad, el botón «Mantener», la renovación de 500 ms y la clave `io.ui.mantener`; `momentanea` se acepta e ignora con aviso. Entran en la orden pendiente de SMP.
- Enclavamiento abrir/cerrar en la misma orden (DECISIÓN SIN CONFIRMAR), con 409 `salida_prueba_opuesta_sin_apagar` si el OFF de la opuesta no lo acepta el enlace. La opuesta se toma de `door.do`.
- Un orden propia de `abrir_puerta_N` termina la inversión por atrapamiento D-ES-16 (DECISIÓN SIN CONFIRMAR).
- **Revisión (opus):** 1.ª pasada RECHAZÓ: el atrapamiento solo se evaluaba al recibir la orden (antes la renovación lo reevaluaba cada 500 ms). Corregido: vigilancia por tick en el lazo, solo en modo prueba, que apaga `cerrar_puerta_N` con atrapamiento o DI no vigentes (falla cerrada, sin bitácora, aviso en `avisos_corte_prueba`). 2.ª pasada: ACEPTAR. Ajuste registrado en `AJUSTES.md`.
- HAZ-IO-07 en `docs/riesgos/registro_riesgos.md` (sección Tanda 27) con los controles reemplazados.
- Hallazgos abiertos:
  - **AJ27-A4-01 (MEDIA, decisión de Cristian):** con la pantalla abierta, el keepalive de 30 s y el rearme de inactividad hacen que el respaldo de 90 s del backend nunca venza: motor de puerta o bomba pueden quedar ON sin tope. Opciones: tope de tiempo para el movimiento de puerta, o que la inactividad no se rearme con puerta/bomba en ON. No se implementó: contradice «interruptor sin tope».
  - **AJ27-A4-02 (baja):** la ruta de `/io/...` solo trata como atrapada la lectura 0; el lazo también corta sin lectura (un pulso de un tick).
  - **AJ27-A4-03 (baja):** «OFF ya comandado» no es confirmación por relectura; depende de la detección de discrepancia.
  - **AJ27-A4-04 (baja):** apertura de puerta y bomba sin corte por tick equivalente.
  - **AJ27-A4-05 (baja):** el texto `io.ui.dialogo_texto` menciona solo el seguro de atrapamiento y el bloqueo del aire; faltan ESG-02 y el enclavamiento.
  - Pendiente de banco: puerta con actuador real.

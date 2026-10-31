# T4 — E2: cámara segura, "NO ABRIR" y condición de inicio

Instrucción: tanda 2026-10-14 §2 T4; `planeacion_fin_de_ciclo_y_puertas.md` §5 y D-04, con el Principal de §1.1.

## 1. Qué se hizo

- `core/runtime/camara_segura.py` (creado en T3 por dependencia del lazo, completado aquí): `evaluar(estado, config, programas, profile)` → `(segura, motivo)`.
  - `camara_segura = pres_camara ∈ [atm − rango_presion_atm, atm + rango_presion_atm] Y temp_seguridad ≤ temp_max_apertura`.
  - `temp_seguridad`: máximo de los sensores Principales de los programas vigentes (en CICLO, el del ciclo; fuera, el seleccionado y, hasta que la cámara sea segura, el del último ciclo, SAF-01 de T3).
  - Falla cerrada: sin lectura válida (None, NaN, 0 °C), sin configuración o con Principal no declarado → no segura.
  - `temp_max_apertura` es el parámetro global (defecto 80 °C, techo 120 °C para pruebas; no cambió).
- `/status`: `camara_segura`, `no_abrir` (= no segura) y `camara_segura_motivo`, en cualquier estado.
- Condición de inicio (D-04): `preparado_state.esta_preparado()` exige `camara_segura()`; los programas los inyecta la `StateMachine` desde `ControlLoop.programas_para_seguridad`.
- Interlock de apertura de puertas: `ServicioPuertas._can_open_physical` usa la misma función (antes duplicaba la lógica con los mismos mensajes).

## 2. Pruebas

`tests/test_t4_camara_segura.py` (22): combinaciones de presión/temperatura, límites exactos, lecturas ausentes, configuración ausente, sensor Principal, `/status`, condición de inicio. Las de `/status` y de inicio se vieron fallar antes de implementar (KeyError / listo con cámara caliente). Ajustadas: `test_adenda_estados`, `test_e1_supply_inputs` (agregan `temp_max_apertura` a su configuración de prueba) y `test_preparado_chaqueta` (aísla la condición que prueba). Suite completa: ver `estado.md`.

## 3. Revisores

Ver §6.

## 4. DECISIONES SIN CONFIRMAR

- D-T4-1: la condición usa el `temp_max_apertura` **global**, como el interlock de puertas. La apertura automática sigue usando `min(ciclo, global)`.
- D-T4-2: el aviso sonoro al pasar de "no segura" a "segura" tras un ciclo (§5) no se agregó: hoy ya suena `BEEP_FALLO` desde el protocolo de fallo al alcanzar condiciones seguras; para el ciclo exitoso lo define el plan de voz/avisos. PENDIENTE.

## 5. PENDIENTES

- Mostrar "NO ABRIR" en las pantallas QML (T7).

## 6. Revisores (resultado)

`safety-reviewer`: 1 Alto, corregido.
- **SAF-01 (Alto)**: con el enlace caído, `/status` calculaba la cámara segura con las últimas lecturas guardadas; con una puerta manual "NO ABRIR" es la única barrera. **Corrección**: `evaluar(..., datos_vigentes=...)`: sin datos vigentes (`ControlLoop.datos_vigentes`), no es segura, motivo "Sin conexión con la tarjeta: datos no vigentes".
- Corregidos (Medio/Bajo): SAF-03 (`presion_admosferica` y `temp_max_apertura` se validan al arrancar, límites 50–110 kPa y 40–120 °C, DECISIÓN SIN CONFIRMAR; sin ellas, `CONFIGURACION_INVALIDA` en vez de un PREPARADO bloqueado sin diagnóstico); SAF-04 (mientras cuenta el último ciclo, rige el menor entre el `temp_max_apertura` global y el `finalizacion.temp_max_apertura` del ciclo, igual que la apertura automática); SAF-05 (la cámara segura va al final de `esta_preparado` para no saltar las alarmas de puertas); SAF-06 (una excepción al evaluar no abre ni corta el tick).
- Pendiente SAF-02 (Medio): si se pierde la sonda Principal del último ciclo, la cámara nunca es segura hasta reiniciar (falla cerrada sin salida auditada). Se trata en T6: el último programa se recupera de `ciclos.asignacion_sensores` tras un reinicio (TMG-02), y queda por decidir una liberación con rol y auditoría.

`timing-auditor`: sin Crítico ni Alto. Corregido TMG-01 (3 ticks seguros consecutivos antes de dejar de considerar el Principal del último ciclo). Pendientes: TMG-02 (persistir el último programa tras reinicio → T6), TMG-03 (instante en que `/status` ve CICLO con la copia del ciclo anterior; solo visual), TMG-04 (= SAF-02), TMG-05 (sin proveedor, PREPARADO y puertas caen a `temp_camara`; hoy siempre hay proveedor).

Preguntas de los revisores para Cristian: ¿el tope global de 120 °C es el deseado para abrir puertas manuales?; ¿se validó que con la chaqueta en régimen la sonda Principal en PREPARADO queda bajo `temp_max_apertura` (si no, D-04 impide iniciar)?; ¿hay admisión de aire en todos los estados donde puede quedar vacío residual?; una presión de 0 kPa se informa como "Cámara en vacío" (falla cerrada, diagnóstico confuso).

## 7. Comprobaciones manuales de Cristian

- Al terminar un ciclo, con la cámara a más de `temp_max_apertura`, `/status` debe dar `no_abrir: true` y el botón de inicio debe quedar bloqueado hasta que enfríe.
- Desconectar la sonda Principal en PREPARADO: `no_abrir: true` y no se puede iniciar ni abrir puertas con actuador.

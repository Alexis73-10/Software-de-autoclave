# Tanda 26 — informe (CMP, ALD, SMP, ARQ)

Rama `tanda26`. Detalle por punto en `CMP_informe.md`, `ALD_informe.md`, `SMP_informe.md` y `ARQ_informe.md` (misma carpeta).

**No se compiló la entrega.**

## Acción pendiente de Cristian (antes de compilar)

1. En el generador de códigos: ejecutar `exportar-transporte` (formato v2, no el de prueba) y guardar el resultado como `C:\Users\tecni\Documents\especifika_secretos\activacion_v2.json` (o apuntar `ESPECIFIKA_TRANSPORTE` a otra ruta). Debe ser versión 2 y distinto del K_t de prueba (§7.1) o la compilación se detiene.
2. Copiar `vectores_formato_v2.json` del generador si aún no está (AUT-R3).
3. Compilar desde `dev` limpio (la rama `tanda26` debe estar unida a `dev`):

```
python tools/entrega/compilar_entrega.py
```

## 1. Qué se hizo por punto

### CMP — por qué no compila
- Causa raíz (CMP-01, ALTA): falta `activacion_v2.json` y no hay `ESPECIFIKA_TRANSPORTE`; los 3 `.spec` llaman a `secretos.entrada_compilacion_transporte()` y terminan con `SystemExit` (LIC-01) al final del análisis (~7 min, por eso parecía un cuelgue).
- Descartado: secretos v1 (presentes), suite (10789 passed, 11 skipped, 7 xfailed, 0 rojas, 840 s, `suite_base.txt`), árbol y rama (solo el error de estar en `tanda26`).
- Sin cambios de código, ni secretos generados, ni K_t de prueba. Tras recibir el archivo hay que reconfirmar el empaquetado final y `verificar_entrega_neutra.py` / `verificar_calibracion_neutra.py`.

### ALD — detalle de todas las alarmas
- Toda fila de alarma abre `VentanaDetalleAlarma`: las 8 filas de `SeccionEstadoSeguro` (incluida NO ABRIR) y `alarmaArranque` de `Main.qml`. Nuevo `ui_qml/domain/detalle_aviso.py` (armado puro) y singleton `Autoclave.DetalleAviso`; `/status.camara_segura_limites` (solo lectura); i18n es/en `aviso_detalle.*`.
- Hallazgos: ALD-01 (ALTA) 8 filas sin detalle, corregido; ALD-02 (MEDIA) límite no publicado, corregido; ALD-03 (MEDIA) alarma de arranque, corregido; ALD-04 (BAJA) avisos de corte del modo prueba sin detalle, excepción justificada; ALD-05 (BAJA) hora de aparición tomada en la UI.
- Pruebas: `tests/test_t26_ald_detalle_alarmas.py` (12), más regresión de textos, tema, teclado, i18n y capas, en verde.

### SMP — salidas en modo prueba
- Orden pendiente por salida sostenida (3 s), `alternar` envía el inverso de lo último ordenado, relectura de 0,2 s con orden pendiente, marca «pendiente», apagar siempre disponible. Backend, lazo y MOD-08 sin cambios.
- Hallazgos: SMP-01 (MEDIA) toque doble enviaba ON dos veces, corregido; SMP-02 (BAJA) espera del Timer de 1 s, reducida; SMP-03 (INFORMATIVO) el PATCH no espera al lazo, lo que demora es la publicación en el tick de 0,5 s; SMP-04 (BAJA, residual) lo mostrado puede adelantarse a lo real hasta 3 s.
- Pruebas: `tests/test_t26_smp_orden_pendiente.py` (14); `test_f6_modo_prueba_async.py::test_m1...` ajustada sin relajar la regla.

### ARQ — el backend no actúa hasta que la UI termina el arranque
- ARQ-D1 `POST /arranque/iniciar`; ARQ-D2 retención en `ControlLoop._tick` paso 2f; ARQ-D3 liberación por (a) etapas terminadas y (b) `interfaz-lista`; ARQ-D4 espera sin tope y `ARR_SIN_INTERFAZ` a los 60 s; ARQ-D5 reinicio del backend con la UI abierta (`BarraReinicioBackend.qml`); ARQ-D6 sin perfil y asistente sin cambio; ARQ-D7 `AUTOCLAVE_ESPERA_INTERFAZ=0` solo fuera de `sys.frozen`; ARQ-D8 etapa 8 mínima y degradable (`ARR_SENSORES`, 10 s). Rutas actuadoras con 409 `arranque_retenido` durante la retención.
- Hallazgos: ARQ-01 y ARQ-02 (Media) la barra se adelantaba al backend, corregidos; ARQ-03 (Alta) rutas actuaban antes de mostrarse la UI, corregido; ARQ-04 (Media) estado seguro de arranque diferido hasta la liberación (pregunta 1); ARQ-05 (Baja) hasta ~70 ms entre aviso y liberación; ARQ-06 (Baja) latido a los 120 s sin perfil (pregunta 3); ARQ-07 (Baja) 409 como error genérico; ARQ-08 (Baja) respaldo de la intro a 1,5 s; ARQ-09 (Info) `test_i18n_linea_base` por claves de ALD (corregido después en `a7befce8`).
- Pruebas: `tests/test_t26_arq_retencion.py` (35) y `tests/test_t26_arq_ui.py` (8). OpenAPI base de la tanda 15 actualizada de forma justificada con `POST /arranque/iniciar`.

## 2. Mediciones (simulador M31)

SMP, `tests/banco/t26_smp_latencia_salidas.py` (12 órdenes ON/OFF, segundos desde el toque):

| Instante | Mediana | Máximo |
|---|---|---|
| Respuesta del PATCH (fc05 incluido) | 0,009 | 0,011 |
| Bobina cambiada en el simulador | 0,010 | 0,012 |
| `salidas_do` refleja (tick del lazo) | 0,340 | 0,519 |
| Primer `/status` del caché que lo refleja | 0,421 | 0,640 |
| Pantalla antes (Timer 1 s, modelado) | 0,809 | 1,392 |
| Orden pendiente resuelta ahora (relectura 0,2 s) | 0,422 | 0,641 |
| Botón muestra lo ordenado ahora | ≈ 0,01 | — |

Limitaciones: HTTP en proceso, repintado = emisión de `cambioDatos`, columna «antes» modelada. Peor caso anterior ≈ 1,6 a 2 s.

ARQ, `python tests/banco/t26_medicion_arranque.py --repeticiones 3` (`arq_medicion.txt`; segundos desde «UI visible»):

| corrida | iniciar | etapas terminadas | interfaz-lista | liberado | PREPARACION | bobinas ON antes de liberar |
|---|---|---|---|---|---|---|
| 1 | 0,01 | 0,63 | 7,38 | 7,45 | 7,62 | 0 |
| 2 | 0,01 | 0,94 | 7,39 | 7,39 | 7,68 | 0 |
| 3 | 0,01 | 0,94 | 7,39 | 7,40 | 7,69 | 0 |

Etapas (corrida 1): instalación/procesos/servicios < 1 ms; configuración 0,026; calibración 0,024; base 0,041; módulos E/S 0,258; sensores 0,261; espera de la interfaz 6,75. Antes de liberar solo hubo 2 escrituras de bobinas, ambas de apagado. PREPARACION llega 0,2 a 0,3 s después de liberar (lazo de 0,5 s sin cambios). Falta medir el PC industrial (ventanas y .exe).

## 3. Decisiones sin confirmar

- SMP: plazo de 3 s de la orden pendiente; un rechazo no borra la orden aceptada anterior; la etiqueta ON/OFF muestra lo leído y solo el botón lo ordenado; marca de pendiente como texto aparte.
- ALD: nivel y color de las filas sintéticas; textos de «qué hacer» (es/en); hora de aparición tomada en la UI.
- ARQ: 60 s de `ARR_SIN_INTERFAZ`; reinicio del backend con la UI abierta (vigilancia 1 s, reenvío, barra); `AUTOCLAVE_ESPERA_INTERFAZ=0` solo fuera del compilado; etapa 8 mínima con plazo de 10 s y degradable; estado seguro de arranque diferido hasta la liberación; 409 `arranque_retenido` en las rutas actuadoras.

## 4. Preguntas abiertas para Cristian

1. ARQ-04: con un ciclo interrumpido y la cámara a presión, ¿se acepta que el venteo automático espere a que la UI termine el arranque (segundos normalmente; sin tope si la UI no aparece)? La alternativa es exceptuar de la retención el protocolo de estado seguro de arranque (solo la lenta), lo que contradice «ninguna salida ON».
2. ARQ-07: ¿texto propio en la UI para `arranque_retenido` o basta el error genérico?
3. ARQ-06: ¿el latido de apagado debe arrancar aunque la UI nunca pida `iniciar` (hoy, a los 120 s)?
4. ¿Se confirma que la pantalla 2 sola (puerta 1 caída) no pida `iniciar`? Hoy el equipo queda retenido y la pantalla 2 muestra «Sin respuesta del sistema de control» a los 20 s y la barra de reinicio si el backend se reinicia.
5. CMP: exportar `activacion_v2.json` y `vectores_formato_v2.json` (acción de arriba) para poder compilar.

## 5. Riesgos, trazabilidad y banco

Riesgos HAZ-ARQ-01 (ALTA), HAZ-ARQ-02 (MEDIA), HAZ-SMP-01 (MEDIA) y HAZ-ALD-01 (MEDIA) en `docs/riesgos/registro_riesgos.md`; trazabilidad REQ-52 a REQ-55 en `docs/riesgos/matriz_trazabilidad.md`; `CLAUDE.md` con la sección de la tanda 26. Banco: bloque T26 (T26-01 a T26-06) de `docs/mis_plans/hoja_pruebas_banco_equipo_pruebas.md`: arranque real con las dos pantallas, reinicio por reasignación, latencia con el M31 real, ninguna bobina ON antes de la liberación, equipo retenido sin aviso y tarjeta de NO ABRIR.

## RESULTADO DEL REVISOR: pendiente

## SUITE FINAL: pendiente

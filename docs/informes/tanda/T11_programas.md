# T11 — Programas de fábrica

Instrucción: tanda 2026-10-14 §2 T11 con la decisión 1.2.

## 1. Qué se hizo

**Numeración**: 1 Bowie & Dick, 2 Instrumental 134, 3 Instrumental 121, 4 Líquidos. No se creó un quinto programa. Una prueba lo verifica.

**`cycles/factory/instrumental_121.json`** (nuevo), derivado de `factory/instrumental_134.json`:
- 121 °C en calentamiento y esterilización (son parámetros vinculados);
- esterilización de 15 min;
- el mismo prevacío;
- `cycle_number` 3, `cycle_id` `instrumental_121`.

Ya existía `user/instrumental_121.json` con el mismo id y número. Como el de usuario reemplaza al de fábrica homónimo al cargar, no hay número repetido.

**`cycles/factory/liquidos.json` y `cycles/user/liquidos.json`** (nuevos, idénticos), `cycle_number` 4:
- sin prevacío (conteos A a D en 0) y sin secado (`tiempo_secado = 0`);
- `tasa_presion` 10 kPa/min y `tiempo_estable_preesterilizacion` 10 s;
- 121 °C / 15 min;
- `globals.tipo_carga = liquido`;
- descompresión modo 4: enfriamiento con contrapresión de aire comprimido (250 kPa, ajustada tras la revisión) hasta 80 °C (`modo_4.temperatura_enfriamiento`) medidos con el Principal;
- F0 desactivado.

El resto se copió del Instrumental 121, incluidos `finalizacion.temp_max_apertura` de 80 °C y la apertura automática desactivada. **Valores PROVISIONALES**: hay que validarlos en banco con vidrio real.

**Omisión de fases (verificado, sin código nuevo):**
- `SecadoFase.update()` devuelve COMPLETADO con `tiempo_secado == 0` (`secado.py:37-40`).
- `PrevacioFase._inicializar()` salta todos los tipos con conteo 0 (`prevacio.py:91-108`).

**F0 por clase:** ya estaba en T3 (`sensores_ciclo.f0_disponible`: solo en equipos de laboratorio). El backend rechaza activarlo fuera de laboratorio. Los 4 programas lo traen desactivado.

**Validaciones (1.2):**
- `tipo_carga = liquido` exige modo 4 o 5, al cargar y al editar (T10, `catalogo_parametros.errores_coherencia`).
- La rápida está prohibida con la carga caliente en el protocolo de fallo, el estado seguro y la válvula de reposo (T5).

**Modo 0 de descompresión:** se conserva. `valvula_reposo.abrir_valvula_modo` y `ProtocoloFallo._modo_efectivo` lo tratan como modo 2 (lenta), con el timeout del modo 2. El estado seguro no depende de un timeout inexistente (ver el informe de T5).

## 2. Prueba de integración (`tests/test_t11_programas_integracion.py`)

El simulador del repositorio (`autoclave.simulador`) solo repite ciclos grabados, así que se construyó una **planta simulada** física y simple:
- presión parcial de vapor más aire;
- carga que sigue a la saturación del vapor;
- sonda con retraso de primer orden (τ = 15 s);
- escapes, vacío, aire comprimido, pérdidas térmicas y chaqueta.

`CicloState` corre con el `SetOutput` real sobre una tarjeta simulada, con la configuración real (presión atmosférica de 75 kPa) y un reloj monotónico virtual de 0,5 s por tick.

Resultado: los **4 programas terminan COMPLETADO** y recorren PRECALENTAMIENTO → PRE_VACIO → CALENTAMIENTO → ESTERILIZACION → DESCOMPRESION → SECADO (en Líquidos, PRE_VACIO y SECADO se saltan). Líquidos además:
- no usa el vacío;
- enfría con aire comprimido;
- no abre la rápida con la sonda por encima de 80,5 °C;
- termina por debajo de 80,5 °C.

Hallazgo de la construcción de la planta, útil para el banco: el corte por calidad de vapor del calentamiento (P ≥ P_sat(T) + 11 kPa por encima del 97 % del objetivo) solo se cumple si la sonda va detrás del vapor. Con una sonda muy rápida, o con fugas o pérdidas altas, el calentamiento puede quedar oscilando entre el 97 % y el objetivo hasta el timeout. Conviene vigilarlo en el banco (`presion_add_calentamiento`).

## 3. DECISIONES SIN CONFIRMAR

- D-T11-1: Líquidos se siembra también en `cycles/user/`, porque `/cycle/select` solo acepta programas de usuario.
- D-T11-2: los demás parámetros de Líquidos se toman del Instrumental 121 sin cambios (precalentamiento, chaqueta 300 kPa, `temp_max_apertura` 80 °C), salvo la contrapresión de enfriamiento: 250 kPa (SAF-05).
- D-T11-3: los parámetros de la planta simulada son ilustrativos. La prueba verifica la secuencia y la lógica, no la dinámica real.

## 4. PENDIENTES

- Validar Líquidos en banco con vidrio real: tasas, enfriamiento y contrapresión.
- El choque térmico (L3) queda fuera de esta versión.

## 5. Revisores (resultado)

**timing-auditor**: 0 críticos, 4 altos, 2 medios y 2 bajos. **safety-reviewer**: 0 críticos, 3 altos, 4 medios y 2 bajos.

Corregidos:
- **TMG-01 (alto)**: en el enfriamiento de los modos 4/5, `_mantener_chaqueta` seguía reponiendo vapor de chaqueta mientras la fase la venteaba y la enfriaba con agua. Ahora `DescompresionFase.chaqueta_en_enfriamiento` hace que el ciclo apague el vapor de chaqueta en esas sub-etapas. La prueba verifica que vapor y agua de chaqueta nunca coinciden.
- **TMG-02 / SAF-04 (alto / medio)**: el paso de enfriamiento a la rápida exige 3 lecturas seguidas, como el protocolo de fallo.
- **SAF-01 (alto)**: una lectura 0 (sensor sin señal) contaba como "carga enfriada" y abría la rápida. Se agregó un predicado único, `lectura.carga_enfriada()`, que exige lectura válida y distinta de 0. Lo usan la descompresión, el protocolo de fallo y la válvula de reposo; esta última también con debounce de 3.
- **TMG-04 / SAF-07 (altos / medio, la prueba)**:
  - el aire ya no desaparece sin válvula: sale por la lenta, desplazado por el vapor;
  - la chaqueta se ventea con agua;
  - se cargan explícitamente los JSON de fábrica;
  - la rápida se mide contra la temperatura real de la planta;
  - hay aserciones de duración de fase frente a su timeout y de fases saltadas en un tick;
  - hay un caso de sonda en 0 durante la descompresión.
- **SAF-05 (medio)**: la contrapresión de Líquidos pasa de 200 a **250 kPa**, por encima de P_sat(121) ≈ 205 kPa. Regla nueva: con carga líquida, contrapresión ≥ P_sat(t_est) + 30 kPa.
- **SAF-06 (medio)**: con carga líquida, el validador exige además sin prevacío, sin secado y sin apertura automática.
- **TMG-06 / SAF-09 (medio / bajo)**: el timeout de la descompresión deja un motivo específico ("Timeout de enfriamiento del modo 4 (T=…, P=…)").
- Guarda nueva: un programa de carga líquida solo se inicia en equipos con `has_liquids` (409 `carga_liquida_no_disponible`).

Altos que no se corrigen en código (decisión de diseño de 1.1 y 1.2), registrados como **HAZ-LIQ-01** en `docs/riesgos/registro_riesgos.md`:
- **SAF-02 / SAF-03 / TMG-03**: en Líquidos, enfriamiento, rápida, puerta y meseta se deciden con el Principal (`temp_camara`).
  - La instrucción fija `temp_camara` como Principal de fábrica en todos los programas. En equipos de laboratorio, esa sonda es flexible y se coloca en el líquido.
  - Riesgo residual: depende de que el operador coloque la sonda en la carga, y de validar en banco el volumen, el equilibrado y el enfriamiento.
  - Alternativas para que Cristian decida: exigir `temp_2_camara` como Referencia en Líquidos, o un tiempo mínimo de enfriamiento por carga.
- **TMG-05**: sin prevacío, el aire residual puede impedir llegar a 121 °C con el techo P_sat + 11, o dar presión alta. En la planta simulada se resuelve con la purga por la lenta, pero en el equipo hay que validarlo en banco.

Pendientes (no son altos ni críticos):
- SAF-08: el pitido de "condiciones seguras" usa el tope global y no el `temp_max_apertura` del ciclo.
- TMG-07: parchear `time.time` en la prueba.
- TMG-08: `P_ATM` global en la prueba.

## 6. Comprobaciones manuales de Cristian

- En la pantalla de ciclos deben aparecer los 4 programas con sus números (1 a 4).
- Ciclo de Líquidos en banco:
  - no hace prevacío ni secado;
  - tras esterilizar, enfría con aire comprimido hasta 80 °C antes de abrir la rápida.

# Cierre de la 1.0 — estado al 9-nov-2026

Complementa `cierre_1_0_checklist.md` (30-oct, alpha.12). Base de esta revisión: `1.0.0-alpha.25` (commit `d9db08dc`, sin etiqueta `v1.0.0-alpha.25` todavía; última etiqueta: alpha.24). Verificado con búsquedas en el código y en `docs/`; lo que depende del banco no se puede saber desde el repositorio y se marca así.

## Dónde estamos en las etapas

- **Alpha → beta (congelar funcionalidad): NO cumplido.** Desde el checklist (tandas 25 a 34) siguió entrando funcionalidad nueva: dashboard de Reportes, modo oscuro, entrega de la cámara al fin de ciclo, enfriamiento de líquidos con contrapresión, cascada de chaqueta, zoom de la gráfica, cancelar con deslizador. La tanda 34 sigue siendo de funciones.
- **Beta → rc (banco aprobado): no evaluable desde el repositorio.** La hoja de banco no trae resultados firmados que yo pueda leer; eso lo sabes tú.

## Sección A (software) — estado

- A-01 Indicador de puerta con DI vencida: SIN HACER. No existe `doors_vigentes` en `/status`; `IndicadorPuerta.datosVigentes` sigue siendo solo la conexión con el backend (hay chequeo de `estadoModuloEs`, pero no de la vigencia de la trama DI).
- A-02 Registro de riesgos AIN-R3 / HAZ-IO-02 desactualizados: SIN VERIFICAR el texto del registro (el catálogo ya no tiene `falta_calibracion_requerida`, así que el código cambió; falta revisar el documento).
- A-03 Hoja de banco al día: PARCIAL / sin verificar. Hay pruebas de T24..T33 en `pruebas.py`, pero las precondiciones siguen citando Setup 1.0.0-alpha.2; revisar H-08 (NO CONFORME retirado).
- A-04 Suite verde con `-n auto`: SIN HACER. No hay `xdist_group`; el cierre de la tanda 30 reporta fallos intermitentes en la corrida completa (4 que pasan al repetir) y uno preexistente en dev (`test_t26_ald_detalle_alarmas::test_qml_tocar_no_abrir`).
- A-05 `/cycle/abort` idempotente: SIN HACER (no existe `ya_cancelado`).
- A-06 Anomalías conocidas de la 1.0: SIN HACER. La última es `anomalias_conocidas_1.0.0-alpha.4.md`; faltan las de las alpha.5 a alpha.25.
- A-07 Registro de riesgos con P/S y aprobación: SIN HACER. Sigue «BORRADOR» y con 8 líneas «por completar».
- A-08 Herramienta de entrega para beta/rc/final: SIN HACER (`compilar_entrega.py` solo acepta `v1.0.0-alpha.N`). ES LO PRIMERO QUE HAY QUE HACER: sin esto no se puede compilar una beta.
- A-09 Aviso sobre la gráfica a pantalla completa: SIN VERIFICAR.
- A-12 `parametros_software.accdb` sigue versionado en `docs/referencia/`.

## Sección C — decisiones que siguen abiertas

- C-01 (alcance: equipo de pruebas o liberación clínica) y C-02 (licencia L1/L2): sin decisión escrita. Son las que más cambian el camino.
- C-04 (CIC-19 sin debounce): el código sigue sin debounce.
- C-10: las DECISIÓN SIN CONFIRMAR crecieron con las tandas 26 a 34 (listas en cada R_informe).

## Orden sugerido

1. Decidir C-01 y C-02.
2. A-08 (entrega con etapa) y crear la etiqueta/compilación pendiente de la alpha.25.
3. Declarar congelamiento de funciones (ninguna tanda nueva de funciones; solo correcciones y cierre del banco).
4. A-01, A-04, A-05, A-06, A-07 y A-03.
5. Compilar `1.0.0-beta.1`.
6. Banco (sección B) y decisiones C restantes; luego `1.0.0-rc.1`.

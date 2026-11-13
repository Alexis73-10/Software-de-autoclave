# Programa de fábrica Prion 134 °C / 30 min (PRI-01..04) (9-nov-2026)

Responde e informa SOLO en español. Cambio de configuración (programa nuevo), sin cambio de lógica de control. Ante ambigüedad, lo más simple y `DECISIÓN SIN CONFIRMAR` en el informe. Máximo 4 subagentes a la vez, sin suite completa en los subagentes. Sin revisor de seguridad salvo que el paso 1 encuentre que hay que tocar código de `src/` fuera de los JSON y el i18n.

## Decisiones de Cristian (9-nov)
- PRI-01: programa de **fábrica número 6** (rompe a propósito la regla «los equipos salen con máximo 5 de fábrica»; 1–10 sigue reservado a fábrica y usuario desde 11).
- PRI-02: copia exacta de `instrumental_134.json` (fábrica y usuario) salvo: `cycle_id` `prion`, `cycle_number` 6, `display_name` «Prion 134°C» (`DECISIÓN SIN CONFIRMAR`), `nombre_clave` `ciclos_fabrica.prion.nombre`, `esterilizacion.temperatura_esterilizacion` 134, `esterilizacion.tiempo_esterilizacion` **30 min**, `secado.tiempo_secado` **30 min** (rango actual 0–120, cabe).
- PRI-03: `globals.F0` false (termina solo por tiempo); `globals.tipo_carga` sólido; `finalizacion.apertura_automatica` false; todo lo demás (prevacío, calentamiento, descompresión, finalización, sensores) igual que Instrumental 134 tal como esté en `dev` al empezar.
- PRI-04: nombre en i18n es «Prion 134°C» y en «Prion 134°C».

## Requisito previo
- Parte de `dev`. La tanda 35 debe estar unida a `dev`: si `docs/informes/tanda35/CERRADO.txt` no existe, empieza con `BLOQUEADO:` o la rama `tanda35` no está en `dev`, escribe `docs/informes/ciclo_prion/CERRADO.txt` con `BLOQUEADO: tanda 35 sin unir a dev` y termina.
- Verifica que no haya cambios pendientes en `src/`, `tests/`, `tools/` ni `packaging/` (los de `docs/`, `AJUSTES.md`, `Hadware/`, los `.log` y `habblaud/` de Cristian no cuentan; no los toques). Si los hay, `BLOQUEADO: árbol con cambios pendientes` y termina.
- Crea la rama `ciclo-prion` desde `dev`. Lleva `docs/informes/ciclo_prion/estado.md` al día tras cada commit; al reanudar, sigue desde el primer paso pendiente.

## Pasos
1. Inventario (sin cambiar nada), en `docs/informes/ciclo_prion/inventario.md`:
   - Todo lo que fija la cantidad o la lista de programas de fábrica (código, pruebas, herramientas como `tools/asignar_programas_tuttnauer.py`, migraciones que recorren «los 10 programas», Reportes/calendario, selector, número de programa efectivo DR-H02, límites de `cycle_number`). Señala cualquier validación que rechace un programa de fábrica 6.
   - Cómo llega un programa de fábrica nuevo a un equipo YA instalado al actualizar (carpeta `cycles/factory` en `{app}` frente a `cycles/user` en `datos`): ¿aparece solo, aparece sin copia de usuario, o no aparece? No supongas: verifícalo en el código de carga (`cycle_manager._load_from_folder` y la creación de la copia de usuario) y en el instalador. Si no aparece solo, detente después del paso 3, explícalo en el informe y deja la decisión a Cristian (`BLOQUEADO:` no; solo `DECISIÓN PENDIENTE`).
2. Crea `src/autoclave/cycles/factory/prion.json` y `src/autoclave/cycles/user/prion.json` copiando el archivo, no reescribiéndolo a mano (script de lectura-modificación-escritura que cambie solo las claves de PRI-02/03), y las claves i18n es/en.
3. Verifica que el programa cargue sin errores ni migraciones: `CycleManager` lo carga, `errores_programa`/`errores_coherencia` vacíos (incluidas las reglas vigentes de coherencia de recuperación, límites de presión del equipo y la de la tanda 35), ninguna migración lo reescribe al cargar (sin `.bak` nuevo ni auditoría), y aparece como 6 en `GET /programas` y en el selector.
4. Pruebas: una prueba nueva `tests/test_pri_programa_prion.py` (carga, valores de PRI-02/03, número 6 de fábrica, i18n es/en, coherencia limpia, igualdad con Instrumental 134 en todo lo no listado). Actualiza las pruebas existentes que cuentan o enumeran programas y lista cada una en el informe con el motivo. Corre un ciclo completo de Prion en la planta simulada (`tests/helpers/planta_vapor.py`, modo cámara y modo chaqueta, caudal abierto) y reporta resultado, duración de ESTERILIZACION y de SECADO, y si hubo aislamientos o avisos.

## Cierre
- Suite completa en verde.
- `CLAUDE.md`: sección corta «Programa Prion (9-nov)» con PRI-01..04 y la nota de que ya hay 6 programas de fábrica.
- Riesgo HAZ-PRI-01 en `docs/riesgos/registro_riesgos.md`: el nombre «Prion» sugiere eficacia frente a priones; el software solo garantiza 134 °C sostenidos 30 min con los criterios de ESTERILIZACION vigentes, no valida la inactivación (validación del proceso y rotulado a cargo de Especifika, ISO 17665). Trazabilidad con el siguiente REQ libre. Bloque PRI en `docs/mis_plans/hoja_pruebas_banco_equipo_pruebas.md` (un ciclo Prion completo en el equipo de pruebas: duración de exposición, temperatura mínima y máxima del Principal en ESTERILIZACION, secado, ticket con nombre y número 6).
- Informe `docs/informes/ciclo_prion/R_informe.md`: cambios, inventario resumido, resultado de la planta, pruebas modificadas, `DECISIÓN SIN CONFIRMAR` y `DECISIÓN PENDIENTE`.
- Merge a `dev`. NO compiles: al cerrar, di que no se compiló y da el comando `python tools/entrega/compilar_entrega.py`.
- Último acto: `docs/informes/ciclo_prion/CERRADO.txt` (fecha, commit del merge, resultado de la suite). Bloqueo que necesite a Cristian: igual, con `BLOQUEADO:` en la primera línea.

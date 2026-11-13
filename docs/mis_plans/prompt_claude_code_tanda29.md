# Tanda 29: correcciones del segundo día de pruebas (6-nov-2026)

Responde e informa SOLO en español. Prioridad: velocidad por tarea; cambio mínimo. Máximo 4 subagentes a la vez, sin suite completa en los subagentes; 1 revisor de seguridad solo al final, sobre el diff de T29-02, T29-03, T29-04, T29-05 y T29-08.

## Requisito previo
El hotfix del estado seguro ya está unido a `dev` (merge f9eaa9d8, cierre real en `docs/informes/hotfix_es_merge/CERRADO.txt`; el `docs/informes/hotfix_estado_seguro/CERRADO.txt` con BLOQUEADO es viejo y NO cuenta). Lee las decisiones D1 a D6 de la unión en `CLAUDE.md` y en `docs/informes/hotfix_es_merge/R_informe.md`: la tanda 29 parte de ese estado (sin protocolo automático de estado seguro; A13 solo en CICLO).
1. Verifica que `dev` contiene f9eaa9d8 (`git merge-base --is-ancestor f9eaa9d8 dev`). Si no, BLOQUEADO con el motivo.
2. La carpeta principal está en la rama `hotfix-estado-seguro` y `dev` está tomada por el worktree `C:/Users/tecni/Documents/codigo_autoclave_merge`. Si ese worktree no tiene cambios (`git -C <ruta> status --porcelain` vacío), quítalo con `git worktree remove <ruta>`; si tiene cambios, BLOQUEADO con la lista. Luego, en la carpeta principal, `git checkout dev`. Los archivos sin seguimiento de `docs/`, `AJUSTES.md` modificado y `habblaud/` son de Cristian: no los toques ni los incluyas en commits.
Rama `tanda29` desde `dev`. Lleva `docs/informes/tanda29/estado.md` (paso → Hecho/Pendiente, último commit) al día tras cada commit; al reanudar, sigue desde el primer paso pendiente. Decisiones de Cristian: todas las de este documento (6-nov). Ante ambigüedad, elige lo seguro y márcalo `DECISIÓN SIN CONFIRMAR` en el informe.

## T29-01 (ALTA) Cambio de parámetros que no se aplicó al ciclo
Cristian cambió parámetros de los pulsos B del prevacío (`prevacio.*_pulso_b` / `conteo_pulso_b`) desde Opciones › Parámetros del ciclo, justo antes de iniciar, y el ciclo corrió con los valores anteriores. Asegura que fue el MISMO programa (descartado el error de selección). Por código el camino parece correcto: `PATCH /cycle/parameter` escribe en el objeto de `cycle_manager.cycles`, que es el mismo que `set_active_cycle` entrega a `CicloState._programa`, y `CicloState.reset()` lo copia al entrar a CICLO. Reprodúcelo de punta a punta (UI QML → backend → simulador o dobles), incluyendo: guardar y luego iniciar sin salir de Opciones; guardar con la pantalla de Preciclo abierta; reselección del programa (`/cycle/select`) después de guardar; recarga de programas; `ParametrosCicloController` y el `cycle_id` que envía; `aplica` "siguiente"/"en_curso". Corrige la causa y agrega una prueba de regresión que falle sin la corrección. Si no se reproduce, deja en el informe las hipótesis descartadas y una prueba de integración que cubra el flujo.

## T29-02 (MEDIA) Avisos de preparación durante y después del ciclo
En el ciclo y al finalizar aparecen, en la bandeja de alarmas y avisos y en las observaciones del fin de ciclo, avisos que son condiciones normales del proceso: «Temperatura de drenaje alta» (PRE-06, activada en CICLO por `CicloState._mantener_drenaje`) y otros de cámara con presión o con vacío (Cristian los ve igual que el del drenaje; no son bloqueantes; el código exacto no se conoce).
1. Corre un ciclo completo en el simulador (sólido con prevacío y secado, y líquido modo 4) y lista TODO lo que aparece en la bandeja, la campana y las observaciones (`terminacion.observaciones`, `alarmas_ciclo`) durante el ciclo y hasta 5 min después. Anota el inventario en el informe.
2. Los avisos de condición de preparación (PRE-01 a PRE-06 y cualquier otro del inventario que solo describa una condición normal del proceso) no se activan en CICLO, se resuelven al entrar a CICLO y no entran en `alarmas_ciclo` ni en las observaciones. El control de la válvula del intercambiador del drenaje durante el ciclo se conserva.
3. Fuera de ciclo, PRE-03 y PRE-04 se activan solo si la condición dura `tiempo_estable` seguido (como `generar_alarma_temporizada` de PREPARADO), también en PREPARACION, para que el igualado normal tras un ciclo no genere avisos.
4. No se tocan fallas de fase, alarmas de sensores, D-CHQ ni VCH-AIS.

## T29-03 Presión de fin de descompresión
Hoy DESCOMPRESION (modos 1 y 2, y la despresurización final de 3, 4 y 5) termina con `pres <= atm + rango_presion_atm`. El vapor residual sostiene la presión apenas por encima y la fase espera a que se condense. Nuevo parámetro de programa `descompresion.presion_fin_descompresion` (kPa sobre la atmosférica, clase «diferencia», defecto 10, rango 2–20): la fase termina con `pres <= atm + presion_fin_descompresion`, en los modos 1 a 5, sólidos y líquidos (decisión de Cristian). El modo 0 no cambia. El timeout de cada modo no cambia. Migración al cargar que agrega el defecto si falta (auditoría, SIS-06, `.bak`, como en A12). NO ABRIR, el bloqueo de inicio y el venteo de PREPARACION/PREPARADO (líquido por la lenta) siguen rigiendo después. Riesgo nuevo en el registro (líquidos con hasta +20 kPa al salir de la fase).

## T29-04 Temperatura de apertura: rige la del programa
Hoy rige el menor entre `temp_max_apertura` del equipo (80) y `finalizacion.temp_max_apertura` del programa (100 en instrumentales), así que la del programa no tiene efecto. Nuevo criterio: rige la del programa; la del equipo se usa solo cuando no hay programa del que tomarla. Aplica a `camara_segura`, NO ABRIR, bloqueo de inicio, apertura automática, `temp_max_tras_ciclo`, `/status.camara_segura_limites`, `detalle_aviso.py` y textos. Revisa los textos que hoy dicen «el menor entre el del equipo y el del programa» y el rótulo del parámetro del equipo (que diga que es el valor sin programa).

## T29-05 Sólidos no pueden usar descompresión 4 o 5
Bowie & Dick de usuario tiene `descompresion.modo = 4` (enfriamiento de líquidos) siendo sólido; el de fábrica tiene 1. Regla: con `tipo_carga` sólido solo se permiten modos 0 a 3 (rechazo al guardar, código y texto propios es/en). Migración al cargar: programa sólido con modo 4 o 5 → el modo del programa de fábrica si es sólido y válido, si no 1; con auditoría, SIS-06 y `.bak`. Los arrastres de `tipo_carga` (D8-5.7) no cambian.

## T29-06 Parámetros del ciclo abre en el programa seleccionado
`ParametrosCicloController._al_cargar` elige `programas[0]` (Bowie & Dick). Debe abrir en el programa seleccionado en Preciclo (`/cycle` o el número del programa activo); si no hay, el primero. El nombre del programa debe verse en todas las vistas del flujo (programa, sección, sensores, entradas).

## T29-07 F0 en el ticket
Con F0 activo, la cabecera del ticket (`ticket_formatter.format_header`) imprime «F0 activo · objetivo {F0_objetivo} min»; al final ya imprime «F0 total» (`format_footer`): verifica que salga en el ticket en vivo y en la reimpresión. Lo mismo en el PDF y el correo. Sin F0 activo, nada cambia. Claves i18n es/en.

## T29-08 Aire atmosférico abierto fuera de ciclo
Fuera de CICLO (PREPARACION, PREPARADO y FALLA), con todas las puertas instaladas confirmadas cerradas (DI vigentes; sin dato = no cerrada), `aire_admosferico_camara` queda abierta. Se cierra en el mismo tick si `pres_camara > atm + rango_presion_atm` o sin lectura de presión, y el venteo actual de sobrepresión sigue igual (líquido por la lenta). Con alguna puerta abierta, comportamiento actual. No aplica en modo prueba (manual) ni en el apagado/ALL_OFF. Respeta el `ConfirmadorApagado` donde ya se use. Riesgo en el registro y prueba de banco nueva (bloque T29).

## Cierre
- Pruebas por cada T29-xx; suite completa en verde; actualiza `CLAUDE.md` (secciones afectadas), riesgos (`docs/riesgos/registro_riesgos.md`), trazabilidad REQ, hoja de banco (bloque T29) e informe `docs/informes/tanda29/R29_informe.md`.
- Merge a `dev`. NO compiles la entrega: al cerrar, di explícitamente que no se compiló y da el comando `python tools/entrega/compilar_entrega.py`.
- Último acto: `docs/informes/tanda29/CERRADO.txt` (fecha, commit del merge, suite). Si te bloquea algo que necesite a Cristian, escríbelo igual con `BLOQUEADO:` en la primera línea.

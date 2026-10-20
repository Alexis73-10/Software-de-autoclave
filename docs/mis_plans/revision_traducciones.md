# Registro de revisión de traducciones (es → en)

Software de Autoclave — Especifika S.A.S.
Catálogo: `src/autoclave/i18n/en.json` (borrador de F1, 14/10/2026), traducido desde `src/autoclave/i18n/es.json`.
Procedimiento: `planeacion_i18n.md` §6 (borrador → revisión técnica → revisión lingüística → registro → compuerta de liberación).

**Estado global: borrador sin revisar.** Ninguna cadena de alarma o de seguridad puede pasar a producción sin la revisión registrada aquí (§6.5, criterio de aceptación 7). El inglés tampoco se habilita en campo hasta cerrar la voz (R-06).

Conteo: textos hoja del catálogo (cada elemento de `fecha.meses` y cada campo de `sensores[]` cuenta como uno). Total: 408.

## Por grupo

| Grupo | Nº de claves | Estado | Revisor técnico | Revisor lingüístico | Fecha | Observaciones |
|---|---:|---|---|---|---|---|
| Alarmas y seguridad (transversal, ver lista abajo) | 20 | Borrador sin revisar — **requiere revisión explícita** | | | | Ver términos dudosos T-01 a T-04. Las alarmas del dominio (`Alarm.description`, motivos de puerta, `motivo_fallo`) aún no están en el catálogo: entran en F2 |
| Ciclo y fases (`ciclo`, `fases`, `estados`, `unidades`, `sensores`, `arranque`) | 66 | Borrador sin revisar | | | | Términos de ISO 17665. Ver T-05 a T-08 |
| Opciones (`opciones`) | 16 | Borrador sin revisar | | | | |
| Reportes y correo (`exportacion`, `reportes`) | 67 | Borrador sin revisar | | | | Ver T-09 y T-10 |
| Menú (`menu`, `modulos`, `notificaciones`) | 63 | Borrador sin revisar | | | | Ver T-11 |
| Resto (`instalacion`, `app`, `fecha`, `acciones`, `teclado`, `prueba_teclado`, `equipo`, `formulario`, `sistema`, `sesion`, `usuarios`, `validacion`) | 196 | Borrador sin revisar | | | | `prueba_teclado` es de pantallas de prueba. Ver T-12 a T-14 |

## Claves de alarma y seguridad (requieren revisión explícita)

Las 20 que el inventario F0 marca como `alarma-seguridad` (`inventario_cadenas_i18n.csv`):

| Clave | Español | Borrador en inglés |
|---|---|---|
| `menu.sin_conexion` | Sin conexión con el equipo | No connection with the equipment |
| `menu.resultado_fallo` | Fallo | Failed |
| `ciclo.cancelar` | CANCELAR CICLO | CANCEL CYCLE |
| `ciclo.cancelar_pregunta` | El ciclo en curso se cancelará. ¿Desea continuar? | The cycle in progress will be cancelled. Do you want to continue? |
| `ciclo.cancelar_error` | No se pudo cancelar el ciclo. Verifique la conexión… | The cycle could not be cancelled. Check the connection… |
| `ciclo.confirmar` | CONFIRMAR | CONFIRM |
| `ciclo.confirmar_error` | No se pudo confirmar el fin del ciclo… | The end of the cycle could not be confirmed… |
| `ciclo.aviso_titulo` | AVISO | NOTICE |
| `ciclo.alarmas_titulo` | ALARMAS Y AVISOS | ALARMS AND NOTICES |
| `ciclo.sin_alarmas` | Sin alarmas ni avisos activos | No active alarms or notices |
| `ciclo.abrir_puerta` | ABRIR PUERTA | OPEN DOOR |
| `ciclo.cerrar_puerta` | CERRAR PUERTA | CLOSE DOOR |
| `estados.fallo` | Fallo | Failed |
| `acciones.reconocer` | Reconocer | Acknowledge |
| `notificaciones.titulo` | NOTIFICACIONES | NOTIFICATIONS |
| `notificaciones.alertas_avisos` | Alertas y avisos | Alerts and notices |
| `sistema.sin_conexion` | Sin conexión con el controlador. Los valores mostrados no están actualizados. | No connection with the controller. The values shown are not up to date. |
| `sistema.modo_prueba` | MODO PRUEBA ACTIVO — los ciclos no son válidos para carga estéril | TEST MODE ACTIVE — cycles are not valid for sterile loads |
| `sesion.sin_conexion_escrituras` | Sin conexión con el equipo: no se pueden guardar cambios | No connection with the equipment: changes cannot be saved |
| `sesion.sin_conexion_cierre` | La sesión se cerrará en {tiempo} si no vuelve la conexión | The session will close in {tiempo} if the connection is not restored |

Propuesta para que el revisor decida si se agregan a esta lista (no están marcadas en F0): `modulos.reconocer_falla` (RECONOCER FALLA → ACKNOWLEDGE FAULT), `arranque.fallo_titulo`, `arranque.fallo_bloqueante`, `arranque.sin_progreso`, `ciclo.temp_camara`, `ciclo.presion`.

## Términos dudosos

| # | Clave(s) | Español | Borrador | Duda |
|---|---|---|---|---|
| T-01 | `ciclo.alarmas_titulo`, `ciclo.sin_alarmas`, `ciclo.aviso_titulo`, `notificaciones.alertas_avisos` | Avisos | Notices | IEC 60601-1-8 distingue *alarm signal* e *information signal*; "advisory"/"notice" no son términos de la norma. Decidir un término único para "aviso" |
| T-02 | `acciones.reconocer`, `modulos.reconocer_falla` | Reconocer (falla) | Acknowledge (fault) | IEC 60601-1-8 usa *acknowledged* para la alarma; confirmar "fault" frente a "failure"/"alarm" |
| T-03 | `estados.fallo`, `menu.resultado_fallo`, `reportes.fallos`, `reportes.col_fallos` | Fallo | Failed | Como resultado de ciclo; en ISO 17665 sería un ciclo *not successful* / *failed*. Confirmar término del registro |
| T-04 | `sistema.modo_prueba` | carga estéril | sterile loads | Confirmar redacción con el responsable técnico (es un aviso de seguridad) |
| T-05 | `fases.descompresion` | Descompresión | Exhaust | EN 285 / ISO 17665 suelen usar *exhaust* o *depressurization*; elegir uno |
| T-06 | `fases.vacio`, `instalacion.cap_vacio` | Vacío | Vacuum | La fase es el prevacío (pulsos); quizá *Pre-vacuum* / *Air removal* |
| T-07 | `ciclo.temp_ester`, `ciclo.tiempo_est`, `ciclo.tiempo_sec` y `sensores[1..2].etiqueta` | Temp. Ester. / Tiempo Est. / Tiempo Sec. | Ster. Temp. / Ster. Time / Dry. Time | Abreviaturas; verificar que caben en el diseño y que se entienden |
| T-08 | `fases.esterilizacion` | Esterilización | Sterilization | ISO 17665 habla de *holding time* / *plateau period*; se dejó el nombre de fase |
| T-09 | `exportacion.consigna_temp`, `exportacion.consigna_pres` | Consigna | Setpoint | Confirmar |
| T-10 | `exportacion.ticket` | Registro del ciclo | Cycle record | Confirmar frente a *cycle printout* |
| T-11 | `menu.realizados`, `equipo.ciclos_realizados` | Realizados | Performed | Se evitó "Completed" porque choca con `resultado_completado`: "realizados" incluye ciclos con fallo. Confirmar *Performed* frente a *Run* |
| T-12 | `instalacion.clase_mesa_*`, `instalacion.clase_piso*` | Mesa / Piso | Tabletop / Floor-standing | Confirmar nombres comerciales en inglés |
| T-13 | `instalacion.cap_chaqueta`, `equipo.*` | Chaqueta | Jacket | Término habitual (*jacketed chamber*); confirmar |
| T-14 | `instalacion.puerta_locking`, `instalacion.puerta_motorized_locking` | Con bloqueo | With lock | Confirmar frente a *interlocked* |

## Altas posteriores a F1 (sin revisar)

Cada fila es una traducción nueva al inglés agregada después del borrador de F1. Estado: **sin revisar**.

| Fecha | Etapa | Clave(s) | Grupo | Estado |
|---|---|---|---|---|
| 2026-10-14 | Tanda E-0 | `arranque.verificando_instalacion`, `arranque.liberando_procesos`, `arranque.cargando_configuracion`, `arranque.verificando_calibracion`, `arranque.conectando_modulos_es`, `arranque.preparando_interfaz` | Ciclo y fases (arranque) | sin revisar |
| 2026-10-14 | Tanda E-0 | `alarmas.<ID>.titulo` y `alarmas.<ID>.accion` para los 9 ids de la tarjeta de E/S (`TARJETA_SIN_TRAMA_VALIDA`, `TARJETA_VERSION_INCOMPATIBLE`, `TARJETA_SIN_ACK`, `TARJETA_ALL_OFF_SIN_CONFIRMAR`, `TARJETA_SALIDAS_NO_APAGADAS`, `TARJETA_EXPANSOR_FUERA_DE_LINEA`, `TARJETA_WATCHDOG`, `TARJETA_REINICIO`, `DISCREPANCIA_SALIDAS`) | Alarmas y seguridad — **requiere revisión explícita** | sin revisar |

| 2026-10-14 | Tanda T3 | `sensores_ciclo.*` (nombres de ubicación Cámara 1/2 y Referencia, roles y estados de los sensores) y `validacion.ASIGNACION_INVALIDA`, `validacion.SENSOR_NO_DISPONIBLE`, `validacion.ASIGNACION_SENSORES_INVALIDA` | Ciclo y fases | sin revisar |
| 2026-10-15 | Tanda T7 | `sistema.no_abrir`, `sistema.paro_no_abrir`, `sistema.paro_liberado`, `sistema.confirmar_estado_seguro`, `sistema.estado_seguro_en_curso`, `equipo.apagar`, `equipo.apagar_pregunta`, `equipo.apagar_rechazado` | Alarmas y seguridad — **requiere revisión explícita** | sin revisar |
| 2026-10-16 | Tanda T12 | `opciones.secciones_programa.*`, `opciones.no_se_ejecuta`, `opciones.programa_no_editable`, `opciones.sensores_*`, `opciones.sensor_sin_senal`, `opciones.leyenda_defecto`, `opciones.actual`, `opciones.por_defecto`, `opciones.minimo`, `opciones.maximo`, `opciones.ultima_modificacion`, `opciones.sin_cambios`, `opciones.toque_nuevo_valor`, `opciones.rango_permitido`, `opciones.si`, `opciones.no`, `opciones.valor_solido`, `opciones.valor_liquido`, `opciones.err_*` | Opciones (los `opciones.err_*` de bloqueo y valor: **requieren revisión explícita**) | sin revisar |
| 2026-10-16 | Tanda T9 | `instalacion.resumen_cerrojo`, `instalacion.resumen_con_cerrojo`, `instalacion.resumen_sin_cerrojo`, `instalacion.resumen_empaque`, `instalacion.resumen_con_empaque`, `instalacion.resumen_sin_empaque`, `instalacion.confirmar_sin_cerrojo` | Alarmas y seguridad — **requiere revisión explícita** | sin revisar |
| 2026-10-16 | Tanda T8 | `ciclo.sin_bd_pregunta`, `ciclo.sin_bd_continuar`, `sesion.sin_bd`, `sesion.continuar_sin_operador` | Alarmas y seguridad — **requiere revisión explícita** | sin revisar |
| 2026-10-19 | Tanda 2 U1 | `sistema.estado_seguro_pendiente`, `sistema.paro_suelte`, `sistema.confirmar_sin_sesion`, `sistema.estado_seguro_en_curso_boton`, `sistema.no_abrir_hasta_segura`, `sistema.seguridad_desconocida` | Alarmas y seguridad — **requiere revisión explícita** | sin revisar |
| 2026-10-19 | Tanda 2 S1 | `instalacion.vapor_generator_desc` (texto cambiado) | Instalación | sin revisar |
| 2026-10-20 | Tanda 3 A1 | `equipo.apagar_camara_no_segura` | Alarmas y seguridad — **requiere revisión explícita** | sin revisar |
| 2026-10-20 | Tanda 3 S4 | `sistema.estado_seguro_detenido_accion`, `sistema.asignar_sonda_principal` | Alarmas y seguridad — **requiere revisión explícita** | sin revisar |
| 2026-10-20 | Tanda 3 M1 | `menu.vencido`, `menu.proximo_vencimiento`, `equipo.ciclos_restantes`, `opciones.mant_*` | Mantenimiento | sin revisar |

## Registro de revisiones

| Clave o grupo | Revisor | Rol (técnico / lingüístico) | Fecha | Resultado | Observaciones |
|---|---|---|---|---|---|
| | | | | | |

# Tanda 30: informe (6-nov-2026)

Rama `tanda30` desde `dev` (ec78c939). Entrega NO compilada.

## Resultado por paso
| Paso | Resultado |
|---|---|
| T30-01 | Operador obligatorio: backend falla cerrada (409 `operador_requerido`, 422 `operador_invalido`, 503 `operador_no_verificable`), modal `ModalOperador.qml` en las dos puertas, nombre en ciclos, ticket, PDF, correo, historial, Reportes y bitácora. 
| T30-02 | Progreso de la fase activa en lugar del tiempo restante (`detalle_fase` en `/cycle/current/progress`, texto en `ciclo_en_curso.py`). |
| T30-03 | Eliminar (borrado lógico, columna `eliminado`, migración v13), cambiar rol, «Cambiar mi contraseña» para todos los roles, con confirmación modal. |

Pruebas nuevas: `test_t30_01_operador_inicio.py`, `test_t30_02_progreso_fase.py`, `test_t30_03_usuarios.py` (110 en total con los ajustes). Ajustadas: `test_u11_cuentas_sistema` (el rol ya se cambia), `test_o1_operador_ciclo`, `test_db_audit_log`, `test_i4_ingles_backend`, `test_automatizacion_ciclos_bd`, `test_s2b_d8_2_14_avisos_ticket_bd`, `test_b1_secado_pyside` (el barrido ignora la cadena de consulta). Suite completa (4878 s): 11426 pasadas, 7 fallos en la primera corrida; 4 eran intermitentes y pasan al repetirlas (`test_nuevo_usuario_puente`, `test_p1_salida_modo_prueba` ×2, `test_t26_arq_revision`); 2 eran míos (identificadores QML con «tarjeta», renombrados a `panelModalOperador` y `panelRol`) y 1 ya fallaba en `dev` sin cambios (`test_t26_ald_detalle_alarmas::test_qml_tocar_no_abrir...`: la salida del subproceso llega vacía, problema del entorno). Ver `CERRADO.txt`.

## Revisión de seguridad (T30-01, T30-03)
Sin ALTA ni MEDIA. Sin escalada de privilegios; las reglas del último ingeniero, autoeliminación, autocambio de rol y cuentas del sistema se aplican bajo el candado de la base. Cuatro BAJA, sin corregir, `DECISIÓN SIN CONFIRMAR`:
- **B1:** sin sesión, `ciclo_iniciado` guarda el nombre del operador en el campo `usuario`; un operador llamado «Admin» se vería como la cuenta Admin en el filtro. Opción: `usuario=""` y operador solo en `detalle`.
- **B2:** la fila `ciclo_iniciado` se escribe al fijar la orden de inicio; si el lazo la descarta, queda una fila sin ciclo.
- **B3:** carrera de microsegundos entre el login y eliminar/cambiar rol (token con rol anterior); ya existía para desactivar. Opción: candado común.
- **B4:** el respaldo (`usuarios.json`) exporta a los eliminados como `activo: false`, sin marca `eliminado`.

## DECISIÓN SIN CONFIRMAR
Las cuatro anteriores; además, sin operadores activos el ciclo sigue iniciando sin operador (como pidió Cristian), y el operador de la lista no se autentica.

## No se compiló
Para compilar: `python tools/entrega/compilar_entrega.py` desde `dev` limpio.

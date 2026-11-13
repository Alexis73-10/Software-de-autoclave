# Tanda 30: operador, progreso por fase y usuarios (6-nov-2026)

Responde e informa SOLO en español. Prioridad: velocidad por tarea; cambio mínimo. Máximo 4 subagentes a la vez, sin suite completa en los subagentes; 1 revisor de seguridad al final sobre el diff de T30-01 y T30-03. Decisiones de Cristian: todas las de este documento (6-nov). Ante ambigüedad, lo seguro y `DECISIÓN SIN CONFIRMAR` en el informe.

## Requisito previo: espera a la tanda 29
La tanda 29 puede estar corriendo en ESTA MISMA carpeta. Mientras esperas NO escribas, cambies de rama ni hagas ninguna operación de git o de archivos en el repositorio; solo lee.
1. Revisa si existe `docs/informes/tanda29/CERRADO.txt` (los `CERRADO_intento*_bloqueado.txt` NO cuentan).
2. Si no existe, espera 5 minutos con un comando de espera del shell (`Start-Sleep -Seconds 300` o `sleep 300`; sin subagentes ni otras herramientas mientras esperas) y vuelve al paso 1. Tope: 14 horas.
3. Si existe y empieza con `BLOQUEADO:`, o se cumple el tope: crea `docs/informes/tanda30/CERRADO.txt` con `BLOQUEADO: tanda 29 no cerrada` (o su motivo) y termina.
4. Si existe sin bloqueo: espera 2 minutos, verifica que la rama actual sea `dev`, que el merge de la tanda 29 esté en `dev` y que no haya cambios pendientes en `src/`, `tests/`, `tools/` ni `packaging/` (los archivos de `docs/`, `AJUSTES.md` y `habblaud/` de Cristian no cuentan; no los toques). Si algo no cuadra, espera 5 minutos y repite (máximo 6 veces; luego BLOQUEADO).
Rama `tanda30` desde `dev`. Lleva `docs/informes/tanda30/estado.md` al día tras cada commit; al reanudar, sigue desde el primer paso pendiente.

## T30-01 Operador obligatorio al iniciar el ciclo
Hoy `/cycle/start` guarda como operador al usuario de la sesión (`estado.operador_inicio`) o lo deja vacío. La tabla `operadores` existe y se gestiona en Opciones › Usuarios.
- Con sesión iniciada: el operador es el usuario de la sesión, sin preguntar (como hoy).
- Sin sesión y con operadores activos: al deslizar INICIAR (`DeslizadorInicio` de `PantallaPreciclo.qml`, las dos puertas) se abre un modal (`ModalConfirmacion` o equivalente, táctil, lista con desplazamiento, sin elide) con los operadores activos. Elegir uno es obligatorio; Cancelar no inicia el ciclo.
- Sin sesión y sin operadores activos: no se pregunta (como hoy).
- El backend lo exige también (falla cerrada): `/cycle/start` acepta `operador_id`; sin token válido y con operadores activos, sin `operador_id` o con uno inactivo o inexistente → 409/422 con código propio y texto es/en; no inicia.
- El nombre del operador queda en `ciclos.operador`, el ticket, el PDF, el correo, el historial y Reportes (como hoy con el usuario de la sesión), y en la fila de bitácora del inicio.

## T30-02 Progreso por fase en lugar del tiempo restante
En la pantalla de ciclo en curso se quita el tiempo restante (queda el transcurrido). En su lugar, un texto de progreso de la fase activa, en las unidades del equipo (`unidades_qml`), publicado por `GET /cycle/current/progress` (dato crudo en el backend; el texto lo arma `ui_qml/domain/ciclo_en_curso.py`; QML solo dibuja):
- Precalentamiento: «250 / 328 kPa» (chaqueta actual / consigna).
- Prevacío: «3/8 Bajo» o «3/8 Alto»: pulso en curso / total de pulsos (suma de A, B, C y D del programa); DECOMPRESION y VACIO_BAJO/HOLD_BAJO = Bajo; VAPOR_ALTO/HOLD_ALTO = Alto.
- Calentamiento: «128 / 134 °C» (Principal / objetivo); en la ventana de estabilización: «Estabilizando 0:45 / 1:00».
- Esterilización: «2:10 / 5:00 min» (exposición transcurrida / total, `exposicion_total_s`); con F0 activo, además «F0 4,2 / 12 min».
- Descompresión: «180 / 85 kPa» (presión actual / presión de fin; con T29-03, atm + `presion_fin_descompresion`); modos 4/5 en enfriamiento: temperatura actual / `temperatura_enfriamiento`.
- Secado: «4:00 / 15:00 min» (o el dato equivalente del modo).
- Sin dato: «—». Textos i18n es/en, sin abreviar ni recortar (D8-5.4).
El llenado de los círculos de fase (LLF) no cambia. Retira el cálculo del tiempo restante solo si nada más lo usa.

## T30-03 Usuarios: eliminar, cambiar rol y cambiar la propia contraseña
Reemplaza en parte U11 (tanda 11): el rol sí se cambia; nombre y usuario siguen sin editarse.
- Eliminar: el usuario desaparece de la lista sin borrarse de la base (columna `eliminado`, migración de esquema); no reversible desde la UI; el nombre de usuario no se reutiliza; cierra sus sesiones; bitácora. Mismas reglas que desactivar: nadie se elimina a sí mismo, las cuentas del sistema (Admin, Ingeniero) no, y el equipo no queda sin un ingeniero activo. `DELETE /usuarios/{u}` deja de dar `usuario_no_se_borra` y hace esto.
- Cambiar rol: `PATCH /usuarios/{u}` con `rol` (nombre y usuario siguen con 409). Reglas actuales: admin gestiona admin y técnico, ingeniero gestiona todos (`ROLES_CREABLES`, rol actual Y rol nuevo dentro de lo gestionable); nadie cambia su propio rol; cuentas del sistema no; el equipo no queda sin un ingeniero activo. Cierra las sesiones del usuario; bitácora con rol anterior y nuevo.
- Cambiar mi contraseña: entrada en Opciones › Usuarios visible para todos los roles, que abre `CambioClave.qml` en modo voluntario (con Atrás) usando `/auth/change_password` (ya existe).
- UI en `OpcionesUsuarios.qml` / `UsuariosController` con confirmación modal para eliminar y para cambiar rol; códigos y textos es/en para cada rechazo.

## Cierre
- Pruebas por cada T30-xx (backend, controlador y QML); suite completa en verde; `CLAUDE.md`, riesgos (`docs/riesgos/registro_riesgos.md`), trazabilidad REQ, banco (bloque T30) e informe `docs/informes/tanda30/R30_informe.md`.
- Merge a `dev`. NO compiles: al cerrar, di que no se compiló y da el comando `python tools/entrega/compilar_entrega.py`.
- Último acto: `docs/informes/tanda30/CERRADO.txt` (fecha, commit del merge, suite). Bloqueo que necesite a Cristian: igual, con `BLOQUEADO:` en la primera línea.

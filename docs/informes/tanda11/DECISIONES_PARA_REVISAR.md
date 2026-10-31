# Tanda 11 — DECISIONES SIN CONFIRMAR y PREGUNTAS PARA CRISTIAN

Resumen. El detalle y el porqué de cada punto están en el informe de cada etapa (`docs/informes/tanda11/<ID>_*.md`). Para cambiar una decisión basta con decir el número.

## DECISIONES SIN CONFIRMAR

### R11 — Reinicio del software al cambiar la impresora (D11-1)
- **R11-1:** el reinicio va dentro del mismo `PUT /printer/config` (campo `reiniciar`). Si no se puede reiniciar, no se guarda nada. `reiniciar_software` sigue siendo una función reutilizable, pero sin endpoint propio.
- **R11-2:** si el backend no lo arrancó `Autoclave.exe` (desarrollo), responde 503 y no guarda nada.
- **R11-3:** el cambio de impresora desde el menú de ajustes PySide también se rechaza ahora en CICLO.
- **R11-4:** las pantallas se cierran con `terminate()`, y con `kill()` si no cierran en 5 s.
- **R11-5:** la instancia nueva espera 60 s como máximo a la anterior. Si se agota la espera, usa el backend que responda y nunca arranca un segundo.
- **R11-6 (revisión de seguridad SAF-01):** el reinicio también se rechaza con el estado seguro actuando o pausado, con una confirmación pendiente tras un paro, y en modo prueba. FALLA solo se permite cuando el estado seguro ya terminó.

### E11 — Retiro de `aire_comprimido_chaqueta` (D11-2)
- **E11-1:** DO 13 queda como puerto **libre**, reasignable como DO 25-32, no bloqueado. Si se prefiere «reservado», hay que agregar una regla en `asignacion_io.validar`.
- **E11-2:** la advertencia por un YAML o un `asignacion_io.json` antiguo que traiga la salida sale en cada arranque, hasta que se reescriba el archivo.

### S11 — SEN-03 según los sensores en uso (D11-3)
- **S11-1:** «la unión de los programas de las dos pantallas» se toma como la lista `programas_seguridad()`. El backend tiene una sola selección de programa: la vigente, más el programa del último ciclo mientras la cámara no sea segura y las copias del estado seguro. Así se vigila de más, nunca de menos.
- **S11-2:** si no se puede obtener la lista, se vigilan los tres sensores, como antes.
- **S11-3:** con un programa de roles inválidos se vigila todo sensor que esa asignación marque como Principal o Referencia.

### U11 — Cuentas Admin e Ingeniero (D11-6)
- **U11-1:** `DELETE` y `PATCH /usuarios/{u}` existen solo para rechazar: 409 auditado para las 2 cuentas del sistema, 409 genérico para las demás. Nunca modifican nada.
- **U11-2:** una semilla que esté inactiva en una BD antigua sigue inactiva tras migrar.
- **U11-3:** si hay choque de nombres, la semilla se marca aunque no se renombre.
- **U11-4:** si la búsqueda es ambigua y no hay coincidencia exacta, nadie inicia sesión.
- **U11-5:** las semillas de BD anteriores a la columna `creado_por` no se migran ni se marcan.
- **U11-6:** la fila `usuario_renombrado` va con `usuario="sistema"`.
- **U11-7 (revisión de seguridad):** los nombres de usuario nuevos solo admiten letras latinas (con tildes y ñ), dígitos y `._-`. Se comparan normalizados con NFKC + casefold. `sistema` y `semilla` quedan reservados. Los usuarios existentes con otros caracteres siguen pudiendo entrar.
- **U11-8 (revisión):** `PRAGMA recursive_triggers=ON` en la conexión de la BD. Si el rol de una semilla no es el esperado, no se toca.

### N11 — Instalador: Instalación limpia y táctiles (D11-4, D11-5)
- **N11-1:** la limpia **no borra `estacion\`** (la necesita el desinstalador para revertir Windows), pero sí la respalda.
- **N11-2:** la limpia no ejecuta el desinstalador: aparta los datos y sigue con el asistente completo.
- **N11-3:** `Autoclave_respaldos\` queda solo para Administradores y SYSTEM.
- **N11-4/5:** el paso 06 no se repite al Reparar ni en un Setup silencioso.
- **N11-6:** «2 o más monitores» se evalúa al ejecutar el Setup.
- **N11-7:** las asociaciones se cuentan por el número de valores de la clave Digimon. Pueden contar entradas viejas.
- **N11-8:** el aviso de «menos de 2 asociaciones» sale como `MsgBox` al final.
- **N11-9:** la herramienta de Windows tiene 10 min como máximo.
- **N11-10:** el respaldo se verifica por número de archivos y bytes. Los respaldos no se borran solos.
- **N11-11 (revisión):** el borrado ya no va entrada por entrada. La carpeta de datos entera se aparta con un solo renombrado a `Autoclave_respaldos\<fecha>_borrar` y después se borra. Si quedan restos, solo se anota en el log.
- **N11-12 (revisión):** si `DisplayVersion` es desconocida y no hay `VersionNum`, el Setup se niega a instalar.

### O11 — Entradas mostradas (D11-7)
- **O11-1:** «en uso» = `sensores_en_uso`. Con una asignación inválida, solo cuenta el Principal de respaldo.
- **O11-2:** mientras no llega `/cycle`, se muestran Cámara 1 y la presión de cámara.
- **O11-3:** la primera Referencia es la primera en el orden del catálogo.
- **O11-4:** la omisión se filtra por las entradas habilitadas en el equipo.
- **O11-5:** la auditoría del cambio de rol no deshace el cambio si la bitácora falla, igual que ya hacía ese endpoint.
- **O11-6:** los botones Guardar de las vistas de entradas y de roles de sensor tenían ancho 0 y no se veían. Se les puso ancho.
- **O11-7:** si se elige «Ninguna» en la fila 2 y hay algo en la 3, se guarda compactado.

### Sesión principal
- **A0/K11:** la compilación de esta tanda se llama **G** (`inst-2026-10-23-g`, `1.0.0-g`, `AppVerNum` 1.0.0.7), la letra siguiente a la F.
- **Revisores de seguridad:** además del exigido para U11, se pasó un `safety-reviewer` a R11 (toca el apagado y ALL_OFF) y a N11 (la limpia borra datos). Ninguno encontró bloqueantes. Sus hallazgos se corrigieron en cada rama antes de unir; los que quedan pendientes se listan en el índice.
- **Rojo de integración de O11:** `test_o2e_bitacora::test_textos_de_todos_los_eventos`. Se arregló en `tanda-11` agregando el evento `entradas_mostradas` a `bitacora.EVENTOS`, con texto en es y en.

## PREGUNTAS PARA CRISTIAN
1. **S11:** ¿la unión de programas para SEN-03 debe incluir el del último ciclo mientras la cámara no sea segura (así quedó)?
2. **U11:** si al migrar otro usuario choca con `Admin` o `Ingeniero` sin distinguir mayúsculas, ¿se renombra al otro usuario o se deja así?
3. **U11:** con `Ingeniero` no desactivable, la regla del «último ingeniero activo» casi nunca actúa. ¿Se mantiene?
4. **U11:** una fila semilla con un rol distinto del esperado no se migra ni se protege. ¿Qué se hace en ese caso?
5. **U11 (revisor):** si `Ingeniero` pierde su contraseña y no hay otro ingeniero, ¿cómo se recupera el acceso? (No es nuevo.)
6. **N11-P1:** ¿la limpia debe además revertir la estación?
7. **N11-P2:** ¿cuántos respaldos de limpia se guardan? Hoy se acumulan sin límite.
8. **N11-P3:** ¿la limpia debe borrar el «recordar usuario» del menú de ajustes (`HKCU\Software\Especifika\Autoclave`)?
9. **N11-P4:** ¿`MultiDigitizer.exe` funciona con Windows 11 Pro y estos paneles? Se comprueba en el caso A-N11-04.
10. **O11:** ¿la omisión [Principal, primera Referencia, presión de cámara] queda así?
11. **O11:** hay otros botones sin ancho en la misma pantalla que probablemente no se ven: «Cerrar» del aviso de cambio automático y psig/inHg de la ventana de ajuste. ¿Se corrigen en otra etapa?

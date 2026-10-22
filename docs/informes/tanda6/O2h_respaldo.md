# O2h — Respaldo y restauración ★

## Qué se hizo

### Backend
- **`core/runtime/respaldo.py`** (nuevo). Cada respaldo es un ZIP guardado en `<USB>/Especifika_respaldos/` con un manifiesto (`manifiesto.json`):
  - formato, versión del software, número de serie y modelo, fecha y usuario, y partes incluidas;
  - SHA-256 de cada archivo, más el `hash` del propio manifiesto.
- **Contenido del ZIP:**
  - `perfil.json`: identificación del equipo;
  - `calibracion.yaml`: leída bajo `_lock_archivos`;
  - `parametros.json`: parámetros del equipo vigentes;
  - `programas/*.json`: programas de `cycles/user`;
  - `usuarios.json`: usuario, nombre, rol y activo, **sin hashes ni contraseñas**;
  - `historial.db`: opcional, copia de la base con la API de backup de SQLite.
- **Validación al restaurar:**
  - hash del manifiesto y hash de cada archivo;
  - topes al número de entradas y al tamaño total;
  - formato y versión mayor del software;
  - **número de serie igual al del equipo**.
  - Un respaldo de **otro equipo se rechaza siempre** (409 `otra_serie`, con registro en la bitácora). Un archivo alterado, faltante o ilegible responde 422.
  - Antes de escribir nada se valida todo. La calibración pasa por `load_config` y además por la **misma plausibilidad que la calibración manual** (`evaluar_desviacion_acumulada` canal por canal). Un rechazo o un aviso rechazan el respaldo completo: falla cerrada.
- **Endpoints** (sección "O2h" de `server.py`): técnico e ingeniero (admin y operador reciben 403, sin token 401). Exportar y restaurar están bloqueados con ciclo en curso: 409, también para el ingeniero.
  - `GET /backup/usb`: unidades extraíbles (psutil) y respaldos de cada una, con Válido o Rechazado y el motivo.
  - `POST /backup/export`: escribe primero un `.tmp` y luego hace un `replace` atómico. Registro `respaldo_exportado`.
  - `POST /backup/restore`:
    - exige `confirmar: true` (si falta, responde 428 y no aplica nada);
    - el nombre de archivo se valida contra recorridos de ruta y la unidad debe estar detectada;
    - comprueba de nuevo que no haya ciclo justo antes de escribir la calibración;
    - recarga la calibración sin reiniciar (`units.reload_calibration`, igual que la calibración manual);
    - los parámetros se aplican como en O2a: base fuera del lock y memoria dentro del guard;
    - **siempre** registra `respaldo_restaurado`, también si falla a medias, con lo aplicado y lo omitido.
- **Qué restaura** (DECISIÓN SIN CONFIRMAR): la calibración y los parámetros del equipo.
- **Qué NO restaura:**
  - los programas: un programa restaurado entraría sin pasar por el validador del editor (rangos del catálogo, reglas entre parámetros, F0). Se exportan solo como referencia hasta tener un validador común;
  - el perfil: se reinstala;
  - los usuarios y el historial: por trazabilidad;
  - la presión atmosférica de referencia: solo la escribe O2f.

### UI (mockup 12)
- Nueva sección **Respaldo** en OPCIONES (`permisos_opciones`: técnico e ingeniero).
- **`OpcionesRespaldo.qml`:**
  - estado de la USB con "Actualizar";
  - casillas para elegir qué exportar y "Exportar a USB";
  - lista de respaldos con su chip (Válido o Rechazado, con el motivo y la serie);
  - "Restaurar seleccionado" con diálogo de confirmación. Un respaldo rechazado no se puede seleccionar.
- Textos en español e inglés: sección `respaldo` y `opciones.secciones.respaldo`.

## Pruebas
`tests/test_o2h_respaldo.py` (26):
- creación y lectura;
- otra serie y otra versión;
- integridad: hash alterado, archivo faltante, manifiesto alterado, sin manifiesto, ZIP ilegible;
- recorrido de ruta y programas inválidos;
- matriz por rol y 401;
- exportar y restaurar de ida y vuelta (sin hashes de contraseña; parámetros y calibración restaurados; programas no restaurados);
- 428 sin confirmación;
- otra serie, archivo alterado y calibración no plausible: no se aplica nada;
- 409 en ciclo;
- USB no detectada;
- pantalla QML.

## Capturas (1200×1920, offscreen)
- `O2h_1_respaldo.png`
- `O2h_2_confirmar.png`
- `O2h_3_restaurado.png`

## Revisión del agente safety-reviewer
- **SAF-01 (Alto):** la calibración se validaba sin plausibilidad. **Corregido**: misma evaluación que la calibración manual y falla cerrada. Que el hash no autentique queda documentado y va como PREGUNTA.
- **SAF-02 (Alto):** los programas se restauraban sin validar. **Corregido**: los programas no se restauran.
- **SAF-03 (Medio):** se comprobaba "sin ciclo" una sola vez y la restauración parcial no quedaba en la bitácora. **Corregido** con una segunda comprobación antes de escribir y auditoría en `finally`. Queda abierto: no se deshacen los parámetros ya aplicados si uno posterior recibe 409.
- **SAF-04 (Medio):** la calibración nueva quedaba en disco sin tomar efecto hasta reiniciar. **Corregido**: se recarga sin reiniciar.
- **SAF-05 (Bajo):** la calibración se leía sin lock al exportar. **Corregido**.
- **SAF-06 (Bajo):** no había topes para ZIP grandes. **Corregido**: tope de entradas, de tamaño total y de manifiesto.

## USB de recuperación del perfil (arranque)
No se conectó. El arranque necesita el perfil para saber qué equipo es, pero este respaldo **no** restaura el perfil: se exige que la serie coincida con la del perfil ya instalado.
- Para encajarlo haría falta un modo "sin perfil" en el asistente de instalación que:
  - lea `perfil.json` y el manifiesto desde la USB;
  - pida confirmación de la serie impresa en la placa del equipo.

Queda documentado; no se implementó.

## PREGUNTA PARA CRISTIAN
1. ¿Se firma el respaldo (HMAC con una clave del equipo)? Hoy el hash detecta daños, pero quien conozca el formato puede rehacer un respaldo con la serie correcta. La plausibilidad de la calibración limita el daño.
2. ¿Se habilita la restauración de programas reutilizando el validador de `PATCH /cycle/parameter`?
3. ¿Los usuarios del respaldo deben poder recrearse, con contraseña temporal y cambio obligatorio?
4. ¿Restaurar debe incluir también la presión atmosférica de referencia del mismo equipo?

## Riesgo (para `docs/riesgos/`)
- **HAZ-RES-01:** restaurar una calibración ajena o manipulada produce lecturas erróneas, y con ellas un interlock o umbrales falsos.
  - Control: serie obligatoria, hashes, plausibilidad por canal, confirmación, solo fuera de ciclo y registro en la bitácora.
  - Verificación: `test_restaurar_otra_serie_se_rechaza`, `test_calibracion_implausible_se_rechaza` y `test_restaurar_alterado_no_aplica_nada`.

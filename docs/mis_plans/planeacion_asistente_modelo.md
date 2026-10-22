# Planeación — Asistente de instalación: cálculo del modelo comercial

Software de Autoclave — Especifika S.A.S.
Versión 1 — 2026-10-21. Estado: **aprobado por Cristian (21-oct, 22:30)**.

## 0. Alcance
Incluye:
- el asistente de instalación pide los datos del equipo y **calcula** el nombre comercial con la nomenclatura oficial de Especifika;
- se retiran del asistente los equipos de mesa.

Fuera de alcance:
- la línea SPK-ION (peróxido), que este software no controla;
- usar la capacidad para ajustar parámetros, por ejemplo tiempos de vacío según el volumen;
- borrar el código de los equipos de mesa (se hará en otra tanda).

## 1. Decisiones de Cristian
| ID | Decisión |
|---|---|
| AM-1 | Nomenclatura oficial de la línea de vapor: `SPK-SAT <capacidad><carga><puertas>`. `SPK` es la marca y `SAT` la familia (vapor saturado). La capacidad es la nominal de la cámara en litros. La carga es `V` (vertical) o `H` (horizontal). El número de puertas va solo cuando es 2. Ejemplos oficiales: `SPK-SAT 45V` y `SPK-SAT 45V2`. |
| AM-2 | Los equipos de laboratorio de piso llevan el sufijo `-LAB` al final, por ejemplo `SPK-SAT 45V2-LAB` o `SPK-SAT 45V-LAB`. Es una licencia creativa autorizada por la empresa. |
| AM-3 | El software se instala solo en equipos de piso (`piso`) y de laboratorio de piso (`piso_lab`). Los de mesa (`mesa_n`, `mesa_b`, `mesa_b_lab`) quedan fuera del alcance: el asistente no los ofrece y no se puede instalar un perfil nuevo de mesa. El código de mesa NO se borra en esta tanda. |
| AM-4 | El técnico escribe la capacidad en litros: entero de 20 a 2000. |
| AM-5 | El modelo es solo un rótulo informativo (ticket, PDF, correo, Información del sistema y Configuración de la máquina). No cambia ningún parámetro. |
| AM-6 | El nombre SIEMPRE lo calcula el software: no hay campo de texto libre ni "modelo especial". Queda bloqueado con el perfil y solo cambia reinstalando el perfil. |
| AM-7 | El ejecutable que se entrega NO lleva un perfil preinstalado: el equipo se instala en sitio con el asistente. |

## 2. Regla de cálculo
```
calcular_modelo(clase, capacidad_litros, tipo_carga, door_count) -> str
  clase ∈ {piso, piso_lab}; cualquier otra → ValueError("clase fuera de alcance")
  capacidad_litros: int, 20 ≤ c ≤ 2000; si no → ValueError (bool y float no enteros se rechazan)
  tipo_carga ∈ {"V", "H"}; si no → ValueError
  door_count ∈ {1, 2}; si no → ValueError
  nombre = f"SPK-SAT {capacidad}{tipo_carga}" + ("2" if door_count == 2 else "") + ("-LAB" if clase == piso_lab else "")
```
| Clase | Litros | Carga | Puertas | Resultado |
|---|---|---|---|---|
| piso | 45 | V | 1 | `SPK-SAT 45V` |
| piso | 45 | V | 2 | `SPK-SAT 45V2` |
| piso_lab | 45 | V | 2 | `SPK-SAT 45V2-LAB` |
| piso_lab | 180 | H | 1 | `SPK-SAT 180H-LAB` |
| piso | 2000 | H | 2 | `SPK-SAT 2000H2` (el más largo con piso, 14 caracteres) |
| piso_lab | 2000 | H | 2 | `SPK-SAT 2000H2-LAB` (el más largo, 18 caracteres) |

La función va en un módulo puro nuevo, `installation/modelo.py`, sin Qt. La usan el puente, la validación y las pruebas.

## 3. Perfil de instalación
- Campos nuevos en `installation_profile.json`: `capacidad_litros` (int) y `tipo_carga` (`"V"`|`"H"`). Se agregan en `InstallationProfile`, `validate_profile_data` y `storage`.
- `model_id` se conserva como clave (compatibilidad) y guarda el nombre calculado.
- Validación de un perfil nuevo con los dos campos: `model_id` debe ser igual a `calcular_modelo(...)`. Si no coincide, el perfil es inválido, lo que protege contra una edición a mano.
- Perfiles anteriores sin `capacidad_litros`/`tipo_carga` siguen siendo válidos y se muestran con su `model_id` tal cual. Donde se muestre la capacidad aparece "—". No se migran ni se reescriben.
- AM-3 en el código: `puente_instalacion.instalar()` y la validación de instalación nueva rechazan las clases de mesa con un error claro, con texto en i18n. Cargar un perfil existente de mesa NO se rechaza: en campo no existe ninguno, y así una carga no tumba el arranque. Queda registrado como DECISIÓN SIN CONFIRMAR.
- `puente.clases` entrega solo `piso` y `piso_lab`.
- Si existe una herramienta `tools/declarar_*.py` que cambie `model_id`, `door_count` o `equipment_class`, debe recalcular el nombre o rechazar el cambio. Revísalo y documéntalo.

## 4. Cambios en el asistente (`Instalacion.qml` y puente)
1. **Paso "Tipo de equipo":** solo dos tarjetas, Piso y Piso laboratorio. Empiezan sin selección (INS-01).
2. **Paso nuevo "Cámara", después de "Puertas":**
   - capacidad nominal en litros, con teclado numérico, entero de 20 a 2000 y error bajo el campo;
   - tipo de carga, con un selector de segmentos Vertical (V) / Horizontal (H), sin selección inicial y obligatorio;
   - vista previa del nombre calculado en tipografía destacada. Se actualiza en vivo y muestra "—" mientras falte un dato.
3. **Paso "Datos":** se elimina el campo de texto libre "Modelo".
4. **Resumen:** el nombre del modelo va arriba y en grande, seguido de la capacidad y el tipo de carga, antes de la confirmación (INS-03).
5. **Indicador de pasos:** se renumera.
6. **Textos:** todo texto nuevo va en `instalacion.*`, en es y en (por ejemplo, Vertical/Horizontal y "Capacidad nominal (L)"). El nombre del modelo NO se traduce.
7. **Puente:** recibe `capacidad_litros` y `tipo_carga`, revalida todo en Python y calcula `model_id` él mismo, sin confiar en el que manda la QML.

## 5. Donde se muestra
Ticket (cp437, verificar el ancho con 18 caracteres), PDF, correo, Información del sistema (O2d) y Configuración de la máquina (O2a, solo lectura). Agrega la capacidad y el tipo de carga en Información del sistema. No se toca otra cosa: todos esos lugares ya leen `model_id`.

## 6. Pruebas mínimas
- Tabla de §2 completa. Rechazos: mesa, 19, 2001, 45.5, "45", `True`, carga "v" (minúscula) y "X", y puertas 0 o 3.
- El puente calcula el nombre e ignora un `model_id` enviado por la QML.
- El perfil con `model_id` inconsistente es inválido. Un perfil anterior sin los campos nuevos es válido.
- `puente.clases` no contiene clases de mesa. Instalar mesa → error.
- QML offscreen: el paso Cámara bloquea "Siguiente" sin datos válidos, la vista previa cambia en vivo y el resumen muestra el nombre.
- Ticket con `SPK-SAT 2000H2-LAB` sin cortes.

## 7. Riesgo (registro de riesgos)
HAZ-INS-02: una capacidad mal digitada deja un rótulo de modelo erróneo en documentos de trazabilidad (ticket, PDF). Severidad baja, porque es informativo y no controla el proceso. Controles: rango 20–2000, vista previa, resumen con confirmación y nombre calculado (sin texto libre).

**Hay compilación H y se recomienda instalarla en el equipo de pruebas antes del lunes 26-oct.** La USB va armada desde `entrega/2026-10-24_h/usb/`, con `Autoclave_Setup_1.0.0-h.exe`. Hay que seguir la sección 8g del LEEME (G → H), dejando marcada «Actualizar (conserva los datos)», y después el bloque T12 de la hoja de banco. Antes del primer ciclo, anote `brecha_segura_temperatura` de los programas de usuario: queda en 0,3.

# Tanda 12: índice (24-oct-2026)

La rama `tanda-12` salió de `dev` en 8bda767 y se unió a `dev` con `--no-ff` y la suite en verde (d660c06). La etiqueta es `inst-2026-10-24-h`. El estado detallado está en `docs/informes/tanda12/estado.md`.

## Resumen por etapa
| Etapa | Qué | Informe |
|---|---|---|
| A0 | Se comprobó la precondición (tanda 11 cerrada y en `dev`). Se creó la rama y se agregó `t_saturacion_c` a `steam.py` con prueba de ida y vuelta. Línea base: 7218 passed | `tanda12/estado.md` |
| J12 | C-04, C-05 (incluido C-05.9), valores JSON de C-07.1 y C-13.4, y migración correctiva con auditoría y SIS-06 | `tanda12/J12_parametros_chaqueta.md` |
| P12 | C-01, C-02, C-09 y C-13.7b en la ventana de CALENTAMIENTO | `tanda12/P12_calentamiento.md` |
| E12 | C-03, C-07.2, C-08, C-10 y C-13 (incluidos 7, 7b y 8) en ESTERILIZACION y CicloState | `tanda12/E12_esterilizacion.md` |
| L12 | C-11 y C-12 como especificación (`docs/mis_plans/planeacion_liquidos_dos_lazos.md`) y bloque T12 de la hoja de banco | `tanda12/L12_liquidos_banco.md` |
| V12 | Revisión de seguridad ★. No hubo bloqueantes; se corrigieron 5 hallazgos con prueba | `tanda12/V12_revision_seguridad.md` |
| K12 | Compilación H con su Setup, prueba de humo, ensayo G → H, SHA-256 y `usb/` | `tanda12/K12_compilacion_h.md` |
| Z | `CLAUDE.md`, suite en verde, unión a `dev`, push y este índice | este índice |

**Suite final** (151599e, con todo unido): **7531 passed, 10 skipped, 3 xfailed**. Con `-n auto` pasan 7522; los otros 9 son de impresión y de calibración QML, fallan solo en paralelo y pasan en serie. También hubo suite tras cada unión, todas en verde: J12 7400, P12 7423, E12 7511.

## Resumen por C-xx
- **C-01 (CALENTAMIENTO):** `presion_add_calentamiento` pasa a ser solo techo. El objetivo de presión es Psat(T_obj). La fase entra a sostener con `P ≥ Psat − 2 kPa` y el techo queda en `Psat + presion_add` (antes era 2×).
- **C-02:** con sólidos, la ventana exige coherencia `|Tsat(P) − T| ≤ 1 K`. Fuera de coherencia, la ventana se reinicia y se arma el timeout de recuperación.
- **C-03:** con sólidos, en ESTERILIZACION se agregan dos FALLO, cada uno tras 5 s:
  - `Tsat(P) − T > +2 K` → CIC-12, aire o gases no condensables;
  - `Tsat(P) − T < −2 K` → CIC-13, vapor sobrecalentado o falla de la sonda.
- **C-04:** el Bowie & Dick de usuario pasa de 99 a 9 y `presion_add_*` queda con máximo 30. Se rechaza un programa cuyo techo llegue a 385 kPa o más; entre 350 y 385 solo hay advertencia. Un programa instalado con `presion_add_*` mayor que 30 se migra a 9, con auditoría, aviso SIS-06 y `.bak`.
- **C-05:** durante el CICLO, la chaqueta sigue una consigna calculada del programa, con banda de ±10 kPa. Nuevos `delta_temp_chaqueta` y `margen_flujo_chaqueta`. Se rechaza un programa con consigna + 10 ≥ 385 o con `presion_chaqueta + rango` ≥ 385.
- **C-06:** no se implementa. Queda registrado como PRG-01.
- **C-07:** `brecha_segura_temperatura` pasa a 1,0 en los 8 JSON. Las fallas de ESTERILIZACION exigen 5 s continuos en vez de 3 lecturas. **Los programas de usuario ya instalados en el equipo conservan 0,3** (DECISIÓN SIN CONFIRMAR).
- **C-08:** la salida de RECUPERACION tiene histéresis (+0,3 K y +1 kPa). En RECUPERACION también rige el techo, con 2 kPa de histéresis (DECISIÓN SIN CONFIRMAR).
- **C-09:** el corte por calidad de vapor empieza en `T_obj − 3 K`.
- **C-10:** sin medición no se cuenta exposición. CicloState falla antes; la fase corre el fin de la exposición y corta el vapor.
- **C-11 y C-12:** solo especificación de líquidos, con 11 preguntas abiertas.
- **C-13:** si una Referencia queda fuera de banda más de 5 s, el conteo se detiene; al volver, se reinicia desde cero. Sin retorno en 5 min → CIC-14. Las excursiones van al ticket y el tiempo restante de la UI refleja el reinicio. Una Referencia sin lectura no detiene el ciclo: activa SEN-11, marca el ciclo NO CONFORME y deja sin apertura automática.

## DECISIONES SIN CONFIRMAR y PREGUNTAS PARA CRISTIAN
El detalle está en `docs/informes/tanda12/DECISIONES_PARA_REVISAR.md`. Las urgentes para el lunes:
1. **Techo frente a la histéresis de C-08 a 134 °C.** Con brecha 1,0, la fase no sale de RECUPERACION porque Tsat del techo es 135,0 °C y la salida exige 135,3 °C. La histéresis de 2 kPa en el techo es una DSC. ¿Se acepta, o se sube `presion_add_esterilizacion` o se ajusta la salida?
2. **Brecha 0,3 en los programas de usuario del equipo.** No se migró. ¿Se migra a 1,0?
3. **Referencia unas décimas más fría que el Principal en CALENTAMIENTO:** el ciclo puede terminar en FALLO `cal_no_sostuvo`. ¿Se da una tolerancia a las Referencias?
4. **NO CONFORME no aparece en la pantalla final** (V12 SAF-02). ¿Se agrega un resultado visible, un reconocimiento del operador o «CARGA NO ESTÉRIL» en el ticket?
5. Sin F0, las excursiones repetidas pueden reiniciar la exposición sin fin. ¿Se pone un tope?
6. ¿Se acepta el debounce de «5 s continuos» frente a una señal que oscila en el umbral?

Las demás DSC de J12, P12, E12 y L12, y las 11 preguntas de líquidos, están en ese documento.

## Pendientes registrados
- **PRG-01:** al cargar un programa, validar que cada rol (Principal o Referencia) corresponda a una sonda cableada en el perfil de instalación. Si no, rechazar el programa o pasar el rol a «No en uso» con aviso. No se implementó.
- **DEU-01:** los límites de presión (fondo de escala 400, suministro 350, alivios 385) están como constantes en `catalogo_parametros.py`. Deberían venir del perfil de instalación o de Parámetros del equipo, porque el suministro absoluto depende de la atmósfera del sitio. No se implementó.

## Lo que quedó sin hacer
- C-11 y C-12 (control de líquidos en dos lazos y eliminación de aire): solo hay especificación, sin código.
- Hallazgos menores de V12 sin corregir: SAF-02 (pregunta), SAF-04 (pregunta), SAF-05 y SAF-09.
- La hoja de banco `pruebas.py` y el `.html` siguen sin regenerarse desde el `.md` (deuda heredada).
- `entrega/drivers/` sigue vacía.

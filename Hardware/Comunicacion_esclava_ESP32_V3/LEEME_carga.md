# Carga del firmware 1.0.0 (Comunicacion_esclava_ESP32_V3)

Procedimiento de `docs/mis_plans/planeacion_firmware_1_5.md` §8. Lo hace Cristian. El firmware V2
(`Hardware/Comunicacion_esclava_ESP32_V2/`) queda en el repositorio como retorno.

## Requisitos

- Arduino IDE con el mismo paquete de placas ESP32 que compiló V2. En el PC de desarrollo está
  instalado **esp32 3.3.7** (`Arduino15/packages/esp32/hardware/esp32/3.3.7`). Si se usa otra versión,
  anótela en el informe de la prueba.
- Librería **PCF8575 de Rob Tillaart, versión 0.2.5** (ya instalada en `Documents/Arduino/libraries/PCF8575`).
  No usar otra librería PCF8575 (hay una `EasyPCF8575` instalada que no sirve aquí).
- La carpeta y el `.ino` se llaman igual: `Comunicacion_esclava_ESP32_V3/Comunicacion_esclava_ESP32_V3.ino`.

## Pasos

1. Respaldo: el `.ino` V2 ya está en el repositorio. No hace falta extraer el binario de la tarjeta.
2. Abrir `Comunicacion_esclava_ESP32_V3.ino` en Arduino IDE, elegir la placa y el puerto, y compilar.
3. Cargar por USB con el equipo **sin carga eléctrica en las salidas** y el **paro presionado**.
4. Abrir el monitor serie a **115200**, fin de línea "Nueva línea" (NL). Al reiniciar debe aparecer:

   ```
   BOOT 1.0.0 2 <ID>*HHHH
   ```

   - versión `1.0.0`, protocolo `2`, `<ID>` = 12 dígitos hexadecimales (MAC de fábrica del chip).
   - Después llegan cada 500 ms las tramas `AI:`, `DI:`, `DO:` y `ST:`, todas con `*HHHH` al final.
   - La `ST:` termina en `,0` (NO_SINCRONIZADO) hasta que el PC envíe `ALL_OFF`.
5. Registrar el ID en el perfil del equipo, con el software cerrado:

   ```
   python tools/emparejar_tarjeta.py --id <ID>
   python tools/emparejar_tarjeta.py --mostrar
   ```

6. Hacer las pruebas 2 a 9 de §6 de la spec (lista en `docs/informes/informe_e6_firmware.md`) antes de
   conectar el autoclave.

## Comandos a mano desde el monitor serie

El firmware rechaza toda línea sin CRC válido. Para probar a mano hay que escribir la línea con su CRC
(CRC-16/CCITT-FALSE en hexadecimal mayúscula). Valores ya calculados:

| Comando | Línea a enviar |
|---|---|
| `HB` | `HB*F1EC` |
| `VER` | `VER*A87C` |
| `ALL_OFF` | `ALL_OFF*70D2` |
| `SET DO4 ON` | `SET DO4 ON*F896` |
| `SET DO4 OFF` | `SET DO4 OFF*59BC` |
| `RESET_MINMAX` | `RESET_MINMAX*9584` |

Ojo: tras `ALL_OFF` el watchdog queda armado; si no se envía otra línea válida en 5 s, la tarjeta
responde `WD: ALL_OFF` y vuelve a NO_SINCRONIZADO (comportamiento esperado, FW-D5).

Para obtener el CRC de cualquier comando:

```
python -c "from autoclave.protocols.crc16 import agregar_crc; print(agregar_crc('SET DO4 ON'))"
```

(desde la raíz del repositorio con `src` en `PYTHONPATH`, o con el entorno del proyecto instalado).

## Volver a V2

Cargar `Hardware/Comunicacion_esclava_ESP32_V2/Comunicacion_esclava_ESP32_V2/Comunicacion_esclava_ESP32_V2.ino`.
Ojo: con V2 el software actual del PC **no funciona** (rechaza las tramas sin CRC y muestra
`TARJETA_VERSION_INCOMPATIBLE`). V2 solo sirve como retorno junto con un software anterior.

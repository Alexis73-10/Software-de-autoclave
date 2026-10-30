# Adenda a la tanda 19: datos reales del banco (27-oct, 12:15)

Se escribe mientras la tanda 19 corre (P en curso). No la modifica: se aplica en la revisión posterior a la tanda o en una sesión corta de corrección.

Origen: página web del módulo principal (192.168.3.7), «设备基本信息» y «从机IO信息».

## Datos leídos

- Principal: modelo `M31-XAXX0A00G-U`, firmware `9232-0-13`, MAC `00-54-04-84-9D-B1`, SN `S6203074S`, dirección Modbus 1.
- Lista de esclavos (ID, modelo, firmware, E/S):
  - 0 · `GXAXX0A00-U` · 9286-0-10 · 16AI de una sola terminal (corriente). **Son las E/S del propio principal, que figura como esclavo 0.**
  - 1 · `GAXXXA000-U` · 9233-0-12 · 16DI (NPN/PNP)
  - 2 · `GXXAX00A0-U` · 9233-0-12 · 16DO (relé tipo A)
  - 3 · `GXXAX00A0-U` · 9233-0-12 · 16DO (relé tipo A)
  - 4 · `GXDXX0600-U` · 9304-0-10 · 6PT100

## Correcciones a la planeación (MOD-06)

- **ADB-01 · Composición esperada:** la lista de esclavos (0x0C80) incluye las E/S del principal como esclavo 0. La composición esperada pasa a ser `["GXAXX0A00", "GAXXXA000", "GXXAX00A0", "GXXAX00A0", "GXDXX0600"]`, es decir, 5 esclavos con IDs 0 a 4. Si `ModbusLink` toma la lista desde `modbus_link.json`, basta con corregir el valor. Si la toma del código, se corrige el código. Una prueba fija el caso real con estos 5 esclavos.
- **ADB-02 · Compatibilidad de firmware:** los números de firmware tienen la forma `<producto>-<x>-<versión>`, y el prefijo de producto es distinto en cada tipo de módulo (9232, 9286, 9233, 9304). La comprobación nunca compara el número completo ni el prefijo: solo la parte de versión (el último número, o el byte bajo del registro 0x0C1F/0x0D80 si el registro da la versión).
  - Con el banco real: principal 13 contra esclavos 10, 12, 12, 12 y 10, compatible, que coincide con la tabla del manual (§6: 9232-0-13 es compatible con 9206-0-10, 9233-0-11/12, 9286-0-10 y 9304-0-10).
  - Si con el registro no se puede separar bien la versión, se usa el texto completo de firmware (0x0C2C para el principal) y se anota.
- **ADB-03 · ID del equipo:** la MAC del principal da el ID `005404849DB1`, que es el `board_id` que se registrará en el perfil (emparejamiento FW-D7).
- Pruebas: una con la lista real de 5 esclavos y sus firmwares, que debe conectar. Otra con un esclavo distinto o ausente, que debe dar `TARJETA_VERSION_INCOMPATIBLE`.

## Prueba de corte por desconexión (banco, 27-oct, 12:20–12:30)

Configuración escrita por Modbus: 0x0C35 = 10, 0x0C36 = 1, 0x1B58–0x1B77 = 1. Se leyó de vuelta igual y **persiste tras reiniciar** el módulo.

Resultados:
- **Antes de reiniciar el módulo**, con la configuración recién escrita, DO1 encendida y el cable de red desconectado: DO1 **no** se apagó.
- **Después de reiniciar:**
  - DO1 se mantiene encendida mientras hay tráfico de lectura cada 0,1 s (10 s).
  - Al cesar el tráfico, con la conexión TCP abierta, DO1 se apaga en ~1 s: el LED se apaga y la bobina leída pasa a False.
- El registro 0x0C37 leyó 100 y, 5 s después, 105. **No se comporta como la bandera 0/1 que describe el manual**: parece un contador.

Correcciones a la planeación:
- **ADB-04 · La configuración de falla puede requerir un reinicio para activarse** (DECISIÓN SIN CONFIRMAR: lo sugiere el banco, sin una prueba aislada todavía). En MOD-07, si al conectar algún registro de seguridad difería y hubo que escribirlo:
  1. reiniciar el módulo (0x0C1D = 0x5BB5);
  2. esperar a que vuelva;
  3. reconectar y volver a leer toda la configuración;
  4. solo entonces dar la conexión por verificada.

  Si tras el reinicio la configuración no coincide, `TARJETA_CONFIG_SEGURIDAD`. Una conexión cuyos registros ya coincidían no reinicia el módulo. Prueba de banco M-5: restablecer fábrica con Reload y comprobar que el software reconfigura, reinicia y que después el corte funciona.
- **ADB-05 · 0x0C37 no se usa como bandera de falla.** Se registra su valor crudo en el diagnóstico y en el log, y no dispara `TARJETA_WATCHDOG` hasta averiguar su significado (consulta a Ebyte). La detección de un corte se hace así: la bobina leída en False con la orden en True, después de una interrupción del tráfico, la cubre la lógica de discrepancia (MOD-11) y la reconexión (MOD-08).
- **MOD-08 queda validado en lo esencial:** cualquier lectura mantiene vivo el módulo y cortar todo el tráfico apaga las salidas en ~1 s.

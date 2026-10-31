Tanda 20 UNIDA a `dev` (merge d8c3ffa) y ENTREGADA como 1.0.0-alpha.4 (a6795c1, etiqueta `v1.0.0-alpha.4`; sin push).

# Índice — tanda 20 (27-oct-2026): cierre de la migración a Modbus TCP (M31-U) y Setup con Modbus

- Informe único: `docs/informes/tanda20/R20_informe.md`
- Estado: `docs/informes/tanda20/estado.md`; línea base: `docs/informes/tanda20/base_suite.txt`; cierre: `docs/informes/tanda20/CERRADO.txt`
- Copia previa al retiro del serial: `G:\Respaldos_autoclave\pre_tanda20_20261027_1448\` (SHA-256 en el informe §3), etiqueta local `respaldo-serial-pre-t20`
- Anomalías de la entrega: `docs/versiones/anomalias_conocidas_1.0.0-alpha.4.md` (MED-01..04, AN-33..AN-35; AN-30/31/32 cerradas)
- Hoja de banco: bloque M en `docs/mis_plans/hoja_pruebas_banco_equipo_pruebas.md` (M-0..M-5, M-5b, M-7)
- Riesgos: `docs/riesgos/registro_riesgos.md` (MED-04, MED-03 actualizado, tanda 20); SOUP: pyserial retirado en `docs/riesgos/lista_soup.md`
- Entrega: `entrega/v1.0.0-alpha.4_2026-10-27/` (Setup `Autoclave_Setup_1.0.0-alpha.4.exe`)

## Para Cristian, primero

1. Publicar: `git push origin dev v1.0.0-alpha.4` (no se hizo push).
2. Banco antes de usar la alpha.4 con los módulos: M-7 (Setup con Modbus: red, contraseña web, prueba de conexión, reversión), M-5b (¿hace falta reiniciar el módulo para activar la configuración de falla?) y M-2 (formato real de 0x0C1F/0x0D80/0x0C2C).
3. Decidir: DECISIONES SIN CONFIRMAR (informe §8, AN-33), `_TOLERANCIA_DI_VENCIDA_SEG` con Modbus (AN-34), MED-04 (red de los módulos sin autenticación) y el residual del reinicio de ADB-04 (MED-03).

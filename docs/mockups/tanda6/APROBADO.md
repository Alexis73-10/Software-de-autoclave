# Mockups de la tanda 6 — APROBADOS (Cristian, 20-oct-2026, 22:54)

Cristian aprobó los 13 mockups publicados como artefacto ("Mockups de la tanda 6"). Code no puede abrir ese enlace, así que aquí está el contenido que debes implementar. Usa el estilo actual de la UI QML (Tema/Colores.qml, Montserrat, `TarjetaContenido`, `BarraInferiorMenu` flotante). Los valores numéricos de los mockups son de ejemplo.

## Cambios respecto a los mockups
- **Fecha y hora (pantalla 7): SOLO LECTURA** con la hora del PC. Sin campos de edición ni botón Aplicar. Muestra hora grande, fecha, zona horaria y aviso si el reloj es anterior a la instalación.
- **Permisos (decisión 1.9 de la instrucción).** El técnico NO cambia idioma ni unidades, NO edita destinatarios de correo y NO crea ni modifica usuarios ni operadores: ve esos controles deshabilitados, con el motivo.
  - Idioma: admin e ingeniero.
  - Unidades: solo ingeniero.
  - Destinatarios: admin e ingeniero.
  - Usuarios y operadores: admin e ingeniero.

## Pantallas
1. **Preciclo (B1, O3).** Barra flotante de 3 secciones fuera de la tarjeta, con las mismas funciones de hoy: Menú a la izquierda, versión al centro e Iniciar sesión a la derecha (en el lugar de Inicio). En la tarjeta:
   - Programa (número grande, nombre, "toque para cambiar") y Estado.
   - 3 parámetros del ciclo y las 3 entradas mostradas del programa, en la unidad vigente ("—" si no hay lectura).
   - Puerta, bandeja de alarmas y avisos, y el botón INICIAR CICLO.
2. **Ciclo en curso (B1, O3).** Misma barra flotante. Fase y tiempo con barra de progreso, las 3 entradas mostradas, y la gráfica con esas 3 series, leyenda y unidad vigente. Cancelar ciclo como hoy.
3. **Parámetros del equipo (O2a).** 7 tarjetas de submenú: Puerta, Impresión, Drenaje, Empaque, Chaqueta y Sistema en rejilla de 2 columnas; Configuración de la máquina a lo ancho. Texto guía: cambios solo sin ciclo en curso y sin reiniciar. El admin ve todo en solo lectura (aviso, sin abrir la ventana de ajuste).
4. **Submenú (ejemplo Puerta).** Lista de filas: nombre, rango y defecto en gris, valor actual a la derecha con su unidad y ">". Al tocar una fila se abre la ventana de ajuste de Parámetros del ciclo. Las diferencias (brecha ±) se convierten sin desplazamiento. Sistema muestra la presión atmosférica de referencia en solo lectura, con fecha y usuario de la última calibración.
5. **Configuración de la máquina.** Controles segmentados, cada uno con confirmación y auditoría:
   - Idioma: Español / English.
   - Temperatura: °C / °F.
   - Presión: kPa / bar / mbar / psi, con la nota "absolutas; psi manométrico y vacío en inHg".

   Aviso "con ciclo en curso las unidades no se pueden cambiar". Número de serie y Modelo en solo lectura ("se cambian reinstalando el perfil").
6. **Usuarios (O2b).** Pestañas Usuarios / Operadores.
   - Usuarios: lista con nombre, rol, último ingreso y chip Activo/Desactivado. Para el seleccionado: "Restablecer contraseña" y "Desactivar" (o Reactivar), y botón "+ Nuevo usuario".
   - Operadores: lista con agregar y desactivar.
   - Nota visible: no se borran usuarios; nadie se desactiva a sí mismo ni deja el equipo sin un ingeniero activo.
7. **Fecha y hora (O2c).** Solo lectura (ver Cambios).
8. **Información del sistema (O2d).** Solo lectura, en grupos de clave–valor:
   - Equipo: modelo, serie, fecha de instalación, fuente de vapor.
   - Software y tarjeta: versión del software, firmware e ID de tarjeta.
   - Uso y mantenimiento: ciclos realizados, próximo mantenimiento (fecha o ciclos restantes).
   - Configuración vigente: idioma, unidades, chip de impresora y chip de red.
9. **Bitácora (O2e).** Filtros Desde, Usuario y Tipo. Filas con fecha y hora a la izquierda y una frase con el usuario en negrita (texto por código en el idioma vigente y valores en la unidad vigente). Paginación "‹ Anterior · Página n de m · Siguiente ›". Solo lectura.
10. **Calibración atmosférica (O2f).** Lista de condiciones con ✓ (puerta abierta, cámara bajo 80 °C, sin ciclo). Barra de progreso con tiempo (mm:ss de 02:00) y número de muestras. Promedio, dispersión y valor anterior con fecha. Recuadro con los criterios de aceptación y aviso de cancelación si se pierde una condición. Solo el botón Cancelar activo, y Atrás/Inicio deshabilitados durante la medición. En Mantenimiento se agregan "Página de prueba de impresora" e "Imprimir ganancias y compensaciones".
11. **Conectividad (O2g).** Red en solo lectura (Wi-Fi y señal, IP, Ethernet) con la nota "para cambiar la red se requiere soporte". Correo: interruptor de envío, lista de destinatarios con quitar, "+ Agregar destinatario" y "Enviar correo de prueba". La contraseña del servidor nunca se muestra. El técnico lo ve en solo lectura.
12. **Respaldo (O2h).** Estado de la USB detectada. Casillas de qué exportar (perfil y calibración, parámetros y programas, usuarios sin contraseñas legibles, historial opcional) y botón "Exportar a USB". Lista de respaldos en la USB con chip Válido o Rechazado (otro número de serie) y "Restaurar seleccionado" con confirmación.
13. **Reingreso PySide (C1a).** Diálogo modal sobre la vista: título "La sesión caducó", texto "Ingrese de nuevo para guardar; lo editado no se pierde". Usuario fijo (el mismo), campo de contraseña y teclado en pantalla:
   - números arriba, QWERTY con ñ, mayúsculas, retroceso, 123, espacio, punto y Listo;
   - botones Cancelar e "Ingresar y guardar".

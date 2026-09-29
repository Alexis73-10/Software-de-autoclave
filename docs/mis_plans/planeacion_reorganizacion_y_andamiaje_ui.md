# Reorganización de assets de UI y escritura del andamiaje QML

**Contexto para quien ejecute esto (Claude Code):** este repositorio es el software de control
de un autoclave industrial (Especifika S.A.S.), clasificación IEC 62304 Clase C. La disciplina del
proyecto es "spec antes de código" — este documento es el spec completo de la tarea: reorganizar
los archivos que entregó el diseñador de UI y dejar escrito el andamiaje base de QML (tema,
componentes y dos pantallas: Arranque y Login). Ejecutar los pasos en orden; detenerse y reportar
si alguna verificación no calza, no improvisar una ruta que no esté descrita aquí.

**Origen de los archivos:** `C:\Users\tecni\Documents\codigo_autoclave\src\autoclave\MOCUP ESPECIFIKA 2.0.zip`

Esa ruta es un error de ubicación en sí misma: un `.zip` de material de diseño (PDF, PNG, CSV,
SVG) no debe vivir dentro de `src\autoclave\`, que es el árbol de código fuente Python. El primer
objetivo es sacarlo de ahí.

**Decisiones ya tomadas, no reabrir en esta tarea:**

- Ubicación del trabajo QML: `src\autoclave\ui_qml\`, espejando la convención de `ui_pyside\`.
- Tipografía: Montserrat (el diseñador envió el archivo real; "Inter" en `tokens.css` es un valor de plantilla sin confirmar).
- Navegación: provisional, un `Loader` con una sola propiedad de estado. El patrón definitivo (`StackView` vs. navegación plana) sigue sin decidirse — no cablear nada que asuma uno u otro.
- Logo: placeholder de texto (`"e-specifika"`) hasta que el diseñador reexporte el SVG sin clases CSS. No hay `Image` de logo todavía.

---

## PARTE 1 — Reorganización de archivos

### 1.1 Verificación previa

Confirmar que existen:

- `C:\Users\tecni\Documents\codigo_autoclave\src\autoclave\MOCUP ESPECIFIKA 2.0.zip`
- La raíz del repositorio en `C:\Users\tecni\Documents\codigo_autoclave\`

Si el `.zip` no está en esa ruta exacta, detenerse y preguntar.

### 1.2 Extracción en carpeta temporal

Extraer `MOCUP ESPECIFIKA 2.0.zip` en:

```
C:\Users\tecni\AppData\Local\Temp\mockup_v2_extraido\
```

Deben aparecer: `00_LEEME.md`, `ENTREGA_UI_AUTOCLAVE.zip` (zip anidado),
`ESPECIFICACION-UI-AUTOCLAVE-v1.pdf`, `indice_visual_iconos.png`.

El PDF y el PNG de este nivel son copias duplicadas de lo que hay dentro del zip anidado —
ignorarlos. Extraer `ENTREGA_UI_AUTOCLAVE.zip` en una subcarpeta de la misma carpeta temporal.
Debe contener las carpetas `01_ESPECIFICACIONES` hasta `07_TEXTOS`; si falta alguna, detenerse.

### 1.3 Crear estructura destino

```
src\autoclave\ui_qml\assets\iconos\mono\
src\autoclave\ui_qml\assets\iconos\color\
src\autoclave\ui_qml\assets\textos\
src\autoclave\ui_qml\assets\fuentes\      (queda vacía — pendiente del diseñador)
src\autoclave\ui_qml\assets\logo\         (queda vacía — pendiente del diseñador)
src\autoclave\ui_qml\qml\Tema\
src\autoclave\ui_qml\qml\Componentes\
src\autoclave\ui_qml\qml\Pantallas\
docs\diseno\referencias\pantallas_1080x1920\
docs\diseno\referencias\proporcion_original\
docs\diseno\png_96\
_archivo\
```

### 1.4 Mover — assets de ejecución (los que la app QML carga en tiempo real)

Desde `mockup_v2_extraido\ENTREGA_UI_AUTOCLAVE\`:

- `04_ICONOS_SVG\svg\` (49 archivos) → `src\autoclave\ui_qml\assets\iconos\mono\`
- `04_ICONOS_SVG\svg_color\` (49 archivos) → `src\autoclave\ui_qml\assets\iconos\color\`
- `07_TEXTOS\textos_ui_es.json` → `src\autoclave\ui_qml\assets\textos\es.json` (renombrar)

### 1.5 Mover — material de referencia (documentación, la app nunca lo lee)

Desde `mockup_v2_extraido\ENTREGA_UI_AUTOCLAVE\`:

- `01_ESPECIFICACIONES\especificacion_ui_autoclave_v1.pdf` → `docs\diseno\`
- `04_ICONOS_SVG\indice_visual_iconos.png` → `docs\diseno\`
- `02_COLOR\tokens.json`, `tokens.css`, `paleta.csv`, `paleta_especifika.ase` → `docs\diseno\`
- `03_TIPOGRAFIA\estilos_de_texto.csv` → `docs\diseno\`
- `06_MEDIDAS\medidas.csv` → `docs\diseno\`
- `07_TEXTOS\casos_mas_largos.csv` → `docs\diseno\`
- `05_PNG_REFERENCIA\pantallas_1080x1920\` (6 PNG) → `docs\diseno\referencias\pantallas_1080x1920\`
- `05_PNG_REFERENCIA\proporcion_original\` (6 PNG) → `docs\diseno\referencias\proporcion_original\`
- `04_ICONOS_SVG\png_96\` (49 PNG) → `docs\diseno\png_96\`
- `00_LEEME.md` (raíz del paquete) → `docs\diseno\00_LEEME_entrega_v2.md`

### 1.6 Verificación posterior

Contar y reportar:

- Archivos en `assets\iconos\mono\` — debe ser 49
- Archivos en `assets\iconos\color\` — debe ser 49
- `assets\textos\es.json` existe y es JSON válido
- `docs\diseno\especificacion_ui_autoclave_v1.pdf` existe, 31 páginas

Si algún conteo no calza, detenerse y reportar qué carpeta quedó incompleta — no seguir a la
Parte 2.

### 1.7 Archivar el original (no borrar)

Mover a `_archivo\`: los dos `.zip` originales y lo que quede de `mockup_v2_extraido\`.
Agregar `_archivo\` a `.gitignore` si no está ya.

---

## PARTE 2 — Escritura del andamiaje QML

Solo ejecutar esta parte si la verificación del paso 1.6 fue exitosa. Crear los siguientes
archivos con el contenido exacto indicado — no modificar valores, son tokens tomados
directamente de `tokens.css`/`paleta.csv`/`estilos_de_texto.csv`/`medidas.csv` del diseñador.

### 2.1 Archivo: `src\autoclave\ui_qml\qml\Tema\qmldir`

(sin extensión)

```
module Tema
singleton Escala 1.0 Escala.qml
singleton Colores 1.0 Colores.qml
singleton Tipografia 1.0 Tipografia.qml
```

### 2.2 Archivo: `src\autoclave\ui_qml\qml\Tema\Escala.qml`

```qml
pragma Singleton
import QtQuick

QtObject {
    // Lienzo de referencia del diseñador (06_MEDIDAS/medidas.csv: mesa_de_trabajo).
    // CAMBIAR estos dos valores a 1200x1920 cuando lleguen los assets corregidos
    // para el panel real medido (1200x1920, 5:8) — es el único lugar que hay que tocar.
    readonly property real anchoDiseno: 1080
    readonly property real altoDiseno: 1920

    property real factor: 1.0

    function px(valor) { return valor * factor }
    // pixelSize exige entero; redondear evita que Qt trunque y el texto quede chico
    function fuente(valor) { return Math.max(1, Math.round(valor * factor)) }
}
```

### 2.3 Archivo: `src\autoclave\ui_qml\qml\Tema\Colores.qml`

```qml
pragma Singleton
import QtQuick

// Fuente única de color: 02_COLOR/tokens.css y paleta.csv del diseñador.
// Ninguna pantalla debe escribir un hex a mano — todo pasa por aquí.
QtObject {
    // Fondos oscuros (arranque / chrome)
    readonly property color fondoMarinoOscuro:  "#1B222A"  // fondo_marino_950
    readonly property color fondoBarraSuperior: "#2C4B70"  // fondo_marino_700
    readonly property color fondoAzulMedio:     "#2E597C"  // fondo_azul_700
    readonly property color fondoCieloNucleo:   "#5C97DB"  // fondo_cielo_300 — halo del arranque
    readonly property color fondoCieloClaro:    "#99C5E2"  // fondo_cielo_200

    // Acción
    readonly property color accionPrimario:      "#1168F6" // botón primario
    readonly property color accionPrimarioTexto: "#0D53C4" // obligatorio para texto (contraste)

    // Alarmas IEC 60601-1-8 — reservado, no usar para nada que no sea alarma
    readonly property color alarmaAlta:  "#EE0000"
    readonly property color alarmaMedia: "#FFCC00"
    readonly property color alarmaBaja:  "#00CCFF"

    // Neutros / texto
    readonly property color textoPrimario:      "#031225" // neutro_900
    readonly property color textoSecundario:    "#4D4D4D" // neutro_700
    readonly property color textoGuia:          "#808080" // neutro_500 — placeholder, ≥19px
    readonly property color bordeCampo:         "#CCCCCC" // neutro_300
    readonly property color fondoTarjeta:       "#FFFFFF"
    readonly property color iconoBarraInferior: "#333333" // neutro_800
}
```

### 2.4 Archivo: `src\autoclave\ui_qml\qml\Tema\Tipografia.qml`

```qml
pragma Singleton
import QtQuick

// Estilos de 03_TIPOGRAFIA/estilos_de_texto.csv.
// PENDIENTE: familia sin confirmar formalmente por el diseñador (tokens.css dice "Inter",
// el único archivo de fuente real entregado es Montserrat). Se usa Montserrat como decisión
// de trabajo, reversible cambiando esta única línea.
QtObject {
    readonly property string familia: "Montserrat"

    // tamaños en px de diseño — pasar por Escala.fuente() al usarlos
    readonly property int relojDisplayTam: 158
    readonly property int relojBarraTam: 54
    readonly property int relojFechaTam: 20
    readonly property int tituloPantallaTam: 36
    readonly property int campoEtiquetaTam: 22
    readonly property int campoValorTam: 26
    readonly property int botonEtiquetaTam: 26

    readonly property int pesoLight: Font.Light
    readonly property int pesoRegular: Font.Normal
    readonly property int pesoMedium: Font.Medium
    readonly property int pesoSemiBold: Font.DemiBold
    readonly property int pesoBold: Font.Bold
}
```

### 2.5 Archivo: `src\autoclave\ui_qml\qml\Componentes\BarraSuperior.qml`

```qml
import QtQuick
import Tema

// Barra superior común a casi todas las pantallas (06_MEDIDAS: 1080x176 en el diseño).
Rectangle {
    id: raiz
    width: Escala.px(Escala.anchoDiseno)
    height: Escala.px(176)
    color: Colores.fondoBarraSuperior

    // Reloj en vivo: formato manual (no Qt.locale) para no depender de que el
    // sistema tenga datos de localización en español instalados.
    property var _meses: ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"]
    property date _ahora: new Date()
    Timer { interval: 1000; running: true; repeat: true; onTriggered: raiz._ahora = new Date() }

    function _dosDigitos(n) { return n < 10 ? "0" + n : "" + n }

    Row {
        anchors.fill: parent
        anchors.leftMargin: Escala.px(24)
        anchors.rightMargin: Escala.px(24)
        spacing: 0

        // Placeholder de logo: reemplazar por Image cuando el SVG esté reexportado
        Text {
            text: "e-specifika"
            color: "white"
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(24)
            font.weight: Tipografia.pesoBold
            anchors.verticalCenter: parent.verticalCenter
        }

        Item { width: parent.width - Escala.px(220); height: 1 } // separador flexible

        Column {
            anchors.verticalCenter: parent.verticalCenter
            spacing: Escala.px(2)
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: raiz._dosDigitos(raiz._ahora.getHours()) + ":" +
                      raiz._dosDigitos(raiz._ahora.getMinutes())
                color: "white"
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(Tipografia.relojBarraTam)
                font.weight: Tipografia.pesoSemiBold
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: raiz._ahora.getDate() + " " +
                      raiz._meses[raiz._ahora.getMonth()] + "  -  " +
                      raiz._ahora.getFullYear()
                color: "#C7DCFD"
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(Tipografia.relojFechaTam)
                font.weight: Tipografia.pesoMedium
            }
        }
    }
}
```

### 2.6 Archivo: `src\autoclave\ui_qml\qml\Componentes\BarraInferior.qml`

```qml
import QtQuick
import Tema

// Barra inferior de navegación (1080x168). Recibe una lista de botones:
// [{icono: "casa", activo: true, accion: function(){...}}, ...]
Rectangle {
    id: raiz
    property var botones: []

    width: Escala.px(Escala.anchoDiseno)
    height: Escala.px(168)
    color: Colores.fondoTarjeta

    // Ruta de assets: ajustar si la ubicación final de los SVG cambia
    property string carpetaIconos: "../../assets/iconos/mono/"

    Row {
        anchors.centerIn: parent
        spacing: Escala.px(64)

        Repeater {
            model: raiz.botones
            delegate: Rectangle {
                width: Escala.px(68); height: Escala.px(68)
                radius: Escala.px(12)
                color: modelData.activo ? Colores.accionPrimario : "transparent"

                Image {
                    anchors.centerIn: parent
                    width: Escala.px(28); height: Escala.px(28)
                    source: raiz.carpetaIconos + modelData.icono + ".svg"
                    sourceSize.width: width
                    sourceSize.height: height
                }

                MouseArea {
                    anchors.fill: parent
                    onClicked: if (modelData.accion) modelData.accion()
                }
            }
        }
    }
}
```

### 2.7 Archivo: `src\autoclave\ui_qml\qml\Pantallas\Arranque.qml`

```qml
import QtQuick
import Tema

// Pantalla 06 · Arranque. Sin dependencias de backend: solo reloj y logo.
// Avanza al tocar cualquier punto — es la señal más simple posible; se
// reemplaza por un disparo real (ej. "backend listo") cuando se defina.
Item {
    id: raiz
    signal tocado()

    // Aproximación de --gradient-splash con Gradient lineal (QML no trae
    // radial nativo sin Qt5Compat.GraphicalEffects). Ajustar con el
    // componente real cuando se decida si vale la pena esa dependencia extra.
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: Colores.fondoCieloNucleo }
            GradientStop { position: 0.4; color: Colores.fondoAzulMedio }
            GradientStop { position: 1.0; color: Colores.fondoMarinoOscuro }
        }
    }

    property var _meses: ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"]
    property date _ahora: new Date()
    Timer { interval: 1000; running: true; repeat: true; onTriggered: raiz._ahora = new Date() }
    function _dosDigitos(n) { return n < 10 ? "0" + n : "" + n }

    Column {
        anchors.centerIn: parent
        spacing: Escala.px(24)

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "e-specifika"   // placeholder de logo
            color: "white"
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(36)
            font.weight: Tipografia.pesoBold
        }

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: raiz._dosDigitos(raiz._ahora.getHours()) + ":" +
                  raiz._dosDigitos(raiz._ahora.getMinutes())
            color: "white"
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(Tipografia.relojDisplayTam)
            font.weight: Tipografia.pesoLight
        }

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: raiz._ahora.getDate() + " " +
                  raiz._meses[raiz._ahora.getMonth()] + "  -  " +
                  raiz._ahora.getFullYear()
            color: "#C7DCFD"
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(Tipografia.relojFechaTam)
            font.weight: Tipografia.pesoMedium
        }
    }

    MouseArea { anchors.fill: parent; onClicked: raiz.tocado() }
}
```

### 2.8 Archivo: `src\autoclave\ui_qml\qml\Pantallas\Login.qml`

```qml
import QtQuick
import QtQuick.Controls.Basic
import Tema
import "../Componentes"

// Pantalla 03 · Inicio de sesión.
// PENDIENTE (bloqueante real): el JSON de textos no trae "LOGIN" ni
// "Inicie sesión para continuar" — solo etiquetas de campo. Quedan como
// placeholder marcados abajo; hay que pedírselos al diseñador junto con
// el resto de textos que faltan.
// PENDIENTE: la autenticación contra el backend no está conectada — este es
// el cascarón visual. Falta resolver el canal de comunicación (HTTP vs.
// acceso directo) antes de cablear el botón "INICIAR SESIÓN".
Item {
    id: raiz

    Rectangle { anchors.fill: parent; color: Colores.fondoBarraSuperior }

    Column {
        anchors.fill: parent
        BarraSuperior {}

        Rectangle {
            width: parent.width
            height: parent.height - Escala.px(176) - Escala.px(168)
            color: "white"

            Column {
                anchors.horizontalCenter: parent.horizontalCenter
                y: Escala.px(60)
                width: Escala.px(700)
                spacing: Escala.px(28)

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "LOGIN"
                    color: Colores.textoPrimario
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(Tipografia.tituloPantallaTam)
                    font.weight: Tipografia.pesoBold
                }

                // Avatar placeholder — reemplazar por foto de usuario cuando exista
                Rectangle {
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: Escala.px(160); height: Escala.px(160); radius: width / 2
                    color: "#E6E6E6"
                }

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "Inicie sesión para continuar"  // PLACEHOLDER
                    color: Colores.textoSecundario
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(Tipografia.campoValorTam)
                }

                Rectangle {
                    width: parent.width; height: Escala.px(88); radius: Escala.px(6)
                    border.color: Colores.bordeCampo; border.width: 1
                    TextField {
                        anchors.fill: parent
                        anchors.margins: Escala.px(4)
                        placeholderText: "Nombre Usuario"
                        font.pixelSize: Escala.fuente(Tipografia.campoValorTam)
                        background: null
                    }
                }

                Rectangle {
                    width: parent.width; height: Escala.px(88); radius: Escala.px(6)
                    border.color: Colores.bordeCampo; border.width: 1
                    TextField {
                        id: campoClave
                        anchors.fill: parent
                        anchors.margins: Escala.px(4)
                        placeholderText: "Contraseña"
                        echoMode: TextInput.Password
                        font.pixelSize: Escala.fuente(Tipografia.campoValorTam)
                        background: null
                    }
                }

                Rectangle {
                    width: parent.width; height: Escala.px(88); radius: Escala.px(6)
                    color: Colores.accionPrimario
                    Text {
                        anchors.centerIn: parent
                        text: "INICIAR SESIÓN"
                        color: "white"
                        font.family: Tipografia.familia
                        font.pixelSize: Escala.fuente(Tipografia.botonEtiquetaTam)
                        font.weight: Tipografia.pesoSemiBold
                    }
                    // TODO: conectar con backend cuando se resuelva el canal
                    MouseArea { anchors.fill: parent }
                }

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "¿Olvidó su contraseña?"
                    color: Colores.accionPrimarioTexto
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(22)
                }
            }
        }

        BarraInferior {
            botones: [
                { icono: "salir_sesion",  activo: false },
                { icono: "historial",     activo: false },
                { icono: "mantenimiento", activo: false },
                { icono: "casa",          activo: true  }
            ]
        }
    }
}
```

### 2.9 Archivo: `src\autoclave\ui_qml\qml\Main.qml`

```qml
import QtQuick
import Tema
import "Pantallas"

Window {
    id: ventana
    width: 540; height: 960
    visibility: Window.Windowed   // producción: Window.FullScreen
    visible: true
    color: Colores.fondoMarinoOscuro

    Binding {
        target: Escala
        property: "factor"
        value: Math.min(ventana.width / Escala.anchoDiseno,
                        ventana.height / Escala.altoDiseno)
    }

    // Navegación provisional de 2 estados — el patrón definitivo (StackView vs.
    // navegación plana) sigue sin decidirse; esto se reemplaza sin tocar pantallas.
    property string pantallaActual: "arranque"

    Item {
        width: Escala.px(Escala.anchoDiseno)
        height: Escala.px(Escala.altoDiseno)
        anchors.centerIn: parent
        clip: true

        Loader {
            anchors.fill: parent
            sourceComponent: ventana.pantallaActual === "arranque"
                             ? arranqueComp : loginComp
        }
    }

    Component {
        id: arranqueComp
        Arranque { onTocado: ventana.pantallaActual = "login" }
    }
    Component { id: loginComp; Login {} }
}
```

### 2.10 Archivo: `src\autoclave\ui_qml\main.py`

```python
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QFontDatabase, QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

BASE_DIR = Path(__file__).resolve().parent
QML_DIR = BASE_DIR / "qml"
FUENTES_DIR = BASE_DIR / "assets" / "fuentes"


def _cargar_fuentes() -> None:
    """Carga los .otf de Montserrat si la carpeta existe y tiene archivos."""
    if not FUENTES_DIR.exists():
        return
    for archivo in FUENTES_DIR.glob("*.otf"):
        QFontDatabase.addApplicationFont(str(archivo))


def main() -> int:
    app = QGuiApplication(sys.argv)
    _cargar_fuentes()

    engine = QQmlApplicationEngine()
    engine.addImportPath(str(QML_DIR))  # visibiliza el módulo "Tema"
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    if not engine.rootObjects():
        return 1
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
```

---

## PARTE 3 — Reporte final esperado

Al terminar, reportar en texto plano:

- Los conteos del paso 1.6 (49 mono, 49 color, es.json válido, PDF de 31 páginas)
- Confirmación de que `_archivo\` contiene los dos `.zip` y la carpeta temporal
- Lista de los 10 archivos creados en la Parte 2, con su ruta completa
- Confirmación de que `assets\fuentes\` y `assets\logo\` existen y están vacías (pendientes)
- Cualquier error de sintaxis QML detectado al guardar

---

## Qué sigue después de esta tarea (no ejecutar ahora)

Una vez confirmado el reporte del paso anterior, la siguiente tarea es:

1. Resolver las 5 preguntas bloqueantes de arquitectura de navegación (canal backend, modelo de actualización, estado de sesión global, modelo de datos de alarmas, patrón de navegación).
2. Construir la pantalla de Menú Principal y la de Ciclo en Curso, que son las que tienen la lógica visual más compleja (mosaicos de módulos, tarjetas de sensor, gráfica de ciclo, stepper de fases).
3. Conectar el backend Python con QML una vez definido el canal de comunicación.

Esa tarea se hace en una sesión de trabajo aparte, con el contenido de cada archivo ya definido.

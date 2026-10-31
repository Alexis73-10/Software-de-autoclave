import QtQuick
import Tema

// Loader de una sección de OPCIONES con crossfade: al dejar de estar
// `seleccionada` se desvanece (sigue cargado hasta terminar) y al seleccionarse
// se carga y aparece mientras la anterior se desvanece. Mientras se desvanece
// no recibe toques y `itemActivo` ya es null, para que la pantalla no consulte
// una sección que ya se dejó (cambiosPendientes, retroceder...).
Loader {
    id: raiz

    property bool seleccionada: false
    readonly property Item itemActivo: seleccionada ? item : null

    active: false
    opacity: 0
    visible: opacity > 0
    enabled: seleccionada

    NumberAnimation {
        id: anim
        target: raiz
        property: "opacity"
        duration: Movimiento.crossfadeMs
        easing.type: Easing.InOutQuad
        onFinished: if (!raiz.seleccionada) raiz.active = false
    }

    onSeleccionadaChanged: {
        anim.stop()
        if (Movimiento.instantaneo) {
            active = seleccionada
            opacity = seleccionada ? 1 : 0
            return
        }
        if (seleccionada) {
            active = true
            anim.to = 1
        } else {
            anim.to = 0
        }
        anim.start()
    }
    Component.onCompleted: if (seleccionada) { active = true; opacity = 1 }
}

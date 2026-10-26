import QtQuick
import Autoclave.I18n

// Tanda 17 (PRC-01): selector de programa reutilizable. Reemplaza la cuadrícula
// (Flow) de chips de Opciones › Parámetros del ciclo y se usa también en
// Opciones avanzadas › Manejo de ciclos (DECISIÓN SIN CONFIRMAR: uniformidad).
// Botón con el programa vigente ("NN · nombre", con ⚠ si está dañado) que abre
// una lista vertical con desplazamiento (Desplegable); cada fila lleva el
// objectName "programa_" + número.
//
// programas: [{numero, nombre, danado?}] (los de ParametrosCicloController /
// ManejoCiclosController)
Desplegable {
    id: raiz

    property var programas: []
    property int numero: 0
    signal programaElegido(int numero)

    function numero2(n) { return String(n).padStart(2, "0") }

    prefijoFila: "programa_"
    tituloLista: I18n.t("selector_programa.titulo", I18n.lang)
    textoVacio: I18n.t("selector_programa.vacio", I18n.lang)
    textoSinValor: I18n.t("selector_programa.elegir", I18n.lang)
    valor: numero
    opciones: (programas || []).map(p => ({ valor: p.numero,
                                            texto: numero2(p.numero) + " · " + p.nombre,
                                            aviso: p.danado ? "⚠" : "" }))
    onElegido: (v) => raiz.programaElegido(Number(v))
}

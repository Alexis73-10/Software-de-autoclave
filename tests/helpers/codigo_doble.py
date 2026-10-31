"""Verificadores de código de instalación inyectables en las pruebas.

Reemplazan a `lambda s, c: True` del v1: tienen la firma de
`installation.activacion_v2.verificar_codigo_instalacion`
(serial, codigo, modo, serie_original=None, modelo_original=None, *, hoy=None, k_t=None, validar_v1=...)
y devuelven un `ResultadoCodigo`. Cada doble guarda sus llamadas en `.llamadas`.
"""
from autoclave.installation.activacion_v2 import Modo, ResultadoCodigo, normalizar_originales


def _doble(resultado_para):
    llamadas = []

    def verificador(serial, codigo, modo=Modo.FABRICACION, serie_original=None, modelo_original=None,
                    *, hoy=None, k_t=None, validar_v1=None):
        llamadas.append({"serial": serial, "codigo": codigo, "modo": Modo(modo),
                         "serie_original": serie_original, "modelo_original": modelo_original})
        return resultado_para(Modo(modo), serie_original, modelo_original)

    verificador.llamadas = llamadas
    return verificador


def acepta(modo=None, originales=None, tipo="INS"):
    """Acepta todo código. `modo` y `originales` (serie_n, modelo_n) fijan lo que devuelve; sin ellos,
    toma el modo y los originales con que se le llama (en automatización, tal cual se recibieron)."""
    def resultado(modo_llamada, serie, modelo):
        efectivo = Modo(modo) if modo is not None else modo_llamada
        orig = originales
        if orig is None and efectivo is Modo.AUTOMATIZACION and serie is not None and modelo is not None:
            orig = normalizar_originales(serie, modelo)   # como el verificador real
        if efectivo is Modo.FABRICACION:
            orig = None
        return ResultadoCodigo(ok=True, formato="v2", tipo=tipo, originales=orig)
    return _doble(resultado)


def rechaza(motivo="etiqueta"):
    """Rechaza todo código con el motivo dado."""
    return _doble(lambda *_: ResultadoCodigo(ok=False, motivo=motivo, formato="v2"))


# --- Constructor de códigos v2 reales (INS/REI/INSA/REIA) para pruebas ---------------------------------
# Puerto de `codigo_instalacion` del generador (generador/formato/codigos.py) sobre los mismos primitivos
# de `activacion_v2`; las pruebas comprueban que reproduce los vectores V1-V3 del generador byte a byte.

K_T_PRUEBA = bytes.fromhex("6578a9994682225f37861fe063d7f5edd44e022a91f884acc21d014ef3889857")


def construir_codigo_v2(serial, k_e, *, permanente, ventana, P, G, orig, emerg, originales=None,
                        k_t=K_T_PRUEBA, agrupar=False):
    """Código canónico de 48 caracteres. `ventana` y `orig` son `date`; `originales` = (serie, modelo)
    en bruto (se normalizan) para INSA/REIA."""
    from autoclave.installation import activacion_v2 as v2
    h_orig = None if originales is None else v2.huella_originales(*originales)
    tipo = "INS" if orig is None else "REI"
    dia_ventana = (ventana - v2._EPOCA).days
    dia_orig = 0 if orig is None else (orig - v2._EPOCA).days
    campos = (int(permanente), dia_ventana, dia_orig, P, G, emerg)
    etiqueta = v2._etiqueta_instalacion(k_t, tipo, serial, campos, k_e, h_orig)
    k_e_cifrado = v2._xor(k_e, v2._flujo_instalacion(k_t, etiqueta))
    valores = (*campos, int.from_bytes(k_e_cifrado, "big"), int.from_bytes(etiqueta, "big"))
    valor, nbits = (v2._VERSION << 3) | v2._TIPOS[tipo], 5
    for campo, ancho in zip(valores, v2._ANCHOS_INSTALACION, strict=True):
        valor, nbits = (valor << ancho) | campo, nbits + ancho
    cuerpo = "".join(v2._ALFABETO[(valor >> d) & 31] for d in range(nbits - 5, -1, -5))
    codigo = con_control(cuerpo)
    if agrupar:
        return "-".join(codigo[i:i + 4] for i in range(0, len(codigo), 4))
    return codigo


def con_control(cuerpo):
    """`cuerpo` + su carácter de control Luhn (para fabricar cabeceras alteradas con control válido)."""
    from autoclave.installation import activacion_v2 as v2
    return cuerpo + v2._ALFABETO[-v2._suma_luhn(cuerpo, 2) % 32]

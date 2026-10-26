# ui_qml/bridge/acciones_ciclos.py
#
# Acciones de impresión y correo del Menú Principal, fuera del hilo de la GUI,
# sobre ciclos del Historial y sobre el resumen por periodo de Reportes:
#   - Imprimir: POST /cycle/history/print; el backend los encola en la impresora
#     térmica (lo rechaza con 409 durante un ciclo y con 503 si Windows no
#     reporta la impresora lista: desconectada, sin papel, no instalada o error).
#   - Enviar por correo: por cada ciclo pide GET /cycle/history/{id}/ticket y
#     /graph, arma un PDF con la gráfica y el ticket (exportacion/pdf_ciclo.py) y
#     lo envía por SMTP con el remitente de exportacion/config_correo.py (un PDF,
#     o varios en un ZIP), como lo hacía ui_pyside/views/ciclos.py.
#   - Resumen por periodo: POST /report/summary/print (mismas reglas que la
#     reimpresión) o GET /report/summary -> PDF (exportacion/pdf_resumen.py) -> correo.
#   - Reporte consolidado de un periodo: resumen + /cycle/list + ticket y curva de
#     cada ciclo -> un solo PDF (exportacion/pdf_consolidado.py) -> correo, con el
#     avance en `progreso` mientras trabaja.
# Las gráficas de los PDF llevan las consignas de esterilización (domain/consignas.py).
# Una acción a la vez (`ocupado`); el resultado llega por accionTerminada(éxito,
# mensaje) para que la pantalla lo muestre.
# C2 (tanda 7): `destino` puede traer varias direcciones separadas por coma
# (las guardadas y/o una escrita a mano). Todas se validan antes de enviar; el
# mensaje sale de lo que el relay ACEPTÓ por destinatario (nunca "enviado" sin
# aceptación) y cada intento queda en la bitácora del backend (POST
# /email/sent) con las direcciones y el resultado, sin la contraseña. Una
# dirección escrita a mano NO se guarda: los destinatarios guardados siguen
# siendo de admin e ingeniero (OPCIONES › Conectividad).

import logging
import smtplib
import tempfile
import threading
from pathlib import Path

import requests
from PySide6.QtCore import Property, QObject, Signal, Slot

from autoclave import i18n
from autoclave.core.runtime.progreso_ciclo import FASES_UI
from autoclave.core.runtime import alarmas_i18n
from autoclave.installation.modelo import desglosar_modelo
from autoclave.services.domain.logging import ticket_formatter
from autoclave.services.domain.logging.ticket_formatter import format_ticket
from autoclave.ui_qml.domain import reporte_resumen
from autoclave.ui_qml.domain.consignas import consigna_esterilizacion
from autoclave.ui_qml.domain import resumen_sistema as dominio
from autoclave.ui_qml.domain.ciclo_en_curso import AcumuladorGrafica
from autoclave.ui_qml.exportacion import config_correo, correo
from autoclave.ui_qml.exportacion import unidades_pdf
from autoclave.ui_qml.exportacion.textos import textos_ciclo

# tope de ciclos del consolidado: el adjunto queda lejos del límite de 25 MB de Gmail
MAX_CICLOS_CONSOLIDADO = 200
# C2: todos los guardados (config_correo_equipo.MAX_DESTINATARIOS = 10) más uno a mano
MAX_DESTINOS_ENVIO = 11

logger = logging.getLogger(__name__)


def texto_empresa(modelo, serie, idioma: str | None = None) -> str:
    """Línea de empresa de la cabecera del PDF. E2 (tanda 8; D8-0 y D8-3.23):
    si el modelo sigue la regla "SPK-SAT …", se agregan la familia
    ("Hospitalario"/"Laboratorio"), la capacidad y el tipo de carga, deducidos
    del nombre guardado; un modelo anterior queda como antes."""
    texto = i18n.t("exportacion.empresa", idioma, modelo=modelo or "", serie=serie or "")
    datos = desglosar_modelo(modelo)
    if datos is None:
        return texto
    return texto + " · " + i18n.t(
        "exportacion.equipo_pdf", idioma,
        clase=i18n.t("equipo.clase_" + datos["clase"], idioma),
        capacidad=datos["capacidad_litros"],
        carga=i18n.t("exportacion.carga_" + datos["tipo_carga"], idioma))


def _en_hilo(tarea) -> None:
    threading.Thread(target=tarea, daemon=True, name="acciones-ciclos").start()


def _es_no_conforme(ciclo) -> bool:
    """P4 (tanda 16, D-14.4): el ciclo guardado quedó NO CONFORME (campo
    no_conforme del backend o, en su defecto, su avisos_ticket)."""
    if not isinstance(ciclo, dict):
        return False
    return ciclo.get("no_conforme") is True or ticket_formatter.ciclo_no_conforme(ciclo)


def _marcar_no_conforme(asunto: str, cuerpo: str, ciclos) -> tuple[str, str]:
    """P4 (D-14.4): con algún ciclo NO CONFORME, el asunto lo dice y el cuerpo
    nombra esos ciclos. Sin ninguno, asunto y cuerpo quedan igual."""
    numeros = []
    for c in ciclos or []:
        if _es_no_conforme(c):
            try:
                numeros.append(f"{int(c.get('numero_ciclo')):06d}")
            except (TypeError, ValueError):
                numeros.append(dominio.SIN_DATO)
    if not numeros:
        return asunto, cuerpo
    return (i18n.t("exportacion.asunto_no_conforme", asunto=asunto),
            cuerpo + "\n\n" + i18n.t("exportacion.cuerpo_no_conforme", ciclos=", ".join(numeros)))


def _presentacion_vigente() -> "ticket_formatter.Presentacion":
    """I4 (tanda 6): idioma de la UI y unidades del singleton Unidades (que
    sigue a GET /units). Ante cualquier error, español en °C y kPa."""
    try:
        from autoclave.ui_qml.bridge.unidades_qml import instancia
        p = ticket_formatter.Presentacion(i18n.idioma(), instancia.temperatura,
                                          instancia.presion, instancia._p_atm)
        from autoclave.core.runtime import unidades as u
        u.validar(p.temperatura, p.presion)
        return p
    except Exception:
        return ticket_formatter.Presentacion()


def _generar_pdf(*args) -> None:
    # importación diferida: QtGui solo hace falta al enviar
    from autoclave.ui_qml.exportacion.pdf_ciclo import generar_pdf
    generar_pdf(*args)


def _generar_pdf_resumen(*args) -> None:
    from autoclave.ui_qml.exportacion.pdf_resumen import generar_pdf_resumen
    generar_pdf_resumen(*args)


def _generar_pdf_consolidado(*args, **kwargs) -> list:
    from autoclave.ui_qml.exportacion.pdf_consolidado import generar_pdf_consolidado
    return generar_pdf_consolidado(*args, **kwargs)


class _ErrorConMensaje(Exception):
    """Fallo ya traducido al mensaje que verá el usuario."""


class AccionesCiclos(QObject):
    ocupadoChanged = Signal()
    correoChanged = Signal()
    accionTerminada = Signal(bool, str)
    progresoChanged = Signal()
    _terminado = Signal(bool, str)          # emitidas desde el hilo de trabajo
    _avance = Signal(str)

    def __init__(self, backend_client, parent=None, cargar_config=config_correo.cargar,
                 ejecutar=_en_hilo, generar_pdf=_generar_pdf, enviar=correo.enviar,
                 generar_pdf_resumen=_generar_pdf_resumen,
                 generar_pdf_consolidado=_generar_pdf_consolidado,
                 presentacion=_presentacion_vigente):
        super().__init__(parent)
        self._presentacion = presentacion
        self._backend = backend_client
        self._cargar_config = cargar_config
        self._ejecutar = ejecutar
        self._generar_pdf = generar_pdf
        self._generar_pdf_resumen = generar_pdf_resumen
        self._generar_pdf_consolidado = generar_pdf_consolidado
        self._progreso = ""
        self._enviar = enviar
        self._ocupado = False
        self._config = cargar_config()
        self._terminado.connect(self._al_terminar)
        self._avance.connect(self._fijar_progreso)

    # ── estado ───────────────────────────────────────────────────────────

    @Property(bool, notify=ocupadoChanged)
    def ocupado(self) -> bool:
        return self._ocupado

    @Property(str, notify=progresoChanged)
    def progreso(self) -> str:
        """Avance de la acción en curso ("Preparando ciclo 3 de 40…"); "" si no hay."""
        return self._progreso

    def _fijar_progreso(self, texto: str) -> None:
        if texto != self._progreso:
            self._progreso = texto
            self.progresoChanged.emit()

    @Property(bool, notify=correoChanged)
    def correoConfigurado(self) -> bool:
        return self._config.configurado

    @Property("QVariantList", notify=correoChanged)
    def destinos(self) -> list:
        """Destinos por defecto: [{nombre, correo}]."""
        return self._config.destinos

    @Slot()
    def actualizarCorreo(self) -> None:
        """Relee la configuración (al abrir la ventana: se edita a mano por ahora)."""
        self._config = self._cargar_config()
        self.correoChanged.emit()

    def _empezar(self, tarea) -> bool:
        if self._ocupado:
            return False
        self._ocupado = True
        self.ocupadoChanged.emit()

        def envoltura():
            try:
                exito, mensaje = tarea()
            except _ErrorConMensaje as e:
                exito, mensaje = False, str(e)
            except Exception:
                logger.exception("Acción sobre ciclos fallida")
                exito, mensaje = False, i18n.t("exportacion.error_envio")
            self._terminado.emit(exito, mensaje)

        self._ejecutar(envoltura)
        return True

    def _al_terminar(self, exito: bool, mensaje: str) -> None:
        self._fijar_progreso("")
        self._ocupado = False
        self.ocupadoChanged.emit()
        self.accionTerminada.emit(exito, mensaje)

    # ── imprimir ─────────────────────────────────────────────────────────

    @Slot("QVariantList")
    def imprimir(self, ids: list) -> None:
        ids = [int(i) for i in ids]
        if not ids:
            return

        def tarea():
            r = self._post_impresion("/cycle/history/print", {"ids": ids})
            return True, i18n.t("exportacion.impreso", n=r.get("impresos", len(ids)))

        self._empezar(tarea)

    @Slot(str, str)
    def imprimirResumen(self, periodo: str, fecha: str) -> None:
        """Resumen del periodo de calendario que contiene `fecha` (ISO)."""
        def tarea():
            self._post_impresion("/report/summary/print", {"periodo": periodo, "fecha": fecha})
            return True, i18n.t("exportacion.impreso_resumen")

        self._empezar(tarea)

    def _post_impresion(self, ruta: str, cuerpo: dict) -> dict:
        """POST de impresión con sus errores traducidos al aviso de la pantalla."""
        try:
            return self._backend.post(ruta, cuerpo)
        except requests.HTTPError as e:
            codigo = getattr(e.response, "status_code", None)
            if codigo == 409:
                raise _ErrorConMensaje(i18n.t("exportacion.imprimir_en_ciclo"))
            if codigo == 503:
                raise _ErrorConMensaje(self._mensaje_impresora(e.response))
            raise _ErrorConMensaje(i18n.t("exportacion.imprimir_error"))
        except Exception as e:
            logger.debug("impresión no disponible: %s", e)
            raise _ErrorConMensaje(i18n.t("exportacion.imprimir_error"))

    def _mensaje_impresora(self, respuesta) -> str:
        """Aviso del estado de la impresora que devolvió el backend (503)."""
        try:
            estado = respuesta.json()["detail"]["impresora"]
        except Exception:
            estado = "error"
        if estado not in ("desconectada", "sin_papel", "no_instalada"):
            estado = "error"
        return i18n.t("exportacion.impresora_" + estado)

    # ── enviar por correo ────────────────────────────────────────────────

    @Slot("QVariantList", str)
    def enviarCorreo(self, ids: list, destino: str) -> None:
        ids = [int(i) for i in ids]
        if not ids:
            return
        config = self._config

        def tarea():
            destinos = self._validar_envio(config, destino)
            pdfs, ciclos = self._pdfs(ids)
            serie = ciclos[0].get("serie") or ""
            numeros = ", ".join(f"{c['numero_ciclo']:06d}" for c in ciclos)
            asunto, cuerpo = _marcar_no_conforme(
                i18n.t("exportacion.asunto", serie=serie, ciclos=numeros),
                i18n.t("exportacion.cuerpo"), ciclos)
            r = self._enviar_mensaje(config, destinos, asunto, cuerpo,
                                     correo.adjunto(pdfs, i18n.t("exportacion.nombre_zip")),
                                     tipo="ciclos", ciclos=ids)
            return self._resultado(r, "exportacion.enviado", n=len(ids))

        self._empezar(tarea)

    @Slot(str, str, str)
    def enviarResumen(self, periodo: str, fecha: str, destino: str) -> None:
        """PDF del resumen del periodo que contiene `fecha` (ISO), por correo."""
        config = self._config

        def tarea():
            destinos = self._validar_envio(config, destino)
            try:
                r = self._backend.get("/report/summary", params={"periodo": periodo, "fecha": fecha})
            except Exception as e:
                logger.debug("resumen del periodo no disponible: %s", e)
                raise _ErrorConMensaje(i18n.t("exportacion.error_datos"))
            desde, hasta = r.get("desde", ""), r.get("hasta", "")
            texto_periodo = i18n.t("exportacion.periodo_resumen",
                                   desde=dominio.formatear_fecha(desde),
                                   hasta=dominio.formatear_fecha(hasta))
            nombre = f"resumen_{desde}_{hasta}.pdf"
            with tempfile.TemporaryDirectory() as carpeta:
                ruta = Path(carpeta) / nombre
                self._generar_pdf_resumen(ruta, {
                    "empresa": texto_empresa(r.get("modelo"), r.get("serie")),
                    "titulo": i18n.t("exportacion.titulo_resumen"),
                    "periodo": texto_periodo,
                    "resumen": reporte_resumen.presentable(r),
                }, dict(i18n.valor("reportes")))
                contenido = ruta.read_bytes()
            envio = self._enviar_mensaje(config, destinos,
                                         i18n.t("exportacion.asunto_resumen",
                                                serie=r.get("serie") or "", periodo=texto_periodo),
                                         i18n.t("exportacion.cuerpo_resumen"),
                                         (nombre, contenido, "pdf"), tipo="resumen")
            return self._resultado(envio, "exportacion.enviado_resumen")

        self._empezar(tarea)

    @Slot(str, str, str)
    def enviarConsolidado(self, periodo: str, fecha: str, destino: str) -> None:
        """Un solo PDF con el resumen, el índice y las páginas de cada ciclo del
        periodo que contiene `fecha` (ISO), por correo."""
        config = self._config

        def tarea():
            destinos = self._validar_envio(config, destino)
            try:
                r = self._backend.get("/report/summary", params={"periodo": periodo, "fecha": fecha})
            except Exception as e:
                logger.debug("resumen del periodo no disponible: %s", e)
                raise _ErrorConMensaje(i18n.t("exportacion.error_datos"))
            total = (r.get("totales") or {}).get("total", 0)
            if not total:
                raise _ErrorConMensaje(i18n.t("exportacion.consolidado_vacio"))
            if total > MAX_CICLOS_CONSOLIDADO:
                raise _ErrorConMensaje(i18n.t("exportacion.consolidado_demasiados", n=total,
                                              maximo=MAX_CICLOS_CONSOLIDADO))
            try:
                lista = self._backend.get("/cycle/list", params={
                    "periodo": periodo, "terminados": "false", "fecha": fecha,
                    "limite": MAX_CICLOS_CONSOLIDADO})
            except Exception as e:
                logger.debug("listado del periodo no disponible: %s", e)
                raise _ErrorConMensaje(i18n.t("exportacion.error_datos"))
            filas = list(reversed(lista.get("ciclos") or []))   # el más antiguo primero
            ciclos = []
            for i, fila in enumerate(filas, start=1):
                self._avance.emit(i18n.t("exportacion.preparando", i=i, n=len(filas)))
                c = self._datos_ciclo(fila["id"])
                p = dominio.ciclo_presentable(fila)
                c["indice"] = [f"{c['ciclo']['numero_ciclo']:06d}", p["fecha"], p["hora"],
                               " · ".join(x for x in (p["programa"], p["programa_nombre"])
                                          if x != dominio.SIN_DATO) or dominio.SIN_DATO,
                               dict(c["datos"]["campos"])[i18n.t("exportacion.resultado")]]
                ciclos.append(c)

            desde, hasta = r.get("desde", ""), r.get("hasta", "")
            texto_periodo = i18n.t("exportacion.periodo_resumen",
                                   desde=dominio.formatear_fecha(desde),
                                   hasta=dominio.formatear_fecha(hasta))
            portada = {
                "empresa": texto_empresa(r.get("modelo"), r.get("serie")),
                "titulo": i18n.t("exportacion.titulo_consolidado"),
                "periodo": texto_periodo,
                "resumen": reporte_resumen.presentable(r),
            }
            nombre = f"consolidado_{desde}_{hasta}.pdf"
            with tempfile.TemporaryDirectory() as carpeta:
                ruta = Path(carpeta) / nombre
                self._generar_pdf_consolidado(
                    ruta, portada, ciclos, i18n.catalogo(),
                    progreso=lambda f: self._avance.emit(
                        i18n.t("exportacion.generando", porcentaje=round(100 * f))))
                contenido = ruta.read_bytes()
            self._avance.emit(i18n.t("menu.enviando"))
            asunto, cuerpo = _marcar_no_conforme(
                i18n.t("exportacion.asunto_consolidado",
                       serie=r.get("serie") or "", periodo=texto_periodo),
                i18n.t("exportacion.cuerpo_consolidado"), [c["ciclo"] for c in ciclos])
            envio = self._enviar_mensaje(config, destinos, asunto, cuerpo,
                                         (nombre, contenido, "pdf"), tipo="consolidado")
            return self._resultado(envio, "exportacion.enviado_consolidado", n=len(ciclos))

        self._empezar(tarea)

    def _validar_envio(self, config, destino) -> list[str]:
        """Direcciones del envío ("a@x.com,b@y.com" o lista), todas con formato
        válido; si una no lo tiene, no se envía a ninguna y el aviso la nombra."""
        destinos = correo.separar_destinos(destino)
        if not destinos or len(destinos) > MAX_DESTINOS_ENVIO:
            raise _ErrorConMensaje(i18n.t("exportacion.correo_invalido"))
        invalidas = [d for d in destinos if not config_correo.correo_valido(d)]
        if invalidas:
            raise _ErrorConMensaje(i18n.t("correo_c2.direccion_invalida",
                                          correo=", ".join(invalidas)))
        if not config.configurado:
            raise _ErrorConMensaje(i18n.t("exportacion.correo_no_configurado"))
        return destinos

    def _enviar_mensaje(self, config, destinos: list, asunto: str, cuerpo: str, archivo,
                        tipo: str, ciclos=None) -> "correo.ResultadoEnvio":
        """Envía y devuelve lo que el relay aceptó. Si no aceptó a nadie (o no
        hubo respuesta que lo confirme) lanza el aviso. Registra el intento."""
        mensaje = correo.armar_mensaje(config.remitente, destinos, asunto, cuerpo, archivo)
        registro = {"tipo": tipo, "destinatarios": list(destinos),
                    "manuales": self._manuales(config, destinos), "ciclos": list(ciclos or []),
                    "aceptados": [], "rechazados": {}}
        try:
            r = self._enviar(config, mensaje)
        except smtplib.SMTPAuthenticationError:
            self._auditar_envio({**registro, "resultado": "error_autenticacion"})
            raise _ErrorConMensaje(i18n.t("exportacion.error_autenticacion"))
        except (smtplib.SMTPException, OSError) as e:
            # solo el tipo: el texto de smtplib puede repetir datos de la sesión
            logger.warning("Envío de correo fallido (%s)", type(e).__name__)
            self._auditar_envio({**registro, "resultado": "error_conexion"})
            raise _ErrorConMensaje(i18n.t("exportacion.error_envio"))
        if not isinstance(r, correo.ResultadoEnvio):
            # sin respuesta por destinatario no hay aceptación que mostrar
            self._auditar_envio({**registro, "resultado": "sin_confirmacion"})
            raise _ErrorConMensaje(i18n.t("exportacion.error_envio"))
        registro.update(aceptados=list(r.aceptados), rechazados=dict(r.rechazados),
                        resultado="enviado" if r.todos_aceptados
                        else "rechazado" if r.ninguno_aceptado else "parcial")
        self._auditar_envio(registro)
        if r.ninguno_aceptado:
            raise _ErrorConMensaje(i18n.t("correo_c2.rechazados_todos",
                                          correos=", ".join(r.rechazados) or ", ".join(destinos)))
        return r

    @staticmethod
    def _resultado(r: "correo.ResultadoEnvio", clave: str, **kw) -> tuple[bool, str]:
        """Mensaje final con las direcciones ACEPTADAS; si el relay rechazó
        alguna, se dice cuál y el aviso queda como no exitoso."""
        texto = i18n.t(clave, destino=", ".join(r.aceptados), **kw)
        if r.rechazados:
            return False, texto + ". " + i18n.t("correo_c2.rechazados_parcial",
                                                 correos=", ".join(r.rechazados))
        return True, texto

    @staticmethod
    def _manuales(config, destinos: list) -> list:
        """Las direcciones del envío que no están entre las guardadas."""
        guardados = {str(d.get("correo", "")).lower() for d in (config.destinos or [])
                     if isinstance(d, dict)}
        return [d for d in destinos if d.lower() not in guardados]

    def _auditar_envio(self, registro: dict) -> None:
        """Bitácora del intento en el backend. Si el backend no responde, el
        resultado del envío no cambia (queda en el log de texto)."""
        try:
            self._backend.post("/email/sent", registro)
        except Exception as e:
            logger.warning("Envío de correo sin registro en la bitácora (%s): %s -> %s",
                           type(e).__name__, registro.get("destinatarios"),
                           registro.get("resultado"))

    def _pdfs(self, ids: list) -> tuple[list, list]:
        """[(nombre, bytes)] de cada ciclo y sus datos, en el orden pedido."""
        pdfs, ciclos = [], []
        with tempfile.TemporaryDirectory() as carpeta:
            for ciclo_id in ids:
                c = self._datos_ciclo(ciclo_id)
                nombre = f"ciclo_{c['ciclo']['numero_ciclo']:06d}.pdf"
                ruta = Path(carpeta) / nombre
                self._generar_pdf(ruta, c["datos"], c["ticket"], c["grafica"], c["fases"],
                                  self._textos_pdf(c), c["consigna"])
                pdfs.append((nombre, ruta.read_bytes()))
                ciclos.append(c["ciclo"])
        return pdfs, ciclos

    def _datos_ciclo(self, ciclo_id: int) -> dict:
        """Lo que necesitan las páginas de un ciclo: {ciclo, datos, ticket,
        grafica, fases, consigna} (GET /cycle/history/{id}/ticket y /graph)."""
        try:
            ticket = self._backend.get(f"/cycle/history/{ciclo_id}/ticket")
            grafica = self._backend.get(f"/cycle/history/{ciclo_id}/graph")
        except Exception as e:
            logger.debug("datos del ciclo %s no disponibles: %s", ciclo_id, e)
            raise _ErrorConMensaje(i18n.t("exportacion.error_datos"))
        ciclo = ticket["ciclo"]
        p = self._presentacion()             # una vez por ciclo: ticket, gráfica y datos iguales
        acumulador = AcumuladorGrafica()
        acumulador.incorporar(grafica)
        datos_grafica = acumulador.datos()
        fases = acumulador.inicios_de_fase(FASES_UI)
        t_fin = datos_grafica["t_min"][-1] if datos_grafica["t_min"] else 0.0
        consigna = consigna_esterilizacion(ciclo.get("temp_esterilizacion"), fases, t_fin)
        return {
            "ciclo": ciclo,
            "datos": self._datos_pdf(ciclo, p),
            "ticket": format_ticket(ciclo, ticket["lecturas"], p),
            # I4 (tanda 6): gráfica y consigna en las unidades vigentes
            "grafica": unidades_pdf.grafica(datos_grafica, p.temperatura, p.presion, p.p_atm),
            "fases": fases,
            "consigna": unidades_pdf.consigna(consigna, p.temperatura, p.presion, p.p_atm),
            "presentacion": p,
        }

    @staticmethod
    def _textos_pdf(c: dict) -> dict:
        """Rótulos del PDF de un ciclo, con los ejes en sus unidades."""
        p = c.get("presentacion") or ticket_formatter.Presentacion()
        return unidades_pdf.textos_ejes(textos_ciclo(i18n.catalogo()), p.temperatura, p.presion)

    def _datos_pdf(self, ciclo: dict, p=None) -> dict:
        p = p or ticket_formatter.Presentacion()
        fila = dominio.ciclo_presentable({
            "id": ciclo.get("id"), "numero_ciclo": ciclo.get("numero_ciclo"),
            "fecha_inicio": ciclo.get("fecha_inicio"), "fecha_fin": ciclo.get("fecha_fin"),
            "programa_nombre": ciclo.get("nombre_ciclo"), "resultado": ciclo.get("resultado")})
        clave = fila["resultado"]
        resultado = i18n.t("menu.resultado_" + clave.lower()) if clave else dominio.SIN_DATO
        if fila["resultado_detalle"]:
            resultado += f" ({fila['resultado_detalle']})"
        # P4 (tanda 16, D-14.4): NO CONFORME delante del resultado técnico
        if _es_no_conforme(ciclo):
            resultado = i18n.t("exportacion.no_conforme_resultado", resultado=resultado)
        fin = dominio.formatear_fecha(ciclo.get("fecha_fin"))
        hora_fin = dominio.formatear_hora(ciclo.get("fecha_fin"))
        return {
            "empresa": texto_empresa(ciclo.get("modelo"), ciclo.get("serie")),
            "titulo": i18n.t("exportacion.titulo", numero=f"{ciclo['numero_ciclo']:06d}",
                             programa=ciclo.get("nombre_ciclo") or dominio.SIN_DATO),
            "campos": [
                (i18n.t("exportacion.inicio"), f"{fila['fecha']}  {fila['hora']}"),
                (i18n.t("exportacion.fin"),
                 f"{fin}  {hora_fin}" if fin != dominio.SIN_DATO else dominio.SIN_DATO),
                (i18n.t("exportacion.resultado"), resultado),
                # I4 (tanda 6): unidades del documento en la cabecera
                (i18n.t("exportacion.unidades"), unidades_pdf.rotulo_unidades(p.temperatura, p.presion)),
            ] + self._campo_motivo(ciclo),
        }

    @staticmethod
    def _campo_motivo(ciclo: dict) -> list:
        """I4 (tanda 6): el motivo de fallo en el idioma vigente, desde su
        código y sus parámetros (ciclos.valores_fallo); [] si no hay."""
        motivo = alarmas_i18n.motivo_fallo(ciclo.get("codigo_fallo"), ciclo.get("valores_fallo"),
                                           ciclo.get("motivo_fallo"), i18n.idioma())
        return [(i18n.t("exportacion.motivo"), motivo)] if motivo else []

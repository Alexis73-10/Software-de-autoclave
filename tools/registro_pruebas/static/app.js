/* app.js — interfaz del registro de pruebas de banco (F1, tanda 3).
 * HTML/JS sin frameworks. Todo texto que viene del servidor o del usuario se
 * inserta con textContent (nunca como HTML): sin inyección de HTML.
 * Cada guardado va a la cola (IndexedDB) y se envía en segundo plano (cola.js). */
"use strict";

const NOMBRE_RESULTADO = { aprobada: "Aprobada", fallada: "Fallada", no_aplica: "No aplica" };
const CLASE_RESULTADO = { aprobada: "ok", fallada: "mal", no_aplica: "na" };
const yo = { usuario: null };
let defs = null;          // definiciones vigentes (GET /api/definiciones)
let det = null;           // registro abierto (estado del servidor + cambios locales)
let cola = null;

// ── utilidades ──────────────────────────────────────────────────────────────
function h(tag, attrs, ...hijos) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === false || v == null) continue;
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (k === "value") e.value = v;
    else e.setAttribute(k, v === true ? "" : v);
  }
  for (const c of hijos.flat()) {
    if (c == null || c === false) continue;
    e.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return e;
}
function idCliente() {
  const b = new Uint8Array(12);
  crypto.getRandomValues(b);          // randomUUID no existe fuera de contextos seguros (HTTP en la LAN)
  return "c" + Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
}
const ahora = () => new Date().toISOString();
const $ = (s) => document.querySelector(s);
function planos(nodos) { return nodos.flat(Infinity).filter((n) => n != null && n !== false); }
function vista(...nodos) { const v = $("#vista"); v.replaceChildren(...planos(nodos)); window.scrollTo(0, 0); }
function titulo(t) { $("#titulo").textContent = t; }

async function api(metodo, ruta, cuerpo) {
  const opc = { method: metodo, credentials: "same-origin", headers: { "X-Registro": "1" } };
  if (cuerpo !== undefined) { opc.headers["Content-Type"] = "application/json"; opc.body = JSON.stringify(cuerpo); }
  const r = await fetch(ruta, opc);
  let datos = null;
  try { datos = await r.json(); } catch (e) { /* sin cuerpo */ }
  if (r.status === 401) { cola && (cola.pausada = true); throw Object.assign(new Error("sesion"), { sesion: true }); }
  if (!r.ok) throw Object.assign(new Error((datos && datos.detail) || ("Error " + r.status)),
                                 { estado: r.status, codigo: datos && datos.codigo });
  return datos;
}

// ── cola de envío ───────────────────────────────────────────────────────────
async function enviarItem(item) {
  let r;
  try {
    const opc = { method: item.metodo, credentials: "same-origin", headers: { "X-Registro": "1" } };
    if (item.tipo === "foto") {
      const f = new FormData();
      f.append("file", item.archivo, "foto.jpg");
      f.append("cliente_id", item.cliente_id);
      f.append("ts_cliente", item.ts_cliente);
      opc.body = f;
    } else {
      opc.headers["Content-Type"] = "application/json";
      opc.body = JSON.stringify(item.cuerpo);
    }
    r = await fetch(item.ruta, opc);
  } catch (e) { return { estado: "red", motivo: "Sin conexión" }; }
  if (r.ok) return { estado: "ok" };
  let motivo = "Error " + r.status;
  try { const d = await r.json(); motivo = (d.detail || motivo) + (d.codigo ? " (" + d.codigo + ")" : ""); } catch (e) { /* */ }
  if (r.status === 401) return { estado: "sesion", motivo };
  if (r.status >= 500 || r.status === 408 || r.status === 429) return { estado: "red", motivo };
  return { estado: "rechazo", motivo };
}

async function actualizarIndicador() {
  const pend = cola ? await cola.pendientes() : [];
  const rech = cola ? await cola.rechazados() : [];
  const e = $("#pendientes");
  const hay = pend.length + rech.length;
  e.classList.toggle("oculto", !hay);
  e.textContent = rech.length ? `${pend.length} pendientes · ${rech.length} rechazados` : `${pend.length} pendientes de enviar`;
  $("#aviso-red").classList.toggle("oculto", !(cola && cola.pausada));
  $("#aviso-red").textContent = "La sesión venció: vuelva a iniciar sesión para enviar los pendientes (no se pierde nada).";
}
window.addEventListener("beforeunload", (ev) => {
  if (cola && cola.ultimosPendientes > 0) { ev.preventDefault(); ev.returnValue = ""; }
});
window.addEventListener("online", () => cola && cola.procesar());

async function iniciarCola() {
  // sin IndexedDB (modo privado, etc.) la cola funciona en memoria: se avisa en la barra
  const almacen = window.indexedDB ? ColaRegistro.almacenIndexedDB() : ColaRegistro.almacenMemoria();
  cola = new ColaRegistro.Cola(almacen, enviarItem, {
    alCambiar: async () => { cola.ultimosPendientes = (await cola.pendientes()).length; actualizarIndicador(); },
  });
  await cola.iniciar();
  cola.procesar();
}
function encolarJson(metodo, ruta, cuerpo) {
  return cola.encolar({ id: idCliente(), tipo: "json", metodo, ruta, cuerpo: Object.assign({ ts_cliente: ahora() }, cuerpo) });
}

// ── sesión ──────────────────────────────────────────────────────────────────
function pantallaLogin(mensaje) {
  titulo("Registro de pruebas");
  $("#btn-salir").classList.add("oculto");
  $("#btn-copia").classList.toggle("oculto", !cola);
  const u = h("input", { type: "text", autocomplete: "username", autocapitalize: "none" });
  const c = h("input", { type: "password", autocomplete: "current-password" });
  const err = h("p", { class: "error-texto" }, mensaje || "");
  const entrar = async () => {
    try {
      await api("POST", "/api/login", { usuario: u.value.trim(), clave: c.value });
      c.value = "";
      await arrancar();
    } catch (e) { err.textContent = e.message; }
  };
  vista(h("h1", null, "Ingreso"), h("label", null, "Usuario", u), h("label", null, "Contraseña", c), err,
        h("button", { class: "primario", onclick: entrar }, "Entrar"),
        h("p", { class: "nota" }, "Cada persona entra con su usuario. La sesión dura toda la jornada."));
}

function pantallaCambioClave() {
  titulo("Cambiar contraseña");
  const a = h("input", { type: "password" }), n = h("input", { type: "password" }), c = h("input", { type: "password" });
  const err = h("p", { class: "error-texto" });
  vista(h("h1", null, "Debe cambiar su contraseña"), h("label", null, "Contraseña actual", a),
        h("label", null, "Contraseña nueva (mínimo 10 caracteres)", n), h("label", null, "Confirmación", c), err,
        h("button", { class: "primario", onclick: async () => {
          try { await api("POST", "/api/cambiar_clave", { clave_actual: a.value, clave_nueva: n.value, confirmacion: c.value }); await arrancar(); }
          catch (e) { err.textContent = e.message; }
        } }, "Guardar"));
}

async function arrancar() {
  try { yo.usuario = await api("GET", "/api/yo"); }
  catch (e) { yo.usuario = null; return pantallaLogin(e.sesion ? "" : e.message); }
  if (yo.usuario.debe_cambiar) return pantallaCambioClave();
  $("#btn-salir").classList.remove("oculto");
  $("#btn-copia").classList.remove("oculto");
  if (!defs) defs = await api("GET", "/api/definiciones");
  if (cola && cola.pausada) await cola.reanudar();
  pantallaInicio();
}

// ── inicio: lista de registros ──────────────────────────────────────────────
async function pantallaInicio() {
  det = null;
  titulo("Mis registros");
  const lista = h("div");
  vista(h("div", { class: "fila" },
          h("button", { class: "primario", onclick: () => formularioCabecera(null) }, "Nuevo registro de campaña"),
          yo.usuario.rol === "admin" && h("button", { onclick: pantallaAdmin }, "Administración")),
        lista);
  try {
    const r = await api("GET", "/api/registros");
    if (!r.registros.length) lista.append(h("p", null, "Aún no hay registros. Cree el suyo para empezar."));
    for (const x of r.registros) {
      lista.append(h("button", { class: "item", onclick: () => abrirRegistro(x.id) },
        h("span", null, `#${x.id} · ${x.usuario} · ${(x.cabecera.serial || "sin serial")} · ${x.creado.slice(0, 10)}`),
        h("span", { class: "etq " + (x.estado === "cerrado" ? "na" : "sin") }, x.estado)));
    }
  } catch (e) { lista.append(h("p", { class: "error-texto" }, e.sesion ? "Sesión vencida" : e.message)); }
}

const CAMPOS_CAB = [
  ["equipo", "Equipo"], ["serial", "Serial del equipo"], ["version_software", "Versión de software"],
  ["commit", "Commit"], ["firmware", "Firmware"], ["id_tarjeta", "ID de la tarjeta"],
  ["perfil_instalacion", "Perfil de instalación"], ["programas", "Programas"],
  ["instrumentos", "Instrumentos (certificado y vigencia)"], ["fecha", "Fecha"], ["lugar", "Lugar"]];

function formularioCabecera(existente) {
  titulo(existente ? "Cabecera del registro" : "Nuevo registro");
  const campos = {};
  const filas = CAMPOS_CAB.map(([k, etq]) => {
    const largo = k === "programas" || k === "instrumentos";
    campos[k] = largo ? h("textarea", { value: (existente && existente[k]) || "" })
                      : h("input", { type: "text", value: (existente && existente[k]) || (k === "fecha" ? ahora().slice(0, 10) : "") });
    return h("label", null, etq, campos[k]);
  });
  const err = h("p", { class: "error-texto" });
  const valores = () => Object.fromEntries(CAMPOS_CAB.map(([k]) => [k, campos[k].value.trim()]));
  vista(h("h1", null, existente ? "Cabecera" : "Nuevo registro de campaña"), filas, err,
    h("div", { class: "fila" },
      h("button", { onclick: () => (existente ? abrirRegistro(det.id) : pantallaInicio()) }, "Cancelar"),
      h("button", { class: "primario", onclick: async () => {
        try {
          if (existente) {
            await encolarJson("PUT", `/api/registros/${det.id}/cabecera`, { cabecera: valores(), cliente_uuid: idCliente() });
            det.cabecera = valores();
            abrirRegistro(det.id, true);
          } else {
            const r = await api("POST", "/api/registros", { cabecera: valores(), ts_cliente: ahora(), cliente_uuid: idCliente() });
            abrirRegistro(r.id);
          }
        } catch (e) { err.textContent = e.message; }
      } }, "Guardar")));
}

// ── registro abierto: avance por bloque ─────────────────────────────────────
async function abrirRegistro(id, local) {
  if (!local) {
    try { det = await api("GET", `/api/registros/${id}`); }
    catch (e) { return e.sesion ? arrancar() : alert_(e.message); }
  }
  const snap = det.snapshot;
  titulo(`Registro #${det.id}`);
  const dueno = det.usuario === yo.usuario.usuario && det.estado === "abierto";
  const bloques = snap.bloques.map(([cod, nombre]) => {
    const ps = snap.pruebas.filter((p) => p.bloque === cod);
    const hechas = ps.filter((p) => (det.pruebas[p.id] || {}).resultado).length;
    return h("div", { class: "tarjeta" },
      h("h3", null, `${cod} — ${nombre}`),
      barraAvance(hechas, ps.length),
      h("p", { class: "nota" }, `${hechas} de ${ps.length} con resultado`),
      ps.map((p) => {
        const r = det.pruebas[p.id] || {};
        return h("button", { class: "item", onclick: () => abrirPrueba(p.id) },
          h("span", null, `${p.id} · ${p.titulo}`),
          h("span", { class: "etq " + (CLASE_RESULTADO[r.resultado] || "sin") }, NOMBRE_RESULTADO[r.resultado] || "pendiente"));
      }));
  });
  const nAn = Object.keys(det.anomalias).length;
  vista(
    h("p", null, `Ejecutor: ${det.usuario} · ${det.estado}${det.estado === "cerrado" ? " (sin cambios)" : ""}`),
    h("div", { class: "fila" },
      h("button", { onclick: pantallaInicio }, "← Registros"),
      h("button", { onclick: () => formularioCabecera(det.cabecera), disabled: !dueno }, "Cabecera"),
      h("button", { onclick: () => pantallaAnomalias(null) }, `Anomalías (${nAn})`)),
    bloques,
    h("div", { class: "fila" },
      h("a", { class: "boton", href: `/api/registros/${det.id}/exportar/html`, target: "_blank" }, "Exportar HTML"),
      h("a", { class: "boton", href: `/api/registros/${det.id}/exportar/json` }, "Exportar JSON"),
      h("a", { class: "boton", href: `/api/registros/${det.id}/exportar/csv` }, "Exportar CSV")),
    h("div", { class: "fila" },
      h("button", { onclick: verificarCadena }, "Verificar cadena de versiones"),
      h("button", { class: "primario", onclick: pantallaCierre, disabled: !dueno }, "Cerrar registro")));
}

async function verificarCadena() {
  try {
    const r = await api("GET", `/api/registros/${det.id}/verificar`);
    modal(h("h2", null, r.ok ? "Cadena ÍNTEGRA" : "Cadena ALTERADA"),
          h("p", null, `${r.versiones} versiones. Último hash:`), h("p", { class: "nota" }, r.ultimo_hash),
          r.errores.map((e) => h("p", { class: "error-texto" }, e)),
          h("button", { class: "primario", onclick: cerrarModal }, "Cerrar"));
  } catch (e) { alert_(e.message); }
}

// ── una prueba por pantalla ─────────────────────────────────────────────────
function barraAvance(hechas, total) {
  const relleno = h("div");
  relleno.style.width = (total ? (100 * hechas / total) : 0) + "%";
  return h("div", { class: "barra-avance", role: "progressbar", "aria-valuenow": hechas, "aria-valuemax": total }, relleno);
}

async function abrirPrueba(pid) {
  const snap = det.snapshot;
  const p = snap.pruebas.find((x) => x.id === pid);
  const idx = snap.pruebas.findIndex((x) => x.id === pid);
  const previo = det.pruebas[pid] || {};
  const dueno = det.usuario === yo.usuario.usuario && det.estado === "abierto";
  titulo(`${p.id} · ${p.titulo}`);
  const bor = {
    pasos: p.pasos.map((_, i) => !!(previo.pasos || [])[i]),
    valores: Object.entries(previo.valores || {}),
    resultado: previo.resultado || null, observaciones: previo.observaciones || "",
    firmaId: previo.firma_id || null, firmaNueva: null,
  };
  while (bor.valores.length < 3) bor.valores.push(["", ""]);

  // aviso del orden seguro (no bloquea)
  const falt = ((snap.requeridas_antes || {})[p.bloque] || []).filter((r) => (det.pruebas[r] || {}).resultado !== "aprobada");
  const aviso = falt.length ? h("div", { class: "tarjeta aviso" },
    h("b", null, "Orden seguro: "), `antes de esta prueba conviene aprobar ${falt.join(", ")}. Puede continuar bajo su criterio.`) : null;

  const pasos = p.pasos.map((txt, i) => h("label", { class: "paso" },
    h("input", { type: "checkbox", checked: bor.pasos[i] ? true : null, disabled: !dueno,
                 onchange: (e) => { bor.pasos[i] = e.target.checked; } }), h("span", null, txt)));
  const valores = bor.valores.map((par, i) => h("div", { class: "fila" },
    h("input", { type: "text", placeholder: "Dato (p. ej. presión)", value: par[0], disabled: !dueno, onchange: (e) => { bor.valores[i][0] = e.target.value; } }),
    h("input", { type: "text", placeholder: "Valor observado", value: par[1], disabled: !dueno, onchange: (e) => { bor.valores[i][1] = e.target.value; } })));
  const botonesRes = ["aprobada", "fallada", "no_aplica"].map((r) => {
    const b = h("button", { class: (r === "aprobada" ? "ok" : r === "fallada" ? "mal" : "") + (bor.resultado === r ? " elegido" : ""),
      disabled: !dueno, onclick: () => { bor.resultado = r; botonesRes.forEach((x) => x.classList.remove("elegido")); b.classList.add("elegido"); } },
      NOMBRE_RESULTADO[r]);
    return b;
  });
  const obs = h("textarea", { value: bor.observaciones, disabled: !dueno, onchange: (e) => { bor.observaciones = e.target.value; } });

  // fotos
  const miniaturas = h("div", { class: "miniaturas" });
  for (const ev of det.evidencias.filter((e) => e.tipo === "foto" && e.prueba_id === pid))
    miniaturas.append(h("img", { src: `/api/evidencias/${ev.id}`, alt: "Foto de evidencia" }));
  for (const url of (det.fotosLocales || {})[pid] || []) miniaturas.append(h("img", { src: url, alt: "Foto pendiente" }));
  const entradaFoto = h("input", { type: "file", accept: "image/*", capture: "environment", class: "oculto",
    onchange: async (e) => {
      for (const f of e.target.files) {
        const blob = await reducirImagen(f);
        const cid = idCliente(), url = URL.createObjectURL(blob);
        ((det.fotosLocales = det.fotosLocales || {})[pid] = (det.fotosLocales[pid] || [])).push(url);
        miniaturas.append(h("img", { src: url, alt: "Foto pendiente" }));
        await cola.encolar({ id: idCliente(), tipo: "foto", metodo: "POST", ruta: `/api/registros/${det.id}/pruebas/${pid}/fotos`,
          archivo: blob, cliente_id: cid, ts_cliente: ahora() });
      }
      e.target.value = "";
    } });

  const estadoFirma = h("p", { class: "nota" }, bor.firmaId ? "Firmada por " + (previo.usuario || "usted") : "Sin firma: se pide al guardar el resultado");
  const guardar = async () => {
    if (!dueno) return;
    const cambio = JSON.stringify([bor.pasos, bor.valores.filter((v) => v[0] || v[1]), bor.resultado, bor.observaciones.trim()]) !==
                   JSON.stringify([previo.pasos || [], Object.entries(previo.valores || {}), previo.resultado || null, (previo.observaciones || "")]);
    const necesitaMotivo = previo.resultado && previo.firma_id && cambio;
    const motivo = necesitaMotivo ? await pedirTexto("Motivo del cambio", "Esta prueba ya estaba firmada: indique por qué la modifica.") : "";
    if (necesitaMotivo && !motivo) return;
    let firmaId = bor.firmaId;
    if (bor.resultado && (!firmaId || cambio)) {
      const png = await pedirFirma(`Firma de ${yo.usuario.usuario} — ${p.id}: ${NOMBRE_RESULTADO[bor.resultado]}`);
      if (!png) return;
      firmaId = idCliente();
      await cola.encolar({ id: idCliente(), tipo: "json", metodo: "POST", ruta: `/api/registros/${det.id}/pruebas/${pid}/firma`,
        cuerpo: { cliente_id: firmaId, png_base64: png, ts_cliente: ahora() } });
    }
    const datos = { pasos: bor.pasos, valores: Object.fromEntries(bor.valores.filter((v) => v[0].trim()).map((v) => [v[0].trim(), v[1].trim()])),
      resultado: bor.resultado, observaciones: bor.observaciones.trim(), firma_id: bor.resultado ? firmaId : null };
    await encolarJson("PUT", `/api/registros/${det.id}/pruebas/${pid}`, { datos, motivo, cliente_uuid: idCliente() });
    det.pruebas[pid] = Object.assign({}, previo, datos, { usuario: yo.usuario.usuario });
    if (idx + 1 < snap.pruebas.length) abrirPrueba(snap.pruebas[idx + 1].id); else abrirRegistro(det.id, true);
  };
  vista(
    h("div", { class: "fila" }, h("button", { onclick: () => abrirRegistro(det.id, true) }, "← Pruebas"),
      h("button", { onclick: () => idx > 0 && abrirPrueba(snap.pruebas[idx - 1].id), disabled: idx === 0 }, "Anterior"),
      h("button", { onclick: () => idx + 1 < snap.pruebas.length && abrirPrueba(snap.pruebas[idx + 1].id), disabled: idx + 1 >= snap.pruebas.length }, "Siguiente")),
    h("p", { class: "nota" }, `Prueba ${idx + 1} de ${snap.pruebas.length} · bloque ${p.bloque} · ${p.modo === "seco" ? "en seco" : "en operación"}`),
    aviso,
    h("h2", null, "Objetivo"), h("p", null, p.objetivo), h("h2", null, "Precondiciones"), h("p", null, p.pre),
    h("h2", null, "Pasos"), pasos,
    h("h2", null, "Esperado"), h("p", null, p.esperado), h("h2", null, "Criterio"), h("p", null, p.criterio),
    h("h2", null, "Valores observados"), valores,
    h("h2", null, "Resultado"), h("div", { class: "fila" }, botonesRes),
    h("h2", null, "Observaciones"), obs,
    h("h2", null, "Fotos"), miniaturas,
    h("div", { class: "fila" }, h("button", { onclick: () => entradaFoto.click(), disabled: !dueno }, "Tomar foto"), entradaFoto),
    estadoFirma,
    h("div", { class: "fila" },
      h("button", { onclick: () => pantallaAnomalias(pid), disabled: !dueno }, "Abrir anomalía"),
      h("button", { class: "primario", onclick: guardar, disabled: !dueno }, "Guardar y siguiente")),
    !dueno && h("p", { class: "nota" }, "Solo lectura: este registro no es suyo o ya está cerrado."));
}

async function reducirImagen(archivo) {
  const MAX = 1600;
  const url = URL.createObjectURL(archivo);
  try {
    const img = await new Promise((ok, mal) => { const i = new Image(); i.onload = () => ok(i); i.onerror = mal; i.src = url; });
    const k = Math.min(1, MAX / Math.max(img.naturalWidth, img.naturalHeight));
    const c = document.createElement("canvas");
    c.width = Math.round(img.naturalWidth * k); c.height = Math.round(img.naturalHeight * k);
    c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
    return await new Promise((ok) => c.toBlob((b) => ok(b), "image/jpeg", 0.8));
  } finally { URL.revokeObjectURL(url); }
}

// ── modales: texto, firma ───────────────────────────────────────────────────
function modal(...nodos) { const m = $("#modal"); m.replaceChildren(h("div", { class: "caja" }, ...planos(nodos))); m.classList.remove("oculto"); }
function cerrarModal() { $("#modal").classList.add("oculto"); $("#modal").replaceChildren(); }
function alert_(texto) { modal(h("p", { class: "error-texto" }, texto), h("button", { class: "primario", onclick: cerrarModal }, "Entendido")); }

function pedirTexto(titulo_, ayuda) {
  return new Promise((ok) => {
    const t = h("textarea");
    modal(h("h2", null, titulo_), h("p", null, ayuda), t, h("div", { class: "fila" },
      h("button", { onclick: () => { cerrarModal(); ok(""); } }, "Cancelar"),
      h("button", { class: "primario", onclick: () => { const v = t.value.trim(); if (v) { cerrarModal(); ok(v); } } }, "Aceptar")));
  });
}

function pedirFirma(etiqueta) {
  return new Promise((ok) => {
    const c = h("canvas", { class: "firma", width: 800, height: 440 });
    const g = c.getContext("2d");
    g.lineWidth = 6; g.lineCap = "round"; g.strokeStyle = "#000";
    let dibujando = false, trazos = 0;
    const pos = (e) => { const r = c.getBoundingClientRect(); return [(e.clientX - r.left) * c.width / r.width, (e.clientY - r.top) * c.height / r.height]; };
    c.addEventListener("pointerdown", (e) => { dibujando = true; trazos += 1; c.setPointerCapture(e.pointerId); g.beginPath(); g.moveTo(...pos(e)); });
    c.addEventListener("pointermove", (e) => { if (dibujando) { g.lineTo(...pos(e)); g.stroke(); } });
    const fin = () => { dibujando = false; };
    c.addEventListener("pointerup", fin); c.addEventListener("pointercancel", fin);
    const err = h("p", { class: "error-texto" });
    modal(h("h2", null, "Firma en pantalla"), h("p", null, etiqueta), c, err, h("div", { class: "fila" },
      h("button", { onclick: () => { cerrarModal(); ok(null); } }, "Cancelar"),
      h("button", { onclick: () => { g.clearRect(0, 0, c.width, c.height); trazos = 0; } }, "Borrar"),
      h("button", { class: "primario", onclick: () => {
        if (!trazos) { err.textContent = "Firme en el recuadro."; return; }
        const r = document.createElement("canvas"); r.width = 400; r.height = 220;      // PNG pequeño
        r.getContext("2d").drawImage(c, 0, 0, r.width, r.height);
        cerrarModal(); ok(r.toDataURL("image/png").split(",")[1]);
      } }, "Aceptar firma")));
  });
}

// ── anomalías ───────────────────────────────────────────────────────────────
function pantallaAnomalias(pidInicial) {
  titulo("Anomalías");
  const dueno = det.usuario === yo.usuario.usuario && det.estado === "abierto";
  const lista = Object.entries(det.anomalias).sort().map(([id, a]) =>
    h("button", { class: "item", onclick: () => formularioAnomalia(id, a) },
      h("span", null, `${id} · ${a.prueba_id || "—"} · ${a.descripcion.slice(0, 60)}`), h("span", { class: "etq sin" }, `${a.gravedad} · ${a.estado}`)));
  vista(h("div", { class: "fila" }, h("button", { onclick: () => abrirRegistro(det.id, true) }, "← Registro"),
        h("button", { class: "primario", disabled: !dueno, onclick: () => formularioAnomalia(null, { prueba_id: pidInicial || "" }) }, "Nueva anomalía")),
        lista.length ? lista : h("p", null, "Sin anomalías registradas."));
  if (pidInicial && dueno) formularioAnomalia(null, { prueba_id: pidInicial });
}

function formularioAnomalia(id, a) {
  const f = {
    prueba_id: h("select", null, h("option", { value: "" }, "(ninguna)"), det.snapshot.pruebas.map((p) => h("option", { value: p.id, selected: p.id === a.prueba_id ? true : null }, p.id))),
    descripcion: h("textarea", { value: a.descripcion || "" }),
    gravedad: h("select", null, ["seguridad", "funcional", "cosmetica"].map((g) => h("option", { value: g, selected: g === a.gravedad ? true : null }, g))),
    accion: h("textarea", { value: a.accion || "" }), responsable: h("input", { type: "text", value: a.responsable || "" }),
    estado: h("select", null, ["abierta", "en_analisis", "corregida", "cerrada"].map((g) => h("option", { value: g, selected: g === a.estado ? true : null }, g))),
    reensayo: h("input", { type: "text", value: a.reensayo || "" }),
  };
  const err = h("p", { class: "error-texto" });
  modal(h("h2", null, id ? `Anomalía ${id}` : "Nueva anomalía"),
    h("label", null, "Prueba", f.prueba_id), h("label", null, "Descripción", f.descripcion), h("label", null, "Gravedad", f.gravedad),
    h("label", null, "Acción", f.accion), h("label", null, "Responsable", f.responsable), h("label", null, "Estado", f.estado),
    h("label", null, "Reensayo", f.reensayo), err,
    h("div", { class: "fila" }, h("button", { onclick: cerrarModal }, "Cancelar"),
      h("button", { class: "primario", onclick: async () => {
        const datos = Object.fromEntries(Object.entries(f).map(([k, e]) => [k, e.value.trim()]));
        if (!datos.descripcion) { err.textContent = "Escriba la descripción."; return; }
        let motivo = "";
        if (id) { motivo = await pedirTexto("Motivo del cambio", "Indique qué cambió en la anomalía."); if (!motivo) return; }
        await encolarJson(id ? "PUT" : "POST", id ? `/api/registros/${det.id}/anomalias/${id}` : `/api/registros/${det.id}/anomalias`,
          { datos, motivo, cliente_uuid: idCliente() });
        det.anomalias[id || "AN-?" + Object.keys(det.anomalias).length] = datos;
        cerrarModal(); pantallaAnomalias(null);
      } }, "Guardar")));
}

// ── cierre ──────────────────────────────────────────────────────────────────
async function pantallaCierre() {
  const faltan = det.snapshot.pruebas.filter((p) => !(det.pruebas[p.id] || {}).resultado).map((p) => p.id);
  titulo("Cerrar registro");
  vista(h("h1", null, "Cerrar el registro"),
    h("p", null, "Al cerrar queda firmado y ya no admite cambios (solo se exporta)."),
    faltan.length ? h("div", { class: "tarjeta aviso" }, `Pruebas sin resultado (${faltan.length}): ${faltan.join(", ")}`) : h("p", null, "Todas las pruebas tienen resultado."),
    h("div", { class: "fila" }, h("button", { onclick: () => abrirRegistro(det.id, true) }, "Cancelar"),
      h("button", { class: "primario", onclick: async () => {
        const png = await pedirFirma(`Firma final de ${yo.usuario.usuario}`);
        if (!png) return;
        const firmaId = idCliente();
        await cola.encolar({ id: idCliente(), tipo: "json", metodo: "POST", ruta: `/api/registros/${det.id}/pruebas/cierre/firma`,
          cuerpo: { cliente_id: firmaId, png_base64: png, ts_cliente: ahora() } });
        await encolarJson("POST", `/api/registros/${det.id}/cerrar`, { firma_id: firmaId, confirmar_incompleto: faltan.length > 0, cliente_uuid: idCliente() });
        det.estado = "cerrado";
        abrirRegistro(det.id, true);
      } }, "Firmar y cerrar")));
}

// ── administración ──────────────────────────────────────────────────────────
async function pantallaAdmin() {
  titulo("Administración");
  const cuerpo = h("div");
  vista(h("div", { class: "fila" }, h("button", { onclick: pantallaInicio }, "← Inicio"),
        h("button", { onclick: async () => { try { const r = await api("POST", "/api/admin/respaldo"); alert_("Respaldo creado: " + r.archivo); } catch (e) { alert_(e.message); } } }, "Respaldar base")),
        cuerpo);
  try {
    const [us, con] = await Promise.all([api("GET", "/api/admin/usuarios"), api("GET", "/api/admin/consolidacion")]);
    const nuevoU = h("input", { type: "text", placeholder: "usuario" }), nuevoN = h("input", { type: "text", placeholder: "nombre" });
    const clave = h("p", { class: "nota" });
    cuerpo.append(h("h2", null, "Usuarios"),
      h("table", null, h("tr", null, ["Usuario", "Rol", "Activo", ""].map((x) => h("th", null, x))),
        us.usuarios.map((u) => h("tr", null, h("td", null, u.usuario), h("td", null, u.rol), h("td", null, u.activo ? "sí" : "no"),
          h("td", null, h("button", { onclick: async () => { const r = await api("POST", `/api/admin/usuarios/${u.usuario}/clave`); clave.textContent = `Clave temporal de ${u.usuario}: ${r.clave_temporal} (se muestra una vez)`; } }, "Nueva clave"),
            h("button", { onclick: async () => { try { await api("POST", `/api/admin/usuarios/${u.usuario}/activo`, { activo: !u.activo }); pantallaAdmin(); } catch (e) { alert_(e.message); } } }, u.activo ? "Desactivar" : "Activar"))))),
      h("div", { class: "fila" }, nuevoU, nuevoN, h("button", { class: "primario", onclick: async () => {
        try { const r = await api("POST", "/api/admin/usuarios", { usuario: nuevoU.value.trim(), nombre: nuevoN.value.trim(), rol: "ejecutor" });
          clave.textContent = `Clave temporal de ${nuevoU.value.trim()}: ${r.clave_temporal} (se muestra una vez; deberá cambiarla)`; } catch (e) { alert_(e.message); } } }, "Crear ejecutor")),
      clave,
      h("h2", null, `Consolidación (${con.discrepancias.length} discrepancias)`),
      h("table", null, h("tr", null, h("th", null, "Prueba"), con.registros.map((r) => h("th", null, `#${r.id} ${r.usuario}`))),
        con.pruebas.map((p) => h("tr", { class: p.discrepancia ? "discrepancia" : "" }, h("td", null, `${p.prueba_id} ${p.titulo}`),
          p.ejecutores.map((e) => h("td", null, NOMBRE_RESULTADO[e.resultado] || "—"))))),
      h("h2", null, "Registros"), (await api("GET", "/api/registros")).registros.map((r) =>
        h("button", { class: "item", onclick: () => abrirRegistro(r.id) }, h("span", null, `#${r.id} · ${r.usuario} · ${r.estado}`))));
  } catch (e) { cuerpo.append(h("p", { class: "error-texto" }, e.message)); }
}

// ── arranque ────────────────────────────────────────────────────────────────
$("#btn-salir").addEventListener("click", async () => {
  try { await api("POST", "/api/logout"); } catch (e) { /* */ }
  yo.usuario = null; defs = null; pantallaLogin("");
});
$("#btn-copia").addEventListener("click", async () => {
  const texto = await cola.copia();
  const a = h("a", { href: URL.createObjectURL(new Blob([texto], { type: "application/json" })), download: `copia_pendientes_${ahora().slice(0, 10)}.json` });
  document.body.append(a); a.click(); a.remove();
});
(async function () {
  try { await iniciarCola(); } catch (e) { console.error("IndexedDB no disponible", e); }
  await arrancar();
})();

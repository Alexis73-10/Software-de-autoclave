/* cola.js — cola de pendientes de envío (F1, tanda 3).
 *
 * El Wi-Fi local por HTTP no es contexto seguro: NO hay service worker ni PWA.
 * Cada guardado va primero a la cola (IndexedDB en el navegador) y se envía en
 * segundo plano, en orden (una firma o foto debe llegar antes de la versión que
 * la usa), con reintento y espera creciente. Un guardado que el servidor
 * rechaza de forma definitiva (4xx) pasa a "rechazados" y no bloquea el resto;
 * una sesión vencida (401) pausa la cola hasta volver a iniciar sesión.
 * El servidor es idempotente por `cliente_uuid`/`cliente_id`: reenviar un
 * guardado que sí llegó no lo duplica.
 *
 * La lógica es independiente del navegador (se prueba con node): recibe un
 * `almacen` {todos, agregar, quitar, guardar} y una función `enviar(item)`.
 */
(function (raiz) {
  "use strict";

  const ESPERA_MIN_MS = 1000;
  const ESPERA_MAX_MS = 30000;

  function almacenMemoria() {
    const items = new Map();
    return {
      async todos() { return [...items.values()].sort((a, b) => a.orden - b.orden); },
      async agregar(item) { items.set(item.id, item); },
      async guardar(item) { items.set(item.id, item); },
      async quitar(id) { items.delete(id); },
    };
  }

  function almacenIndexedDB(nombre) {
    const abrir = () => new Promise((ok, mal) => {
      const r = indexedDB.open(nombre || "registro_pruebas_cola", 1);
      r.onupgradeneeded = () => r.result.createObjectStore("items", { keyPath: "id" });
      r.onsuccess = () => ok(r.result);
      r.onerror = () => mal(r.error);
    });
    const tx = async (modo, fn) => {
      const db = await abrir();
      return new Promise((ok, mal) => {
        const t = db.transaction("items", modo);
        const res = fn(t.objectStore("items"));
        t.oncomplete = () => { db.close(); ok(res && res.result); };
        t.onerror = () => { db.close(); mal(t.error); };
      });
    };
    return {
      async todos() { const l = await tx("readonly", (s) => s.getAll()); return (l || []).sort((a, b) => a.orden - b.orden); },
      async agregar(item) { await tx("readwrite", (s) => s.put(item)); },
      async guardar(item) { await tx("readwrite", (s) => s.put(item)); },
      async quitar(id) { await tx("readwrite", (s) => s.delete(id)); },
    };
  }

  class Cola {
    /**
     * @param almacen  {todos, agregar, guardar, quitar}
     * @param enviar   async (item) => {estado: "ok"|"red"|"sesion"|"rechazo", motivo?}
     * @param opciones {esperar(ms), alCambiar(), reloj()}
     */
    constructor(almacen, enviar, opciones) {
      this.almacen = almacen;
      this.enviar = enviar;
      this.opciones = opciones || {};
      this.esperar = this.opciones.esperar || ((ms) => new Promise((r) => setTimeout(r, ms)));
      this.alCambiar = this.opciones.alCambiar || (() => {});
      this.procesando = false;
      this.pausada = false;           // sesión vencida
      this.espera = ESPERA_MIN_MS;
      this.siguienteOrden = 0;
      this.temporizador = null;
    }

    async iniciar() {
      const todos = await this.almacen.todos();
      this.siguienteOrden = todos.reduce((m, i) => Math.max(m, i.orden), 0) + 1;
      this.alCambiar();
    }

    async encolar(item) {
      item = Object.assign({}, item, { orden: this.siguienteOrden++, estado: "pendiente", intentos: 0 });
      await this.almacen.agregar(item);
      this.alCambiar();
      if (this.opciones.autoprocesar !== false) this.procesar();   // en segundo plano
      return item;
    }

    async pendientes() { return (await this.almacen.todos()).filter((i) => i.estado === "pendiente"); }
    async rechazados() { return (await this.almacen.todos()).filter((i) => i.estado === "rechazado"); }
    async todo() { return this.almacen.todos(); }

    reanudar() { this.pausada = false; this.espera = ESPERA_MIN_MS; return this.procesar(); }

    /** Envía en orden hasta vaciar la cola o hasta un fallo de red / sesión. */
    async procesar() {
      if (this.procesando || this.pausada) return;
      this.procesando = true;
      try {
        for (;;) {
          const pend = await this.pendientes();
          if (!pend.length) { this.espera = ESPERA_MIN_MS; break; }
          const item = pend[0];
          let r;
          try { r = await this.enviar(item); } catch (e) { r = { estado: "red", motivo: String(e) }; }
          if (r.estado === "ok") {
            await this.almacen.quitar(item.id);
            this.espera = ESPERA_MIN_MS;
          } else if (r.estado === "rechazo") {
            item.estado = "rechazado"; item.motivo = r.motivo || "Rechazado por el servidor";
            await this.almacen.guardar(item);          // se conserva para revisarlo y en la copia JSON
          } else if (r.estado === "sesion") {
            this.pausada = true; this.alCambiar(); break;
          } else {                                      // red caída o error 5xx: reintentar luego
            item.intentos += 1; item.ultimoError = r.motivo || "Sin red";
            await this.almacen.guardar(item);
            this.alCambiar();
            this.programarReintento();
            break;
          }
          this.alCambiar();
        }
      } finally {
        this.procesando = false;
        this.alCambiar();
      }
    }

    programarReintento() {
      if (this.temporizador || this.opciones.sinTemporizador) return;
      const ms = this.espera;
      this.espera = Math.min(this.espera * 2, ESPERA_MAX_MS);
      this.temporizador = setTimeout(() => { this.temporizador = null; this.procesar(); }, ms);
    }

    /** Copia de todo lo pendiente y rechazado, para "Descargar copia (JSON)". */
    async copia() {
      const todos = await this.almacen.todos();
      return JSON.stringify({ generado: new Date().toISOString(), pendientes: todos.map((i) => {
        const c = Object.assign({}, i);
        if (c.archivo) c.archivo = "(archivo binario: " + (c.archivo.size || "?") + " bytes; reenviar desde el teléfono)";
        return c;
      }) }, null, 2);
    }
  }

  const api = { Cola, almacenMemoria, almacenIndexedDB, ESPERA_MIN_MS, ESPERA_MAX_MS };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else raiz.ColaRegistro = api;
})(typeof window !== "undefined" ? window : globalThis);

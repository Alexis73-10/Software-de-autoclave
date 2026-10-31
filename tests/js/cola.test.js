// Pruebas de la cola de pendientes (F1, tanda 3): node --test tests/js/cola.test.js
const test = require("node:test");
const assert = require("node:assert");
const path = require("node:path");
const { Cola, almacenMemoria } = require(path.join(__dirname, "..", "..", "tools", "registro_pruebas", "static", "cola.js"));

function nueva(enviar, extra) {
  const cola = new Cola(almacenMemoria(), enviar, Object.assign({ sinTemporizador: true, autoprocesar: false }, extra || {}));
  return cola;
}

test("envía en orden FIFO (la firma antes de la versión que la usa)", async () => {
  const enviados = [];
  const cola = nueva(async (i) => { enviados.push(i.tipo); return { estado: "ok" }; });
  await cola.iniciar();
  await cola.encolar({ id: "a", tipo: "firma" });
  await cola.encolar({ id: "b", tipo: "prueba" });
  await cola.procesar();
  assert.deepStrictEqual(enviados, ["firma", "prueba"]);
  assert.strictEqual((await cola.pendientes()).length, 0);
});

test("con la red cortada conserva los pendientes y los reintenta al volver", async () => {
  let hayRed = false;
  const enviados = [];
  const cola = nueva(async (i) => {
    if (!hayRed) return { estado: "red", motivo: "sin red" };
    enviados.push(i.id);
    return { estado: "ok" };
  });
  await cola.iniciar();
  await cola.encolar({ id: "1", tipo: "prueba" });
  await cola.encolar({ id: "2", tipo: "foto" });
  await cola.procesar();
  assert.strictEqual((await cola.pendientes()).length, 2);       // nada se pierde
  assert.strictEqual((await cola.pendientes())[0].intentos >= 1, true);
  hayRed = true;
  await cola.procesar();
  assert.deepStrictEqual(enviados, ["1", "2"]);                  // y en el mismo orden
  assert.strictEqual((await cola.pendientes()).length, 0);
});

test("un fallo de red a mitad conserva el resto en orden", async () => {
  let llamadas = 0;
  const cola = nueva(async (i) => { llamadas += 1; return llamadas === 2 ? { estado: "red" } : { estado: "ok" }; });
  await cola.iniciar();
  for (const id of ["x", "y", "z"]) await cola.encolar({ id, tipo: "prueba" });
  await cola.procesar();
  assert.deepStrictEqual((await cola.pendientes()).map((i) => i.id), ["y", "z"]);
});

test("un rechazo definitivo no bloquea al resto y queda en rechazados", async () => {
  const cola = nueva(async (i) => (i.id === "mala" ? { estado: "rechazo", motivo: "422 resultado inválido" } : { estado: "ok" }));
  await cola.iniciar();
  await cola.encolar({ id: "mala", tipo: "prueba" });
  await cola.encolar({ id: "buena", tipo: "prueba" });
  await cola.procesar();
  assert.strictEqual((await cola.pendientes()).length, 0);
  const r = await cola.rechazados();
  assert.strictEqual(r.length, 1);
  assert.strictEqual(r[0].motivo, "422 resultado inválido");
});

test("la sesión vencida pausa la cola hasta reanudar", async () => {
  let sesion = false;
  const cola = nueva(async () => (sesion ? { estado: "ok" } : { estado: "sesion" }));
  await cola.iniciar();
  await cola.encolar({ id: "1", tipo: "prueba" });
  await cola.procesar();
  assert.strictEqual(cola.pausada, true);
  assert.strictEqual((await cola.pendientes()).length, 1);
  sesion = true;
  await cola.procesar();                                          // pausada: no hace nada
  assert.strictEqual((await cola.pendientes()).length, 1);
  await cola.reanudar();
  assert.strictEqual((await cola.pendientes()).length, 0);
});

test("la espera de reintento crece y tiene tope", async () => {
  const cola = new Cola(almacenMemoria(), async () => ({ estado: "red" }), { sinTemporizador: false, autoprocesar: false });
  await cola.iniciar();
  const esperas = [];
  const original = global.setTimeout;
  global.setTimeout = (fn, ms) => { esperas.push(ms); return 0; };
  try {
    for (let i = 0; i < 8; i++) { cola.temporizador = null; cola.programarReintento(); }
  } finally { global.setTimeout = original; }
  assert.deepStrictEqual(esperas.slice(0, 5), [1000, 2000, 4000, 8000, 16000]);
  assert.strictEqual(Math.max(...esperas), 30000);
});

test("el indicador cuenta los pendientes y avisa los cambios", async () => {
  let cambios = 0;
  const cola = nueva(async () => ({ estado: "red" }), { alCambiar: () => { cambios += 1; } });
  await cola.iniciar();
  await cola.encolar({ id: "1", tipo: "prueba" });
  await cola.encolar({ id: "2", tipo: "prueba" });
  assert.strictEqual((await cola.pendientes()).length, 2);
  assert.ok(cambios >= 2);
});

test("la copia JSON incluye pendientes y rechazados", async () => {
  const cola = nueva(async (i) => (i.id === "r" ? { estado: "rechazo", motivo: "x" } : { estado: "red" }));
  await cola.iniciar();
  await cola.encolar({ id: "r", tipo: "prueba", cuerpo: { a: 1 } });
  await cola.encolar({ id: "p", tipo: "foto", archivo: { size: 1234 } });
  await cola.procesar();
  const copia = JSON.parse(await cola.copia());
  assert.deepStrictEqual(copia.pendientes.map((i) => [i.id, i.estado]), [["r", "rechazado"], ["p", "pendiente"]]);
  assert.ok(copia.pendientes[1].archivo.includes("1234"));
});

test("el orden continúa tras reabrir la página (pendientes de antes)", async () => {
  const almacen = almacenMemoria();
  const c1 = new Cola(almacen, async () => ({ estado: "red" }), { sinTemporizador: true, autoprocesar: false });
  await c1.iniciar();
  await c1.encolar({ id: "vieja", tipo: "prueba" });
  const enviados = [];
  const c2 = new Cola(almacen, async (i) => { enviados.push(i.id); return { estado: "ok" }; }, { sinTemporizador: true, autoprocesar: false });
  await c2.iniciar();
  await c2.encolar({ id: "nueva", tipo: "prueba" });
  await c2.procesar();
  assert.deepStrictEqual(enviados, ["vieja", "nueva"]);
});

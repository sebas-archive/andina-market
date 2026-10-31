// Interfaz web de AndinaMarket: consume la API del gateway (mismo origen).
// El catálogo de la demo es pequeño (20 productos), así que se carga completo y los filtros,
// el orden y los conteos se calculan en el navegador; la búsqueda por texto sí va a la API.
const CATEGORIAS = [
  { valor: "tecnologia", etiqueta: "Tecnología" },
  { valor: "hogar", etiqueta: "Hogar" },
  { valor: "moda", etiqueta: "Moda" },
  { valor: "deportes", etiqueta: "Deportes" },
];
const PASO_PRECIO = 10000;

const estado = {
  token: sessionStorage.getItem("token"),
  usuario: null,
  q: "",
  catalogo: [],             // resultado de la búsqueda actual
  productos: new Map(),     // id -> producto, para el carrito y los pedidos
  limites: [0, 0],          // rango de precio del catálogo
  filtros: { categorias: [], precio: [0, 0], soloStock: false },
  orden: "destacados",
  carrito: new Map(),       // id -> cantidad
  pedidoActual: null,
  modoSesion: "login",
};

const $ = (id) => document.getElementById(id);
const pesos = (n) => "$ " + Math.round(n).toLocaleString("es-CO");
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const etiquetaCategoria = (valor) => CATEGORIAS.find((c) => c.valor === valor)?.etiqueta ?? "General";

// ---------- API ----------
async function api(ruta, opciones = {}) {
  const cabeceras = { ...(opciones.headers || {}) };
  if (opciones.body) cabeceras["Content-Type"] = "application/json";
  if (estado.token) cabeceras.Authorization = `Bearer ${estado.token}`;
  const r = await fetch(ruta, { ...opciones, headers: cabeceras });
  const cuerpo = await r.json().catch(() => ({}));
  if (!r.ok) {
    if (r.status === 401 && estado.token && !ruta.endsWith("/login")) cerrarSesion("Tu sesión venció; inicia sesión de nuevo.");
    throw Object.assign(new Error(cuerpo.detalle || `Error ${r.status}`), { status: r.status, codigo: cuerpo.error });
  }
  return cuerpo;
}

function avisar(texto, esError = false) {
  const aviso = $("aviso");
  aviso.textContent = texto;
  aviso.classList.toggle("error-aviso", esError);
  aviso.hidden = false;
  clearTimeout(avisar.t);
  avisar.t = setTimeout(() => (aviso.hidden = true), 3500);
}

// ---------- Filtros ----------
function coincide(p, filtros, ignorarCategoria = false) {
  return (ignorarCategoria || !filtros.categorias.length || filtros.categorias.includes(p.categoria)) &&
    p.precio >= filtros.precio[0] && p.precio <= filtros.precio[1] &&
    (!filtros.soloStock || p.stock > 0);
}

function ordenar(lista) {
  const copia = [...lista];
  if (estado.orden === "precio-asc") copia.sort((a, b) => a.precio - b.precio);
  if (estado.orden === "precio-desc") copia.sort((a, b) => b.precio - a.precio);
  if (estado.orden === "nombre") copia.sort((a, b) => a.nombre.localeCompare(b.nombre, "es"));
  return copia;
}

function filtrosActivos() {
  const f = estado.filtros, [min, max] = estado.limites;
  return [
    ...f.categorias.map((c) => ({ clave: c, etiqueta: etiquetaCategoria(c), quitar: () => (f.categorias = f.categorias.filter((x) => x !== c)) })),
    ...(f.precio[0] !== min || f.precio[1] !== max
      ? [{ clave: "precio", etiqueta: `${pesos(f.precio[0])} a ${pesos(f.precio[1])}`, quitar: () => (f.precio = [min, max]) }]
      : []),
    ...(f.soloStock ? [{ clave: "stock", etiqueta: "Con stock", quitar: () => (f.soloStock = false) }] : []),
    ...(estado.q ? [{ clave: "q", etiqueta: `«${estado.q}»`, quitar: () => { estado.q = ""; $("busqueda").value = ""; return "recargar"; } }] : []),
  ];
}

function limpiarFiltros() {
  estado.filtros = { categorias: [], precio: [...estado.limites], soloStock: false };
  const habiaBusqueda = Boolean(estado.q);
  estado.q = ""; $("busqueda").value = "";
  habiaBusqueda ? cargarCatalogo() : pintarTodo();
}

function pintarFiltros() {
  const f = estado.filtros;
  $("lista-categorias").replaceChildren(...CATEGORIAS.map((c) => {
    const n = estado.catalogo.filter((p) => p.categoria === c.valor && coincide(p, f, true)).length;
    const marcado = f.categorias.includes(c.valor);
    const etiqueta = document.createElement("label");
    etiqueta.className = "opcion" + (n === 0 && !marcado ? " deshabilitada" : "");
    etiqueta.innerHTML = `<input type="checkbox" ${marcado ? "checked" : ""} ${n === 0 && !marcado ? "disabled" : ""}><span>${c.etiqueta}</span><span class="n">${n}</span>`;
    etiqueta.querySelector("input").addEventListener("change", () => {
      f.categorias = marcado ? f.categorias.filter((x) => x !== c.valor) : [...f.categorias, c.valor];
      pintarTodo();
    });
    return etiqueta;
  }));

  const [min, max] = estado.limites;
  for (const [id, valor] of [["precio-min", f.precio[0]], ["precio-max", f.precio[1]]]) {
    Object.assign($(id), { min, max, step: PASO_PRECIO, value: valor });
  }
  const pct = (v) => (max === min ? 0 : ((v - min) / (max - min)) * 100);
  $("rango-relleno").style.left = pct(f.precio[0]) + "%";
  $("rango-relleno").style.width = pct(f.precio[1]) - pct(f.precio[0]) + "%";
  $("valor-min").textContent = pesos(f.precio[0]);
  $("valor-max").textContent = pesos(f.precio[1]);
  $("solo-stock").setAttribute("aria-checked", String(f.soloStock));
}

function pintarActivos() {
  const activos = filtrosActivos();
  const lista = $("activos");
  lista.hidden = !activos.length;
  lista.replaceChildren(...activos.map((a) => {
    const li = document.createElement("li");
    li.innerHTML = `<span class="chip-activo"><span></span><button aria-label="Quitar filtro">×</button></span>`;
    li.querySelector("span span").textContent = a.etiqueta;
    li.querySelector("button").addEventListener("click", () => (a.quitar() === "recargar" ? cargarCatalogo() : pintarTodo()));
    return li;
  }));
  if (activos.length) {
    const li = document.createElement("li");
    li.innerHTML = `<button class="enlace">Limpiar todo</button>`;
    li.querySelector("button").addEventListener("click", limpiarFiltros);
    lista.append(li);
  }
  const n = activos.length;
  $("cuenta-activos").textContent = n ? `(${n})` : "";
  $("limpiar-filtros").disabled = $("limpiar-filtros-movil").disabled = !n;
}

// ---------- Catálogo ----------
// Productos sin foto: ícono neutro sobre el tono de su categoría.
const ICONO_SIN_FOTO = `<svg aria-hidden="true" viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="m21 16-5-5-9 9"/></svg>`;

function arte(p, clase = "") {
  return p.imagen_url
    ? `<img alt="${esc(p.nombre)}" loading="lazy" src="${esc(p.imagen_url)}" class="${clase}">`
    : `<div class="arte arte-${CATEGORIAS.some((c) => c.valor === p.categoria) ? p.categoria : "general"} ${clase}" role="img" aria-label="Sin foto">${ICONO_SIN_FOTO}</div>`;
}

function tarjeta(p, i) {
  const el = document.createElement("article");
  el.className = "tarjeta cambiar" + (p.stock === 0 ? " agotada" : "");
  el.style.animationDelay = Math.min(i, 8) * 45 + "ms";
  const insignia = p.stock === 0 ? `<span class="insignia">Agotado</span>`
    : p.stock !== null && p.stock < 10 ? `<span class="insignia bajo">Últimas ${p.stock}</span>` : "";
  const stock = p.stock === null ? "Stock no disponible" : p.stock === 0 ? "Sin unidades" : `<span class="ok">${p.stock} disponibles</span>`;
  el.innerHTML = `
    <div class="tarjeta-imagen">${insignia}${arte(p)}</div>
    <div class="tarjeta-info">
      <div class="tarjeta-fila"><h3></h3><span class="precio">${pesos(p.precio)}</span></div>
      <span class="meta">${etiquetaCategoria(p.categoria)} · ${esc(p.sku)}</span>
      <span class="meta">${stock}</span>
      <button class="boton boton-contorno boton-sm" ${p.stock === 0 ? "disabled" : ""}>Agregar al carrito</button>
    </div>`;
  el.querySelector("h3").textContent = p.nombre;
  el.querySelector("button").addEventListener("click", () => agregar(p.id));
  return el;
}

function pintarTodo() {
  const resultados = ordenar(estado.catalogo.filter((p) => coincide(p, estado.filtros)));
  $("rejilla").replaceChildren(...resultados.map(tarjeta));
  $("rejilla").hidden = !resultados.length;
  $("vacio").hidden = Boolean(resultados.length);
  $("conteo").textContent = `${resultados.length} ${resultados.length === 1 ? "producto" : "productos"}`;
  $("ver-resultados").textContent = resultados.length ? `Ver ${resultados.length} ${resultados.length === 1 ? "resultado" : "resultados"}` : "Sin coincidencias";
  pintarFiltros();
  pintarActivos();
}

async function cargarCatalogo() {
  const params = new URLSearchParams({ pagina: 1, tamano: 100 });
  if (estado.q) params.set("q", estado.q);
  try {
    const datos = await api(`/api/productos?${params}`);
    estado.catalogo = datos.items;
    datos.items.forEach((p) => estado.productos.set(p.id, p));
    if (!estado.limites[1]) {
      const precios = datos.items.map((p) => p.precio);
      estado.limites = [Math.floor(Math.min(...precios) / PASO_PRECIO) * PASO_PRECIO, Math.ceil(Math.max(...precios) / PASO_PRECIO) * PASO_PRECIO];
      estado.filtros.precio = [...estado.limites];
    }
    pintarTodo();
  } catch (e) {
    $("conteo").textContent = "No se pudo cargar el catálogo.";
    avisar(e.message, true);
  }
}

function abrirFiltros(abrir) {
  $("filtros").classList.toggle("abierto", abrir);
  $("velo-filtros").hidden = !abrir;
}

// ---------- Carrito ----------
function agregar(id) {
  estado.carrito.set(id, (estado.carrito.get(id) || 0) + 1);
  pintarCarrito();
  avisar(`Agregado: ${estado.productos.get(id).nombre}`);
}

function cambiarCantidad(id, delta) {
  const n = (estado.carrito.get(id) || 0) + delta;
  n > 0 ? estado.carrito.set(id, n) : estado.carrito.delete(id);
  pintarCarrito();
}

function pintarCarrito() {
  let unidades = 0, total = 0;
  const filas = [...estado.carrito].map(([id, cantidad]) => {
    const p = estado.productos.get(id);
    unidades += cantidad; total += p.precio * cantidad;
    const fila = document.createElement("div");
    fila.className = "item-carrito";
    fila.innerHTML = `
      <div class="miniatura">${arte(p)}</div>
      <div><h3></h3>
        <div class="cantidad"><button aria-label="Quitar uno">−</button><span>${cantidad}</span><button aria-label="Agregar uno">+</button></div>
      </div>
      <strong class="precio">${pesos(p.precio * cantidad)}</strong>`;
    fila.querySelector("h3").textContent = p.nombre;
    const [menos, mas] = fila.querySelectorAll(".cantidad button");
    menos.addEventListener("click", () => cambiarCantidad(id, -1));
    mas.addEventListener("click", () => cambiarCantidad(id, 1));
    return fila;
  });
  $("items-carrito").replaceChildren(...filas);
  if (!filas.length) $("items-carrito").innerHTML = `<p class="vacio">Tu carrito está vacío.</p>`;
  $("contador-carrito").textContent = unidades;
  $("total-carrito").textContent = pesos(total);
  $("boton-pedido").disabled = !filas.length;
  $("boton-pedido").textContent = estado.token ? "Crear pedido" : "Inicia sesión para pedir";
}

function abrirCarrito(abrir) {
  $("panel-carrito").hidden = !abrir;
  $("velo").hidden = !abrir;
}

async function crearPedido() {
  if (!estado.token) { abrirCarrito(false); abrirSesion("login"); return; }
  const items = [...estado.carrito].map(([producto_id, cantidad]) => ({ producto_id, cantidad }));
  $("boton-pedido").disabled = true;
  try {
    const pedido = await api("/api/pedidos", {
      method: "POST",
      body: JSON.stringify({ items }),
      headers: { "Idempotency-Key": crypto.randomUUID() },
    });
    estado.pedidoActual = { ...pedido, items };
    estado.carrito.clear();
    pintarCarrito();
    abrirCarrito(false);
    mostrarPedido();
    cargarCatalogo();
  } catch (e) {
    avisar(e.codigo === "stock_insuficiente" ? "No hay stock suficiente para uno de los productos." : e.message, true);
    $("boton-pedido").disabled = false;
  }
}

function mostrarPedido(error = "") {
  const p = estado.pedidoActual;
  $("titulo-pedido").textContent = p.estado === "pagado" ? "¡Pago aprobado!" : p.estado === "cancelado" ? "Pago rechazado" : "Pedido creado";
  $("detalle-pedido").innerHTML = `
    <p class="codigo">Pedido ${esc(p.id)}</p>
    ${p.items.map((i) => `<div class="linea-detalle"><span>${i.cantidad} × ${esc(estado.productos.get(i.producto_id)?.nombre ?? "Producto")}</span></div>`).join("")}
    <div class="linea-detalle"><strong>Total</strong><strong>${pesos(p.total)}</strong></div>
    <p><span class="estado estado-${esc(p.estado)}">${esc(p.estado)}</span></p>`;
  $("error-pedido").textContent = error;
  $("boton-pagar").hidden = p.estado !== "creado";
  if (!$("dialogo-pedido").open) $("dialogo-pedido").showModal();
}

async function pagar() {
  const p = estado.pedidoActual;
  $("boton-pagar").disabled = true;
  try {
    const r = await api(`/api/pedidos/${p.id}/pago`, { method: "POST" });
    p.estado = r.estado;
    mostrarPedido();
  } catch (e) {
    if (e.status === 402) { p.estado = "cancelado"; mostrarPedido("La pasarela rechazó el pago; las unidades reservadas volvieron al inventario."); }
    else mostrarPedido(e.message);
  } finally {
    $("boton-pagar").disabled = false;
  }
}

// ---------- Pedidos ----------
async function nombreProducto(id) {
  if (!estado.productos.has(id)) {
    try { estado.productos.set(id, await api(`/api/productos/${id}`)); } catch { return "Producto"; }
  }
  return estado.productos.get(id).nombre;
}

async function cargarPedidos() {
  const lista = $("lista-pedidos");
  try {
    const pedidos = await api("/api/pedidos");
    $("resumen-pedidos").textContent = `${pedidos.length} pedido${pedidos.length === 1 ? "" : "s"}`;
    const tarjetas = await Promise.all(pedidos.map(async (p, k) => {
      const nombres = await Promise.all(p.items.map((i) => nombreProducto(i.producto_id)));
      const el = document.createElement("article");
      el.className = "pedido";
      el.style.animationDelay = Math.min(k, 8) * 45 + "ms";
      el.innerHTML = `
        <div class="pedido-cabecera">
          <div><strong class="precio">${pesos(p.total)}</strong>
            <p class="codigo">${new Date(p.created_at).toLocaleString("es-CO")} · ${esc(p.id.slice(0, 8))}</p></div>
          <span class="estado estado-${esc(p.estado)}">${esc(p.estado)}</span>
        </div>
        <ul>${p.items.map((i, n) => `<li>${i.cantidad} × ${esc(nombres[n])} — ${pesos(i.precio_unitario)}</li>`).join("")}</ul>`;
      return el;
    }));
    lista.replaceChildren(...tarjetas);
    if (!tarjetas.length) lista.innerHTML = `<p class="vacio">Todavía no tienes pedidos.</p>`;
  } catch {
    lista.innerHTML = `<p class="vacio">No se pudieron cargar los pedidos.</p>`;
  }
}

// ---------- Sesión ----------
function abrirSesion(modo) {
  estado.modoSesion = modo;
  document.querySelectorAll(".pestana").forEach((b) => b.classList.toggle("activa", b.dataset.modo === modo));
  $("campo-nombre").hidden = modo !== "registro";
  $("boton-enviar-sesion").textContent = modo === "registro" ? "Crear cuenta" : "Entrar";
  $("error-sesion").textContent = "";
  if (!$("dialogo-sesion").open) $("dialogo-sesion").showModal();
}

async function enviarSesion(evento) {
  evento.preventDefault();
  const datos = Object.fromEntries(new FormData(evento.target));
  $("error-sesion").textContent = "";
  try {
    if (estado.modoSesion === "registro") {
      await api("/api/usuarios/registro", { method: "POST", body: JSON.stringify(datos) });
    }
    const r = await api("/api/usuarios/login", {
      method: "POST",
      body: JSON.stringify({ email: datos.email, password: datos.password }),
    });
    estado.token = r.access_token;
    sessionStorage.setItem("token", r.access_token);
    await cargarUsuario();
    $("dialogo-sesion").close();
    evento.target.reset();
    avisar(`Hola, ${estado.usuario.email}`);
  } catch (e) {
    const mensajes = { credenciales_invalidas: "Email o contraseña incorrectos.", cuenta_bloqueada: "Cuenta bloqueada por intentos fallidos. Intenta en 15 minutos.", email_existe: "Ya existe una cuenta con ese email." };
    $("error-sesion").textContent = mensajes[e.codigo] || e.message;
  }
}

async function cargarUsuario() {
  if (!estado.token) return pintarSesion();
  try { estado.usuario = await api("/api/usuarios/me"); }
  catch { estado.usuario = null; }
  pintarSesion();
}

function cerrarSesion(mensaje) {
  estado.token = null; estado.usuario = null;
  sessionStorage.removeItem("token");
  pintarSesion();
  if (location.hash === "#pedidos") location.hash = "#catalogo";
  if (mensaje) avisar(mensaje, true);
}

function pintarSesion() {
  const conectado = Boolean(estado.usuario);
  $("boton-sesion").textContent = conectado ? "Cerrar sesión" : "Iniciar sesión";
  $("boton-sesion").title = conectado ? `Conectado como ${estado.usuario.email}` : "";
  $("enlace-pedidos").hidden = !conectado;
  pintarCarrito();
}

// ---------- Navegación y eventos ----------
function enrutar() {
  const pedidos = location.hash === "#pedidos" && estado.token;
  $("vista-catalogo").hidden = pedidos;
  $("vista-pedidos").hidden = !pedidos;
  if (pedidos) cargarPedidos();
}

$("form-busqueda").addEventListener("submit", (e) => {
  e.preventDefault();
  estado.q = $("busqueda").value.trim();
  location.hash = "#catalogo";
  cargarCatalogo();
});
for (const [id, i] of [["precio-min", 0], ["precio-max", 1]]) {
  $(id).addEventListener("input", (e) => {
    const p = estado.filtros.precio, v = Number(e.target.value);
    p[i] = i === 0 ? Math.min(v, p[1] - PASO_PRECIO) : Math.max(v, p[0] + PASO_PRECIO);
    pintarTodo();
  });
}
$("solo-stock").addEventListener("click", () => { estado.filtros.soloStock = !estado.filtros.soloStock; pintarTodo(); });
$("orden").addEventListener("change", (e) => { estado.orden = e.target.value; pintarTodo(); });
for (const id of ["limpiar-filtros", "limpiar-filtros-movil", "limpiar-vacio"]) $(id).addEventListener("click", limpiarFiltros);
$("abrir-filtros").addEventListener("click", () => abrirFiltros(true));
for (const id of ["cerrar-filtros", "ver-resultados", "velo-filtros"]) $(id).addEventListener("click", () => abrirFiltros(false));
$("boton-sesion").addEventListener("click", () => (estado.usuario ? cerrarSesion() : abrirSesion("login")));
document.querySelectorAll(".pestana").forEach((b) => b.addEventListener("click", () => abrirSesion(b.dataset.modo)));
$("form-sesion").addEventListener("submit", enviarSesion);
$("boton-carrito").addEventListener("click", () => abrirCarrito(true));
$("velo").addEventListener("click", () => abrirCarrito(false));
document.querySelector("[data-cerrar='panel-carrito']").addEventListener("click", () => abrirCarrito(false));
$("boton-pedido").addEventListener("click", crearPedido);
$("boton-pagar").addEventListener("click", pagar);
$("boton-cerrar-pedido").addEventListener("click", () => $("dialogo-pedido").close());
window.addEventListener("hashchange", enrutar);
// Si una foto no carga (archivo dañado o URL vencida), se reemplaza por el ícono neutro.
document.addEventListener("error", (e) => {
  const img = e.target;
  if (img.tagName !== "IMG" || !img.closest(".tarjeta-imagen, .miniatura")) return;
  const respaldo = document.createElement("div");
  respaldo.className = "arte arte-general";
  respaldo.setAttribute("role", "img");
  respaldo.setAttribute("aria-label", "Sin foto");
  respaldo.innerHTML = ICONO_SIN_FOTO;
  img.replaceWith(respaldo);
}, true);
document.addEventListener("keydown", (e) => { if (e.key === "Escape") { abrirCarrito(false); abrirFiltros(false); } });

cargarUsuario().then(() => { cargarCatalogo(); enrutar(); });

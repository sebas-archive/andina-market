// Prueba de carga escalonada 20 → 100 → 200 req/s (Tarea 4.8).
// Mezcla: 70 % GET /api/productos, 20 % GET /api/productos/{id}, 10 % POST /api/pedidos autenticado.
// Uso: docker compose --profile carga run --rm k6 run /pruebas/pedidos.js
import http from 'k6/http';
import { check } from 'k6';

const BASE = __ENV.BASE || 'https://nginx:8443';

export const options = {
  insecureSkipTLSVerify: true, // certificado autofirmado de la demo
  scenarios: {
    escalonado: {
      executor: 'ramping-arrival-rate',
      startRate: 20,
      timeUnit: '1s',
      preAllocatedVUs: 100,
      maxVUs: 600,
      stages: [
        { target: 20, duration: '1m' },
        { target: 100, duration: '1m' },
        { target: 200, duration: '1m' },
      ],
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.02'],
    'http_req_duration': ['p(95)<800'],
    'http_req_duration{name:listar_productos}': ['p(95)<800'],
    'http_req_duration{name:detalle_producto}': ['p(95)<800'],
    'http_req_duration{name:crear_pedido}': ['p(95)<800'],
  },
  summaryTrendStats: ['avg', 'p(50)', 'p(95)', 'p(99)', 'max'],
};

export function setup() {
  const login = http.post(`${BASE}/api/usuarios/login`,
    JSON.stringify({ email: __ENV.EMAIL, password: __ENV.PASSWORD }),
    { headers: { 'Content-Type': 'application/json' } });
  check(login, { 'login 200': (r) => r.status === 200 });
  const productos = http.get(`${BASE}/api/productos?pagina=1&tamano=20`).json('items');
  return { token: login.json('access_token'), ids: productos.map((p) => p.id) };
}

export default function (datos) {
  const azar = Math.random();
  const id = datos.ids[Math.floor(Math.random() * datos.ids.length)];
  if (azar < 0.7) {
    const pagina = 1 + Math.floor(Math.random() * 4);
    const r = http.get(`${BASE}/api/productos?pagina=${pagina}&tamano=5`, { tags: { name: 'listar_productos' } });
    check(r, { 'listar 200': (x) => x.status === 200 });
  } else if (azar < 0.9) {
    const r = http.get(`${BASE}/api/productos/${id}`, { tags: { name: 'detalle_producto' } });
    check(r, { 'detalle 200': (x) => x.status === 200 });
  } else {
    const r = http.post(`${BASE}/api/pedidos`,
      JSON.stringify({ items: [{ producto_id: id, cantidad: 1 }] }),
      { headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${datos.token}` },
        tags: { name: 'crear_pedido' } });
    check(r, { 'pedido 201': (x) => x.status === 201 });
  }
}

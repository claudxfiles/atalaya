export interface Revisor { id: string; nombre: string; roles: string[]; celula: number; cert_datos: boolean; disponible: number; capacidad: number }
export interface Resumen {
  id: string; titulo: string; autor: string; estado: string; impacto: string; version: number; celula: number; origen: string; destino: string;
  actualizado: string; sintetico: string | null; hallazgos: number | null; bloqueantes: number; avisos: number; faltan: string[];
}
export interface Hallazgo { codigo: string; origen: string; confirmado: boolean; evidencia: string | null; descripcion: string; bloqueante: boolean; descartado: boolean }
export interface Revision {
  id: string; fecha: string; modo: string; nota: string; hallazgos: Hallazgo[]; avisos: string[]; fiscal: string[]; explicacion: string;
  normas: { id: string; texto: string; version: number }[]; citadas: string[]; modelo: string | null; usd: number; tokens: number; segundos: number; enviado: string;
}
export interface Plan { paquete: string; hechos: string[]; pendientes: string[]; hechas: { accion: string; actor: string; fecha: string }[]; metodo: string; replanificaciones: number; pii: boolean; alto: boolean }
export interface RegistroAud { n: number; fecha: string; actor: string; accion: string; objeto: string; detalle: Record<string, unknown>; hash: string }
export interface Paquete extends Resumen {
  revisor_propuesto: string; pruebas: string[]; plazo_dias: number; hu: string; contrato: string; muestra: string; etl: string;
  aprobaciones: { revisor: string; nombre: string; fecha: string; comentario: string }[]; descartes: string[]; revision: Revision | null; plan: Plan | null;
  requisitos: { firmas: number; arquitectura: boolean; certificacion_datos: boolean }; auditoria: RegistroAud[];
}
export interface Trabajo<T = unknown> { id: string; tipo: string; estado: string; etapas: { etapa: string; detalle: string }[]; resultado: T | null; error: string | null }
export interface Tarea { id: string; paquete: string; titulo: string; rol: string; duracion: number; plazo: number; peso: number }
export interface Asignacion {
  id: string; publicada: boolean; estado: string; mensaje: string; metodo: string; publicable: boolean; objetivo?: number; cota?: number | null; segundos?: number;
  calendario: Record<string, { revisor: string; inicio: number }>; tareas: Tarea[]; fecha: string;
}
export interface Ausencia { id: string; revisor: string; nombre: string; desde_dia: number; hasta_dia: number }
export interface Norma { id: string; texto: string; version: number; vigente: boolean; fecha: string; indexada: boolean }
export interface Propuesta { tipo: string; revisor: string; nombre: string; desde_dia: number; hasta_dia: number }
export interface Mensaje { rol: string; texto: string; herramientas?: string[]; propuestas?: Propuesta[]; usd?: number }
export interface Salud { ok: boolean; modelo: boolean; gasto_hoy: number; tope: number; revisor: string; triaje: string }

async function pedir<T>(metodo: string, ruta: string, cuerpo?: unknown): Promise<T> {
  let r: Response;
  try {
    r = await fetch("/api" + ruta, { method: metodo, headers: cuerpo ? { "Content-Type": "application/json" } : {}, body: cuerpo ? JSON.stringify(cuerpo) : undefined });
  } catch {
    throw new Error("No hay conexión con el servicio. Revisa que siga encendido.");
  }
  if (!r.ok) {
    const d = await r.json().catch(() => ({}));
    const detalle = Array.isArray(d.detail) ? "Revisa los campos del formulario: " + d.detail.map((x: { loc: string[] }) => x.loc.at(-1)).join(", ") + "." : d.detail;
    throw new Error(detalle || `Error ${r.status}.`);
  }
  return r.json();
}
export const api = {
  get: <T,>(ruta: string) => pedir<T>("GET", ruta),
  post: <T,>(ruta: string, cuerpo?: unknown) => pedir<T>("POST", ruta, cuerpo ?? {}),
  put: <T,>(ruta: string, cuerpo: unknown) => pedir<T>("PUT", ruta, cuerpo),
  del: <T,>(ruta: string) => pedir<T>("DELETE", ruta),
};
export async function esperarTrabajo<T>(id: string, alAvanzar: (t: Trabajo<T>) => void): Promise<Trabajo<T>> {
  for (;;) {
    const t = await api.get<Trabajo<T>>(`/trabajos/${id}`);
    alAvanzar(t);
    if (t.estado === "listo" || t.estado === "error") return t;
    await new Promise((res) => setTimeout(res, 500));
  }
}

export const ESTADOS: Record<string, string> = {
  borrador: "Sin revisar", en_revision: "En revisión", rechazado: "Con bloqueantes", por_aprobar: "Por aprobar", devuelto: "Devuelto",
  aprobado: "Aprobado", en_promocion: "En promoción", promovido: "Promovido",
};
export const DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"];
export const fecha = (s: string) => new Date(s).toLocaleString("es-CL", { dateStyle: "short", timeStyle: "short" });

import { useEffect, useState } from "react";
import { api, ESTADOS, fecha, type Paquete, type Resumen } from "../api";

const PERFILES = [
  ["correcto", "Correcto"], ["credencial", "Clave en cadena de conexión"], ["sobrescribe", "Contradice la historia"],
  ["funciones", "Autor que se revisa a sí mismo"], ["rut", "RUT sin declarar"], ["inyeccion", "Instrucción maliciosa"],
];
const FILTROS: [string, string, (p: Resumen) => boolean][] = [
  ["todos", "Todos", () => true],
  ["accion", "Requieren acción", (p) => ["por_aprobar", "rechazado", "borrador", "devuelto"].includes(p.estado)],
  ["promocion", "En promoción", (p) => ["aprobado", "en_promocion"].includes(p.estado)],
  ["cerrados", "Promovidos", (p) => p.estado === "promovido"],
];

export function Etiqueta({ estado }: { estado: string }) {
  return <span className={"etq e-" + estado}>{ESTADOS[estado] ?? estado}</span>;
}

export function Bandeja() {
  const [lista, setLista] = useState<Resumen[] | null>(null);
  const [filtro, setFiltro] = useState("accion");
  const [error, setError] = useState("");
  const [perfil, setPerfil] = useState("correcto");
  const [creando, setCreando] = useState(false);
  const cargar = () => api.get<Resumen[]>("/paquetes").then(setLista).catch((e) => setError(e.message));
  useEffect(() => { cargar(); const t = setInterval(cargar, 5000); return () => clearInterval(t); }, []);
  const crear = async () => {
    setCreando(true);
    try { const p = await api.post<Paquete>("/paquetes/sintetico", { perfil }); window.location.hash = `/paquete/${p.id}`; }
    catch (e) { setError((e as Error).message); setCreando(false); }
  };
  const f = FILTROS.find((x) => x[0] === filtro)!;
  const visibles = lista?.filter(f[2]) ?? [];
  return (
    <>
      <div className="titulo-fila">
        <h1>Bandeja de paquetes</h1>
        <div className="acciones">
          <label className="en-linea">Paquete de prueba
            <select value={perfil} onChange={(e) => setPerfil(e.target.value)}>{PERFILES.map(([k, n]) => <option key={k} value={k}>{n}</option>)}</select>
          </label>
          <button onClick={crear} disabled={creando}>Crear de prueba</button>
          <a className="boton primario" href="#/nuevo">Nuevo paquete</a>
        </div>
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="pestanas" role="tablist">
        {FILTROS.map(([k, n, fn]) => <button key={k} role="tab" aria-selected={filtro === k} className={filtro === k ? "sel" : ""} onClick={() => setFiltro(k)}>{n}<span className="cuenta">{lista?.filter(fn).length ?? ""}</span></button>)}
      </div>
      {lista === null ? <div className="esqueleto" /> : visibles.length === 0 ? (
        <div className="vacio"><p>No hay paquetes en esta vista.</p><p>Crea un paquete nuevo con tu historia, contrato, muestra y código, o genera uno de prueba para ver el flujo completo.</p></div>
      ) : (
        <div className="tabla-marco"><table>
          <thead><tr><th>Paquete</th><th>Estado</th><th>Impacto</th><th>Autor</th><th>Destino</th><th className="num">Hallazgos</th><th>Lo que falta</th><th>Actualizado</th></tr></thead>
          <tbody>{visibles.map((p) => (
            <tr key={p.id} className="fila-enlace" onClick={() => { window.location.hash = `/paquete/${p.id}`; }}>
              <td><a href={`#/paquete/${p.id}`}><b>{p.titulo}</b></a><div className="sutil">{p.id} · v{p.version}{p.sintetico ? " · prueba" : ""}</div></td>
              <td><Etiqueta estado={p.estado} /></td><td><span className={"imp i-" + p.impacto}>{p.impacto}</span></td><td>{p.autor}</td><td>{p.origen} → {p.destino}</td>
              <td className="num">{p.hallazgos === null ? "—" : p.hallazgos}{p.bloqueantes > 0 && <span className="rojo"> · {p.bloqueantes} bloq.</span>}</td>
              <td>{falta(p)}</td><td className="sutil">{fecha(p.actualizado)}</td>
            </tr>))}</tbody>
        </table></div>
      )}
    </>
  );
}

function falta(p: Resumen): string {
  if (p.estado === "borrador") return "Revisar";
  if (p.estado === "rechazado") return "Corregir bloqueantes";
  if (p.estado === "devuelto") return "Corregir y volver a revisar";
  if (p.estado === "por_aprobar") return p.faltan.join(", ") || "Firma";
  if (p.estado === "aprobado" || p.estado === "en_promocion") return "Completar plan";
  return "—";
}

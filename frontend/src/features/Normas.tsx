import { useEffect, useState } from "react";
import { api, fecha, type Norma } from "../api";

export function Normas() {
  const [lista, setLista] = useState<Norma[] | null>(null);
  const [q, setQ] = useState("");
  const [encontradas, setEncontradas] = useState<{ metodo: string; normas: Norma[] } | null>(null);
  const [editando, setEditando] = useState<{ id: string | null; texto: string; vigente: boolean } | null>(null);
  const [error, setError] = useState("");
  const [buscando, setBuscando] = useState(false);
  const cargar = () => api.get<Norma[]>("/normas").then(setLista).catch((e) => setError(e.message));
  useEffect(() => { cargar(); }, []);
  const buscar = async () => {
    if (!q.trim()) return setEncontradas(null);
    setBuscando(true); setError("");
    try { setEncontradas(await api.get(`/normas/buscar?q=${encodeURIComponent(q)}`)); } catch (e) { setError((e as Error).message); }
    setBuscando(false);
  };
  const guardar = async () => {
    if (!editando) return;
    setError("");
    try {
      const c = { texto: editando.texto, vigente: editando.vigente };
      if (editando.id) await api.put(`/normas/${editando.id}`, c); else await api.post("/normas", c);
      setEditando(null); setEncontradas(null); cargar();
    } catch (e) { setError((e as Error).message); }
  };
  const visibles = encontradas ? encontradas.normas : lista ?? [];
  return (
    <>
      <div className="titulo-fila"><h1>Normas internas</h1><div className="acciones"><button className="primario" onClick={() => setEditando({ id: null, texto: "", vigente: true })}>Nueva norma</button></div></div>
      {error && <p className="error" role="alert">{error}</p>}
      <form className="fila-form" onSubmit={(e) => { e.preventDefault(); buscar(); }}>
        <input className="crece" aria-label="Buscar" placeholder="Pregunta en tus palabras, por ejemplo: ¿cuándo puedo pasar a producción?" value={q} onChange={(e) => setQ(e.target.value)} />
        <button disabled={buscando}>{buscando ? "Buscando" : "Buscar"}</button>
        {encontradas && <button type="button" className="sin-borde" onClick={() => { setEncontradas(null); setQ(""); }}>Ver todas</button>}
      </form>
      {encontradas && <p className="sutil">Búsqueda {encontradas.metodo === "embeddings" ? "semántica" : "por palabras, porque el modelo no está disponible"}.</p>}
      {editando && (
        <div className="panel"><h2>{editando.id ? `Editar ${editando.id}` : "Nueva norma"}</h2><p className="sutil">Guardar crea una versión nueva. Las revisiones anteriores conservan la que citaron.</p>
          <label>Texto<textarea rows={3} value={editando.texto} onChange={(e) => setEditando({ ...editando, texto: e.target.value })} /></label>
          <label className="check"><input type="checkbox" checked={editando.vigente} onChange={(e) => setEditando({ ...editando, vigente: e.target.checked })} />Vigente</label>
          <div className="acciones"><button className="primario" disabled={editando.texto.trim().length < 5} onClick={guardar}>Guardar</button><button onClick={() => setEditando(null)}>Cancelar</button></div></div>
      )}
      {lista === null ? <div className="esqueleto" /> : visibles.length === 0 ? <div className="vacio"><p>Ninguna norma coincide con esa búsqueda.</p></div> : (
        <div className="tabla-marco"><table><thead><tr><th>Norma</th><th>Texto</th><th>Versión</th><th>Fecha</th><th /></tr></thead>
          <tbody>{visibles.map((n) => <tr key={n.id} className={n.vigente ? "" : "apagada"}><td><b>{n.id}</b>{!n.vigente && <div className="sutil">No vigente</div>}</td><td className="prosa-t">{n.texto}</td><td>v{n.version}</td><td className="sutil">{fecha(n.fecha)}</td>
            <td><button className="sin-borde" onClick={() => setEditando({ id: n.id, texto: n.texto, vigente: n.vigente })}>Editar</button></td></tr>)}</tbody></table></div>
      )}
    </>
  );
}

import { useEffect, useState } from "react";
import { api, type Salud } from "../api";

interface Uso { por_dia: { dia: string; modelo: string; llamadas: number; entrada: number; salida: number; usd: number }[]; gasto_hoy: number; tope: number }

export function Ajustes({ alCambiar }: { alCambiar: () => void }) {
  const [uso, setUso] = useState<Uso | null>(null);
  const [salud, setSalud] = useState<Salud | null>(null);
  const [tope, setTope] = useState("");
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");
  const cargar = () => { api.get<Uso>("/uso").then((u) => { setUso(u); setTope(String(u.tope)); }).catch((e) => setError(e.message)); api.get<Salud>("/salud").then(setSalud).catch(() => {}); };
  useEffect(cargar, []);
  const guardar = async () => {
    setMsg(""); setError("");
    try { await api.put("/ajustes", { tope_diario_usd: Number(tope) }); setMsg("Tope guardado."); cargar(); alCambiar(); } catch (e) { setError((e as Error).message); }
  };
  return (
    <>
      <div className="titulo-fila"><h1>Ajustes</h1></div>
      {error && <p className="error" role="alert">{error}</p>}
      <section className="panel ancho-medio">
        <h2>Modelos</h2>
        <dl className="datos"><dt>Revisor y agente</dt><dd>{salud?.revisor ?? "—"}</dd><dt>Triaje y explicaciones</dt><dd>{salud?.triaje ?? "—"}</dd><dt>Clave de API</dt><dd>{salud?.modelo ? "Configurada" : "No configurada: la aplicación opera solo con reglas"}</dd></dl>
      </section>
      <section className="panel ancho-medio">
        <h2>Tope diario de gasto</h2>
        <p className="sutil">Al alcanzarlo, Atalaya sigue operando con reglas y deja la revisión semántica pendiente para una persona.</p>
        <div className="fila-form"><label className="en-linea">USD por día<input className="corto" type="number" min={0} max={100} step={0.1} value={tope} onChange={(e) => setTope(e.target.value)} /></label><button className="primario" onClick={guardar}>Guardar</button>{msg && <span className="verde" role="status">{msg}</span>}</div>
      </section>
      <h2>Consumo</h2>
      {!uso || uso.por_dia.length === 0 ? <div className="vacio"><p>Aún no hay llamadas a modelos.</p></div> : (
        <div className="tabla-marco"><table><thead><tr><th>Día</th><th>Modelo</th><th className="num">Llamadas</th><th className="num">Tokens de entrada</th><th className="num">Tokens de salida</th><th className="num">USD</th></tr></thead>
          <tbody>{uso.por_dia.map((u) => <tr key={u.dia + u.modelo}><td>{u.dia}</td><td>{u.modelo}</td><td className="num">{u.llamadas}</td><td className="num">{u.entrada.toLocaleString("es-CL")}</td><td className="num">{u.salida.toLocaleString("es-CL")}</td><td className="num">{u.usd.toFixed(4)}</td></tr>)}</tbody></table></div>
      )}
    </>
  );
}

import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, DIAS, type Mensaje, type Propuesta } from "../api";

const SUGERENCIAS = ["¿Qué paquetes están esperando una firma?", "¿Qué dice la norma sobre aprobar el cambio de alguien de mi célula?", "Paula Fuentes no estará el jueves"];

/** Solo interpreta negritas; el resto del texto del modelo se muestra literal y React lo escapa. */
function conNegritas(texto: string) {
  return texto.split(/\*\*(.+?)\*\*/g).map((parte, i) => (i % 2 ? <b key={i}>{parte}</b> : parte));
}

function sesionId() {
  try {
    let s = localStorage.getItem("sesion_agente");
    if (!s) { s = "s" + Math.random().toString(36).slice(2, 10); localStorage.setItem("sesion_agente", s); }
    return s;
  } catch { return "s-temporal"; }
}

export function Agente({ paquete, alCambiar }: { paquete: string | null; alCambiar: () => void }) {
  const [sesion, setSesion] = useState(sesionId);
  const [msgs, setMsgs] = useState<Mensaje[]>([]);
  const [texto, setTexto] = useState("");
  const [pensando, setPensando] = useState(false);
  const [error, setError] = useState("");
  const [confirmadas, setConfirmadas] = useState<Set<string>>(new Set());
  const fin = useRef<HTMLDivElement>(null);
  useEffect(() => { api.get<Mensaje[]>(`/agente/${sesion}`).then(setMsgs).catch((e) => setError(e.message)); }, [sesion]);
  useEffect(() => { fin.current?.scrollIntoView?.({ block: "nearest" }); }, [msgs, pensando]);
  const enviar = async (t: string) => {
    if (!t.trim() || pensando) return;
    setTexto(""); setError(""); setPensando(true);
    setMsgs((m) => [...m, { rol: "usuario", texto: t }]);
    try {
      const r = await api.post<Mensaje>("/agente", { sesion, texto: t, paquete });
      const h = await api.get<Mensaje[]>(`/agente/${sesion}`);
      setMsgs(h.length ? h : (m) => [...m, r]);
      alCambiar();
    } catch (e) { setError((e as Error).message); }
    setPensando(false);
  };
  const confirmar = async (p: Propuesta, clave: string) => {
    setError("");
    try { await api.post("/restricciones", { revisor: p.revisor, desde_dia: p.desde_dia, hasta_dia: p.hasta_dia }); setConfirmadas((s) => new Set(s).add(clave)); }
    catch (e) { setError((e as Error).message); }
  };
  const nueva = () => { const s = "s" + Math.random().toString(36).slice(2, 10); try { localStorage.setItem("sesion_agente", s); } catch { /* sin almacenamiento */ } setSesion(s); setMsgs([]); };
  return (
    <div className="chat">
      <div className="titulo-fila"><h1>Agente</h1><div className="acciones"><button onClick={nueva}>Nueva conversación</button></div></div>
      <p className="sutil">Consulta paquetes, planes, normas y calendario. No puede aprobar ni cambiar nada: lo que propone lo confirma una persona.</p>
      <div className="mensajes" aria-live="polite">
        {msgs.length === 0 && !pensando && <div className="sugerencias">{SUGERENCIAS.map((s) => <button key={s} onClick={() => enviar(s)}>{s}</button>)}</div>}
        {msgs.map((m, i) => (
          <div key={i} className={"msg m-" + m.rol}>
            <div className="burbuja">{conNegritas(m.texto)}</div>
            {m.propuestas?.map((p, j) => { const clave = `${i}-${j}`; return (
              <div className="propuesta" key={clave}><div><b>Propuesta:</b> {p.nombre} ausente {DIAS[p.desde_dia]}{p.hasta_dia !== p.desde_dia ? ` a ${DIAS[p.hasta_dia]}` : ""}.</div>
                {confirmadas.has(clave) ? <span className="verde">Confirmada</span> : <button className="primario" onClick={() => confirmar(p, clave)}>Confirmar</button>}</div>); })}
            {m.herramientas && m.herramientas.length > 0 && <div className="sutil">Usó: {[...new Set(m.herramientas)].join(", ").replaceAll("_", " ")}</div>}
          </div>))}
        {pensando && <div className="msg m-agente"><div className="burbuja pensando">Consultando</div></div>}
        <div ref={fin} />
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      <form className="entrada" onSubmit={(e: FormEvent) => { e.preventDefault(); enviar(texto); }}>
        <textarea aria-label="Mensaje" rows={2} value={texto} placeholder="Escribe tu pregunta" onChange={(e) => setTexto(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); enviar(texto); } }} />
        <button className="primario" disabled={pensando || !texto.trim()}>Enviar</button>
      </form>
    </div>
  );
}

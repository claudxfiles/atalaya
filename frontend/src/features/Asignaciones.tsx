import { useCallback, useEffect, useState } from "react";
import { api, DIAS, esperarTrabajo, fecha, type Asignacion, type Ausencia, type Revisor, type Tarea, type Trabajo } from "../api";

const BLOQUES_DIA = 32;
const TOTAL = 160;
const hora = (b: number) => { const d = Math.floor(b / BLOQUES_DIA); const m = (b % BLOQUES_DIA) * 15; return `${DIAS[Math.min(d, 4)].slice(0, 3)} ${String(9 + Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`; };

export function Asignaciones({ actor, revisores, recargarRevisores }: { actor: string; revisores: Revisor[]; recargarRevisores: () => void }) {
  const [pendientes, setPendientes] = useState<Tarea[]>([]);
  const [vigente, setVigente] = useState<Asignacion | null>(null);
  const [aus, setAus] = useState<Ausencia[]>([]);
  const [job, setJob] = useState<Trabajo | null>(null);
  const [error, setError] = useState("");
  const [nueva, setNueva] = useState({ revisor: "", desde_dia: 0, hasta_dia: 0 });
  const cargar = useCallback(() => {
    api.get<{ tareas_pendientes: Tarea[]; vigente: Asignacion | null }>("/asignacion").then((r) => { setPendientes(r.tareas_pendientes); setVigente(r.vigente); }).catch((e) => setError(e.message));
    api.get<Ausencia[]>("/restricciones").then(setAus).catch(() => {});
  }, []);
  useEffect(cargar, [cargar]);
  const correr = async (f: () => Promise<unknown>) => { setError(""); try { await f(); cargar(); } catch (e) { setError((e as Error).message); } };
  const calcular = () => correr(async () => {
    const t = await api.post<Trabajo>("/asignacion/calcular");
    setJob(t);
    const fin = await esperarTrabajo(t.id, setJob);
    setJob(null);
    if (fin.error) throw new Error(fin.error);
  });
  const porRevisor = (id: string) => (vigente ? Object.entries(vigente.calendario).filter(([, c]) => c.revisor === id).map(([tid, c]) => ({ t: vigente.tareas.find((x) => x.id === tid)!, c })).filter((x) => x.t) : []);
  return (
    <>
      <div className="titulo-fila">
        <h1>Asignación de revisiones</h1>
        <div className="acciones">
          {vigente?.publicable && !vigente.publicada && <button onClick={() => vigente && correr(() => api.post(`/asignacion/${vigente.id}/publicar`))}>Publicar calendario</button>}
          <button className="primario" disabled={!!job} onClick={calcular}>{job ? "Calculando" : "Calcular calendario"}</button>
        </div>
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      <p className="sutil">{pendientes.length === 1 ? "1 revisión espera" : `${pendientes.length} revisiones esperan`} a una persona. El optimizador solo considera rol, certificación, célula y capacidad, nunca desempeño individual.</p>
      {job && <p className="progreso-simple" role="status">{job.etapas.at(-1)?.detalle ?? "Preparando el modelo."}</p>}
      {vigente && (
        <div className={"resultado " + (vigente.publicable ? "r-ok" : "r-mal")}>
          <b>{vigente.mensaje}</b>
          <div className="sutil">{vigente.metodo}{vigente.objetivo !== undefined ? ` · costo ${vigente.objetivo}` : ""}{vigente.segundos !== undefined ? ` · ${vigente.segundos} s` : ""} · {fecha(vigente.fecha)} · {vigente.publicada ? "publicado" : "sin publicar"}</div>
        </div>
      )}
      {vigente?.publicable && (
        <>
          <h2>Calendario de la semana</h2>
          <div className="tabla-marco"><div className="gantt">
            <div className="g-cab"><div />{DIAS.map((d) => <div key={d}>{d}</div>)}</div>
            {revisores.filter((r) => porRevisor(r.id).length > 0 || aus.some((a) => a.revisor === r.id)).map((r) => (
              <div className="g-fila" key={r.id}><div className="g-nom">{r.nombre}</div><div className="g-pista">
                {aus.filter((a) => a.revisor === r.id).map((a) => <div key={a.id} className="g-aus" style={{ left: `${(a.desde_dia * BLOQUES_DIA / TOTAL) * 100}%`, width: `${((a.hasta_dia - a.desde_dia + 1) * BLOQUES_DIA / TOTAL) * 100}%` }}>Ausente</div>)}
                {porRevisor(r.id).map(({ t, c }) => <div key={t.id} className={"g-bloque rol-" + t.rol} title={`${t.titulo} · ${t.rol} · ${hora(c.inicio)}`} style={{ left: `${(c.inicio / TOTAL) * 100}%`, width: `${(t.duracion / TOTAL) * 100}%` }}>{t.rol[0].toUpperCase()}</div>)}
              </div></div>))}
          </div></div>
          <h2>Tareas</h2>
          <div className="tabla-marco"><table><thead><tr><th>Paquete</th><th>Revisión</th><th>Inicio</th><th>Plazo</th><th>Asignada a</th></tr></thead>
            <tbody>{vigente.tareas.map((t) => { const c = vigente.calendario[t.id]; const tarde = c && c.inicio + t.duracion > t.plazo; return (
              <tr key={t.id}><td><a href={`#/paquete/${t.paquete}`}>{t.titulo}</a></td><td>{t.rol}</td><td>{c ? hora(c.inicio) : "—"}{tarde && <span className="ambar"> · atrasada</span>}</td><td>{hora(Math.min(t.plazo, TOTAL - 1))}</td>
                <td>{c && <select aria-label={`Revisor de ${t.titulo}, ${t.rol}`} value={c.revisor} onChange={(e) => correr(() => api.post(`/asignacion/${vigente.id}/ajustar`, { actor: actor || "coordinacion", tarea: t.id, revisor: e.target.value, inicio: c.inicio }))}>
                  {revisores.filter((r) => r.roles.includes(t.rol)).map((r) => <option key={r.id} value={r.id}>{r.nombre}</option>)}</select>}</td></tr>); })}</tbody></table></div>
        </>
      )}
      <div className="dos-col parejas">
        <section>
          <h2>Ausencias</h2>
          <p className="sutil">También puedes pedírselo al agente; quedará como propuesta hasta confirmarla.</p>
          <div className="fila-form">
            <select aria-label="Revisor" value={nueva.revisor} onChange={(e) => setNueva({ ...nueva, revisor: e.target.value })}><option value="">Revisor</option>{revisores.map((r) => <option key={r.id} value={r.id}>{r.nombre}</option>)}</select>
            <select aria-label="Desde" value={nueva.desde_dia} onChange={(e) => { const v = Number(e.target.value); setNueva({ ...nueva, desde_dia: v, hasta_dia: Math.max(v, nueva.hasta_dia) }); }}>{DIAS.map((d, i) => <option key={d} value={i}>{d}</option>)}</select>
            <select aria-label="Hasta" value={nueva.hasta_dia} onChange={(e) => setNueva({ ...nueva, hasta_dia: Number(e.target.value) })}>{DIAS.map((d, i) => i >= nueva.desde_dia && <option key={d} value={i}>{d}</option>)}</select>
            <button disabled={!nueva.revisor} onClick={() => correr(() => api.post("/restricciones", nueva))}>Agregar</button>
          </div>
          {aus.length === 0 ? <p className="sutil">Sin ausencias esta semana.</p> : <ul className="lista-simple">{aus.map((a) => <li key={a.id}>{a.nombre}: {DIAS[a.desde_dia]}{a.hasta_dia !== a.desde_dia ? ` a ${DIAS[a.hasta_dia]}` : ""}<button className="sin-borde" onClick={() => correr(() => api.del(`/restricciones/${a.id}`))}>Quitar</button></li>)}</ul>}
        </section>
        <section>
          <h2>Revisores</h2>
          <div className="tabla-marco"><table><thead><tr><th>Nombre</th><th>Roles</th><th className="num">Célula</th><th>Datos personales</th><th className="num">Horas</th></tr></thead>
            <tbody>{revisores.map((r) => <tr key={r.id}><td>{r.nombre}</td><td>{r.roles.join(", ")}</td><td className="num">{r.celula}</td>
              <td><input type="checkbox" aria-label={`${r.nombre} certificado en datos personales`} checked={r.cert_datos} onChange={(e) => correr(async () => { await api.put(`/revisores/${r.id}`, { ...sinId(r), cert_datos: e.target.checked }); recargarRevisores(); })} /></td>
              <td className="num"><input className="corto" type="number" min={0} max={40} aria-label={`Horas de ${r.nombre}`} defaultValue={r.capacidad / 4} onBlur={(e) => { const h = Number(e.target.value); if (h * 4 !== r.capacidad) correr(async () => { await api.put(`/revisores/${r.id}`, { ...sinId(r), capacidad: h * 4 }); recargarRevisores(); }); }} /></td></tr>)}</tbody></table></div>
        </section>
      </div>
    </>
  );
}

function sinId(r: Revisor) { const { id: _id, ...resto } = r; void _id; return resto; }

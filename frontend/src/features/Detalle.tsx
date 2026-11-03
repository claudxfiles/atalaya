import { useCallback, useEffect, useState } from "react";
import { api, esperarTrabajo, ESTADOS, fecha, type Hallazgo, type Paquete, type Trabajo } from "../api";
import { Etiqueta } from "./Bandeja";

const PASOS: Record<string, string> = {
  validar_contrato: "Validar contrato", escanear_secretos: "Escanear secretos", correr_pruebas: "Correr pruebas", desplegar_qa: "Desplegar en QA", pruebas_integracion: "Pruebas de integración",
  generar_ada: "Documento de arquitectura", revisar_privacidad: "Revisión de privacidad", revisar_arquitectura: "Revisión de arquitectura", aprobar_comite: "Aprobación del comité", tomar_respaldo: "Tomar respaldo",
  reservar_ventana: "Reservar ventana", desplegar_prod: "Despliegue en producción (plataforma)", verificar_prod: "Verificar en producción", liberar_ventana: "Liberar ventana",
};
const CON_FALLA = new Set(["correr_pruebas", "desplegar_qa", "pruebas_integracion", "tomar_respaldo", "desplegar_prod", "verificar_prod"]);
const ETAPAS = ["Guardrail", "Reglas", "Enmascaramiento", "Revisor", "Normas", "Fiscalizador", "Veredicto"];

export function Detalle({ id, actor, alCambiar }: { id: string; actor: string; alCambiar: () => void }) {
  const [p, setP] = useState<Paquete | null>(null);
  const [error, setError] = useState("");
  const [pestana, setPestana] = useState("revision");
  const [job, setJob] = useState<Trabajo | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [comentario, setComentario] = useState("");
  const cargar = useCallback(() => api.get<Paquete>(`/paquetes/${id}`).then(setP).catch((e) => setError(e.message)), [id]);
  useEffect(() => { cargar(); }, [cargar]);
  const accion = async (f: () => Promise<unknown>) => {
    setError(""); setOcupado(true);
    try { await f(); setComentario(""); await cargar(); alCambiar(); }
    catch (e) { setError((e as Error).message); }
    setOcupado(false);
  };
  const revisar = () => accion(async () => {
    setPestana("revision");
    const t = await api.post<Trabajo>(`/paquetes/${id}/revisar`);
    setJob(t);
    await cargar();
    const fin = await esperarTrabajo(t.id, setJob);
    setJob(null);
    if (fin.error) throw new Error(fin.error);
  });
  if (!p) return error ? <p className="error" role="alert">{error}</p> : <div className="esqueleto" />;
  const puedeRevisar = ["borrador", "rechazado", "devuelto", "por_aprobar"].includes(p.estado) && !job;
  const rev = p.revision;
  return (
    <>
      <a className="migas" href="#/bandeja">Bandeja</a>
      <div className="titulo-fila">
        <div><h1>{p.titulo}</h1><div className="sutil">{p.id} · versión {p.version} · {p.autor} · célula {p.celula} · {p.origen} → {p.destino}</div></div>
        <div className="acciones">
          {!["aprobado", "en_promocion", "promovido", "en_revision"].includes(p.estado) && <a className="boton" href={`#/paquete/${id}/editar`}>Editar</a>}
          <button className={p.estado === "borrador" || p.estado === "devuelto" ? "primario" : ""} disabled={!puedeRevisar || ocupado} onClick={revisar}>{rev ? "Revisar de nuevo" : "Revisar paquete"}</button>
        </div>
      </div>
      <div className="resumen-estado"><Etiqueta estado={p.estado} /><span className={"imp i-" + p.impacto}>Impacto {p.impacto}</span>
        {p.requisitos.firmas > 1 && <span className="sutil">Requiere {p.requisitos.firmas} firmas{p.requisitos.arquitectura ? ", una de arquitectura" : ""}{p.requisitos.certificacion_datos ? ", una con certificación de datos" : ""}</span>}</div>
      {error && <p className="error" role="alert">{error}</p>}
      {job && <Progreso job={job} />}
      <div className="pestanas" role="tablist">
        {[["revision", "Revisión"], ["contenido", "Contenido"], ["plan", "Plan"], ["historial", "Historial"]].map(([k, n]) =>
          <button key={k} role="tab" aria-selected={pestana === k} className={pestana === k ? "sel" : ""} onClick={() => setPestana(k)}>{n}</button>)}
      </div>
      {pestana === "revision" && (
        <div className="dos-col">
          <div>
            {!rev ? <div className="vacio"><p>Este paquete aún no se revisa.</p><p>La revisión corre las reglas, oculta datos sensibles, consulta al modelo y deja el veredicto listo para una persona.</p></div> : (
              <>
                {rev.nota && <p className="aviso">{rev.nota}</p>}
                <h2>Hallazgos <span className="sutil">{rev.modelo ? `${rev.modelo} · ${rev.segundos} s · ${rev.tokens} tokens · USD ${rev.usd.toFixed(4)}` : "solo reglas"}</span></h2>
                {rev.hallazgos.length === 0 ? <p>Sin defectos. Falta la decisión humana.</p> : <ul className="hallazgos">{rev.hallazgos.map((h) => <FilaHallazgo key={h.codigo} h={h} id={id} actor={actor} accion={accion} />)}</ul>}
                {(rev.avisos.length > 0 || rev.fiscal.length > 0) && <><h2>Avisos para la persona que revisa</h2><ul className="avisos">{[...rev.avisos, ...rev.fiscal].map((a) => <li key={a}>{a}</li>)}</ul></>}
                {rev.explicacion && <><h2>Explicación para el autor</h2><p className="prosa">{rev.explicacion}</p></>}
                {rev.normas.length > 0 && <><h2>Normas relacionadas</h2><ul className="normas-ref">{rev.normas.map((n) => <li key={n.id}><b>{n.id}</b> v{n.version}{rev.citadas.includes(n.id) && <span className="citada">citada</span>} {n.texto}</li>)}</ul></>}
              </>
            )}
          </div>
          <aside className="panel-decision">
            <h2>Decisión</h2>
            {p.aprobaciones.length > 0 && <ul className="firmas">{p.aprobaciones.map((a) => <li key={a.revisor}><b>{a.nombre}</b><span className="sutil">{fecha(a.fecha)}</span>{a.comentario && <div>{a.comentario}</div>}</li>)}</ul>}
            {["por_aprobar", "rechazado"].includes(p.estado) ? (
              <>
                {p.estado === "por_aprobar" && p.faltan.length > 0 && <p className="sutil">Falta: {p.faltan.join(", ")}.</p>}
                {!actor && <p className="aviso">Elige arriba quién está actuando.</p>}
                <label>Comentario<textarea rows={3} value={comentario} onChange={(e) => setComentario(e.target.value)} placeholder="Qué revisaste o qué debe corregir el autor" /></label>
                <div className="acciones">
                  <button className="primario" disabled={!actor || ocupado || p.estado === "rechazado"} onClick={() => accion(() => api.post(`/paquetes/${id}/decision`, { accion: "aprobar", actor, comentario }))}>Aprobar</button>
                  <button disabled={!actor || ocupado} onClick={() => accion(() => api.post(`/paquetes/${id}/decision`, { accion: "devolver", actor, comentario }))}>Devolver</button>
                </div>
                {p.estado === "rechazado" && <p className="sutil">No se puede aprobar con bloqueantes abiertos.</p>}
              </>
            ) : <p className="sutil">{p.estado === "borrador" ? "Primero hay que revisarlo." : p.estado === "devuelto" ? "Devuelto al autor: debe corregir y revisar de nuevo." : `Estado: ${ESTADOS[p.estado]}.`}</p>}
            <p className="sutil pie">Atalaya propone; decide una persona. Nunca despliega.</p>
          </aside>
        </div>
      )}
      {pestana === "contenido" && (
        <div className="bloques">
          {([["Historia", p.hu], ["Contrato", p.contrato], ["Muestra", p.muestra], ["Código", p.etl]] as const).map(([n, v]) => <details key={n} open><summary>{n}</summary><pre>{v}</pre></details>)}
          <details><summary>Lo que se envió al modelo{rev ? "" : " (aún nada)"}</summary><pre>{rev?.enviado ?? "Sin envíos todavía."}</pre></details>
        </div>
      )}
      {pestana === "plan" && <PlanVista p={p} actor={actor} ocupado={ocupado} accion={accion} />}
      {pestana === "historial" && (
        <div className="tabla-marco"><table><thead><tr><th>Fecha</th><th>Quién</th><th>Acción</th><th>Detalle</th></tr></thead>
          <tbody>{p.auditoria.map((a) => <tr key={a.n}><td className="sutil">{fecha(a.fecha)}</td><td>{a.actor}</td><td>{a.accion.replaceAll("_", " ")}</td><td className="sutil detalle-json">{JSON.stringify(a.detalle)}</td></tr>)}</tbody></table></div>
      )}
    </>
  );
}

function Progreso({ job }: { job: Trabajo }) {
  const hechas = new Set(job.etapas.map((e) => e.etapa));
  const ultima = job.etapas.at(-1);
  return (
    <div className="progreso" role="status" aria-live="polite">
      <ol>{ETAPAS.map((e) => <li key={e} className={hechas.has(e) ? "hecha" : ""}>{e}</li>)}</ol>
      <p className="sutil">{ultima ? `${ultima.etapa}: ${ultima.detalle}` : "En cola."}</p>
    </div>
  );
}

function FilaHallazgo({ h, id, actor, accion }: { h: Hallazgo; id: string; actor: string; accion: (f: () => Promise<unknown>) => void }) {
  const [abierto, setAbierto] = useState(false);
  const [motivo, setMotivo] = useState("");
  return (
    <li className={h.descartado ? "descartado" : ""}>
      <div className="h-cab"><span className={"origen o-" + h.origen}>{h.origen}</span><code>{h.codigo}</code>{h.bloqueante && !h.descartado && <span className="rojo">bloqueante</span>}{!h.confirmado && <span className="ambar">sin cita exacta</span>}{h.descartado && <span className="sutil">descartado</span>}</div>
      <div>{h.descripcion}</div>
      {h.evidencia && <pre className="evidencia">{h.evidencia}</pre>}
      {h.origen === "modelo" && !h.descartado && (abierto ? (
        <div className="descartar"><input aria-label="Motivo" placeholder="Por qué no aplica" value={motivo} onChange={(e) => setMotivo(e.target.value)} />
          <button disabled={!actor || !motivo.trim()} onClick={() => accion(() => api.post(`/paquetes/${id}/hallazgos/${h.codigo}/descartar`, { actor, motivo }))}>Confirmar</button><button className="sin-borde" onClick={() => setAbierto(false)}>Cancelar</button></div>
      ) : <button className="sin-borde" onClick={() => setAbierto(true)}>Descartar</button>)}
    </li>
  );
}

function PlanVista({ p, actor, ocupado, accion }: { p: Paquete; actor: string; ocupado: boolean; accion: (f: () => Promise<unknown>) => void }) {
  const [falla, setFalla] = useState<string | null>(null);
  const [motivo, setMotivo] = useState("");
  if (!p.plan) return <div className="vacio"><p>El plan se crea cuando el paquete recibe todas sus firmas.</p></div>;
  const plan = p.plan;
  const siguiente = plan.pendientes[0];
  return (
    <>
      <p className="sutil">{plan.metodo}{plan.replanificaciones > 0 ? ` · replanificado ${plan.replanificaciones} vez/veces` : ""} · cada paso lo registra una persona y el validador rechaza lo imposible.</p>
      {!actor && <p className="aviso">Elige arriba quién está actuando.</p>}
      <ol className="plan">
        {plan.hechas.map((h, i) => <li key={i} className="hecho"><span className="marca-paso">✓</span><div><b>{PASOS[h.accion] ?? h.accion}</b><div className="sutil">{h.actor} · {fecha(h.fecha)}</div></div>
          {CON_FALLA.has(h.accion) && plan.pendientes.length > 0 && <button className="sin-borde" onClick={() => setFalla(h.accion)}>Registrar falla</button>}</li>)}
        {plan.pendientes.map((a) => <li key={a} className={a === siguiente ? "siguiente" : ""}><span className="marca-paso" /><div><b>{PASOS[a] ?? a}</b></div>
          {a === siguiente && <button className="primario" disabled={!actor || ocupado} onClick={() => accion(() => api.post(`/paquetes/${p.id}/plan/paso`, { accion: a, actor }))}>Marcar hecho</button>}</li>)}
      </ol>
      {plan.pendientes.length === 0 && <p>Promoción terminada.</p>}
      {falla && <div className="panel"><h2>Falla en: {PASOS[falla]}</h2><label>Motivo<input value={motivo} onChange={(e) => setMotivo(e.target.value)} /></label>
        <div className="acciones"><button className="primario" disabled={!actor || !motivo.trim() || ocupado} onClick={() => { accion(() => api.post(`/paquetes/${p.id}/plan/falla`, { accion: falla, actor, motivo })); setFalla(null); setMotivo(""); }}>Replanificar</button><button onClick={() => setFalla(null)}>Cancelar</button></div></div>}
    </>
  );
}

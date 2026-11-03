import { useEffect, useState } from "react";
import { api, fecha, type RegistroAud } from "../api";

export function Auditoria() {
  const [d, setD] = useState<{ registros: RegistroAud[]; cadena: { integra: boolean; registros: number; falla_en: number | null } } | null>(null);
  const [filtro, setFiltro] = useState("");
  const [error, setError] = useState("");
  const cargar = () => api.get<NonNullable<typeof d>>("/auditoria").then(setD).catch((e) => setError(e.message));
  useEffect(() => { cargar(); }, []);
  const q = filtro.toLowerCase();
  const filas = d?.registros.filter((r) => !q || [r.actor, r.accion, r.objeto].some((x) => x.toLowerCase().includes(q))) ?? [];
  return (
    <>
      <div className="titulo-fila"><h1>Auditoría</h1><div className="acciones"><button onClick={cargar}>Verificar cadena</button></div></div>
      {error && <p className="error" role="alert">{error}</p>}
      {d && <div className={"resultado " + (d.cadena.integra ? "r-ok" : "r-mal")}><b>{d.cadena.integra ? `Cadena íntegra: ${d.cadena.registros} registros verificados.` : `Cadena alterada en el registro ${d.cadena.falla_en}.`}</b>
        <div className="sutil">Cada registro incluye la huella del anterior: alterar uno rompe la cadena desde ese punto.</div></div>}
      <input className="buscador" aria-label="Filtrar" placeholder="Filtrar por persona, acción o paquete" value={filtro} onChange={(e) => setFiltro(e.target.value)} />
      {!d ? <div className="esqueleto" /> : filas.length === 0 ? <div className="vacio"><p>Sin registros para ese filtro.</p></div> : (
        <div className="tabla-marco"><table><thead><tr><th className="num">N.º</th><th>Fecha</th><th>Quién</th><th>Acción</th><th>Objeto</th><th>Detalle</th><th>Huella</th></tr></thead>
          <tbody>{filas.map((r) => <tr key={r.n}><td className="num">{r.n}</td><td className="sutil">{fecha(r.fecha)}</td><td>{r.actor}</td><td>{r.accion.replaceAll("_", " ")}</td>
            <td>{r.objeto.startsWith("PKG") ? <a href={`#/paquete/${r.objeto}`}>{r.objeto}</a> : r.objeto}</td><td className="sutil detalle-json">{JSON.stringify(r.detalle)}</td><td><code>{r.hash.slice(0, 10)}</code></td></tr>)}</tbody></table></div>
      )}
    </>
  );
}

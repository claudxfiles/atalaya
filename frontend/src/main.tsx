import "@fontsource-variable/archivo/wdth.css";
import { StrictMode, useCallback, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { api, type Revisor, type Salud } from "./api";
import { Agente } from "./features/Agente";
import { Ajustes } from "./features/Ajustes";
import { Asignaciones } from "./features/Asignaciones";
import { Auditoria } from "./features/Auditoria";
import { Bandeja } from "./features/Bandeja";
import { Detalle } from "./features/Detalle";
import { Formulario } from "./features/Formulario";
import { Normas } from "./features/Normas";
import "./estilos.css";

const NAV = [
  { id: "bandeja", paso: "01", nombre: "Bandeja" },
  { id: "asignacion", paso: "02", nombre: "Asignación" },
  { id: "agente", paso: "03", nombre: "Agente" },
  { id: "normas", paso: "04", nombre: "Normas" },
  { id: "auditoria", paso: "05", nombre: "Auditoría" },
];

function leerRuta() {
  return window.location.hash.replace(/^#\/?/, "") || "bandeja";
}
export const ir = (ruta: string) => { window.location.hash = "/" + ruta; };

function App() {
  const [ruta, setRuta] = useState(leerRuta());
  const [revisores, setRevisores] = useState<Revisor[]>([]);
  const [salud, setSalud] = useState<Salud | null>(null);
  const [actor, setActorS] = useState(() => { try { return localStorage.getItem("actor") || ""; } catch { return ""; } });
  const setActor = (v: string) => { setActorS(v); try { localStorage.setItem("actor", v); } catch { /* sin almacenamiento */ } };
  const cargarRevisores = useCallback(() => { api.get<Revisor[]>("/revisores").then(setRevisores).catch(() => {}); }, []);
  const cargarSalud = useCallback(() => { api.get<Salud>("/salud").then(setSalud).catch(() => setSalud(null)); }, []);
  useEffect(() => {
    const f = () => setRuta(leerRuta());
    window.addEventListener("hashchange", f);
    cargarRevisores();
    cargarSalud();
    const t = setInterval(cargarSalud, 15000);
    return () => { window.removeEventListener("hashchange", f); clearInterval(t); };
  }, [cargarRevisores, cargarSalud]);
  const [seccion, id, sub] = ruta.split("/");
  const activa = seccion === "paquete" || seccion === "nuevo" ? "bandeja" : seccion;
  return (
    <div className="app">
      <aside className="lateral">
        <div className="logo"><img src="/logo_uai.png" alt="Facultad de Ingeniería y Ciencias, Universidad Adolfo Ibáñez" /></div>
        <div className="marca">Atalaya Studio</div>
        <nav aria-label="Principal">
          {NAV.map((n) => (
            <a key={n.id} href={`#/${n.id}`} className={activa === n.id ? "activo" : ""} aria-current={activa === n.id ? "page" : undefined}><span>{n.paso}</span>{n.nombre}</a>
          ))}
        </nav>
        <a href="#/ajustes" className={"ajustes" + (activa === "ajustes" ? " activo" : "")}>Ajustes</a>
      </aside>
      <div className="contenido">
        <header className="barra">
          <label className="actuando">Actuando como
            <select value={actor} onChange={(e) => setActor(e.target.value)}>
              <option value="">Elige una persona</option>
              {revisores.map((r) => <option key={r.id} value={r.id}>{r.nombre} · {r.roles.join(", ")}</option>)}
            </select>
          </label>
          <div className="estado-modelo" role="status">
            {salud === null ? <span className="pto pto-mal" /> : <span className={"pto " + (salud.modelo && salud.gasto_hoy < salud.tope ? "pto-ok" : "pto-aviso")} />}
            {salud === null ? "Servicio sin conexión" : !salud.modelo ? "Sin modelo: solo reglas" : salud.gasto_hoy >= salud.tope ? "Tope diario alcanzado: solo reglas" : `Modelo activo · USD ${salud.gasto_hoy.toFixed(3)} de ${salud.tope.toFixed(2)} hoy`}
          </div>
        </header>
        <main>
          {seccion === "bandeja" && <Bandeja />}
          {seccion === "nuevo" && <Formulario />}
          {seccion === "paquete" && sub === "editar" && <Formulario id={id} />}
          {seccion === "paquete" && !sub && <Detalle key={id} id={id} actor={actor} alCambiar={cargarSalud} />}
          {seccion === "asignacion" && <Asignaciones actor={actor} revisores={revisores} recargarRevisores={cargarRevisores} />}
          {seccion === "agente" && <Agente paquete={null} alCambiar={cargarSalud} />}
          {seccion === "normas" && <Normas />}
          {seccion === "auditoria" && <Auditoria />}
          {seccion === "ajustes" && <Ajustes alCambiar={cargarSalud} />}
        </main>
      </div>
    </div>
  );
}

createRoot(document.getElementById("raiz")!).render(<StrictMode><App /></StrictMode>);

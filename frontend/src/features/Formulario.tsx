import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import { api, type Paquete } from "../api";

const VACIO = {
  titulo: "", autor: "", revisor_propuesto: "", celula: 0, origen: "qa", destino: "prod", pruebas: "", plazo_dias: 3,
  hu: "# Historia\nComo ... necesito ...\n\n## Criterios de aceptación\n- ",
  contrato: '{\n  "tabla": "",\n  "llave_primaria": "",\n  "retencion_anios": 5,\n  "columnas": [\n    {"nombre": "", "tipo": "string", "dato_personal": false}\n  ]\n}',
  muestra: "", etl: "",
};

function Cargable({ nombre, etiqueta, valor, ayuda, alto, alCambiar }: { nombre: string; etiqueta: string; valor: string; ayuda: string; alto: number; alCambiar: (v: string) => void }) {
  const leer = async (e: ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) alCambiar(await f.text());
    e.target.value = "";
  };
  return (
    <div className="campo">
      <div className="campo-cab">
        <label htmlFor={nombre}>{etiqueta}</label>
        <label className="boton chico">Cargar archivo<input type="file" onChange={leer} hidden /></label>
      </div>
      <p className="ayuda">{ayuda}</p>
      <textarea id={nombre} className="codigo" rows={alto} value={valor} spellCheck={false} onChange={(e) => alCambiar(e.target.value)} />
    </div>
  );
}

export function Formulario({ id }: { id?: string }) {
  const [d, setD] = useState(VACIO);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  useEffect(() => {
    if (id) api.get<Paquete>(`/paquetes/${id}`).then((p) => setD({ ...VACIO, ...p, pruebas: (p.pruebas || []).join("\n"), revisor_propuesto: p.revisor_propuesto || "" })).catch((e) => setError(e.message));
  }, [id]);
  const fijar = <K extends keyof typeof VACIO>(k: K, v: (typeof VACIO)[K]) => setD((x) => ({ ...x, [k]: v }));
  const enviar = async (e: FormEvent) => {
    e.preventDefault();
    setEnviando(true);
    setError("");
    const cuerpo = { titulo: d.titulo, autor: d.autor, revisor_propuesto: d.revisor_propuesto, celula: Number(d.celula), origen: d.origen, destino: d.destino, plazo_dias: Number(d.plazo_dias),
      pruebas: String(d.pruebas).split("\n").map((s) => s.trim()).filter(Boolean), hu: d.hu, contrato: d.contrato, muestra: d.muestra, etl: d.etl };
    try {
      const p = id ? await api.put<Paquete>(`/paquetes/${id}`, cuerpo) : await api.post<Paquete>("/paquetes", cuerpo);
      window.location.hash = `/paquete/${p.id}`;
    } catch (ex) { setError((ex as Error).message); setEnviando(false); }
  };
  return (
    <form onSubmit={enviar} className="formulario">
      <div className="titulo-fila">
        <h1>{id ? "Editar paquete" : "Nuevo paquete"}</h1>
        <div className="acciones"><a className="boton" href={id ? `#/paquete/${id}` : "#/bandeja"}>Cancelar</a><button className="primario" disabled={enviando}>{enviando ? "Guardando" : "Guardar paquete"}</button></div>
      </div>
      <p className="aviso">Usa solo datos de prueba. Antes de llamar al modelo se ocultan RUT, correos y secretos, pero el resto del texto sale hacia la API de OpenAI.</p>
      {id && <p className="aviso">Guardar crea una versión nueva: se borran las firmas y hay que revisar de nuevo.</p>}
      {error && <p className="error" role="alert">{error}</p>}
      <div className="rejilla">
        <label className="ancho-2">Título<input required minLength={3} value={d.titulo} onChange={(e) => fijar("titulo", e.target.value)} /></label>
        <label>Autor<input required minLength={2} value={d.autor} onChange={(e) => fijar("autor", e.target.value)} /></label>
        <label>Revisor propuesto<input value={d.revisor_propuesto} onChange={(e) => fijar("revisor_propuesto", e.target.value)} /></label>
        <label>Célula del autor<input type="number" min={0} max={20} value={d.celula} onChange={(e) => fijar("celula", Number(e.target.value))} /></label>
        <label>Origen<select value={d.origen} onChange={(e) => fijar("origen", e.target.value)}><option value="dev">dev</option><option value="qa">qa</option></select></label>
        <label>Destino<select value={d.destino} onChange={(e) => fijar("destino", e.target.value)}><option value="qa">qa</option><option value="prod">prod</option></select></label>
        <label>Plazo (días hábiles)<input type="number" min={1} max={5} value={d.plazo_dias} onChange={(e) => fijar("plazo_dias", Number(e.target.value))} /></label>
      </div>
      <div className="campo"><label htmlFor="pruebas">Pruebas automatizadas</label><p className="ayuda">Una ruta por línea. Sin pruebas se registra un hallazgo.</p>
        <textarea id="pruebas" className="codigo" rows={2} value={d.pruebas} onChange={(e) => fijar("pruebas", e.target.value)} /></div>
      <Cargable nombre="hu" etiqueta="Historia de usuario" ayuda="Debe incluir una sección de criterios de aceptación." alto={8} valor={d.hu} alCambiar={(v) => fijar("hu", v)} />
      <Cargable nombre="contrato" etiqueta="Contrato de datos (JSON)" ayuda="Tabla, llave primaria, retención y columnas con su clasificación." alto={9} valor={d.contrato} alCambiar={(v) => fijar("contrato", v)} />
      <Cargable nombre="muestra" etiqueta="Muestra (CSV)" ayuda="Primera fila con los nombres de columna." alto={6} valor={d.muestra} alCambiar={(v) => fijar("muestra", v)} />
      <Cargable nombre="etl" etiqueta="Código" ayuda="Python, PySpark o SQL del proceso." alto={12} valor={d.etl} alCambiar={(v) => fijar("etl", v)} />
    </form>
  );
}

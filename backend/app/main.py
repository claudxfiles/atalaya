"""API de Atalaya Studio y entrega de la interfaz compilada."""
from __future__ import annotations

import pathlib
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from . import agente, almacen, dominio, flujo, modelos, normas

@asynccontextmanager
async def _ciclo(_: FastAPI):
    almacen.iniciar()
    flujo.sembrar()
    # Un reinicio no debe dejar paquetes colgados.
    for p in almacen.paquetes():
        if p["estado"] == "en_revision":
            p["estado"] = "borrador"
            almacen.guardar_paquete(p)
    yield


app = FastAPI(title="Atalaya Studio", docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None, lifespan=_ciclo)
DIST = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "dist"


class Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PaqueteE(Base):
    titulo: str = Field(min_length=3, max_length=200)
    autor: str = Field(min_length=2, max_length=100)
    revisor_propuesto: str = Field(default="", max_length=100)
    celula: int = Field(ge=0, le=20)
    origen: Literal["dev", "qa"]
    destino: Literal["qa", "prod"]
    pruebas: list[str] = []
    plazo_dias: int = Field(default=3, ge=1, le=5)
    hu: str = Field(default="", max_length=60000)
    contrato: str = Field(default="", max_length=60000)
    muestra: str = Field(default="", max_length=60000)
    etl: str = Field(default="", max_length=120000)


class SinteticoE(Base):
    perfil: Literal["correcto", "credencial", "sobrescribe", "funciones", "rut", "inyeccion"]


class Actor(Base):
    actor: str


class DecisionE(Actor):
    accion: Literal["aprobar", "devolver"]
    comentario: str = Field(default="", max_length=2000)


class DescarteE(Actor):
    motivo: str = Field(max_length=2000)


class PasoE(Actor):
    accion: str


class FallaE(PasoE):
    motivo: str = Field(max_length=2000)


class RevisorE(Base):
    nombre: str = Field(min_length=2, max_length=100)
    roles: list[Literal["calidad", "arquitectura", "privacidad", "gobierno"]] = Field(min_length=1)
    celula: int = Field(ge=0, le=20)
    cert_datos: bool = False
    disponible: int = Field(default=0, ge=0, le=160)
    capacidad: int = Field(default=128, ge=0, le=160)


class AusenciaE(Base):
    revisor: str
    desde_dia: int = Field(ge=0, le=4)
    hasta_dia: int = Field(ge=0, le=4)


class ReasignaE(Actor):
    tarea: str
    revisor: str
    inicio: int = Field(ge=0, le=160)


class NormaE(Base):
    texto: str = Field(min_length=5, max_length=4000)
    vigente: bool = True
    actor: str = "Administración"


class MensajeE(Base):
    sesion: str = Field(min_length=1, max_length=60)
    texto: str = Field(min_length=1, max_length=4000)
    paquete: str | None = None


class AjustesE(Base):
    tope_diario_usd: float = Field(ge=0, le=100)


@app.exception_handler(flujo.ReglaFlujo)
def regla(_: Request, e: flujo.ReglaFlujo) -> JSONResponse:
    return JSONResponse({"detail": str(e)}, 409)


@app.exception_handler(KeyError)
def no_existe(_: Request, e: KeyError) -> JSONResponse:
    return JSONResponse({"detail": "No existe ese registro."}, 404)


def _nombre(actor_id: str) -> str:
    v = almacen.obtener_doc("revisores", actor_id)
    return v["nombre"] if v else "Usuario"


@app.get("/api/salud")
def salud() -> dict:
    return {"ok": True, "modelo": modelos.disponible(), "gasto_hoy": round(almacen.gasto_hoy(), 5), "tope": modelos.tope(), "revisor": modelos.MODELO_REVISOR, "triaje": modelos.MODELO_TRIAJE}


# ---------- Paquetes ----------
def _resumen(p: dict) -> dict:
    rev = flujo.revision_actual(p)
    return {**{k: p.get(k) for k in ("id", "titulo", "autor", "estado", "impacto", "version", "celula", "origen", "destino", "actualizado", "sintetico")},
            "hallazgos": len(rev["hallazgos"]) if rev else None, "bloqueantes": len(flujo.bloqueantes_abiertos(p, rev)), "avisos": len(rev["avisos"]) + len(rev["fiscal"]) if rev else 0, "faltan": flujo.faltan_firmas(p) if p["estado"] == "por_aprobar" else []}


@app.get("/api/paquetes")
def listar_paquetes() -> list[dict]:
    return [_resumen(p) for p in almacen.paquetes()]


@app.post("/api/paquetes", status_code=201)
def crear(d: PaqueteE) -> dict:
    return flujo.crear_paquete(d.model_dump(), d.autor)


@app.post("/api/paquetes/sintetico", status_code=201)
def crear_sintetico(d: SinteticoE) -> dict:
    return flujo.crear_paquete(dominio.sintetico(d.perfil), "Atalaya")


@app.get("/api/paquetes/{id_}")
def ver_paquete(id_: str) -> dict:
    p = almacen.paquete(id_)
    if not p:
        raise HTTPException(404, "No existe ese paquete.")
    rev = flujo.revision_actual(p)
    hallazgos = [{**h, "descripcion": dominio.DEFECTOS[h["codigo"]][0], "bloqueante": dominio.DEFECTOS[h["codigo"]][1], "descartado": h["codigo"] in p["descartes"]} for h in rev["hallazgos"]] if rev else []
    return {**p, "revision": {**rev, "hallazgos": hallazgos} if rev else None, "hechos_previos": dominio.hechos(p), "plan": flujo.plan_de(id_), "requisitos": flujo.requisitos(p), "faltan": flujo.faltan_firmas(p),
            "decisiones": almacen.por_paquete("decisiones", id_), "auditoria": almacen.auditoria(40, id_)}


@app.put("/api/paquetes/{id_}")
def editar(id_: str, d: PaqueteE) -> dict:
    return flujo.editar_paquete(id_, d.model_dump(), d.autor)


@app.post("/api/paquetes/{id_}/revisar", status_code=202)
def revisar(id_: str) -> dict:
    return flujo.revisar(id_, "Usuario")


@app.post("/api/paquetes/{id_}/decision")
def decidir(id_: str, d: DecisionE) -> dict:
    return flujo.decidir(id_, d.accion, d.actor, d.comentario)


@app.post("/api/paquetes/{id_}/hallazgos/{codigo}/descartar")
def descartar(id_: str, codigo: str, d: DescarteE) -> dict:
    return flujo.descartar_hallazgo(id_, codigo, d.actor, d.motivo)


@app.post("/api/paquetes/{id_}/plan/paso")
def paso(id_: str, d: PasoE) -> dict:
    return flujo.paso_plan(id_, d.accion, d.actor)


@app.post("/api/paquetes/{id_}/plan/falla")
def falla(id_: str, d: FallaE) -> dict:
    return flujo.fallo_plan(id_, d.accion, d.actor, d.motivo)


@app.get("/api/trabajos/{id_}")
def ver_trabajo(id_: str) -> dict:
    t = flujo.trabajo(id_)
    if not t:
        raise HTTPException(404, "No existe ese trabajo.")
    return t


# ---------- Asignacion ----------
@app.get("/api/revisores")
def revisores() -> list[dict]:
    return sorted(almacen.listar_docs("revisores"), key=lambda v: v["id"])


@app.post("/api/revisores", status_code=201)
def crear_revisor(d: RevisorE) -> dict:
    id_ = almacen.nuevo_id("REV")
    almacen.guardar_doc("revisores", id_, d.model_dump())
    almacen.auditar("Coordinación", "revisor_creado", id_, {"nombre": d.nombre})
    return {"id": id_, **d.model_dump()}


@app.put("/api/revisores/{id_}")
def editar_revisor(id_: str, d: RevisorE) -> dict:
    if not almacen.obtener_doc("revisores", id_):
        raise HTTPException(404, "No existe ese revisor.")
    almacen.guardar_doc("revisores", id_, d.model_dump())
    almacen.auditar("Coordinación", "revisor_editado", id_, {"nombre": d.nombre})
    return {"id": id_, **d.model_dump()}


@app.get("/api/restricciones")
def restricciones() -> list[dict]:
    return almacen.listar_docs("restricciones")


@app.post("/api/restricciones", status_code=201)
def crear_restriccion(d: AusenciaE) -> dict:
    if d.desde_dia > d.hasta_dia:
        raise HTTPException(422, "El día inicial no puede ser posterior al final.")
    v = almacen.obtener_doc("revisores", d.revisor)
    if not v:
        raise HTTPException(404, "No existe ese revisor.")
    id_ = almacen.nuevo_id("RES")
    doc = {"tipo": "ausencia", "revisor": d.revisor, "nombre": v["nombre"], "desde_dia": d.desde_dia, "hasta_dia": d.hasta_dia}
    almacen.guardar_doc("restricciones", id_, doc)
    almacen.auditar("Coordinación", "restriccion_confirmada", id_, doc)
    return {"id": id_, **doc}


@app.delete("/api/restricciones/{id_}")
def borrar_restriccion(id_: str) -> dict:
    almacen.borrar_doc("restricciones", id_)
    almacen.auditar("Coordinación", "restriccion_retirada", id_, {})
    return {"ok": True}


@app.get("/api/asignacion")
def ver_asignacion() -> dict:
    return {"tareas_pendientes": flujo.tareas_pendientes(), "vigente": flujo.asignacion_vigente()}


@app.post("/api/asignacion/calcular", status_code=202)
def calcular() -> dict:
    return flujo.calcular_asignacion("Coordinación")


@app.post("/api/asignacion/{id_}/publicar")
def publicar(id_: str) -> dict:
    return flujo.publicar_asignacion(id_, "Coordinación")


@app.post("/api/asignacion/{id_}/ajustar")
def ajustar(id_: str, d: ReasignaE) -> dict:
    return flujo.reasignar(id_, d.tarea, d.revisor, d.inicio, _nombre(d.actor))


# ---------- Agente ----------
@app.get("/api/agente/{sesion}")
def ver_chat(sesion: str) -> list[dict]:
    return agente.historial(sesion)


@app.post("/api/agente")
def conversar(d: MensajeE) -> dict:
    return agente.conversar(d.sesion, d.texto, d.paquete)


# ---------- Normas, auditoria, ajustes ----------
@app.get("/api/normas")
def ver_normas() -> list[dict]:
    return normas.listar(False)


@app.get("/api/normas/buscar")
def buscar_normas(q: str) -> dict:
    r, metodo = normas.buscar(q)
    return {"metodo": metodo, "normas": r}


@app.post("/api/normas", status_code=201)
def crear_norma(d: NormaE) -> dict:
    return normas.guardar(None, d.texto, d.vigente, d.actor)


@app.put("/api/normas/{id_}")
def editar_norma(id_: str, d: NormaE) -> dict:
    return normas.guardar(id_, d.texto, d.vigente, d.actor)


@app.get("/api/auditoria")
def ver_auditoria() -> dict:
    return {"registros": almacen.auditoria(), "cadena": almacen.verificar_auditoria()}


@app.get("/api/uso")
def uso() -> dict:
    por = [dict(f) for f in almacen.filas("SELECT substr(fecha,1,10) AS dia, modelo, COUNT(*) AS llamadas, SUM(entrada) AS entrada, SUM(salida) AS salida, ROUND(SUM(usd),5) AS usd FROM uso GROUP BY dia, modelo ORDER BY dia DESC, modelo")]
    return {"por_dia": por, "gasto_hoy": round(almacen.gasto_hoy(), 5), "tope": modelos.tope()}


@app.put("/api/ajustes")
def ajustes(d: AjustesE) -> dict:
    almacen.fijar_ajuste("tope_diario_usd", d.tope_diario_usd)
    almacen.auditar("Administración", "tope_actualizado", "ajustes", {"tope": d.tope_diario_usd})
    return {"tope": d.tope_diario_usd}


if (DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")


@app.get("/{ruta:path}", include_in_schema=False)
def interfaz(ruta: str) -> FileResponse:
    if ruta.startswith("api/"):
        raise HTTPException(404, "No existe esa ruta.")
    candidato = (DIST / ruta).resolve()
    if ruta and candidato.is_file() and DIST.resolve() in candidato.parents:
        return FileResponse(candidato)
    if not (DIST / "index.html").exists():
        raise HTTPException(503, "La interfaz no está compilada.")
    return FileResponse(DIST / "index.html", headers={"Cache-Control": "no-cache"})

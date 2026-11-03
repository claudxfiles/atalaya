"""Base de normas: versionadas, con cita, y busqueda por embeddings con respaldo lexico si no hay modelo."""
from __future__ import annotations

import json
import math
import re
from collections import Counter

from . import almacen, modelos

# Normas ficticias de Banco Cordillera, para que la aplicacion tenga contenido desde el primer uso.
SEMILLA = {
    "N01": "Todo paquete que trate datos personales debe contar con revisión de la Oficina de Privacidad antes del comité de cambios.",
    "N02": "La retención por defecto de tablas transaccionales es de cinco años, salvo mandato legal que exija un plazo mayor.",
    "N03": "Los ambientes de desarrollo no pueden contener RUT reales; se usan valores enmascarados.",
    "N04": "Un autor no puede aprobar su propio cambio ni el de un integrante de su misma célula.",
    "N05": "Las ventanas de despliegue a producción se abren martes y jueves de 21:00 a 23:00, salvo cambios de emergencia.",
    "N06": "Durante el cierre contable, los últimos tres días hábiles del mes, se congelan los despliegues sobre tablas financieras.",
    "N07": "Un cambio de emergencia requiere aprobación del gerente de turno y revisión posterior dentro de 48 horas.",
    "N08": "Toda credencial se almacena en el gestor de secretos; nunca en código ni en cadenas de conexión.",
    "N09": "Antes de desplegar en producción se debe tomar un respaldo verificable de la tabla afectada.",
    "N10": "Los productos de datos deben publicar su contrato y mantener todas las columnas que este exige.",
    "N11": "Los procesos de transformación deben referenciar pruebas automatizadas; la cobertura mínima en procesos críticos es de 70 por ciento.",
    "N12": "Los modelos de lenguaje externos solo reciben metadatos, esquemas y muestras enmascaradas.",
    "N14": "Las consultas deben listar sus columnas; no se permite SELECT * sobre tablas de origen.",
    "N15": "Un incidente de severidad uno se notifica a Riesgo Operacional dentro de 30 minutos desde su detección.",
    "N17": "La documentación de arquitectura es obligatoria para todo cambio de impacto alto. Cada historia debe tener criterios de aceptación.",
    "N20": "El código debe cumplir la historia aprobada: modo de carga, unidad monetaria y registros incluidos. Los procesos financieros concilian totales de control.",
    "N22": "Los errores de un proceso deben registrarse y relanzarse; no se permite silenciarlos.",
    "N24": "La revisión de impacto alto exige dos revisores distintos, uno de ellos de arquitectura.",
}
NORMA_DE_DEFECTO = {"C00": "N10", "D01": "N08", "D02": "N14", "D03": "N20", "D04": "N10", "D05": "N01", "D06": "N11", "D07": "N17", "D08": "N04", "D09": "N05", "D10": "N22",
                    "S11": "N20", "S12": "N02", "S13": "N20", "S14": "N20"}


def sembrar() -> None:
    if almacen.filas("SELECT 1 FROM normas LIMIT 1"):
        return
    for k, v in SEMILLA.items():
        almacen.ejecutar("INSERT INTO normas (id, datos, vector) VALUES (?,?,NULL)", (k, json.dumps({"texto": v, "version": 1, "vigente": True, "fecha": almacen.ahora()}, ensure_ascii=False)))


def listar(solo_vigentes=True) -> list[dict]:
    salida = [{"id": f["id"], "indexada": f["vector"] is not None, **json.loads(f["datos"])} for f in almacen.filas("SELECT * FROM normas ORDER BY id")]
    return [n for n in salida if n["vigente"]] if solo_vigentes else salida


def guardar(id_: str | None, texto: str, vigente: bool, actor: str) -> dict:
    previa = almacen.filas("SELECT datos FROM normas WHERE id = ?", (id_,)) if id_ else []
    if not id_:
        usados = [int(f["id"][1:]) for f in almacen.filas("SELECT id FROM normas") if re.fullmatch(r"N\d+", f["id"])]
        id_ = f"N{max(usados, default=0) + 1:02d}"
    version = json.loads(previa[0]["datos"])["version"] + 1 if previa else 1
    d = {"texto": texto, "version": version, "vigente": vigente, "fecha": almacen.ahora()}
    almacen.ejecutar("INSERT OR REPLACE INTO normas (id, datos, vector) VALUES (?,?,NULL)", (id_, json.dumps(d, ensure_ascii=False)))
    almacen.auditar(actor, "norma_guardada", id_, {"version": version, "vigente": vigente})
    return {"id": id_, **d}


def _indexar() -> None:
    faltan = [f for f in almacen.filas("SELECT id, datos FROM normas WHERE vector IS NULL")]
    if not faltan:
        return
    vs = modelos.embeddings([json.loads(f["datos"])["texto"] for f in faltan], "indexar_normas")
    for f, v in zip(faltan, vs):
        almacen.ejecutar("UPDATE normas SET vector = ? WHERE id = ?", (json.dumps(v), f["id"]))


def _coseno(a, b) -> float:
    return sum(x * y for x, y in zip(a, b)) / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)) or 1)


def _lexica(consulta: str, vigentes: list[dict], k: int) -> list[dict]:
    terminos = Counter(re.findall(r"\w{4,}", consulta.lower()))
    puntuar = lambda n: sum(c for w, c in terminos.items() if w in n["texto"].lower())
    return [n for n in sorted(vigentes, key=puntuar, reverse=True)[:k] if puntuar(n)]


def buscar(consulta: str, k: int = 4) -> tuple[list[dict], str]:
    """Devuelve las normas y el metodo usado. Sin modelo cae a busqueda lexica, y lo declara."""
    vigentes = listar()
    try:
        _indexar()
        q = modelos.embeddings([consulta], "buscar_normas")[0]
    except modelos.SinModelo:
        return _lexica(consulta, vigentes, k), "lexica"
    vectores = {f["id"]: json.loads(f["vector"]) for f in almacen.filas("SELECT id, vector FROM normas WHERE vector IS NOT NULL")}
    orden = sorted((n for n in vigentes if n["id"] in vectores), key=lambda n: -_coseno(q, vectores[n["id"]]))
    return orden[:k], "embeddings"

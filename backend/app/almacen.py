"""Persistencia en SQLite y auditoria encadenada por hash: alterar un registro rompe la cadena."""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

DATOS = pathlib.Path(os.environ.get("ATALAYA_DATOS", pathlib.Path(__file__).resolve().parents[2] / "data"))
_candado = threading.RLock()

ESQUEMA = """
CREATE TABLE IF NOT EXISTS paquetes (id TEXT PRIMARY KEY, version INTEGER, estado TEXT, creado TEXT, actualizado TEXT, datos TEXT);
CREATE TABLE IF NOT EXISTS revisiones (id TEXT PRIMARY KEY, paquete TEXT, version INTEGER, fecha TEXT, datos TEXT);
CREATE TABLE IF NOT EXISTS decisiones (id TEXT PRIMARY KEY, paquete TEXT, version INTEGER, fecha TEXT, datos TEXT);
CREATE TABLE IF NOT EXISTS planes (paquete TEXT PRIMARY KEY, datos TEXT);
CREATE TABLE IF NOT EXISTS trabajos (id TEXT PRIMARY KEY, tipo TEXT, estado TEXT, datos TEXT);
CREATE TABLE IF NOT EXISTS revisores (id TEXT PRIMARY KEY, datos TEXT);
CREATE TABLE IF NOT EXISTS restricciones (id TEXT PRIMARY KEY, datos TEXT);
CREATE TABLE IF NOT EXISTS asignaciones (id TEXT PRIMARY KEY, fecha TEXT, publicada INTEGER, datos TEXT);
CREATE TABLE IF NOT EXISTS normas (id TEXT PRIMARY KEY, datos TEXT, vector TEXT);
CREATE TABLE IF NOT EXISTS mensajes (id INTEGER PRIMARY KEY AUTOINCREMENT, sesion TEXT, datos TEXT);
CREATE TABLE IF NOT EXISTS uso (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, modelo TEXT, etiqueta TEXT, entrada INTEGER, cacheados INTEGER, salida INTEGER, seg REAL, usd REAL);
CREATE TABLE IF NOT EXISTS auditoria (n INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, actor TEXT, accion TEXT, objeto TEXT, detalle TEXT, previo TEXT, hash TEXT);
CREATE TABLE IF NOT EXISTS ajustes (clave TEXT PRIMARY KEY, valor TEXT);
"""


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def nuevo_id(prefijo: str) -> str:
    return f"{prefijo}-{uuid.uuid4().hex[:8]}"


def conectar() -> sqlite3.Connection:
    DATOS.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DATOS / "atalaya.db", timeout=30)
    c.row_factory = sqlite3.Row
    return c


def iniciar() -> None:
    with _candado, conectar() as c:
        c.executescript(ESQUEMA)


def ejecutar(sql: str, args: tuple = ()) -> None:
    with _candado, conectar() as c:
        c.execute(sql, args)


def filas(sql: str, args: tuple = ()) -> list[sqlite3.Row]:
    with _candado, conectar() as c:
        return c.execute(sql, args).fetchall()


def guardar_doc(tabla: str, id_: str, datos: dict) -> None:
    ejecutar(f"INSERT OR REPLACE INTO {tabla} (id, datos) VALUES (?, ?)", (id_, json.dumps(datos, ensure_ascii=False)))


def listar_docs(tabla: str) -> list[dict]:
    return [{"id": f["id"], **json.loads(f["datos"])} for f in filas(f"SELECT id, datos FROM {tabla}")]


def obtener_doc(tabla: str, id_: str) -> dict | None:
    f = filas(f"SELECT id, datos FROM {tabla} WHERE id = ?", (id_,))
    return {"id": f[0]["id"], **json.loads(f[0]["datos"])} if f else None


def borrar_doc(tabla: str, id_: str) -> None:
    ejecutar(f"DELETE FROM {tabla} WHERE id = ?", (id_,))


def ajuste(clave: str, defecto: Any = None) -> Any:
    f = filas("SELECT valor FROM ajustes WHERE clave = ?", (clave,))
    return json.loads(f[0]["valor"]) if f else defecto


def fijar_ajuste(clave: str, valor: Any) -> None:
    ejecutar("INSERT OR REPLACE INTO ajustes (clave, valor) VALUES (?, ?)", (clave, json.dumps(valor)))


# ---------- Paquetes ----------
def guardar_paquete(p: dict) -> None:
    ejecutar("INSERT OR REPLACE INTO paquetes (id, version, estado, creado, actualizado, datos) VALUES (?,?,?,?,?,?)",
             (p["id"], p["version"], p["estado"], p["creado"], ahora(), json.dumps(p, ensure_ascii=False)))


def paquete(id_: str) -> dict | None:
    f = filas("SELECT datos, actualizado FROM paquetes WHERE id = ?", (id_,))
    return {**json.loads(f[0]["datos"]), "actualizado": f[0]["actualizado"]} if f else None


def paquetes() -> list[dict]:
    return [{**json.loads(f["datos"]), "actualizado": f["actualizado"]} for f in filas("SELECT datos, actualizado FROM paquetes ORDER BY creado DESC")]


def guardar_por_paquete(tabla: str, paquete_id: str, version: int, datos: dict, prefijo: str) -> dict:
    d = {"id": nuevo_id(prefijo), "fecha": ahora(), "paquete": paquete_id, "version": version, **datos}
    ejecutar(f"INSERT INTO {tabla} (id, paquete, version, fecha, datos) VALUES (?,?,?,?,?)", (d["id"], paquete_id, version, d["fecha"], json.dumps(d, ensure_ascii=False)))
    return d


def por_paquete(tabla: str, paquete_id: str) -> list[dict]:
    return [json.loads(f["datos"]) for f in filas(f"SELECT datos FROM {tabla} WHERE paquete = ? ORDER BY fecha", (paquete_id,))]


# ---------- Auditoria ----------
def _huella(n_previo: str, fecha: str, actor: str, accion: str, objeto: str, detalle: str) -> str:
    return hashlib.sha256("|".join((n_previo, fecha, actor, accion, objeto, detalle)).encode()).hexdigest()


def auditar(actor: str, accion: str, objeto: str, detalle: dict | None = None) -> None:
    fecha, txt = ahora(), json.dumps(detalle or {}, ensure_ascii=False, sort_keys=True)
    with _candado, conectar() as c:
        f = c.execute("SELECT hash FROM auditoria ORDER BY n DESC LIMIT 1").fetchone()
        previo = f["hash"] if f else "origen"
        c.execute("INSERT INTO auditoria (fecha, actor, accion, objeto, detalle, previo, hash) VALUES (?,?,?,?,?,?,?)",
                  (fecha, actor, accion, objeto, txt, previo, _huella(previo, fecha, actor, accion, objeto, txt)))


def auditoria(limite: int = 300, objeto: str | None = None) -> list[dict]:
    sql, args = ("SELECT * FROM auditoria WHERE objeto = ? ORDER BY n DESC LIMIT ?", (objeto, limite)) if objeto else ("SELECT * FROM auditoria ORDER BY n DESC LIMIT ?", (limite,))
    return [{**dict(f), "detalle": json.loads(f["detalle"])} for f in filas(sql, args)]


def verificar_auditoria() -> dict:
    previo, total = "origen", 0
    for f in filas("SELECT * FROM auditoria ORDER BY n"):
        total += 1
        if f["previo"] != previo or f["hash"] != _huella(previo, f["fecha"], f["actor"], f["accion"], f["objeto"], f["detalle"]):
            return {"integra": False, "registros": total, "falla_en": f["n"]}
        previo = f["hash"]
    return {"integra": True, "registros": total, "falla_en": None}


# ---------- Uso de modelos ----------
def registrar_uso(modelo: str, etiqueta: str, entrada: int, cacheados: int, salida: int, seg: float, usd: float) -> None:
    ejecutar("INSERT INTO uso (fecha, modelo, etiqueta, entrada, cacheados, salida, seg, usd) VALUES (?,?,?,?,?,?,?,?)", (ahora(), modelo, etiqueta, entrada, cacheados, salida, seg, usd))


def gasto_hoy() -> float:
    f = filas("SELECT COALESCE(SUM(usd), 0) AS t FROM uso WHERE substr(fecha, 1, 10) = ?", (ahora()[:10],))
    return float(f[0]["t"])

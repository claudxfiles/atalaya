"""Cliente de la API de OpenAI con tope diario. La clave se lee del entorno o de clases/.env; nunca se expone."""
from __future__ import annotations

import json
import os
import pathlib
import re
import time
import urllib.error
import urllib.request

from . import almacen

# USD por 1M de tokens (entrada, cacheada, salida). developers.openai.com/api/docs/pricing, consultado 02-11-2026.
PRECIOS = {"gpt-6-luna": (0.10, 0.01, 0.50), "gpt-6.1-terra": (1.00, 0.05, 5.00), "gpt-6.1-sol": (2.00, 0.10, 10.00), "text-embedding-3-small": (0.02, 0.02, 0.0)}
MODELO_TRIAJE = "gpt-6-luna"
MODELO_REVISOR = "gpt-6.1-terra"
MODELO_EMBEDDINGS = "text-embedding-3-small"
TOPE_DEFECTO = 1.0


class SinModelo(RuntimeError):
    """El modelo no esta disponible: sin clave, sin cupo o con el proveedor caido. La app sigue con reglas."""


def _clave() -> str:
    for nombre in ("OPENAI_API_KEY", "openai"):
        if os.environ.get(nombre, "").strip():
            return os.environ[nombre].strip().strip("\"'")
    env = pathlib.Path(__file__).resolve().parents[4] / ".env"
    if env.exists():
        for linea in env.read_text(encoding="utf-8-sig").splitlines():
            n, _, v = linea.partition("=")
            if n.strip().lower() == "openai" and v.strip():
                return v.strip().strip("\"'")
    raise SinModelo("No hay clave de API configurada.")


def disponible() -> bool:
    try:
        _clave()
    except SinModelo:
        return False
    return True


def tope() -> float:
    return float(almacen.ajuste("tope_diario_usd", TOPE_DEFECTO))


def _post(ruta: str, cuerpo: dict) -> dict:
    if almacen.gasto_hoy() >= tope():
        raise SinModelo("Se alcanzó el tope diario de gasto en modelos.")
    q = urllib.request.Request("https://api.openai.com/v1/" + ruta, json.dumps(cuerpo).encode(), {"Authorization": "Bearer " + _clave(), "Content-Type": "application/json"})
    for intento in range(3):
        try:
            with urllib.request.urlopen(q, timeout=180) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and intento < 2:
                time.sleep(2 ** intento * 2)
                continue
            raise SinModelo(f"El proveedor respondió con error {e.code}.") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            if intento < 2:
                time.sleep(2 ** intento * 2)
                continue
            raise SinModelo("No se pudo conectar con el proveedor.") from None
    raise SinModelo("Sin respuesta del proveedor.")


def _registrar(modelo, etiqueta, seg, u) -> dict:
    entrada, salida = u.get("prompt_tokens", 0), u.get("completion_tokens", 0)
    cache = (u.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
    pe, pc, ps = PRECIOS.get(modelo, PRECIOS[MODELO_REVISOR])
    usd = ((entrada - cache) * pe + cache * pc + salida * ps) / 1e6
    almacen.registrar_uso(modelo, etiqueta, entrada, cache, salida, seg, usd)
    return {"entrada": entrada, "salida": salida, "seg": round(seg, 2), "usd": usd, "modelo": modelo}


def chat(modelo: str, mensajes: list[dict], etiqueta: str, json_mode=False, herramientas: list[dict] | None = None) -> tuple[dict, dict]:
    cuerpo: dict = {"model": modelo, "messages": mensajes}
    if json_mode:
        cuerpo["response_format"] = {"type": "json_object"}
    if herramientas:
        cuerpo["tools"] = herramientas
        cuerpo["reasoning_effort"] = "none"  # chat/completions no admite herramientas junto con razonamiento en estos modelos
    t0 = time.perf_counter()
    d = _post("chat/completions", cuerpo)
    return d["choices"][0]["message"], _registrar(modelo, etiqueta, time.perf_counter() - t0, d.get("usage", {}))


def embeddings(textos: list[str], etiqueta: str) -> list[list[float]]:
    t0 = time.perf_counter()
    d = _post("embeddings", {"model": MODELO_EMBEDDINGS, "input": textos})
    _registrar(MODELO_EMBEDDINGS, etiqueta, time.perf_counter() - t0, d.get("usage", {}))
    return [x["embedding"] for x in d["data"]]


def leer_json(texto: str | None):
    texto = re.sub(r"^```(?:json)?|```$", "", (texto or "").strip(), flags=re.M).strip()
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", texto, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
    return None

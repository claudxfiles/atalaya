"""Asignacion de revisiones: CP-SAT para dictaminar y SA para mejorar. Ningun calendario se publica sin el verificador."""
from __future__ import annotations

import math
import random
import threading
import time

from ortools.sat.python import cp_model

BLOQUES_DIA = 32  # bloques de 15 minutos en 8 horas
HORIZONTE = 5 * BLOQUES_DIA
MU = 2


def elegibles(t: dict, revisores: list[dict]) -> list[str]:
    return [v["id"] for v in revisores if t["rol"] in v["roles"] and v["celula"] != t["celula_autor"] and t["autor"] != v["nombre"] and (v["cert_datos"] or not t["datos_personales"])]


def _ausencias(v_id: str, restricciones: list[dict]) -> list[tuple[int, int]]:
    tramos = [(r["desde_dia"] * BLOQUES_DIA, (r["hasta_dia"] + 1) * BLOQUES_DIA) for r in restricciones if r["revisor"] == v_id and r["tipo"] == "ausencia"]
    return sorted(tramos)


def verificar(tareas: list[dict], revisores: list[dict], restricciones: list[dict], calendario: dict[str, dict]) -> list[str]:
    """Comprueba cada restriccion dura sin usar la logica de los optimizadores. Devuelve los problemas."""
    problemas, por = [], {}
    rv = {v["id"]: v for v in revisores}
    for t in tareas:
        c = calendario.get(t["id"])
        if not c:
            problemas.append(f"{t['id']} sin asignar.")
            continue
        if c["revisor"] not in elegibles(t, revisores):
            problemas.append(f"{t['id']}: revisor no elegible.")
        por.setdefault(c["revisor"], []).append((c["inicio"], c["inicio"] + t["duracion"], t["id"]))
    for r_id, tramos in por.items():
        v = rv.get(r_id)
        if v is None:
            continue
        tramos.sort()
        if sum(b - a for a, b, _ in tramos) > v["capacidad"]:
            problemas.append(f"{v['nombre']}: supera su capacidad.")
        if tramos[0][0] < v["disponible"] or tramos[-1][1] > HORIZONTE:
            problemas.append(f"{v['nombre']}: fuera de su disponibilidad.")
        for (_, b, _), (c, _, x) in zip(tramos, tramos[1:]):
            if c < b:
                problemas.append(f"{v['nombre']}: solape en {x}.")
        for a, b in _ausencias(r_id, restricciones):
            if any(i < b and a < j for i, j, _ in tramos):
                problemas.append(f"{v['nombre']}: asignado durante una ausencia.")
    return problemas


def objetivo(tareas: list[dict], calendario: dict[str, dict]) -> int:
    atraso = sum(t["peso"] * max(0, calendario[t["id"]]["inicio"] + t["duracion"] - t["plazo"]) for t in tareas)
    carga: dict[str, int] = {}
    for t in tareas:
        carga[calendario[t["id"]]["revisor"]] = carga.get(calendario[t["id"]]["revisor"], 0) + t["duracion"]
    return atraso + MU * max(carga.values(), default=0)


def _decodificar(tareas, rv, ausencias, asign, orden):
    libre = {r: v["disponible"] for r, v in rv.items()}
    cal = {}
    for i in orden:
        t, r = tareas[i], asign[i]
        s = libre[r]
        for a, b in ausencias[r]:
            if s < b and a < s + t["duracion"]:
                s = b
        cal[t["id"]] = {"revisor": r, "inicio": s}
        libre[r] = s + t["duracion"]
    return cal


def _regla(tareas, ele, rv):
    orden = sorted(range(len(tareas)), key=lambda i: (tareas[i]["plazo"], -tareas[i]["peso"]))
    libre = {r: v["disponible"] for r, v in rv.items()}
    asign = {}
    for i in orden:
        r = min(ele[i], key=lambda x: libre[x])
        asign[i] = r
        libre[r] += tareas[i]["duracion"]
    return asign, orden


def _costo(tareas, revisores, restricciones, rv, aus, asign, orden):
    cal = _decodificar(tareas, rv, aus, asign, orden)
    exceso = 0
    carga = {}
    fin = {}
    for t in tareas:
        c = cal[t["id"]]
        carga[c["revisor"]] = carga.get(c["revisor"], 0) + t["duracion"]
        fin[c["revisor"]] = max(fin.get(c["revisor"], 0), c["inicio"] + t["duracion"])
    exceso += sum(max(0, carga[r] - rv[r]["capacidad"]) for r in carga) + sum(max(0, fin[r] - HORIZONTE) for r in fin)
    return objetivo(tareas, cal) + 10000 * exceso, cal


def _recocido(tareas, revisores, restricciones, ele, seg, semilla=7):
    r = random.Random(semilla)
    rv = {v["id"]: v for v in revisores}
    aus = {v["id"]: _ausencias(v["id"], restricciones) for v in revisores}
    asign, orden = _regla(tareas, ele, rv)
    costo, cal = _costo(tareas, revisores, restricciones, rv, aus, asign, orden)
    mejor = (costo, cal)
    t0 = time.perf_counter()
    T0, Tf = max(1.0, min(costo, 5000) * .02), .05
    n = len(tareas)
    while (avance := (time.perf_counter() - t0) / seg) < 1:
        T = T0 * (Tf / T0) ** avance
        a2, o2 = asign, orden
        if r.random() < .5 or n < 2:
            i = r.randrange(n)
            a2 = dict(asign)
            a2[i] = r.choice(ele[i])
        else:
            o2 = list(orden)
            o2.insert(r.randrange(n), o2.pop(r.randrange(n)))
        c2, cal2 = _costo(tareas, revisores, restricciones, rv, aus, a2, o2)
        d = c2 - costo
        if d <= 0 or r.random() < math.exp(-d / T):
            asign, orden, costo = a2, o2, c2
            if c2 < mejor[0]:
                mejor = (c2, cal2)
    return mejor[1]


def _cp_sat(tareas, revisores, restricciones, ele, seg, trabajadores=6):
    m = cp_model.CpModel()
    por = {v["id"]: [] for v in revisores}
    carga = {v["id"]: [] for v in revisores}
    x, s, atrasos = {}, {}, []
    rv = {v["id"]: v for v in revisores}
    for i, t in enumerate(tareas):
        s[i] = m.NewIntVar(0, HORIZONTE - t["duracion"], f"s{i}")
        lits = []
        for r in ele[i]:
            b = m.NewBoolVar(f"x{i}_{r}")
            x[i, r] = b
            lits.append(b)
            por[r].append(m.NewOptionalIntervalVar(s[i], t["duracion"], s[i] + t["duracion"], b, f"iv{i}_{r}"))
            carga[r].append(t["duracion"] * b)
            m.Add(s[i] >= rv[r]["disponible"]).OnlyEnforceIf(b)
        m.AddExactlyOne(lits)
        a = m.NewIntVar(0, HORIZONTE, f"a{i}")
        m.Add(a >= s[i] + t["duracion"] - t["plazo"])
        atrasos.append(t["peso"] * a)
    lmax = m.NewIntVar(0, HORIZONTE, "lmax")
    for v in revisores:
        ivs = por[v["id"]] + [m.NewFixedSizeIntervalVar(a, b - a, f"aus{v['id']}{a}") for a, b in _ausencias(v["id"], restricciones)]
        if ivs:
            m.AddNoOverlap(ivs)
        m.Add(sum(carga[v["id"]]) <= v["capacidad"])
        m.Add(sum(carga[v["id"]]) <= lmax)
    m.Minimize(sum(atrasos) + MU * lmax)
    sol = cp_model.CpSolver()
    sol.parameters.max_time_in_seconds = seg
    sol.parameters.num_workers = trabajadores
    st = sol.Solve(m)
    nombre = sol.StatusName(st)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return nombre, None, None
    cal = {t["id"]: {"revisor": next(r for r in ele[i] if sol.Value(x[i, r])), "inicio": sol.Value(s[i])} for i, t in enumerate(tareas)}
    return nombre, cal, sol.BestObjectiveBound()


MENSAJES = {
    "OPTIMAL": "Calendario óptimo demostrado.",
    "FEASIBLE": "Mejor calendario encontrado en el tiempo disponible, sin óptimo demostrado.",
    "INFEASIBLE": "No hay solución: faltan horas o certificaciones esta semana. Decide una persona.",
    "UNKNOWN": "El solver no dictaminó en el tiempo disponible.",
}


def resolver(tareas: list[dict], revisores: list[dict], restricciones: list[dict], segundos: float = 12) -> dict:
    if not tareas:
        return {"estado": "SIN_TAREAS", "mensaje": "No hay revisiones pendientes por asignar.", "calendario": {}, "publicable": False, "metodo": "—"}
    ele = [elegibles(t, revisores) for t in tareas]
    sin = [t["id"] for t, e in zip(tareas, ele) if not e]
    if sin:
        return {"estado": "INFEASIBLE", "mensaje": "Nadie puede revisar estas tareas (rol, célula o certificación): " + ", ".join(sin) + ".", "calendario": {}, "publicable": False, "metodo": "Reglas", "sin_elegibles": sin}
    grande = len(tareas) > 40
    t0 = time.perf_counter()
    cal_sa: dict = {}
    if grande:
        hilo = threading.Thread(target=lambda: cal_sa.update(_recocido(tareas, revisores, restricciones, ele, segundos)), daemon=True)
        hilo.start()
    nombre, cal_cp, cota = _cp_sat(tareas, revisores, restricciones, ele, segundos)
    if grande:
        hilo.join()
    candidatos = []
    for metodo, cal in (("CP-SAT", cal_cp), ("Recocido simulado", cal_sa or None)):
        if cal and not verificar(tareas, revisores, restricciones, cal):
            candidatos.append((objetivo(tareas, cal), metodo, cal))
    if nombre == "INFEASIBLE":
        return {"estado": nombre, "mensaje": MENSAJES[nombre], "calendario": {}, "publicable": False, "metodo": "CP-SAT", "segundos": round(time.perf_counter() - t0, 1)}
    if not candidatos:
        return {"estado": nombre, "mensaje": MENSAJES["UNKNOWN"] + " Se mantiene el último calendario válido; decide una persona.", "calendario": {}, "publicable": False, "metodo": "CP-SAT", "segundos": round(time.perf_counter() - t0, 1)}
    obj, metodo, cal = min(candidatos, key=lambda c: c[0])
    mensaje = MENSAJES.get(nombre, "") if metodo == "CP-SAT" else f"Calendario de recocido simulado, verificado. El solver terminó en estado {nombre}."
    return {"estado": nombre, "mensaje": mensaje, "calendario": cal, "objetivo": obj, "cota": cota, "publicable": True, "metodo": metodo, "verificado": True, "segundos": round(time.perf_counter() - t0, 1)}

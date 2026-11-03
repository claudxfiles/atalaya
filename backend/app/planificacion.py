"""Planificacion del paso a produccion: dominio STRIPS instanciado, receta HTN, A* para replanificar y validador."""
from __future__ import annotations

import heapq
from dataclasses import dataclass

from . import dominio

ETIQUETAS = {"validar_contrato": "Validar contrato", "escanear_secretos": "Escanear secretos", "correr_pruebas": "Correr pruebas", "desplegar_qa": "Desplegar en QA",
             "pruebas_integracion": "Pruebas de integración", "generar_ada": "Generar documento de arquitectura", "revisar_privacidad": "Revisión de privacidad",
             "revisar_arquitectura": "Revisión de arquitectura", "aprobar_comite": "Aprobación del comité", "tomar_respaldo": "Tomar respaldo", "reservar_ventana": "Reservar ventana de despliegue",
             "desplegar_prod": "Despliegue en producción (lo ejecuta la plataforma)", "verificar_prod": "Verificar en producción", "liberar_ventana": "Liberar ventana"}


@dataclass(frozen=True)
class Accion:
    nombre: str
    pre: frozenset
    agrega: frozenset
    borra: frozenset


def acciones(pii: bool, alto: bool) -> list[Accion]:
    f = lambda *x: frozenset(x)
    previo = ["contrato_ok", "secretos_ok", "pruebas_ok", "integracion_ok", "ada_lista"] + (["privacidad_ok"] if pii else []) + (["arquitectura_ok"] if alto else [])
    a = [Accion("validar_contrato", f("recibido"), f("contrato_ok"), f()), Accion("escanear_secretos", f("recibido"), f("secretos_ok"), f()),
         Accion("correr_pruebas", f("contrato_ok", "secretos_ok"), f("pruebas_ok"), f()), Accion("desplegar_qa", f("pruebas_ok"), f("en_qa"), f()),
         Accion("pruebas_integracion", f("en_qa"), f("integracion_ok"), f()), Accion("generar_ada", f("contrato_ok"), f("ada_lista"), f()),
         Accion("aprobar_comite", frozenset(previo), f("aprobado"), f()), Accion("tomar_respaldo", f("aprobado"), f("respaldo_ok"), f()),
         Accion("reservar_ventana", f("respaldo_ok", "ventana_libre"), f("con_ventana"), f("ventana_libre")), Accion("desplegar_prod", f("con_ventana"), f("en_prod"), f()),
         Accion("verificar_prod", f("en_prod"), f("verificado"), f()), Accion("liberar_ventana", f("verificado", "con_ventana"), f("ventana_libre"), f("con_ventana"))]
    if pii:
        a.append(Accion("revisar_privacidad", f("contrato_ok"), f("privacidad_ok"), f()))
    if alto:
        a.append(Accion("revisar_arquitectura", f("pruebas_ok"), f("arquitectura_ok"), f()))
    return a


META = frozenset({"verificado", "ventana_libre"})


def receta_htn(pii: bool, alto: bool) -> list[str]:
    """promover(p): metodo unico por tarea, por lo que no hay busqueda."""
    return (["validar_contrato", "escanear_secretos", "correr_pruebas", "desplegar_qa", "pruebas_integracion", "generar_ada"] + (["revisar_privacidad"] if pii else []) +
            (["revisar_arquitectura"] if alto else []) + ["aprobar_comite", "tomar_respaldo", "reservar_ventana", "desplegar_prod", "verificar_prod", "liberar_ventana"])


def validar(acc: list[Accion], inicio: frozenset, plan: list[str]) -> tuple[bool, str]:
    """Equivalente simple a VAL: ejecuta el plan y explica el primer error."""
    por = {a.nombre: a for a in acc}
    s = set(inicio)
    for i, n in enumerate(plan):
        a = por.get(n)
        if a is None:
            return False, f"Paso {i + 1}: acción inexistente {n}."
        falta = a.pre - s
        if falta:
            return False, f"Paso {i + 1}: {n} no cumple {sorted(falta)}."
        s = (s - a.borra) | a.agrega
    return (True, "ok") if META <= s else (False, f"Meta incompleta: {sorted(META - s)}.")


def _h(s: frozenset, acc: list[Accion]) -> int:
    costo = {x: 0 for x in s}
    cambio = True
    while cambio:
        cambio = False
        for a in acc:
            if all(q in costo for q in a.pre):
                c = 1 + sum(costo[q] for q in a.pre)
                for x in a.agrega:
                    if costo.get(x, 10 ** 9) > c:
                        costo[x] = c
                        cambio = True
    return sum(costo.get(q, 10 ** 6) for q in META)


def a_estrella(acc: list[Accion], inicio: frozenset, limite=5000) -> list[str] | None:
    """A* ponderado con relajacion por borrado. Valido, pero sin garantia de plan minimo."""
    cola, n = [(0.0, 0, inicio)], 0
    padre, g = {inicio: None}, {inicio: 0}
    for _ in range(limite):
        if not cola:
            return None
        _, _, s = heapq.heappop(cola)
        if META <= s:
            plan = []
            while padre[s]:
                s, nombre = padre[s]
                plan.append(nombre)
            return plan[::-1]
        for a in acc:
            if a.pre <= s:
                t = (s - a.borra) | a.agrega
                if g[s] + 1 < g.get(t, 10 ** 9):
                    g[t], padre[t] = g[s] + 1, (s, a.nombre)
                    n += 1
                    heapq.heappush(cola, (g[t] + 5 * _h(t, acc), n, t))
    return None


def nuevo_plan(p: dict) -> dict:
    pii, alto = dominio.tiene_datos_personales(p), dominio.impacto(p) == "alto"
    pasos = receta_htn(pii, alto)
    ok, motivo = validar(acciones(pii, alto), frozenset({"recibido", "ventana_libre"}), pasos)
    if not ok:
        raise ValueError(f"El validador rechazó la receta: {motivo}")
    return {"paquete": p["id"], "pii": pii, "alto": alto, "hechos": ["recibido"], "pendientes": pasos, "hechas": [], "metodo": "HTN + validador", "valido": True, "replanificaciones": 0}


def _estado(plan: dict, ventana_libre: bool) -> frozenset:
    return frozenset(plan["hechos"]) | (frozenset({"ventana_libre"}) if ventana_libre else frozenset())


def ejecutar_paso(plan: dict, accion: str, ventana_libre: bool, actor: str) -> dict:
    """Registra un paso hecho por una persona. Lo imposible se rechaza aqui, no en la interfaz."""
    acc = {a.nombre: a for a in acciones(plan["pii"], plan["alto"])}
    a = acc.get(accion)
    if a is None:
        raise ValueError("Acción inexistente para este paquete.")
    s = _estado(plan, ventana_libre)
    falta = a.pre - s
    if falta:
        if "ventana_libre" in falta:
            raise ValueError("La ventana de despliegue la ocupa otro paquete.")
        raise ValueError("Falta completar antes: " + ", ".join(sorted(falta)) + ".")
    s2 = (s - a.borra) | a.agrega
    plan["hechos"] = sorted(s2 - {"ventana_libre"})
    plan["hechas"].append({"accion": accion, "actor": actor, "fecha": dominio_ahora()})
    plan["pendientes"] = [x for x in plan["pendientes"] if x != accion]
    return plan


def replanificar(plan: dict, perdidos: list[str], ventana_libre: bool) -> dict:
    """Ante una falla se retiran hechos y se recalcula desde el estado actual. Sin ventana propia, se asume que quedara libre."""
    conservados = set(plan["hechos"]) - set(perdidos)
    con_ventana = "con_ventana" in conservados
    inicio = frozenset(conservados | ({"ventana_libre"} if not con_ventana else set()))
    acc = acciones(plan["pii"], plan["alto"])
    nuevo = a_estrella(acc, inicio)
    if nuevo is None:
        raise ValueError("No existe un plan desde el estado actual: requiere una persona.")
    ok, motivo = validar(acc, inicio, nuevo)
    if not ok:
        raise ValueError(f"El validador rechazó el plan: {motivo}")
    plan.update({"hechos": sorted(conservados), "pendientes": nuevo, "metodo": "A* + validador", "replanificaciones": plan["replanificaciones"] + 1})
    return plan


def dominio_ahora() -> str:
    from .almacen import ahora
    return ahora()

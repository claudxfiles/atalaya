"""Pruebas sin red: compuertas, verificadores, degradacion y auditoria."""
import json
import random
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def cli(tmp_path, monkeypatch):
    monkeypatch.setenv("ATALAYA_DATOS", str(tmp_path))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("openai", raising=False)
    from app import almacen, main, modelos
    monkeypatch.setattr(almacen, "DATOS", tmp_path)
    monkeypatch.setattr(modelos, "_clave", lambda: (_ for _ in ()).throw(modelos.SinModelo("No hay clave de API configurada.")))
    with TestClient(main.app) as c:
        yield c


def _sint(c, perfil):
    return c.post("/api/paquetes/sintetico", json={"perfil": perfil}).json()["id"]


def _esperar(c, job):
    for _ in range(200):
        t = c.get(f"/api/trabajos/{job}").json()
        if t["estado"] in ("listo", "error"):
            return t
        time.sleep(.02)
    raise AssertionError("trabajo colgado")


def _revisar(c, pid):
    r = c.post(f"/api/paquetes/{pid}/revisar")
    assert r.status_code == 202
    assert _esperar(c, r.json()["id"])["estado"] == "listo"
    return c.get(f"/api/paquetes/{pid}").json()


def _actor(c, p, rol=None, cert=None, excluir=()):
    for v in c.get("/api/revisores").json():
        if v["nombre"] != p["autor"] and v["celula"] != p["celula"] and v["id"] not in excluir and (not rol or rol in v["roles"]) and (cert is None or v["cert_datos"] == cert):
            return v
    raise AssertionError("sin actor")


def test_inicia_con_datos_y_sin_modelo(cli):
    assert cli.get("/api/salud").json()["modelo"] is False
    assert len(cli.get("/api/paquetes").json()) == 6
    assert len(cli.get("/api/revisores").json()) == 11


def test_rechaza_campo_extra(cli):
    assert cli.post("/api/paquetes/sintetico", json={"perfil": "rut", "x": 1}).status_code == 422


def test_sin_modelo_degrada_y_nunca_aprueba_solo(cli):
    p = _revisar(cli, _sint(cli, "correcto"))
    assert p["revision"]["modo"] == "solo_reglas" and p["estado"] == "por_aprobar" and "pendiente" in " ".join(p["revision"]["avisos"])


def test_regla_bloquea_y_no_se_puede_descartar(cli):
    p = _revisar(cli, _sint(cli, "credencial"))
    assert p["estado"] == "rechazado" and "D01" in [h["codigo"] for h in p["revision"]["hallazgos"]]
    v = _actor(cli, p)
    r = cli.post(f"/api/paquetes/{p['id']}/hallazgos/D01/descartar", json={"actor": v["id"], "motivo": "no aplica"})
    assert r.status_code == 409
    assert cli.post(f"/api/paquetes/{p['id']}/decision", json={"accion": "aprobar", "actor": v["id"], "comentario": "ok"}).status_code == 409


def test_secreto_nunca_sale_al_modelo(cli):
    p = _revisar(cli, _sint(cli, "credencial"))
    assert "Xy72ab" not in p["revision"]["enviado"] and "[SECRETO_OCULTO]" in p["revision"]["enviado"]
    p2 = _revisar(cli, _sint(cli, "rut"))
    from app.dominio import RUT
    assert not RUT.search(p2["revision"]["enviado"])


def test_separacion_de_funciones(cli):
    p = _revisar(cli, _sint(cli, "correcto"))
    misma = next((v for v in cli.get("/api/revisores").json() if v["celula"] == p["celula"]), None)
    assert misma and cli.post(f"/api/paquetes/{p['id']}/decision", json={"accion": "aprobar", "actor": misma["id"], "comentario": "x"}).status_code == 409


def test_flujo_completo_alto_impacto_y_plan(cli):
    from app import dominio
    d = dominio.sintetico("correcto", random.Random(4))
    d["contrato"] = json.dumps({"tabla": "t", "llave_primaria": "id_registro", "columnas": [{"nombre": "id_registro", "tipo": "string", "dato_personal": False}, {"nombre": "rut", "tipo": "string", "dato_personal": True}]})
    d["muestra"] = "id_registro,rut\nA1,12.345.678-9\nA2,11.111.111-1\n"
    d.pop("sintetico")
    pid = cli.post("/api/paquetes", json=d).json()["id"]
    p = _revisar(cli, pid)
    assert p["impacto"] == "alto" and p["requisitos"]["firmas"] == 2
    arq = _actor(cli, p, "arquitectura", True) if any("arquitectura" in v["roles"] and v["cert_datos"] and v["celula"] != p["celula"] and v["nombre"] != p["autor"] for v in cli.get("/api/revisores").json()) else _actor(cli, p, "arquitectura")
    otro = _actor(cli, p, "privacidad", excluir=(arq["id"],))
    r = cli.post(f"/api/paquetes/{pid}/decision", json={"accion": "aprobar", "actor": arq["id"], "comentario": "revisado a mano"})
    assert r.status_code == 200 and r.json()["estado"] == "por_aprobar"
    assert cli.post(f"/api/paquetes/{pid}/decision", json={"accion": "aprobar", "actor": arq["id"], "comentario": "otra vez"}).status_code == 409
    r = cli.post(f"/api/paquetes/{pid}/decision", json={"accion": "aprobar", "actor": otro["id"], "comentario": "revisado a mano"})
    assert r.json()["estado"] == "aprobado"
    p = cli.get(f"/api/paquetes/{pid}").json()
    pasos = list(p["plan"]["pendientes"])
    assert "revisar_privacidad" in pasos and pasos[0] == "validar_contrato"
    assert cli.post(f"/api/paquetes/{pid}/plan/paso", json={"accion": "desplegar_prod", "actor": arq["id"]}).status_code == 409
    for a in pasos:
        assert cli.post(f"/api/paquetes/{pid}/plan/paso", json={"accion": a, "actor": arq["id"]}).status_code == 200, a
    assert cli.get(f"/api/paquetes/{pid}").json()["estado"] == "promovido"


def test_ventana_exclusiva_y_replanificacion(cli):
    pids = []
    for _ in range(2):
        pid = _revisar(cli, _sint(cli, "correcto"))["id"]
        for _ in range(3):
            p = cli.get(f"/api/paquetes/{pid}").json()
            if p["estado"] == "aprobado":
                break
            usados = tuple(a["revisor"] for a in p["aprobaciones"])
            rol = "arquitectura" if p["requisitos"]["arquitectura"] and not any("arquitectura" in a["roles"] for a in p["aprobaciones"]) else None
            cert = True if p["requisitos"]["certificacion_datos"] and not any(a["cert_datos"] for a in p["aprobaciones"]) else None
            v = _actor(cli, p, rol, cert, usados)
            assert cli.post(f"/api/paquetes/{pid}/decision", json={"accion": "aprobar", "actor": v["id"], "comentario": "visto"}).status_code == 200
        pids.append((pid, v["id"]))
    def hasta_ventana(pid, a):
        for x in cli.get(f"/api/paquetes/{pid}").json()["plan"]["pendientes"]:
            if x == "reservar_ventana":
                break
            assert cli.post(f"/api/paquetes/{pid}/plan/paso", json={"accion": x, "actor": a}).status_code == 200
    (a, ax), (b, bx) = pids
    hasta_ventana(a, ax), hasta_ventana(b, bx)
    assert cli.post(f"/api/paquetes/{a}/plan/paso", json={"accion": "reservar_ventana", "actor": ax}).status_code == 200
    assert "ventana" in cli.post(f"/api/paquetes/{b}/plan/paso", json={"accion": "reservar_ventana", "actor": bx}).json()["detail"]
    r = cli.post(f"/api/paquetes/{b}/plan/falla", json={"accion": "correr_pruebas", "actor": bx, "motivo": "cayó una prueba"})
    assert r.status_code == 200 and r.json()["replanificaciones"] == 1 and "correr_pruebas" in r.json()["pendientes"]


def test_asignacion_verificada_y_ausencia(cli):
    for pf in ("correcto", "correcto", "correcto"):
        _revisar(cli, _sint(cli, pf))
    r = cli.post("/api/asignacion/calcular")
    t = _esperar(cli, r.json()["id"])["resultado"]
    assert t["publicable"] and t["verificado"]
    assert cli.post(f"/api/asignacion/{t['id']}/publicar").json()["publicada"] is True
    tarea, c = next(iter(t["calendario"].items()))
    assert cli.post("/api/restricciones", json={"revisor": c["revisor"], "desde_dia": 0, "hasta_dia": 4}).status_code == 201
    assert cli.post(f"/api/asignacion/{t['id']}/publicar").status_code == 409
    assert cli.post(f"/api/asignacion/{t['id']}/ajustar", json={"actor": "x", "tarea": tarea, "revisor": c["revisor"], "inicio": c["inicio"]}).status_code == 409


def test_infactible_lo_dice_y_no_publica():
    from app import asignacion
    v = [{"id": "A", "nombre": "A", "roles": ["calidad"], "celula": 1, "cert_datos": False, "disponible": 0, "capacidad": 5}]
    t = [{"id": "t", "rol": "calidad", "duracion": 10, "plazo": 20, "peso": 1, "celula_autor": 2, "autor": "Z", "datos_personales": False}]
    r = asignacion.resolver(t, v, [], 2)
    assert r["estado"] == "INFEASIBLE" and r["publicable"] is False


def test_verificador_detecta_ausencia_y_solape():
    from app import asignacion as a
    v = [{"id": "A", "nombre": "A", "roles": ["calidad"], "celula": 1, "cert_datos": False, "disponible": 0, "capacidad": 100}]
    t = [{"id": "x", "rol": "calidad", "duracion": 10, "plazo": 20, "peso": 1, "celula_autor": 2, "autor": "Z", "datos_personales": False}, {"id": "y", "rol": "calidad", "duracion": 10, "plazo": 20, "peso": 1, "celula_autor": 2, "autor": "Z", "datos_personales": False}]
    assert a.verificar(t, v, [], {"x": {"revisor": "A", "inicio": 0}, "y": {"revisor": "A", "inicio": 5}})
    assert a.verificar(t[:1], v, [{"tipo": "ausencia", "revisor": "A", "desde_dia": 0, "hasta_dia": 0}], {"x": {"revisor": "A", "inicio": 0}})


def test_auditoria_detecta_alteracion(cli):
    _sint(cli, "rut")
    assert cli.get("/api/auditoria").json()["cadena"]["integra"] is True
    from app import almacen
    almacen.ejecutar("UPDATE auditoria SET actor = 'Nadie' WHERE n = 1")
    assert cli.get("/api/auditoria").json()["cadena"] == {"integra": False, "registros": 1, "falla_en": 1}


def test_contrato_invalido_bloquea(cli):
    from app import dominio
    d = dominio.sintetico("correcto", random.Random(2))
    d["contrato"] = "{no es json"
    d.pop("sintetico")
    p = _revisar(cli, cli.post("/api/paquetes", json=d).json()["id"])
    assert p["estado"] == "rechazado" and "C00" in [h["codigo"] for h in p["revision"]["hallazgos"]]


def test_agente_valida_propuesta_de_ausencia(cli):
    from app import agente
    assert agente.validar_ausencia("Paula", 1, 2)["nombre"] == "Paula Fuentes"
    with pytest.raises(ValueError):
        agente.validar_ausencia("Nadie", 1, 2)
    with pytest.raises(ValueError):
        agente.validar_ausencia("Paula", 3, 9)
    r = cli.post("/api/agente", json={"sesion": "s", "texto": "hola 12.345.678-9"}).json()
    assert "clave" in r["texto"].lower()
    assert "12.345.678-9" not in json.dumps(cli.get("/api/agente/s").json())

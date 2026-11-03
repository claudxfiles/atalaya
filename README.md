# Atalaya Studio

Aplicación para gobernar el paso a producción de paquetes de datos. Lo calculable lo deciden reglas, lo interpretable lo propone un modelo y la aprobación la firma una persona. Atalaya nunca despliega.

Prototipo académico: el banco, los revisores y las normas incluidas son ficticios. **No uses datos reales.** No hay inicio de sesión: "Actuando como" solo identifica a la persona en la traza.

## Iniciar

Con Docker Desktop encendido, doble clic en `INICIAR_ATALAYA.bat` (carpeta superior). Abre http://localhost:8790. La clave de OpenAI se lee de `clases/.env` (variable `openai`) al iniciar. Los datos quedan en el volumen de Docker `atalaya-datos`; para partir de cero: `docker volume rm atalaya-datos`.

Sin clave o al alcanzar el tope diario, sigue operando solo con reglas y deja la revisión semántica pendiente.

## Flujo

1. **Bandeja:** crea un paquete (historia, contrato, muestra, código) o uno de prueba, y revísalo.
2. **Revisión:** guardrail, reglas, enmascaramiento, revisor LLM, grounding, normas, fiscalizador y veredicto por código.
3. **Decisión:** firma humana, con separación de funciones. Impacto alto exige dos firmas, una de arquitectura.
4. **Plan:** pasos HTN con validador. Lo imposible se rechaza; una falla replanifica con A*. La ventana de despliegue es exclusiva.
5. **Asignación:** CP-SAT y recocido simulado, con verificador independiente. Una semana sin solución se informa, no se fuerza.
6. **Agente:** consulta con herramientas de solo lectura. Lo que propone lo confirma una persona.
7. **Auditoría:** registros encadenados por hash.

## Desarrollo

```
cd backend && pip install -r requirements.txt pytest httpx && python -m pytest
python -m uvicorn app.main:app --port 8790
cd frontend && npm ci && npm run dev
```

Estructura inspirada en la organización de Director Studio (FastAPI + React, etapas numeradas, trabajos en segundo plano, datos en disco), sin reutilizar su código.

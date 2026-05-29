"""
QA Agent Brain Visualizer — Backend
Construye el grafo de conocimiento dinámicamente desde BigQuery.
Toda la lógica de tipos, failure_rate, conexiones módulo→bug vive acá.

Correr: python server.py  →  http://localhost:8001
"""

import re
import unicodedata
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

app = FastAPI(title="QA Agent Brain Visualizer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECT_ID = "procontacto-claude"
DATASET    = "qa_agent"


# ── Módulos canónicos ─────────────────────────────────────────────────────────
# Lista maestra. Cualquier subject/object que matchee (case-insensitive, sin tildes)
# se tipará como "module" en lugar de "generic".

CANONICAL_MODULES = {
    "gestión de visitas", "gestion de visitas",
    "gestión de casos", "gestion de casos",
    "oportunidades",
    "app offline",
    "gestión de candidatos", "gestion de candidatos",
    "gestión de prospectos", "gestion de prospectos",
    "acuerdo de desarrollo",
    "consumer goods cloud",
    "servicio técnico", "servicio tecnico",
    "segmentación", "segmentacion",
    "perfilamiento",
    "gestión de contactos", "gestion de contactos",
    "gestión de eventos", "gestion de eventos",
    "gestión de planes de acción", "gestion de planes de accion",
    "gestión de rutas", "gestion de rutas",
    "gestión de órdenes", "gestion de ordenes",
    "gestión de despacho", "gestion de despacho",
    "pagos", "deposito", "reservas", "crear reserva",
    "bot de mensajería", "bot de mensajeria",
    "expedicion", "expedición",
    "expedicion - ordenes directas",
    "generar reporte de despacho",
    "order",
}

# Perfiles reales (palabras exactas, sin substring)
REAL_PROFILES = {
    "ate", "cobrador", "gerente comercial", "sales_user", "admin",
    "vendedor", "distribuidor", "ebx", "macro canal", "approvalprospectbyebx",
}


def _normalize(s: str) -> str:
    """Minúsculas + sin tildes para comparación."""
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().strip()


def infer_node_type(name: str, bug_ids: set = None, module_set: set = None) -> str:
    """Infiere el tipo del nodo dado su nombre."""
    n      = _normalize(name)
    name_l = name.lower()

    # Tipos explícitos primero
    if bug_ids and name in bug_ids:
        return "bug"
    if module_set and n in module_set:
        return "module"
    if n in CANONICAL_MODULES:
        return "module"

    # Proyecto
    if re.match(r'^(cmiv2|solo|cmi|global)$', n):
        return "project"

    # Skills
    if n.startswith("skill:"):
        return "skill"

    # Campos SF (por API Name)
    if any(x in name for x in ["__c", "Account.", "Contact.", "Opportunity.", "Case.", "Lead.", "Product."]):
        return "sf_field"

    # Perfiles — solo palabras exactas
    if n in REAL_PROFILES:
        return "sf_profile"

    # Flows / Triggers
    if any(x in name_l for x in ["flow", "trigger", "apex", "process builder"]):
        return "flow"

    # Root causes
    if any(x in name_l for x in ["fls", "owd", "sharing", "restriction", "validation_rule"]):
        return "root_cause"

    # Condiciones
    if any(x in name_l for x in ["dynamic_forms", "dynamic forms", "condition"]):
        return "condition"

    # Test cases
    if re.match(r'^tc-\d+$', n) or re.match(r'^tc_\d+$', n):
        return "test_case"

    # Issue keys de Jira (PROJ-1234) → test_case (referencias)
    if re.match(r'^[a-z]+-\d{3,5}$', n):
        return "test_case"

    return "generic"


def build_graph(kg_rows: list, skill_rows: list) -> dict:
    """
    Construye nodes + links con toda la inteligencia:
    - Tipos correctos (module, bug, sf_field, sf_profile...)
    - failure_rate_pct en nodos módulo
    - Links directos módulo → has_open_bug → bug (bypassing issue keys)
    - Tamaños según jerarquía
    """
    nodes: dict = {}
    links: list = []

    # ── Paso 1: recolectar metadatos para type inference ─────────────────────

    # a) IDs de nodos bug (objetos de has_open_bug)
    bug_ids: set = {
        row["object"] for row in kg_rows
        if row["relation"] == "has_open_bug"
    }

    # b) Nombres de módulos que aparecen en contains_module
    module_names: set = {
        _normalize(row["object"]) for row in kg_rows
        if row["relation"] == "contains_module"
    } | {
        _normalize(row["subject"]) for row in kg_rows
        if row["relation"] in ("contains_module", "has_submodule", "failure_rate")
        and row["relation"] != "has_open_bug"
    }

    # c) failure_rate max por módulo (de triples module → failure_rate → "alto (58.1%)")
    failure_rates: dict = {}
    for row in kg_rows:
        if row["relation"] == "failure_rate":
            m = re.search(r'(\d+\.?\d*)%', row["object"])
            pct = float(m.group(1)) / 100.0 if m else 0.0
            subj = row["subject"]
            if subj not in failure_rates or failure_rates[subj] < pct:
                failure_rates[subj] = pct

    # d) Mapa issue_key → módulo (para conectar bugs a módulos)
    issue_to_module: dict = {}
    for row in kg_rows:
        if row["relation"] == "tested_in_module":
            if row["subject"] not in issue_to_module:
                issue_to_module[row["subject"]] = row["object"]

    # ── Paso 2: helper upsert ────────────────────────────────────────────────

    def upsert_node(node_id: str, node_type: str, is_new: bool = False, **extra):
        if node_id not in nodes:
            label = extra.pop("label", node_id)
            # Truncar labels largos (bugs tienen summaries de 120 chars)
            display = (label[:35] + "…") if len(label) > 38 else label
            # Tamaño base según jerarquía
            base_val = 27 if node_type == "project" else 8 if node_type == "module" else 3 if node_type == "skill" else 2 if node_type == "bug" else 1
            nodes[node_id] = {
                "id":      node_id,
                "name":    display,
                "type":    node_type,
                "val":     base_val,
                "is_new":  is_new,
                **extra
            }
        else:
            if node_type not in ("project", "module", "bug"):
                nodes[node_id]["val"] += 1  # solo aumentar val para nodos genéricos
            if is_new:
                nodes[node_id]["is_new"] = True

    # ── Paso 3: procesar triples ─────────────────────────────────────────────

    # Links directos que vamos a reemplazar/omitir
    SKIP_AS_SOURCE = {"has_open_bug"}   # los reconstruimos con módulo como source
    bug_link_targets: set = set()       # bugs ya conectados a módulos

    for row in kg_rows:
        relation = row["relation"]
        subject  = row["subject"]
        obj      = row["object"]
        project  = row.get("project") or "GLOBAL"
        is_new   = bool(row.get("is_new", False))
        conf     = float(row.get("confidence_score") or 1.0)

        subj_type = infer_node_type(subject, bug_ids, module_names)
        obj_type  = infer_node_type(obj,     bug_ids, module_names)

        if relation == "has_open_bug":
            # Intentar conectar directo al módulo via issue_key
            module = issue_to_module.get(subject)
            if module:
                k = f"{module}||{obj}"
                if k not in bug_link_targets:
                    bug_link_targets.add(k)
                    upsert_node(module, "module", False, project=project)
                    upsert_node(obj, "bug", is_new, project=project)
                    links.append({"source": module, "target": obj, "relation": "has_open_bug", "value": conf})
            else:
                # Sin módulo mapeado — conectar directo al subject (issue key o manual)
                upsert_node(subject, subj_type, is_new, project=project)
                upsert_node(obj, "bug", is_new, project=project)
                links.append({"source": subject, "target": obj, "relation": relation, "value": conf})
            continue

        if relation == "failure_rate":
            # No crear nodo "alto (58.1%)" — la info va al módulo como failure_rate_pct
            continue

        if relation in ("tested_in_module",):
            # Omitir del grafo visual — solo útil como lookup interno
            continue

        upsert_node(subject, subj_type, is_new, project=project)
        upsert_node(obj,     obj_type,  is_new, project=project)
        links.append({"source": subject, "target": obj, "relation": relation, "value": conf})

    # ── Paso 4: skills ───────────────────────────────────────────────────────

    for row in skill_rows:
        skill_id = f"skill:{row['skill_id']}"
        project  = row.get("project") or "GLOBAL"
        is_new   = bool(row.get("is_new", False))
        upsert_node(skill_id, "skill", is_new,
                    label=row["title"], project=project,
                    success_rate=float(row.get("success_rate") or 1.0),
                    use_count=int(row.get("use_count") or 0))
        for kw in (row.get("keywords") or "").split(",")[:3]:
            kw = kw.strip()
            if not kw:
                continue
            upsert_node(kw, "root_cause", False, project=project)
            links.append({"source": skill_id, "target": kw, "relation": "covers", "value": 0.7})

    # ── Paso 5: enriquecer módulos con failure_rate_pct ──────────────────────

    for node_id, node in nodes.items():
        if node["type"] == "module":
            n_norm = _normalize(node_id)
            # Buscar por nombre normalizado
            fr = next((v for k, v in failure_rates.items() if _normalize(k) == n_norm), -1.0)
            node["failure_rate_pct"] = fr

    # ── Paso 6: asegurar nodos de proyecto ───────────────────────────────────

    seen_projects = {n.get("project") for n in nodes.values() if n.get("project")}
    for proj in seen_projects:
        if proj and proj != "GLOBAL" and proj not in nodes:
            nodes[proj] = {"id": proj, "name": proj, "type": "project",
                           "val": 80, "is_new": False}

    return {"nodes": list(nodes.values()), "links": links}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index():
    return Path(__file__).parent.joinpath("cortex-standalone.html").read_text(encoding="utf-8")


@app.get("/api/graph")
def get_graph(project: str = Query("ALL")):
    proj_filter = "" if project == "ALL" else "AND project = @project"

    kg_query = f"""
        SELECT subject, relation, object, confidence_score, project,
               TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), created_at, HOUR) < 24 AS is_new
        FROM `{PROJECT_ID}.{DATASET}.agent_knowledge_graph`
        WHERE 1=1 {proj_filter}
        LIMIT 5000
    """
    skills_query = f"""
        SELECT skill_id, title, keywords, success_rate, use_count, project,
               TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), created_at, HOUR) < 24 AS is_new
        FROM `{PROJECT_ID}.{DATASET}.agent_skills`
        WHERE active = true {proj_filter}
        LIMIT 500
    """

    try:
        from google.cloud import bigquery
        from google.cloud.bigquery import QueryJobConfig, ScalarQueryParameter
        client = bigquery.Client(project=PROJECT_ID)

        def run(query):
            cfg = None
            if project != "ALL":
                cfg = QueryJobConfig(query_parameters=[
                    ScalarQueryParameter("project", "STRING", project)
                ])
            return [dict(r) for r in client.query(query, job_config=cfg).result()]

        kg_rows    = run(kg_query)
        skill_rows = run(skills_query)
        graph      = build_graph(kg_rows, skill_rows)
        graph["meta"] = {
            "project": project, "kg_rows": len(kg_rows),
            "skill_rows": len(skill_rows), "demo": False
        }
        return graph

    except Exception as e:
        return JSONResponse(status_code=200, content={
            "nodes": _demo_nodes(), "links": _demo_links(),
            "meta": {"project": project, "demo": True, "error": str(e)},
        })


@app.get("/api/stats")
def get_stats():
    try:
        from google.cloud import bigquery
        client = bigquery.Client(project=PROJECT_ID)
        row = list(client.query(f"""
            SELECT
              (SELECT COUNT(*) FROM `{PROJECT_ID}.{DATASET}.agent_knowledge_graph`) AS total_triples,
              (SELECT COUNT(DISTINCT subject) FROM `{PROJECT_ID}.{DATASET}.agent_knowledge_graph`) AS total_entities,
              (SELECT COUNT(*) FROM `{PROJECT_ID}.{DATASET}.agent_skills` WHERE active = true) AS total_skills,
              (SELECT COUNT(DISTINCT project) FROM `{PROJECT_ID}.{DATASET}.agent_knowledge_graph`) AS total_projects,
              (SELECT COUNT(*) FROM `{PROJECT_ID}.{DATASET}.agent_knowledge_graph`
               WHERE TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), created_at, HOUR) < 24) AS new_today
        """).result())[0]
        return dict(row)
    except:
        return {"total_triples": 0, "total_entities": 0, "total_skills": 0,
                "total_projects": 0, "new_today": 0, "demo": True}


@app.get("/api/projects")
def get_projects():
    try:
        from google.cloud import bigquery
        client = bigquery.Client(project=PROJECT_ID)
        rows = client.query(f"""
            SELECT DISTINCT project
            FROM `{PROJECT_ID}.{DATASET}.agent_knowledge_graph`
            WHERE project IS NOT NULL AND project != 'GLOBAL'
            ORDER BY project
        """).result()
        return [r["project"] for r in rows]
    except:
        return ["CMIV2", "SOLO"]


# ── Demo data ─────────────────────────────────────────────────────────────────

def _demo_nodes():
    return [
        {"id": "CMIV2",              "name": "CMIV2",               "type": "project",    "val": 80, "is_new": False},
        {"id": "Oportunidades",      "name": "Oportunidades",       "type": "module",     "val": 20, "is_new": False, "failure_rate_pct": 0.58},
        {"id": "Gestión de Visitas", "name": "Gestión de Visitas",  "type": "module",     "val": 20, "is_new": False, "failure_rate_pct": 0.14},
        {"id": "bug-demo-1",         "name": "Campo Email no visible para Sales", "type": "bug", "val": 4, "is_new": True},
        {"id": "Sales_User",         "name": "Sales_User",          "type": "sf_profile", "val": 6,  "is_new": False},
        {"id": "dynamic_forms",      "name": "dynamic_forms",       "type": "condition",  "val": 5,  "is_new": False},
        {"id": "fls_restriction",    "name": "fls_restriction",     "type": "root_cause", "val": 4,  "is_new": False},
    ]

def _demo_links():
    return [
        {"source": "CMIV2",              "target": "Oportunidades",      "relation": "contains_module", "value": 1.0},
        {"source": "CMIV2",              "target": "Gestión de Visitas",  "relation": "contains_module", "value": 1.0},
        {"source": "Oportunidades",      "target": "bug-demo-1",          "relation": "has_open_bug",    "value": 0.9},
        {"source": "Sales_User",         "target": "fls_restriction",     "relation": "blocked_by",      "value": 0.9},
        {"source": "dynamic_forms",      "target": "fls_restriction",     "relation": "relates_to",      "value": 0.7},
    ]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=False)

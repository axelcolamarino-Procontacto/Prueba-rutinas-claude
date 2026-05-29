"""
QA Agent Brain Visualizer — Backend
Sirve el grafo de conocimiento del agente desde BigQuery.

Correr: python server.py
Abre:   http://localhost:8000
"""

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import json

app = FastAPI(title="QA Agent Brain Visualizer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECT_ID = "procontacto-claude"
DATASET    = "qa_agent"


def get_bq_client():
    from google.cloud import bigquery
    return bigquery.Client(project=PROJECT_ID)


def infer_node_type(name: str) -> str:
    n = name.lower()
    if any(n.startswith(p) for p in ["skill:"]):
        return "skill"
    if any(x in name for x in ["__c", "Account.", "Contact.", "Opportunity.", "Case.", "Lead.", "Product."]):
        return "sf_field"
    if any(x in n for x in ["profile", "user", "admin", "gerente", "vendedor", "manager", "rep "]):
        return "sf_profile"
    if any(x in n for x in ["flow", "trigger", "apex", "process builder"]):
        return "flow"
    if any(x in n for x in ["fls", "owd", "sharing", "permission", "restriction", "rule", "validation"]):
        return "root_cause"
    if any(x in n for x in ["dynamic_forms", "dynamic forms", "condition", "hidden", "visible"]):
        return "condition"
    if n.startswith("tc-") or n.startswith("tc_"):
        return "test_case"
    return "generic"


def build_graph(kg_rows, skill_rows):
    nodes = {}
    links = []

    def upsert_node(node_id, node_type, is_new=False, **extra):
        if node_id not in nodes:
            nodes[node_id] = {
                "id":      node_id,
                "name":    extra.get("label", node_id),
                "type":    node_type,
                "val":     1,
                "is_new":  is_new,
                **{k: v for k, v in extra.items() if k != "label"}
            }
        else:
            nodes[node_id]["val"] += 1
            if is_new:
                nodes[node_id]["is_new"] = True

    # Knowledge graph triples → nodes + links
    for row in kg_rows:
        subj_type = infer_node_type(row["subject"])
        obj_type  = infer_node_type(row["object"])
        project   = row.get("project") or "GLOBAL"
        is_new    = bool(row.get("is_new", False))

        obj_full  = row["object"]
        # Para nodos de bugs (objetos largos), usar label corto y guardar texto completo
        obj_label = (obj_full[:35] + "…") if len(obj_full) > 38 else obj_full

        upsert_node(row["subject"], subj_type, is_new, project=project)
        upsert_node(obj_full, obj_type, is_new, project=project,
                    label=obj_label, full_text=obj_full if len(obj_full) > 38 else None)

        links.append({
            "source":   row["subject"],
            "target":   obj_full,
            "relation": row["relation"],
            "value":    float(row.get("confidence_score") or 1.0)
        })

    # Skills → nodes + edges to keywords
    for row in skill_rows:
        skill_id = f"skill:{row['skill_id']}"
        project  = row.get("project") or "GLOBAL"
        is_new   = bool(row.get("is_new", False))

        upsert_node(skill_id, "skill", is_new,
                    label=row["title"],
                    project=project,
                    success_rate=float(row.get("success_rate") or 1.0),
                    use_count=int(row.get("use_count") or 0))

        # Link skill to first 3 keywords
        for kw in (row.get("keywords") or "").split(",")[:3]:
            kw = kw.strip()
            if not kw:
                continue
            upsert_node(kw, "root_cause", False, project=project)
            links.append({"source": skill_id, "target": kw, "relation": "covers", "value": 0.7})

    # Project nodes (always big)
    seen_projects = {n.get("project") for n in nodes.values() if n.get("project")}
    for proj in seen_projects:
        if proj and proj != "GLOBAL" and proj not in nodes:
            nodes[proj] = {"id": proj, "name": proj, "type": "project", "val": 25, "is_new": False}

    return {"nodes": list(nodes.values()), "links": links}


@app.get("/", response_class=HTMLResponse)
def index():
    return Path(__file__).parent.joinpath("index.html").read_text(encoding="utf-8")


@app.get("/api/graph")
def get_graph(
    project: str = Query("ALL", description="project_key o ALL"),
    since:   str = Query(None,  description="ISO timestamp — mostrar solo nodos creados antes de esta fecha")
):
    proj_filter = "" if project == "ALL" else f"AND project = @project"
    date_filter = "AND created_at <= @since" if since else ""

    kg_query = f"""
        SELECT
            subject, relation, object,
            confidence_score, project, team_name,
            TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), created_at, HOUR) < 24 AS is_new
        FROM `{PROJECT_ID}.{DATASET}.agent_knowledge_graph`
        WHERE 1=1 {proj_filter} {date_filter}
        LIMIT 2000
    """

    skills_query = f"""
        SELECT
            skill_id, title, keywords, success_rate, use_count, project,
            TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), created_at, HOUR) < 24 AS is_new
        FROM `{PROJECT_ID}.{DATASET}.agent_skills`
        WHERE active = true {proj_filter}
        LIMIT 500
    """

    try:
        client = get_bq_client()

        def run(query):
            job_config = None
            if project != "ALL" or since:
                from google.cloud.bigquery import QueryJobConfig, ScalarQueryParameter
                params = []
                if project != "ALL":
                    params.append(ScalarQueryParameter("project", "STRING", project))
                if since:
                    params.append(ScalarQueryParameter("since", "TIMESTAMP", since))
                job_config = QueryJobConfig(query_parameters=params)
            rows = client.query(query, job_config=job_config).result()
            return [dict(r) for r in rows]

        kg_rows    = run(kg_query)
        skill_rows = run(skills_query)
        graph      = build_graph(kg_rows, skill_rows)
        graph["meta"] = {"project": project, "kg_rows": len(kg_rows), "skill_rows": len(skill_rows)}
        return graph

    except Exception as e:
        return JSONResponse(
            status_code=200,
            content={
                "nodes": _demo_nodes(),
                "links": _demo_links(),
                "meta": {"project": project, "demo": True, "error": str(e)},
                "message": "BigQuery no disponible — mostrando datos de demo. Ejecutá el agente para poblar el grafo."
            }
        )


@app.get("/api/stats")
def get_stats():
    try:
        client = get_bq_client()
        q = f"""
            SELECT
              (SELECT COUNT(*)               FROM `{PROJECT_ID}.{DATASET}.agent_knowledge_graph`) AS total_triples,
              (SELECT COUNT(DISTINCT subject) FROM `{PROJECT_ID}.{DATASET}.agent_knowledge_graph`) AS total_entities,
              (SELECT COUNT(*)               FROM `{PROJECT_ID}.{DATASET}.agent_skills` WHERE active = true) AS total_skills,
              (SELECT COUNT(DISTINCT project) FROM `{PROJECT_ID}.{DATASET}.agent_knowledge_graph`) AS total_projects,
              (SELECT COUNT(*)               FROM `{PROJECT_ID}.{DATASET}.agent_knowledge_graph`
               WHERE TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), created_at, HOUR) < 24) AS new_today
        """
        row = list(client.query(q).result())[0]
        return dict(row)
    except Exception as e:
        return {"total_triples": 0, "total_entities": 0, "total_skills": 0,
                "total_projects": 0, "new_today": 0, "demo": True}


@app.get("/api/projects")
def get_projects():
    try:
        client = get_bq_client()
        q = f"""
            SELECT DISTINCT project FROM `{PROJECT_ID}.{DATASET}.agent_knowledge_graph`
            WHERE project IS NOT NULL
            UNION DISTINCT
            SELECT DISTINCT project FROM `{PROJECT_ID}.{DATASET}.agent_skills`
            WHERE project IS NOT NULL AND project != 'GLOBAL'
            ORDER BY project
        """
        return [r["project"] for r in (dict(row) for row in client.query(q).result())]
    except:
        return ["CMIV2", "SOLO", "APP_OFFLINE"]


# ── Demo data (shown when BigQuery is not available) ─────────────────────────

def _demo_nodes():
    return [
        {"id": "CMIV2",             "name": "CMIV2",              "type": "project",    "val": 25, "is_new": False},
        {"id": "Contact.Email__c",  "name": "Contact.Email__c",   "type": "sf_field",   "val": 8,  "is_new": True},
        {"id": "Sales_User",        "name": "Sales_User",         "type": "sf_profile", "val": 6,  "is_new": False},
        {"id": "Account.Type",      "name": "Account.Type",       "type": "sf_field",   "val": 5,  "is_new": False},
        {"id": "skill:dyn-forms",   "name": "Dynamic Forms Check","type": "skill",      "val": 4,  "is_new": True, "success_rate": 0.95},
        {"id": "dynamic_forms",     "name": "dynamic_forms",      "type": "condition",  "val": 7,  "is_new": False},
        {"id": "fls_restriction",   "name": "fls_restriction",    "type": "root_cause", "val": 5,  "is_new": False},
        {"id": "TC-0047",           "name": "TC-0047",            "type": "test_case",  "val": 3,  "is_new": False},
        {"id": "TC-0023",           "name": "TC-0023",            "type": "test_case",  "val": 2,  "is_new": False},
        {"id": "Validation_Rule_1", "name": "Validation Rule",    "type": "root_cause", "val": 4,  "is_new": False},
        {"id": "Contact_Page",      "name": "Contact Record Page","type": "sf_field",   "val": 3,  "is_new": False},
        {"id": "Partner_Account",   "name": "Account.Type=Partner","type": "condition", "val": 3,  "is_new": False},
    ]

def _demo_links():
    return [
        {"source": "Contact.Email__c", "target": "Sales_User",      "relation": "hidden_when",    "value": 0.95},
        {"source": "Sales_User",       "target": "fls_restriction",  "relation": "blocked_by",     "value": 0.9},
        {"source": "Contact_Page",     "target": "dynamic_forms",    "relation": "uses",           "value": 0.85},
        {"source": "dynamic_forms",    "target": "Account.Type",     "relation": "depends_on",     "value": 0.8},
        {"source": "Account.Type",     "target": "Partner_Account",  "relation": "triggers_flow",  "value": 0.75},
        {"source": "TC-0047",          "target": "Contact.Email__c", "relation": "tests",          "value": 1.0},
        {"source": "TC-0047",          "target": "fls_restriction",  "relation": "failed_because", "value": 0.95},
        {"source": "TC-0023",          "target": "Account.Type",     "relation": "tests",          "value": 1.0},
        {"source": "skill:dyn-forms",  "target": "dynamic_forms",    "relation": "covers",         "value": 0.7},
        {"source": "skill:dyn-forms",  "target": "fls_restriction",  "relation": "covers",         "value": 0.7},
        {"source": "Validation_Rule_1","target": "Contact.Email__c", "relation": "blocked_by",     "value": 0.6},
        {"source": "CMIV2",            "target": "Contact.Email__c", "relation": "contains",       "value": 0.5},
        {"source": "CMIV2",            "target": "Sales_User",       "relation": "contains",       "value": 0.5},
    ]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=False)

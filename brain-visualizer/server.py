"""
QA Agent Brain Visualizer — Backend
Construye el grafo de conocimiento dinámicamente desde BigQuery.
Toda la lógica de tipos, failure_rate, conexiones módulo→bug vive acá.

Correr: python server.py  →  http://localhost:8001
"""

import os
import re
import unicodedata
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

# ── Auth BigQuery: usar la key del SA qa-agent si no hay credenciales explícitas ──────────────
# El server consulta BQ con google.cloud.bigquery, que se autentica por ADC. El ADC global de la
# máquina puede estar apuntando a otra cuenta (p.ej. la personal gmail) SIN acceso a
# procontacto-claude → todas las queries dan 403 y los endpoints caen a demo/vacío. Para que el
# cortex funcione SIEMPRE (sin depender del ADC global ni de un login interactivo), si no está
# seteado GOOGLE_APPLICATION_CREDENTIALS buscamos la key del SA y la usamos solo en este proceso.
if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
    for _cand in (
        Path(__file__).resolve().parent / "sa.json",
        Path(__file__).resolve().parent.parent.parent / "qa-adk" / "sa.json",
    ):
        if _cand.exists():
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(_cand)
            print(f"[cortex] usando SA key para BigQuery: {_cand}")
            break
    else:
        print("[cortex] WARN: sin GOOGLE_APPLICATION_CREDENTIALS y sin sa.json — BQ usará el ADC global")

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


# Keywords por módulo — para conectar bugs/skills a su módulo por contenido.
# Escalable: cualquier bug nuevo se ata al módulo cuyo texto matchee mejor.
MODULE_KEYWORDS = {
    "Oportunidades":          ["oportunidad","opportunity","potencial","desarrollo de producto","monto","amount","stagename","opportunitylineitem","desarrollo de negocio"],
    "Gestión de Visitas":     ["visita","visit","tareas del cliente","medición","medicion","formulario nueva visita","intencionalidad","motivo de visita","tipo del evento","asunto"],
    "Gestión de Casos":       ["caso","case","reclamo","validación st","validacion st","resolutionsatisfaction","servicesuggestions","etapas del caso","área responsable","area responsable","tab resumen","marcar estado","servicio técnico","servicio tecnico"],
    "Gestión de Candidatos":  ["candidato","clasificacion","clasificación","notificacion","notificación","ebx","desarrollador responsable","get_user"],
    "Gestión de Prospectos":  ["prospecto","indirecto","directo","transformacion","transformación","casa matriz","macro canal","distribuidor","customertype","fecha_reclasific","customer","cliente indirecto"],
    "App Offline":            ["app offline","field service","mobile","offline","gps","sincroniz"],
    "Acuerdo de Desarrollo":  ["acuerdo","add","campo país","campo pais","tms","otro recursos","otros recursos","justificativo","otherbenefit","justification"],
    "Gestión de Rutas":       ["ruta","ventana de visita","cobrador","ruta avanzada"],
    "Consumer Goods Cloud":   ["cgcloud","consumer goods","salesforce maps"],
    "Servicio Técnico":       ["servicio técnico premezclas","servicio tecnico premezclas","premezclas"],
    "Segmentación":           ["segmentación","segmentacion"],
    "Perfilamiento":          ["perfilamiento","encuesta"],
    "Gestión de Eventos":     ["evento"],
    "Gestión de Contactos":   ["contacto","contact"],
    "Pagos":                  ["pago","estado_del_paquete","entrega en sucursal"],
    "Gestión de Despacho":    ["despacho","destinatarios_email","reporte de órdenes","reporte de ordenes"],
    "Expedicion":             ["expedicion","expedición","clase apex"],
    "Gestión de Órdenes":     ["orden","revertir full"],
    "Reservas":               ["reserva"],
    "Crear Reserva":          ["crear reserva","búsqueda por teléfono","busqueda por telefono"],
    "Bot de Mensajería":      ["bot","mensajería","mensajeria"],
}

def guess_module(text: str, available_modules: set):
    """Devuelve el módulo cuyo texto matchee mejor, o None. Solo módulos presentes."""
    t = (text or "").lower()
    best, best_score = None, 0
    for mod, kws in MODULE_KEYWORDS.items():
        if available_modules and mod not in available_modules:
            continue
        score = sum(1 for kw in kws if kw in t)
        if score > best_score:
            best_score, best = score, mod
    return best


def _normalize(s: str) -> str:
    """Minúsculas + sin tildes para comparación."""
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().strip()


KNOWN_PROJECTS: set = set()   # claves de proyecto NORMALIZADAS (config_canales); lo puebla get_graph


def infer_node_type(name: str, bug_ids: set = None, module_set: set = None) -> str:
    """Infiere el tipo del nodo dado su nombre."""
    n      = _normalize(name)
    name_l = name.lower()

    # Proyecto SIEMPRE primero — un nombre de proyecto nunca es otra cosa
    if n in KNOWN_PROJECTS or re.match(r'^(cmiv2|solo|cmi|global)$', n):
        return "project"

    # Tipos explícitos
    if bug_ids and name in bug_ids:
        return "bug"
    if module_set and n in module_set:
        return "module"
    if n in CANONICAL_MODULES:
        return "module"

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


def build_graph(kg_rows: list, skill_rows: list, known_projects: set = None, freeform: bool = True) -> dict:
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

    # b) Nombres canónicos de módulos (objetos de contains_module) y proyectos (subjects)
    canonical_modules: set = {
        row["object"] for row in kg_rows if row["relation"] == "contains_module"
    }
    project_keys: set = {
        row["subject"] for row in kg_rows if row["relation"] == "contains_module"
    }
    project_keys |= (known_projects or set())   # + proyectos de config_canales (aunque no tengan contains_module)
    # Versión normalizada para type inference.
    # Módulos = objects de contains_module + subjects de has_submodule/failure_rate.
    # OJO: NO incluir subjects de contains_module → esos son PROYECTOS, no módulos.
    module_names: set = { _normalize(m) for m in canonical_modules } | {
        _normalize(row["subject"]) for row in kg_rows
        if row["relation"] in ("has_submodule", "failure_rate")
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
            # Resolver el módulo del bug, en orden de preferencia:
            # 1) si el subject YA es un módulo → usarlo
            # 2) via issue_key → módulo (tested_in_module)
            # 3) keyword matching del texto del bug
            # 4) fallback: colgar del proyecto (nunca de un issue key suelto)
            module = None
            if subject in canonical_modules:
                module = subject
            elif issue_to_module.get(subject) in canonical_modules:
                module = issue_to_module.get(subject)
            else:
                module = guess_module(obj, canonical_modules)
            anchor = module if module else project   # proyecto como último recurso

            k = f"{anchor}||{obj}"
            if k not in bug_link_targets:
                bug_link_targets.add(k)
                upsert_node(anchor, "module" if module else "project", False, project=project)
                upsert_node(obj, "bug", is_new, project=project)
                links.append({"source": anchor, "target": obj, "relation": "has_open_bug", "value": conf})
            continue

        # Estructura del cerebro: proyecto→módulo y módulo→submódulo
        if relation in ("contains_module", "has_submodule"):
            upsert_node(subject, subj_type, is_new, project=project)
            upsert_node(obj,     obj_type,  is_new, project=project)
            links.append({"source": subject, "target": obj, "relation": relation, "value": conf})
        # Resto de relaciones (failure_rate, tested_in_module, has_label, failed_because,
        # signals, etc.) NO se renderizan como nodos sueltos — son metadata o ruido visual.

    # ── Paso 4: skills ───────────────────────────────────────────────────────

    for row in skill_rows:
        skill_id = f"skill:{row['skill_id']}"
        project  = row.get("project") or "GLOBAL"
        is_new   = bool(row.get("is_new", False))
        title    = row["title"]
        keywords = row.get("keywords") or ""
        sr       = float(row.get("success_rate") or 1.0)
        upsert_node(skill_id, "skill", is_new, label=title, project=project,
                    success_rate=sr, use_count=int(row.get("use_count") or 0))

        # Conectar la skill a su(s) ancla(s), sin crear nodos keyword sueltos:
        mod = guess_module(title + " " + keywords, canonical_modules)
        if mod:
            links.append({"source": skill_id, "target": mod, "relation": "covers", "value": sr})
        elif project != "GLOBAL" and project in project_keys:
            links.append({"source": skill_id, "target": project, "relation": "covers", "value": sr})
        else:
            # Skill GLOBAL sin módulo: cuelga de UN hub central "GLOBAL" (NO de todos los proyectos -> evita
            # la telaraña N×M, pero las skills quedan conectadas/marcadas como conjunto compartido).
            upsert_node("GLOBAL", "project", False, project="GLOBAL", label="GLOBAL")
            links.append({"source": "GLOBAL", "target": skill_id, "relation": "covers", "value": sr})

    # ── Paso 4.5: render del CONOCIMIENTO LIBRE de proyectos SIN backbone de módulos ──
    # Algunos proyectos (ej PDDARTEL) aprendieron MUCHO pero en relaciones libres
    # (blocked_by, depends_on, has_root_cause, missing_field…) y CERO contains_module -> sin esto
    # el nodo proyecto se ve VACÍO aunque haya testeado un montón. Renderizamos esas triples como
    # subject→object (ambos nodos, con la relación real) y colgamos el subject del proyecto, para que
    # el cluster sea visible y conectado. Saltamos relaciones de PURA métrica (no son entidades).
    _STRUCT = {"contains_module", "has_submodule", "has_open_bug", "covers"}
    _META = {"failure_rate", "has_failed_tc_count", "has_label", "confidence_score",
             "validation_result", "execution_result", "verification_result", "has_test_result",
             "execution_outcome", "retest_confirmed", "test_platform", "display_format"}
    # tested_in / tested_in_module NO se dibujan como edge propio (son metadata de ubicación), pero SÍ se usan
    # para ANCLAR cada subject a su módulo (issue_to_module). Así el tamaño del cluster de cada proyecto es
    # proporcional a lo aprendido, y el conocimiento libre queda ANIDADO bajo el módulo (no un hairball).
    _META_ANCHOR = {"tested_in_module", "tested_in"}
    _known = known_projects or set()
    _anchored = set()
    def _ff_type(name):   # un subject/object de conocimiento LIBRE nunca debe tiparse como 'project' (ej "CMI")
        t = infer_node_type(name, bug_ids, module_names)
        return "generic" if t == "project" else t
    for row in (kg_rows if freeform else []):   # conocimiento libre SOLO al filtrar un proyecto (no en "Todos")
        rel = row["relation"]; p = row.get("project")
        if rel in _STRUCT or rel in _META or rel in _META_ANCHOR:
            continue
        if not p or p not in _known:
            continue   # TODOS los proyectos conocidos (con o sin backbone propio)
        subj = row.get("subject"); obj = row.get("object")
        if not subj or _normalize(subj) == _normalize(p):
            continue
        is_new = bool(row.get("is_new", False))
        upsert_node(subj, _ff_type(subj), is_new, project=p)
        # subject -> object (el conocimiento real), si el object parece una entidad (no un valor largo)
        if obj and len(str(obj)) <= 60 and _normalize(obj) not in (_normalize(subj), _normalize(p)):
            upsert_node(obj, _ff_type(obj), False, project=p)
            links.append({"source": subj, "target": obj, "relation": rel,
                          "value": float(row.get("confidence_score") or 0.6)})
        # anclar el subject a su MÓDULO (si es un issue con módulo conocido) o, si no, al PROYECTO (una sola vez)
        if subj not in _anchored:
            _anchored.add(subj)
            mod = issue_to_module.get(subj)
            if mod in canonical_modules:
                upsert_node(mod, "module", False, project=p)
                links.append({"source": mod, "target": subj, "relation": "tracks", "value": 0.3})
            else:
                upsert_node(p, "project", False, project=p)
                links.append({"source": p, "target": subj, "relation": "tracks", "value": 0.3})

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
        # Proyectos conocidos (config_canales) -> el grafo los reconoce como proyectos, ancla sus
        # triples sueltos al nodo proyecto, y cuelga las skills GLOBAL de TODOS ellos.
        global KNOWN_PROJECTS
        try:
            known_projects = {r["project"] for r in client.query(
                f"SELECT DISTINCT project FROM `{PROJECT_ID}.{DATASET}.config_canales` "
                f"WHERE project IS NOT NULL").result() if r["project"]}
        except Exception:
            known_projects = set()
        KNOWN_PROJECTS = {_normalize(p) for p in known_projects}
        graph      = build_graph(kg_rows, skill_rows, known_projects, freeform=True)   # conocimiento libre SIEMPRE (también en "Todos")

        # Sembrar TODOS los proyectos conocidos desde config_canales (para que aparezcan aunque
        # todavía no tengan conocimiento aprendido en el KG — ej proyectos recién onboardeados).
        if project == "ALL":
            try:
                existing = {n["id"] for n in graph["nodes"]}
                seeded = 0
                for r in client.query(
                    f"SELECT project, ANY_VALUE(project_name) AS pname FROM `{PROJECT_ID}.{DATASET}.config_canales` "
                    f"WHERE project IS NOT NULL GROUP BY project"
                ).result():
                    p = r["project"]; pname = r["pname"]
                    if p and p not in existing:
                        label = f"{p} · {pname}" if (pname and pname != p) else p   # ej "IMPSLJ · SALJAMEX"
                        graph["nodes"].append({"id": p, "name": label, "type": "project",
                                               "val": 18, "is_new": False, "empty": True})
                        seeded += 1
                graph["seeded_projects"] = seeded
            except Exception:
                pass

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


@app.get("/api/costs")
def get_costs(project: str = Query("ALL"), limit: int = Query(300)):
    """Ledger de costos (Capa 1). Devuelve agregados POR PROYECTO + ejecuciones recientes (expand/búsqueda).
    Lee qa_agent.run_costs (estimación in-app). Si la tabla no existe / sin datos -> ok:false, listas vacías."""
    try:
        from google.cloud import bigquery
        from google.cloud.bigquery import QueryJobConfig, ScalarQueryParameter
        client = bigquery.Client(project=PROJECT_ID)

        by_proj = [dict(r) for r in client.query(f"""
            SELECT project,
              COUNT(*) AS runs,
              ROUND(SUM(total_usd), 4)     AS total_usd,
              ROUND(SUM(deepseek_usd), 4)  AS deepseek_usd,
              ROUND(SUM(cloudrun_usd), 4)  AS cloudrun_usd,
              ROUND(SUM(gemini_usd), 4)    AS gemini_usd,
              ROUND(SUM(bigquery_usd), 4)  AS bigquery_usd,
              ROUND(SUM(vm_usd), 4)        AS vm_usd,
              ROUND(AVG(total_usd), 4)     AS avg_usd,
              MAX(ts)                      AS last_run
            FROM `{PROJECT_ID}.{DATASET}.run_costs`
            GROUP BY project ORDER BY total_usd DESC
        """).result()]

        proj_filter = "" if project == "ALL" else "WHERE project = @project"
        cfg = None if project == "ALL" else QueryJobConfig(
            query_parameters=[ScalarQueryParameter("project", "STRING", project)])
        execs = [dict(r) for r in client.query(f"""
            SELECT run_id, ts, project, issue, platform, verdict, duration_s,
                   deepseek_calls, deepseek_usd, cloudrun_usd, total_usd
            FROM `{PROJECT_ID}.{DATASET}.run_costs`
            {proj_filter}
            ORDER BY ts DESC LIMIT {int(limit)}
        """, job_config=cfg).result()]

        grand = round(sum((p.get("total_usd") or 0) for p in by_proj), 4)
        return {"by_project": by_proj, "executions": execs,
                "grand_total_usd": grand, "total_runs": sum(p["runs"] for p in by_proj), "ok": True}
    except Exception as e:
        return {"by_project": [], "executions": [], "grand_total_usd": 0,
                "total_runs": 0, "ok": False, "error": str(e)}


@app.get("/api/deepseek-balance")
def deepseek_balance():
    """Saldo restante de la cuenta DeepSeek (API GET /user/balance). El key se lee de
    Secret Manager (DEEPSEEK_API_KEY) con las credenciales de gcloud locales."""
    try:
        import urllib.request, json, os, subprocess, shutil
        # key: env -> Secret Manager (si está la lib) -> gcloud CLI (fallback sin dep)
        key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        if not key:
            try:
                from google.cloud import secretmanager
                sm = secretmanager.SecretManagerServiceClient()
                key = sm.access_secret_version(
                    name=f"projects/{PROJECT_ID}/secrets/DEEPSEEK_API_KEY/versions/latest").payload.data.decode().strip()
            except Exception:
                gc = shutil.which("gcloud") or "gcloud"
                key = subprocess.run([gc, "secrets", "versions", "access", "latest",
                                      "--secret", "DEEPSEEK_API_KEY", "--project", PROJECT_ID],
                                     capture_output=True, text=True, timeout=25).stdout.strip()
        if not key:
            return {"ok": False, "error": "no pude obtener DEEPSEEK_API_KEY (env/secretmanager/gcloud)"}
        req = urllib.request.Request(
            "https://api.deepseek.com/user/balance",
            headers={"Authorization": f"Bearer {key}", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        infos = data.get("balance_infos") or []
        usd = next((b for b in infos if (b.get("currency") or "").upper() == "USD"),
                   (infos[0] if infos else {}))
        def _f(v):
            try: return round(float(v), 2)
            except Exception: return 0.0
        return {"ok": True,
                "is_available": bool(data.get("is_available")),
                "currency": usd.get("currency", "USD"),
                "total_balance": _f(usd.get("total_balance", 0)),
                "granted_balance": _f(usd.get("granted_balance", 0)),
                "topped_up_balance": _f(usd.get("topped_up_balance", 0))}
    except Exception as e:
        return {"ok": False, "error": str(e)}


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

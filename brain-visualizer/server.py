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
# Export de facturación REAL de GCP (fuente de verdad; distinto de qa_agent.run_costs que es estimación in-app).
# Vive en procontacto-bi. El SA qa-agent NO tiene acceso ahí, pero el USUARIO (axel.colamarino) SÍ -> el billing
# se consulta con el ADC de USUARIO (gcloud application-default), no con el SA. Ver _billing_client().
BILLING_TABLE = "procontacto-bi.raw_gcp_billing.gcp_billing_export_v1_01E617_7DB838_84F9C5"


def _billing_client():
    """Cliente BQ para el billing REAL: usa el ADC de USUARIO (gcloud application-default), que SÍ tiene acceso a
    procontacto-bi (el SA no). Como Cortex corre local en la máquina del usuario, puede usar sus credenciales sin
    depender de ningún grant al SA. Si no hay ADC de usuario, cae al default (SA) -> fallará con 403 y el endpoint
    lo reporta con el hint de correr `gcloud auth application-default login`."""
    from google.cloud import bigquery
    import google.auth
    # ADC de usuario de gcloud (independiente del sa.json que server.py fuerza para el resto de queries).
    adc = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_USER")
    if not (adc and os.path.exists(adc)):
        base = os.environ.get("CLOUDSDK_CONFIG") or (
            os.path.join(os.environ.get("APPDATA", ""), "gcloud") if os.name == "nt"
            else os.path.join(os.path.expanduser("~"), ".config", "gcloud"))
        cand = os.path.join(base, "application_default_credentials.json")
        adc = cand if os.path.exists(cand) else None
    if adc:
        creds, _ = google.auth.load_credentials_from_file(
            adc, scopes=["https://www.googleapis.com/auth/cloud-platform"])
        return bigquery.Client(project=PROJECT_ID, credentials=creds)
    return bigquery.Client(project=PROJECT_ID)   # fallback (SA); probablemente 403 en procontacto-bi


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


def _canon_key(s: str) -> str:
    """Clave de MERGE de variantes de nombre que el learner escribe distinto para la misma entidad:
    'Operador Logístico' ≡ 'Operador Logistico' ≡ 'Operador_Logistico' ≡ 'Operador_Logistico__c',
    'Templates_WhatsApp' ≡ 'WhatsApp Templates'. Sin acentos, lower, sin sufijo __c/__r, _ y
    puntuación -> espacio, y palabras ORDENADAS (mata inversiones de orden)."""
    t = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower().strip()
    t = re.sub(r"__[cr]\b", "", t)          # sufijos de API name de Salesforce
    t = re.sub(r"[^a-z0-9]+", " ", t)       # _ , - , . , etc -> espacio
    return " ".join(sorted(t.split()))


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

    # Backbone VÁLIDO: excluye proyectos stray (no en config_canales, ej TQ/TEST) y el backfill en proyectos que YA
    # tienen backbone real del learner (CMIV2/SOLO usan su mapa limpio; PDDARTEL/DENTAL sí usan el backfill porque no tenían).
    _known = known_projects or set()
    _real_bb = {row["subject"] for row in kg_rows
                if row["relation"] == "contains_module" and row.get("source_issue_key") != "backfill_test_cases"}
    def _cm_valido(row):
        if row["relation"] != "contains_module":
            return False
        if _known and row["subject"] not in _known:
            return False
        if row.get("source_issue_key") == "backfill_test_cases" and row["subject"] in _real_bb:
            return False
        return True

    # b) Nombres canónicos de módulos (objetos de contains_module VÁLIDO) y proyectos (subjects)
    canonical_modules: set = { row["object"]  for row in kg_rows if _cm_valido(row) }
    project_keys:      set = { row["subject"] for row in kg_rows if _cm_valido(row) }
    project_keys |= _known   # + proyectos de config_canales (aunque no tengan contains_module)
    # Versión normalizada para type inference.
    # Módulos = objects de contains_module + subjects de has_submodule/failure_rate.
    # OJO: NO incluir subjects de contains_module → esos son PROYECTOS, no módulos.
    module_names: set = { _normalize(m) for m in canonical_modules } | {
        _normalize(row["subject"]) for row in kg_rows
        if row["relation"] in ("has_submodule", "failure_rate")
    }

    # b2) Dueño de cada módulo canónico (para namespacear ids cross-proyecto) + pares exactos
    # (proyecto, módulo) para NUNCA anclar un bug/knowledge a un módulo homónimo de OTRO proyecto.
    module_project: dict = {}
    module_pairs: set = set()
    for row in kg_rows:
        if _cm_valido(row):
            module_pairs.add((row["subject"], row["object"]))
            if row["object"] not in module_project:
                module_project[row["object"]] = row["subject"]

    # IDs CANÓNICOS POR PROYECTO — arregla dos males vistos en el grafo real:
    # (a) MERGE de variantes que el learner escribe distinto para la misma entidad
    #     ('Operador Logístico'/'Operador Logistico'/'Operador_Logistico'/'Operador_Logistico__c'
    #     eran 4 nodos regados con los hijos repartidos -> spaghetti de links de 1000+px);
    # (b) SPLIT de nombres iguales de proyectos distintos ('Campos' de CMIV2 y el de PDDARTEL
    #     compartían UN nodo -> línea cruzando ambos clusters).
    def _nid(name, project):
        s = str(name)
        if s.startswith("skill:") or s in project_keys or s == "GLOBAL":
            return s                      # proyectos y skills no se namespacean
        return f"{project or 'GLOBAL'}::{_canon_key(s)}"

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

    _TYPE_PRIO = {"project": 5, "skill": 5, "module": 4, "bug": 3}   # resto = 1

    def upsert_node(node_id: str, node_type: str, is_new: bool = False, **extra):
        label = extra.pop("label", node_id)
        if node_id not in nodes:
            # Truncar labels largos (bugs tienen summaries de 120 chars)
            display = (label[:35] + "…") if len(label) > 38 else label
            # Tamaño base según jerarquía
            base_val = 27 if node_type == "project" else 8 if node_type == "module" else 3 if node_type == "skill" else 2 if node_type == "bug" else 1
            nodes[node_id] = {
                "id":      node_id,
                "name":    display,
                "_raw":    label,
                "type":    node_type,
                "val":     base_val,
                "is_new":  is_new,
                **extra
            }
        else:
            nd = nodes[node_id]
            # merge de VARIANTES (mismo id canónico): quedarse con el label más "humano"
            # (con acentos y espacios gana a API-names tipo Operador_Logistico__c)
            def _score(t): return (any(ord(c) > 127 for c in t), " " in t, len(t))
            if label != node_id and _score(label) > _score(nd.get("_raw", nd["name"])):
                nd["_raw"] = label
                nd["name"] = (label[:35] + "…") if len(label) > 38 else label
            # y con el TIPO más fuerte (module gana a generic/sf_field)
            if _TYPE_PRIO.get(node_type, 1) > _TYPE_PRIO.get(nd["type"], 1):
                nd["type"] = node_type
            if node_type not in ("project", "module", "bug"):
                nd["val"] += 1  # solo aumentar val para nodos genéricos
            if is_new:
                nd["is_new"] = True

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
            # NUNCA anclar a un módulo homónimo de OTRO proyecto (dibujaba una línea cross-cluster):
            # el módulo tiene que existir en ESTE proyecto; si no, el ancla es el proyecto.
            if module and (project, module) not in module_pairs:
                module = None
            anchor = module if module else project   # proyecto como último recurso

            anchor_id = _nid(anchor, project)
            bug_id = _nid(obj, project)
            k = f"{anchor_id}||{bug_id}"
            if k not in bug_link_targets:
                bug_link_targets.add(k)
                upsert_node(anchor_id, "module" if module else "project", False, label=anchor, project=project)
                upsert_node(bug_id, "bug", is_new, label=obj, project=project)
                links.append({"source": anchor_id, "target": bug_id, "relation": "has_open_bug", "value": conf})
            continue

        # Estructura del cerebro: proyecto→módulo y módulo→submódulo
        if relation == "contains_module":
            if not _cm_valido(row):
                continue   # proyecto stray (TQ/TEST) o backfill en proyecto con backbone real -> no renderizar
            oid = _nid(obj, subject)   # el dueño del módulo es el subject (el proyecto)
            upsert_node(subject, subj_type, is_new, label=subject, project=project)
            upsert_node(oid,     obj_type,  is_new, label=obj, project=project)
            links.append({"source": subject, "target": oid, "relation": relation, "value": conf})
        elif relation == "has_submodule":
            sid = _nid(subject, project)   # todo queda dentro del proyecto de la fila
            oid = _nid(obj, project)
            upsert_node(sid, subj_type, is_new, label=subject, project=project)
            upsert_node(oid, obj_type,  is_new, label=obj, project=project)
            links.append({"source": sid, "target": oid, "relation": relation, "value": conf})
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
            links.append({"source": skill_id, "target": _nid(mod, module_project.get(mod, project)),
                          "relation": "covers", "value": sr})
        elif project != "GLOBAL" and project in project_keys:
            links.append({"source": skill_id, "target": project, "relation": "covers", "value": sr})
        else:
            # Skill GLOBAL sin módulo -> conectada a CADA proyecto = la "estrella" radial de skills compartidas
            # (es lo que el usuario quiere ver). Con R1 amplio + alpha baja queda como estrella, no telaraña.
            for p in project_keys:
                links.append({"source": skill_id, "target": p, "relation": "covers", "value": sr})

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
        sid = _nid(subj, p)
        upsert_node(sid, _ff_type(subj), is_new, label=subj, project=p)
        # subject -> object (el conocimiento real), si el object parece una entidad (no un valor largo)
        if obj and len(str(obj)) <= 60 and _normalize(obj) not in (_normalize(subj), _normalize(p)):
            oid = _nid(obj, p)
            upsert_node(oid, _ff_type(obj), False, label=obj, project=p)
            links.append({"source": sid, "target": oid, "relation": rel,
                          "value": float(row.get("confidence_score") or 0.6)})
        # anclar el subject a su MÓDULO (si es un issue con módulo conocido) o, si no, al PROYECTO (una sola vez)
        if sid not in _anchored:
            _anchored.add(sid)
            mod = issue_to_module.get(subj)
            if mod and (p, mod) in module_pairs:   # solo módulos de ESTE proyecto (no homónimos ajenos)
                mid = _nid(mod, p)
                upsert_node(mid, "module", False, label=mod, project=p)
                links.append({"source": mid, "target": sid, "relation": "tracks", "value": 0.3})
            else:
                upsert_node(p, "project", False, label=p, project=p)
                links.append({"source": p, "target": sid, "relation": "tracks", "value": 0.3})

    # ── Paso 5: enriquecer módulos con failure_rate_pct ──────────────────────

    for node_id, node in nodes.items():
        if node["type"] == "module":
            # el id ahora es "PROYECTO::clave canonica" -> matchear failure_rates por clave canónica
            n_ck = node_id.split("::", 1)[1] if "::" in node_id else _canon_key(node_id)
            fr = next((v for k, v in failure_rates.items() if _canon_key(k) == n_ck), -1.0)
            node["failure_rate_pct"] = fr

    # ── Paso 6: asegurar nodos de proyecto ───────────────────────────────────

    seen_projects = {n.get("project") for n in nodes.values() if n.get("project")}
    for proj in seen_projects:
        if proj and proj != "GLOBAL" and proj not in nodes:
            nodes[proj] = {"id": proj, "name": proj, "type": "project",
                           "val": 80, "is_new": False}

    # ── Paso 7: dedupe de links (el merge de variantes puede duplicar) + sin self-loops ──
    _seen_l, uniq_links = set(), []
    for l in links:
        if l["source"] == l["target"]:
            continue
        k = (l["source"], l["target"], l["relation"])
        if k in _seen_l:
            continue
        _seen_l.add(k)
        uniq_links.append(l)

    return {"nodes": list(nodes.values()), "links": uniq_links}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index():
    return Path(__file__).parent.joinpath("cortex-standalone.html").read_text(encoding="utf-8")


@app.get("/api/graph")
def get_graph(project: str = Query("ALL")):
    proj_filter = "" if project == "ALL" else "AND project = @project"

    kg_query = f"""
        SELECT subject, relation, object, confidence_score, project, source_issue_key,
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
        graph      = build_graph(kg_rows, skill_rows, known_projects, freeform=(project != "ALL"))   # panorama limpio (estrella); detalle al filtrar

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
def get_costs(project: str = Query("ALL"), limit: int = Query(300), month: str = Query("current")):
    """Ledger de costos (Capa 1). Devuelve agregados POR PROYECTO + ejecuciones recientes (expand/búsqueda).
    Lee qa_agent.run_costs (estimación in-app). Filtra por MES: 'current' (mes actual, default), 'all' (histórico),
    o 'YYYY-MM'. Devuelve 'months' (meses con datos) para poblar el selector. ok:false si la tabla no existe."""
    try:
        from google.cloud import bigquery
        from google.cloud.bigquery import QueryJobConfig, ScalarQueryParameter
        client = bigquery.Client(project=PROJECT_ID)
        tbl = f"`{PROJECT_ID}.{DATASET}.run_costs`"

        # meses disponibles (para el <select> del front)
        months = [r["m"] for r in client.query(
            f"SELECT DISTINCT FORMAT_TIMESTAMP('%Y-%m', ts) AS m FROM {tbl} WHERE ts IS NOT NULL ORDER BY m DESC"
        ).result()]
        cur_month = months[0] if months else None

        # cláusula de mes reutilizable
        params, month_clause, sel_month = [], "", month
        if month == "all":
            month_clause = ""
        else:
            if month == "current":
                sel_month = cur_month   # el mes más reciente con datos
            if sel_month:
                month_clause = "FORMAT_TIMESTAMP('%Y-%m', ts) = @month"
                params.append(ScalarQueryParameter("month", "STRING", sel_month))

        def _where(extra=""):
            conds = [c for c in (month_clause, extra) if c]
            return ("WHERE " + " AND ".join(conds)) if conds else ""

        cfg = QueryJobConfig(query_parameters=params) if params else None
        by_proj = [dict(r) for r in client.query(f"""
            SELECT project, COUNT(*) AS runs,
              ROUND(SUM(total_usd), 4)     AS total_usd,
              ROUND(SUM(deepseek_usd), 4)  AS deepseek_usd,
              ROUND(SUM(cloudrun_usd), 4)  AS cloudrun_usd,
              ROUND(SUM(gemini_usd), 4)    AS gemini_usd,
              ROUND(SUM(bigquery_usd), 4)  AS bigquery_usd,
              ROUND(SUM(vm_usd), 4)        AS vm_usd,
              ROUND(AVG(total_usd), 4)     AS avg_usd,
              MAX(ts)                      AS last_run
            FROM {tbl} {_where()}
            GROUP BY project ORDER BY total_usd DESC
        """, job_config=cfg).result()]

        params2 = list(params)
        proj_extra = ""
        if project != "ALL":
            proj_extra = "project = @project"
            params2.append(ScalarQueryParameter("project", "STRING", project))
        cfg2 = QueryJobConfig(query_parameters=params2) if params2 else None
        execs = [dict(r) for r in client.query(f"""
            SELECT run_id, ts, project, issue, platform, verdict, duration_s,
                   deepseek_calls, deepseek_usd, cloudrun_usd, total_usd
            FROM {tbl} {_where(proj_extra)}
            ORDER BY ts DESC LIMIT {int(limit)}
        """, job_config=cfg2).result()]

        grand = round(sum((p.get("total_usd") or 0) for p in by_proj), 4)
        return {"by_project": by_proj, "executions": execs, "grand_total_usd": grand,
                "total_runs": sum(p["runs"] for p in by_proj), "ok": True,
                "months": months, "selected_month": (sel_month if month != "all" else "all")}
    except Exception as e:
        return {"by_project": [], "executions": [], "grand_total_usd": 0, "total_runs": 0,
                "months": [], "selected_month": None, "ok": False, "error": str(e)}


@app.get("/api/gcp-billing")
def get_gcp_billing(month: str = Query("current")):
    """Gasto REAL de GCP (billing export, no estimación). Neto = cost + créditos. Por servicio y por proyecto,
    en MXN y USD (usando la currency_conversion_rate real del export). Filtra por MES ('current'|'all'|'YYYY-MM').
    Usa el ADC de USUARIO (gcloud application-default) porque el billing vive en procontacto-bi y el SA no llega ahí
    (ver _billing_client). NO incluye DeepSeek (se factura fuera de GCP; eso está en /api/costs)."""
    try:
        from google.cloud.bigquery import QueryJobConfig, ScalarQueryParameter
        client = _billing_client()   # ADC de usuario (tiene acceso a procontacto-bi), NO el SA
        tbl = f"`{BILLING_TABLE}`"

        months = [r["m"] for r in client.query(
            f"SELECT DISTINCT FORMAT_DATE('%Y-%m', DATE(usage_start_time)) AS m FROM {tbl} "
            f"WHERE usage_start_time IS NOT NULL ORDER BY m DESC"
        ).result()]
        cur_month = months[0] if months else None

        params, month_clause, sel_month = [], "", month
        if month != "all":
            if month == "current":
                sel_month = cur_month
            if sel_month:
                month_clause = "WHERE FORMAT_DATE('%Y-%m', DATE(usage_start_time)) = @month"
                params.append(ScalarQueryParameter("month", "STRING", sel_month))
        cfg = QueryJobConfig(query_parameters=params) if params else None

        # neto MXN + USD (usando la tasa real de conversión del propio export)
        net_mxn = "SUM(cost) + SUM((SELECT IFNULL(SUM(c.amount),0) FROM UNNEST(credits) c))"
        rate = "AVG(currency_conversion_rate)"
        by_service = [dict(r) for r in client.query(f"""
            SELECT service.description AS service,
                   ROUND({net_mxn}, 2) AS mxn,
                   ROUND(SAFE_DIVIDE({net_mxn}, {rate}), 2) AS usd
            FROM {tbl} {month_clause}
            GROUP BY service HAVING mxn > 0 ORDER BY mxn DESC
        """, job_config=cfg).result()]
        by_project = [dict(r) for r in client.query(f"""
            SELECT project.id AS project,
                   ROUND({net_mxn}, 2) AS mxn,
                   ROUND(SAFE_DIVIDE({net_mxn}, {rate}), 2) AS usd
            FROM {tbl} {month_clause}
            GROUP BY project HAVING mxn > 0 ORDER BY mxn DESC
        """, job_config=cfg).result()]

        g_mxn = round(sum((s.get("mxn") or 0) for s in by_service), 2)
        g_usd = round(sum((s.get("usd") or 0) for s in by_service), 2)
        agent = next((p for p in by_project if p.get("project") == PROJECT_ID), None)
        return {"ok": True, "currency": "MXN", "by_service": by_service, "by_project": by_project,
                "grand_mxn": g_mxn, "grand_usd": g_usd,
                "agent_mxn": (agent or {}).get("mxn", 0), "agent_usd": (agent or {}).get("usd", 0),
                "months": months, "selected_month": (sel_month if month != "all" else "all")}
    except Exception as e:
        msg = str(e)
        if "403" in msg or "does not have" in msg or "Access Denied" in msg or "default credentials" in msg.lower():
            msg = ("Sin acceso al billing con las credenciales actuales. Corré una vez: "
                   "`gcloud auth application-default login` con tu cuenta corp (axel.colamarino@procontacto.com.mx). "
                   f"Detalle: {str(e)[:160]}")
        return {"ok": False, "by_service": [], "by_project": [], "grand_mxn": 0, "grand_usd": 0,
                "months": [], "selected_month": None, "error": msg}


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

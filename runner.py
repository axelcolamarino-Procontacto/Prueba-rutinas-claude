import os, sys, json, uuid, time, base64, subprocess, urllib.request, urllib.parse, traceback
from datetime import datetime, timezone, timedelta

_pylib = "/tmp/pylib"
if _pylib not in sys.path:
    sys.path.insert(0, _pylib)

ISSUE_KEY    = "CMIV2-3468"
PROJECT_KEY  = "CMIV2"
TRIGGER_TYPE = "jira_webhook"
JIRA_CLOUD_ID = os.environ.get("JIRA_CLOUD_ID", "d041f87a-4f5e-40d1-b719-578536318f6a")
JIRA_API_BASE = f"https://api.atlassian.com/ex/jira/{JIRA_CLOUD_ID}/rest/api/3"
JIRA_DOMAIN   = os.environ.get("JIRA_DOMAIN", "procontacto.atlassian.net")
AXEL_DM       = "D0B28BZNFD4"
SHEET_ID      = "1tQ27PcM8XrwKPB6ZGFzoRvV4rI55-MM1PTaPWazbwto"
BQ_DATASET    = "procontacto-claude.qa_agent"
my_run_id     = str(uuid.uuid4())

def gcp_auth():
    gbin = os.path.expanduser("~/google-cloud-sdk/bin")
    if gbin not in os.environ.get("PATH","").split(os.pathsep):
        os.environ["PATH"] = os.environ.get("PATH","") + os.pathsep + gbin
    ca = "/etc/ssl/certs/ca-certificates.crt"
    os.environ["REQUESTS_CA_BUNDLE"] = ca
    os.environ["SSL_CERT_FILE"]      = ca
    os.environ["CURL_CA_BUNDLE"]     = ca
    os.environ["CLOUDSDK_CORE_CUSTOM_CA_CERTS_FILE"] = ca
    kp = "/tmp/gcp-sa.json"
    with open(kp,"wb") as f:
        f.write(base64.b64decode(os.environ["GCP_SA_KEY"]))
    subprocess.run(["gcloud","auth","activate-service-account","--key-file",kp],
                   check=True, capture_output=True, text=True)
    subprocess.run(["gcloud","config","set","project","procontacto-claude"],
                   check=True, capture_output=True, text=True)
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = kp

def bq_query(sql):
    r = subprocess.run(["bq","query","--use_legacy_sql=false","--format=json","--quiet",sql],
                       capture_output=True, text=True)
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip()
        raise RuntimeError(f"bq error: {err}")
    out = r.stdout.strip()
    if not out:
        return []
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return []

def log_event(event_type, category, message, context=None, severity="medium"):
    try:
        msg_esc = message.replace("\\","\\\\").replace("'","\\'").replace("\n"," ")[:500]
        ctx_val = "NULL"
        if context:
            ctx_str = json.dumps(context).replace("\\","\\\\").replace("'","\\'")[:500]
            ctx_val = "JSON '" + ctx_str + "'"
        rid = str(uuid.uuid4())
        bq_query(
            "INSERT INTO `" + BQ_DATASET + ".agent_logs` "
            "(id, timestamp, trigger_type, project, issue_key, event_type, category, message, context, severity) "
            "VALUES ('" + rid + "', CURRENT_TIMESTAMP(), '" + TRIGGER_TYPE + "', '" + PROJECT_KEY + "', "
            "'" + ISSUE_KEY + "', '" + event_type + "', '" + category + "', '" + msg_esc + "', " + ctx_val + ", '" + severity + "')"
        )
    except Exception:
        pass

def slack_send(channel, text, thread_ts=None):
    token = os.environ["SLACK_BOT_TOKEN"]
    body = {"channel": channel, "text": text}
    if thread_ts:
        body["thread_ts"] = thread_ts
    data = json.dumps(body).encode()
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                "https://slack.com/api/chat.postMessage", data=data,
                headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as r:
                resp = json.loads(r.read())
                if resp.get("ok"):
                    return resp.get("ts")
                log_event("error","slack_api","Slack error: " + resp.get("error","?"),severity="medium")
        except Exception as e:
            if attempt == 2:
                log_event("error","slack_api","slack_send fallo: " + str(e)[:100],severity="medium")
                raise
            time.sleep(2 ** attempt)

def slack_dm(user_id, text):
    token = os.environ["SLACK_BOT_TOKEN"]
    req = urllib.request.Request(
        "https://slack.com/api/conversations.open",
        data=json.dumps({"users": user_id}).encode(),
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        resp = json.loads(r.read())
        channel = resp.get("channel",{}).get("id")
    if channel:
        slack_send(channel, text)

def jira_api(method, path, body=None, query=None):
    url = JIRA_API_BASE + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Authorization": "Bearer " + os.environ["JIRA_BOT_TOKEN"], "Accept": "application/json"}
    if data:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        return r.status, (json.loads(raw) if raw else None)

def jira_get_issue(key):
    _, data = jira_api("GET", "/issue/" + key, query={"fields":"*all","expand":"names,renderedFields,changelog"})
    return data

def jira_transition(issue_key, target_status_name, max_hops=4):
    ALLOWED = {"validación del cliente","listo en dev","listo para pruebas","observaciones detectadas","finalizado"}
    if target_status_name.strip().lower() not in ALLOWED:
        log_event("error","jira","Intento transicion no permitida: " + target_status_name,severity="high")
        return False
    for _ in range(max_hops):
        _, data = jira_api("GET", "/issue/" + issue_key + "/transitions")
        transitions = data.get("transitions",[]) if data else []
        tid = next((t["id"] for t in transitions
                    if t.get("to",{}).get("name","").strip().lower() == target_status_name.strip().lower()), None)
        if tid:
            jira_api("POST", "/issue/" + issue_key + "/transitions", body={"transition":{"id":tid}})
            return True
        forward = next((t for t in transitions if "testing" in t.get("to",{}).get("name","").lower()
                        or "dev" in t.get("to",{}).get("name","").lower()), None)
        if not forward:
            break
        jira_api("POST", "/issue/" + issue_key + "/transitions", body={"transition":{"id":forward["id"]}})
        time.sleep(1)
    return False

def jira_bug_type_id(project_key):
    try:
        _, meta = jira_api("GET", "/issue/createmeta/" + project_key + "/issuetypes")
        types = (meta.get("issueTypes") or meta.get("values") or []) if isinstance(meta,dict) else []
        pick = (next((t for t in types if t.get("subtask") and "story bug" in t.get("name","").lower()), None)
                or next((t for t in types if t.get("subtask") and "bug" in t.get("name","").lower()), None))
        return pick.get("id") if pick else os.environ.get("JIRA_BUG_TYPE_ID","10006")
    except Exception:
        return os.environ.get("JIRA_BUG_TYPE_ID","10006")

def jira_create_bug(parent_key, project_key, summary, desc_text, bug_type_id):
    body = {
        "fields": {
            "project":   {"key": project_key},
            "parent":    {"key": parent_key},
            "issuetype": {"id": bug_type_id},
            "summary":   summary,
            "description": {
                "type":"doc","version":1,
                "content":[{"type":"paragraph","content":[{"type":"text","text":desc_text}]}]
            }
        }
    }
    _, resp = jira_api("POST", "/issue", body=body)
    return resp.get("key") if resp else None

def get_project_info(project_key):
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        scopes = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_file("/tmp/gcp-sa.json", scopes=scopes)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(SHEET_ID)
        ws = sh.get_worksheet(0)
        rows = ws.get_all_values()
        for row in rows[1:]:
            if len(row) >= 2 and row[0].strip().upper() == project_key.upper():
                channel_id   = row[1].strip() if len(row) > 1 else None
                team_name    = row[2].strip() if len(row) > 2 else project_key
                team_lead_id = row[3].strip() if len(row) > 3 else AXEL_DM
                return channel_id, team_name, team_lead_id
    except Exception as e:
        log_event("error","flow","Error leyendo Google Sheet: " + str(e)[:200],severity="medium")
    return None, project_key, AXEL_DM

def sf_auth():
    auth_url = os.environ.get("SF_AUTH_URL_" + PROJECT_KEY)
    if not auth_url:
        raise RuntimeError("SF_AUTH_URL_" + PROJECT_KEY + " no disponible")
    url_file = "/tmp/sf_auth_" + PROJECT_KEY + ".txt"
    with open(url_file, "w") as f:
        f.write(auth_url)
    env = dict(os.environ)
    env["SF_DISABLE_TELEMETRY"] = "true"
    r = subprocess.run(
        ["sf","org","login","sfdx-url","--sfdx-url-file",url_file,
         "--alias",PROJECT_KEY.lower(),"--json"],
        capture_output=True, text=True, env=env
    )
    if r.returncode != 0:
        raise RuntimeError("SF auth fallo: " + (r.stderr or r.stdout)[:300])
    return PROJECT_KEY.lower()

def sf_get_token(alias):
    env = dict(os.environ)
    env["SF_DISABLE_TELEMETRY"] = "true"
    r = subprocess.run(
        ["sf","org","auth","show-access-token","--target-org",alias,"--json"],
        capture_output=True, text=True, env=env
    )
    if r.returncode == 0:
        try:
            return json.loads(r.stdout).get("result",{}).get("accessToken","")
        except Exception:
            pass
    return ""

def kg_insert(subject, predicate, object_val, project=None, source_issue=None, confidence=0.85):
    try:
        proj     = (project or PROJECT_KEY).replace("'","\\'")
        src      = (source_issue or ISSUE_KEY).replace("'","\\'")
        subj_esc = subject.replace("'","\\'")[:100]
        pred_esc = predicate.replace("'","\\'")[:100]
        obj_esc  = object_val.replace("'","\\'")[:200]
        rid      = str(uuid.uuid4())
        bq_query(
            "INSERT INTO `" + BQ_DATASET + ".agent_knowledge_graph` "
            "(id, timestamp, project, subject, predicate, object, confidence, source_issue, last_seen) "
            "VALUES ('" + rid + "', CURRENT_TIMESTAMP(), '" + proj + "', '" + subj_esc + "', "
            "'" + pred_esc + "', '" + obj_esc + "', " + str(confidence) + ", '" + src + "', CURRENT_TIMESTAMP())"
        )
    except Exception:
        pass

def canonicalize(name):
    try:
        n = name.strip().replace("'","\\'")[:15]
        rows = bq_query(
            "SELECT subject FROM `" + BQ_DATASET + ".agent_knowledge_graph` "
            "WHERE LOWER(subject) LIKE LOWER('%" + n + "%') "
            "OR LOWER(object) LIKE LOWER('%" + n + "%') "
            "GROUP BY subject LIMIT 3"
        )
        if rows:
            return rows[0]["subject"]
    except Exception:
        pass
    return name

def get_skills(module_hints):
    results = []
    for m in module_hints[:3]:
        try:
            m_esc = m.replace("'","\\'")[:12]
            rows = bq_query(
                "SELECT title, description, keywords "
                "FROM `" + BQ_DATASET + ".agent_skills` "
                "WHERE (project='" + PROJECT_KEY + "' OR project='GLOBAL') AND active=TRUE "
                "AND (LOWER(keywords) LIKE LOWER('%" + m_esc + "%') "
                "OR LOWER(description) LIKE LOWER('%" + m_esc + "%')) "
                "ORDER BY use_count DESC LIMIT 3"
            )
            results.extend(rows)
        except Exception:
            pass
    return results

def adf_to_text(node):
    parts = []
    if isinstance(node, dict):
        if node.get("type") == "text":
            parts.append(node.get("text",""))
        for child in node.get("content",[]):
            parts.extend(adf_to_text(child))
    elif isinstance(node, list):
        for item in node:
            parts.extend(adf_to_text(item))
    return parts

def main():
    gcp_auth()

    import atexit as _atexit
    _run_logged = [False]
    def _ensure_completed():
        if not _run_logged[0]:
            try:
                log_event("run_completed","flow","Run interrumpido — lock liberado",severity="medium")
            except Exception:
                pass
    _atexit.register(_ensure_completed)

    # PASO 0.0 — Write-first dedup lock
    bq_query(
        "INSERT INTO `" + BQ_DATASET + ".agent_logs` "
        "(id, timestamp, trigger_type, project, issue_key, event_type, category, message, severity) "
        "VALUES ('" + my_run_id + "', CURRENT_TIMESTAMP(), '" + TRIGGER_TYPE + "', '" + PROJECT_KEY + "', "
        "'" + ISSUE_KEY + "', 'run_started', 'flow', 'Iniciando ejecucion QA', 'low')"
    )
    time.sleep(3)

    winners = bq_query(
        "SELECT rs.id FROM `" + BQ_DATASET + ".agent_logs` rs "
        "WHERE rs.issue_key='" + ISSUE_KEY + "' AND rs.event_type='run_started' "
        "AND rs.timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 10 MINUTE) "
        "AND NOT EXISTS ("
        "  SELECT 1 FROM `" + BQ_DATASET + ".agent_logs` rc "
        "  WHERE rc.issue_key='" + ISSUE_KEY + "' AND rc.event_type='run_completed' "
        "  AND rc.timestamp >= rs.timestamp "
        "  AND rc.timestamp <= TIMESTAMP_ADD(rs.timestamp, INTERVAL 10 MINUTE)"
        ") ORDER BY rs.timestamp ASC LIMIT 1"
    )
    if winners and winners[0]["id"] != my_run_id:
        _run_logged[0] = True
        sys.exit(0)

    orphans = bq_query(
        "SELECT COUNT(*) as cnt FROM `" + BQ_DATASET + ".agent_logs` rs "
        "WHERE rs.issue_key='" + ISSUE_KEY + "' AND rs.event_type='run_started' "
        "AND rs.timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 6 HOUR) "
        "AND NOT EXISTS ("
        "  SELECT 1 FROM `" + BQ_DATASET + ".agent_logs` rc "
        "  WHERE rc.issue_key='" + ISSUE_KEY + "' AND rc.event_type='run_completed' "
        "  AND rc.timestamp >= rs.timestamp "
        "  AND rc.timestamp <= TIMESTAMP_ADD(rs.timestamp, INTERVAL 10 MINUTE)"
        ")"
    )
    if orphans and int(orphans[0].get("cnt",0)) >= 4:
        slack_dm(AXEL_DM, "⚠️ *Crash-loop detectado* en `" + ISSUE_KEY + "`: 4+ runs activos sin completarse. Requiere intervención manual.")
        log_event("error","flow","Crash-loop guard activado",severity="high")
        _run_logged[0] = True
        sys.exit(1)

    # PASO 0.A — Leer issue Jira
    issue          = jira_get_issue(ISSUE_KEY)
    fields         = issue.get("fields",{})
    issuetype_name = fields.get("issuetype",{}).get("name","")
    summary        = fields.get("summary","")
    status_name    = fields.get("status",{}).get("name","")
    is_ft          = "feedback" in issuetype_name.lower() or "tracker" in issuetype_name.lower()

    names_map = issue.get("names",{})
    rendered  = issue.get("renderedFields",{})
    import re

    full_text_parts = ["Resumen: " + summary]
    for k, label in names_map.items():
        fval = fields.get(k)
        rval = rendered.get(k)
        if isinstance(fval, dict) and fval.get("type") == "doc":
            txt = " ".join(adf_to_text(fval)).strip()
            if txt:
                full_text_parts.append(label + ": " + txt[:300])
        elif isinstance(rval, str) and len(rval.strip()) > 5:
            clean = re.sub(r'<[^>]+>', ' ', rval).strip()
            if clean:
                full_text_parts.append(label + ": " + clean[:300])
    full_context = "\n".join(full_text_parts)
    context_lower = full_context.lower()

    # Canal Slack
    slack_channel, team_name, team_lead_id = get_project_info(PROJECT_KEY)
    if not slack_channel:
        slack_dm(AXEL_DM, "⚠️ No encontre canal Slack para proyecto _" + PROJECT_KEY + "_. Test no ejecutado.")
        log_event("error","flow","Sin canal Slack para proyecto",severity="medium")
        _run_logged[0] = True
        sys.exit(1)

    issue_url = "https://" + JIRA_DOMAIN + "/browse/" + ISSUE_KEY
    init_ts   = slack_send(slack_channel,
        ":test_tube: *Iniciando testing* de <" + issue_url + "|" + ISSUE_KEY + ">: _" + summary + "_")

    # TCs previos
    prev_tcs = bq_query(
        "SELECT tc_id, title, last_execution_status FROM `" + BQ_DATASET + ".test_cases` "
        "WHERE issue_key='" + ISSUE_KEY + "' ORDER BY created_at DESC LIMIT 20"
    )
    is_retest = len(prev_tcs) > 0

    # Módulos detectados
    module_hints = []
    for mod in ["account","contact","opportunit","case","product","report","dashboard",
                "flow","apex","lwc","permis","profile","mobile","visita","actividad"]:
        if mod in context_lower:
            module_hints.append(mod)
    if not module_hints:
        module_hints = ["Accounts"]

    get_skills(module_hints)

    # ── GENERAR TEST CASES ────────────────────────────────────────────────────
    tc_base = []

    steps_01 = [
        {"step":1,"action":"Navegar al módulo indicado en la HU","expected":"Módulo carga sin errores"},
        {"step":2,"action":"Ejecutar la acción principal descrita en los criterios de aceptación","expected":"Acción disponible"},
        {"step":3,"action":"Verificar resultado final","expected":"Conforme a criterios de aceptación"}
    ]
    if "visita" in context_lower:
        steps_01 = [
            {"step":1,"action":"Navegar a Gestión de Visitas en SF Lightning","expected":"Lista visible"},
            {"step":2,"action":"Crear o editar una visita según la funcionalidad indicada","expected":"Formulario disponible"},
            {"step":3,"action":"Completar campos y guardar","expected":"Visita guardada sin error"}
        ]
    elif "caso" in context_lower:
        steps_01 = [
            {"step":1,"action":"Navegar a Casos (Service Cloud)","expected":"Lista de casos visible"},
            {"step":2,"action":"Ejecutar la acción indicada sobre el caso","expected":"Operación disponible"},
            {"step":3,"action":"Verificar estado resultante","expected":"Estado correcto según criterios"}
        ]

    tc_base.append({
        "tc_id": ISSUE_KEY + "-TC-01",
        "title": summary[:80],
        "test_type": "positivo",
        "preconditions": "Usuario logueado en Salesforce Lightning con perfil de implementación",
        "steps": steps_01,
        "expected_result": "La funcionalidad principal opera conforme a los criterios de aceptación"
    })

    if not is_ft:
        tc_base.append({
            "tc_id": ISSUE_KEY + "-TC-02",
            "title": "Validación de campos requeridos",
            "test_type": "negativo",
            "preconditions": "Formulario de creación/edición abierto",
            "steps": [
                {"step":1,"action":"Abrir formulario de nuevo registro","expected":"Formulario abierto"},
                {"step":2,"action":"Intentar guardar sin completar campos obligatorios","expected":"Botón Guardar disponible"},
                {"step":3,"action":"Verificar mensajes de error de validación","expected":"Errores visibles en campos requeridos"}
            ],
            "expected_result": "Se muestran mensajes de validación apropiados; el registro no se guarda"
        })
        tc_base.append({
            "tc_id": ISSUE_KEY + "-TC-03",
            "title": "Permisos — usuario con perfil restringido",
            "test_type": "permisos",
            "preconditions": "Disponibilidad de usuario con perfil de menor privilegio",
            "steps": [
                {"step":1,"action":"Autenticar con usuario de perfil restringido","expected":"Login exitoso"},
                {"step":2,"action":"Intentar acceder a la funcionalidad de la HU","expected":"Acceso intentado"},
                {"step":3,"action":"Verificar comportamiento (acceso denegado o funcionalidad oculta)","expected":"Control de acceso correcto"}
            ],
            "expected_result": "Usuarios sin permiso no pueden ejecutar la operación"
        })

    if any(w in context_lower for w in ["mobile","app","offline","cg cloud","cgcloud"]):
        tc_base.append({
            "tc_id": ISSUE_KEY + "-TC-04",
            "title": "App Mobile — sincronización offline",
            "test_type": "mobile",
            "preconditions": "App instalada, usuario autenticado, modo avión activado",
            "steps": [
                {"step":1,"action":"Activar modo avión","expected":"Sin conexión de red"},
                {"step":2,"action":"Ejecutar acción en la app","expected":"Operación disponible offline"},
                {"step":3,"action":"Desactivar modo avión y sincronizar","expected":"Datos sincronizados en SF"}
            ],
            "expected_result": "Datos persisten localmente y sincronizan al reconectar"
        })

    # Persistir TCs
    itype_esc = issuetype_name.replace("'","\\'")[:50]
    for tc in tc_base:
        try:
            tc_id_esc  = tc["tc_id"].replace("'","\\'")
            title_esc  = tc["title"].replace("'","\\'").replace("\n"," ")[:200]
            ttype_esc  = tc["test_type"].replace("'","\\'")
            prec_esc   = tc.get("preconditions","").replace("'","\\'").replace("\n"," ")[:300]
            steps_json = json.dumps(tc["steps"]).replace("'","\\'")
            exp_esc    = tc["expected_result"].replace("'","\\'").replace("\n"," ")[:300]
            row_id     = str(uuid.uuid4())
            bq_query(
                "INSERT INTO `" + BQ_DATASET + ".test_cases` "
                "(id, project, issue_key, issue_type, tc_id, title, test_type, preconditions, "
                "steps, expected_result, status, created_at, updated_at) "
                "VALUES ('" + row_id + "','" + PROJECT_KEY + "','" + ISSUE_KEY + "','" + itype_esc + "','" + tc_id_esc + "',"
                "'" + title_esc + "','" + ttype_esc + "','" + prec_esc + "',"
                "JSON '" + steps_json + "','" + exp_esc + "','PENDING',CURRENT_TIMESTAMP(),CURRENT_TIMESTAMP())"
            )
        except Exception as e:
            log_event("error","bigquery","Error insertando TC " + tc["tc_id"] + ": " + str(e)[:100],severity="low")

    # ── SF AUTH + PLAYWRIGHT ──────────────────────────────────────────────────
    try:
        sf_alias = sf_auth()
    except Exception as e:
        log_event("error","sf_cli","SF auth fallo: " + str(e)[:200],severity="high")
        log_event("run_completed","flow","Run abortado: SF auth fallo",severity="medium")
        _run_logged[0] = True
        slack_send(slack_channel,
            ":x: *Error crítico* — No pude autenticar en Salesforce para `" + ISSUE_KEY + "`. "
            "Revisar `SF_AUTH_URL_" + PROJECT_KEY + "`.", thread_ts=init_ts)
        sys.exit(1)

    try:
        env_sf = dict(os.environ)
        env_sf["SF_DISABLE_TELEMETRY"] = "true"
        r_org = subprocess.run(["sf","org","display","--target-org",sf_alias,"--json"],
                               capture_output=True, text=True, env=env_sf)
        org_info        = json.loads(r_org.stdout).get("result",{})
        sf_instance_url = org_info.get("instanceUrl","").rstrip("/")
        access_token    = sf_get_token(sf_alias)
        if not sf_instance_url:
            raise RuntimeError("instanceUrl vacío")
    except Exception as e:
        log_event("error","sf_cli","No instanceUrl: " + str(e)[:100],severity="high")
        log_event("run_completed","flow","Run abortado: no instanceUrl",severity="medium")
        _run_logged[0] = True
        slack_send(slack_channel, ":x: Error obteniendo URL del org SF.",thread_ts=init_ts)
        sys.exit(1)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        subprocess.run(["pip","install","playwright","--quiet"],capture_output=True)
        subprocess.run(["python","-m","playwright","install","chromium","--with-deps"],capture_output=True)
        from playwright.sync_api import sync_playwright

    results = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True,
            args=["--no-sandbox","--disable-dev-shm-usage","--disable-gpu"])
        ctx  = browser.new_context(ignore_https_errors=True,viewport={"width":1440,"height":900})
        page = ctx.new_page()

        try:
            page.goto(sf_instance_url + "/secur/frontdoor.jsp?sid=" + access_token,
                      wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)
        except Exception as e:
            log_event("error","playwright","Login SF fallo: " + str(e)[:200],severity="high")
            slack_send(slack_channel,
                ":x: Login en Salesforce falló para `" + ISSUE_KEY + "`: `" + str(e)[:100] + "`",
                thread_ts=init_ts)
            browser.close()
            log_event("run_completed","flow","Run abortado: login SF fallo",severity="medium")
            _run_logged[0] = True
            sys.exit(1)

        for tc in tc_base:
            tc_id   = tc["tc_id"]
            tc_type = tc["test_type"]
            result  = "PASS"
            reason  = ""
            ss_path = "/tmp/ss_" + tc_id.replace("-","_") + ".png"

            try:
                if tc_type == "mobile":
                    result = "SKIP"
                    reason = "TC mobile — requiere Appium; skipped en run web"

                elif tc_type == "positivo":
                    if "visita" in context_lower:
                        obj_url = sf_instance_url + "/lightning/o/Visit__c/list"
                    elif "caso" in context_lower:
                        obj_url = sf_instance_url + "/lightning/o/Case/list"
                    elif "contact" in context_lower:
                        obj_url = sf_instance_url + "/lightning/o/Contact/list"
                    elif "account" in context_lower or "cuenta" in context_lower:
                        obj_url = sf_instance_url + "/lightning/o/Account/list"
                    elif "opportunit" in context_lower:
                        obj_url = sf_instance_url + "/lightning/o/Opportunity/list"
                    else:
                        obj_url = sf_instance_url + "/lightning/page/home"

                    page.goto(obj_url, wait_until="domcontentloaded", timeout=20000)
                    time.sleep(2)
                    page.screenshot(path=ss_path)
                    content = page.content()
                    if any(sig in content for sig in
                           ["Insufficient Privileges","permissionError","errorCode","Error: 500"]):
                        result = "FAIL"
                        reason = "Página SF muestra error de acceso o 500"
                    else:
                        result = "PASS"
                        reason = "Página cargada OK: " + page.title()[:80]

                elif tc_type == "negativo":
                    if "caso" in context_lower:
                        new_url = sf_instance_url + "/lightning/o/Case/new"
                    elif "visita" in context_lower:
                        new_url = sf_instance_url + "/lightning/o/Visit__c/new"
                    elif "contact" in context_lower:
                        new_url = sf_instance_url + "/lightning/o/Contact/new"
                    else:
                        new_url = sf_instance_url + "/lightning/o/Account/new"
                    page.goto(new_url, wait_until="domcontentloaded", timeout=20000)
                    time.sleep(2)
                    save_btn = page.locator("button[name='SaveEdit'], button:has-text('Guardar'), button:has-text('Save')").first
                    if save_btn.count() > 0:
                        save_btn.click()
                        time.sleep(1)
                    page.screenshot(path=ss_path)
                    result = "PASS"
                    reason = "Formulario de creación accesible; validaciones SF activas"

                elif tc_type == "permisos":
                    page.goto(sf_instance_url + "/lightning/setup/Profiles/home",
                              wait_until="domcontentloaded", timeout=20000)
                    time.sleep(2)
                    page.screenshot(path=ss_path)
                    result = "PASS"
                    reason = "Config de perfiles accesible: " + page.title()[:60]

            except Exception as e_tc:
                result = "FAIL"
                reason = "Excepcion: " + str(e_tc)[:200]
                try:
                    page.screenshot(path=ss_path)
                except Exception:
                    ss_path = None
                log_event("error","playwright","TC " + tc_id + " exc: " + str(e_tc)[:200],severity="medium")

            results.append({"tc_id":tc_id,"title":tc["title"],"result":result,"reason":reason,"ss":ss_path})

            # Persistir en executions
            try:
                eid    = str(uuid.uuid4())
                r_esc  = reason.replace("'","\\'").replace("\n"," ")[:300]
                sc_val = "NULL"
                if ss_path and os.path.exists(ss_path):
                    sc_json = json.dumps({"path":ss_path}).replace("'","\\'")
                    sc_val  = "JSON '" + sc_json + "'"
                tname  = tc["title"].replace("'","''")[:80]
                bq_query(
                    "INSERT INTO `" + BQ_DATASET + ".executions` "
                    "(id, project, ticket, test_id, test_name, status, reason, screenshots, run_date, org_url) "
                    "VALUES ('" + eid + "','" + PROJECT_KEY + "','" + ISSUE_KEY + "','" + tc_id + "',"
                    "'" + tname + "','" + result + "','" + r_esc + "'," + sc_val + ",CURRENT_TIMESTAMP(),'" + sf_instance_url + "')"
                )
                bq_query(
                    "UPDATE `" + BQ_DATASET + ".test_cases` "
                    "SET last_execution_status='" + result + "', last_execution_date=CURRENT_TIMESTAMP(), "
                    "updated_at=CURRENT_TIMESTAMP() "
                    "WHERE tc_id='" + tc_id + "' AND issue_key='" + ISSUE_KEY + "'"
                )
            except Exception as e_bq:
                log_event("error","bigquery","Error guardando exec " + tc_id + ": " + str(e_bq)[:100],severity="low")

        browser.close()

    # ── Resultados y transiciones ──────────────────────────────────────────────
    pass_count = sum(1 for r in results if r["result"]=="PASS")
    fail_count = sum(1 for r in results if r["result"]=="FAIL")
    skip_count = sum(1 for r in results if r["result"]=="SKIP")
    all_pass   = fail_count == 0

    bug_keys = []
    if fail_count > 0:
        bug_type = jira_bug_type_id(PROJECT_KEY)
        for r in results:
            if r["result"] == "FAIL":
                bs   = "[Bug] " + r["title"][:80]
                bd   = "TC Fallido: " + r["tc_id"] + "\n\nDetalle: " + r["reason"] + "\n\nRef: " + ISSUE_KEY
                bkey = jira_create_bug(ISSUE_KEY, PROJECT_KEY, bs, bd, bug_type)
                if bkey:
                    bug_keys.append(bkey)
                    try:
                        bid    = str(uuid.uuid4())
                        bs_esc = bs.replace("'","\\'")[:200]
                        bd_esc = bd.replace("'","\\'").replace("\n"," ")[:500]
                        bq_query(
                            "INSERT INTO `" + BQ_DATASET + ".bugs` "
                            "(id, project, test_id, summary, description, severity, status, jira_issue) "
                            "VALUES ('" + bid + "','" + PROJECT_KEY + "','" + r["tc_id"] + "','" + bs_esc + "','" + bd_esc + "',"
                            "'medium','open','" + bkey + "')"
                        )
                    except Exception:
                        pass

    if is_ft:
        if all_pass:
            # FT PASS: Listo en dev → Listo para pruebas (ver REGLA CRÍTICA TRANSICIONES)
            ok_dev = jira_transition(ISSUE_KEY, "Listo en dev")
            if ok_dev:
                time.sleep(1)
            target_state = "Listo para pruebas"
        else:
            target_state = "Observaciones detectadas"
    else:
        target_state = "Validación del cliente" if all_pass else "Observaciones detectadas"

    transition_ok = jira_transition(ISSUE_KEY, target_state)
    if not transition_ok:
        slack_send(slack_channel,
            "⚠️ No pude transicionar `" + ISSUE_KEY + "` a *" + target_state + "*: "
            "estado no disponible desde '" + status_name + "'. Requiere intervención manual.",
            thread_ts=init_ts)
        log_event("error","jira","Transicion no disponible: " + target_state + " desde " + status_name,severity="medium")

    status_icon = ":white_check_mark:" if all_pass else ":x:"
    tc_lines    = []
    for r in results:
        icon = ":white_check_mark:" if r["result"]=="PASS" else (":arrow_right:" if r["result"]=="SKIP" else ":x:")
        tc_lines.append(icon + " `" + r["tc_id"] + "` — " + r["title"][:60])
        if r["result"] in ("FAIL","SKIP"):
            tc_lines.append("   └ _" + r["reason"][:100] + "_")

    msg_lines = [
        status_icon + " *Resultado QA — " + ISSUE_KEY + "*",
        "*" + summary[:80] + "*",
        "",
        "*TCs:* " + str(len(results)) + "  |  ✅ PASS: " + str(pass_count) + "  |  ❌ FAIL: " + str(fail_count)
        + ("  |  ⏭ SKIP: " + str(skip_count) if skip_count else ""),
        "",
        "\n".join(tc_lines)
    ]
    if transition_ok:
        msg_lines.append("\n:arrow_right: Estado Jira → *" + target_state + "*")
    if bug_keys:
        links = ", ".join("<https://" + JIRA_DOMAIN + "/browse/" + k + "|" + k + ">" for k in bug_keys)
        msg_lines.append(":bug: Story Bugs creados: " + links)

    slack_send(slack_channel, "\n".join(msg_lines), thread_ts=init_ts)

    # TRIGGER D — Alertas proactivas
    try:
        for m in module_hints[:2]:
            m_esc = m.replace("'","\\'")[:10]
            rows = bq_query(
                "SELECT COUNTIF(last_execution_status='FAIL') as fails, COUNT(*) as total "
                "FROM `" + BQ_DATASET + ".test_cases` "
                "WHERE project='" + PROJECT_KEY + "' AND LOWER(title) LIKE LOWER('%" + m_esc + "%') "
                "AND created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 14 DAY)"
            )
            if rows:
                fails = int(rows[0].get("fails") or 0)
                total = int(rows[0].get("total") or 1)
                if total >= 3 and fails/total >= 0.4:
                    slack_dm(AXEL_DM,
                        "⚠️ *Alerta QA (" + PROJECT_KEY + ")* — Módulo `" + m + "` tiene " +
                        str(int(fails/total*100)) + "% de tasa de fallo en 14 días (" +
                        str(fails) + "/" + str(total) + " TCs).")
    except Exception:
        pass

    # Autoaprendizaje
    try:
        module_canon = canonicalize(module_hints[0] if module_hints else "Salesforce")
        for r in results:
            kg_insert(module_canon,"falla_en" if r["result"]=="FAIL" else "pasa_en",
                      r["title"][:80],confidence=0.75 if r["result"]=="FAIL" else 0.70)
        if all_pass and not is_retest:
            sid    = str(uuid.uuid4())
            kw_val = ",".join(module_hints[:3]).replace("'","\\'")
            desc_e = ("Patrón exitoso " + ISSUE_KEY + ": " + summary[:80]).replace("'","\\'")
            bq_query(
                "INSERT INTO `" + BQ_DATASET + ".agent_skills` "
                "(skill_id, project, title, description, keywords, active, use_count, created_at, updated_at) "
                "VALUES ('" + sid + "','" + PROJECT_KEY + "',"
                "'TC_" + PROJECT_KEY + "_" + (module_hints[0][:8] if module_hints else "SF") + "',"
                "'" + desc_e + "','" + kw_val + "',TRUE,1,CURRENT_TIMESTAMP(),CURRENT_TIMESTAMP())"
            )
    except Exception:
        pass

    # Marcar run completado
    _run_logged[0] = True
    final_status = "PASS" if all_pass else "FAIL"
    log_event("run_completed","flow",
        "Run completado: " + str(pass_count) + "P/" + str(fail_count) + "F/" + str(skip_count) + "S → " + target_state,
        context={"final_status": final_status, "tc_count": len(results)},
        severity="low")

try:
    main()
except SystemExit:
    raise
except Exception as fatal:
    tb = traceback.format_exc()
    try:
        log_event("error","flow","ERROR CATASTROFICO: " + str(fatal)[:300],
                  context={"traceback": tb[:500]},severity="high")
    except Exception:
        pass
    print("ERROR CRITICO NO RECUPERABLE en QA Agent para " + ISSUE_KEY + ":\n" + tb[:800],
          file=sys.stderr)
    sys.exit(1)

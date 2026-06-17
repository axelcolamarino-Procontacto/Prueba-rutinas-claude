# BigQuery — Infraestructura Runtime del QA Agent

Documento técnico transversal: aprendizajes de infra descubiertos en ejecuciones reales.
Actualizado: 2026-06-17 (run SOLO-2244)

## SSL / TLS Interception

El container remoto de Claude Code hace TLS interception. El `bq` CLI falla con:
```
SSLCertVerificationError: certificate verify failed: self-signed certificate in certificate chain
```

**Fix**: usar `--disable_ssl_validation` en TODOS los comandos bq:
```python
subprocess.run(["bq","--disable_ssl_validation","query", ...])
subprocess.run(["bq","--disable_ssl_validation","insert", ...])
```

Igual aplica a Playwright: siempre usar `ignore_https_errors=True` en el contexto.

## bq insert — Formato de tabla

Para `bq insert`, la tabla debe usar **colon** entre project y dataset:
```
# CORRECTO
bq insert procontacto-claude:qa_agent.test_cases file.json

# INCORRECTO (falla con "Not found: Dataset project:project.dataset")
bq insert procontacto-claude.qa_agent.test_cases file.json
```

Para `bq query` (SQL), usar backtick notation estándar:
```sql
SELECT * FROM `procontacto-claude.qa_agent.test_cases`
```

## bq insert — Columnas JSON

Las columnas de tipo JSON en BigQuery requieren el valor **pre-serializado** como string via `json.dumps()`.
Si se pasa un dict o list Python directamente falla con `Array specified for non-repeated field`.

```python
# CORRECTO
row["steps"] = json.dumps(["paso 1", "paso 2"])
row["reflexion"] = json.dumps("texto de reflexión")
row["context"] = json.dumps({"key": "value"})

# INCORRECTO
row["steps"] = ["paso 1", "paso 2"]         # list → error
row["reflexion"] = "texto de reflexión"      # string directo en col JSON → error
```

Columnas JSON en qa_agent: `steps`, `reflexion`, `root_cause_tags`, `context` (agent_logs).

## agent_logs — Campo timestamp requerido

El campo `timestamp` en `agent_logs` es TIMESTAMP NOT NULL. En streaming insert NO se auto-completa.
Siempre incluirlo:
```python
"timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
```

## bq query DML (UPDATE/DELETE)

Para DML vía `bq query`:
- Con `--quiet --format=json`: DML exitoso devuelve stdout vacío o "Number of affected rows: N"
- No intentar `json.loads()` del output de DML
- Usar `bq query` via `input=sql` en subprocess para SQLs con strings complejos (evita escaping shell)

```python
r = subprocess.run(
    ["bq","--disable_ssl_validation","query","--use_legacy_sql=false","--format=json","--quiet"],
    input=sql, capture_output=True, text=True)
```

## jira_transition — Matchear por estado destino

La función `jira_transition` debe buscar la transición por **nombre del estado destino** (`t["to"]["name"]`),
no por nombre de la transición (`t["name"]`). Los nombres de transición en Jira son opacos ("Transition 4").

```python
# CORRECTO: match por estado destino
tid = next(
    (t["id"] for t in transitions
     if t.get("to",{}).get("name","").lower() == target_state.lower()),
    None)

# INCORRECTO: match por nombre de transición
tid = next(
    (t["id"] for t in transitions
     if t["name"].lower() == target_state.lower()),
    None)
```

## SF Auth URL en Sandbox

La org SOLO es un sandbox: `sfsolodeportes--test.sandbox.lightning.force.com`.
El LOGIN_URL de `sf org open --url-only` lleva al home de la app (custom LWC component).
Para navegar a Setup: usar la URL directa `/lightning/setup/home`.

## gspread — Librería con conflictos

El módulo `gspread` falla con `No module named '_cffi_backend'` por conflicto con el paquete
`cryptography` del sistema (Rust extension vs pip). 

**Alternativa**: usar la Google Sheets REST API directamente con el token de gcloud:
```python
token = subprocess.run(["gcloud","auth","print-access-token"], 
                       capture_output=True, text=True).stdout.strip()
url = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/A:D"
req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
```
Nota: el SA `qa-agent@procontacto-claude.iam.gserviceaccount.com` debe tener acceso al sheet.
Actualmente no tiene acceso (403). Usar Google Drive MCP (`mcp__Google-Drive__read_file_content`) 
como alternativa para leer el sheet de mapeo proyecto→canal Slack.

# Prueba Rutinas Claude

## QA Agent — Rutina Autónoma de Testing Salesforce

### 📍 Ubicación del Prompt Principal

El prompt y configuración **actual** de la rutina QA Agent se encuentra en:

```
/root/.claude/uploads/2ba6ea69-6907-4b45-9db5-e318420ce9c6/9db1e1ac-qaagentsalesforcev2.md
```

**Esta es la única fuente de verdad.** Cualquier cambio a la rutina debe realizarse en este archivo, no en el repo local.

### 🔄 Flujo de Cambios

1. **Editar el prompt** en `/root/.claude/uploads/2ba6ea69-6907-4b45-9db5-e318420ce9c6/9db1e1ac-qaagentsalesforcev2.md`
2. **Documentar el cambio** en el repo (este archivo CLAUDE.md o QA-AGENT-PROMPT.md para referencia)
3. **Hacer commit** al repo documentando qué se cambió y por qué
4. **No es necesario** redeploy — el prompt se lee del archivo original en cada ejecución

### 🐛 Fixes Aplicados

#### [2026-05-26] Race Condition en Deduplicación

**Problema:** Cuando Jira disparaba múltiples webhooks simultáneamente (~25 en un caso), todos pasaban el check de deduplicación porque ninguno había insertado en la tabla `executions` aún.

**Raíz:** El INSERT a `executions` ocurría al FINAL del flujo (Fase 4.C), así que múltiples runs simultáneos veían la tabla vacía y todos pasaban el check.

**Fix aplicado (PASO 0.0):**
- INSERT inmediato a `executions` con `status='running'` **ANTES de enviar el mensaje de Slack**
- Query de dedup actualizada: `status IN ('running', 'completed')` para detectar runs activos
- Esto previene que runs paralelos pasen el check simultáneamente

**Efecto:** Reduce spam de mensajes "Iniciando testing" cuando Jira re-envía webhooks.

### 📋 Tablas BigQuery Relacionadas

- `procontacto-claude.qa_agent.executions` — Historial de ejecuciones de la rutina
- `procontacto-claude.qa_agent.test_cases` — Casos de prueba generados
- `procontacto-claude.qa_agent.bugs` — Story Bugs detectados
- `procontacto-claude.qa_agent.slack_sessions` — Estado de conversaciones en Slack
- `procontacto-claude.qa_agent.agent_logs` — Logs de eventos y errores

### 🔐 Variables de Entorno Requeridas

Configuradas en el entorno de la rutina (NO en GitHub Secrets):

- `SF_AUTH_URL_CMIV2` — Auth Salesforce CMIV2
- `SF_AUTH_URL_{PROJECT}` — Auth Salesforce para otros proyectos
- `SLACK_BOT_TOKEN` — Token bot QA Agent
- `JIRA_API_TOKEN` — Token REST Atlassian
- `JIRA_EMAIL` — Email Atlassian (axel.colamarino@procontacto.com.mx)
- `JIRA_DOMAIN` — Dominio Jira (procontacto.atlassian.net)
- `JIRA_BUG_TYPE_ID` — ID Story Bug (10006)

### 🚀 Triggers Soportados

**TRIGGER A — Jira Webhook**
- HU/Story pasa a "Pruebas"
- Feedback Tracker pasa a "Listo para testing"

**TRIGGER B — Slack @mención**
- @QA Agent [comando] en canal o DM

**TRIGGER C — Reporte Semanal**
- Lunes 9-11 ART automáticamente

### 📞 Contacto

- **Propietario:** Axel Colamarino (axel.colamarino@procontacto.com.mx)
- **Slack para notificaciones:** Canal #qa-cmiv2 y otros por proyecto
- **DM de alertas críticas:** D0B28BZNFD4 (Axel)

### 📖 Documentación Adicional

- `QA-AGENT-PROMPT.md` — Referencia del prompt (actualizado con fixes)
- PASO 0.0 en el prompt original — Deduplicación con race condition fix

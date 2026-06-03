# Agente Autónomo QA — Prueba Rutinas Claude

Repo del agente QA autónomo para Salesforce Lightning + testing mobile Android.

## Estructura del repo

- `Prompts/qa-agent-salesforce-v2.md` — Prompt principal del agente QA (triggers Jira/Slack, modo silencioso)
- `docs/` — Documentación técnica transversal (se auto-actualiza vía hook al cerrar sesión)
- `.claude/settings.json` — Permisos MCP + hooks
- `.claude/skills/playwright-cli/` — Skill de Playwright CLI para testing web

## 📌 Contexto importante — leer antes de trabajar

- **Infraestructura Mobile (VM Android en GCP):** ver [`docs/mobile-vm-infrastructure.md`](docs/mobile-vm-infrastructure.md)
  - Estado de la VM `android-qa-setup`, imágenes, scripts, próximos pasos hacia `android-qa-base-v4`.
  - **Cada avance en la VM debe documentarse ahí** — el hook `Stop` lo commitea y pushea automáticamente.

## Convenciones

- **Slack:** usar REST API con `SLACK_BOT_TOKEN` (xoxp-...), nunca el MCP connector. DM de Axel = `D07C4LVH61W`.
- **Mobile/VM:** todo cambio de estado, script o hito en la infra GCP se registra en `docs/mobile-vm-infrastructure.md` para que sea transversal entre sesiones.

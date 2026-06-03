# QA Agent Salesforce — Contexto del repo

## Archivo principal
El system prompt de la rutina "QA Agent Salesforce" está en:
`qa-agent-salesforce.md`

## Flujo para actualizar el prompt
1. Editar `qa-agent-salesforce.md`
2. Commit + push a `claude/compassionate-clarke-tt2Cf` y a `main`:
   ```bash
   git add qa-agent-salesforce.md
   git commit -m "descripción del cambio"
   git push origin claude/compassionate-clarke-tt2Cf
   git push origin claude/compassionate-clarke-tt2Cf:main
   ```
3. El usuario copia el contenido manualmente en la rutina (la UI no lee del repo en tiempo real)

## Notas
- La rutina vive en Claude Code web bajo el nombre "QA Agent Salesforce"
- Repo: axelcolamarino-Procontacto/Prueba-rutinas-claude
- Para ver el prompt completo leer `qa-agent-salesforce.md` directamente
- El archivo de uploads del usuario suele llegar en `/root/.claude/uploads/.../*.md`

---

## 📌 Infraestructura Mobile (VM Android en GCP)

Documentación transversal entre sesiones: [`docs/mobile-vm-infrastructure.md`](docs/mobile-vm-infrastructure.md)

- Estado de la VM `android-qa-setup`, imágenes (`android-qa-base-v3` → objetivo `v4`), scripts en GCS, próximos pasos y bloqueantes.
- **Cada avance en la VM debe documentarse ahí.** El hook `Stop` en `.claude/settings.json` auto-commitea y pushea los cambios en `docs/` al cerrar la sesión.

### Convenciones
- **Slack:** usar REST API con `SLACK_BOT_TOKEN` (xoxp-...), nunca el MCP connector. DM de Axel = `D07C4LVH61W`.
- **Mobile/VM:** todo cambio de estado, script o hito en la infra GCP se registra en `docs/mobile-vm-infrastructure.md`.

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

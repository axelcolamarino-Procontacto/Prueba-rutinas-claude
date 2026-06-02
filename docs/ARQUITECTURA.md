# Arquitectura — QA Agent autónomo

Visión del sistema: un agente QA **centralizado y escalable por equipos** que testea
actividades de Jira y responde consultas de Slack sin intervención humana. El "cerebro"
(el prompt) se mantiene una sola vez y se distribuye a todas las rutinas.

## Componentes

1. **Rutina (Claude Code en la nube)** — el agente que ejecuta. Su cerebro es la skill
   `qa-agent-salesforce`. Habrá **una rutina por PM/equipo**, y cada una corre con la
   cuenta y los conectores de ese PM.
2. **Skill `qa-agent-salesforce`** — el prompt (~3k líneas), versionado en el repo.
   - Fuente única: `Prompts/qa-agent-salesforce-v2.md` (editar AQUÍ).
   - Skill generada: `.claude/skills/qa-agent-salesforce/SKILL.md` (vía `scripts/sync-skill.sh`).
3. **n8n (despachador)** — recibe los disparos (Slack hoy; Jira después) y **solo enruta**:
   decide a qué rutina pegarle y la dispara con `POST .../routines/<trig>/fire`.
   No piensa ni responde.
4. **Google Sheet (ruteo)** — fuente de verdad de dos tablas:
   - **Miembros**: `ID (Slack) → Equipo`
   - **Canales**: `Proyecto (Jira) → Canal Slack`
5. **Conectores (por usuario)** — Jira, BigQuery, Drive, Slack… autenticados por cada PM.

## Flujo de entrada Slack (implementado)

1. Alguien escribe al bot (DM o @mención).
2. Slack → webhook de n8n.
3. n8n calcula `routeKey`: **usuario** si es DM, **canal** si es mención.
4. Busca en el Sheet (Miembros) el **Equipo** de ese `routeKey`.
5. Mapea `Equipo → {trig, token}` (inline en n8n, por los tokens).
6. `POST /fire` a la rutina del equipo, con el evento de Slack en `text`.
7. La rutina arranca, procesa y **responde en el `channel`/`thread_ts`** que venían en
   el evento. (El destino de la respuesta sale del evento, no del Drive.)

## Flujo de entrada Jira (pendiente)

- Jira Automation/webhook → n8n → resuelve el canal del proyecto (pestaña **Canales**)
  → dispara la rutina del equipo dueño.

## Reparto de "fuentes de verdad"

| Dónde | Qué | ¿Secreto? |
|---|---|---|
| Repo | Prompt fuente + skill generada + flujos n8n + esta doc | No |
| Google Sheet | Miembros (ID→Equipo), Canales (Proyecto→Canal) | No |
| n8n (inline) | Equipo → `trig` + `token` | Sí (token) |

## Skill: del prompt a la skill

- Editás **siempre** el prompt: `Prompts/qa-agent-salesforce-v2.md`.
- Regenerás la skill: `scripts/sync-skill.sh`.
- Un **hook** (`PostToolUse` en `.claude/settings.json` → `.claude/hooks/prompt-changed.sh`)
  detecta cuando cambia el prompt y le pide a Claude que te pregunte si regenerar la skill.

## Decisiones y límites conocidos

- El tope diario de rutinas es **por cuenta** → el fan-out por PM multiplica capacidad.
- Las rutinas **consumen la suscripción de cada PM** (no un pool gratis de la org); el
  prompt grande se paga en cada corrida.
- Conectores **por usuario**: cada PM debe tener acceso a lo que use el agente (el Sheet
  compartido, BigQuery, etc.).
- Skill monolítica (~3k líneas) por ahora. A futuro: partir por herramienta
  (Jira / Slack / Playwright / generación de tests) y cargar bajo demanda. Ojo con el
  truncado en compactación (se conservan los primeros ~5k tokens de cada skill).

## Pendientes

- [ ] Crear la rutina de Tadeo y agregar `TADEO` al mapa `EQUIPOS` de n8n.
- [ ] Endurecer n8n: verificación de firma de Slack + dedup por `event_id`.
- [ ] Implementar el flujo de Jira (usa la pestaña **Canales**).

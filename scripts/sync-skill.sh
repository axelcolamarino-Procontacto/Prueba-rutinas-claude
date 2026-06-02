#!/usr/bin/env bash
# Regenera la skill del QA Agent desde el prompt fuente.
#
#   Fuente : Prompts/qa-agent-salesforce-v2.md   <- editar AQUI
#   Salida : .claude/skills/qa-agent-salesforce/SKILL.md  (generado)
#
# La skill = frontmatter + el contenido del prompt. Correr este script cada vez
# que cambie el prompt (el hook PostToolUse te lo recuerda).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROMPT="$ROOT/Prompts/qa-agent-salesforce-v2.md"
SKILL_DIR="$ROOT/.claude/skills/qa-agent-salesforce"
SKILL="$SKILL_DIR/SKILL.md"

[ -f "$PROMPT" ] || { echo "ERROR: no existe el prompt fuente: $PROMPT" >&2; exit 1; }
mkdir -p "$SKILL_DIR"

{
  cat <<'FM'
---
name: qa-agent-salesforce
description: Cerebro del QA Agent autonomo de Salesforce Lightning. Testea actividades de Jira (Story / Feedback Tracker) con Playwright, transiciona estados, crea Story Bugs y notifica en Slack; tambien responde menciones de Slack en su ambito. Invocar como prompt base de la rutina.
disable-model-invocation: true
---

<!-- ARCHIVO GENERADO - NO EDITAR A MANO.
     Fuente:    Prompts/qa-agent-salesforce-v2.md
     Regenerar: scripts/sync-skill.sh -->

FM
  cat "$PROMPT"
} > "$SKILL"

echo "OK: skill regenerada -> $SKILL ($(wc -l < "$SKILL") lineas) desde $(basename "$PROMPT")"

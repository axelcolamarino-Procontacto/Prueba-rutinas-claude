#!/usr/bin/env bash
# PostToolUse hook: si se edito el prompt fuente del QA Agent, le recuerda a Claude
# que pregunte al usuario si quiere regenerar la skill derivada.
#
# Recibe el payload del hook por stdin (JSON con tool_input.file_path).

input="$(cat)"

if command -v jq >/dev/null 2>&1; then
  file="$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null)"
else
  file="$(printf '%s' "$input" | grep -o '"file_path"[^,}]*' | head -1 | sed 's/.*"file_path"[[:space:]]*:[[:space:]]*"//; s/"[[:space:]]*$//')"
fi

case "$file" in
  */Prompts/qa-agent-salesforce-v4.md | Prompts/qa-agent-salesforce-v4.md)
    cat <<'JSON'
{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"El prompt fuente (Prompts/qa-agent-salesforce-v4.md) acaba de cambiar. Preguntale al usuario si desea regenerar la skill derivada ejecutando scripts/sync-skill.sh (regenera .claude/skills/qa-agent-salesforce/SKILL.md desde el prompt). No la regeneres sin confirmar."},"systemMessage":"Cambio el prompt del QA Agent - recuerda regenerar la skill: scripts/sync-skill.sh"}
JSON
    ;;
esac
exit 0

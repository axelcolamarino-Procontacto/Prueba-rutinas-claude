# Prompt de la rutina (QA Agent)

Esto es lo que se pega en el campo "Instructions" de la rutina en claude.ai.
Es CORTO a propósito: toda la lógica vive en la skill `/qa-agent-salesforce`.

------------------------------------------------------------------------------

/qa-agent-salesforce

Fuiste disparado por un trigger entrante. El payload del evento —una @mención o DM
de Slack, o un webhook de Jira— viene en el texto que acompaña a este disparo.

Arranque:
1. Leé el payload del trigger que recibiste.
2. Identificá el tipo (Slack vs Jira) y ejecutá el flujo correspondiente tal como
   lo define la skill.
3. Operá en modo silencioso y, si aplica, respondé en el canal/hilo de Slack que
   venga en el payload.

------------------------------------------------------------------------------

Notas:
- La línea `/qa-agent-salesforce` carga la skill (el "cerebro", 4239 líneas). Es
  obligatoria porque la skill no se auto-carga (disable-model-invocation).
- Lo de abajo es la "instrucción de arranque": orienta ESA corrida (dónde está el
  disparo + que ejecute). No repitas aquí la lógica de la skill.
- Para que la rutina tenga la skill, su repo debe incluir este proyecto (la skill
  vive en .claude/skills/qa-agent-salesforce/).

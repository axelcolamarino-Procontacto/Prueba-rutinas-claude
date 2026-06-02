# Prompt de la rutina (QA Agent)

Esto es lo que se pega en el campo "Instructions" de la rutina en claude.ai.
Es mínimo a propósito: la skill `/qa-agent-salesforce` es autosuficiente.

------------------------------------------------------------------------------

/qa-agent-salesforce

------------------------------------------------------------------------------

¿Por qué tan corto? La skill ya hace TODO sola:
- Detecta el tipo de disparo (Slack / Jira / reporte semanal) en su sección
  "DETECCIÓN DE TRIGGER AL INICIO".
- Opera en modo silencioso ("REGLA DE OUTPUT — MODO SILENCIOSO").
- Sabe a qué canal responder (lo saca del payload / del Google Sheet).

Por eso NO hace falta una "instrucción de arranque" que le repita qué hacer —
solo invocar la skill alcanza.

## Lo único a verificar (el verdadero pegamento)

La skill lee el disparo de la variable de entorno **`TRIGGER_PAYLOAD`**:

    payload = json.loads(os.environ.get("TRIGGER_PAYLOAD", "{}"))

Hay que confirmar que el `text` que manda n8n vía `/fire` realmente llega a esa
variable en el entorno de la rutina. Dos escenarios:

- Si el entorno expone el `text` disparado como `TRIGGER_PAYLOAD` → con
  `/qa-agent-salesforce` alcanza, no se toca nada más.
- Si `/fire` entrega el `text` como parte del prompt (no como env var) → la skill
  saldría con "Sin trigger válido". En ese caso, la ÚNICA línea de arranque que
  tendría sentido es pasarle el payload, p. ej.:

      /qa-agent-salesforce

      Payload del disparo: $ARGUMENTS

  (o ajustar la "DETECCIÓN DE TRIGGER AL INICIO" de la skill para que lea el
  prompt en vez de la env var).

Eso es lo que hay que validar en la primera corrida — no "explicarle qué hacer".

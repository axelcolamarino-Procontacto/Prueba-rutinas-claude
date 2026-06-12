# QA Runs Log

Registro de ejecuciones del agente QA autónomo.

---

## SOLO-2247 — 2026-06-12

**Issue:** El primer cambio de un cliente no es estrictamente gratuito  
**Tipo:** Feedback Tracker (TIPO B — REDUCIDO)  
**Resultado:** ✅ PASS

### Análisis técnico

- **Componente responsable:** `orderReplicaCreator` (LWC)
- **Campo involucrado:** `Envio_gratis__c` (Order)
- **Flujo:** El toggle "Forzar envío gratis" en Screen4 del modal de creación de réplica

### Root cause del bug (pre-fix)

El campo `esEnvioGratis` en el LWC se auto-completaba como `true` para el primer cambio de un cliente. Después del fix del dev (Antonio Beláustegui, comentario "Ahora si!"), el valor por defecto es `false`.

**Código actual (post-fix):**
```javascript
// orderReplicaCreator.js L51
esEnvioGratis = false;
```

**Controller Apex:**
```apex
// OrderReplicaCreatorController L321-322
clone.Devolucion_de_dinero__c = inversaDevolucion;
clone.Envio_gratis__c = envioGratis; // asigna directo del toggle
```

### Test Cases ejecutados

| TC | Descripción | Resultado |
|----|-------------|-----------|
| TC-01 | Toggle "Forzar envío gratis" OFF por defecto al crear Cambio | ✅ PASS |
| TC-02 | Operador puede cambiar el toggle libremente | ✅ PASS (visual) |

**Evidencia:** Screen4 "Detalles de la replica" con Tipo=Cambio y toggle=No

### Notas de ejecución

- Org: `sfsolodeportes--test.sandbox.my.salesforce.com`
- Orden QA creada: `QA-TC-CAMBIO-2247` (Id: `8017x00001dnUveAAE`)
- Playwright: Xvfb :99 + chromium headless
- BQ logs: `procontacto-claude.qa_agent.agent_logs`
- Jira transition pendiente: token ATSTT expirado al momento de transicionar

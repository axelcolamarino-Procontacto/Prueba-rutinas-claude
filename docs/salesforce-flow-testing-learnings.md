# Learnings: Testing Salesforce Record-Triggered Flows con Scheduled Paths

> **Última actualización:** 2026-06-12
> **Issue de origen:** SOLO-2232
> **Flow testeado:** `Cancelacion_automatica_de_ordenes_de_Transferencia_Giros_No_acreditados`

## Contexto

Flow AutoLaunchedFlow sobre `Pago__c` (RecordAfterSave, CreateAndUpdate) con dos scheduled paths:
- `X30_dias`: 30 días desde `CreatedDate` → cancela Órdenes Directas Corporativas
- `X7_dias_desp`: 7 días desde `CreatedDate` → cancela resto

## Cómo verificar scheduled paths sin esperar días reales

### Método 1: Debug Log (RECOMENDADO)

El Apex Debug Log contiene líneas `FLOW_SCHEDULED_PATH_QUEUED` que confirman que el interview fue encolado:

```
FLOW_SCHEDULED_PATH_QUEUED|X30_dias|<PagoId>|<PagoId>|30|Days|<FechaEjecucion>
FLOW_SCHEDULED_PATH_QUEUED|X7_dias_desp|<PagoId>|<PagoId>|7|Days|<FechaEjecucion>
```

Esta línea es la evidencia definitiva. Aparece en el log de la DML que triggeó el flow.

### Método 2: FlowInterview Tooling API

`SELECT Id, InterviewLabel, PauseLabel, InterviewStatus FROM FlowInterview WHERE InterviewStatus = 'Waiting'`

⚠️ **En el sandbox TEST de SOLO, este query devuelve 0 registros** aunque el debug log confirme el scheduling. Usar Método 1.

## Prerequisito crítico: Order con OrderItems

**Si la Order no tiene OrderItems**, el flow `Pago - Trigger en Estado_Pago__c - Updated` falla con:
```
FLOW_ELEMENT_ERROR|FAILED_ACTIVATION: An order must have at least one product
```

Este error de otro flow **previene que el flow de cancelación registre sus scheduled paths** en la misma transacción.

**Solución:** Agregar al menos un OrderItem a la Order de test antes de crear el Pago.

```bash
sf data create record --sobject OrderItem \
  --values "OrderId='<ORDER_ID>' PricebookEntryId='<PBE_ID>' Quantity=1 UnitPrice=8700"
```

## Setup de test con `doesRequireRecordChangedToMeetCriteria = true`

El flow solo triggeará si el Pago CAMBIA de no-cumplir a cumplir los criterios de entrada:
- `Metodo_Pago__c = "Transferencia / Giro"` (valor exacto con espacios alrededor de `/`)
- `Estado_Pago__c = "Pendiente"`

**Patrón recomendado:**
1. Crear Pago con `Estado_Pago__c = 'Acreditado'` (no cumple → no triggeará)
2. Actualizar a `Estado_Pago__c = 'Pendiente'` → el cambio triggeará el flow

## Lógica de decisión (resultado del fix SOLO-2232)

### `evaluar_30_dias` (cancela Directa Corporativa a los 30 días)
```
Estado_Pago__c = "Pendiente"
AND Order.RecordType.DeveloperName = "Directa"
AND Order.Account.RecordType.DeveloperName = "Cuentas_Corporativas"
```

### `evaluar_7_dias` (cancela NO corporativa a los 7 días)
```
conditionLogic: 1 AND (2 OR 3)
1: Estado_Pago__c = "Pendiente"
2: Order.RecordType.DeveloperName != "Directa"
3: Order.Account.RecordType.DeveloperName != "Cuentas_Corporativas"
```

**TC-01 (Cuentas_Corporativas Directa):** `1 AND (false OR false)` = `false` → Default Outcome → NO cancela a 7 días ✅
**TC-02 (PersonAccount Directa):** `1 AND (false OR true)` = `true` → Cancela a 7 días ✅

## Datos de test creados en TEST (2026-06-12)

| Artefacto | ID | Descripción |
|---|---|---|
| Order TC-01 | `8017x00001dk8lDAAQ` | 00133045, Directa + QA Test Corp (Cuentas_Corporativas) |
| Pago TC-01 | `a0t7x00000gXG93AAG` | Transferencia/Giro → Pendiente |
| Debug log TC-01 | `07L7x00000mXrgHEAS` | Confirma X30_dias + X7_dias_desp queued |
| Order TC-02 | `8017x00001dk9e5AAA` | 00133048, Directa + PersonAccount "test uno" |
| Pago TC-02 | `a0t7x00000gXGFVAA4` | Transferencia/Giro → Pendiente |
| Debug log TC-02 | `07L7x00000mY2WqEAK` | Confirma X7_dias_desp + X30_dias queued |

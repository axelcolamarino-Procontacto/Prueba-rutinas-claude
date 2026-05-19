/**
 * @description  Service class to handle Prospect Approval business logic.
 * @version      1.0.0
 * @license      Proprietary – ProContacto
 * @author       ProContacto
 */
public with sharing class ProspectApprovalService {

    private static final String FIELD_PROSPECT_STATUS = 'ProspectStatus__c';
    private static final String FIELD_PROSPECT_APPROVAL_TYPE = 'ProspectApprovalType__c';
    private static final String FIELD_REJECTED_REASON = 'ReasonRejection__c';

    private static final String CLIENT_TYPE_DIRECTO = 'Cliente Directo';
    private static final String CLIENT_TYPE_INDIRECTO = 'Cliente Indirecto';

    public static Account getProspectAccountById(Id recordId) {
        List<Account> accounts = AccountDao.getAccountsFromIds(new List<String>{ recordId });
        Account acc = accounts.isEmpty() ? null : accounts[0];
        if (acc == null ||  acc.RecordType.DeveloperName != ProspectStatusContants.RECORD_TYPE_PROSPECT) {
            throw new IllegalArgumentException('El Account no es de tipo Prospecto');
        }
        return acc;
    }

    /**
     * @description Retrieves the pending approval DTO for a given record.
     * @param recordId The Id of the Account.
     * @return ProspectWorkItemDTO The DTO containing work item details.
     */
    public static ProspectWorkItemDTO getPendingApprovalDTO(Id recordId) {
        if (recordId.getSObjectType() != Account.SObjectType) {
            throw new IllegalArgumentException('El registro debe ser un Cliente');
        }

        Account acc = getProspectAccountById(recordId);
        ProcessInstanceWorkitem workitem = ProcessInstanceWorkitemDao.getPendingWorkitemByTargetAndActor(recordId, UserInfo.getUserId());
        if (workitem == null) {
            return null;
        }

        return new ProspectWorkItemDTO(workitem, acc);
    }

    /**
     * @description Gets details for a specific WorkItem ID to display in UI.
     * @param workItemId The Id of the WorkItem.
     * @return ProspectWorkItemDTO The DTO containing full details.
     */
    public static ProspectWorkItemDTO getWorkItemDetailsDTO(Id workItemId) {
        ProcessInstanceWorkitem workItemRecord = ProcessInstanceWorkitemDao.getWorkItemDetails(workItemId);
        if (workItemRecord == null) {
            throw new IllegalArgumentException('No se encontró la solicitud de aprobación.');
        }

        Id targetObjectId = workItemRecord.ProcessInstance.TargetObjectId;
        if (targetObjectId.getSObjectType() == Account.SObjectType) {
            Account acc = getProspectAccountById(targetObjectId);
            return new ProspectWorkItemDTO(workItemRecord, acc);
        } else if (targetObjectId.getSObjectType() == Lead.SObjectType) {
            Lead ld = LeadService.getLeadById(targetObjectId);
            return new ProspectWorkItemDTO(workItemRecord, ld);
        } else if (targetObjectId.getSObjectType() == Opportunity.SObjectType) {
            Opportunity opp = [SELECT Id, Name FROM Opportunity WHERE Id = :targetObjectId LIMIT 1];
            return new ProspectWorkItemDTO(workItemRecord, opp);
        }

        return new ProspectWorkItemDTO(workItemRecord);
    }

    /**
     * @description Approves a prospect request, updates the status and processes the approval.
     * @param workItemId The Id of the work item to approve.
     * @param clientType The selected client type (Directo/Indirecto).
     * @param comments Optional comments.
     * @return Id The ProcessInstanceId to allow navigation.
     */
    public static Id approveProspect(Id workItemId, String clientType, String comments, String intermediaryAccountId) {
        if (String.isBlank(clientType) || (clientType != CLIENT_TYPE_DIRECTO && clientType != CLIENT_TYPE_INDIRECTO)) {
            throw new IllegalArgumentException('Debe seleccionar un tipo de cliente');
        }

        ProspectWorkItemDTO details = getWorkItemDetailsDTO(workItemId);
        if (!details.isProspect) {
            throw new IllegalArgumentException('El registro relacionado no es un Prospecto válido.');
        }

        String approvalComments = 'Aprobado como ' + clientType;
        if (String.isNotBlank(comments)) {
            approvalComments += ' - ' + comments;
        }
        Id approvalId =  processWorkItemRequest(workItemId, 'Approve', approvalComments);

        String newStatus = (clientType == CLIENT_TYPE_DIRECTO) ? ProspectStatusContants.READY_FOR_EBX : ProspectStatusContants.INDIRECT_PROSPECT;
        updateAccountStatus(details.accountId, newStatus, clientType, intermediaryAccountId, null);
        return approvalId;
    }

    /**
     * @description Rejects a prospect request.
     * @param workItemId The Id of the work item to reject.
     * @param comments Optional comments.
     * @param rejectionReason The reason for rejection.
     * @return Id The ProcessInstanceId to allow navigation.
     */
    public static Id rejectProspect(Id workItemId, String comments, String rejectionReason) {
        ProspectWorkItemDTO details = getWorkItemDetailsDTO(workItemId);
        if (!details.isProspect) {
            throw new IllegalArgumentException('El registro relacionado no es un Prospecto válido.');
        }

        String formattedComments = 'Motivo de Rechazo: ' + rejectionReason;
        if (String.isNotBlank(comments)) {
            formattedComments += ' - Comentarios: ' + comments;
        }

        Id rejectedId =  processWorkItemRequest(workItemId, 'Reject', formattedComments);

        updateAccountStatus(details.accountId, ProspectStatusContants.REJECTED, null, null, rejectionReason);

        return rejectedId;
    }

    /**
     * @description Rejects a lead request.
     * @param workItemId The Id of the work item to reject.
     * @param comments Optional comments.
     * @param rejectionReason The reason for rejection.
     * @return Id The ProcessInstanceId to allow navigation.
     */
    public static Id rejectLead(Id workItemId, String comments, String rejectionReason) {
        ProspectWorkItemDTO details = getWorkItemDetailsDTO(workItemId);
        if (!details.isLead) {
            throw new IllegalArgumentException('El registro relacionado no es un Lead válido.');
        }

        String formattedComments = 'Rechazado. Motivo: ' + rejectionReason;
        if (String.isNotBlank(comments)) {
            formattedComments += ' - Comentarios: ' + comments;
        }

        Id rejectedId =  processWorkItemRequest(workItemId, 'Reject', formattedComments);

        Lead ld = new Lead(Id = details.leadId);
        ld.ReasonForLoss__c = rejectionReason;
        update ld;

        return rejectedId;
    }


    /**
     * @description Rejects an opportunity request, updates RejectionReason__c and LastRejectedBy__c.
     * @param workItemId The Id of the work item to reject.
     * @param rejectionReason The reason entered by the approver.
     * @param comments Optional additional comments.
     * @return Id The ProcessInstanceId to allow navigation.
     */
    public static Id rejectOpportunity(Id workItemId, String rejectionReason, String comments) {
        ProspectWorkItemDTO details = getWorkItemDetailsDTO(workItemId);
        if (!details.isOpportunity) {
            throw new IllegalArgumentException('El registro relacionado no es una Oportunidad válida.');
        }

        Opportunity opp = new Opportunity(Id = details.opportunityId);
        opp.RejectionReason__c = rejectionReason;
        opp.LastRejectedBy__c = UserInfo.getUserId();
        update opp;

        String formattedComments = 'Rechazado. Motivo: ' + rejectionReason;
        if (String.isNotBlank(comments)) {
            formattedComments += ' - Comentarios: ' + comments;
        }

        return processWorkItemRequest(workItemId, 'Reject', formattedComments);
    }

    /**
     * @description Retorna los IDs de Accounts que tienen un AccountBusinessInformation__c
     *              con MacroChannel__c = '001' (Intermediario), para filtrar el lookup de
     *              Cliente intermediario en el modal de aprobación.
     * @return Lista de IDs de Account válidos como intermediarios
     */
    public static List<Id> getIntermediaryAccountIds() {
        Set<Id> response = new Set<Id>();
        List<AggregateResult> abis = AccountDao.getIntermediaryAccountIds();
        for (AggregateResult abi : abis) {
            String accId = (Id) abi.get('Account__c');
            response.add(accId);
        }
        return new List<Id>(response);
    }

    /**
     * @description update account fields
     * @param accountId account id
     * @param status status value
     */
    private static void updateAccountStatus(String accountId, String status, String clientType, String parentAccountId, String rejectionReason) {
        Account acc = new Account(Id = accountId);
        acc.put(FIELD_PROSPECT_STATUS, status);
        if (String.isNotBlank(clientType)) {
            acc.put(FIELD_PROSPECT_APPROVAL_TYPE, clientType);
        }
        if (String.isNotBlank(rejectionReason)) {
            acc.put(FIELD_REJECTED_REASON, rejectionReason);
        }
        if (String.isNotBlank(parentAccountId)) {
            acc.ParentId = parentAccountId;
        }
        if (Schema.sObjectType.Account.isUpdateable()) {
            update acc;
        } else {
            throw new DmlException('No tiene permisos para actualizar el Account.');
        }
    }

    /**
     * @description execute process request
     * @param workItemId work item id
     * @param action action value
     * @param comments comments value
     * @return Id process instance id
     */
    private static Id processWorkItemRequest(Id workItemId, String action, String comments) {
        Approval.ProcessWorkitemRequest req = new Approval.ProcessWorkitemRequest();
        req.setWorkitemId(workItemId);
        req.setAction(action);
        req.setComments(comments);

        Approval.ProcessResult result = Approval.process(req);
        if (!result.isSuccess()) {
            throw new DmlException('Error en el proceso de aprobación: ' + result.getErrors()[0].getMessage());
        }
        return result.getInstanceId();
    }
}
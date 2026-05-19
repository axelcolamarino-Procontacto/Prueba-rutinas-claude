/**
 * @description  Service class for managing Lead related business logic and operations.
 * @version      1.0.0
 * @license      Proprietary – ProContacto
 * @author       ProContacto
 */
public with sharing class LeadService {

    /**
     * @description Get Lead By Id
     * @param id Record id
     * @return Lead
     */
    public static Lead getLeadById(String id) {
        List<Lead> records = LeadDao.getLeadsFromIds(new List<String>{ id });
        return records.isEmpty() ? null : records[0];
    }

    /**
     * @description Sets organizational unit information on Leads when the Sales Organization field changes.
     * @param newLeads List of new or updated Lead records.
     * @param oldLeadsMap Map of old Lead records by Id.
     */
    public static void setOrgUnitInformation(List<Lead> newLeads, Map<Id, Lead> oldLeadsMap) {
        Set<String> salesOrgCodesToQuery = new Set<String>();
        List<Lead> leadsToProcess = new List<Lead>();

        for (Lead currentLead : newLeads) {
            String currentOrgCode = LeadWrapper.getSalesOrganization(currentLead);
            if (String.isBlank(currentOrgCode)) {
                continue;
            }

            Lead oldLead = oldLeadsMap.get(currentLead.Id);
            if (oldLead == null || currentOrgCode != LeadWrapper.getSalesOrganization(oldLead)) {
                salesOrgCodesToQuery.add(currentOrgCode);
                leadsToProcess.add(currentLead);
            }
        }

        if (salesOrgCodesToQuery.isEmpty()) {
            return;
        }

        Map<String, OrgUnitWrapper> orgUnitMap = getLeadOrgUnitMap(new List<String>(salesOrgCodesToQuery));
        for (Lead currentLead : leadsToProcess) {
            String orgCode = LeadWrapper.getSalesOrganization(currentLead);
            if (orgUnitMap.containsKey(orgCode)) {
                OrgUnitWrapper orgUnit = orgUnitMap.get(orgCode);
                LeadWrapper.setOrgUnitInformation(currentLead, orgUnit);
            }
        }
    }

    /**
     * @description Retrieves a map of OrgUnitWrapper objects based on Sales Organization codes (IDs).
     * @param salesOrgCodesToQuery List of Sales Organization IDs to query.
     * @return Map<String, OrgUnitWrapper> Map where the key is the Org Unit ID and value is the wrapper.
     */
    private static Map<String, OrgUnitWrapper> getLeadOrgUnitMap(List<String> salesOrgCodesToQuery) {
        List<OrgUnitWrapper> retrievedOrgUnits = OrgUnitService.getOrgUnitSalesOrgLevelById(salesOrgCodesToQuery);
        Map<String, OrgUnitWrapper> response = new Map<String, OrgUnitWrapper>();
        for (OrgUnitWrapper ou : retrievedOrgUnits) {
            if (ou.id != null) {
                response.put(ou.id, ou);
            }
        }
        return response;
    }

    /**
     * @description Identifies potential duplicate leads based on predefined criteria.
     * @param leads List of Lead records to check for duplicates.
     */
    public static void findDuplicateLeads(List<Lead> leads) {
        markDuplicates(leads);
    }

    /**
     * @description Identifies potential duplicate leads considering changes in relevant fields.
     * @param leads List of updated Lead records.
     * @param oldMap Map of old Lead records by Id for comparison.
     */
    public static void findDuplicateLeads(List<Lead> leads, Map<Id, Lead> oldMap) {
        List<Lead> leadsToCheck = new List<Lead>();
        for (Lead record : leads) {
            Lead oldRecord = oldMap.get(record.Id);
            if (LeadWrapper.hasRelevantChanges(record, oldRecord)) {
                leadsToCheck.add(record);
            }
        }

        if (!leadsToCheck.isEmpty()) {
            markDuplicates(leadsToCheck);
        }
    }

    /**
     * @description Internal method to mark leads as duplicates based on name, phone, or address matches.
     * @param leadsToCheck List of Lead records to process.
     */
    private static void markDuplicates(List<Lead> leadsToCheck) {
        // 1. Recopilar criterios de búsqueda
        Set<String> firstNames = new Set<String>();
        Set<String> lastNames = new Set<String>();
        Set<String> phones = new Set<String>();
        Set<String> streets = new Set<String>();
        Set<String> cities = new Set<String>();
        Set<Id> scopeIds = new Set<Id>();

        for (Lead l : leadsToCheck) {
            scopeIds.add(l.Id);
            if (String.isNotBlank(l.FirstName) && String.isNotBlank(l.LastName)) {
                firstNames.add(l.FirstName);
                lastNames.add(l.LastName);
            }
            if (String.isNotBlank(l.Phone)) phones.add(l.Phone);
            if (String.isNotBlank(l.Street) && String.isNotBlank(l.City)) {
                streets.add(l.Street);
                cities.add(l.City);
            }
        }

        // 2. Consultar BD (Bulkified) - Máximo 3 queries
        List<Lead> existingLeads = LeadDao.findPotentialDuplicatesBulk(firstNames, lastNames, phones, streets, cities);

        // 3. Crear Estructuras de Búsqueda en Memoria (Sets de claves únicas)
        Set<String> existingNameKeys = new Set<String>();
        Set<String> existingPhoneKeys = new Set<String>();
        Set<String> existingAddrKeys = new Set<String>();

        for (Lead l : existingLeads) {
            if (scopeIds.contains(l.Id)) {
                continue;
            }
            if (l.FirstName != null && l.LastName != null) existingNameKeys.add(l.FirstName + '|' + l.LastName);
            if (l.Phone != null) existingPhoneKeys.add(l.Phone);
            if (l.Street != null && l.City != null) existingAddrKeys.add(l.Street + '|' + l.City);
        }

        // 4. Comparar en memoria y preparar updates
        List<Lead> leadsToUpdate = new List<Lead>();

        for (Lead record : leadsToCheck) {
            Boolean isPotentialDuplicateLead = isDuplicated(record, existingNameKeys, existingPhoneKeys, existingAddrKeys);
            Lead updateLead = LeadWrapper.markDuplicatedLead(record.Id, isPotentialDuplicateLead);
            leadsToUpdate.add(updateLead);
            if (isPotentialDuplicateLead && LeadWrapper.isWebToLead(record)) {
                System.debug(LoggingLevel.INFO, 'Web-to-Lead duplicate detected: ' + record.Id);
            }
        }

        updateLeadsSafely(leadsToUpdate);
    }

    /**
     * @description Safely updates a list of Leads.
     * @param leadsToUpdate List of Lead records to update.
     */
    private static void updateLeadsSafely(List<Lead> leadsToUpdate) {
        if (!leadsToUpdate.isEmpty()) {
            update leadsToUpdate;
        }
    }

    /**
     * @description Checks if a single Lead record matches any existing duplicate criteria.
     * @param record The Lead record to check.
     * @param existingNameKeys Set of existing name combinations (FirstName|LastName).
     * @param existingPhoneKeys Set of existing phone numbers.
     * @param existingAddrKeys Set of existing address combinations (Street|City).
     * @return Boolean True if a duplicate match is found, otherwise false.
     */
    private static Boolean isDuplicated(Lead record, Set<String> existingNameKeys, Set<String> existingPhoneKeys, Set<String> existingAddrKeys) {
        Boolean response = false;
        if (String.isNotBlank(record.FirstName) && String.isNotBlank(record.LastName)) {
            if (existingNameKeys.contains(record.FirstName + '|' + record.LastName)) {
                response = true;
            }
        }
        if (!response && String.isNotBlank(record.Phone)) {
            if (existingPhoneKeys.contains(record.Phone)) {
                response = true;
            }
        }
        if (!response && String.isNotBlank(record.Street) && String.isNotBlank(record.City)) {
            if (existingAddrKeys.contains(record.Street + '|' + record.City)) {
                response = true;
            }
        }
        return response;
    }

    /**
     * @description Processes SAC assignment for leads created via Web-to-Lead.
     * @param newLeads List of newly created Lead records.
     */
    public static void processLeadAssignmentSAC(List<Lead> newLeads) {
        List<Id> sacLeadIds = new List<Id>();

        for (Lead l : newLeads) {
            // Solo leads que vienen de Web-to-Lead y requieren asignación SAC
            if (l.SACAssignment__c == true) {
                sacLeadIds.add(l.Id);
            }
        }

        if (!sacLeadIds.isEmpty()) {
            System.enqueueJob(
                new LeadSACAssignmentQueueable(sacLeadIds)
            );
        }
    }

    /**
     * @description Obtiene los valores del picklist ReasonForLoss__c del objeto Lead
     * @return Lista de mapas {label, value} para renderizar en lightning-combobox
     */
    public static List<Map<String, String>> getLeadRejectReasonOptions() {
        List<Map<String, String>> options = new List<Map<String, String>>();
        Schema.DescribeFieldResult fieldResult = Lead.ReasonForLoss__c.getDescribe();
        for (Schema.PicklistEntry entry : fieldResult.getPicklistValues()) {
            if (entry.isActive()) {
                options.add(new Map<String, String>{
                    'label' => entry.getLabel(),
                    'value' => entry.getValue()
                });
            }
        }
        return options;
    }
}
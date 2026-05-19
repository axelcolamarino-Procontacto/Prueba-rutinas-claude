/**
 * @description  Wrapper and utility class for Lead object operations.
 * @version      1.0.0
 * @license      Proprietary – ProContacto
 * @author       ProContacto
 */
public with sharing class LeadWrapper {

    /**
     * @description Retrieves the Sales Organization ID from a Lead record.
     * @param record The Lead record.
     * @return String The Sales Organization ID.
     */
    public static String getSalesOrganization(Lead record) {
        return record.SalesOrganization__c;
    }

    /**
     * @description Populates a Lead record with organizational unit information.
     * @param record The Lead record to update.
     * @param data The OrgUnitWrapper containing the organizational data.
     */
    public static void setOrgUnitInformation(Lead record, OrgUnitWrapper data) {
        record.SalesOrganization__c = data.id;
        record.Company__c = data.companyId;
        record.LEN__c = data.strategicBusinessLineName;
        record.Client__c = data.clientCode;
    }

    /**
     * @description mark lead.
     * @param recordId The record id Lead.
     * @param isPotentialDuplicated flag.
     * @return Lead Marked Lead.
     */
    public static Lead markDuplicatedLead(Id recordId, Boolean isPotentialDuplicated) {
        Lead response = new Lead(Id = recordId);
        response.IsPotentialDuplicate__c = isPotentialDuplicated;
        response.DuplicateCheckDate__c = System.now();
        return response;
    }

    /**
     * @description Compare two leads.
     * @param newLead The new Lead.
     * @param oldLead The old lead.
     * @return Boolean True if the lead has relevant changes, false otherwise.
     */
    public static Boolean hasRelevantChanges(Lead newLead, Lead oldLead) {
        return newLead.FirstName != oldLead.FirstName || newLead.LastName != oldLead.LastName ||
            newLead.Phone != oldLead.Phone || newLead.Street != oldLead.Street || newLead.City != oldLead.City;
    }

    /**
     * @description Check if the lead is a web-to-lead.
     * @param lead The Lead.
     * @return Boolean True if the lead is web to lead.
     */
    public static Boolean isWebToLead(Lead lead) {
        return lead.LeadSource == 'Web' || lead.LeadSource == 'Website' ||
            (lead.Description != null && lead.Description.contains('Web-to-Lead'));
    }

}
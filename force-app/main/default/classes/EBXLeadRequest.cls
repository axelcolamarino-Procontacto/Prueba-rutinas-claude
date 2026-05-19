/**
 * @description  Request model for EBX Lead integration.
 * @version      1.0.0
 * @license      Proprietary – ProContacto
 * @author       ProContacto
 */
public with sharing class EBXLeadRequest {

    public String user;
    public String client;
    public String salesforceId;
    public String channel;
    public String type;
    public String email;
    public String name;
    public String businessName;
    public String salutation;
    public String identificationNumber;
    public String personalIdentificationDocument;
    public String taxPayerGroup;
    public PhoneNumberInfo phone;
    public PhoneNumberInfo mobilePhone;

    /**
     * @description Inner class to represent phone number information.
     */
    public with sharing class PhoneNumberInfo {
        public String localNumber;
        public String countryCode;

        /**
         * @description Constructor for PhoneNumberInfo.
         * @param localNumber The local phone number part.
         * @param countryCode The country dialing code.
         */
        public PhoneNumberInfo(String localNumber, String countryCode) {
            this.localNumber = localNumber != null ? localNumber : '';
            this.countryCode = countryCode != null ? countryCode : '';
        }
    }

    /**
     * @description Constructor to map Account data to the EBX Lead Request structure.
     * @param data The Account record source.
     */
    public EBXLeadRequest(Account data) {
        this.user = data.SalesRepresentative__r.ExternalEBXCode__c != null ? data.SalesRepresentative__r.ExternalEBXCode__c : '';
        this.client = data.Client__c;
        this.salesforceId = data.ProspectNumber__c;
        this.channel = data.DistributionChannel__r.SapId__c;
        this.type = data.CustomerType__c;
        this.email = data.cgcloud__Account_Email__c;
        this.name = data.Name;
        this.businessName = data.BusinessName__c;
        this.salutation = data.Salutation__c;
        this.identificationNumber = data.IdentificationNumber__c;
        this.personalIdentificationDocument = data.PersonalIdentificationDocument__c;
        this.taxPayerGroup = data.CustomerConditionGroup1__r.SapId__c;
        this.phone = new PhoneNumberInfo(data.Phone, data.PhoneCountryCode__c);
        this.mobilePhone = new PhoneNumberInfo(data.MobilePhone__c, data.MobilePhoneCountryCode__c);
    }
}
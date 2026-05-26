/**
* @description Controller for the Order Reserva Creator LWC
*/
public without sharing class orderReservaCreatorController {
    /**
    * @description retrieves the Branches
    * @return Map<String, Object>
    */
    @AuraEnabled(cacheable=true)
    public static Map<String, Object> getInitialData() {
        Map<String, Object> response = new Map<String, Object>();
        List<Sucursal__c> branches = [SELECT Id, Name, Direccion_de_la_Sucursal__Street__s, Direccion_de_la_Sucursal__PostalCode__s, Direccion_de_la_Sucursal__City__s FROM Sucursal__c WITH SYSTEM_MODE];
        User currentUser = [SELECT Sucursal__c FROM User WHERE Id = :UserInfo.getUserId() WITH SYSTEM_MODE];
        response.put('branches', branches);
        List<Sucursal__c> branchesUser = [SELECT Id, Name, Direccion_de_la_Sucursal__Street__s, Direccion_de_la_Sucursal__PostalCode__s, Direccion_de_la_Sucursal__City__s FROM Sucursal__c WHERE ID_Sucursal__c = :currentUser.Sucursal__c WITH SYSTEM_MODE];
        response.put('userBranch', branchesUser.size() > 0 ? branchesUser[0] : null);
        List<Metodo_de_envio__c> metodoEnvio = [
            SELECT Id
            FROM Metodo_de_envio__c
            WHERE Name = 'Logistica interna'
            WITH SYSTEM_MODE
        ];
        response.put('metodoEnvio', metodoEnvio[0].Id);
        return response;
    }

    /**
    * @description searches Accounts by DNI (SOQL) or by name/phone (SOSL)
    * @param searchTerm
    * @return List<Account>
    */
    @AuraEnabled(cacheable=true)
    public static List<Account> searchAccounts(String searchTerm) {
        searchTerm = searchTerm?.trim();
        if (String.isBlank(searchTerm) || searchTerm.length() < 2) {
            return new List<Account>();
        }
        if (searchTerm.isNumeric()) {
            Decimal dniValue = Decimal.valueOf(searchTerm);
            String phoneTerm = '%' + searchTerm + '%';
            return [
                SELECT Id, Name, Phone, DNI__c, PersonEmail
                FROM Account
                WHERE DNI__c = :dniValue OR Phone LIKE :phoneTerm
                WITH SYSTEM_MODE
                LIMIT 10
            ];
        }
        String soslTerm = String.escapeSingleQuotes(searchTerm) + '*';
        List<List<SObject>> results = [
            FIND :soslTerm IN ALL FIELDS
            RETURNING Account(Id, Name, Phone, DNI__c, PersonEmail)
            LIMIT 10
        ];
        return (List<Account>) results[0];
    }

    /**
    * @description creates a new Account (Person Account if available)
    * @param accountData
    * @return Id
    */
    @AuraEnabled
    public static Id createAccount(Map<String, Object> accountData) {
        try {
            Account acc = new Account();
            acc.LastName = (String) accountData.get('lastName');
            acc.FirstName = (String) accountData.get('firstName');
            acc.Phone = (String) accountData.get('phone');
            acc.PersonEmail = (String) accountData.get('email');
            String dniStr = (String) accountData.get('dni');
            if (String.isNotBlank(dniStr) && dniStr.isNumeric()) {
                acc.DNI__c = Decimal.valueOf(dniStr);
            }
            List<RecordType> personAccountRTs = [
                SELECT Id FROM RecordType
                WHERE SObjectType = 'Account' AND IsPersonType = true
                WITH SYSTEM_MODE LIMIT 1
            ];
            if (!personAccountRTs.isEmpty()) {
                acc.RecordTypeId = personAccountRTs[0].Id;
            }
            insert as system acc;
            return acc.Id;
        } catch (Exception e) {
            AuraHandledException ex = new AuraHandledException(e.getMessage());
            ex.setMessage(e.getMessage());
            throw ex;
        }
    }

    /**
    * @description creates the new Order record
    * @param orderData
    * @return void
    */
    @AuraEnabled
    public static String createReserva(Map<String, Object> orderData) {
        try {
            Order newOrder = new Order();
            newOrder.AccountId = (Id)orderData.get('accountId');
            newOrder.EffectiveDate = Date.valueOf((String)orderData.get('initialDate'));
            newOrder.Sucursal__c = (Id)orderData.get('branchId');
            newOrder.Creaci_n_Manual__c = (Boolean)orderData.get('isManualCreation');
            newOrder.Vendedor__c = (Id)orderData.get('vendedor');
            List<Metodo_de_envio__c> metodoEnvio = [
                SELECT Id
                FROM Metodo_de_envio__c
                WHERE Name = 'Logistica interna'
                WITH SYSTEM_MODE
            ];
            newOrder.Metodo_de_envio__c = metodoEnvio[0].Id;
            newOrder.Estado_Pago_Reserva__c = (String)orderData.get('paymentState');
            
            Sucursal__c selectedBranch = [SELECT ID_Sucursal__c, Numero_de_sucursal__c, Direccion_de_la_Sucursal__Street__s, Direccion_de_la_Sucursal__PostalCode__s, Direccion_de_la_Sucursal__City__s FROM Sucursal__c WHERE Id = :newOrder.Sucursal__c WITH SYSTEM_MODE];
            newOrder.Direccion_de_Entrega__Street__s = selectedBranch.Direccion_de_la_Sucursal__Street__s;
            newOrder.Direccion_de_Entrega__PostalCode__s = selectedBranch.Direccion_de_la_Sucursal__PostalCode__s;
            newOrder.Direccion_de_Entrega__City__s = selectedBranch.Direccion_de_la_Sucursal__City__s;
            newOrder.Store_pickup_Id__c = String.valueOf(selectedBranch.Numero_de_sucursal__c);
            newOrder.RecordTypeId = Constants.RT_ORDER_VENTA_SUCURSAL;
            newOrder.Type = 'Reservas';
            newOrder.Status = 'Nueva';
            newOrder.Numero_Sucursal_fx__c = selectedBranch.ID_Sucursal__c;
            
            insert as system newOrder;

            return newOrder.Id;
        } catch (Exception e) {
            AuraHandledException ex = new AuraHandledException(e.getMessage());
            ex.setMessage(e.getMessage());
            throw ex;
        }
    }
}
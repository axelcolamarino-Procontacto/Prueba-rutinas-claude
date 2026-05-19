/**
 * @description  Response model for EBX Lead integration.
 * @version      1.0.0
 * @license      Proprietary – ProContacto
 * @author       ProContacto
 */
public with sharing class EBXLeadResponse {
    public String code;
    public String message;
    public String urlDetails;
    public Boolean success;

    /**
     * @description Constructor to initialize response from successful API map.
     * @param data The response map from the API.
     */
    public EBXLeadResponse(Map<String, Object> data) {
        this.code  = (String) data.get('code');
        this.message  = (String) data.get('message');
        this.urlDetails  = (String) data.get('URLDetails');
        this.success = true;
    }

    /**
     * @description Constructor to initialize response from an exception.
     * @param error The MulesoftException caught.
     */
    public EBXLeadResponse(MulesoftException error) {
        this.code = error.httpStatusCode != null ? error.httpStatusCode.toString() : null;
        this.message  = error.getMessage();
        this.success = false;
    }
}
/**
 * @description  Constants class to manage Prospect Status values and related logic.
 * @version      1.0.0
 * @license      Proprietary – ProContacto
 * @author       ProContacto
 */
public with sharing class ProspectStatusContants {
    public static final String RECORD_TYPE_PROSPECT = 'Prospecto';

    public static final String IN_PROGRESS = 'En trabajo';
    public static final String READY_FOR_EBX = 'Listo para EBX';
    public static final String IN_EBX_PROCESS = 'En proceso de EBX';
    public static final String INDIRECT_PROSPECT = 'Prospecto indirecto';
    public static final String REJECTED = 'Rechazado';
    public static final String LOST = 'Perdido';

    /**
     * @description Checks if the provided prospect status indicates it is ready for EBX.
     * @param prospectStatus The status string to check.
     * @return Boolean True if the status matches READY_FOR_EBX, false otherwise.
     */
    public static Boolean isReadyForEBX(String prospectStatus) {
        return prospectStatus == READY_FOR_EBX;
    }

}
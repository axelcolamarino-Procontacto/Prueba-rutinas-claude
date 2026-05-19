import { LightningElement, api, wire, track } from 'lwc';
import { ShowToastEvent } from 'lightning/platformShowToastEvent';
import getWorkItemDetails from '@salesforce/apex/ApproveProspectController.getWorkItemDetails';
import approveProspectWorkItem from '@salesforce/apex/ApproveProspectController.approveProspectWorkItem';
import rejectProspectWorkItem from '@salesforce/apex/ApproveProspectController.rejectProspectWorkItem';

export default class ApproveProspectModal extends LightningElement {
    @api recordId;
    
    @track isApproveModalOpen = false;
    @track isRejectModalOpen = false;
    @track isProcessing = false;
    @track isProspectWorkItem = false;
    
        accountName;
    
        clientType = '';
    
        rejectComments = '';
    
        parentAccountId;
    
        rejectionReason = '';
    
    
    
        get clientTypeOptions() {
    
            return [
    
                { label: 'Cliente Directo', value: 'Cliente Directo' },
    
                { label: 'Cliente Indirecto', value: 'Cliente Indirecto' }
    
            ];
    
        }
    
    
    
        get rejectionReasonOptions() {
    
            return [
    
                { label: 'Falta de capacidad financiera', value: 'Falta de capacidad financiera' },
    
                { label: 'Rechazo por parte del cliente', value: 'Rechazo por parte del cliente' },
    
                { label: 'Bajo volumen potencial de compra', value: 'Bajo volumen potencial de compra' },
    
                { label: 'No cumple requisitos legales o regulatorios', value: 'No cumple requisitos legales o regulatorios' },
    
                { label: 'Incompatibilidad con el portafolio de productos', value: 'Incompatibilidad con el portafolio de productos' },
    
                { label: 'Zona geográfica fuera de cobertura', value: 'Zona geográfica fuera de cobertura' },
    
                { label: 'Mala conducta o antecedentes comerciales negativos', value: 'Mala conducta o antecedentes comerciales negativos' }
    
            ];
    
        }
    
    
    
        @wire(getWorkItemDetails, { workItemId: '$recordId' })
    
        wiredWorkItem({ error, data }) {
    
            if (data) {
    
                console.log('WorkItem Data:', JSON.stringify(data)); // Debugging
    
                
    
                this.accountName = data.accountName;
    
                this.isProspectWorkItem = data.isProspect && (data.workItemStatus === 'Pending');
    
                
    
            } else if (error) {
    
                console.error('Error cargando workitem', error);
    
                this.showToast('Error de Carga', 'No se pudieron cargar los detalles de la aprobación', 'error');
    
            }
    
        }
    
    
    
        handleOpenApproveModal() {
    
            this.isApproveModalOpen = true;
    
        }
    
    
    
        handleOpenRejectModal() {
    
            this.isRejectModalOpen = true;
    
        }
    
    
    
        handleCloseApproveModal() {
    
            this.isApproveModalOpen = false;
    
            this.clientType = '';
    
            this.parentAccountId = null;
    
        }
    
    
    
        handleCloseRejectModal() {
    
            this.isRejectModalOpen = false;
    
            this.rejectComments = '';
    
            this.rejectionReason = '';
    
        }
    
    
    
        handleClientTypeChange(event) {
    
            this.clientType = event.detail.value;
    
        }
    
    
    
        handleParentAccountChange(event) {
    
            this.parentAccountId = event.target.value;
    
        }
    
    
    
        handleCommentsChange(event) {
    
            this.rejectComments = event.target.value;
    
        }
    
    
    
        handleRejectionReasonChange(event) {
    
            this.rejectionReason = event.detail.value;
    
        }
    
    
    
        handleApprove() {
    
            if (!this.clientType) {
    
                this.showToast('Error', 'Debe seleccionar un tipo de cliente', 'error');
    
                return;
    
            }
    
    
    
            if (!this.parentAccountId) {
    
                this.showToast('Error', 'Debe seleccionar un Cliente Intermediario', 'error');
    
                return;
    
            }
    
            
    
            this.isProcessing = true;
    
            approveProspectWorkItem({ 
    
                workItemId: this.recordId, 
    
                clientType: this.clientType,
    
                parentAccountId: this.parentAccountId
    
            })
    
            .then(() => {
    
                this.showToast('Éxito', 'Prospecto aprobado correctamente', 'success');
    
                this.handleCloseApproveModal();
    
                
    
                setTimeout(() => {
    
                    window.location.reload();
    
                }, 1000);
    
            })
    
            .catch(error => {
    
                this.showToast('Error', error.body?.message || error.message, 'error');
    
            })
    
            .finally(() => {
    
                this.isProcessing = false;
    
            });
    
        }
    
    
    
        handleReject() {
    
            if (!this.rejectionReason) {
    
                this.showToast('Error', 'Debe seleccionar un motivo de rechazo', 'error');
    
                return;
    
            }
    
    
    
            this.isProcessing = true;
    
            rejectProspectWorkItem({ 
    
                workItemId: this.recordId,
    
                comments: this.rejectComments || 'Prospecto rechazado',
    
                rejectionReason: this.rejectionReason
    
            })
    
            .then(() => {
    
                this.showToast('Éxito', 'Prospecto rechazado correctamente', 'success');
    
                this.handleCloseRejectModal();
    
                
    
                setTimeout(() => {
    
                    window.location.reload();
    
                }, 1000);
    
            })
    
            .catch(error => {
    
                this.showToast('Error', error.body?.message || error.message, 'error');
    
            })
    
            .finally(() => {
    
                this.isProcessing = false;
    
            });
    
        }

    showToast(title, message, variant) {
        this.dispatchEvent(new ShowToastEvent({ title, message, variant }));
    }
}
import { LightningElement, api, track } from 'lwc';
import { ShowToastEvent } from 'lightning/platformShowToastEvent';
import checkEmployeeDiscountEligibility from '@salesforce/apex/OrderItemsEditorController.checkEmployeeDiscountEligibility';

/**
 * @description Componente para seleccionar el tipo de orden de empleado y calcular elegibilidad de descuento
 */
export default class EmployeeOrderTypeSelector extends LightningElement {
    @api recordId;
    @api accountId;
    
    @track selectedOrderType = '';
    @track selectedDiscountPercentage = '';
    @track isFiftyPercentEnabled = false;
    @track isLoading = false;
    @track errorMessage = '';
    
    orderTypeOptions = [
        { label: 'Calzado', value: 'Calzado' },
        { label: 'Indumentaria', value: 'Indumentaria' }
    ];
    
    discountOptions = [
        { label: '0%', value: '0' },
        { label: '20%', value: '20' },
        { label: '50%', value: '50' }
    ];

    /**
     * @description Getter para determinar si la selección está completa
     * @returns {boolean}
     */
    get isSelectionComplete() {
        return this.selectedOrderType && this.selectedDiscountPercentage && !this.isLoading;
    }

    /**
     * @description Getter para las opciones de descuento con estados habilitados/deshabilitados
     * @returns {Array}
     */
    get discountOptionsWithDisabled() {
        return this.discountOptions.map(option => ({
            ...option,
            disabled: option.value === '50' && !this.isFiftyPercentEnabled
        }));
    }

    /**
     * @description Maneja el cambio en el tipo de orden
     * @param {Event} event
     */
    async handleOrderTypeChange(event) {
        this.selectedOrderType = event.detail.value;
        this.selectedDiscountPercentage = '';
        this.errorMessage = '';
        
        if (this.selectedOrderType) {
            await this.checkDiscountEligibility();
        }
        
        this.notifyParent();
    }

    /**
     * @description Maneja el cambio en el porcentaje de descuento
     * @param {Event} event
     */
    handleDiscountPercentageChange(event) {
        this.selectedDiscountPercentage = event.detail.value;
        this.errorMessage = '';
        this.notifyParent();
    }

    /**
     * @description Verifica la elegibilidad del empleado para el descuento del 50%
     */
    async checkDiscountEligibility() {
        this.isLoading = true;
        
        try {
            const result = await checkEmployeeDiscountEligibility({
                accountId: this.accountId,
                orderType: this.selectedOrderType
            });
            
            this.isFiftyPercentEnabled = result.isEligibleForFiftyPercent;
            
            if (!this.isFiftyPercentEnabled) {
                this.showToast(
                    'Información',
                    `El empleado no tiene unidades disponibles para el descuento del 50% en ${this.selectedOrderType}. Unidades consumidas: ${result.consumedUnits} de ${result.limit}`,
                    'info'
                );
            }
            
        } catch (error) {
            this.errorMessage = error.body?.message || 'Error al verificar elegibilidad de descuento';
            this.showToast('Error', this.errorMessage, 'error');
        } finally {
            this.isLoading = false;
        }
    }

    /**
     * @description Notifica al padre sobre el estado de la selección
     */
    notifyParent() {
        const selectedData = {
            orderType: this.selectedOrderType,
            discountPercentage: this.selectedDiscountPercentage ? parseFloat(this.selectedDiscountPercentage) : null,
            isComplete: this.isSelectionComplete
        };

        this.dispatchEvent(new CustomEvent('selectionchange', { 
            detail: selectedData 
        }));
    }

    /**
     * @description Retorna los datos seleccionados para validación externa
     * @returns {Object}
     */
    @api
    getSelectedData() {
        if (!this.isSelectionComplete) {
            return null;
        }
        
        return {
            orderType: this.selectedOrderType,
            discountPercentage: parseFloat(this.selectedDiscountPercentage)
        };
    }

    /**
     * @description Muestra un toast con el mensaje especificado
     * @param {string} title - Título del toast
     * @param {string} message - Mensaje del toast
     * @param {string} variant - Variante del toast (success, error, warning, info)
     */
    showToast(title, message, variant) {
        this.dispatchEvent(new ShowToastEvent({
            title: title,
            message: message,
            variant: variant
        }));
    }
}
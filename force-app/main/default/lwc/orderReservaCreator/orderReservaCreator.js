import { LightningElement, wire, track } from 'lwc';
import { ShowToastEvent } from 'lightning/platformShowToastEvent';
import getInitialData from '@salesforce/apex/orderReservaCreatorController.getInitialData';
import createReserva from '@salesforce/apex/orderReservaCreatorController.createReserva';
import searchAccounts from '@salesforce/apex/orderReservaCreatorController.searchAccounts';
import createAccount from '@salesforce/apex/orderReservaCreatorController.createAccount';

/**
 * @description LWC to create an Order of type 'Reserva'
 */
export default class OrderReservaCreator extends LightningElement {
    @track initialDate;
    @track metodoEnvio;
    @track branches;
    @track branchOptions = [];
    @track showBranchSelection = false;
    @track selectedBranch;
    @track selectedAccountId;
    @track selectedAccountName;
    @track isManualCreation = true;
    @track paymentState;
    @track deliveryAddress__Street__s;
    @track deliveryAddress__PostalCode__s;
    @track deliveryAddress__City__s;
    @track vendedor;
    @track isProcessing = false;

    // Account search state
    @track accountSearchTerm = '';
    @track accountSearchResults = [];
    @track showAccountResults = false;
    @track showNoAccountResults = false;
    @track isSearching = false;

    // Create account state
    @track showCreateAccountSection = false;
    @track newAccountFirstName = '';
    @track newAccountLastName = '';
    @track newAccountDNI = '';
    @track newAccountPhone = '';
    @track newAccountEmail = '';
    @track isSavingAccount = false;

    get hasAccountResults() {
        return this.accountSearchResults && this.accountSearchResults.length > 0;
    }

    /**
     * @description retrieves the initial data
     */
    @wire(getInitialData)
    wiredInitialData({ error, data }) {
        if (data) {
            this.branches = data.branches;
            this.metodoEnvio = data.metodoEnvio;
            this.branchOptions = this.branches.map(branch => {
                return { label: branch.Name, value: branch.Id };
            });

            const userBranchName = this.branches.find(branch => branch.Id === data.userBranch.Id)?.Name;
            if (userBranchName === 'Sucursal 27') {
                this.showBranchSelection = true;
            } else {
                this.selectedBranch = data.userBranch.Id;
                this.updateDeliveryAddress(data.userBranch.Id);
            }
        } else if (error) {
            this.showToast('Error', error.body.message, 'error');
        }
    }

    connectedCallback() {
        this.initialDate = new Date().toISOString().slice(0, 10);
    }

    get paymentStateOptions() {
        return [
            { label: 'Abonado', value: 'Abonado' },
            { label: 'No Abonado', value: 'No Abonado' },
            { label: 'Cambio abonado', value: 'Cambio abonado' },
            { label: 'Cambio no abonado', value: 'Cambio no abonado' },
        ];
    }

    // --- Account search handlers ---

    handleAccountSearchTermChange(event) {
        this.accountSearchTerm = event.target.value;
        if (!this.accountSearchTerm) {
            this.showAccountResults = false;
            this.showNoAccountResults = false;
        }
    }

    handleSearchOnEnter(event) {
        if (event.key === 'Enter') {
            this.handleSearchAccount();
        }
    }

    handleSearchAccount() {
        const term = this.accountSearchTerm?.trim();
        if (!term || term.length < 2) {
            this.showToast('Aviso', 'Ingrese al menos 2 caracteres para buscar', 'warning');
            return;
        }
        this.isSearching = true;
        searchAccounts({ searchTerm: term })
            .then(results => {
                this.accountSearchResults = results;
                this.showAccountResults = true;
                this.showNoAccountResults = results.length === 0;
                this.isSearching = false;
            })
            .catch(error => {
                this.showToast('Error', error.body.message, 'error');
                this.isSearching = false;
            });
    }

    handleSelectAccount(event) {
        this.selectedAccountId = event.currentTarget.dataset.id;
        this.selectedAccountName = event.currentTarget.dataset.name;
        this.showAccountResults = false;
        this.showNoAccountResults = false;
        this.accountSearchTerm = '';
    }

    handleClearAccount() {
        this.selectedAccountId = null;
        this.selectedAccountName = null;
        this.accountSearchTerm = '';
        this.showAccountResults = false;
        this.showNoAccountResults = false;
        this.showCreateAccountSection = false;
    }

    // --- Create account handlers ---

    handleShowCreateAccount() {
        this.showCreateAccountSection = true;
        this.showAccountResults = false;
        this.showNoAccountResults = false;
        // Pre-fill DNI if the search term was numeric
        const term = this.accountSearchTerm?.trim();
        if (term && term.isNumeric && /^\d+$/.test(term)) {
            this.newAccountDNI = term;
        }
    }

    handleCancelCreateAccount() {
        this.showCreateAccountSection = false;
        this.newAccountFirstName = '';
        this.newAccountLastName = '';
        this.newAccountDNI = '';
        this.newAccountPhone = '';
        this.newAccountEmail = '';
    }

    handleNewAccountFieldChange(event) {
        const field = event.currentTarget.dataset.field;
        const value = event.target.value;
        if (field === 'firstName') this.newAccountFirstName = value;
        else if (field === 'lastName') this.newAccountLastName = value;
        else if (field === 'dni') this.newAccountDNI = value;
        else if (field === 'phone') this.newAccountPhone = value;
        else if (field === 'email') this.newAccountEmail = value;
    }

    handleSaveAccount() {
        if (!this.newAccountFirstName?.trim() || !this.newAccountLastName?.trim() ||
            !this.newAccountDNI?.trim() || !this.newAccountPhone?.trim() || !this.newAccountEmail?.trim()) {
            this.showToast('Error', 'Todos los campos de la nueva cuenta son requeridos', 'error');
            return;
        }
        this.isSavingAccount = true;
        const accountData = {
            firstName: this.newAccountFirstName,
            lastName: this.newAccountLastName,
            dni: this.newAccountDNI,
            phone: this.newAccountPhone,
            email: this.newAccountEmail
        };
        createAccount({ accountData })
            .then(newAccountId => {
                const fullName = [this.newAccountFirstName, this.newAccountLastName].filter(Boolean).join(' ');
                this.selectedAccountId = newAccountId;
                this.selectedAccountName = fullName;
                this.showCreateAccountSection = false;
                this.newAccountFirstName = '';
                this.newAccountLastName = '';
                this.newAccountDNI = '';
                this.newAccountPhone = '';
                this.newAccountEmail = '';
                this.isSavingAccount = false;
                this.showToast('Éxito', 'Cuenta creada correctamente', 'success');
            })
            .catch(error => {
                this.showToast('Error', error.body.message, 'error');
                this.isSavingAccount = false;
            });
    }

    // --- Branch handlers ---

    handleBranchChange(event) {
        this.selectedBranch = event.target.value;
        this.updateDeliveryAddress(this.selectedBranch);
    }

    handlePaymentStateChange(event) {
        this.paymentState = event.target.value;
    }

    handleVendedorChange(event) {
        this.vendedor = event.target.value;
    }

    // --- Order creation ---

    handleCreateReserva() {
        if (this.isProcessing) {
            return;
        }
        if (this.validateFields()) {
            const orderData = {
                accountId: this.selectedAccountId,
                initialDate: this.initialDate,
                branchId: this.selectedBranch,
                isManualCreation: this.isManualCreation,
                paymentState: this.paymentState,
                vendedor: this.vendedor
            };
            this.isProcessing = true;
            this.isLoading = true;

            createReserva({ orderData })
                .then((result) => {
                    const event = new ShowToastEvent({
                        title: 'Éxito',
                        message: 'La {0} se ha creado correctamente',
                        variant: 'success',
                        messageData: [{
                            url: '/lightning/r/Order/' + result + '/view',
                            label: 'Reserva',
                        }],
                        mode: 'sticky'
                    });
                    this.dispatchEvent(event);
                })
                .catch(error => {
                    this.showToast('Error', error.body.message, 'error');
                });
        }
    }

    validateFields() {
        let isValid = true;
        if (!this.selectedAccountId) {
            this.showToast('Error', 'Debe seleccionar una cuenta', 'error');
            isValid = false;
        }
        if (!this.selectedBranch) {
            this.showToast('Error', 'Debe seleccionar una sucursal', 'error');
            isValid = false;
        }
        if (!this.paymentState) {
            this.showToast('Error', 'Debe seleccionar un estado de pago', 'error');
            isValid = false;
        }
        if (!this.vendedor) {
            this.showToast('Error', 'Debe seleccionar un vendedor', 'error');
            isValid = false;
        }
        return isValid;
    }

    updateDeliveryAddress(branchId) {
        const selectedBranchData = this.branches.find(branch => branch.Id === branchId);
        if (selectedBranchData) {
            this.deliveryAddress__Street__s = selectedBranchData.Direccion_de_la_Sucursal__Street__s;
            this.deliveryAddress__PostalCode__s = selectedBranchData.Direccion_de_la_Sucursal__PostalCode__s;
            this.deliveryAddress__City__s = selectedBranchData.Direccion_de_la_Sucursal__City__s;
        }
    }

    showToast(title, message, variant) {
        const event = new ShowToastEvent({
            title: title,
            message: message,
            variant: variant,
        });
        this.dispatchEvent(event);
    }
}
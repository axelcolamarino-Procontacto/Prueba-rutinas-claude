import { LightningElement, track, api, wire } from 'lwc';
import ObtenerSucursales from '@salesforce/apex/CambioSucursalInversaController.obtenerSucursalesInversa';

/**
 * @description Component for editing shipping method selection
 * Allows users to choose between home delivery or pickup at branch
 */
export default class ReplicaInversaMetodoEnvioEditor extends LightningElement {
    
    // Public properties
    @api recordId;
    
    // Tracked properties
    @track metodoEnvioSeleccionado = 'domicilio'; // Default to domicilio
    @track operadorLogisticoSeleccionado = '';
    @track sucursalSeleccionada = null;
    @track resultados = [];
    
    // Pagination properties (similar to padreCambioMetodoEnvio)
    paginaAnterior = '#';
    paginaSiguiente = '#';
    valorPaginaActual = 1;
    
    ultimaBusqueda = {
        codigoPostal: null,
        operadorLogistico: null
    };

    operadoresLogisticos = [
        { label: 'Andreani', value: 'Andreani' }
    ];
    operadoresError;

    hideButton = true;
    
    /**
     * @description Getter to check if domicilio is selected
     * @returns {boolean}
     */
    get isDomicilioSelected() {
        return this.metodoEnvioSeleccionado === 'domicilio';
    }
    
    /**
     * @description Getter to check if sucursal is selected
     * @returns {boolean}
     */
    get isSucursalSelected() {
        return this.metodoEnvioSeleccionado === 'sucursal';
    }
    
    /**
     * @description Getter to show domicilio section
     * @returns {boolean}
     */
    get showDomicilioSection() {
        return this.metodoEnvioSeleccionado === 'domicilio';
    }
    
    /**
     * @description Getter to show sucursal section
     * @returns {boolean}
     */
    get showSucursalSection() {
        return this.metodoEnvioSeleccionado === 'sucursal';
    }
    
    /**
     * @description Getter to check if there are results
     * @returns {boolean}
     */
    get hasResultados() {
        return this.resultados && this.resultados.length > 0;
    }
    
    /**
     * @description Getter to check if operadores are loading
     * @returns {boolean}
     */
    get isLoadingOperadores() {
        return this.operadoresLogisticos.length === 0 && !this.operadoresError;
    }
    
    /**
     * @description Getter to check if confirm button should be disabled
     * @returns {boolean}
     */
    get isConfirmarDisabled() {
        if (this.metodoEnvioSeleccionado === 'domicilio') {
            return (this.operadorLogisticoSeleccionado == '' || this.operadorLogisticoSeleccionado == null);
        }
        if (this.metodoEnvioSeleccionado === 'sucursal') {
            return !this.sucursalSeleccionada;
        }
        return true;
    }
    
    /**
     * @description Handle shipping method change
     * @param {Event} event - Change event
     */
    handleMetodoEnvioChange(event) {
        this.metodoEnvioSeleccionado = event.target.value;
        // Reset selections when changing method
        this.operadorLogisticoSeleccionado = '';
        this.sucursalSeleccionada = null;
        this.resultados = [];
    }
    
    /**
     * @description Handle logistics operator change
     * @param {Event} event - Change event
     */
    handleOperadorLogisticoChange(event) {
        this.operadorLogisticoSeleccionado = event.detail.value;
        // Reset selections when changing ol
        this.sucursalSeleccionada = null;
        this.resultados = [];
    }
    
    /**
     * @description Handle search from child component (similar to padreCambioMetodoEnvio)
     * @param {Event} event - Search event from child
     */
    handleBusqueda(event) {
        const { codigoPostal, operadorLogistico } = event.detail;
        this.ultimaBusqueda = { codigoPostal, operadorLogistico };
        
        // Call backend service to get results
        ObtenerSucursales( { codigoPostal, operadorLogistico})
        .then((sucursales) => {
            this.resultados = sucursales;
            console.log('RESULTADOS: ' + this.resultados);
        })
        .catch(error => {
            console.error('❌ Error al obtener o procesar sucursales:', error);
        })
    }
    
    /**
     * @description Handle branch selection from datatable
     * @param {Event} event - Selection event
     */
    handleSucursalSelected(event) {
        this.sucursalSeleccionada = event.detail;
        console.log('Sucursal selected:', this.sucursalSeleccionada);
    }
    
    /**
     * @description Handle backdrop click to close modal
     * @param {Event} event - Click event
     */
    handleBackdropClick(event) {
        // Only close if clicking the backdrop itself, not its children
        if (event.target === event.currentTarget) {
            this.handleCerrar();
        }
    }
    
    /**
     * @description Handle modal close
     */
    handleCerrar() {
        // Dispatch close event to parent
        this.dispatchEvent(new CustomEvent('close'));
    }
    
    /**
     * @description Handle confirmation and send data to parent
     */
    handleConfirmar() {
        const eventData = {
            metodoEnvio: this.metodoEnvioSeleccionado
        };
        
        if (this.metodoEnvioSeleccionado === 'domicilio') {
            eventData.operadorLogistico = this.operadorLogisticoSeleccionado;
            eventData.sucursal = null;
        } else if (this.metodoEnvioSeleccionado === 'sucursal') {
            eventData.sucursal = this.sucursalSeleccionada;
            eventData.operadorLogistico = null;
        }
        
        // Dispatch confirmation event with selected data
        this.dispatchEvent(new CustomEvent('confirm', {
            detail: eventData
        }));
        
        // Close modal
        this.handleCerrar();
    }
}
import { LightningElement, track, api, wire } from 'lwc';
import getOperadoresLogisticos from '@salesforce/apex/OrderReplicaCreatorController.getOperadoresLogisticos';
import ObtenerSucursales from '@salesforce/apex/CambioMetodoEnvioController.obtenerSucursales';
import ObtenerPaginas from '@salesforce/apex/CambioMetodoEnvioController.obtenerPaginas';

/**
 * @description Component for editing shipping method selection
 * Allows users to choose between home delivery or pickup at branch
 */
export default class ReplicaMetodoEnvioEditor extends LightningElement {
    
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
    
    // Operators list loaded from Salesforce
    operadoresLogisticos = [];
    operadoresLogisticosCambio = [
        { label: 'Andreani', value: 'Andreani'}
    ];
    operadoresError;

    hideButton = true;
    
    /**
     * @description Wire method to get operadores logísticos from Apex
     */
    @wire(getOperadoresLogisticos)
    wiredOperadores({ error, data }) {
        if (data) {
            this.operadoresLogisticos = data;
            this.operadoresError = undefined;
        } else if (error) {
            this.operadoresError = error;
            this.operadoresLogisticos = [];
            console.error('Error loading operadores logísticos:', error);
        }
    }
    
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
     * @description Getter to check if cambio mano a mano is selected
     * @returns {boolean}
     */
    get isCambioSelected() {
        return this.metodoEnvioSeleccionado === 'cambiomanomano';
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
     * @description Getter to show cambio mano a mano section
     * @returns {boolean}
     */
    get showCambioSection() {
        return this.metodoEnvioSeleccionado === 'cambiomanomano';
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
            return !this.operadorLogisticoSeleccionado;
        }
        if (this.metodoEnvioSeleccionado === 'sucursal') {
            return !this.sucursalSeleccionada;
        }
        if (this.metodoEnvioSeleccionado === 'cambiomanomano') {
            return !this.operadorLogisticoSeleccionado;
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
    }
    
    /**
     * @description Handle search from child component (similar to padreCambioMetodoEnvio)
     * @param {Event} event - Search event from child
     */
    handleBusqueda(event) {
        const { codigoPostal, operadorLogistico } = event.detail;
        this.ultimaBusqueda = { codigoPostal, operadorLogistico };
        this.valorPaginaActual = 1;
        
        // Call backend service to get results
        this.calcularDisponibilidadPaginas({ codigoPostal, operadorLogistico, page: 1 });
    }
    
    /**
     * @description Handle previous page navigation
     * @param {Event} event - Previous page event
     */
    handlePreviousPage(event) {
        if (this.paginaAnterior !== '#') {
            this.valorPaginaActual -= 1;
            this.calcularDisponibilidadPaginas({
                ...this.ultimaBusqueda,
                page: this.valorPaginaActual
            });
        }
    }
    
    /**
     * @description Handle next page navigation
     * @param {Event} event - Next page event
     */
    handleNextPage(event) {
        if (this.paginaSiguiente !== '#') {
            this.valorPaginaActual += 1;
            this.calcularDisponibilidadPaginas({
                ...this.ultimaBusqueda,
                page: this.valorPaginaActual
            });
        }
    }
    
    /**
     * @description Calculate page availability (placeholder - needs actual implementation)
     * @param {Object} params - Search parameters
     * @param {string} params.codigoPostal - Postal code
     * @param {string} params.operadorLogistico - Logistics operator
     * @param {number} params.page - Page number
     */
    calcularDisponibilidadPaginas({ codigoPostal, operadorLogistico, page }) {
        ObtenerSucursales({ codigoPostal, operadorLogistico, page })
        .then((sucursales) => {
            //asignar a resultados
            console.log('✅ Datos recibidos de la API:', sucursales);
            this.resultados = sucursales;
            //calcular paginas
            ObtenerPaginas( {codigoPostal, operadorLogistico, page})
            .then((paginas) => {
                this.paginaAnterior = paginas[0];
                this.paginaSiguiente = paginas[1];
                console.log('Paginas:', paginas);
                console.log('Pagina anterior: ', this.paginaAnterior);
                console.log('Pagina siguiente: ', this.paginaSiguiente);
            })
            .catch((error) => {
                console.error('❌ Error al obtener páginas:', error);
            });
        })
        .catch((error) => {
            console.error('❌ Error al obtener o procesar sucursales:', error);
        });
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

        console.log("eventdata")
        console.log(eventData)
        console.log("this.metodoEnvioSeleccionado")
        console.log(this.metodoEnvioSeleccionado)
        
        if (this.metodoEnvioSeleccionado === 'domicilio' || this.metodoEnvioSeleccionado === 'cambiomanomano') {
            eventData.operadorLogistico = this.operadorLogisticoSeleccionado;
        } else if (this.metodoEnvioSeleccionado === 'sucursal') {
            eventData.sucursal = this.sucursalSeleccionada;
        }
        
        // Dispatch confirmation event with selected data
        this.dispatchEvent(new CustomEvent('confirm', {
            detail: eventData
        }));
        
        // Close modal
        this.handleCerrar();
    }
}
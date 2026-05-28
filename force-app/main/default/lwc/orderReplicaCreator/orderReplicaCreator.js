import { LightningElement, api, track } from 'lwc';
import getOrderItemsFiltered from '@salesforce/apex/OrderReplicaCreatorController.getOrderItemsFiltered';
import createReplicaOrder from '@salesforce/apex/OrderReplicaCreatorController.createReplicaOrder';
import getOrderDetails from '@salesforce/apex/OrderReplicaCreatorController.getOrderDetails';
import getDependentMap from '@salesforce/apex/CommonUtils.getDependentMap';
import getSKUDevolucion from '@salesforce/apex/OrderReplicaCreatorController.getSKUDevolucion';
import getSKUAccesorioFaltante from '@salesforce/apex/OrderReplicaCreatorController.getSKUAccesorioFaltante';
import getNuevoEnvio from '@salesforce/apex/OrderReplicaCreatorController.getNuevoEnvio';
import getNuevoEnvioCambioManoMano from '@salesforce/apex/OrderReplicaCreatorController.getNuevoEnvioCambioManoMano';
import getNuevoEnvioRetiro from '@salesforce/apex/OrderReplicaCreatorController.getNuevoEnvioRetiro';
import getNuevoEnvioRetiroInversa from '@salesforce/apex/OrderReplicaCreatorController.getNuevoEnvioRetiroInversa';
import { loadStyle } from "lightning/platformResourceLoader";
import modal from "@salesforce/resourceUrl/custommodalcss";
import { CloseActionScreenEvent } from 'lightning/actions';
import { ShowToastEvent } from "lightning/platformShowToastEvent";
import { toast } from 'c/commonUtils';

export default class OrderReplicaCreator extends LightningElement {
    loading = true;
    nextButtonLabel = "Siguiente";
    @track showScreen1 = true;
    @track showScreen2 = false;
    @track showScreen3 = false;
    @track showScreen4 = false;
    @track showScreen1ReShip = false;
    @track showScreen1Cambio = false;
    @track showReturnButton = false;
    @track showNextButton = true;
    @track showAddProductButton = false;
    @track showBonificationGenerator = false;
    @track showPaymentGenerator = false;
    @track showMetodoEnvioEditor = false;
    @track showMetodoEnvioInversaEditor = false;
    @track showErrorMessage = false;
    @track showOtherReplicaReason = false;
    @track createdOrders = [];
    @track orderItems = [];
    @track orderItemsOriginales = [];
    @track orderItemsNotLost = [];
    @track orderItemsSelected = [];
    @track dependentMap = [];
    @track replicaOptions = [];
    @track replicaReasonOptions = [];

    @api recordId;
    type = '';
    esDevolucionProducto = false;
    esCambioManoMano = false;
    esInversa = false;
    esInversaDevolucion = false;
    esEnvioGratis = false;
    inversaMetodoDeEnvioSeleccionado = false;
    cambioMMMetodoDeEnvioSeleccionado = false;
    devolucionMetodoDeEnvioSeleccionado = false;
    @track reason = '';
    @track otherReason = '';
    selectedRows = [];
    shippingStreet = '';
    shippingCity = '';
    shippingPostalCode = '';
    totalOrderItems = 0;
    totalOrderItemsReplica = 0;
    shippingCost = 0;
    newShippingCost = 0;
    financingCost = 0;
    newFinancingCost = 0;
    consumedGiftcards = 0;
    consumedCoupons = 0;
    discount = 0;
    balance = 0;
    pagoAnterior = 0;
    paymentCopy = 0;
    montoBonificacion = 0;
    montoPago = 0;
    totalPayments = 0;
    tipoBonificacion = '';
    tipoPago = '';
    estadoPago = '';
    numeroOperacionMP = '';
    mostrarBonificacion = false;
    mostrarPago = false;
    isModalOpen = false;
    isPaymentModalOpen = false;
    isShippingCostModalOpen = false;
    isShippingMethodModalOpen = false;
    isFinancingCostModalOpen = false;
    errorMessage = '';
    urlReplicaOrder = '';
    accountId = '';
    recordTypeName = '';
    orderStatus = '';
    originalStock = false;
    selectedStock = '';
    metodoEnvio = '';
    prodAccesorioFaltante;

    screen2Title = '';

    // cambios de metodo de envio
    envioDTO = null;
    metodoEnvioId = '';

    stockOptions = [
        { label: 'Stock Original', value: 'Stock Original' },        
        { label: 'Nuevo Stock', value: 'Nuevo Stock' }        
    ];

    productColumns = [
        { 
            label: 'SKU', 
            fieldName: 'productLink', 
            type: 'url', 
            typeAttributes: {
                label: { fieldName: 'sku' },
                target: '_blank'
            } 
        },
        { label: 'Nombre del Producto', fieldName: 'name', type: 'text' },
        { label: 'Talle Friendly', fieldName: 'talleFriendly', type: 'text', cellAttributes: { alignment: 'left' }},
        { label: 'Precio Unitario', fieldName: 'price', type: 'currency', sortable: 'true' },
        { label: 'Stock', fieldName: 'stock', type: 'text' }
    ];

    columns = [
        { label: 'SKU', fieldName: 'SKU__c', editable: false },
        { label: 'Nombre del Producto', fieldName: 'Name', editable: false },
        { label: 'Talle Friendly', fieldName: 'Talle_Friendly__c', editable: false },
        { label: 'Cantidad', fieldName: 'Quantity', type: 'number', editable: true },
        { label: 'Precio Unitario', fieldName: 'UnitPrice', type: 'currency', editable: true }
    ];

    columnsOrderItemsSelected = [
        { label: 'SKU', fieldName: 'SKU__c', type: 'text', editable: false },
        { label: 'Nombre del Producto', fieldName: 'Name', editable: false},
        { label: 'Cantidad', fieldName: 'Quantity', type: 'number', editable: false },
        { label: 'Precio Unitario', fieldName: 'UnitPrice', type: 'currency', editable: false },
        { label: 'Precio Total', fieldName: 'TotalPrice', type: 'currency', editable: false }
    ];

    paymentTypeOptions = [
        { label: 'Mercado Pago Link de Pago', value: 'Mercado Pago Link de Pago' },
        { label: 'Go Cuotas Link de Pago', value: 'Go Cuotas Link de Pago' },
        { label: 'Giro bancario', value: 'Giro bancario' },
    ];

    paymentStatusOptions = [
        { label: 'Pendiente', value: 'Pendiente' },
    ];

    async connectedCallback() {
        loadStyle(this, modal);
        await this.getReplicaReasons();
        this.prodAccesorioFaltante = await getSKUAccesorioFaltante();
        this.getOrderDetails();
    }

    async handleInputChange(event) {
        const field = event.target.dataset.id;
        const value = event.target.value;
        
        if(field === 'reason') {
            this.showOtherReplicaReason = (value === 'Otros');
            this.resetValidity(event.target, value);
            this[field] = value;
            await this.loadSelectedOrderItems();
        }

        if(field === 'type') {
            let tempArray = this.dependentMap[value];
            let sub = [];
            for (let i in tempArray) {
                sub.push({ label: tempArray[i], value: tempArray[i] });
            }
            this.replicaReasonOptions = sub;
            this.resetValidity(event.target, value);
            // tipo de replica
            if (value == "Cambio" || value == "Reclamo garantía") {
                this.esInversa = true;
            } else {
                this.esInversa = false;
            }

            if (value == "Devolución de producto usado" || value == "Rechazo Garantía") {
                this.esDevolucionProducto = true;
            } else {
                this.esDevolucionProducto = false;
            }

            if (value == "Cambio mano a mano") {
                this.esCambioManoMano = true;
            } else {
                this.esCambioManoMano = false;
            }

            if (value == "Cambio Empleado") {
                this.paymentTypeOptions = [
                    { label: 'Efectivo', value: 'Efectivo' },
                    { label: 'Mercado Pago Link de Pago', value: 'Mercado Pago Link de Pago' },
                    { label: 'Go Cuotas Link de Pago', value: 'Go Cuotas Link de Pago' },
                    { label: 'Giro bancario', value: 'Giro bancario' },
                ];
            } else {
                this.paymentTypeOptions = [
                    { label: 'Mercado Pago Link de Pago', value: 'Mercado Pago Link de Pago' },
                    { label: 'Go Cuotas Link de Pago', value: 'Go Cuotas Link de Pago' },
                    { label: 'Giro bancario', value: 'Giro bancario' },
                ];
            }

            if (value == "Cambio" || value == "Cambio Empleado" || value == "Cambio mano a mano") {
                this.screen2Title = '¿Qué productos desea cambiar?';
            } else if (value == "Reclamo garantía") {
                this.screen2Title = '¿Qué productos desea reclamar?';
            } else if (value == "Devolución de producto usado" || value == "Rechazo Garantía") {
                this.screen2Title = '¿Qué productos desea devolver?';
            } else {
                this.screen2Title = '¿Qué productos se extraviaron?';
            }
        }

        this[field] = value;
    }

    resetValidity(target, value) {
        if(value !== '' && value !== undefined && value !== null) {
            target.setCustomValidity('');
            target.reportValidity();
        }
    }

    get mostrarCambioMetodo() {
        return !this.esInversa && this.type != 'Cambio Empleado';
    }

    handleEsInversaChange(event) {
        this.esInversaDevolucion = event.detail.checked;
    }

    handleEsEnvioGratis(event) {
        this.esEnvioGratis = event.detail.checked;
    }

    async setDireccionCambioEmpleado() {
        // solo_deportes
        getNuevoEnvioRetiro({operadorABuscar: 'solo_deportes'})
        .then(result => {
            this.metodoEnvio = result['label'];
            this.metodoEnvioId = result['value'];
            this.shippingStreet = 'Aconquija 2308';
            this.shippingCity = 'Ituzaingó';
            this.shippingPostalCode = '1714';
        })
    }

    async nextScreen4() {
        this.showScreen4 = true;
        this.loadSelectedOrderItems();
        this.bonificationType = '';
        this.bonificationAmmount = 0;
        this.paymentType = '';
        this.paymentStatus = '';
        this.paymentAmmount = 0;
        this.mostrarBonificacion = false;
        this.mostrarPago = false;
        this.showAddProductButton = false;
        this.nextButtonLabel = 'Crear réplica';
    }

    async goToNextScreen() {
        if (this.showScreen1) {
            let field = this.template.querySelector('[data-id="type"]');

            if(!field.value) {
                field.setCustomValidity('Elegí un tipo de réplica');
                field.reportValidity();
                return;
            }
            if(this.type === 'Reenvío') {
                this.showReturnButton = true;
                this.showScreen1 = false;
                this.showScreen1ReShip = true;
                return;
            }
            if(this.type === 'Cambio') {
                this.showReturnButton = true;
                this.showScreen1 = false;
                this.showScreen1Cambio = true;
                return;
            }
            if (this.type == 'Cambio Empleado') {
                await this.setDireccionCambioEmpleado();
            } else if (this.shippingStreet == 'Aconquija 2308') {
                await this.getOrderDetails();
            }
            await this.loadOrderItems();
            if (this.orderItemsNotLost.length == 0) {
                toast(this, '', "La orden ya no tiene productos disponibles para réplica", 'error');
                return;
            }
            this.showReturnButton = true;
            this.showScreen1 = false;
            this.showScreen2 = true;
        } else if (this.showScreen1ReShip) {
            let field = this.template.querySelector('[data-id="selectedStock"]');

            if(!field.value) {
                field.setCustomValidity('Elegí el stock a utilizar');
                field.reportValidity();
                return;
            }
            this.showScreen1ReShip = false;
            await this.loadOrderItems();
            if (this.orderItemsNotLost.length == 0) {
                toast(this, '', "La orden ya no tiene productos disponibles para réplica", 'error');
                return;
            }
            if (this.type === 'Reenvío') {
                if(this.selectedStock === 'Stock Original') {
                    this.nextScreen4();
                } else {
                    this.showScreen3 = true;
                    this.loadLostOrderItems();
                    this.showAddProductButton = true;
                }
            }
        } else if (this.showScreen1Cambio) {
            await this.loadOrderItems();
            if (this.orderItemsNotLost.length == 0) {
                toast(this, '', "La orden ya no tiene productos disponibles para réplica", 'error');
                return;
            }
            this.showScreen1Cambio = false;
            this.showScreen2 = true;
        } else if (this.showScreen2) {
            this.showScreen2 = false;
            if (this.esInversa || this.esDevolucionProducto) {
                this.loadInversaItems();
                this.nextScreen4();
            } else {
                this.loadLostOrderItems();
                this.showScreen3 = true;
                this.showAddProductButton = true;
            }
        } else if (this.showScreen3) {
            this.showScreen3 = false;
            this.nextScreen4();
        } else if (this.showScreen4) {
            let field = this.template.querySelector('[data-id="reason"]');

            if(!field.value && this.replicaReasonOptions.length > 0) {
                field.setCustomValidity('Elegí un Motivo de réplica');
                field.reportValidity();
                return;
            }

            if(this.showOtherReplicaReason) {
                field = this.template.querySelector('[data-id="otherReason"]');
                if(!field.value) {
                    field.setCustomValidity('Ingrese un Motivo de réplica');
                    field.reportValidity();
                    return;
                }
            }

            if (this.esInversa && !this.inversaMetodoDeEnvioSeleccionado) {
                toast(this, 'Seleccione un metodo de envio', "No se puede avanzar ya que es necesario seleccionar un método de envío de inversa.", 'warning');
                return;
            }

            if (this.esDevolucionProducto && !this.devolucionMetodoDeEnvioSeleccionado) {
                toast(this, 'Seleccione un metodo de envio', "No se puede avanzar ya que es necesario seleccionar un método de envío que no sea de inversa.", 'warning');
                return;
            }

            if (this.esCambioManoMano && !this.cambioMMMetodoDeEnvioSeleccionado) {
                toast(this, 'Seleccione un metodo de envio', "No se puede avanzar ya que es necesario seleccionar un método de envío cambio mano a mano.", 'warning');
                return;
            }

            if(this.balance !== 0) {
                let errorMessage = this.showBonificationGenerator
                    ? "No se puede avanzar ya que se le debe dinero al cliente, genere una devolucion de saldo"
                    : "No se puede avanzar ya que el cliente debe dinero, genere un pago o bonificacion";
                toast(this, '', errorMessage, 'warning');  
                return;
            }

            let resultReplication = await this.createReplica();
            this.showScreen4 = false;
            this.showScreen5 = true;
            if(this.showErrorMessage) {
                toast(this, '', 'No se pudo crear la réplica. Intentelo nuevamente', 'warning');
            } else {
                const event = new ShowToastEvent({
                    title: 'Success!',
                    message: '{0} creada correctamente',
                    variant: 'success',
                    messageData: [{
                        url: this.urlReplicaOrder,
                        label: 'Réplica',
                    }],
                    mode: 'sticky'
                });
                this.dispatchEvent(event);
                this.handleFinish();
            }
        }
    }

    goToPreviousScreen() {
        if (this.showScreen1ReShip) {
            this.showScreen1ReShip = false;
            this.showScreen1 = true;
            this.showReturnButton = false;
            this.originalStock = false;
        } else if (this.showScreen1Cambio) {
            this.showScreen1Cambio = false;
            this.showScreen1 = true;
            this.showReturnButton = false;
        } else if (this.showScreen2) {
            if(this.type === 'Reenvío') {
                this.showScreen2 = false;
                this.showScreen1ReShip = true;
            } else if(this.type === 'Cambio') {
                this.showScreen2 = false;
                this.showScreen1Cambio = true;
            } else {
                this.showScreen2 = false;
                this.showScreen1 = true;
                this.showReturnButton = false;
            }
            this.esEnvioGratis = false;
        } else if (this.showScreen3) {
            this.showScreen3 = false;
            if(this.type === 'Reenvío') {
                this.showScreen1ReShip = true;
            } else {
                this.showScreen2 = true;
            }
            this.showAddProductButton = false;
        } else if (this.showScreen4) {
            if(this.selectedStock === 'Stock Original') {
                this.showScreen1ReShip = true;
            } else if (this.esInversa || this.esDevolucionProducto) {
                this.showScreen2 = true;
            } else {
                this.showScreen3 = true;
                this.showAddProductButton = true;
            }
            this.nextButtonLabel = 'Siguiente';
            this.showScreen4 = false;
            this.showBonificationGenerator = false;
            this.showPaymentGenerator = false;
            this.balance = '';
        }
    }

    handleCellChange(event) {
        try {
            let saveDraftValues = event.detail.draftValues;
            let updatedItems = [...this.orderItems];
            if (this.showScreen2) {
                updatedItems = [...this.orderItemsNotLost];
            }
            
            for(let saveDraftValue of saveDraftValues) {
                let skuToFind = saveDraftValue.SKU__c;
                let newQuantity = saveDraftValue.Quantity;
                let newPrice = saveDraftValue.UnitPrice;
                let valid = true;

                if ( (newQuantity === undefined || newQuantity === null || newQuantity === '' || newQuantity <= 0)
                    && (newPrice === undefined || newPrice === null || newPrice === '' || newPrice <= 0)) {
                    toast(this, 'Error', 'Ingrese un valor mayor a 0', 'error');
                    valid = false;
                }

                const itemIndex = updatedItems.findIndex(item => item.SKU__c === skuToFind);
                if (itemIndex !== -1) {
                    updatedItems[itemIndex] = {
                        ...updatedItems[itemIndex],
                        Quantity: valid && newQuantity !== undefined ? newQuantity : updatedItems[itemIndex].Quantity,
                        UnitPrice: valid && newPrice !== undefined ? newPrice : updatedItems[itemIndex].UnitPrice,

                    };
                }
            }
            
            this.orderItems = updatedItems;
            if (this.showScreen2) {
                this.orderItemsNotLost = updatedItems;
            }
        } catch (error) {
            toast(this, 'Error', 'Error al actualizar los items de la orden: ' + error.message, 'error');
        }
    }

    async loadOrderItems() {
        this.loading = true;
        try {
            const result = await getOrderItemsFiltered({ orderId: this.recordId });
            const orderItems = result.orderItems;
            const orderItemsCambiados = result.orderItemsCambiados;

            this.orderItemsNotLost = orderItems.reduce((acc, item) => {
                let cant = item.Quantity;
                let ordItemCambiado = orderItemsCambiados.find(i => i.SKU__c == item.SKU__c);
                if (ordItemCambiado) {
                    cant -= ordItemCambiado.Quantity;
                }
                if (cant > 0) {
                    acc.push({
                        SKU__c: item.SKU__c,
                        Name: item.Description,
                        Talle__c: item.Talle__c,
                        Talle_Friendly__c: item.Talle_Friendly__c,
                        Quantity: cant,
                        UnitPrice: item.UnitPrice,
                        Product2Id: item.Product2Id,
                        TotalLineAmount: (item.TotalLineAmount != null && item.TotalLineAmount > 0) ? item.TotalLineAmount : item.TotalPrice,
                        IndvLineAmount: ((item.TotalLineAmount != null && item.TotalLineAmount > 0) ? item.TotalLineAmount : item.TotalPrice) / item.Quantity,
                    });
                }
                return acc;
            }, []);

            this.selectedRows = [];
            if (this.type === 'Reenvío') {
                let arrayProducts = [];
                for (let i = 0; i < this.orderItemsNotLost.length; i++) {
                    let selectedProduct = this.orderItemsNotLost[i];
                    arrayProducts.push(selectedProduct.SKU__c);
                }
                this.selectedRows = [...this.selectedRows, ...arrayProducts];
            }
            if(this.selectedStock === 'Stock Original') {
                this.originalStock = true;
                this.orderItems = orderItems.map(orderItem => ({
                    SKU__c: orderItem.SKU__c,
                    Name: orderItem.Name,
                    Quantity: orderItem.Quantity,
                    UnitPrice: orderItem.UnitPrice,
                    TotalPrice: orderItem.Quantity * orderItem.UnitPrice,
                    Product2Id: orderItem.Product2Id,
                    Talle__c: orderItem.Talle__c,
                    Talle_Friendly__c: orderItem.Talle_Friendly__c
                }));
            } else {
                this.originalStock = false;
            }
            this.loading = false;
        } catch (error) {
            toast(this, 'Error', 'Error al cargar los OrderItems: ' + error.message, 'error');
        }
    }

    addProduct() {
        const productModal = this.template.querySelector('c-product-selector-modal');
        productModal.open(this.products);
    }

    handleProductSelected(event) {
        const selectedProducts = event.detail;
        let orderItemsToAdd = [];
        let rowsToAdd = [];
        
        for(let selectedProduct of selectedProducts) {
            let newOrderItem = {
                SKU__c: selectedProduct.sku,
                Name: selectedProduct.name,
                Talle__c: selectedProduct.Talle__c,
                Talle_Friendly__c: selectedProduct.talleFriendly,
                Quantity: 1,
                UnitPrice: selectedProduct.price,
                Product2Id: selectedProduct.Product2Id
            };
            orderItemsToAdd.push(newOrderItem);
            rowsToAdd.push(newOrderItem.SKU__c);
        }
        
        this.orderItems = [...this.orderItems, ...orderItemsToAdd];
        this.selectedRows = [...this.selectedRows, ...rowsToAdd];
    }

    handleProductDeselected(event) {
        const selectedProducts = event.detail;
        let orderItemsToRemove = [];
        
        for(let selectedProduct of selectedProducts) {
            orderItemsToRemove.push(selectedProduct.sku);
        }
        
        this.orderItems = this.orderItems.filter(
            orderItem => !orderItemsToRemove.includes(orderItem.SKU__c)
        );

        this.selectedRows = this.selectedRows.filter(
            orderItem => !orderItemsToRemove.includes(orderItem)
        );
    }

    handleRowSelection(event) {
        let arrayProducts = [];
    
        switch (event.detail.config.action) {
            case 'selectAllRows':
                for (let selectedProduct of event.detail.selectedRows) {
                    arrayProducts.push(selectedProduct.SKU__c);
                }
                this.selectedRows = [...this.selectedRows, ...arrayProducts];
                break;
            case 'deselectAllRows':
                this.selectedRows = [];
                break;
            case 'rowSelect':
                this.selectedRows = [...this.selectedRows, event.detail.config.value];
                break;
            case 'rowDeselect':
                this.selectedRows = this.selectedRows.filter(orderItem => orderItem !== event.detail.config.value);
                break;
        }
    }

    async getOrderDetails() {
        this.loading = true;
        try {
            let mapResponse = await getOrderDetails({orderId: this.recordId});
            
            this.accountId = mapResponse['accountId'];
            this.recordTypeName = mapResponse['recordtype.name'];
            this.typeName = mapResponse['typeName'];
            this.orderStatus = mapResponse['status'];

            this.getReplicaTypes();
            
            let replicatedOrdersQuantity = parseInt(mapResponse['replicatedOrdersQuantity']);
            // if(replicatedOrdersQuantity >= 2) {
            //     toast(this, '', 'Ya hay 2 réplicas creadas para esta orden', 'info');  
            //     this.handleFinish();
            // }

            this.shippingStreet = mapResponse['shippingStreet'];
            this.shippingCity = mapResponse['shippingCity'];
            this.shippingPostalCode = mapResponse['shippingPostalCode'];
            this.metodoEnvio = mapResponse['metodoEnvio'];

            this.totalOrderItems = parseInt(mapResponse['totalOrderItems']);
            this.totalPayments = parseInt(mapResponse['totalPayments']);
            this.shippingCost = parseInt(mapResponse['shippingCost']);
            this.newShippingCost = parseInt(mapResponse['shippingCost']);
            this.financingCost = parseInt(mapResponse['financingCost']);
            this.newFinancingCost = parseInt(mapResponse['financingCost']);
            this.consumedGiftcards = parseInt(mapResponse['consumedGiftcards']);
            this.consumedCoupons = parseInt(mapResponse['consumedCoupons']);
            this.discount = parseInt(mapResponse['discount']);
            this.esEmpleado = mapResponse['esEmpleado'] === 'true' || mapResponse['esEmpleado'] === true;
            this.employeeDiscountPercentage = parseFloat(mapResponse['employeeDiscountPercentage']) || 0;
            this.loading = false;
        } catch (error) {
            toast(this, 'Error', 'Error al obtener detalles de la orden: ' + error.message, 'error');
        }
    }

    getReplicaTypes() {
        this.replicaOptions = [];

        if((this.recordTypeName === 'Directa' && (this.typeName == 'Venta nueva' || this.typeName == 'Siniestro' || this.typeName == 'Reenvío')) || this.recordTypeName === 'Reservas') {
            if(this.orderStatus === 'Enviada' || this.orderStatus === 'Entregada sucursal') {
                this.replicaOptions = [...this.replicaOptions, { label: 'Siniestro', value: 'Siniestro' }];
                this.replicaOptions = [...this.replicaOptions, { label: 'Reenvío', value: 'Reenvío' }];
                this.replicaOptions = [...this.replicaOptions, { label: 'Cambio mano a mano', value: 'Cambio mano a mano' }];
                this.replicaOptions = [...this.replicaOptions, { label: 'Cambio', value: 'Cambio' }];
                this.replicaOptions = [...this.replicaOptions, { label: 'Cambio Empleado', value: 'Cambio Empleado' }];
                this.replicaOptions = [...this.replicaOptions, { label: 'Reclamo garantía', value: 'Reclamo garantía' }];
            } else if (this.orderStatus === 'Vencida') {
                this.replicaOptions = [...this.replicaOptions, { label: 'Reenvío', value: 'Reenvío' }];
            }
        } else if(this.recordTypeName === 'Directa' && this.typeName == 'Cambio mano a mano') {
            if(this.orderStatus === 'Enviada') {
                this.replicaOptions = [...this.replicaOptions, { label: 'Cambio mano a mano', value: 'Cambio mano a mano' }];
                this.replicaOptions = [...this.replicaOptions, { label: 'Cambio', value: 'Cambio' }];
                this.replicaOptions = [...this.replicaOptions, { label: 'Reclamo garantía', value: 'Reclamo garantía' }];
            }
        } else if(this.recordTypeName === 'Entrega Giftcard / Cupón') {
            // N/A
        } else if (this.recordTypeName === 'Devolución de Producto') {
            if(this.orderStatus === 'Enviada') {
                this.replicaOptions = [...this.replicaOptions, { label: 'Siniestro', value: 'Siniestro' }];
                this.replicaOptions = [...this.replicaOptions, { label: 'Reenvío', value: 'Reenvío' }];
            }
        } else if(this.recordTypeName === 'Cambio Empleado') {
            if(this.orderStatus === 'Enviada') {
                this.replicaOptions = [...this.replicaOptions, { label: 'Siniestro', value: 'Siniestro' }];
                this.replicaOptions = [...this.replicaOptions, { label: 'Reenvío', value: 'Reenvío' }];
                this.replicaOptions = [...this.replicaOptions, { label: 'Cambio Empleado', value: 'Cambio Empleado' }];
                this.replicaOptions = [...this.replicaOptions, { label: 'Reclamo garantía', value: 'Reclamo garantía' }];
            }
        } else if(this.recordTypeName === 'Entrega rápida') {
            if(this.orderStatus === 'Entregada sucursal' || this.orderStatus === 'Lista para entregar') {
                this.replicaOptions = [...this.replicaOptions, { label: 'Reenvío', value: 'Reenvío' }];
                this.replicaOptions = [...this.replicaOptions, { label: 'Cambio mano a mano', value: 'Cambio mano a mano' }];
                this.replicaOptions = [...this.replicaOptions, { label: 'Cambio', value: 'Cambio' }];
                this.replicaOptions = [...this.replicaOptions, { label: 'Reclamo garantía', value: 'Reclamo garantía' }];
            } else if (this.orderStatus === 'Vencida') {
                this.replicaOptions = [...this.replicaOptions, { label: 'Reenvío', value: 'Reenvío' }];
            }
        }  else if(this.recordTypeName === 'Inversa') {
            if(this.orderStatus === 'Recepcionada' && this.typeName == 'Cambio') {
                this.replicaOptions = [...this.replicaOptions, { label: 'Devolución de producto usado', value: 'Devolución de producto usado' }];
            }
            if(this.orderStatus === 'Información enviada a fábrica' && this.typeName == 'Reclamo garantía') {
                this.replicaOptions = [...this.replicaOptions, { label: 'Rechazo Garantía', value: 'Rechazo Garantía' }];
            }
        }
    }

    loadInversaItems() {
        let foundOrderItems = [];
        for(let skuSelectedRow of this.selectedRows) {
            let foundOrderItem = this.orderItemsNotLost.find(orderItem => orderItem.SKU__c === skuSelectedRow);
            foundOrderItems.push(foundOrderItem);
        }

        this.orderItemsOriginales = foundOrderItems.map(orderItem => ({
            SKU__c: orderItem.SKU__c,
            Name: orderItem.Name,
            Quantity: orderItem.Quantity,
            UnitPrice: orderItem.UnitPrice,
            TotalPrice: orderItem.Quantity * orderItem.UnitPrice,
            Product2Id: orderItem.Product2Id,
            Talle__c: orderItem.Talle__c,
            Talle_Friendly__c: orderItem.Talle_Friendly__c,
            IndvLineAmount: orderItem.IndvLineAmount != null ? orderItem.IndvLineAmount : orderItem.UnitPrice
        }));
        
        this.orderItems = foundOrderItems.map(orderItem => ({
            SKU__c: orderItem.SKU__c,
            Name: orderItem.Name,
            Quantity: orderItem.Quantity,
            UnitPrice: orderItem.UnitPrice,
            TotalPrice: orderItem.Quantity * orderItem.UnitPrice,
            Product2Id: orderItem.Product2Id,
            Talle__c: orderItem.Talle__c,
            Talle_Friendly__c: orderItem.Talle_Friendly__c,
            IndvLineAmount: orderItem.IndvLineAmount != null ? orderItem.IndvLineAmount : orderItem.UnitPrice
        }));
    }

    loadLostOrderItems() {
        let foundOrderItems = [];
        for(let skuSelectedRow of this.selectedRows) {
            let foundOrderItem = this.orderItemsNotLost.find(orderItem => orderItem.SKU__c === skuSelectedRow);
            foundOrderItems.push(foundOrderItem);
        }

        this.orderItemsOriginales = foundOrderItems.map(orderItem => ({
            SKU__c: orderItem.SKU__c,
            Name: orderItem.Name,
            Quantity: orderItem.Quantity,
            UnitPrice: orderItem.UnitPrice,
            TotalPrice: orderItem.Quantity * orderItem.UnitPrice,
            Product2Id: orderItem.Product2Id,
            Talle__c: orderItem.Talle__c,
            Talle_Friendly__c: orderItem.Talle_Friendly__c,
            IndvLineAmount: orderItem.IndvLineAmount != null ? orderItem.IndvLineAmount : orderItem.UnitPrice
        }));

        this.selectedRows = [];
        
        this.orderItems = foundOrderItems.map(orderItem => ({
            SKU__c: orderItem.SKU__c,
            Name: orderItem.Name,
            Quantity: orderItem.Quantity,
            UnitPrice: orderItem.UnitPrice,
            TotalPrice: orderItem.Quantity * orderItem.UnitPrice,
            Product2Id: orderItem.Product2Id,
            Talle__c: orderItem.Talle__c,
            Talle_Friendly__c: orderItem.Talle_Friendly__c,
            IndvLineAmount: orderItem.IndvLineAmount != null ? orderItem.IndvLineAmount : orderItem.UnitPrice
        }));
    }

    async loadSelectedOrderItems() {
        this.loading = true;
        let foundOrderItems = [];
        for (let skuSelectedRow of this.selectedRows) {
            let foundOrderItem = this.orderItems.find(orderItem => orderItem.SKU__c === skuSelectedRow);
            foundOrderItems.push(foundOrderItem);
        }
        if (this.type == 'Devolución de producto usado') {
            let prodDevolucion = await getSKUDevolucion();
            let count = foundOrderItems.reduce((acc, row) => acc += 1 * row.Quantity, 0);
            this.orderItemsSelected = [{
                SKU__c: prodDevolucion.SKU__c,
                Name: prodDevolucion.Description,
                Quantity: count,
                UnitPrice: 0,
                TotalPrice: 0,
                Product2Id: prodDevolucion.Id,
                Talle__c: prodDevolucion.Talle__c,
                Talle_Friendly__c: prodDevolucion.Talle_Friendly__c,
                IndvLineAmount: 0
            }]
        } else {
            this.orderItemsSelected = foundOrderItems.map(orderItem => ({
                SKU__c: orderItem.SKU__c,
                Name: orderItem.Name,
                Quantity: orderItem.Quantity,
                UnitPrice: orderItem.UnitPrice,
                TotalPrice: orderItem.Quantity * orderItem.UnitPrice,
                Product2Id: orderItem.Product2Id,
                Talle__c: orderItem.Talle__c,
                Talle_Friendly__c: orderItem.Talle_Friendly__c,
                IndvLineAmount: orderItem.IndvLineAmount != null ? orderItem.IndvLineAmount : orderItem.UnitPrice
            }));

            if (this.type == 'Reenvío' && this.reason == 'Art.Faltante' && this.prodAccesorioFaltante != null) {
                this.orderItemsSelected.push({
                    SKU__c: this.prodAccesorioFaltante.SKU__c,
                    Name: this.prodAccesorioFaltante.Description,
                    Quantity: 1,
                    UnitPrice: 1,
                    TotalPrice: 1,
                    Product2Id: this.prodAccesorioFaltante.Id,
                    Talle__c: this.prodAccesorioFaltante.Talle__c,
                    Talle_Friendly__c: this.prodAccesorioFaltante.Talle_Friendly__c,
                    IndvLineAmount: 1
                });
            }
        }

        this.totalOrderItemsReplica = 0;
        for (let orderItemSelected of this.orderItemsSelected) {
            this.totalOrderItemsReplica += (orderItemSelected.IndvLineAmount * orderItemSelected.Quantity);
        }

        // Si es Reenvío con Art.Faltante, el balance debe ser 0
        if (this.type === 'Reenvío' && this.reason === 'Art.Faltante') {
            this.balance = 0;
            this.paymentCopy = this.totalPayments;
            this.showBonificationGenerator = false;
            this.showPaymentGenerator = false;
        } else if (this.type === 'Siniestro') {
            let totalPrevio = this.orderItemsOriginales.reduce((acc, oi) => {acc += (oi.IndvLineAmount * oi.Quantity);return acc;}, 0) + this.financingCost;
            let nuevoTotal = this.totalOrderItemsReplica + this.newFinancingCost;
            this.balance = parseFloat((nuevoTotal - totalPrevio - this.consumedCoupons).toFixed(2));
            if (this.reason != null && this.reason.includes('Parcial')) {
                this.balance += this.newShippingCost;
                this.paymentCopy = totalPrevio;
            } else {
                this.balance += (this.newShippingCost - this.shippingCost);
                this.paymentCopy = totalPrevio + this.shippingCost;
            }
            let saldoAFavor = this.balance * -1;
            if (saldoAFavor > this.paymentCopy) {
                // no se puede devolver mas de lo que pago
                this.balance = this.paymentCopy * -1;
            }
        } else if (this.esInversa) {
            this.balance = 0;
        } else if (this.esDevolucionProducto) {
            this.balance = this.newShippingCost;
        } else {
            this.employeeDiscount = (this.totalOrderItemsReplica * (this.employeeDiscountPercentage / 100)).toFixed(2);
            let descuentoTotal = this.consumedGiftcards + this.consumedCoupons + this.discount;
            let nuevoTotal = this.totalOrderItemsReplica + this.newShippingCost + this.newFinancingCost;
            this.balance = parseFloat((nuevoTotal - this.totalPayments - descuentoTotal - this.montoBonificacion - this.employeeDiscount)).toFixed(2);
            let saldoAFavor = this.balance * -1;
            if (saldoAFavor > this.totalPayments) {
                // no se puede devolver mas de lo que pago
                this.balance = this.totalPayments * -1;
            }
            if (this.totalOrderItemsNew === 0) {
                // si no hay items en la orden, se devuelve el shippingCost y el financingCost
                this.balance -= (this.shippingCost + this.financingCost).toFixed(2);
            }
            if (this.type === 'Reenvío') {
                this.paymentCopy = this.totalPayments;
            }
        }

        if(this.balance < 0) {
            this.balance = this.balance * -1;
            this.montoBonificacion = this.balance;
            this.balance = 'Se le debe $' + this.balance + ' al cliente';
            this.showBonificationGenerator = true;
            this.showPaymentGenerator = false;
        } else if(this.balance > 0) {
            this.montoPago = this.balance;
            this.balance = 'El cliente debera abonar $' + this.balance;
            this.showBonificationGenerator = false;
            this.showPaymentGenerator = true;
        } else {
            this.showBonificationGenerator = false;
            this.showPaymentGenerator = false;
            this.balance = 0;
        }
        this.loading = false;
    }

    openModal() {
        this.isModalOpen = true;
    }

    openPaymentModal() {
        this.isPaymentModalOpen = true;
    }

    openShippingCostModal() {
        this.isShippingCostModalOpen = true;
    }

    openFinancingCostModal() {
        this.isFinancingCostModalOpen = true;
    }

    openShippingEditorModal() {
        if (this.esInversa) {
            this.showMetodoEnvioInversaEditor = true;
        } else {
            this.showMetodoEnvioEditor = true;
        }
    }

    handleBonificacionCreated(event) {
        const bonificacion = event.detail;
        this.tipoBonificacion = bonificacion["Tipo__c"];
        this.mostrarBonificacion = true;
        this.balance = 0;
        this.isModalOpen = false;
        this.showBonificationGenerator = false;
    }

    handlePaymentCreated(event) {
        const pago = event.detail;
        this.tipoPago = pago["Tipo__c"];
        this.estadoPago = pago["Estado__c"];
        this.numeroOperacionMP = pago["Numero_de_operacion_Mercado_Pago__c"] || '';
        this.mostrarPago = true;
        this.balance = 0;
        this.isPaymentModalOpen = false;
        this.showPaymentGenerator = false;
    }

    handleShippingCostModified(event) {
        const newShippingCost = event.detail;
        this.newShippingCost = newShippingCost;
        this.isShippingCostModalOpen = false;
        this.loadSelectedOrderItems();
        toast(this, 'Éxito', 'Costo de envío modificado correctamente', 'success');
    }

    handleFinancingCostModified(event) {
        const newFinancingCost = event.detail;
        this.newFinancingCost = newFinancingCost;
        this.isFinancingCostModalOpen = false;
        this.loadSelectedOrderItems();
        toast(this, 'Éxito', 'Costo de financiación modificado correctamente', 'success');
    }

    handleMetodoEnvioConfirm(event) {
        const metodoEnvio = event.detail.metodoEnvio;
        let operadorLogistico;
        let sucursal;
        if (this.esInversa) {
            let esDomicilio;
            this.inversaMetodoDeEnvioSeleccionado = true;
            if (event.detail.sucursal != null) {
                sucursal = event.detail.sucursal;
                this.shippingStreet = sucursal.address;
                this.shippingCity = sucursal.city;
                this.shippingPostalCode = String(sucursal.postcode);
                this.envioDTO = {
                    name: sucursal.name,
                    address: sucursal.address,
                    city: sucursal.city,
                    state: sucursal.state,
                    postcode: String(sucursal.postcode),
                    is_disabled: false,
                    external_id: sucursal.external_id,
                    operador_logistico: sucursal.operador_logistico,
                };
                operadorLogistico = sucursal.operador_logistico;
                esDomicilio = false;
            } else {
                operadorLogistico = event.detail.operadorLogistico;
                esDomicilio = true;
            }
            getNuevoEnvioRetiroInversa({operadorABuscar: operadorLogistico, esDomicilio: esDomicilio})
            .then(result => {
                this.metodoEnvio = result['label'];
                this.metodoEnvioId = result['value'];
            })
        } else {
            if (metodoEnvio === 'domicilio') {
                operadorLogistico = event.detail.operadorLogistico;
                this.devolucionMetodoDeEnvioSeleccionado = true;
                this.cambioMMMetodoDeEnvioSeleccionado = false;
                getNuevoEnvio({operadorABuscar: operadorLogistico})
                .then(result => {
                    this.metodoEnvio = result['label'];
                    this.metodoEnvioId = result['value'];
                })
            } else if (metodoEnvio == 'cambiomanomano') {
                operadorLogistico = event.detail.operadorLogistico;
                this.devolucionMetodoDeEnvioSeleccionado = false;
                this.cambioMMMetodoDeEnvioSeleccionado = true;
                getNuevoEnvioCambioManoMano({operadorABuscar: operadorLogistico})
                .then(result => {
                    this.metodoEnvio = result['label'];
                    this.metodoEnvioId = result['value'];
                })
            } else {
                this.devolucionMetodoDeEnvioSeleccionado = true;
                this.cambioMMMetodoDeEnvioSeleccionado = false;
                sucursal = event.detail.sucursal;
                this.shippingStreet = sucursal.address;
                this.shippingCity = sucursal.city;
                this.shippingPostalCode = String(sucursal.postcode);
                this.envioDTO = {
                    name: sucursal.name,
                    address: sucursal.address,
                    city: sucursal.city,
                    state: sucursal.state,
                    postcode: String(sucursal.postcode),
                    is_disabled: false,
                    external_id: sucursal.external_id,
                    operador_logistico: sucursal.operador_logistico,
                };
                getNuevoEnvioRetiro({operadorABuscar: sucursal.operador_logistico})
                .then(result => {
                    this.metodoEnvio = result['label'];
                    this.metodoEnvioId = result['value'];
                })
            }
        }
    }

    closeModal() {
        this.isModalOpen = false;
        this.isPaymentModalOpen = false;
        this.isShippingCostModalOpen = false;
        this.isFinancingCostModalOpen = false;
        this.showMetodoEnvioEditor = false;
        this.showMetodoEnvioInversaEditor = false;
    }

    async getReplicaReasons() {
        const data = await getDependentMap({ 
            objDetail: "Order", 
            contrfieldApiName: "Type",
            depfieldApiName: "Motivo_Replica__c"
        });
        
        if (data) {
            var tempArray = [];
            for (var key in data) {
                if(data[key].length > 0) {
                    tempArray.push({ label: key, value: key });
                }
            }
            
            this.replicaOptions = tempArray;
            this.dependentMap = data;
            this.loading = false;
        }
    }

    async createReplica() {
        this.loading = true;
        try {
            let mapOrderItems = {};
            for(let orderItemSelected of this.orderItemsSelected) {
                mapOrderItems[orderItemSelected.Product2Id] = {
                    Quantity: orderItemSelected['Quantity'],
                    UnitPrice: orderItemSelected['UnitPrice'],
                    SKU__c: orderItemSelected['SKU__c'],
                    Name: orderItemSelected['Name'],
                    Talle__c: orderItemSelected['Talle__c'],
                    Talle_Friendly__c: orderItemSelected['Talle_Friendly__c']
                };
            }

            let mapOrderItemsOriginales = {};
            for(let orderItem of this.orderItemsOriginales) {
                mapOrderItemsOriginales[orderItem.Product2Id] = {
                    Quantity: orderItem['Quantity'],
                    UnitPrice: orderItem['UnitPrice'],
                    SKU__c: orderItem['SKU__c'],
                    Name: orderItem['Name'],
                    Talle__c: orderItem['Talle__c'],
                    Talle_Friendly__c: orderItem['Talle_Friendly__c']
                };
            }
            
            const result = await createReplicaOrder({ 
                orderId: this.recordId, 
                type: this.type, 
                reason: this.reason,
                otherReason: this.otherReason, 
                originalStock: this.originalStock,
                inversaDevolucion: this.esInversaDevolucion,
                envioGratis: this.esEnvioGratis,
                mapOrderItemsReplicas: mapOrderItems, 
                mapOrderItemsOriginales: mapOrderItemsOriginales, 
                bonificationType: this.tipoBonificacion, 
                bonificationAmmount: this.montoBonificacion, 
                accountid: this.accountId,
                paymentCopy: this.paymentCopy,
                paymentType: this.tipoPago,
                paymentStatus: this.estadoPago,
                paymentAmmount: this.montoPago,
                paymentNumeroOperacion: this.numeroOperacionMP,
                shippingStreet: this.shippingStreet,
                shippingCity: this.shippingCity, 
                shippingPostalCode: this.shippingPostalCode, 
                metodoEnvioId: this.metodoEnvioId,
                envioDTO: this.envioDTO,
                financeCost: this.newFinancingCost,
                shippingCost: this.newShippingCost
            });

            for (let key in result) {
                let keyFriendly = key === 'Order' ? 'Orden' :
                                key === 'Bonificacion__c' ? 'Bonificacion' :
                                key === 'Case' ? 'Caso' :
                                key === 'Pago__c' ? 'Pago' : key;

                if(key === 'Order') {
                    this.urlReplicaOrder = '/lightning/r/' + key + '/' + result[key] + '/view';
                }

                keyFriendly += ' ' + result[key];
                let createdRecord = { 
                    name: keyFriendly, 
                    link: '/lightning/r/' + key + '/' + result[key] + '/view', 
                    id: result[key] 
                };
                this.createdOrders = [...this.createdOrders, createdRecord];
            }
            this.showErrorMessage = false;
            this.loading = false;
        } catch (error) {
            this.showErrorMessage = true;
            this.errorMessage = error.message;
            toast(this, 'Error', 'Error al crear la réplica: ' + error.message, 'error');
        }
    }

    handleFinish() {
        this.dispatchEvent(new CloseActionScreenEvent());
    }
}
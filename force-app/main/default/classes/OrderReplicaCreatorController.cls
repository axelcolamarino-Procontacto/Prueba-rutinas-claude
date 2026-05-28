public with sharing class OrderReplicaCreatorController {
    @AuraEnabled(cacheable=true)
    public static Map<String, Object> getPaginatedProducts(Integer page, Integer pageSize) {
        Integer offset = (page - 1) * pageSize;
        List<Product2> products = [
            SELECT Id, ProductCode, Name,sku__c,Description, Talle__c, Talle_Friendly__c,(select UnitPrice from pricebookentries where pricebook2id = :Constants.getStandardPricebookId())
            FROM Product2 
            where productCode != ''
            LIMIT :pageSize OFFSET :offset
        ];
        List<Product2> productsWithPrice = new List<Product2>();

        for (Product2 product : products) {
            if(product.pricebookentries.size() > 0) {
                productsWithPrice.add(product);
            }
        }
        Integer totalCount = [SELECT COUNT() FROM Product2 where productCode != ''];

        Map<String, Object> result = new Map<String, Object>();
        result.put('products', productsWithPrice);
        result.put('totalCount', totalCount);
        return result;
    }

    @AuraEnabled(cacheable=true)
    public static List<OrderItem> getOrderItems(String orderId) {
        return [
            SELECT Id, SKU__c, Quantity, UnitPrice,Description,Talle__c, Talle_Friendly__c
            FROM OrderItem
            WHERE OrderId = :orderId
        ];
    }

    @AuraEnabled(cacheable=true)
    public static Map<String,Object> getOrderItemsFiltered(String orderId) {

        List<OrderItem> orderItems = [
            SELECT Id, SKU__c, Quantity, UnitPrice,Description,Talle__c, Talle_Friendly__c, Product2Id, TotalLineAmount, TotalPrice 
            FROM OrderItem
            WHERE OrderId = :orderId AND SKU__c != :Constants.SKU_DESCUENTO AND SKU__c != '99904DIFERENPREU'
        ];

        List<OrderItem> orderItemsCambiados = [
            SELECT Id, SKU__c, Quantity, UnitPrice,Description,Talle__c, Talle_Friendly__c, Product2Id, TotalLineAmount, TotalPrice 
            FROM OrderItem
            WHERE Order.Original_Order__c = :orderId AND SKU__c != :Constants.SKU_DESCUENTO AND SKU__c != '99904DIFERENPREU'
        ];

        Map<String, Object> result = new Map<String, Object>();
        result.put('orderItems', orderItems);
        result.put('orderItemsCambiados', orderItemsCambiados);

        return result; 
    }

    @AuraEnabled(cacheable=true)
    public static Map<String,Object> searchProducts(String searchKey, Integer page, Integer pageSize, Boolean checkboxProductsWithoutStock) {
        /*
        if (String.isBlank(searchKey)) {
            throw new AuraHandledException('El término de búsqueda no puede estar vacío.');
        }*/

        Integer offset = (page -    1) * pageSize;

        // Query de búsqueda basada en nombre o SKU
        Id pricebookId = Constants.getStandardPricebookId(); // Reemplazar con el ID deseado

        String filter = '';

        if (!checkboxProductsWithoutStock) {
            filter += 'WHERE Stock__c > 0';
        }
        if(String.isNotBlank(searchKey)) {
            if(checkboxProductsWithoutStock){
                filter+= 'WHERE ';
            }else{
                filter += ' AND';
            }
            filter += '(Name LIKE \'%' + String.escapeSingleQuotes(searchKey) + '%\' ' +
                    'OR Description LIKE \'%' + String.escapeSingleQuotes(searchKey) + '%\') ';
        }

        // Construcción de la query dinámica
        String query = 'SELECT Id, ProductCode, Name, sku__c, Description, Talle_Friendly__c, Stock__c, ' + 
                    '(SELECT UnitPrice FROM PricebookEntries WHERE Pricebook2Id = :pricebookId) ' +
                    'FROM Product2 '+
                    filter +
                    'LIMIT :pageSize OFFSET :offset';

        // Ejecutar la consulta dinámica
        List<Product2> productsList = Database.query(query);

        List<Product2> productsWithPrice = new List<Product2>();

        for (Product2 product : productsList) {
            if(product.pricebookentries.size() > 0) {
                productsWithPrice.add(product);
            }
        }




        // Construcción de la query dinámica
        String countQuery = 'SELECT COUNT() FROM Product2 '+ filter;

        // Ejecutar la consulta dinámica
        Integer totalCount = Database.countQuery(countQuery);

        Map<String, Object> result = new Map<String, Object>();
        result.put('products', productsWithPrice);
        result.put('totalCount', totalCount);

        return result; 
    }

    @AuraEnabled(cacheable = false)
    public static Map<String,String> getOrderDetails(String orderId){
        Map<String,String> responseMap = new Map<String,String>();
        Order order = [
            SELECT AccountId, GrandTotalAmount, base_finance_cost_amount__c, RecordType.Name, Status, Costo_de_envio__c, Cupon_solicitado__c, 
                    Monto_cupon__c, Account.Employee_Flag__c, Descuento_Empleado__c, Bonificacion_Solicitada__c, base_gift_cards_amount__c, base_discount_amount__c, Type,
                    Direccion_de_Entrega__Street__s, Direccion_de_Entrega__City__s, Direccion_de_Entrega__PostalCode__s, Provincia__c, Metodo_de_envio__r.Name,
                    (SELECT Id, SKU__c, Quantity, UnitPrice FROM OrderItems),
                    (SELECT Id FROM Replicas__r),
                    (SELECT Id, Importe__c, Estado_Pago__c FROM Pagos2__r WHERE Estado_Pago__c = 'Acreditado' OR Estado_Pago__c = 'Pendiente') 
            FROM Order 
            WHERE Id = :orderId
        ];

        List<Order> replicatedOrders = order.Replicas__r;
        List<Pago__c> payments = order.Pagos2__r;

        Decimal consumedGiftcards = order.base_gift_cards_amount__c ?? 0;
        Decimal consumedCoupons = (order.base_discount_amount__c ?? 0) * -1;
        Decimal discount = 0;
        Decimal totalOrderItems = 0;

        for (OrderItem orderItem : order.OrderItems) {
            if (orderItem.SKU__c == Constants.SKU_DESCUENTO) {
                consumedCoupons += orderItem.UnitPrice;
            } else if (orderItem.SKU__c == '99904DIFERENPREU') {
                discount += orderItem.UnitPrice;
            } else {
                totalOrderItems += orderItem.Quantity * orderItem.UnitPrice;
            }
        }

        String shippingStreet = order.Direccion_de_Entrega__Street__s;
        String shippingCity = order.Direccion_de_Entrega__City__s;
        String shippingPostalCode = order.Direccion_de_Entrega__PostalCode__s;
        Integer replicatedOrdersQuantity = replicatedOrders?.size() ?? 0;

        Decimal totalPayments = 0;
        for(Pago__c pago : payments){
            totalPayments += pago.Importe__c;
        }

        responseMap.put('accountId', order.accountid);
        responseMap.put('totalOrderItems', '' + totalOrderItems.setScale(2));
        responseMap.put('shippingCost', '' + (order.Costo_de_envio__c ?? 0));
        responseMap.put('financingCost', '' + (order.base_finance_cost_amount__c ?? 0));
        responseMap.put('consumedGiftcards', '' + consumedGiftcards.setScale(2));
        responseMap.put('consumedCoupons', '' + consumedCoupons.setScale(2));
        responseMap.put('discount', '' + discount.setScale(2));
        responseMap.put('shippingStreet', shippingStreet != null ? shippingStreet : '');
        responseMap.put('shippingCity', shippingCity != null ? shippingCity : '');
        responseMap.put('shippingPostalCode', shippingPostalCode != null ? shippingPostalCode : '');
        responseMap.put('recordtype.name', '' + order.recordtype.name);
        responseMap.put('typeName', '' + order.Type);
        responseMap.put('status', '' + order.status);
        responseMap.put('metodoEnvio', '' + order.Metodo_de_envio__r.Name);
        responseMap.put('replicatedOrdersQuantity', '' + replicatedOrdersQuantity);
        responseMap.put('totalPayments', '' + totalPayments);
        responseMap.put('employeeDiscountPercentage', '' + (order.Descuento_Empleado__c ?? 0));
        responseMap.put('esEmpleado', '' + order.Account.Employee_Flag__c);
        return responseMap;
    }

    @AuraEnabled(cacheable=false)
    public static Map<String,String> createReplicaOrder(String orderId, String type, String reason, String otherReason, Boolean originalStock, Boolean inversaDevolucion, Boolean envioGratis,  
    Map<String,Map<String,String>> mapOrderItemsReplicas, Map<String,Map<String,String>> mapOrderItemsOriginales, 
    String bonificationType, Decimal bonificationAmmount, String accountId, Decimal paymentCopy, String paymentType, String paymentStatus, Decimal paymentAmmount,
    String shippingStreet, String shippingCity, String shippingPostalCode, String metodoEnvioId, CustomDTOSucursal envioDTO, Decimal financeCost, Decimal shippingCost, String paymentNumeroOperacion) {
        Order orderOriginal = [
            SELECT Id, External_Id__c, GrandTotalAmount, Prioridad__c, Nombre_del_tercero_autorizado__c, Apellido_del_tercero_autorizado__c, DNI_del_tercero_autorizado__c, Sucursal__c, Shipping_Method__c,
            Store_Id__c, Costo_de_envio__c, base_finance_cost_amount__c, Motivo_devolucion__c, Num_de_Seguimiento_de_ML__c, Sucursal_pickup__c, AccountId, Invoice_Type__c, Tipo_Factura__c, BillingStreet, BillingPostalCode, BillingCity, BillingState,
            Provincia__c, Compania__c, store_pickup_external_id__c, Metodo_de_envio__c, Account.Employee_Flag__c, Descuento_Empleado__c, AuthorizationCode__c,
            (SELECT Id FROM Replicas__r WHERE type =: type),
            (SELECT cuit__c,tipo_de_tarjeta_de_credito__c,tipo_de_documento_mercado_pago__c, numero_de_documento_mercado_pago__c, titular_tarjeta__c,
            importe__c,cuotas__c,Metodo_Pago__c,Codigo_forma_de_pago__c,Estado_Pago__c,Numero_de_operacion_Mercado_Pago__c from Pagos2__r WHERE Estado_Pago__c = 'Acreditado' ORDER BY CreatedDate ASC)
            FROM Order 
            WHERE id =:orderId
        ];

        Map<String, Sucursal__c> mapaSucursales = new Map<String, Sucursal__c>();
        List<Sucursal__c> sucursales = [SELECT Id, ID_Sucursal__c, Direccion_de_la_Sucursal__Street__s, Direccion_de_la_Sucursal__City__s, Direccion_de_la_Sucursal__PostalCode__s FROM Sucursal__c];
        for(Sucursal__c suc : sucursales){
            mapaSucursales.put(suc.ID_Sucursal__c, suc);
        }

        Boolean esInversa = false;
        Boolean esDevolucionProducto = false;
        Prefijo_replica__c prefijo;
        Prefijo_replica__c prefijo2;
        String prefix, prefix_copy;
        String prefix2, prefix2_copy;
        if (type == 'Cambio mano a mano') {
            List<Prefijo_replica__c> prefijoList = [SELECT Valor__c FROM Prefijo_replica__c WHERE Name = :(type + ' Directa') LIMIT 1];
            List<Prefijo_replica__c> prefijo2List = [SELECT Valor__c FROM Prefijo_replica__c WHERE Name = :(type + ' Inversa') LIMIT 1];
            prefijo = !prefijoList.isEmpty() ? prefijoList[0] : null;
            prefijo2 = !prefijo2List.isEmpty() ? prefijo2List[0] : null;
            prefix = prefijo != null ? prefijo.Valor__c : '1';
            prefix2 = prefijo2 != null ? prefijo2.Valor__c : '1';
        } else {
            List<Prefijo_replica__c> prefijoList = [SELECT Valor__c FROM Prefijo_replica__c WHERE Name = :type LIMIT 1];
            prefijo = !prefijoList.isEmpty() ? prefijoList[0] : null;
            prefix = prefijo != null ? prefijo.Valor__c : '1';
        }
        prefix_copy = prefix;
        prefix2_copy = prefix2;

        for (Integer i = 0; i < orderOriginal.Replicas__r.size(); i++) {
            prefix += prefix_copy;
            if (prefix2 != null) {
                prefix2 += prefix2_copy;
            }
        }

        Order clone = new Order();
        clone.status = Constants.ORDER_STATUS_NEW;
        clone.Name = prefix + orderOriginal.External_Id__c;
        clone.External_Id__c = prefix + orderOriginal.External_Id__c;
        if (type == 'Cambio' || type == 'Reclamo garantía') {
            clone.RecordTypeId = constants.RT_ORDER_INVERSA;
            esInversa = true;
        }
        if (type == 'Devolución de producto usado' || type == 'Rechazo Garantía') {
            clone.RecordTypeId = constants.RT_ORDER_DEVOLUCION_PRODUCTO;
            clone.Control_de_calidad__c = true;
            esDevolucionProducto = true;
        }
        if (type == 'Cambio Empleado') {
            clone.RecordTypeId = constants.RT_ORDER_CAMBIO_EMPLEADO;
            clone.Descuento_Empleado__c = orderOriginal.Descuento_Empleado__c;
        }
        clone.entity_Id__c = null;
        clone.type = type;
        clone.Motivo_Replica__c = reason;
        clone.detalle__c = otherReason;
        clone.Original_Order__c = orderId;
        clone.EffectiveDate = Date.today();
        clone.pedidos_solicitados__c = false;
        clone.Direccion_de_Entrega__Street__s = shippingStreet;
        clone.Direccion_de_Entrega__City__s = shippingCity;
        clone.Direccion_de_Entrega__PostalCode__s = shippingPostalCode;
        clone.Prioridad__c = orderOriginal.Prioridad__c;
        clone.Nombre_del_tercero_autorizado__c = orderOriginal.Nombre_del_tercero_autorizado__c;
        clone.Apellido_del_tercero_autorizado__c = orderOriginal.Apellido_del_tercero_autorizado__c;
        clone.DNI_del_tercero_autorizado__c = orderOriginal.DNI_del_tercero_autorizado__c;
        clone.Store_Id__c = orderOriginal.Store_Id__c;
        clone.Motivo_devolucion__c = orderOriginal.Motivo_devolucion__c;
        clone.Num_de_Seguimiento_de_ML__c = orderOriginal.Num_de_Seguimiento_de_ML__c;
        clone.Sucursal_pickup__c = orderOriginal.Sucursal_pickup__c;
        clone.AccountId = orderOriginal.AccountId;
        clone.Invoice_Type__c = orderOriginal.Invoice_Type__c;
        clone.Tipo_Factura__c = orderOriginal.Tipo_Factura__c;
        clone.BillingStreet = orderOriginal.BillingStreet;
        clone.BillingPostalCode = orderOriginal.BillingPostalCode;
        clone.BillingCity = orderOriginal.BillingCity;
        clone.BillingState = orderOriginal.BillingState;
        clone.Pagos_acreditados__c = true;
        clone.AuthorizationCode__c = orderOriginal.AuthorizationCode__c;
        if (bonificationType == 'Cupón') {
            clone.Cupon_solicitado__c = true;
            clone.Monto_cupon__c = bonificationAmmount;
        }
        if (originalStock) {
            clone.pedidos_solicitados__c = true;
            clone.Control_de_calidad__c = false;
            clone.Stock_original__c = true;
        }
        if (metodoEnvioId != null && metodoEnvioId != '') {
            clone.Metodo_de_envio__c = metodoEnvioId;
        } else {
            clone.Metodo_de_envio__c = orderOriginal.Metodo_de_envio__c;
        }
        if (!esInversa || esDevolucionProducto) {
            clone.Costo_de_envio__c = shippingCost;
            clone.base_finance_cost_amount__c = financeCost;
        } else {
            clone.Costo_de_envio__c = 0;
            clone.base_finance_cost_amount__c = 0;
        }
        if (envioDTO != null) {
            clone.Direccion_de_Entrega__Street__s = envioDTO.address;
            clone.Direccion_de_Entrega__PostalCode__s = String.valueOf(envioDTO.postcode);
            clone.Direccion_de_Entrega__City__s = envioDTO.city;
            clone.Provincia__c = envioDTO.state;
            clone.Compania__c = envioDTO.operador_logistico;
            clone.store_pickup_external_id__c = envioDTO.external_id;
            if (envioDTO.operador_logistico == 'solo_deportes') {
                clone.Shipping_Method__c = 'storepickup_storepickup';
                clone.Sucursal__c = mapaSucursales.get('sucursal_' + envioDTO.external_id)?.Id;
            } else {
                clone.Sucursal__c = mapaSucursales.get('sucursal_27')?.Id;
            }
        } else {
            clone.Provincia__c = orderOriginal.Provincia__c;
            clone.Compania__c = orderOriginal.Compania__c;
            clone.store_pickup_external_id__c = orderOriginal.store_pickup_external_id__c;
            clone.Sucursal__c = orderOriginal.Sucursal__c;
            clone.Shipping_Method__c = orderOriginal.Shipping_Method__c;
        }
        if (mapOrderItemsReplicas.keySet().isEmpty()) {
            // Si no hay nuevos order items, se debera pasar a entrega cupon/giftcard una vez creado el cupon
            clone.Convertir_entrega_cupon__c = true;
        }
        clone.Devolucion_de_dinero__c = inversaDevolucion;
        clone.Envio_gratis__c = envioGratis;
        if (Test.isRunningTest()) {
            clone.Pricebook2Id = Test.getStandardPricebookId();
        }
        insert clone;

        Order cloneInversa;
        if (type == 'Cambio mano a mano') {
            cloneInversa = new Order();
            cloneInversa.RecordTypeId = constants.RT_ORDER_INVERSA;
            cloneInversa.status = Constants.ORDER_STATUS_NEW;
            cloneInversa.Name = prefix2 + orderOriginal.External_Id__c;
            cloneInversa.External_Id__c = prefix2 + orderOriginal.External_Id__c;
            cloneInversa.entity_Id__c = null;
            cloneInversa.type = type;
            cloneInversa.EffectiveDate = Date.today();
            cloneInversa.Motivo_Replica__c = reason;
            cloneInversa.detalle__c = otherReason;
            cloneInversa.Original_Order__c = orderId;
            cloneInversa.pedidos_solicitados__c = true;
            cloneInversa.Direccion_de_Entrega__Street__s = clone.Direccion_de_Entrega__Street__s;
            cloneInversa.Direccion_de_Entrega__City__s = clone.Direccion_de_Entrega__City__s;
            cloneInversa.Direccion_de_Entrega__PostalCode__s = clone.Direccion_de_Entrega__PostalCode__s;
            cloneInversa.Provincia__c = clone.Provincia__c;
            cloneInversa.Compania__c = clone.Compania__c;
            cloneInversa.store_pickup_external_id__c = clone.store_pickup_external_id__c;
            cloneInversa.Prioridad__c = orderOriginal.Prioridad__c;
            cloneInversa.Nombre_del_tercero_autorizado__c = orderOriginal.Nombre_del_tercero_autorizado__c;
            cloneInversa.Apellido_del_tercero_autorizado__c = orderOriginal.Apellido_del_tercero_autorizado__c;
            cloneInversa.DNI_del_tercero_autorizado__c = orderOriginal.DNI_del_tercero_autorizado__c;
            cloneInversa.Store_Id__c = orderOriginal.Store_Id__c;
            cloneInversa.Motivo_devolucion__c = orderOriginal.Motivo_devolucion__c;
            cloneInversa.Num_de_Seguimiento_de_ML__c = orderOriginal.Num_de_Seguimiento_de_ML__c;
            cloneInversa.Sucursal_pickup__c = orderOriginal.Sucursal_pickup__c;
            cloneInversa.AccountId = orderOriginal.AccountId;
            cloneInversa.Invoice_Type__c = orderOriginal.Invoice_Type__c;
            cloneInversa.Tipo_Factura__c = orderOriginal.Tipo_Factura__c;
            cloneInversa.BillingStreet = orderOriginal.BillingStreet;
            cloneInversa.BillingPostalCode = orderOriginal.BillingPostalCode;
            cloneInversa.BillingCity = orderOriginal.BillingCity;
            cloneInversa.BillingState = orderOriginal.BillingState;
            cloneInversa.Costo_de_envio__c = 0;
            cloneInversa.base_finance_cost_amount__c = 0;
            cloneInversa.Pagos_acreditados__c = true;
            cloneInversa.AuthorizationCode__c = orderOriginal.AuthorizationCode__c;
            if (Test.isRunningTest()) {
                cloneInversa.Pricebook2Id = Test.getStandardPricebookId();
            }
            insert cloneInversa;
        }

        Map<String,String> resultIds = new Map<String,String>();
        resultIds.put('Order', clone.id);

        System.debug(clone.id);

        List<OrderItem> orderItemsCloned = new List<OrderItem>();
        Integer cont = 1;
        for (String product2Id : mapOrderItemsReplicas.keySet()){
            Map<String,String> mapReplicas = mapOrderItemsReplicas.get(product2Id);
            OrderItem newOrderItem = new OrderItem();
            newOrderItem.orderId = clone.id;
            newOrderItem.product2Id = product2Id;
            newOrderItem.quantity = Decimal.valueOf(mapReplicas.get('Quantity'));
            newOrderItem.UnitPrice = Decimal.valueOf(mapReplicas.get('UnitPrice'));
            newOrderItem.ListPrice = Decimal.valueOf(mapReplicas.get('UnitPrice'));
            newOrderItem.PricebookEntryId = mapReplicas.get('PricebookEntryId');
            
            newOrderItem.Talle__c = mapReplicas.get('Talle__c');
            newOrderItem.Talle_Friendly__c = mapReplicas.get('Talle_Friendly__c');
            newOrderItem.SKU__c = mapReplicas.get('SKU__c');
            newOrderItem.Description = mapReplicas.get('Name');
            
            newOrderItem.Unique_Id__c = 'ReplicaOrder'+clone.id+'_OrderItem'+cont++;
            orderItemsCloned.add(newOrderItem);
        }
        if (type == 'Cambio empleado') {
            for (String product2Id : mapOrderItemsOriginales.keySet()){
                Map<String,String> mapReplicas = mapOrderItemsOriginales.get(product2Id);
                OrderItem newOrderItem = new OrderItem();
                newOrderItem.orderId = clone.id;
                newOrderItem.product2Id = product2Id;
                newOrderItem.Devolucion_empleado__c = true;
                newOrderItem.quantity = Decimal.valueOf(mapReplicas.get('Quantity'));
                newOrderItem.UnitPrice = 0;
                newOrderItem.ListPrice = 0;
                if (Test.isRunningTest()) {
                    newOrderItem.ListPrice = Decimal.valueOf(mapReplicas.get('UnitPrice'));
                }
                newOrderItem.PricebookEntryId = mapReplicas.get('PricebookEntryId');
                
                newOrderItem.Talle__c = mapReplicas.get('Talle__c');
                newOrderItem.Talle_Friendly__c = mapReplicas.get('Talle_Friendly__c');
                newOrderItem.SKU__c = mapReplicas.get('SKU__c');
                newOrderItem.Description = mapReplicas.get('Name');
                
                newOrderItem.Unique_Id__c = 'ReplicaOrder'+clone.id+'_OrderItem'+cont++;
                orderItemsCloned.add(newOrderItem);
            }
        } else if (type == 'Cambio mano a mano') {
            for (String product2Id : mapOrderItemsOriginales.keySet()){
                Map<String,String> mapReplicas = mapOrderItemsOriginales.get(product2Id);
                OrderItem newOrderItem = new OrderItem();
                newOrderItem.orderId = cloneInversa.id;
                newOrderItem.product2Id = product2Id;
                newOrderItem.quantity = Decimal.valueOf(mapReplicas.get('Quantity'));
                newOrderItem.UnitPrice = Decimal.valueOf(mapReplicas.get('UnitPrice'));
                newOrderItem.ListPrice = Decimal.valueOf(mapReplicas.get('UnitPrice'));
                newOrderItem.PricebookEntryId = mapReplicas.get('PricebookEntryId');
                
                newOrderItem.Talle__c = mapReplicas.get('Talle__c');
                newOrderItem.Talle_Friendly__c = mapReplicas.get('Talle_Friendly__c');
                newOrderItem.SKU__c = mapReplicas.get('SKU__c');
                newOrderItem.Description = mapReplicas.get('Name');
                
                newOrderItem.Unique_Id__c = 'ReplicaOrder'+cloneInversa.id+'_OrderItem'+cont++;
                orderItemsCloned.add(newOrderItem);
            }
        }
        insert orderItemsCloned;

        if (bonificationType != null && bonificationType != '') {
            if (bonificationType != 'Cupón') {
                Bonificacion__c bonificacion = new Bonificacion__c();
                bonificacion.Order__c = clone.id;
                bonificacion.Discount_Amount__c = bonificationAmmount;
                bonificacion.Tipo__c = bonificationType;
                insert bonificacion;
                resultIds.put('Bonificacion__c', bonificacion.id);
            }
        }

        if ((type == 'Siniestro' || type == 'Reenvío') && orderOriginal.Pagos2__r.size() > 0 && paymentCopy > 0) {
            Pago__c pagoCopy = new Pago__c();
            pagoCopy.Orden__c = clone.id;
            pagoCopy.cuit__c = orderOriginal.Pagos2__r[0].cuit__c;
            pagoCopy.tipo_de_tarjeta_de_credito__c = orderOriginal.Pagos2__r[0].tipo_de_tarjeta_de_credito__c;
            pagoCopy.tipo_de_documento_mercado_pago__c = orderOriginal.Pagos2__r[0].tipo_de_documento_mercado_pago__c;
            pagoCopy.numero_de_documento_mercado_pago__c = orderOriginal.Pagos2__r[0].numero_de_documento_mercado_pago__c;
            pagoCopy.titular_tarjeta__c = orderOriginal.Pagos2__r[0].titular_tarjeta__c;
            pagoCopy.importe__c = paymentCopy;
            pagoCopy.cuotas__c = orderOriginal.Pagos2__r[0].cuotas__c;
            pagoCopy.Metodo_Pago__c = orderOriginal.Pagos2__r[0].Metodo_Pago__c;
            pagoCopy.Codigo_forma_de_pago__c = orderOriginal.Pagos2__r[0].Codigo_forma_de_pago__c;
            pagoCopy.Numero_de_operacion_Mercado_Pago__c = orderOriginal.Pagos2__r[0].Numero_de_operacion_Mercado_Pago__c;
            pagoCopy.Estado_Pago__c = 'Pendiente';
            insert pagoCopy;
        }
  
        if (paymentType != null && paymentType != '') {
            Pago__c pago = new Pago__c();
            pago.Orden__c = clone.id;
            pago.Metodo_Pago__c = paymentType;
            pago.Estado_Pago__c = paymentStatus;
            pago.Importe__c = paymentAmmount;
            pago.Numero_de_operacion_Mercado_Pago__c = paymentNumeroOperacion;
            pago.name = 'ReplicaOrder'+clone.id+'_Pago';
            insert pago;
            resultIds.put('Pago__c', Pago.id);
        }

        if (type == 'Siniestro') {
            if (clone.Sucursal_pickup__c == 'ML') {
                 // Obtener attachments del Order
                List<Attachment> attachments = [
                    SELECT Id, Name, Body, ContentType, Description, ParentId
                    FROM Attachment
                    WHERE ParentId = :clone.Original_Order__c
                    AND Name LIKE 'guia%'
                ];

                // Clonar los attachments para asignarlos a las nuevas guias
                List<Attachment> attachmentsNuevos = new List<Attachment>();
                for (Attachment a : attachments) {
                    Attachment nuevo = new Attachment();
                    nuevo.Body = a.Body;
                    nuevo.Name = a.Name;
                    nuevo.ContentType = a.ContentType;
                    nuevo.Description = a.Description;
                    nuevo.ParentId = clone.id;
                    attachmentsNuevos.add(nuevo);
                }
                if (!attachmentsNuevos.isEmpty()) {
                    insert attachmentsNuevos;
                }

                Guia__c newGuia = new Guia__c();
                newGuia.Name = 'Orden ' + clone.External_Id__c + '. Guia única';
                newGuia.Numero_de_seguimiento__c = clone.Num_de_Seguimiento_de_ML__c;
                newGuia.Order__c = clone.Id;
                insert newGuia;
            }
        }
            
        if (originalStock) {
            clone.Status = Constants.ORDER_STATUS_COMPLETED;
            clone.status_flag__c = true;
        } else if (esDevolucionProducto) {
            clone.Status = Constants.ORDER_STATUS_CHECK_PAYMENT;
            clone.status_flag__c = true;
        } else if (esInversa) {
            clone.Status = Constants.ORDER_STATUS_ENVIO_ETIQUETAS;
            clone.status_flag__c = true;
        } else if (type == 'Cambio Empleado') {
            clone.Status = Constants.ORDER_STATUS_CHECK_PAYMENT;
            clone.status_flag__c = true;
        } else {
            clone.Status = Constants.ORDER_STATUS_REQUEST_STOCK;
            clone.status_flag__c = true;
        }
        update clone;
        
        return resultIds;
    }

    /**
     * @description Get all active logistic operators for shipping method selection
     * @return List of operators in format suitable for lightning-combobox
     */
    @AuraEnabled(cacheable=true)
    public static List<Map<String, String>> getOperadoresLogisticos() {
        List<Map<String, String>> operadores = new List<Map<String, String>>();
        
        try {
            List<Operador_Logistico__c> operadoresList = [
                SELECT Id, Name 
                FROM Operador_Logistico__c 
                // WHERE IsActive__c = true
                ORDER BY Name
            ];
            
            for (Operador_Logistico__c op : operadoresList) {
                Map<String, String> operador = new Map<String, String>();
                operador.put('label', op.Name);
                operador.put('value', op.Id);
                operadores.add(operador);
            }
            
        } catch (Exception e) {
            throw new AuraHandledException('Error retrieving operadores logísticos: ' + e.getMessage());
        }
        
        return operadores;
    }

    @AuraEnabled(cacheable = true)
    public static Object getSKUDevolucion() {
        List<Product2> productoDevolucion = [
            SELECT Id, ProductCode, Name, sku__c, Description, Talle__c, Talle_Friendly__c, Stock__c,
            (SELECT UnitPrice FROM PricebookEntries WHERE Pricebook2Id = :Constants.getStandardPricebookId())
            FROM Product2 WHERE sku__c = :Constants.SKU_DEVOLUCIONUSADO];

        return productoDevolucion.size() > 0 ? productoDevolucion[0] : null;
    }

    /**
     * @description Obtiene el producto con SKU 99904ACCESORFALU para artículos faltantes en reenvíos
     * @return Product2 con sus detalles y precio
     */
    @AuraEnabled(cacheable = true)
    public static Object getSKUAccesorioFaltante() {
        List<Product2> productoAccesorioFaltante = [
            SELECT Id, ProductCode, Name, sku__c, Description, Talle__c, Talle_Friendly__c, Stock__c,
            (SELECT UnitPrice FROM PricebookEntries WHERE Pricebook2Id = :Constants.getStandardPricebookId())
            FROM Product2 
            WHERE sku__c = '99904ACCESORFALU'
        ];

        return productoAccesorioFaltante.size() > 0 ? productoAccesorioFaltante[0] : null;
    }

    @AuraEnabled(cacheable = false)
    public static Map<String, String> getNuevoEnvio(String operadorABuscar){
        //para verificar que el envio recibido no sea null
        if (operadorABuscar == null) {
            throw new AuraHandledException('No se pudo obtener correctamente los datos del Operador Logístico.');
        }
        Map<String, String> returnMap = new Map<String, String>();
        List<Metodo_de_envio__c> metodoEnvio = [
            SELECT Id, Name
            FROM Metodo_de_envio__c
            WHERE Operador_Logistico__c = :operadorABuscar
            AND (
                Servicio_de_Operador__r.Name LIKE '%interna%'
                OR
                Servicio_de_Operador__r.Name LIKE '%domicilio%'
            )
            AND (NOT Servicio_de_Operador__r.Name LIKE '%olecta%')
            WITH USER_MODE
        ];
        returnMap.put('value', metodoEnvio[0].Id);
        returnMap.put('label', metodoEnvio[0].Name);
        return returnMap;
    }

    @AuraEnabled(cacheable = false)
    public static Map<String, String> getNuevoEnvioRetiro(String operadorABuscar){
        //para verificar que el envio recibido no sea null
        if (operadorABuscar == null) {
            throw new AuraHandledException('No se pudo obtener correctamente los datos de la sucursal.');
        }
        Map<String, String> returnMap = new Map<String, String>();
        List<Metodo_de_envio__c> metodoEnvio = [
            SELECT Id, Name
            FROM Metodo_de_envio__c
            WHERE Operador_Logistico__r.Api_name__c = :operadorABuscar
            AND (
                Servicio_de_Operador__r.Name LIKE '%interna%'
                OR
                Servicio_de_Operador__r.Name LIKE '%retiro%'
            )
            WITH USER_MODE
        ];
        returnMap.put('value', metodoEnvio[0].Id);
        returnMap.put('label', metodoEnvio[0].Name);
        return returnMap;
    }

    @AuraEnabled(cacheable = false)
    public static Map<String, String> getNuevoEnvioCambioManoMano(String operadorABuscar){
        //para verificar que el envio recibido no sea null
        if (operadorABuscar == null) {
            throw new AuraHandledException('No se pudo obtener correctamente los datos del operador.');
        }
        Map<String, String> returnMap = new Map<String, String>();
        List<Metodo_de_envio__c> metodoEnvio = [
            SELECT Id, Name
            FROM Metodo_de_envio__c
            WHERE Operador_Logistico__r.Api_name__c = :operadorABuscar
            AND Servicio_de_Operador__r.Name LIKE '%mano%'
            WITH USER_MODE
        ];
        returnMap.put('value', metodoEnvio[0].Id);
        returnMap.put('label', metodoEnvio[0].Name);
        return returnMap;
    }

    @AuraEnabled(cacheable = false)
    public static Map<String, String> getNuevoEnvioRetiroInversa(String operadorABuscar, Boolean esDomicilio) {
        //para verificar que el envio recibido no sea null
        if (operadorABuscar == null) {
            throw new AuraHandledException('No se pudo obtener correctamente los datos de la sucursal.');
        }
        Map<String, String> returnMap = new Map<String, String>();
        List<Metodo_de_envio__c> metodoEnvio;
        if (esDomicilio) {
            metodoEnvio = [
                SELECT Id, Name
                FROM Metodo_de_envio__c
                WHERE Operador_Logistico__r.Api_name__c = :operadorABuscar
                AND Servicio_de_Operador__r.Name LIKE '%olecta por domicilio%'
            ];
        } else {
            metodoEnvio = [
                SELECT Id, Name
                FROM Metodo_de_envio__c
                WHERE Operador_Logistico__r.Api_name__c = :operadorABuscar
                AND (
                    Servicio_de_Operador__r.Name LIKE '%interna%'
                    OR
                    Servicio_de_Operador__r.Name LIKE '%inversa%'
                    OR
                    Servicio_de_Operador__r.Name LIKE '%olecta por sucursal'
                    )
                WITH USER_MODE
            ];
        }
        returnMap.put('value', metodoEnvio[0].Id);
        returnMap.put('label', metodoEnvio[0].Name);
        return returnMap;
    }

}
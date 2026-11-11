from comun import dynamodb, NO_AUTORIZADO, respuesta, autenticar

def lambda_handler(event, context):
    # Proteger el Lambda
    sesion = autenticar(event)
    if not sesion:
        return NO_AUTORIZADO
    tenant_id = sesion['tenant_id']
    # Entrada (json)
    portafolio_id = (event.get('body') or {}).get('portafolio_id')
    if not portafolio_id:
        return respuesta(400, mensaje='Falta portafolio_id')
    # Proceso
    r = dynamodb.Table('t_portafolios').get_item(
        Key={'tenant_id': tenant_id, 'portafolio_id': portafolio_id})
    if 'Item' not in r:
        return respuesta(404, mensaje='El portafolio no existe')
    # Cuantos proyectos tiene (contador de t_resumen_tenant)
    resumen = dynamodb.Table('t_resumen_tenant').get_item(
        Key={'tenant_id': tenant_id, 'clave': f'PORT#{portafolio_id}'})
    total = resumen.get('Item', {}).get('total_proyectos', 0)
    # Salida (json)
    return respuesta(200, portafolio=r['Item'], total_proyectos=total)

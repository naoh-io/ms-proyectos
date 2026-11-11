from comun import dynamodb, NO_AUTORIZADO, respuesta, autenticar

def lambda_handler(event, context):
    # Proteger el Lambda
    sesion = autenticar(event)
    if not sesion:
        return NO_AUTORIZADO
    tenant_id = sesion['tenant_id']
    # Proceso: un solo get_item, los contadores ya estan calculados
    r = dynamodb.Table('t_resumen_tenant').get_item(
        Key={'tenant_id': tenant_id, 'clave': 'RESUMEN'})
    resumen = r.get('Item', {'tenant_id': tenant_id, 'clave': 'RESUMEN'})
    # Salida (json)
    return respuesta(200, resumen=resumen)

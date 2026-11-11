from comun import dynamodb, NO_AUTORIZADO, respuesta, autenticar, ajustar_resumen

def lambda_handler(event, context):
    # Proteger el Lambda
    sesion = autenticar(event)
    if not sesion:
        return NO_AUTORIZADO
    tenant_id = sesion['tenant_id']
    # Entrada (json)
    proyecto_id = (event.get('body') or {}).get('proyecto_id')
    if not proyecto_id:
        return respuesta(400, mensaje='Falta proyecto_id')
    # Proceso
    try:
        r = dynamodb.Table('t_proyectos').delete_item(
            Key={'tenant_id': tenant_id, 'proyecto_id': proyecto_id},
            ConditionExpression='attribute_exists(tenant_id)',
            ReturnValues='ALL_OLD'
        )
    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        return respuesta(404, mensaje='El proyecto no existe')
    viejo = r['Attributes']
    # Contadores del dashboard
    ajustar_resumen(tenant_id, 'RESUMEN',
                    {'total_proyectos': -1, f"proy_{viejo.get('estado')}": -1})
    if viejo.get('portafolio_id'):
        ajustar_resumen(tenant_id, f"PORT#{viejo['portafolio_id']}", {'total_proyectos': -1})
    # Salida (json)
    return respuesta(200, mensaje='Proyecto eliminado')

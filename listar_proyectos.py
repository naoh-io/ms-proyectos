from boto3.dynamodb.conditions import Key
from comun import dynamodb, NO_AUTORIZADO, respuesta, autenticar, parametros_lista

def lambda_handler(event, context):
    # Proteger el Lambda
    sesion = autenticar(event)
    if not sesion:
        return NO_AUTORIZADO
    tenant_id = sesion['tenant_id']
    # Entrada (json): todos los campos son opcionales
    body = event.get('body') or {}
    # Proceso
    tabla = dynamodb.Table('t_proyectos')
    kwargs = parametros_lista(body)
    if body.get('estado'):
        kwargs['IndexName'] = 'gsi_estado'
        kwargs['KeyConditionExpression'] = Key('tenant_id').eq(tenant_id) & Key('estado').eq(body['estado'])
    elif body.get('portafolio_id'):
        kwargs['IndexName'] = 'gsi_portafolio'
        kwargs['KeyConditionExpression'] = Key('tenant_id').eq(tenant_id) & Key('portafolio_id').eq(body['portafolio_id'])
    elif body.get('fecha_desde') or body.get('fecha_hasta'):
        desde = body.get('fecha_desde', '0000-01-01')
        hasta = body.get('fecha_hasta', '9999-12-31')
        kwargs['IndexName'] = 'gsi_fecha'
        kwargs['KeyConditionExpression'] = Key('tenant_id').eq(tenant_id) & Key('fecha_fin').between(desde, hasta)
    else:
        kwargs['KeyConditionExpression'] = Key('tenant_id').eq(tenant_id)
    r = tabla.query(**kwargs)
    # Salida (json)
    return respuesta(200, items=r['Items'], count=r['Count'],
                     last_key=r.get('LastEvaluatedKey'))

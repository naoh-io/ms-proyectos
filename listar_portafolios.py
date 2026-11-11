from boto3.dynamodb.conditions import Key
from comun import dynamodb, NO_AUTORIZADO, respuesta, autenticar, parametros_lista

def lambda_handler(event, context):
    # Proteger el Lambda
    sesion = autenticar(event)
    if not sesion:
        return NO_AUTORIZADO
    tenant_id = sesion['tenant_id']
    # Entrada (json): limit y last_key opcionales
    body = event.get('body') or {}
    # Proceso
    kwargs = parametros_lista(body)
    r = dynamodb.Table('t_portafolios').query(
        KeyConditionExpression=Key('tenant_id').eq(tenant_id), **kwargs)
    # Salida (json)
    return respuesta(200, items=r['Items'], count=r['Count'],
                     last_key=r.get('LastEvaluatedKey'))

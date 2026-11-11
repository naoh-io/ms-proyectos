import uuid
from datetime import datetime
from comun import dynamodb, NO_AUTORIZADO, respuesta, autenticar

def lambda_handler(event, context):
    # Proteger el Lambda
    sesion = autenticar(event)
    if not sesion:
        return NO_AUTORIZADO
    tenant_id = sesion['tenant_id']
    # Entrada (json)
    body = event.get('body') or {}
    nombre = body.get('nombre')
    if not nombre:
        return respuesta(400, mensaje='Falta nombre')
    # Proceso
    portafolio = {
        'tenant_id': tenant_id,
        'portafolio_id': f'POR-{tenant_id}-{uuid.uuid4().hex[:8]}',
        'nombre': nombre,
        'descripcion': body.get('descripcion', ''),
        'creado_en': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    dynamodb.Table('t_portafolios').put_item(
        Item=portafolio, ConditionExpression='attribute_not_exists(tenant_id)')
    # Salida (json)
    return respuesta(200, portafolio=portafolio)

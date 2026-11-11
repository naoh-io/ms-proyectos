from comun import dynamodb, NO_AUTORIZADO, respuesta, autenticar

CAMPOS = ['nombre', 'descripcion']

def lambda_handler(event, context):
    # Proteger el Lambda
    sesion = autenticar(event)
    if not sesion:
        return NO_AUTORIZADO
    tenant_id = sesion['tenant_id']
    # Entrada (json)
    body = event.get('body') or {}
    portafolio_id = body.get('portafolio_id')
    cambios = {c: body[c] for c in CAMPOS if body.get(c)}
    if not portafolio_id or not cambios:
        return respuesta(400, mensaje='Falta portafolio_id o algun campo a modificar')
    # Proceso
    nombres, valores, partes = {}, {}, []
    for i, (campo, valor) in enumerate(cambios.items()):
        nombres[f'#c{i}'] = campo
        valores[f':v{i}'] = valor
        partes.append(f'#c{i} = :v{i}')
    try:
        r = dynamodb.Table('t_portafolios').update_item(
            Key={'tenant_id': tenant_id, 'portafolio_id': portafolio_id},
            UpdateExpression='SET ' + ', '.join(partes),
            ConditionExpression='attribute_exists(tenant_id)',
            ExpressionAttributeNames=nombres,
            ExpressionAttributeValues=valores,
            ReturnValues='ALL_NEW'
        )
    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        return respuesta(404, mensaje='El portafolio no existe')
    # Salida (json)
    return respuesta(200, portafolio=r['Attributes'])

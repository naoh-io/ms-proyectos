# Lambda Portafolios (ms-proyectos). Una sola Lambda atiende varios endpoints.
# API Gateway (integration: lambda) manda en "requestPath" la ruta del recurso.
import uuid
from boto3.dynamodb.conditions import Key
from comun import dynamodb, NO_AUTORIZADO, respuesta, autenticar, parametros_lista
from datetime import datetime


def crear_portafolio(event, context):
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


def listar_portafolios(event, context):
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


def buscar_portafolio(event, context):
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


CAMPOS = ['nombre', 'descripcion']


def modificar_portafolio(event, context):
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


def obtener_resumen(event, context):
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


RUTAS = {
    '/portafolios/crear': crear_portafolio,
    '/portafolios/listar': listar_portafolios,
    '/portafolios/buscar': buscar_portafolio,
    '/portafolios/modificar': modificar_portafolio,
    '/resumen/obtener': obtener_resumen,
}

def lambda_handler(event, context):
    ruta = (event or {}).get('requestPath')
    funcion = RUTAS.get(ruta)
    if funcion is None:
        return {'statusCode': 404, 'mensaje': 'Ruta no encontrada: %s' % ruta}
    return funcion(event, context)

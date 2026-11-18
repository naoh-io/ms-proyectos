# Lambda Proyectos (ms-proyectos). Una sola Lambda atiende varios endpoints.
# API Gateway (integration: lambda) manda en "requestPath" la ruta del recurso.
import os
import uuid
from boto3.dynamodb.conditions import Key, Attr
from comun import dynamodb, ESTADOS, NO_AUTORIZADO, respuesta, autenticar, ajustar_resumen, publicar, parametros_lista
from datetime import datetime


def crear_proyecto(event, context):
    # Proteger el Lambda
    sesion = autenticar(event)
    if not sesion:
        return NO_AUTORIZADO
    tenant_id = sesion['tenant_id']
    # Entrada (json)
    body = event.get('body') or {}
    nombre = body.get('nombre')
    estado = body.get('estado', 'PLANIFICADO')
    portafolio_id = body.get('portafolio_id')
    if not nombre or estado not in ESTADOS:
        return respuesta(400, mensaje='Falta nombre o el estado no es valido: ' + ', '.join(ESTADOS))
    # Proceso
    if portafolio_id:
        r = dynamodb.Table('t_portafolios').get_item(
            Key={'tenant_id': tenant_id, 'portafolio_id': portafolio_id})
        if 'Item' not in r:
            return respuesta(404, mensaje='El portafolio no existe')
    proyecto_id = f'PRY-{tenant_id}-{uuid.uuid4().hex[:8]}'
    proyecto = {
        'tenant_id': tenant_id,
        'proyecto_id': proyecto_id,
        'nombre': nombre,
        'descripcion': body.get('descripcion', ''),
        'estado': estado,
        'prioridad': 'MEDIA',
        'avance_pct': 0,
        'tareas_total': 0,
        'tareas_completadas': 0,
        'estado_presupuesto': 'NORMAL',
        'creado_en': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    if portafolio_id:
        proyecto['portafolio_id'] = portafolio_id
    if body.get('fecha_fin'):
        proyecto['fecha_fin'] = body['fecha_fin']
    dynamodb.Table('t_proyectos').put_item(
        Item=proyecto, ConditionExpression='attribute_not_exists(tenant_id)')
    # Contadores del dashboard
    ajustar_resumen(tenant_id, 'RESUMEN', {'total_proyectos': 1, f'proy_{estado}': 1})
    if portafolio_id:
        ajustar_resumen(tenant_id, f'PORT#{portafolio_id}', {'total_proyectos': 1})
    # Evento para Priorizacion
    publicar(os.environ['TOPIC_PROYECTOS_ARN'], 'ProyectoCreado', tenant_id,
             {'proyecto_id': proyecto_id, 'portafolio_id': portafolio_id})
    # Salida (json)
    return respuesta(200, proyecto=proyecto)


def listar_proyectos(event, context):
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
        # Estado + portafolio a la vez: el portafolio se aplica como filtro sobre el indice de estado
        if body.get('portafolio_id'):
            kwargs['FilterExpression'] = Attr('portafolio_id').eq(body['portafolio_id'])
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


CAMPOS = ['nombre', 'descripcion', 'estado', 'portafolio_id', 'fecha_fin']


def modificar_proyecto(event, context):
    # Proteger el Lambda
    sesion = autenticar(event)
    if not sesion:
        return NO_AUTORIZADO
    tenant_id = sesion['tenant_id']
    # Entrada (json)
    body = event.get('body') or {}
    proyecto_id = body.get('proyecto_id')
    cambios = {c: body[c] for c in CAMPOS if body.get(c)}
    if not proyecto_id or not cambios:
        return respuesta(400, mensaje='Falta proyecto_id o algun campo a modificar')
    if 'estado' in cambios and cambios['estado'] not in ESTADOS:
        return respuesta(400, mensaje='Estado no valido: ' + ', '.join(ESTADOS))
    # Proceso
    if 'portafolio_id' in cambios:
        r = dynamodb.Table('t_portafolios').get_item(
            Key={'tenant_id': tenant_id, 'portafolio_id': cambios['portafolio_id']})
        if 'Item' not in r:
            return respuesta(404, mensaje='El portafolio no existe')
    nombres, valores, partes = {}, {}, []
    for i, (campo, valor) in enumerate(cambios.items()):
        nombres[f'#c{i}'] = campo
        valores[f':v{i}'] = valor
        partes.append(f'#c{i} = :v{i}')
    tabla = dynamodb.Table('t_proyectos')
    try:
        r = tabla.update_item(
            Key={'tenant_id': tenant_id, 'proyecto_id': proyecto_id},
            UpdateExpression='SET ' + ', '.join(partes),
            ConditionExpression='attribute_exists(tenant_id)',
            ExpressionAttributeNames=nombres,
            ExpressionAttributeValues=valores,
            ReturnValues='ALL_OLD'
        )
    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        return respuesta(404, mensaje='El proyecto no existe')
    viejo = r['Attributes']
    # Contadores del dashboard
    if 'estado' in cambios and cambios['estado'] != viejo.get('estado'):
        ajustar_resumen(tenant_id, 'RESUMEN',
                        {f"proy_{viejo.get('estado')}": -1, f"proy_{cambios['estado']}": 1})
    if 'portafolio_id' in cambios and cambios['portafolio_id'] != viejo.get('portafolio_id'):
        if viejo.get('portafolio_id'):
            ajustar_resumen(tenant_id, f"PORT#{viejo['portafolio_id']}", {'total_proyectos': -1})
        ajustar_resumen(tenant_id, f"PORT#{cambios['portafolio_id']}", {'total_proyectos': 1})
    # Salida (json)
    return respuesta(200, proyecto={**viejo, **cambios})


def eliminar_proyecto(event, context):
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


RUTAS = {
    '/proyectos/crear': crear_proyecto,
    '/proyectos/listar': listar_proyectos,
    '/proyectos/modificar': modificar_proyecto,
    '/proyectos/eliminar': eliminar_proyecto,
}

def lambda_handler(event, context):
    ruta = (event or {}).get('requestPath')
    funcion = RUTAS.get(ruta)
    if funcion is None:
        return {'statusCode': 404, 'mensaje': 'Ruta no encontrada: %s' % ruta}
    return funcion(event, context)

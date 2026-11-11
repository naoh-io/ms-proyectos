import os
import uuid
from datetime import datetime
from comun import (dynamodb, ESTADOS, NO_AUTORIZADO, respuesta, autenticar,
                   ajustar_resumen, publicar)

def lambda_handler(event, context):
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

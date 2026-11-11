import json
from comun import dynamodb, ajustar_resumen

tabla = dynamodb.Table('t_proyectos')


def actualizar_avance(tenant_id, proyecto_id, delta_total, delta_completadas):
    """Suma a los contadores del proyecto y recalcula avance_pct."""
    try:
        r = tabla.update_item(
            Key={'tenant_id': tenant_id, 'proyecto_id': proyecto_id},
            UpdateExpression='ADD tareas_total :t, tareas_completadas :c',
            ConditionExpression='attribute_exists(tenant_id)',
            ExpressionAttributeValues={':t': delta_total, ':c': delta_completadas},
            ReturnValues='ALL_NEW'
        )
    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        print('Proyecto no existe, evento ignorado:', proyecto_id)
        return
    total = int(r['Attributes']['tareas_total'])
    completadas = int(r['Attributes']['tareas_completadas'])
    avance = round(100 * completadas / total) if total else 0
    tabla.update_item(
        Key={'tenant_id': tenant_id, 'proyecto_id': proyecto_id},
        UpdateExpression='SET avance_pct = :a',
        ExpressionAttributeValues={':a': avance}
    )
    ajustar_resumen(tenant_id, 'RESUMEN',
                    {'tareas_total': delta_total, 'tareas_completadas': delta_completadas})


def lambda_handler(event, context):
    # Entrada: mensajes de SQS; el cuerpo es el sobre de SNS y 'Message' es nuestro JSON
    for registro in event['Records']:
        sobre = json.loads(registro['body'])
        msg = json.loads(sobre['Message'])
        tipo = msg.get('tipo_evento')
        tenant_id = msg['tenant_id']
        proyecto_id = msg.get('proyecto_id')
        print('Evento recibido:', tipo, tenant_id, proyecto_id)
        # Proceso
        if tipo == 'TareaCreada':
            actualizar_avance(tenant_id, proyecto_id, 1, 0)
        elif tipo == 'TareaCompletada':
            actualizar_avance(tenant_id, proyecto_id, 0, 1)
        elif tipo == 'PresupuestoExcedido':
            try:
                r = tabla.update_item(
                    Key={'tenant_id': tenant_id, 'proyecto_id': proyecto_id},
                    UpdateExpression='SET estado_presupuesto = :e',
                    ConditionExpression='attribute_exists(tenant_id)',
                    ExpressionAttributeValues={':e': 'EXCEDIDO'},
                    ReturnValues='ALL_OLD'
                )
                if r['Attributes'].get('estado_presupuesto') != 'EXCEDIDO':
                    ajustar_resumen(tenant_id, 'RESUMEN', {'presupuestos_excedidos': 1})
            except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
                print('Proyecto no existe, evento ignorado:', proyecto_id)
        elif tipo == 'PuntajeActualizado':
            try:
                tabla.update_item(
                    Key={'tenant_id': tenant_id, 'proyecto_id': proyecto_id},
                    UpdateExpression='SET prioridad = :p',
                    ConditionExpression='attribute_exists(tenant_id)',
                    ExpressionAttributeValues={':p': msg['prioridad']}
                )
            except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
                print('Proyecto no existe, evento ignorado:', proyecto_id)
        else:
            print('Tipo de evento ignorado:', tipo)
    # Salida
    return {'statusCode': 200}

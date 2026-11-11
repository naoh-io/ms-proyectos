from comun import (dynamodb, ESTADOS, NO_AUTORIZADO, respuesta, autenticar,
                   ajustar_resumen)

# prioridad, avance_pct y contadores NO se modifican aqui: los actualizan los eventos
CAMPOS = ['nombre', 'descripcion', 'estado', 'portafolio_id', 'fecha_fin']

def lambda_handler(event, context):
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

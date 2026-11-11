import json
import boto3
from decimal import Decimal

dynamodb = boto3.resource('dynamodb')
_lambda = boto3.client('lambda')
_sns = boto3.client('sns')

ESTADOS = ('PLANIFICADO', 'EN_CURSO', 'COMPLETADO')

NO_AUTORIZADO = {'statusCode': 403, 'mensaje': 'Forbidden - Acceso No Autorizado'}


def limpiar(obj):
    """DynamoDB devuelve Decimal; el JSON de salida necesita int/float."""
    if isinstance(obj, Decimal):
        return int(obj) if obj == obj.to_integral_value() else float(obj)
    if isinstance(obj, dict):
        return {k: limpiar(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [limpiar(v) for v in obj]
    return obj


def respuesta(codigo, **campos):
    return {'statusCode': codigo, **limpiar(campos)}


def autenticar(event):
    """Valida el token con ValidarTokenAcceso.
    Devuelve {'tenant_id', 'usuario_id', 'rol', ...} o None si no es valido."""
    headers = {k.lower(): v for k, v in (event.get('headers') or {}).items()}
    token = headers.get('authorization')
    if not token:
        return None
    r = _lambda.invoke(FunctionName='ValidarTokenAcceso',
                       InvocationType='RequestResponse',
                       Payload=json.dumps({'token': token}))
    datos = json.loads(r['Payload'].read())
    if datos.get('statusCode') != 200:
        return None
    return datos


def parametros_lista(body):
    """Limit y ExclusiveStartKey para paginar un Query."""
    try:
        limit = max(1, min(int(body.get('limit', 20)), 100))
    except (TypeError, ValueError):
        limit = 20
    kwargs = {'Limit': limit}
    if body.get('last_key'):
        kwargs['ExclusiveStartKey'] = body['last_key']
    return kwargs


def ajustar_resumen(tenant_id, clave, deltas):
    """Suma (o resta) contadores en t_resumen_tenant con ADD."""
    deltas = {k: v for k, v in deltas.items() if v}
    if not deltas:
        return
    nombres, valores, partes = {}, {}, []
    for i, (campo, delta) in enumerate(deltas.items()):
        nombres[f'#c{i}'] = campo
        valores[f':d{i}'] = delta
        partes.append(f'#c{i} :d{i}')
    dynamodb.Table('t_resumen_tenant').update_item(
        Key={'tenant_id': tenant_id, 'clave': clave},
        UpdateExpression='ADD ' + ', '.join(partes),
        ExpressionAttributeNames=nombres,
        ExpressionAttributeValues=valores
    )


def publicar(topic_arn, tipo_evento, tenant_id, datos):
    """Publica un evento en SNS. Si falla, no tumba la operacion principal."""
    mensaje = {'tipo_evento': tipo_evento, 'tenant_id': tenant_id, **datos}
    try:
        _sns.publish(
            TopicArn=topic_arn,
            Message=json.dumps(mensaje),
            MessageAttributes={
                'tipo_evento': {'DataType': 'String', 'StringValue': tipo_evento},
                'tenant_id': {'DataType': 'String', 'StringValue': tenant_id}
            }
        )
    except Exception as e:
        print('Error publicando evento:', str(e))

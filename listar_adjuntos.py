import os
import boto3
from botocore.config import Config
from boto3.dynamodb.conditions import Key
from comun import dynamodb, NO_AUTORIZADO, respuesta, autenticar

s3 = boto3.client('s3', region_name=os.environ['AWS_REGION'],
                  config=Config(signature_version='s3v4'))

def lambda_handler(event, context):
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
    r = dynamodb.Table('t_adjuntos').query(
        IndexName='gsi_proyecto',
        KeyConditionExpression=Key('tenant_id').eq(tenant_id) & Key('proyecto_id').eq(proyecto_id)
    )
    items = r['Items']
    for item in items:
        item['url_descarga'] = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': os.environ['BUCKET_ADJUNTOS'], 'Key': item['clave_s3']},
            ExpiresIn=300
        )
    # Salida (json)
    return respuesta(200, items=items, count=len(items))

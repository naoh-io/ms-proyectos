import os
import re
import uuid
import boto3
from botocore.config import Config
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
    body = event.get('body') or {}
    proyecto_id = body.get('proyecto_id')
    nombre_archivo = body.get('nombre_archivo')
    if not proyecto_id or not nombre_archivo:
        return respuesta(400, mensaje='Falta proyecto_id o nombre_archivo')
    # Proceso: el proyecto debe existir en este tenant
    r = dynamodb.Table('t_proyectos').get_item(
        Key={'tenant_id': tenant_id, 'proyecto_id': proyecto_id})
    if 'Item' not in r:
        return respuesta(404, mensaje='El proyecto no existe')
    nombre_limpio = re.sub(r'[^A-Za-z0-9._-]', '_', os.path.basename(nombre_archivo))
    clave = f'adjuntos/{tenant_id}/{proyecto_id}/{uuid.uuid4().hex[:8]}_{nombre_limpio}'
    url = s3.generate_presigned_url(
        'put_object',
        Params={'Bucket': os.environ['BUCKET_ADJUNTOS'], 'Key': clave},
        ExpiresIn=300
    )
    # Salida (json): el navegador sube el archivo con PUT a esta url
    return respuesta(200, url=url, clave=clave, expira_en_segundos=300)

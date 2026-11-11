import hashlib
import urllib.parse
from datetime import datetime
from comun import dynamodb

def lambda_handler(event, context):
    # Entrada: evento de S3 (ObjectCreated). La clave es adjuntos/{tenant}/{proyecto}/{archivo}
    tabla = dynamodb.Table('t_adjuntos')
    for registro in event['Records']:
        clave = urllib.parse.unquote_plus(registro['s3']['object']['key'])
        partes = clave.split('/')
        if len(partes) != 4 or partes[0] != 'adjuntos':
            print('Clave ignorada:', clave)
            continue
        _, tenant_id, proyecto_id, archivo = partes
        # Proceso: el adjunto_id sale de la clave, asi un evento repetido no duplica
        tabla.put_item(Item={
            'tenant_id': tenant_id,
            'adjunto_id': 'ADJ-' + hashlib.sha1(clave.encode()).hexdigest()[:16],
            'proyecto_id': proyecto_id,
            'clave_s3': clave,
            'nombre': archivo.split('_', 1)[-1],
            'tamano_bytes': registro['s3']['object'].get('size', 0),
            'subido_en': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    # Salida
    return {'statusCode': 200}

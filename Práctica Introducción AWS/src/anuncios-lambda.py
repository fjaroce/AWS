import json
import boto3
import uuid
import base64
from datetime import datetime, timedelta

#recursos AWS
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('AnunciosApp')
s3 = boto3.client('s3')

#config
DIAS_EXPIRACION = 30
BUCKET_IMAGENES = 'anuncios-app-imagenes'

def lambda_handler(event, context):
    #operaciones CRUD para anuncio
    method = event.get('httpMethod', 'GET')
    path = event.get('path', '')
    path_segments = path.split('/')
    
    #get id
    anuncio_id = path_segments[3] if len(path_segments) > 3 else None
    
    #si patch tiene comentarios, otra lambda
    if len(path_segments) > 4 and path_segments[4] == 'comentarios':
        return respuesta_error(400, 'Las operaciones de comentarios deben dirigirse a la Lambda de comentarios')
    #metodo ejecuión
    if method == 'GET':
        if path.rstrip('/') == '/api/anuncios':
            return listar_anuncios()
        elif anuncio_id:
            return obtener_anuncio(anuncio_id)
    elif method == 'POST':
        if path.rstrip('/') == '/api/anuncios':
            return crear_anuncio(event)
    

    return respuesta_error(404, 'Ruta no encontrada')

def respuesta_error(status_code, mensaje):
    #error
    return {
        'statusCode': status_code,
        'headers': get_cors_headers(),
        'body': json.dumps({'error': mensaje})
    }

def get_cors_headers():
    return {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'
    }

def listar_anuncios():
    #get de anuncios
    try:
        #@filtrar para no traer coments (solo se usa 1 tabla para todo)
        response = table.scan(
            FilterExpression="begins_with(PK, :pk_prefix) AND SK = :sk",
            ExpressionAttributeValues={
                ':pk_prefix': 'ANUNCIO#',
                ':sk': 'METADATA'
            }
        )
        
        #formteao de respuesta
        anuncios = []
        for item in response.get('Items', []):
            anuncio_id = item.get('PK').split('#')[1]
            anuncios.append({
                'id': anuncio_id,
                'titulo': item.get('titulo', ''),
                'descripcion': item.get('descripcion', ''),
                'creado': item.get('creado', ''),
                'usuario': item.get('usuario', 'Anónimo'),
                'expira': item.get('fecha_expiracion', ''),
                'imagenes': item.get('imagenes', [])
            })
        
        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': json.dumps({'anuncios': anuncios})
        }
    except Exception as e:
        print(f"Error al listar anuncios: {str(e)}")
        return respuesta_error(500, str(e))

def obtener_anuncio(anuncio_id):
    #get anuncio X
    try:
        
        if not anuncio_id:
            return respuesta_error(400, 'ID de anuncio no proporcionado')
        
        #traer info de X anuncio de dynamo
        response = table.get_item(
            Key={
                'PK': f'ANUNCIO#{anuncio_id}',
                'SK': 'METADATA'
            }
        )
        
        anuncio = response.get('Item')
        if not anuncio:
            return respuesta_error(404, 'Anuncio no encontrado')
        
        #format respuesta
        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'anuncio': {
                    'id': anuncio_id,
                    'titulo': anuncio.get('titulo', ''),
                    'descripcion': anuncio.get('descripcion', ''),
                    'imagenes': anuncio.get('imagenes', []),
                    'creado': anuncio.get('creado', ''),
                    'usuario': anuncio.get('usuario', 'Anónimo'),
                    'expira': anuncio.get('fecha_expiracion', '')
                }
            })
        }
    except Exception as e:
        print(f"Error al obtener anuncio: {str(e)}")
        return respuesta_error(500, str(e))

def procesar_imagen(imagen_base64, anuncio_id):
    #Guarda una imagen en S3 y devuelve su URL
    try:
        # Procesar el formato base64 y determinar extensión
        extension = "png"  # Por defecto
        
        # Si viene en formato "data:image/tipo;base64,contenido"
        if ";" in imagen_base64 and "," in imagen_base64:
            formato = imagen_base64.split(";")[0]
            if "/" in formato:
                extension = formato.split("/")[1]
            imagen_base64 = imagen_base64.split(",")[1]
        
        # Crear nombre único para el archivo
        nombre_archivo = f"{anuncio_id}/{uuid.uuid4()}.{extension}"
        
        # Decodificar imagen
        imagen_bytes = base64.b64decode(imagen_base64)
        
        # Subir a S3
        s3.put_object(
            Bucket=BUCKET_IMAGENES,
            Key=nombre_archivo,
            Body=imagen_bytes,
            ContentType=f'image/{extension}'
        )
        
        # Devolver URL de acceso
        return f"https://{BUCKET_IMAGENES}.s3.amazonaws.com/{nombre_archivo}"
    except Exception as e:
        print(f"Error al procesar imagen: {str(e)}")
        raise e

def crear_anuncio(event):
    #crear auncio con imagen
    try:
        #obtener datos d la peticon
        body = json.loads(event.get('body', '{}'))
        
        #datos obligatorios
        if not body.get('titulo') or not body.get('descripcion'):
            return respuesta_error(400, 'Título y descripción son obligatorios')
        
        #ia imagen es obligaria
        imagenes_base64 = body.get('imagenes', [])
        if not imagenes_base64:
            return respuesta_error(400, 'Se requiere al menos una imagen')
        
        #generar id
        anuncio_id = str(uuid.uuid4())
        ahora = datetime.now()
        fecha_expiracion = ahora + timedelta(days=DIAS_EXPIRACION)
        
        #procesar imagnen
        urls_imagenes = []
        for imagen_base64 in imagenes_base64:
            url = procesar_imagen(imagen_base64, anuncio_id)
            urls_imagenes.append(url)
        
        # Obtener información del usuario (si está autenticado)
        usuario = 'Anónimo'
        if 'requestContext' in event and 'authorizer' in event['requestContext']:
            claims = event['requestContext']['authorizer'].get('claims', {})
            usuario = claims.get('name', usuario)
        
        #registor para dynamo
        item = {
            'PK': f'ANUNCIO#{anuncio_id}',
            'SK': 'METADATA',
            'titulo': body.get('titulo'),
            'descripcion': body.get('descripcion'),
            'imagenes': urls_imagenes,
            'creado': ahora.isoformat(),
            'actualizado': ahora.isoformat(),
            'usuario': usuario,
            'fecha_expiracion': fecha_expiracion.isoformat(),
            'expiracion_ttl': int(fecha_expiracion.timestamp())
        }
        
        table.put_item(Item=item)
        
        return {
            'statusCode': 201,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'id': anuncio_id,
                'mensaje': 'Anuncio creado correctamente',
                'expira': fecha_expiracion.isoformat(),
                'imagenes': urls_imagenes
            })
        }
    except Exception as e:
        print(f"Error al crear anuncio: {str(e)}")
        return respuesta_error(500, str(e))
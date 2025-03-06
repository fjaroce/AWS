import json
import boto3
import uuid
from datetime import datetime

#recursos AWS
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('AnunciosApp')

def lambda_handler(event, context):
    #operaciones CRUD  para anuncios
    method = event.get('httpMethod', 'GET')
    path = event.get('path', '')
    path_segments = path.split('/')
    
    #check path
    if len(path_segments) <= 4 or path_segments[4] != 'comentarios':
        return respuesta_error(404, 'Ruta no encontrada. Esta Lambda maneja solo rutas /api/anuncios/{id}/comentarios')
    
    #get anuncio id
    anuncio_id = path_segments[3]
    
    #q aplica
    if method == 'GET':
        return listar_comentarios(anuncio_id)
    elif method == 'POST':
        return crear_comentario(event, anuncio_id)
    elif method == 'OPTIONS':
        # Manejo de pre-flight CORS
        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': '{}'
        }
    else:
        return respuesta_error(405, 'Método no permitido')

def respuesta_error(status_code, mensaje):
    #error
    return {
        'statusCode': status_code,
        'headers': get_cors_headers(),
        'body': json.dumps({'error': mensaje})
    }

def get_cors_headers():
    """Headers CORS para permitir acceso desde el frontend"""
    return {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'
    }

def verificar_anuncio(anuncio_id):
    if not anuncio_id:
        return False, respuesta_error(400, 'ID de anuncio no proporcionado')
    
    #get x anuncio from dinamo
    response = table.get_item(
        Key={
            'PK': f'ANUNCIO#{anuncio_id}',
            'SK': 'METADATA'
        }
    )
    
    if not response.get('Item'):
        return False, respuesta_error(404, 'Anuncio no encontrado')
    
    return True, None

def listar_comentarios(anuncio_id):
    #listar ocmentarios
    try:

        anuncio_existe, error_response = verificar_anuncio(anuncio_id)
        if not anuncio_existe:
            return error_response
        
        #check comentarios en dynamo
        result = table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
            ExpressionAttributeValues={
                ':pk': f'ANUNCIO#{anuncio_id}',
                ':sk_prefix': 'COMENTARIO#'
            }
        )
        
        #formatear respuesta
        comentarios = []
        for item in result.get('Items', []):
            comentario_id = item.get('SK').split('#')[1]
            comentarios.append({
                'id': comentario_id,
                'texto': item.get('texto', ''),
                'autor': item.get('autor', 'Anónimo'),
                'creado': item.get('creado', '')
            })
        
        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': json.dumps({'comentarios': comentarios})
        }
    except Exception as e:
        print(f"Error al listar comentarios: {str(e)}")
        return respuesta_error(500, f"Error interno: {str(e)}")

def crear_comentario(event, anuncio_id):
    #generar nuevco coment
    try:
        #tiene que asociarse a un anuncio
        anuncio_existe, error_response = verificar_anuncio(anuncio_id)
        if not anuncio_existe:
            return error_response
        
        #get datos de la json recibido
        try:
            body = json.loads(event.get('body', '{}'))
        except json.JSONDecodeError:
            return respuesta_error(400, 'Formato JSON inválido')
        
        #validar existencia
        texto = body.get('texto', '').strip()
        if not texto:
            return respuesta_error(400, 'El texto del comentario es obligatorio')
        
        #mtdata asoicada
        comentario_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        #determinar autor (anónimo o autenticado) (NO HA LLEGADO A IMPLEMENTARSE)
        autor = body.get('autor', 'Anónimo')
        if 'requestContext' in event and 'authorizer' in event['requestContext']:
            claims = event['requestContext']['authorizer'].get('claims', {})
            if 'name' in claims:
                autor = claims['name']
        
        #guardar comentario dynamo
        table.put_item(Item={
            'PK': f'ANUNCIO#{anuncio_id}',
            'SK': f'COMENTARIO#{comentario_id}',
            'texto': texto,
            'autor': autor,
            'creado': timestamp
        })
        
        return {
            'statusCode': 201,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'id': comentario_id,
                'mensaje': 'Comentario añadido correctamente'
            })
        }
    except Exception as e:
        print(f"Error al crear comentario: {str(e)}")
        return respuesta_error(500, f"Error interno: {str(e)}")
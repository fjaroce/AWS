# Manual de despliegue

La guía está dividida en componenetes de manera que se crean manera independiente y convergen en el funcionamiento final. Señalar que esta guía tiene aplicación exclusiva en el entorno de AWS, en mi caso particular, aplicado a la región de Irlanda.
##### S3:
1. Acceder a https://console.aws.amazon.com/s3/

2. Crear el Bucket S3 para Frontend 'anuncios-frontend-bck'(General purpose buckets).
    1. Dar nombre al bucket.
    2. Mantener la opción 'ACLs disabled (recommended)' para indicar que los objetos del bucket son propiedad de la cuenta y que el acceso se gestiona únicamente mediante las políticas propias del bucket.
    3. Descamarcar la opción 'Bloquear acceso público (configuración del bucket)' para permitir el acceso remoto al HTML contenido en él.
    4. Dejar en deshabilitado el versionado del bucket, si quisieramos versionar el frontend, sería una manera.
    5. Añadir la configuración CORS especificando  que permita solicitudes desde cualquier origuen, los métodos permitidos y un caché preflight de 3600 segundos.
    6. Subir el fichero index.html.

3. Crear el Bucket S3 para imágenes 'anuncios-app-imagenes' con la misma configuración del anterior (puede referenciarse).
    1. En esta ocación añadir configuración en el uso compartido de orígenes( CORS).
    2. Configurar la política del bucket para que permita el acceso público de solo lectura a todos los objetos contenidos.

##### API Gateway:
1. Acceder a https://console.aws.amazon.com/apigateway/

2. Crear un recurso con el nombre 'AnunciosAPI' que hará de API REST.

3. Crear la jerarquía de recursos, en este caso la implementada es: 
    ``` 
      /api
        /anuncios
          GET (lista todos los anuncios)
          POST (crea un nuevo anuncio)
          /{id}
            GET (obtiene un anuncio específico)
            /comentarios
              GET (lista comentarios de un anuncio)
              POST (añade un comentario a un anuncio)
     ```
4. Integrar la jerarquía con la lambda para establecer comunicación:
   ```
    /api/anuncios y /api/anuncios/{id} → anuncios-lambda
    /api/anuncios/{id}/comentarios → comentarios-lambda
   ```
   Para realizar la integración, además hay que configurarla como tipo 'Lambda Function' y seleccionar la lambda y región en la que se ubica.

5. Configurar el CORS, habilitar todos los orígenes (*) y acceso de métodos GET,POST y OPTIONS.

6. Habilitar la transformación de solicitudes/respuesta mediante las plantillas de mapeo.

7. Crear una etapa y desplegar la API.

8. El flujo de acceso consiste en que ell componente recibe una petición, identifica el recurso y el método  invoca a la lambda que ha sido sido mapeada pasandole los datos asociados a la solicitud. Por último recibe la respuesta de la lambda se la devuelve a l cliente.


##### Lambda:

1. Acceder a https://console.aws.amazon.com/lambda/

2. Crear "desde cero" y configurar la función.
   1. Añadirle el nombre 'anuncios-lambda'.
   2. Añadir el timpo de ejecución Python 3.13, arquitectura x86_64.
   3. Crear rol nuevo con permisos básicos (se edita más tarde).
   4. Crear lambda.

3. Una vez ha sido creada, eliminar el código que viene por defecto, pegar el contenido de /src/anuncios-lambda.py e implementar los cambios.

4. En Configuración/Desencadenadores añadir los puntos de enlace de la API 
  ```
    https://2quhnyhb9j.execute-api.eu-west-1.amazonaws.com/prod/api/anuncios  (GET)
    https://2quhnyhb9j.execute-api.eu-west-1.amazonaws.com/prod/api/anuncios  (POST)
    https://2quhnyhb9j.execute-api.eu-west-1.amazonaws.com/prod/api/anuncios/{id} (GET)
    https://2quhnyhb9j.execute-api.eu-west-1.amazonaws.com/prod/api (GET)
  ```
5. Configurar los permisos desde IAM:
   1. Adjuntar política AmazonDynamoDBFullAccess para que pueda acceder a DynamoDB.
   2. AmazonS3FullAccess para que pueda gestionar las imágenes.

6. Configurar la política de recursos, para que la API pueda hacer las llamadas.

7. Crear la lambda 'comentarios-lambda' replicando el punto 2 anterior.

8. Eliminar el código que viene predetermiando y añadir el de /src/comentarios-lambda.py

9. Agregar los desencadenadores
  ``` 
    https://2quhnyhb9j.execute-api.eu-west-1.amazonaws.com/prod/api/anuncios/{id}/comentarios (GET)
    https://2quhnyhb9j.execute-api.eu-west-1.amazonaws.com/prod/api/anuncios/{id}/comentarios (POST)
  ```
10. Añadir la política de recursos para que pueda ser invocada por la API.

##### Dynamo:

1.  Acceder a https://console.aws.amazon.com/dynamodb/.

2. Crear la tabla 'AnunciosApp' añadiendo 'PK' como clave partición y 'SK' como clave de ordenación

3. Seleccionar que la capacidad de lectura/escritura es bajo demanda que si lo necesita escale de maenra autónoma según el uso.

4. Habilitar Time-to-live (TTL) para que los anuncios expiren automáticamente (campo expiración TTL)

5. La estructura de datos se basa en una tabla:
    1. Anuncios:
    ```
    {
      "PK": "ANUNCIO#[id-único]",
      "SK": "METADATA",
      "titulo": "Título del anuncio",
      "descripcion": "Descripción detallada",
      "imagenes": ["https://bucket-s3/ruta-imagen1.jpg"],
      "creado": "2023-05-20T14:30:45.123Z",
      "actualizado": "2023-05-20T14:30:45.123Z",
      "usuario": "nombre-usuario", #no he llegado a implementar uso
      "fecha_expiracion": "2023-06-20T14:30:45.123Z",
      "expiracion_ttl": 1687271445
    }
    ```
    2. Comentarios 
    ```
        {
          "PK": "ANUNCIO#[mismo-id-anuncio]",
          "SK": "COMENTARIO#[id-comentario]",
          "texto": "Texto del comentario",
          "autor": "Autor", #no he llegado a implementar uso
          "creado": "2023-05-21T10:15:30.456Z"
        }
    ```

##### CloudWatch:
Por último, hacer referencia al apartado de observabilidad, que es necesario para el despliegue pues permite debuggear y conocer los errores que puedan surgir. Destacar que las funciones lambdas crean de manera automática los logs con el formato y que en el apartado de 'Métricas' pueden revisarse los datos de monitoreo.


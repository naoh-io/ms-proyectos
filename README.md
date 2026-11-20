# ms-proyectos

Microservicio de Proyectos y Portafolios del SaaS PPM (multi-tenant, serverless).

## Despliegue

1. Desplegar antes `ms-auth` (todas las Lambdas leen `t_tokens_acceso` directo).
2. `serverless deploy`

Crea: 6 Lambdas, 4 tablas DynamoDB, tema SNS `tema-proyectos`, cola SQS
`cola-proyectos-eventos` (+ DLQ) y el bucket S3 `ppm-adjuntos-<account id>`.

## Rutas (todas piden la cabecera `Authorization` con el token del login)

| Ruta | Lambda | Cuerpo |
| --- | --- | --- |
| POST /proyectos/crear | Proyectos (`proyectos.py`) | nombre, portafolio_id?, estado?, fecha_fin?, descripcion? |
| POST /proyectos/listar | Proyectos (`proyectos.py`) | estado?, portafolio_id?, fecha_desde?, fecha_hasta?, limit?, last_key? (estado y portafolio_id se pueden combinar) |
| POST /proyectos/buscar | BuscarProyecto | proyecto_id |
| PUT /proyectos/modificar | Proyectos (`proyectos.py`) | proyecto_id + nombre/descripcion/estado/portafolio_id/fecha_fin |
| DELETE /proyectos/eliminar | Proyectos (`proyectos.py`) | proyecto_id |
| POST /portafolios/crear | Portafolios (`portafolios.py`) | nombre, descripcion? |
| POST /portafolios/listar | Portafolios (`portafolios.py`) | limit?, last_key? |
| POST /portafolios/buscar | Portafolios (`portafolios.py`) | portafolio_id |
| PUT /portafolios/modificar | Portafolios (`portafolios.py`) | portafolio_id + nombre/descripcion |
| POST /adjuntos/url | Adjuntos (`adjuntos.py`) | proyecto_id, nombre_archivo |
| POST /adjuntos/listar | Adjuntos (`adjuntos.py`) | proyecto_id |
| POST /resumen/obtener | Portafolios (`portafolios.py`) | (vacio) |

Sin ruta: `RegistrarAdjunto` (lo dispara S3) y `ProcesarEventosProyectos` (lo dispara SQS).

Estados de proyecto: PLANIFICADO, EN_CURSO, COMPLETADO.
`prioridad`, `avance_pct`, `tareas_*` y `estado_presupuesto` los actualizan los eventos, no el CRUD.

## Pruebas rapidas (Postman)

1. Login en ms-auth: `POST /auth/login` -> copiar `token`.
2. Poner el token en la cabecera `Authorization`.
3. `POST /portafolios/crear` con `{"nombre": "Portafolio TI"}` -> copiar `portafolio_id`.
4. `POST /proyectos/crear` con `{"nombre": "Migracion a la nube", "portafolio_id": "<id>", "fecha_fin": "2026-12-15"}`.
5. `POST /proyectos/listar` con `{}`.
6. `POST /resumen/obtener` -> total_proyectos = 1.

## Subir un adjunto

1. `POST /adjuntos/url` con `{"proyecto_id": "<id>", "nombre_archivo": "plan.pdf"}`.
2. `PUT <url>` con el archivo en el body (Postman: Body > binary). Sin cabecera Authorization.
3. Esperar unos segundos y `POST /adjuntos/listar` con `{"proyecto_id": "<id>"}`.

## Suscripciones a eventos

Este stack solo crea el tema `tema-proyectos` y la cola `cola-proyectos-eventos` con su politica
(acepta mensajes de cualquier tema `tema-*` de la cuenta). Las suscripciones SNS -> SQS
las declara el microservicio que se despliega despues (Tareas, Presupuestos, Priorizacion).

## Estructura de Lambdas (6)

Una Lambda atiende varios endpoints: el codigo elige la funcion segun la ruta (`requestPath` de API Gateway).

- `proyectos.py` -> Lambda **Proyectos**: /proyectos/crear, /proyectos/listar, /proyectos/modificar, /proyectos/eliminar
- `portafolios.py` -> Lambda **Portafolios**: /portafolios/crear, /portafolios/listar, /portafolios/buscar, /portafolios/modificar, /resumen/obtener
- `adjuntos.py` -> Lambda **Adjuntos**: /adjuntos/url, /adjuntos/listar
- `buscar_proyecto.py` (BuscarProyecto, solo la usa el frontend), `registrar_adjunto.py` (trigger S3), `procesar_eventos_proyectos.py` (trigger SQS).

`comun.py` es codigo compartido (token, respuestas, helpers), no es una Lambda.

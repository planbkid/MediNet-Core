# Entorno local independiente de PAC

Continuidad comprobada el 30 de octubre de 2026. API disponible en
http://127.0.0.1:18081/docs. Se conserva el Compose de desarrollo sin cambios.

Continuación más reciente: [revisión de seguridad de imagen y preparación de
Docker Compose](seguridad-y-docker-compose.md). Podman verificado; Docker
revisado estáticamente. [Trivy ya se ejecutó con hallazgos](auditoria-trivy-2026-10-30/README.md);
sus correcciones y la ejecución Docker siguen pendientes.

## Herramientas y versiones ejecutadas

Host: Podman 5.8.7 rootless y `.venv/bin/podman-compose` 1.6.0.
Docker y Docker Compose no están instalados localmente; no se instalaron herramientas.
Dentro de la imagen: Python 3.14.7, FastAPI 0.149.0, Pydantic 2.14.1,
SQLAlchemy 2.1.6 y psycopg 3.3.6. PostgreSQL local: 18.6 (`postgres:18-alpine`).
`requirements.txt` no se modificó; sus paquetes se instalaron solo dentro de la imagen.

Las plantillas originales se conservaron. `Dockerfile.local` usa dos etapas y
Python slim para utilizar los wheels existentes de las versiones fijadas, sin
añadir compiladores ni cambiar dependencias. La etapa final usa UID/GID 10001.
`.dockerignore` permite únicamente requirements, app, migraciones, alembic.ini
y scripts/containers; excluye cachés, `.env*`, `.venv` y claves `.pem`/`.key`.
No se pasan secretos como argumentos de construcción.

## Recursos exclusivos creados

| Recurso | Nombre / configuración |
| --- | --- |
| Proyecto Compose | `medinet-pac-local-20261030` |
| Imagen API | `localhost/medinet-pac:local-20261030` |
| Contenedores persistentes | `medinet-pac-local-20261030-db`, `medinet-pac-local-20261030-api` |
| Volumen | `medinet-pac-local-20261030-pgdata`, montado en `/var/lib/postgresql` |
| Redes | `medinet-pac-local-20261030-backend` (interna), `medinet-pac-local-20261030-frontend` |
| Secretos Podman | `medinet-pac-local-20261030-admin`, `medinet-pac-local-20261030-api` |
| BD / administrador / API | `pac_local` / `pac_local_admin` / `pac_local_api` |
| Puerto API | `127.0.0.1:18081` → 8000; comprobado libre antes de crear |
| Puerto PostgreSQL | Sin publicación al host; solo 5432 dentro de la red interna |

Las contraseñas aleatorias distintas se enviaron por stdin a `podman secret create`;
no se guardaron en archivos del proyecto, argumentos ni salidas de comandos.
Podman las administra en su almacenamiento local. La API monta únicamente su
secreto, legible por UID 10001; lo carga en el entorno del proceso Uvicorn en memoria.
El administrador solo está disponible en db y en el servicio efímero `migrate`.
Los secretos externos de esta configuración dependen de Podman; no se ha probado
esta configuración con Docker Compose.

## Comandos reales desde la raíz del proyecto

Solo para la primera preparación en un equipo sin estos recursos:

```sh
.venv/bin/python scripts/init_local_containers.py
podman build -f Dockerfile.local -t localhost/medinet-pac:local-20261030 .
.venv/bin/podman-compose --env-file .env.containers -f compose.local.yml config --quiet
.venv/bin/podman-compose --env-file .env.containers -f compose.local.yml up -d db
.venv/bin/podman-compose --env-file .env.containers -f compose.local.yml --profile tools run --rm migrate
.venv/bin/podman-compose --env-file .env.containers -f compose.local.yml up -d api
.venv/bin/python scripts/verify_local_containers.py create
```

El inicializador aborta ante colisiones; no debe repetirse sobre este entorno ya
preparado. Crea `.env.containers` con un puerto, sin contraseñas, y permisos 600.
El ejemplo `.env.containers.example` documenta ese ajuste. El verificador actual
usa explícitamente 18081: si se elige otro puerto en el futuro, adaptar también
su URL. Se usa siempre `--env-file .env.containers`, separado del `.env` existente.

El perfil `tools` debe activarse expresamente con este proveedor. Un primer intento
sin el perfil respondió `missing services [migrate]`; con el perfil terminó con éxito.
El comando administrativo comprueba destino e identidad, aplica Alembic 0001/0002,
crea el rol limitado si falta y otorga SELECT/INSERT/UPDATE y USAGE de secuencia.
Genera el verificador SCRAM en el cliente; no envía contraseñas literales como SQL.
No vuelve a cambiar la contraseña de un rol existente. La API no importa este paso
ni ejecuta migraciones al iniciar. No ejecutar los scripts administrativos de desarrollo
en esta base nueva: aquellos comprueban nombres diferentes.

Arranque habitual (no requiere migraciones):

```sh
.venv/bin/podman-compose --env-file .env.containers -f compose.local.yml up -d db api
.venv/bin/podman-compose --env-file .env.containers -f compose.local.yml ps
curl --fail http://127.0.0.1:18081/health
curl --fail http://127.0.0.1:18081/openapi.json
```

Parada conservando datos, ejecutada y comprobada:

```sh
.venv/bin/podman-compose --env-file .env.containers -f compose.local.yml stop api db
```

Recreación comprobada, conservando el volumen exclusivo:

```sh
.venv/bin/podman-compose --env-file .env.containers -f compose.local.yml up -d --force-recreate db api
.venv/bin/python scripts/verify_local_containers.py persist
```

No usar `down -v` ni borrar el volumen o los secretos: destruiría los datos o
impediría autenticarse. Todos los recursos anteriores a esta tarea se conservaron.
Los dos servicios nuevos quedaron iniciados y healthy al finalizar.

## Evidencia ejecutada ahora

- Construcción de imagen exitosa; inspección runtime confirmó versiones y UID 10001.
- Ambos servicios healthy. Solo la API publica `127.0.0.1:18081`; db no publica puertos.
- `/health`: 200, `{"status":"ok"}`. OpenAPI contiene las cinco operaciones PAC.
- Ejecución HTTP real de POST/GET `/patients`, GET/PATCH `/patients/{id}` y
  POST `/patients/validate-run`. Paciente exclusivamente ficticio creado con 201,
  consultado, listado y actualizado con 200. Página enorme rechazada con 422.
- Tras esas peticiones, `pg_stat_activity` mostró sesiones TCP desde la IP real
  de la API con usuario `pac_local_api`. Esto acredita conexiones utilizadas por
  el servidor HTTP, además de revisar su configuración; `/health` no prueba BD.
- Metadatos de permisos: SELECT, INSERT y UPDATE comprobados por separado;
  sin DELETE, TRUNCATE, SELECT de alembic_version, CREATE en public ni TEMPORARY;
  sin atributos administrativos del rol. No se ejecutaron operaciones destructivas
  para comprobar denegaciones en este entorno con volumen persistente.
- Se recrearon ambos contenedores: IDs distintos, misma fecha de creación del
  volumen y paciente conservado íntegro, incluidas fechas y teléfono actualizado.
- Se ejecutó también `stop` y un arranque habitual, con verificación posterior exitosa.
- Logs completos de db y api revisados mediante captura de stdout y stderr antes
  y después de recrear: sin coincidencias de las dos contraseñas, sus formas URL
  ni verificadores SCRAM. Salida administrativa revisada: mensaje de éxito sin secretos.
  Metadatos de contenedores e imagen revisados sin coincidencias de contraseñas.
  Esto describe las salidas revisadas, no una garantía sobre cualquier log futuro.
- API sin secreto administrativo, POSTGRES_USER ni POSTGRES_PASSWORD en su
  configuración; `/srv/pac/.env` y `/srv/pac/.venv` ausentes.

El verificador conserva una instantánea ficticia e IDs originales en
`.local-containers/patient.json`, ignorado por Git, para comparar tras recreación.
Un primer intento de verificación comparaba `client_addr::text` (con máscara)
con la IP del contenedor; se corrigió a `host(client_addr)` y la comprobación pasó.
El paciente ya creado se reconoció por sus campos sintéticos, sin duplicarlo.

Las **130 pruebas de pytest pertenecen a la etapa anterior de paginación**.
No se repitió esa suite ni se sumaron estas comprobaciones manuales a su total.
Los comandos `verify_local_containers.py create` y `persist` finalizaron con
código 0. No se tocaron desarrollo, contenedores/volúmenes previos, dependencias,
autenticación HTTP, CI/CD, AWS ni informe académico. No hubo commit ni push.

## Pendientes

El entorno local de contenedores quedó operativo. Para cambios de esquema futuros,
ejecutar deliberadamente el paso administrativo separado y revisar los permisos
de nuevas tablas. La comprobación TCP pendiente del entorno de desarrollo sigue
sin abordarse: es independiente de este resultado. Docker Compose, análisis de
vulnerabilidades, CI/CD y AWS no se ejecutaron en esta etapa.

Referencias de formato consultadas: [construcción Podman](https://docs.podman.io/en/latest/markdown/podman-build.1.html)
y [secrets de Compose](https://docs.docker.com/reference/compose-file/secrets/).
El soporte concreto de secretos externos se comprobó en el proveedor local instalado.

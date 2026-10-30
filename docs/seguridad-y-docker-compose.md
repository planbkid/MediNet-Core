# Continuidad: seguridad de imagen y preparación de Docker Compose

Revisión del 30 de octubre de 2026. Se leyeron las instrucciones de
`/home/leecho/AGENTS.md`, las notas locales, Dockerfile, filtros, Compose y scripts.
Sin instrucciones AGENTS.md adicionales encontradas dentro del proyecto.
Se conservaron los archivos sin seguimiento y no se hizo commit ni push.

Continuación posterior: [auditoría Trivy completada con hallazgos](auditoria-trivy-2026-10-30/README.md).
La autorización de descarga ya se recibió y el análisis pendiente descrito abajo
se ejecutó. No se aplicaron actualizaciones. Docker real continúa pendiente.

## Ejecutado con Podman

Herramientas: Podman 5.8.7 rootless, podman-compose 1.6.0 y Python 3.14.7.
Imagen final `localhost/medinet-pac:local-20261030`, ID
`0343ffca9f000f2831b59b4b6c8ba7f2db4bef16186d24a3c484a853062ee681`.
El endurecimiento del contexto conserva la misma imagen original: no cambió código
de aplicación ni dependencias. Dockerfile.local y compose.local.yml no se modificaron.

Comprobaciones ejecutadas:

- UID/GID de API 10001/10001. Archivos de aplicación root:root, modo 0644,
  sin escritura para grupo/otros y ningún camino de aplicación escribible por API.
  Filesystem de API de solo lectura, tmpfs para /tmp, capacidades eliminadas y
  no-new-privileges. Su secreto es 0400 y pertenece a UID 10001.
- API sin secreto administrativo. Migraciones e inicialización en servicio
  administrativo separado, perfil tools. La imagen compartida contiene código
  administrativo, pero el arranque API no lo ejecuta ni monta su contraseña.
- API publicada solo en 127.0.0.1:18081; PostgreSQL sin publicación al host;
  red backend comprobada con Internal=true.
- Auditoría del contexto real con una imagen scratch y COPY: exactamente 23
  archivos permitidos. `.dockerignore` ahora permite únicamente fuentes Python
  en los directorios existentes, plantilla Alembic, configuración y requirements.
  Excluye también scripts de host, texto innecesario, .env*, .venv, claves y cachés.
  Añadir directorios nuevos requiere revisar explícitamente esta lista.
- Fixture de construcción separado con archivos señuelo: se excluyeron .env,
  claves, .venv, cachés, scripts de host y un .txt dentro de app/routers.
- Exportación docker-archive y lectura de todas las 9 capas: 6851 entradas de
  archivos regulares examinadas; sin coincidencias de las dos contraseñas Podman
  actuales. Los 22 archivos del proyecto en las capas coinciden byte por byte
  con las fuentes y conservan propiedad root sin escritura ajena. También se
  inspeccionó la configuración de imagen. Esto no es un detector universal de secretos.
  [Inventario y resultados sin secretos](seguridad-imagen-2026-10-30.json).
- Reconstrucción local y recreación solo de la API independiente; PostgreSQL y
  volumen permanecieron intactos. `verify_local_containers.py persist` terminó
  con código 0: HTTP, OpenAPI, listado/consulta ficticia, 422 para página enorme,
  conexión real como pac_local_api, permisos, persistencia y logs revisados.
  Ambos servicios quedaron healthy. No se repitió toda la suite de pytest;
  las 130 pruebas anteriores siguen siendo evidencia de otra etapa.

Una primera versión demasiado restrictiva del filtro omitió directorios Python;
la API no arrancó y la verificación lo detectó. Se corrigió incluyendo los
directorios y volviendo a excluir sus archivos no permitidos. La reconstrucción,
el fixture y las verificaciones finales posteriores aprobaron.

Artefactos de auditoría conservados en `/tmp/medinet-image-security-rrzggjgd/`:
archivos exportados de imagen/contexto, fixture e inventario. Imágenes auxiliares
`localhost/medinet-pac-context-audit:20261030` y
`localhost/medinet-pac-context-fixture:20261030`. Se conservaron también las
imágenes intermedias de los ensayos. No se eliminó ningún volumen ni recurso previo.

## Docker Compose: preparado y revisado; NO ejecutado

Docker y Docker Compose siguen sin estar instalados en este equipo. No se
conectó a EC2 ni se desplegó. Parsear YAML no sustituye a ejecutar `docker compose
config`, construir y probar sobre el motor Docker real.

Se añadió `compose.docker.yml` independiente, sin fusionarlo con compose.local.yml.
Conserva la misma imagen construible con Dockerfile.local, UID no root, servicio
administrativo separado, healthchecks, filesystem de solo lectura y capacidades
eliminadas. Usa proyecto/redes/volumen `medinet-pac-docker-20261030`, puerto
predeterminado 127.0.0.1:18082 y PostgreSQL sin publicación.
Los nombres lógicos de BD/roles pac_local, pac_local_admin y pac_local_api se
conservan dentro de una instancia nueva para reutilizar las barreras del script
administrativo; no se conecta a la base Podman existente ni copia sus datos.

| Componente | Dependencia de Podman / adaptación |
| --- | --- |
| Secretos externos locales | Recursos Podman; no existen automáticamente en Docker. Docker usa secrets.file nuevos. |
| uid/gid/mode de secretos | Podman los aplica. Docker Compose con archivos conserva permisos del archivo de origen; se omiten esos campos. |
| init_local_containers.py | Invoca podman y crea secretos nativos. No usarlo para Docker. |
| verify_local_containers.py | Usa podman inspect/exec/logs/secret y direcciones/estado propios del motor. No se declara portátil. |
| Redes | internal y DNS por servicio son Compose estándar; etiquetas, IDs y almacenamiento son propios de cada motor. Redes nuevas para Docker. |
| Imagen localhost/... | Etiqueta local de Podman; Docker usará medinet-pac:docker-prepared-20261030 construida allí. |
| entrypoint y prepare_database | Python y PostgreSQL; no invocan Podman. Se reutilizan sin cambios. |

La diferencia de permisos de secrets.file está documentada por
[Docker Compose](https://docs.docker.com/reference/compose-file/services/#secrets).
La red interna usa la opción estándar
[internal](https://docs.docker.com/reference/compose-file/networks/#internal).

### Credenciales nuevas en el servidor: procedimiento preparado, no desplegado

Requisitos previos: Docker Engine, plugin Docker Compose y Python 3 en el servidor,
usuario autorizado para Docker y un puerto libre. Comprobar sus versiones allí;
no inferirlas de este equipo. En esta receta se contempla Docker Linux sin remapeos
personalizados; validar permisos, SELinux/AppArmor y montaje real en el host destino.

Generar dos contraseñas nuevas en un directorio fuera del checkout y del contexto:

```sh
python3 scripts/init_docker_credentials.py "$HOME/.medinet-pac-docker-secrets"
```

El script usa solo la biblioteca estándar, exige ruta absoluta fuera del repo,
crea directorio NUEVO 0700 y archivos 0444. El directorio privado impide lectura
por otros usuarios del host; los permisos de archivo permiten lectura por UID
10001 y el usuario de PostgreSQL dentro de sus montajes individuales. No montar
el directorio entero ni relajar 0700. La API recibe solo api_password; db solo
admin_password; migrate ambos. No hay contraseñas en argumentos, salida, YAML,
variables de construcción ni .env. Docker con secrets.file usa archivos del host,
no un almacén cifrado ni un mecanismo de rotación automática.

Copiar `.env.docker.example` a `.env.docker` y ajustar PAC_DOCKER_SECRETS_DIR a
esa ruta absoluta y PAC_DOCKER_PORT a un puerto libre. Contiene solo ruta/puerto;
está ignorado por Git. No copiar secretos Podman ni el .env de desarrollo.
Conservar los archivos privados junto con la base persistente: regenerarlos no
cambia la contraseña de un PostgreSQL ya inicializado. El inicializador rechaza
directorios existentes y no implementa rotación. Si el proceso se interrumpe a
mitad, revisar el directorio parcial; no se reemplaza automáticamente.

Comandos preparados para ejecutar posteriormente en el servidor autorizado:

```sh
docker --version
docker compose version
docker compose --env-file .env.docker -f compose.docker.yml config --quiet
docker build -f Dockerfile.local -t medinet-pac:docker-prepared-20261030 .
docker compose --env-file .env.docker -f compose.docker.yml up -d db
docker compose --env-file .env.docker -f compose.docker.yml --profile tools run --rm migrate
docker compose --env-file .env.docker -f compose.docker.yml up -d api
docker compose --env-file .env.docker -f compose.docker.yml ps
curl --fail http://127.0.0.1:18082/health
```

Arranque habitual: `docker compose --env-file .env.docker -f compose.docker.yml up -d db api`.
Parada sin borrar datos: `docker compose --env-file .env.docker -f compose.docker.yml stop api db`.
Antes de aprobar Docker: comprobar lectura real de secretos como UID 10001,
POST/GET/PATCH sintéticos, usuario real de conexión, logs y persistencia al recrear
ambos contenedores sin borrar el volumen. /health solo no prueba PostgreSQL.
La API seguirá restringida a localhost; no se configura exposición pública aquí.

Ejecutado aquí sobre el generador, sin Docker: creación de archivos aleatorios
en `/tmp/medinet-docker-credentials-check-q4wlv1md/secrets`, contraseñas distintas,
permisos 0700/0444, salida sin contraseñas, rechazo de sobrescritura y de destino
dentro del repositorio. Se parseó YAML y se comprobaron puertos, separación de
secretos y red interna. Ninguno de estos ensayos acredita ejecución en Docker.

## Análisis de vulnerabilidades

**Pendiente, no ejecutado.** El 30 de octubre de 2026 se buscaron ejecutables
Trivy, Grype, Syft, pip-audit, Bandit y Safety, paquetes del entorno virtual e
imágenes locales de analizadores. No se encontraron analizadores utilizables.
No se instalaron herramientas ni descargaron imágenes de analizadores o bases CVE.

Se solicitó autorización para descargar la imagen oficial `docker.io/aquasec/trivy`
y sus bases, ejecutándola con Podman sobre el archivo exportado api-final.tar,
sin montar el socket del motor ni secretos. También se puede examinar requirements.txt
con el modo filesystem, montando únicamente una copia de ese archivo. Antes de
descargar, fijar la versión disponible y registrar su digest. Requiere red,
espacio para imagen/base/cache y permiso de descarga; la decisión sigue pendiente.

No hay todavía versión de analizador, resultados CVE ni versiones corregidas
contrastadas para estos paquetes. No interpretar las inspecciones de permisos,
archivos y secretos como un análisis SCA de dependencias o del sistema operativo.
Tampoco se ejecutó SAST.

Corrección aplicada: contexto de construcción más reducido y provisión separada
de credenciales para Docker. Propuestas pendientes: analizar paquetes Python y OS
de la imagen API, analizar también postgres:18-alpine y evaluar hallazgos antes
de actualizar. El runtime incluye podman-compose porque está en requirements.txt;
se propone evaluar separar dependencias de host/runtime en una tarea posterior.
Las etiquetas de bases son mutables: valorar fijar digest junto a un proceso
deliberado de actualización. No se cambió ninguna versión ni se afirma ausencia
de vulnerabilidades.

Siguiente paso: autorizar la descarga del analizador, fijar versión/digest y
ejecutar el análisis con informe de hallazgos y versiones corregidas. Después,
probar compose.docker.yml en un entorno Docker autorizado antes de AWS.

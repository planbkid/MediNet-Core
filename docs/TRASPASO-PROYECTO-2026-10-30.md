# Traspaso de MediNet-Core / PAC

Fecha de corte: 30 de octubre de 2026. Preparado a partir del código y las
evidencias locales. No reconstruye conversaciones que no quedaron registradas.
En esta revisión de traspaso no se repitieron pruebas, escaneos ni comprobaciones
de servicios: los resultados de ejecución citados corresponden a sus informes.

## 1. Qué es el proyecto y hasta dónde llega

MediNet-Core implementa el módulo PAC, Gestión de Pacientes y Admisión del Grupo 6.
Actualmente existe un backend FastAPI con PostgreSQL, validaciones, migraciones,
Swagger y pruebas aisladas. No hay frontend ni implementación de otros módulos.
La documentación declara completados los pasos 1, 2 y 3 del backend.

Stack documentado: Python 3.14.7, FastAPI 0.149.0, Pydantic 2.14.1,
SQLAlchemy 2.1.6, psycopg 3.3.6 y PostgreSQL 18; el entorno de contenedores
documenta PostgreSQL 18.6. Dependencias fijadas en requirements.txt y
requirements-dev.txt. Estas versiones describen lo registrado, no una
recomendación de actualización ni una comprobación actual de seguridad.

El backend está probado localmente. La evaluación EVA02 completa todavía no está
acreditada: faltan Docker real, AWS, pipeline con despliegue e informe formal.
Hay vulnerabilidades de imágenes detectadas y sin corregir.

## 2. Funcionalidad implementada

| Operación | Contrato principal |
| --- | --- |
| POST /patients | Alta, 201 y Location; RUN duplicado devuelve 409 |
| GET /patients | Listado con items, total, page y page_size |
| GET /patients/{patient_id} | Consulta; 404 si no existe; ID inválido devuelve 422 |
| PATCH /patients/{patient_id} | Modificación parcial; valida el estado resultante |
| POST /patients/validate-run | Valida formato y Módulo 11 sin consultar existencia |
| GET /health | Comprueba HTTP; no comprueba PostgreSQL |

Swagger: /docs. Contrato: /openapi.json. No hay DELETE ni prefijo de versión
acordado. La revisión de la pauta no identificó DELETE como requisito PAC.

- RUN normalizado, sin puntos, con DV mayúsculo, cuerpo de 7–8 dígitos y Módulo 11.
  Esto no acredita la identidad de una persona.
- Nombres/apellidos normalizados con Unicode NFC, recorte y espacios colapsados;
  conservan tildes, ñ, guiones y apóstrofos.
- Previsión: FONASA, ISAPRE, CAPREDENA o DIPRECA. No se aceptan fechas futuras.
- Email con validación sintáctica; teléfono almacenado como 1–15 dígitos.
- PATCH distingue ausencia de campo y null; rechaza objeto vacío, campos extra,
  escritura de ID/fechas y null en campos obligatorios.
- Filtros RUN, apellidos y previsión combinados con AND. Apellidos por prefijo
  literal, sin distinguir mayúsculas, distinguiendo tildes y escapando comodines.
- Orden por apellido paterno, materno con NULL al final e ID.
- page: 1–100000, predeterminado 1. page_size: 1–100, predeterminado 20.
  Página válida sin filas: 200 con items vacío y total conservado.

## 3. Persistencia, migraciones y seguridad ya incorporada

patients tiene 12 columnas: id, run, nombres, apellido_paterno,
apellido_materno, fecha_nacimiento, prevision, email, telefono, direccion,
created_at y updated_at. Tiene PK, RUN UNIQUE, CHECK de formato RUN y previsión,
índice compuesto de apellidos y dos índices funcionales para búsquedas por prefijo.
El DV se valida en el backend. updated_at se actualiza mediante SQLAlchemy;
no existe trigger equivalente para escrituras SQL directas.

Alembic 0001 crea o adopta el esquema anterior después de verificar su estructura;
0002 incorpora índices de prefijo. Se registró aplicación a desarrollo con datos
conservados y alembic check sin diferencias. No usar stamp a ciegas ni create_all
para evolucionar el esquema. El downgrade destructivo de 0001 está bloqueado.
python -m app.crear_tablas conserva el comando anterior y llama a Alembic.

La API usa sesión por solicitud, cierre garantizado, rollback y consultas
parametrizadas. La UNIQUE resuelve duplicados concurrentes: solo SQLSTATE 23505
con patients_run_key se traduce a 409. Otros errores de integridad devuelven 500
genérico; conectividad, 503. Los errores no exponen entradas personales ni SQL.

Se separaron las credenciales administrativas y las de API. El rol de API tiene
SELECT/INSERT/UPDATE y uso de secuencia; carece de DELETE, TRUNCATE, permisos
administrativos y acceso a alembic_version. Las migraciones usan administrador
en un proceso separado. No se ejecutan automáticamente al arrancar la API.
El lanzador local solicita contraseña oculta y excluye credenciales administrativas
del proceso hijo. No hay autenticación ni autorización HTTP implementadas.

## 4. Entornos: no confundirlos

| Entorno | Destino | Estado registrado |
| --- | --- | --- |
| Desarrollo original | medinet_pac_db, PostgreSQL en 127.0.0.1:5433; API 8000/8001 | Datos conservados; comprobación de contraseña TCP limitada pendiente |
| Contenedores locales independientes | Proyecto medinet-pac-local-20261030; API 127.0.0.1:18081 | Probado con Podman, HTTP real, conexión limitada y persistencia |
| Docker preparado | compose.docker.yml; puerto propuesto 127.0.0.1:18082 | Revisión estática; sin ejecución en Docker |
| Pruebas | Clústeres temporales separados, datos ficticios y tmpfs | Suite registrada de 130 aprobadas |

El entorno independiente tiene base pac_local, administrador pac_local_admin y
API pac_local_api. Sus contenedores son medinet-pac-local-20261030-db y
medinet-pac-local-20261030-api; volumen medinet-pac-local-20261030-pgdata.
PostgreSQL no publica puerto al host. La red backend es interna.

Dockerfile.local construye en dos etapas; API con UID/GID 10001, código propiedad
de root, filesystem de solo lectura, /tmp temporal, capacidades eliminadas y
no-new-privileges. Secretos Podman separados: API recibe solo el suyo. Se verificó
que las conexiones del servidor HTTP usan pac_local_api y se comprobó persistencia
tras recrear ambos contenedores. El informe dejó ambos healthy; no se consultó
su estado durante este traspaso.

La preparación Docker tiene recursos propios y secretos nuevos mediante
scripts/init_docker_credentials.py. No reutiliza automáticamente los secretos
Podman. Docker/Compose no estaban instalados en el equipo según la última evidencia.
Los scripts de inicialización/verificación Podman no se declaran portátiles a Docker.

## 5. Pruebas y evidencia obtenida

- Paso 3: 87 pruebas aprobadas tras corregir la adopción del CHECK y ampliar cobertura.
- Revisión del 29/10: 119 aprobadas; diagnóstico adicional reprodujo la página enorme
  con 500 y el acceso a pacientes sin credenciales HTTP con 200.
- Corrección final de paginación del 30/10: **130 passed in 16.18s**, en PostgreSQL
  exclusivo. Es la última suite completa documentada; no se repitió después.
- Cobertura registrada: validaciones, PATCH/null, filtros, orden, concurrencia,
  rollback, cierre de sesiones, migraciones compatibles/incompatibles, permisos
  efectivos, contraseña incorrecta e identidad del usuario de conexión.
- EXPLAIN sobre 30000 filas sintéticas mostró uso de ambos índices de prefijo.
  Los tiempos locales no garantizan rendimiento en producción.
- Contenedores: operaciones HTTP reales, permisos, secretos/logs y persistencia;
  verify_local_containers.py create y persist terminaron con código 0.
- Imagen: contexto permitido de 23 archivos, revisión de capas y ausencia de
  coincidencias con las contraseñas conocidas. No es una garantía universal.

Las cifras de distintas etapas no se suman. Las verificaciones manuales de
contenedores y los escaneos tampoco aumentan el total de pytest.

## 6. Errores detectados y estado

| Hallazgo | Estado y efecto |
| --- | --- |
| page enorme desbordaba OFFSET PostgreSQL y devolvía 500 | Corregido en código principal: máximo 100000 y regresiones; ahora 422 |
| Comparación del CHECK de previsión fallaba por un cast de arreglo PostgreSQL | Corregido durante Paso 3; suite posterior aprobada |
| Una ejecución temporal de paginación dio 129 passed, 1 failed por SQL auxiliar no enlazado | Corregido el entorno de pruebas; repetición completa con 130 aprobadas |
| Servicio migrate no encontrado sin perfil tools | Corregido el comando usando --profile tools |
| Comparación de IP de API fallaba por máscara de client_addr::text | Corregido el verificador con host(client_addr) |
| .dockerignore demasiado restrictivo excluyó directorios Python y API no arrancó | Corregido; reconstrucción, fixture de contexto y verificaciones aprobadas |
| Contraseña TCP de medinet_pac_api rechazada en desarrollo original | Pendiente; no se cambiaron credenciales. El éxito del entorno independiente no resuelve esto |
| GET /patients accesible sin identidad HTTP | Pendiente de contrato IAM e implementación de autenticación/autorización |
| Integración de eventos críticos asíncronos con AUD ausente | Pendiente de contrato de eventos, autenticación y reintentos |
| Vulnerabilidades de imágenes API/PostgreSQL | Detectadas por Trivy; ninguna corrección aplicada |
| Sin commits en main | Confirmado en este traspaso: archivos aún sin seguimiento; no existe historial versionado |

Otros límites: /health no verifica BD; OFFSET profundo puede seguir siendo lento;
el transporte de etiquetas como JSON no demuestra prevención de XSS en navegador.
El rol de BD no sustituye los permisos de personas sobre HTTP.

## 7. Vulnerabilidades: último análisis documentado

Trivy 0.76.1 ejecutó cuatro análisis el 30/10/2026 con base de ese día.
Resultados por registro paquete/aviso, no por CVE único:

| Entrada | Críticas | Altas | Medias | Bajas | Desconocidas | Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Imagen API | 1 | 53 | 90 | 68 | 4 | 216 |
| Imagen PostgreSQL | 2 | 26 | 32 | 25 | 1 | 86 |
| requirements.txt | 0 | 0 | 0 | 0 | 0 | 0 |
| requirements + dev | 0 | 0 | 0 | 0 | 0 | 0 |

La API tiene 164 registros sin versión corregida informada. El cero de requirements
no cubre todo el runtime ni demuestra ausencia de vulnerabilidades transitivas.
Código de salida 0 del escáner significa ejecución correcta: se configuró
--exit-code 0 para conservar hallazgos.

Prioridades registradas: certifi y otras bibliotecas vendorizadas dentro de pip;
certificados del sistema, OpenSSL, PCRE2 y xz en API; brotli, libcurl y componentes
Go compilados dentro de gosu en PostgreSQL. Instalar certifi por separado no
reemplaza la copia de pip; actualizar Go instalado no recompila gosu.
Consultar versiones exactas y avisos en el informe antes de preparar candidatas.

También hay avisos por HEALTHCHECK ausente en imágenes y USER de imagen PostgreSQL.
Compose sí tiene healthchecks y se comprobó PostgreSQL ejecutando como postgres
tras inicialización. No cambiar USER a ciegas. Ningún secreto detectado por Trivy;
detector heurístico, sin garantía exhaustiva. No hubo SAST ni explotación o análisis
exhaustivo de alcanzabilidad. La cobertura de binarios compilados tiene límites.

**No se actualizaron dependencias, imágenes ni datos para corregir estos hallazgos.**
Todo el detalle está en auditoria-trivy-2026-10-30/README.md, COMPONENTES.md,
vulnerabilities.csv y los cuatro reportes JSON.

## 8. Trabajo pendiente, en orden recomendado

1. Revisar este traspaso con el equipo y consolidar una primera versión Git,
   revisando archivos y exclusiones antes de preparar un commit. Acordar remoto
   real y flujo de colaboración; no publicar secretos ni artefactos privados.
2. Preparar imágenes candidatas para remediar los hallazgos, con etiquetas nuevas.
   Evaluar retirar pip del runtime y separar podman-compose de requirements runtime.
   Registrar digest, reescanear y probar. Probar candidata PostgreSQL con volumen
   nuevo, datos sintéticos y restauración de respaldo; preservar el volumen actual.
3. Ejecutar compose.docker.yml en Docker real: config, build, secretos con UID
   correcto, operaciones HTTP, identidad de conexión, logs y persistencia.
4. Resolver por separado la contraseña TCP del rol limitado de desarrollo y
   demostrar la identidad realmente usada por esa API. No basta /health.
5. Acordar con IAM identidad y permisos e implementar protección de rutas.
   Objetivos por probar: 401 sin identidad, 403 sin permiso y éxito con autorización.
   Acordar también integración asíncrona con AUD; no inventar contratos externos.
6. Preparar despliegue AWS con cuenta/región/instancia y accesos reales del grupo,
   secretos nuevos, acceso restringido y evidencia desde un equipo externo autorizado.
   No hay despliegue AWS acreditado por estas evidencias.
7. Implementar y ejecutar CI/CD: build, pruebas, SAST/SCA y despliegue de imagen
   identificada por tag/commit. La plantilla existente es propuesta histórica,
   no pipeline operativo; adaptarla a la configuración final y probarla.
8. Elaborar informe EVA02: arquitectura, modelo, ISO 27034, OWASP, controles,
   riesgos, evidencias de Docker/AWS/pipeline y límites. README no lo sustituye.
9. Confirmar campos/largos definitivos con docente y contrato entre módulos.
   Frontend, XSS en navegador y HTTPS siguen pendientes para integración/uso real.
   Según la revisión de pauta, frontend no es incumplimiento automático de EVA02.

## 9. Cómo retomar localmente sin reinicializar datos

Desde la raíz, para el entorno independiente YA preparado en este equipo:

```sh
.venv/bin/podman-compose --env-file .env.containers -f compose.local.yml up -d db api
.venv/bin/podman-compose --env-file .env.containers -f compose.local.yml ps
curl --fail http://127.0.0.1:18081/health
curl --fail http://127.0.0.1:18081/openapi.json
```

Swagger: http://127.0.0.1:18081/docs. Salud/OpenAPI no bastan para comprobar BD.
La guía contenedores-locales.md explica la verificación sintética y persistencia.
En otro equipo se requiere preparación nueva siguiendo esa guía: los secretos,
volúmenes y entornos virtuales de este host no viajan con el código.

Suite segura documentada:

```sh
.venv/bin/python scripts/run_pac_tests.py
```

Requiere Podman y la imagen local postgres:18-alpine. Aborta si el nombre de
contenedor de pruebas ya existe. Identificar recursos antes de resolver colisiones.
No ejecutar pytest apuntando a desarrollo ni eliminar contenedores por semejanza
de nombres. El runner valida identidad antes de migrar o limpiar datos ficticios.

No repetir init_local_containers.py sobre el entorno existente; no repetir el SQL
de creación del rol ya aplicado. No usar down -v, drop_all, limpiezas globales ni
borrar secretos/volúmenes. No compartir .env, llaves, contraseñas, .venv ni
.local-containers. Migraciones y rotación de credenciales son tareas deliberadas.

## 10. Mapa de archivos y lecturas

| Ubicación | Uso |
| --- | --- |
| app/main.py | Aplicación y tratamiento de errores |
| app/models.py, schemas.py, validators/run.py | Persistencia y validación |
| app/routers/patients.py, services/patients.py | Contrato HTTP y operaciones |
| app/database.py, admin_database.py, run_local.py | Separación de conexiones y arranque |
| migrations/versions/ | Historial 0001/0002 |
| tests/, scripts/run_pac_tests.py | Pruebas y aislamiento PostgreSQL |
| scripts/containers/ | Arranque y preparación administrativa de contenedores |
| Dockerfile.local, compose.local.yml | Entorno probado con Podman |
| compose.docker.yml, scripts/init_docker_credentials.py | Preparación Docker aún por ejecutar |
| scripts/run_trivy_scans.py | Reproducción de auditoría con artefactos locales |
| docs/revision-eva02/plantillas/ | Propuestas históricas; revisar antes de reutilizar |

Leer después: README.md, docs/contenedores-locales.md,
docs/seguridad-y-docker-compose.md y docs/auditoria-trivy-2026-10-30/README.md.
Para historia: docs/paso3-validacion.md, docs/continuidad-paginacion-2026-10-30.md
y docs/revision-eva02/Revision y receta EVA02.txt.

Los informes históricos conservan pendientes de su fecha. En particular, el texto
antiguo que dice que faltan contenedores locales o que Trivy está pendiente fue
superado por las verificaciones posteriores. Siguen pendientes Docker real y las
correcciones de vulnerabilidades. No hubo commit/push en las etapas documentadas,
y en este traspaso se confirmó que main todavía no tiene commits.

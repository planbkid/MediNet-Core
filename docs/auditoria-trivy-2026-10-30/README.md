# Auditoría local con Trivy — 30 de octubre de 2026

Se completaron cuatro análisis locales con **Trivy 0.76.1**, entre
21:33:28 y 21:34:57 UTC (horas exactas en commands.json).
Todos finalizaron con código 0 y JSON válido. Se configuró `--exit-code 0` para
conservar todos los hallazgos: ese código indica ejecución correcta, no ausencia
de vulnerabilidades. No se aplicaron actualizaciones ni cambios de ejecución.

## Procedencia, integridad y privacidad

Binario Linux x86_64 de la [publicación oficial v0.76.1](https://github.com/aquasecurity/trivy/releases/tag/v0.76.1),
instalado exclusivamente en `.local-containers/trivy-audit-2026-10-30/bin/trivy`.
SHA256 del tarball: `c7cbe3137fb8a48a17574bede3dd6beb16742d1e9772929940fc90082c39d9c0`.
Se verificó contra la lista oficial de checksums y el digest del asset publicado
por la API de GitHub. También se verificaron los digests de la lista de checksums
y del paquete Sigstore descargado. No se verificó criptográficamente la firma
Sigstore: Cosign no está instalado. Los checksums sobre HTTPS verifican integridad;
no se presentan como una verificación independiente de identidad del firmante.
Detalles en integridad.json, release.json, checksums y paquete Sigstore conservados.
No se instalaron paquetes del host ni Docker.

Los análisis usaron archivos exportados y un snapshot local. Se desactivaron
telemetría, comprobación de versión, actualización durante el análisis y consultas
de dependencias (`--offline-scan`). No se utilizó servidor remoto, socket del
motor, registro remoto de imágenes ni servicio externo de análisis. Se limpiaron
variables TRIVY heredadas y se desactivó la carga de configuración/ignorefile
externos. Las únicas descargas fueron metadatos/archivos oficiales, base y reglas.
No se enviaron fuentes, imágenes ni secretos.

## Imágenes y entradas exactas

| Objetivo | Referencia | ID local |
| --- | --- | --- |
| API | localhost/medinet-pac:local-20261030 | 0343ffca9f000f2831b59b4b6c8ba7f2db4bef16186d24a3c484a853062ee681 |
| PostgreSQL | docker.io/library/postgres:18-alpine | 57b23a0326ee442e83b3d3fa027c5a148be0a392d7c91d1ca4e1e70131ee859a |

Los IDs se contrastaron con los contenedores activos y con Config de cada
docker-archive. `images.json` registra además digests de manifiesto y SHA256
de las exportaciones. API: Debian 13.7, 87 paquetes OS y 44 entradas Python.
PostgreSQL: Alpine 3.24.3, 53 paquetes OS y cuatro componentes Go de gosu.
Son inventarios del analizador; no equivalen al listado de distribuciones Python
instaladas directamente, pues incluyen copias vendorizadas.

Snapshot del proyecto: app, migrations, scripts y tests existentes al preparar
el análisis; requirements, Dockerfile.local, Compose y configuración activa.
Se excluyeron `.env` reales, .venv, .git, datos/volúmenes, secretos Podman,
documentos académicos y plantillas históricas. Se incluyeron ejemplos de entorno
sin contraseñas reales. Manifest de 48 archivos en source-sha256.json.
El snapshot precede a los scripts/reportes de esta auditoría.

Se añadió una copia idéntica de Dockerfile.local con nombre Dockerfile para
garantizar reconocimiento; Trivy reconoció ambos. Esto duplica un aviso de
configuración, no dos defectos diferentes. `requirements.txt` aportó 25 paquetes.
Como el escaneo inicial no enumeró requirements-dev.txt, se realizó un análisis
adicional con los 33 paquetes de requirements + requirements-dev aplanados,
eliminando solo la directiva `-r requirements.txt`. Hash en development-input.json.
Los dos snapshots completos sin secretos se conservan en inputs.tar.gz.

## Bases utilizadas y actualización

- Vulnerabilidades: `ghcr.io/aquasecurity/trivy-db:2`, esquema 2.
- UpdatedAt: **2026-10-30T19:07:50.77378237Z**.
- DownloadedAt: **2026-10-30T21:33:05.165026973Z**.
- NextUpdate: **2026-10-31T19:07:50.77378224Z**; vigente durante estos análisis.
- Reglas: `ghcr.io/aquasecurity/trivy-checks:2`, digest
  `sha256:b0e12d009b01dcc8ca2ebbc199b9caf3922491978d21c17b61c1d7f6dc75220b`.
- Descarga de reglas: 2026-10-30T21:33:05.646946141Z. La preparación usó un
  directorio vacío: su informe no representa un análisis del proyecto.
- Java DB no descargada: no se detectaron componentes Java que la requirieran.

Metadatos y hashes de base/reglas en databases.json y version.json. El caché exacto
queda privado en `.local-containers/trivy-audit-2026-10-30/cache`; se congeló
con `--skip-db-update --skip-java-db-update --skip-check-update` para todas las
entradas. Una ejecución futura con bases nuevas puede arrojar resultados distintos.

## Resultado por severidad

Conteos por registro paquete/aviso. Las severidades son las seleccionadas por
Trivy según sus fuentes; UNKNOWN no se omite. Un mismo CVE puede afectar a varios
paquetes derivados de una fuente y contarse varias veces.

| Objetivo | Crítica | Alta | Media | Baja | Desconocida | Total | Sin versión corregida informada |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| API | 1 | 53 | 90 | 68 | 4 | 216 | 164 |
| PostgreSQL | 2 | 26 | 32 | 25 | 1 | 86 | 0 |
| requirements.txt, 25 paquetes | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| requirements + dev, 33 paquetes | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

API: 207 registros OS + 9 Python, 97 identificadores de aviso distintos,
52 registros con versión corregida informada. PostgreSQL: 25 registros Alpine
+ 61 Go en gosu, 86 identificadores distintos, todos con versión corregida
informada. No se usaron `--ignore-unfixed`, filtros de severidad, VEX ni excepciones
para ocultar resultados. [Todos los componentes, incluidas versiones sin corrección](COMPONENTES.md)
y [los 302 registros completos con aviso y versión corregida](vulnerabilities.csv).

### Componentes prioritarios

| Componente y ubicación | Severidad máxima | Instalada | Corregida según base / observación |
| --- | --- | --- | --- |
| certifi, copia vendorizada por pip en API | Crítica | 2026.6.17 | 2026.10.18; el aviso del mantenedor recomienda 2026.10.19 o posterior |
| urllib3, vendorizada por pip | Alta | 2.7.0 | 2.8.0 |
| msgpack, vendorizada por pip | Alta | 1.1.2 | 1.2.3 para cubrir ambos avisos registrados |
| setuptools, vendorizada por pip | Alta | 70.3.0 | 78.1.1 para CVE-2025-47273; 83.0.0 y 84.1.0 para los otros avisos; cubrir todos requiere como mínimo 84.1.0 |
| libssl3t64 / openssl / openssl-provider-legacy, API | Alta | 3.5.7-1~deb13u2 | 3.5.7-1~deb13u3 |
| libpcre2-8-0, API | Alta | 10.46-1~deb13u2 | 10.46-1~deb13u3 |
| ca-certificates, API | Desconocida | 20250419 | 20250419+deb13u1; importante aunque la base no asigne severidad |
| liblzma5, API | Desconocida | 5.8.1-1+deb13u1 | 5.8.1-1+deb13u2 |
| brotli-libs, PostgreSQL | Crítica | 1.2.0-r1 | 1.2.1-r0, CVE-2026-111497 |
| stdlib Go embebida en gosu, PostgreSQL | Crítica | v1.24.6 | CVE-2025-68121: 1.24.13 / 1.25.7 / 1.26.0-rc.3; los otros avisos requieren versiones posteriores, incluido 1.27.3 para CVE-2026-111943 |
| libcurl, PostgreSQL | Alta | 8.22.0-r0 | 8.23.0-r0 |
| github.com/moby/sys/user, gosu | Media | v0.1.0 | 0.4.1 |
| golang.org/x/sys, gosu | Desconocida | v0.1.0 | 0.44.0; aviso Windows, requiere evaluar aplicabilidad a Linux |

La [alerta de certifi](https://github.com/advisories/GHSA-6q48-6c7w-9gw2)
afecta a la confianza en certificados emSign tras el compromiso de claves de
intermedias. Su presencia en pip se confirmó leyendo vendor.txt del contenedor,
sin modificarlo. Instalar una distribución normal de certifi/urllib3/msgpack no
reemplaza las copias internas de pip. La mitigación debe abordar el instalador
o eliminarlo deliberadamente del runtime, además de actualizar el trust store OS.

Los 164 registros sin corrección informada incluyen avisos altos en componentes
de util-linux, acl, ncurses, systemd y perl, y avisos medios/bajos de glibc y otros.
No se ocultaron ni se clasificaron automáticamente como falsos positivos.
No tener versión corregida en esta base significa eso; no demuestra que ningún
proveedor tenga una solución alternativa ni que el código vulnerable sea alcanzable.

### Configuración y secretos

- Imagen API: DS-0026, LOW, falta HEALTHCHECK dentro de la imagen.
- Imagen PostgreSQL: DS-0002, HIGH, configuración de imagen sin USER no root;
  DS-0026, LOW, falta HEALTHCHECK en la imagen.
- Proyecto: DS-0026 aparece dos veces por la copia idéntica Dockerfile/Dockerfile.local;
  es un aviso único. Ningún secreto detectado en los cuatro análisis.

Se conservaron estos avisos en sus reportes. Contexto contrastado: Compose define
healthchecks para ambos servicios y PostgreSQL PID 1 ejecuta como usuario postgres;
el entrypoint de su imagen empieza con root para preparar permisos y después
reduce privilegios. No cambiar USER a ciegas, pues puede romper inicialización de
volúmenes. Evidencia runtime en runtime-context.json.

Trivy no produjo resultados de reglas sobre Compose en esta ejecución. Sus YAML
estaban en el snapshot, pero eso no equivale a validación de seguridad de Compose.
Se completó revisión estática suplementaria de compose.local.yml y compose.docker.yml
(compose-review.json): localhost, BD sin puerto, secretos separados, migración
por perfil, red interna, solo lectura, capacidades y healthchecks. Esa revisión
no es una ejecución sobre Docker ni certifica reglas que el script no comprueba.

## Límites y estado de completitud

Los cuatro análisis solicitados a Trivy **se completaron**; no hubo fallos de
ejecución ocultados. Requirements tuvo cero vulnerabilidades detectadas; las
imágenes tuvieron hallazgos. El resultado cero en requirements no puede extrapolarse
a sus transitivas no resueltas, al runtime completo ni al código de la aplicación.
Se usó prioridad de detección precise, sin resolución online de dependencias.
No se ejecutó SAST, pruebas de explotación, evaluación exhaustiva de alcanzabilidad
ni auditoría del host. El detector de secretos es heurístico.

Los binarios compilados desde fuentes no quedan necesariamente cubiertos por los
paquetes del sistema o metadatos de lenguaje. PostgreSQL 18.6 no figura como
paquete postgresql versionado en APK (solo .postgresql-rundeps); por ello no se
afirma que Trivy haya descartado todas las vulnerabilidades del servidor. La
[tabla oficial de PostgreSQL](https://www.postgresql.org/support/security/)
consultada informa varias correcciones en 18.6, pero no sustituye ese límite de
cobertura ni garantiza ausencia de otros problemas. Tampoco se considera
exhaustiva la cobertura de CPython y bibliotecas nativas compiladas.

## Propuesta de correcciones, sin aplicarlas todavía

1. **Confianza TLS e instaladores de la API:** preparar una imagen candidata,
   manteniendo Python 3.14 compatible, con ca-certificates corregido y sin las
   copias vulnerables de pip en runtime. Evaluar eliminar pip/herramientas de
   construcción en la etapa final, o una versión de pip cuyos componentes
   vendorizados cumplan todos los mínimos anteriores. Verificar contenido real;
   no basta agregar certifi a requirements. Separar podman-compose de las
   dependencias runtime en un cambio explícito y revisable.
2. **Paquetes OS de API:** seleccionar base actualizada o actualización dirigida
   que incluya OpenSSL, PCRE2, xz y certificados en las versiones indicadas.
   Construir con etiqueta nueva, registrar digest y reanalizar. No cambiar de
   distribución o versión mayor para aparentar que desaparecen avisos. Mantener
   seguimiento de los 164 registros sin corrección y evaluar alcanzabilidad por
   componente, documentando cualquier excepción en vez de ocultarla.
3. **PostgreSQL:** evaluar otra construcción oficial compatible de PostgreSQL 18
   que incluya brotli >=1.2.1-r0, libcurl >=8.23.0-r0 y gosu recompilado con
   componentes Go corregidos. Cambiar Go instalado o APK no modifica una stdlib
   enlazada estáticamente en gosu. No se eligió ni descargó una imagen candidata;
   un tag más nuevo no garantiza estas correcciones sin inspeccionarlo y escanearlo.
   No sustituir automáticamente el servidor que conserva el volumen local.
4. **Configuración:** valorar HEALTHCHECK en Dockerfile.local para uso fuera de
   Compose, conservando los checks actuales y controlando su efecto en el servicio
   administrativo. Mantener UID 10001, archivos de root, secretos separados y
   privilegios limitados. Evaluar el aviso root de PostgreSQL con inicialización
   nueva y usuario de proceso real antes de proponer modificaciones.

Pruebas propuestas para cada imagen candidata: nuevo escaneo con mismo snapshot
de base y luego base actualizada, inventario de paquetes/archivos, versiones SSL y
certificados, importaciones y `pip check` en builder, suite PAC con runner seguro
en PostgreSQL exclusivo, HTTP de las cinco operaciones, identidad real de conexión,
ausencia de secretos en logs y persistencia tras recrear. La candidata PostgreSQL
debe probarse primero con volumen nuevo y datos ficticios, sin montar ni modificar
el volumen local existente; comprobar inicialización y restauración de un respaldo
sintético antes de planificar cualquier cambio del servidor actual.

**Correcciones aplicadas ahora: ninguna a dependencias, imágenes, Compose ni datos.**
Solo se añadieron herramienta aislada, script de auditoría y evidencia/documentación.
El entorno local y su volumen se conservaron; ambos servicios siguen healthy.
No hubo commit, push, AWS ni instalación de Docker.

## Reproducción y archivos

- `integridad.json`, release.json, checksum y paquete Sigstore: procedencia.
- `images.json`: referencias, IDs, digests y SHA256 de archivos de imagen.
- `databases.json`, `version.json`: snapshot y estado de actualización de bases.
- `preparation-commands.json`: comandos ejecutados de adquisición/exportación.
- `commands.json`: comandos exactos de cada análisis, fechas UTC y salidas.
- `api.json`, `postgres.json`, `project.json`, `development.json`: reportes completos.
- `*.stdout.log`, `*.stderr.log`: salidas y advertencias.
- `summary.json`, COMPONENTES.md, vulnerabilities.csv: resúmenes y lista íntegra.
- `inputs.tar.gz`, source-sha256.json: fuentes/configuración sin secretos utilizadas.
- `compose-review.json`, runtime-context.json: contraste suplementario, fuera de Trivy.
- `SHA256SUMS`: integridad de los artefactos publicados en esta carpeta.

La instalación, los archivos de imagen, reportes crudos y caché exacto se conservan
en `.local-containers/trivy-audit-2026-10-30/`, ignorado por Git. No borrar ese
directorio si se necesita repetir con las mismas imágenes/bases. Los reportes
publicados redactarían valores del detector de secretos; no hubo hallazgos que
redactar. No se guardaron credenciales Podman en los archivos de auditoría.

Desde la raíz, para repetir sin descargar, usando los artefactos conservados:

```sh
.venv/bin/python scripts/run_trivy_scans.py
```

El script verifica antes los hashes del binario, imágenes, base/reglas y entradas.
Se comprobó también esa validación sin volver a escanear mediante
`.venv/bin/python scripts/run_trivy_scans.py --verify-inputs`.

Permite objetivos individuales: `api`, `postgres`, `project`, `development`.
El script agrega el diario de comandos y vuelve a generar reportes; conservar
una copia de esta carpeta antes de repetir si se requiere retener cada ejecución.
Para reconstruir el entorno de auditoría, usar release.json y download_verify.py
conservados (versión fijada), verificar inputs y hashes, disponer de los archivos
de imagen o exportarlos por sus IDs y restaurar el caché cuyo hash figura en
databases.json. Descargar bases nuevas produce otra ejecución, no la misma.

No se ejecutó toda la suite ni se alteraron servicios para esta auditoría de solo
lectura. Las 130 pruebas anteriores son evidencia separada. Próximo paso:
acordar el primer cambio de imagen candidata y validar las correcciones propuestas.
**Sigue pendiente ejecutar compose.docker.yml sobre Docker real antes de AWS.**

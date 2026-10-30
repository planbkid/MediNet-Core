# Continuidad local: corrección de paginación

Fecha: 30 de octubre de 2026. Corrección aplicada al proyecto principal.

Se leyeron `/home/leecho/AGENTS.md`, README, runner, pruebas y
`docs/revision-eva02/Revision y receta EVA02.txt` (nombre real sin tilde).
No se encontraron instrucciones AGENTS.md adicionales dentro del proyecto.
El repositorio sigue sin commits y sus archivos estaban sin seguimiento.
La copia `/tmp/medinet-eva02-audit-20261029` ya no existía. Se reconstruyó
únicamente el cambio de paginación descrito por la guía; el límite seguía pendiente.

## Causa y contrato

`page` solo tenía mínimo 1. El servicio calcula `(page - 1) * page_size`;
un entero Python muy grande genera un OFFSET fuera del rango de PostgreSQL
y terminaba en 500, según la reproducción del 29 de octubre.
En esta sesión se confirmó la causa en código, sin reproducir el fallo en desarrollo.

Ahora `page` admite 1–100000, predeterminado 1; `page_size` conserva 1–100,
predeterminado 20. El máximo OFFSET por HTTP es 9999900. Es una política
de entrada, no una garantía de rendimiento para páginas profundas.
Valores fuera de rango y entradas no enteras producen 422 antes de ejecutar
el servicio de listado. El límite también aparece en OpenAPI/Swagger.
Una página dentro del rango sin filas devuelve 200, `items: []`, el total
de coincidencias y los parámetros solicitados. Sin coincidencias, `total: 0`.
Se conservan orden, filtros y estructura de las respuestas válidas.

## Cambios

- `app/routers/patients.py`: máximo de página y descripción OpenAPI.
- `tests/test_patients.py`: cinco casos inválidos adicionales (negativo,
  fracción, 100001, 9223372036854775808 y un entero de 1000 dígitos),
  comprobación de que entradas inválidas no llaman al servicio, cuatro
  combinaciones de límites página/tamaño sobre base vacía, valores predeterminados,
  páginas más allá de resultados con total conservado y contrato OpenAPI.
  Se conservan las regresiones existentes de orden y páginas sucesivas.
- `README.md`: contrato de paginación y enlace a esta continuidad.
- Este archivo: evidencia de ejecución y siguiente paso.

## Verificación real

El nombre habitual `medinet_pac_credentials_test` estaba ocupado. Para conservar
todos los contenedores previos se preparó el entorno temporal
`/tmp/medinet-pagination-20261030-gpt4d7rc` sin `.env`:

- `app/`, `migrations/`, configuración Alembic/pytest y scripts SQL enlazados
  al proyecto principal.
- Runner copiado sin cambios y pruebas copiadas idénticas, salvo las constantes
  CONTAINER y PORT del soporte de aislamiento. Se comprobó igualdad de archivos.
- Base/roles, etiquetas, identidad de clúster, marcador y barreras originales
  conservados; PostgreSQL 18 local con `--pull=never`, tmpfs y sin mounts persistentes.

Comando ejecutado desde la raíz del proyecto, con autorización para Podman fuera
del sandbox (el primer intento dentro falló por `/run/user/1000` de solo lectura):

```sh
/home/leecho/Asistente-Codex/MediNet-Core/.venv/bin/python /tmp/medinet-pagination-20261030-gpt4d7rc/scripts/run_pac_tests.py
```

Resultado final comprobado: **130 passed in 16.18s**, código de salida 0.
Contenedor exclusivo: `medinet_pac_pagination_verified_20261030`,
`127.0.0.1:55439`, conservado para inspección. El servicio de la API probado es
el código principal, mediante TestClient y conexiones al PostgreSQL temporal.

La primera ejecución, en `medinet_pac_pagination_20261030`, puerto 55438,
dio **129 passed, 1 failed in 16.49s**: faltaba enlazar
`scripts/check_runtime_permissions.sql` en el entorno temporal. Se corrigió
ese entorno y se repitió toda la suite en otra instancia nueva. No fue un fallo
de paginación. Ambos contenedores se conservaron, sin limpiezas.

`git diff --check` terminó sin errores; al no haber archivos versionados,
esa comprobación no cubre los archivos sin seguimiento. No se hicieron
migraciones, TRUNCATE, lecturas de pacientes ni cambios en desarrollo.
Las migraciones y limpiezas de fixtures ocurrieron solo en PostgreSQL de pruebas,
tras sus barreras de identidad. No se cambiaron dependencias ni se instalaron
herramientas; tampoco se modificaron informe académico, plantillas Docker,
autenticación, CI/CD o AWS. No hubo commit ni push.

## Siguiente paso acordado

Preparar contenedores locales: comprobar las herramientas instaladas y revisar
las plantillas Dockerfile, .dockerignore y Compose de `docs/revision-eva02/plantillas/`
antes de incorporarlas y probarlas. Usar proyecto y volumen independientes de
desarrollo, con datos sintéticos. Esta etapa todavía no se implementó.
AWS queda fuera del alcance actual. Sigue pendiente de antes la comprobación
de la credencial TCP del rol limitado en desarrollo; no se abordó en esta sesión.

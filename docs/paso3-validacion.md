# Entrega Paso 3 PAC

Ejecución real del 26 de octubre de 2026 en este workspace. Se leyó
`/home/leecho/AGENTS.md`, la guía DOCX, el README y el código existente antes de
editar. No se encontró un AGENTS.md adicional dentro del proyecto. El repositorio
ya contenía archivos sin seguimiento y no tenía commits; no se hizo commit ni push.

## Archivos cambiados

- `app/database.py`: sesión por solicitud, cierre y ocultación de parámetros SQL.
- `app/models.py`: índices funcionales de apellidos, sin cambiar columnas.
- `app/main.py`: router y errores de validación/BD sin entradas sensibles.
- `app/crear_tablas.py`: comando anterior conservado, ahora aplica Alembic.
- `app/schemas.py`: contratos separados, validación y normalización.
- `app/validators/run.py` y `app/validators/__init__.py`: formatos RUN y Módulo 11.
- `app/services/patients.py` y `app/services/__init__.py`: persistencia, transacciones,
  paginación, filtros parametrizados y tratamiento específico de duplicados.
- `app/routers/patients.py` y `app/routers/__init__.py`: cinco operaciones y Swagger.
- `alembic.ini`, `migrations/env.py`, `migrations/script.py.mako`,
  `migrations/versions/0001_existing_patients.py` y
  `migrations/versions/0002_prefix_indexes.py`: historial y adopción validada del Paso 2.
- `tests/conftest.py`, `tests/test_patients.py`, `tests/test_migrations.py` y
  `pytest.ini`: PostgreSQL aislado, regresiones, concurrencia y EXPLAIN.
- `requirements.txt`, `requirements-dev.txt`: dependencias nuevas fijadas,
  manteniendo las versiones existentes del stack.
- `.gitignore`, `README.md` y este informe: exclusiones, contrato, comandos,
  recorrido Swagger, evidencia y pendientes.

El `.env`, Compose y el volumen de desarrollo existentes se conservaron.

## Decisiones

Se mantienen Python 3.14.7, FastAPI 0.149.0, Pydantic 2.14.1, SQLAlchemy 2.1.6,
psycopg 3.3.6 y el PostgreSQL 18 existente. No se actualizó el stack por rutina.
No hay otro motor asíncrono ni rutas de hospitalización o facturación.

Se mantiene `/patients`, sin un prefijo de integración todavía no acordado. RUN
permite cuerpos de 7–8 dígitos compatibles con el CHECK real. Se usa prefijo literal
de apellido sobre `lower`, con tildes significativas y comodines escapados. Ambos
índices funcionales usan `text_pattern_ops`; el índice compuesto previo permanece.

Alembic `0001` verifica la tabla real antes de adoptarla, sin stamp. `0002` solo
añade índices, mediante una transacción; puede bloquear escrituras brevemente.
Se bloquea el downgrade que eliminaría patients. El comando antiguo
`python -m app.crear_tablas` continúa funcionando mediante Alembic.

No se hace una consulta previa de duplicados: la UNIQUE es la garantía de
concurrencia. SQLSTATE 23505 y `patients_run_key` producen 409, después de rollback;
otra integridad produce 500 genérico. Un error de BD no expone SQL ni valores.
El cliente de pruebas usa httpx2, recomendado por el Starlette instalado.

## Comandos ejecutados y verificaciones

Desde `/home/leecho/Asistente-Codex/MediNet-Core`:

```sh
git status --short
git log -5 --oneline
.venv/bin/python -m pip install alembic email-validator pytest httpx
.venv/bin/python -m pip install httpx2
.venv/bin/python -m pip check
.venv/bin/python -m compileall -q app migrations tests
git diff --check
git check-ignore -v .env
```

La consulta de historial confirmó que todavía no había commits. La instalación
inicial dentro del aislamiento falló por resolución de red; se repitió con permiso
de red y terminó correctamente. `httpx` se instaló en la primera preparación, pero
la suite final usa `httpx2`; las dependencias de pruebas reproducibles están en
`requirements-dev.txt`. `pip check` no informó incompatibilidades. `.env` sigue
ignorado por Git. No se imprimió su contenido ni una URL con contraseña.

Se inspeccionó la estructura de desarrollo con `sqlalchemy.inspect` y se comprobó
`SELECT 1`. El resultado fue: 12 columnas, PK, `patients_run_key`, dos CHECK e
índice compuesto como en el Paso 2; conectividad correcta. No se mostró ninguna fila.

El PostgreSQL aislado se creó con:

```sh
podman run -d --name medinet_pac_test --label medinet.purpose=isolated-tests \
  -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_DB=medinet_pac_test \
  -e POSTGRES_USER=medinet_pac_test -p 127.0.0.1:55433:5432 \
  --tmpfs /var/lib/postgresql:rw docker.io/library/postgres:18-alpine
PAC_TEST_DATABASE=medinet_pac_test PAC_TEST_PORT=55433 .venv/bin/python -m pytest -q
```

Primera ejecución: **84 aprobadas, 1 fallida**. Fallaba la comparación del CHECK de
previsión al adoptar el esquema anterior, por la representación de un cast de
arreglo de PostgreSQL. Se corrigió la comparación y se volvió a ejecutar:
**85 aprobadas**. Después de añadir cobertura de 503 y del comando heredado:

```text
........................................................................ [ 82%]
...............                                                          [100%]
87 passed in 2.95s
```

La concurrencia usa dos solicitudes y sesiones distintas sincronizadas antes del
commit: resultados 201 y 409, con una sola fila. Se verificaron rollback en la
misma sesión y cierre tras éxito y 404. Se probaron entradas inválidas, vectores K
y 0, Unicode, PATCH, null, límites, filtros AND, orden, comodines literales,
SQLi y transporte JSON de etiquetas.

Las migraciones se ejecutaron en bases nuevas del servidor de pruebas: una vacía,
una réplica del esquema del Paso 2 con una fila sintética y una deliberadamente
incompatible. El upgrade preservó íntegramente la fila y sus fechas, fue repetible
y rechazó el esquema incompatible sin añadir los índices.

Después de esas pruebas se ejecutó un script local temporal
`/tmp/medinet_apply_migration.py`, con `PYTHONPATH=.`, que aplicó
`alembic upgrade head` a desarrollo. Comparó antes y después la cantidad y una
huella del contenido de las filas, las columnas, defaults, CHECK y UNIQUE, sin
imprimir datos ni huellas. Resultado:

```text
Migraciones 0001 y 0002 aplicadas a desarrollo: filas, columnas y restricciones previas conservadas.
```

```sh
.venv/bin/python -m alembic check
```

```text
No new upgrade operations detected.
```

## Planes de búsqueda

```sh
PAC_TEST_DATABASE=medinet_pac_test PAC_TEST_PORT=55433 .venv/bin/python -m pytest -q -s tests/test_migrations.py::test_prefix_indexes_query_plan
```

Se capturaron las consultas reales emitidas por el servicio y se ejecutó
`EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` con sus parámetros. No se forzó al
optimizador a desactivar escaneos secuenciales.

```text
EXPLAIN: ix_patients_paterno_prefix; 30000 filas; planificación=0.143 ms; ejecución=0.122 ms; bloques compartidos hit=3
EXPLAIN: ix_patients_materno_prefix; 30000 filas; planificación=0.119 ms; ejecución=0.099 ms; bloques compartidos hit=3
.
1 passed in 0.68s
```

Estos tiempos son mediciones locales con distribución sintética selectiva; no
son una garantía de rendimiento en producción. Las filas de rendimiento se
insertan directamente para medir índices y solo cumplen el formato de RUN del
CHECK; no representan altas realizadas por el validador de la API.

## HTTP y aislamiento

Se inició la API con:

```sh
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Una comprobación HTTP real mediante `urllib.request` obtuvo:

```text
/health 200
/docs 200
/openapi.json 200
/patients?page=1&page_size=1 200
HTTP real verificado sin escribir pacientes.
```

Se verificaron el HTML de Swagger, las cinco operaciones de pacientes en OpenAPI,
la respuesta de salud y la forma del listado, sin imprimir datos del listado.
Se comprobó mediante un subproceso que pytest sin las dos variables opt-in
rechaza la ejecución con código 4, antes de importar la aplicación.

Al terminar se detuvo únicamente `medinet_pac_test`; el README indica cómo volver
a iniciarlo. La base de desarrollo se mantiene en 127.0.0.1:5433 y la API local
se dejó iniciada en 127.0.0.1:8000. No se ejecutaron DELETE sobre desarrollo,
drop_all, down -v ni eliminación de su volumen.

## Lo no verificado y pendientes

- No se automatizó un navegador ni se tomaron capturas: Swagger se comprobó por
  HTTP y su contrato con TestClient. El recorrido manual exacto está en README.
- No hay frontend en esta entrega; no se puede afirmar prevención de XSS en su
  renderizado. Solo se verificó contenido y tipo JSON de la API.
- No se probaron Docker para la API, pipeline, SAST/SCA, AWS, HTTPS, autenticación,
  autorización ni permisos limitados de PostgreSQL. Corresponden a las próximas
  iteraciones; no se declaran operativos ni libres de vulnerabilidades.
- Los campos definitivos y el contrato común de identidad y permisos requieren
  acuerdo con docente/equipo. No se agregaron supuestos sobre otros módulos.

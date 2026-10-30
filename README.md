# MediNet-Core · Módulo PAC

API FastAPI para Gestión de Pacientes y Admisión (Grupo 6).
Implementados los pasos 1, 2 y 3: persistencia, validaciones, contrato REST y
pruebas de integración sobre PostgreSQL aislado. Stack existente conservado.

Última continuidad local: [contenedores independientes operativos, comandos y
evidencia](docs/contenedores-locales.md). Swagger local en http://127.0.0.1:18081/docs.
Revisión posterior: [seguridad de imagen y compatibilidad Docker preparada](docs/seguridad-y-docker-compose.md),
con ejecución Docker aún pendiente. [Auditoría Trivy completada con hallazgos y
propuesta de correcciones](docs/auditoria-trivy-2026-10-30/README.md); sin actualizaciones automáticas.
La etapa anterior de [paginación tuvo 130 pruebas aprobadas el
30 de octubre de 2026](docs/continuidad-paginacion-2026-10-30.md).

## Preparación

Desde esta carpeta, con Python 3.14:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
```

Reemplazar la contraseña de `.env` por el valor generado. Si `.env` ya existe,
conservarlo: cambiar la contraseña no modifica las credenciales de un volumen
PostgreSQL ya inicializado. No subir este archivo a Git.

## Base de datos

En este equipo se utiliza Podman con el proveedor `podman-compose`.
Para iniciar y comprobar la base existente:

```sh
source .venv/bin/activate
podman-compose up -d
podman exec medinet_pac_db pg_isready -U medinet_pac -d medinet_pac
podman-compose ps
```

El arranque habitual no requiere migraciones. Los comandos de migración de la
sección siguiente se reservan para cambios de esquema deliberados.

`pg_isready` comprueba disponibilidad, no la autenticación del usuario limitado.
Usar un solo motor de contenedores para administrar esta base.
PostgreSQL se publica en `127.0.0.1:5433`, con volumen persistente y red propia.
El servicio local que pueda ocupar el puerto 5432 no necesita detenerse.

## API

```sh
source .venv/bin/activate
python -m app.run_local
```

- Salud: http://127.0.0.1:8000/health devuelve `{"status":"ok"}`.
- Swagger: http://127.0.0.1:8000/docs.

`/health` solo comprueba el proceso HTTP: no abre una conexión ni verifica PostgreSQL.
La instancia candidata actual utiliza el puerto 8001; el puerto predeterminado es 8000.

## Alcance de la tabla

`patients` tiene 12 columnas, RUN único, índice compuesto de apellidos y reglas
CHECK para el formato del RUN y las cuatro previsiones admitidas. La validación
del dígito verificador corresponde al backend del paso 3. Los campos y largos
propuestos en el documento todavía deben confirmarse con el docente.

`python -m app.crear_tablas` conserva el comando del Paso 2 y ahora ejecuta
`alembic upgrade head`. No usar `create_all` para actualizar el esquema.
`updated_at` se actualiza mediante SQLAlchemy; no hay un trigger para SQL directo.
El rol limitado `medinet_pac_api` ya está aplicado en desarrollo; véase el estado
de verificación de la transición más abajo.

Para detener sin borrar los datos: `podman-compose stop`.
Evitar `down -v`: elimina el volumen y sus datos.

## Migraciones del Paso 3

Desde la raíz de `MediNet-Core`, con el `.env` existente:

```sh
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
alembic current
alembic check
```

No hace falta recrear la base ni su volumen. `0001` crea la tabla si falta o
comprueba tipos, nulabilidad, PK, generación del ID, fechas predeterminadas,
UNIQUE, CHECK e índice de apellidos antes de adoptar la tabla del Paso 2.
Una incompatibilidad detiene la migración: no se usa `stamp` a ciegas.
`0002` agrega índices `lower(apellido_paterno) text_pattern_ops` y
`lower(apellido_materno) text_pattern_ops`; conserva el índice compuesto previo.
La creación de índices es transaccional y puede bloquear escrituras brevemente;
planificar una ventana si la tabla crece. El downgrade de `0001` está bloqueado
para impedir que elimine pacientes. Las migraciones requieren conexión online.

## Contrato REST

Swagger está en `/docs` y OpenAPI en `/openapi.json`. No se añadió prefijo de
versión porque no existe un acuerdo de integración que lo requiera.

| Ruta | Resultado |
| --- | --- |
| `POST /patients` | 201, paciente y cabecera Location; 409 por RUN ocupado; 422 por entrada inválida |
| `GET /patients` | 200 con `items`, `total`, `page`, `page_size` |
| `GET /patients/{patient_id}` | 200, 404 por ausencia, 422 por ID no positivo o no entero |
| `PATCH /patients/{patient_id}` | 200, 404, 409 o 422; solo actualiza lo enviado |
| `POST /patients/validate-run` | 200 con `valid` y `normalized_run`; 422 por JSON o tipo incorrecto |
| `GET /health` | 200 con `{"status":"ok"}`; comprueba el proceso |

Los errores no devuelven entradas personales, SQL ni detalles de conexión.
Un fallo de conectividad devuelve 503; otros fallos de integridad al guardar
devuelven 500 genérico. Solo `patients_run_key` con SQLSTATE 23505 devuelve 409.
La restricción UNIQUE resuelve duplicados concurrentes; no se depende de una
consulta previa. Cada solicitud tiene una sesión síncrona con cierre garantizado.

Los filtros `run`, `apellido_paterno`, `apellido_materno` y `prevision` se combinan
con AND. RUN es exacto y normalizado; apellidos usan prefijo literal, sin distinguir
mayúsculas pero distinguiendo tildes. `%`, `_` y `\` no amplían la búsqueda.
Orden estable por apellido paterno, materno (`NULL` al final) e ID. `page` tiene
valor predeterminado 1 y rango 1–100000; `page_size` tiene valor predeterminado
20 y rango 1–100. Valores fuera de esos rangos o no enteros devuelven 422,
incluidas páginas enormes, antes de ejecutar la consulta de listado.
Una página permitida que supera los resultados disponibles devuelve 200 con
`items: []`, conserva el `total` de coincidencias y refleja `page` y `page_size`.
Una búsqueda sin coincidencias devuelve el mismo contrato con `total: 0`.
El máximo de página es una política de la API para acotar OFFSET a 9999900;
no garantiza el rendimiento de páginas profundas.

RUN admite cuerpo de 7 u 8 dígitos, con o sin puntos de miles y guion; persiste
sin puntos y con DV mayúsculo. No admite letras en el cuerpo, ceros iniciales,
espacios interiores ni otros separadores. Módulo 11 no comprueba identidad real.
Nombres y apellidos usan NFC, recorte y espacios colapsados; conservan tildes, ñ,
apóstrofos y guiones. Controles, texto obligatorio vacío y campos extra se rechazan.
Previsión se normaliza a las cuatro opciones mayúsculas. No se admiten fechas
futuras. Email valida sintaxis sin consultar DNS y conserva la parte local;
el dominio se normaliza a minúsculas. Teléfono permite presentación con `+`,
espacios, paréntesis o guiones y guarda solo 1–15 dígitos, sin agregar país.
Los opcionales se omiten o se envían como `null`; texto vacío no sustituye a `null`.

PATCH rechaza `{}`, campos extra, `null` en obligatorios e intentos de escribir
ID o marcas de tiempo. Revalida explícitamente el estado resultante antes de
guardar. Ausencia conserva el valor; `null` borra solo campos opcionales.

## Recorrido exacto en Swagger con datos sintéticos

1. Ejecutar las migraciones anteriores y `python -m app.run_local`.
   Abrir http://127.0.0.1:8000/docs. En cada operación usar **Try it out** y **Execute**.
2. En `POST /patients/validate-run`, enviar `{"run":"12.345.678-5"}`:
   esperar 200, `valid: true` y `normalized_run: "12345678-5"`.
   Con `{"run":"12345678-4"}`, esperar 200, `valid: false` y `normalized_run: null`.
3. En `POST /patients`, enviar este registro exclusivamente sintético:

```json
{
  "run": "12.345.678-5",
  "nombres": "Ana María Sintética",
  "apellido_paterno": "Muñoz",
  "apellido_materno": "O'Neill",
  "fecha_nacimiento": "1990-05-10",
  "prevision": " fonasa ",
  "email": "Ana.PAC@EXAMPLE.COM",
  "telefono": "+56 (9) 1234-5678",
  "direccion": "Calle Sintética 123"
}
```

4. Esperar 201 y copiar el `id` devuelto y la cabecera `Location`.
   El RUN será `12345678-5`, la previsión `FONASA` y el teléfono `56912345678`.
   Repetir con RUN `123456785`: esperar 409. Si el registro ya existía de una
   demostración anterior, el primer POST también devuelve 409; consultar
   `GET /patients` con `run=12.345.678-5` para recuperar su ID sin borrar nada.
5. En `GET /patients`, completar `apellido_paterno=mUÑ`, `apellido_materno=o'`,
   `prevision=FONASA`, `page=1`, `page_size=1`. Dejar `run` sin enviar.
   Esperar 200 con el paciente en `items` y metadatos. `apellido_paterno=Munoz`
   no coincide con Muñoz. Con `page=999`, esperar `items: []`.
6. En `GET /patients/{patient_id}`, enviar el ID copiado: esperar 200.
7. En `PATCH /patients/{patient_id}`, enviar `{"telefono":"987654321","email":null}`:
   esperar 200 con teléfono nuevo, email nulo y nombres/apellidos conservados.
8. Crear otro sintético repitiendo el JSON del punto 3 con `run: "1.000.005-k"`.
   Copiar su ID. Intentar cambiar su RUN mediante PATCH a `12345678-5`: esperar
   409. En el paciente original se puede cambiar RUN a `1.000.013-0` y comprobar
   DV 0; evitar ese cambio si se quiere repetir literalmente la demostración.
9. Probar POST con `run: "12345678-4"`, `prevision: "OTRA"`, fecha futura o
   `id: 1`: esperar 422. PATCH con `{}` o `{"nombres":null}` también devuelve 422.
10. GET con ID `0` devuelve 422. Para comprobar 404, escoger un ID positivo que
    no exista (en una demo vacía, por ejemplo `999999999`).

Los RUN son vectores de prueba, no una acreditación de personas reales.
Este recorrido guarda los registros sintéticos creados; no incluye borrado.
El comando desactiva el access log para evitar registrar RUN u otros filtros en URLs.

## Credenciales separadas y estado de la transición

La API exige `PAC_DB_USER` y `PAC_DB_PASSWORD`, además de `POSTGRES_DB`,
`DB_HOST` y `DB_PORT`. No carga `.env` ni usa credenciales administrativas como
alternativa. Los modelos se pueden importar sin credenciales y sin crear motores.
Alembic y `python -m app.crear_tablas` usan una conexión administrativa independiente:
leen `.env` sin exportarlo al entorno, con prioridad de las variables exportadas.
No ejecutar esos comandos desde el proceso de API ni con su usuario limitado.

Arranque local desde la raíz del proyecto:

```sh
.venv/bin/python -m app.run_local
```

Solicita la contraseña con entrada oculta; nunca la incluye en argumentos ni la
imprime. Si no hay terminal segura, aborta. Por defecto usa `medinet_pac_api`, base
`medinet_pac`, `127.0.0.1:5433` y API en `127.0.0.1:8000`. Los ajustes no secretos
se pueden indicar con `--db-user`, `--db-name`, `--db-host`, `--db-port` y `--port`.
El hijo no recibe las variables POSTGRES administrativas de la sesión. El secreto
vive en memoria y en el entorno del hijo. Esto separa credenciales; no impide que
un proceso del mismo usuario del sistema lea archivos o procesos a los que tenga
acceso. Mantener `.env` fuera de Git y con permisos 600; no copiarlo a salidas.

### Estado comprobado el 26 de octubre de 2026

- El rol `medinet_pac_api` ya fue aplicado a desarrollo. La recuperación anterior
  verificó sus permisos efectivos mediante consultas de metadatos como ese rol
  por conexión local dentro del contenedor. Esto no verifica una contraseña TCP.
- Permisos verificados: CONNECT, USAGE del esquema, SELECT/INSERT/UPDATE de
  `patients` y USAGE de su secuencia. Sin CREATE, TEMPORARY, DELETE, TRUNCATE,
  REFERENCES, TRIGGER, MAINTAIN, SELECT/UPDATE de la secuencia ni acceso a
  `alembic_version`; sin membresías ni atributos administrativos. Los propietarios
  permanecen intactos. No volver a ejecutar el SQL de aplicación del rol.
- El usuario informó haber configurado manualmente la contraseña y arrancado
  `.venv/bin/python -m app.run_local --port 8001`.
- En esta continuación se comprobaron HTTP 200 y `{"status":"ok"}` en
  `http://127.0.0.1:8001/health`, y las cinco operaciones PAC en OpenAPI:
  POST/GET `/patients`, GET/PATCH `/patients/{patient_id}` y
  POST `/patients/validate-run`. No se invocaron operaciones que lean pacientes.
- El código del lanzador, para ese comando, selecciona `medinet_pac_api`, base
  `medinet_pac`, destino TCP `127.0.0.1:5433`; reemplaza la configuración de conexión
  del hijo y excluye las credenciales administrativas heredadas. Se revisó el
  código sin leer el entorno secreto del proceso activo.
- **Conexión TCP independiente con contraseña: autenticación rechazada.**
  Se intentó conectar desde el host a `127.0.0.1:5433` como `medinet_pac_api`,
  base `medinet_pac`, con entrada oculta. PostgreSQL rechazó la contraseña
  proporcionada; no se ejecutaron las consultas de identidad ni de permisos TCP.
  El puerto 5433 estaba accesible y `/health` en 8001 seguía respondiendo 200.
  No se cambiaron credenciales. Falta verificar manualmente la credencial correcta.
- **Conexión realmente utilizada por la API: no comprobada.** Salud y OpenAPI no
  usan PostgreSQL. Una conexión independiente tampoco demuestra este punto.
- Las **119 pruebas aprobadas** fueron reportadas en una ejecución anterior.
  No se repitió la suite en esta continuación ni se generó un informe nuevo.

Arranque de la candidata y comprobaciones HTTP habituales, desde esta carpeta:

```sh
.venv/bin/python -m app.run_local --port 8001
# En otra terminal:
curl --fail http://127.0.0.1:8001/health
curl --fail http://127.0.0.1:8001/openapi.json
```

La contraseña se introduce solo en el prompt oculto del lanzador. No cambiar
`.env` ni usar credenciales administrativas para el arranque habitual.

No se requieren migraciones, cambios de propiedad ni permisos de administrador
para el rol de API. Mantener Alembic en 0002 hasta una evolución de esquema real.
Los permisos se revisan explícitamente para nuevas tablas; no hay GRANT ALL ni
concesiones automáticas sobre todas las tablas futuras.

### Reversión futura

Si falla la transición, conservar la instancia previa o restaurar los archivos
anteriores y su arranque administrativo anterior. Reiniciar solo la API candidata
cuando corresponda, sin tocar PostgreSQL ni datos. El administrador y las
propiedades permanecen intactos. Con el código nuevo también se puede volver
explícitamente al administrador, de forma temporal, mediante
`.venv/bin/python -m app.run_local --db-user medinet_pac --port 8001`, introduciendo
su contraseña en el prompt. Esto recupera los privilegios anteriores, no es un
fallback automático ni la configuración final recomendada. No exige editar .env.
Si es necesario restituir exactamente el permiso
previo, ejecutar como administrador `GRANT TEMPORARY ON DATABASE medinet_pac TO
PUBLIC;`. No borrar el rol nuevo, tablas ni volúmenes para revertir la aplicación.

PUBLIC también permite CONNECT a otras bases de la instancia y TEMPORARY en
`postgres`; esta separación limita las operaciones de PAC en su base, no establece
un aislamiento completo entre bases. Las reglas locales trust del contenedor
siguen sin cambios. Limitar PostgreSQL no autentica ni autoriza personas en HTTP.

## Pruebas con PostgreSQL exclusivo

Con las dependencias existentes en `.venv` y Podman disponible:

```sh
.venv/bin/python scripts/run_pac_tests.py
```

El runner usa exclusivamente la imagen local `postgres:18-alpine` con
`--pull=never`. Crea `medinet_pac_credentials_test`, puerto
`127.0.0.1:55434`, almacenamiento tmpfs sin volúmenes/bind mounts, administrador
`pac_test_admin` y API `pac_test_api`, con contraseñas aleatorias efímeras que no
se imprimen ni se guardan en archivos. No usa el `.env` de desarrollo.

Antes de migrar o limpiar verifica ID del contenedor, etiqueta, puerto, mounts,
identificador del clúster, base, usuario y marcador exclusivo de esta ejecución.
Sin esos datos pytest aborta antes de importar la aplicación. El administrador
migra y trunca únicamente los datos ficticios; las solicitudes usan el rol limitado.
Las pruebas de migración crean bases adicionales solo en ese mismo clúster.
`crear_tablas.py` se comprueba contra el administrador de pruebas, no desarrollo.

El runner conserva el contenedor para inspección. No reutiliza uno existente con
el mismo nombre. Para repetir desde cero, comprobar primero su etiqueta
`medinet.task=pac-credentials-tests`, identidad y puerto con Podman, y eliminar
**solo ese contenedor creado por esta tarea**, mediante
`podman rm -f medinet_pac_credentials_test`; luego repetir el runner. No usar
limpiezas globales, borrar volúmenes ni actuar sobre medinet_pac_db o el contenedor
antiguo medinet_pac_test. Al no persistir las contraseñas, cada ejecución nueva
parte de su propio servidor temporal.

Se prueban el contrato PAC, persistencia en sesión nueva, concurrencia, rollback,
permisos efectivos y denegaciones reales (incluidas operaciones destructivas
exclusivamente en pruebas), rechazo de contraseña incorrecta y evidencia de
`current_user` en las consultas que atienden POST/GET/PATCH.

## Pendientes de integración

Frontend y comprobación de XSS en un navegador quedan para la próxima iteración.
Ahora las etiquetas se transportan como JSON; el futuro frontend deberá usar
`textContent` o autoescape al mostrarlas. No se verificó ejecución de interfaz.
El entorno local de API y PostgreSQL en contenedores ya fue verificado con Podman;
véase [su guía independiente](docs/contenedores-locales.md). Quedan pipeline, SAST/SCA, AWS, HTTPS, autenticación y
autorización de usuarios HTTP y contrato con los demás módulos. El rol PostgreSQL
limitado ya está aplicado; no sustituye la autenticación ni la autorización HTTP.
Mantener esta demo local con datos sintéticos. `patient.id` entero es la referencia
estable propuesta; no se añadieron tablas ni flujos de otros módulos.

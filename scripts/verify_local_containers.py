"""Comprobaciones reales solo del Compose local exclusivo, con datos sintéticos."""
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'medinet-pac-local-20261030'
BASE = 'http://127.0.0.1:18081'
STATE = ROOT / '.local-containers' / 'patient.json'


def podman(*args):
    result = subprocess.run(['podman', *args], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError('Falló una consulta de verificación Podman; no se vuelca su salida.')
    return result.stdout + result.stderr if args[0] == 'logs' else result.stdout


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def request(path, method='GET', body=None, expected=200):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={'Content-Type': 'application/json'})
    try:
        response = urllib.request.urlopen(req, timeout=5)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        require(response.status == expected, 'HTTP inesperado: ' + method + ' ' + path)
        return json.load(response)


def main():
    require(sys.argv[1:] in (['create'], ['persist']), 'Usar create o persist')
    infos = {name: json.loads(podman('inspect', PREFIX + '-' + name))[0]
             for name in ('db', 'api')}
    for name, info in infos.items():
        require(info['State']['Running'], name + ' no está iniciado')
    require(not infos['db']['HostConfig'].get('PortBindings'), 'BD con puerto publicado')
    require(infos['api']['HostConfig']['PortBindings']['8000/tcp'] ==
            [{'HostIp': '127.0.0.1', 'HostPort': '18081'}], 'Publicación API incorrecta')
    require(infos['api']['Config']['User'] == '10001:10001', 'API debe ser no root')
    require(not any(value.startswith(('POSTGRES_PASSWORD=', 'POSTGRES_USER='))
                    for value in infos['api']['Config']['Env']), 'Credenciales admin en API')
    mounts = infos['db']['Mounts']
    require(any(m.get('Name') == PREFIX + '-pgdata' and m['Destination'] == '/var/lib/postgresql'
                for m in mounts), 'Volumen exclusivo no encontrado')
    for _ in range(30):
        try:
            require(request('/health') == {'status': 'ok'}, 'Salud incorrecta')
            break
        except (OSError, RuntimeError):
            time.sleep(1)
    else:
        raise RuntimeError('API no disponible')
    paths = request('/openapi.json')['paths']
    require(all(method in paths.get(path, {}) for method, path in [
        ('post', '/patients'), ('get', '/patients'), ('get', '/patients/{patient_id}'),
        ('patch', '/patients/{patient_id}'), ('post', '/patients/validate-run')]),
        'Faltan operaciones PAC')
    if sys.argv[1] == 'create':
        require(not STATE.exists(), 'Evidencia previa existente; usar persist')
        require(request('/patients/validate-run', 'POST', {'run': '12.345.678-5'}) ==
                {'valid': True, 'normalized_run': '12345678-5'}, 'Validación RUN incorrecta')
        payload = {
            'run': '12.345.678-5', 'nombres': 'Paciente Ficticio Local',
            'apellido_paterno': 'Sintético', 'apellido_materno': 'Contenedores',
            'fecha_nacimiento': '1990-05-10', 'prevision': 'FONASA',
        }
        existing = request('/patients?run=12345678-5')
        if existing['total']:
            require(existing['total'] == 1 and all(existing['items'][0][key] == value
                    for key, value in payload.items() if key != 'run'),
                    'El RUN existente no corresponde al paciente sintético de esta verificación')
            patient = existing['items'][0]
        else:
            patient = request('/patients', 'POST', payload, expected=201)
        patient = request('/patients/' + str(patient['id']), 'PATCH', {'telefono': '56911112222'})
    else:
        saved = json.loads(STATE.read_text())
        patient = saved['patient']
        require(all(infos[name]['Id'] != saved['containers'][name] for name in infos),
                'Los dos contenedores deben haberse recreado')
        require(json.loads(podman('volume', 'inspect', PREFIX + '-pgdata'))[0]['CreatedAt'] ==
                saved['volume_created_at'], 'El volumen debe conservarse')
    require(request('/patients/' + str(patient['id'])) == patient, 'Paciente no conservado')
    listed = request('/patients?run=12345678-5')
    require(listed['total'] == 1 and listed['items'] == [patient], 'Listado incorrecto')
    request('/patients?page=9223372036854775808', expected=422)
    # Las conexiones del servidor HTTP permanecen en su pool tras POST/GET/PATCH.
    # pg_stat_activity demuestra el usuario de esas sesiones reales, sin exponer consultas.
    rows = json.loads(podman('exec', PREFIX + '-db', 'psql', '-U', 'pac_local_admin',
        '-d', 'pac_local', '-Atc', "SELECT coalesce(json_agg(row_to_json(s)), '[]') FROM "
        "(SELECT usename, host(client_addr) AS client_addr, application_name FROM pg_stat_activity "
        "WHERE datname='pac_local' AND backend_type='client backend' AND client_addr IS NOT NULL) s"))
    addresses = {net['IPAddress'] for net in infos['api']['NetworkSettings']['Networks'].values()}
    require(rows and all(row['usename'] == 'pac_local_api' and row['client_addr'] in addresses
                        for row in rows), 'La conexión real HTTP no acredita el rol limitado')
    permissions = podman('exec', PREFIX + '-db', 'psql', '-U', 'pac_local_admin',
        '-d', 'pac_local', '-Atc', "SELECT NOT (rolsuper OR rolcreatedb OR rolcreaterole "
        "OR rolreplication OR rolbypassrls) AND "
        "has_table_privilege('pac_local_api','patients','SELECT') AND "
        "has_table_privilege('pac_local_api','patients','INSERT') AND "
        "has_table_privilege('pac_local_api','patients','UPDATE') AND "
        "NOT has_table_privilege('pac_local_api','patients','DELETE') AND "
        "NOT has_table_privilege('pac_local_api','patients','TRUNCATE') AND "
        "NOT has_table_privilege('pac_local_api','alembic_version','SELECT') AND "
        "NOT has_schema_privilege('pac_local_api','public','CREATE') AND "
        "NOT has_database_privilege('pac_local_api','pac_local','TEMPORARY') "
        "FROM pg_roles WHERE rolname='pac_local_api'").strip()
    require(permissions == 't', 'Privilegios efectivos inesperados para la API')
    require(podman('exec', PREFIX + '-api', 'python', '-c',
        "import os; from pathlib import Path; assert os.getuid()==10001; "
        "assert not Path('/run/secrets/admin_password').exists(); "
        "assert not Path('/srv/pac/.env').exists(); assert not Path('/srv/pac/.venv').exists(); "
        "import fastapi,pydantic,sqlalchemy,psycopg,platform; "
        "print(platform.python_version(),fastapi.__version__,pydantic.__version__,sqlalchemy.__version__,psycopg.__version__)"
    ).strip(), 'Inspección runtime fallida')
    # Capturar los secretos sin mostrarlos, solo para buscar coincidencias en logs y metadatos.
    passwords = []
    for suffix in ('admin', 'api'):
        secret = json.loads(podman('secret', 'inspect', '--showsecret', PREFIX + '-' + suffix))[0]
        passwords.append(secret['SecretData'])
    logs = ''.join(podman('logs', PREFIX + '-' + name) for name in ('db', 'api'))
    require('SCRAM-SHA-256$' not in logs, 'Verificador de contraseña encontrado en logs')
    metadata = json.dumps(infos) + podman('image', 'inspect', 'localhost/medinet-pac:local-20261030')
    for password in passwords:
        require(password not in logs and urllib.parse.quote(password, safe='') not in logs,
                'Secreto encontrado en logs; no se imprime')
        require(password not in metadata, 'Secreto encontrado en metadatos; no se imprime')
    if sys.argv[1] == 'create':
        STATE.parent.mkdir(mode=0o700, exist_ok=True)
        STATE.write_text(json.dumps({'patient': patient,
            'containers': {name: info['Id'] for name, info in infos.items()},
            'volume_created_at': json.loads(podman('volume', 'inspect', PREFIX + '-pgdata'))[0]['CreatedAt']}, indent=2))
        STATE.chmod(0o600)
    print('PASS: servicios, localhost, OpenAPI, HTTP/BD, rol limitado, no root y logs revisados.')
    print('PASS: paciente ficticio creado y consultado.' if sys.argv[1] == 'create'
          else 'PASS: paciente íntegro después de recrear ambos contenedores y conservar volumen.')


if __name__ == '__main__':
    main()

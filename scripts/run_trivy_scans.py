"""Repetir análisis locales con Trivy y bases ya verificadas; no descarga ni modifica servicios."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / '.local-containers/trivy-audit-2026-10-30'
REPORTS = ROOT / 'docs/auditoria-trivy-2026-10-30'


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def verify_inputs():
    def check(path, expected):
        with path.open('rb') as file:
            actual = hashlib.file_digest(file, 'sha256').hexdigest()
        if actual != expected:
            raise SystemExit('Entrada de auditoría modificada: ' + str(path))

    integrity = json.loads((REPORTS / 'integridad.json').read_text())
    check(WORK / 'bin/trivy', integrity['binary_sha256'])
    for image in json.loads((REPORTS / 'images.json').read_text()):
        check(ROOT / image['archive'], image['archive_sha256'])
    databases = json.loads((REPORTS / 'databases.json').read_text())
    check(WORK / 'cache/db/trivy.db', databases['db_sha256'])
    for name, digest in databases['policy_files'].items():
        check(WORK / 'cache/policy' / name, digest)
    for name, digest in json.loads((REPORTS / 'source-sha256.json').read_text()).items():
        check(WORK / 'project' / name, digest)
    check(WORK / 'development/requirements.txt',
          json.loads((REPORTS / 'development-input.json').read_text())['sha256'])


def main():
    os.chdir(ROOT)
    verify_inputs()
    if sys.argv[1:] == ['--verify-inputs']:
        print('PASS: binario, imágenes, bases y snapshots coinciden con los hashes registrados.')
        return
    # No heredar configuración TRIVY que pudiera activar servidor remoto o filtros.
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(('TRIVY_', 'POSTGRES_', 'PAC_', 'DB_'))}
    common = ['--disable-telemetry', '--skip-version-check', '--offline-scan',
              '--skip-db-update', '--skip-java-db-update', '--skip-check-update',
              '--ignorefile', '', '--secret-config', '', '--exit-code', '0',
              '--include-non-failures', '--format', 'json']
    commands = [
        ('api', ['image', '--input', str(WORK / 'api.tar'), '--scanners', 'vuln,secret',
                 '--image-config-scanners', 'misconfig,secret']),
        ('postgres', ['image', '--input', str(WORK / 'postgres.tar'), '--scanners', 'vuln,secret',
                      '--image-config-scanners', 'misconfig,secret']),
        ('project', ['fs', '--scanners', 'vuln,misconfig,secret', str(WORK / 'project')]),
        ('development', ['fs', '--scanners', 'vuln,misconfig,secret', str(WORK / 'development')]),
    ]
    selected = set(sys.argv[1:]) or {name for name, _ in commands}
    if selected - {name for name, _ in commands}:
        raise SystemExit('Objetivos permitidos: api postgres project development')
    journal_path = REPORTS / 'commands.json'
    journal = json.loads(journal_path.read_text()) if journal_path.exists() else []
    for name, args in commands:
        if name not in selected:
            continue
        raw = WORK / (name + '.json')
        command = [str(WORK / 'bin/trivy'), '--config', '', '--cache-dir', str(WORK / 'cache'),
                   '--timeout', '10m', *args, *common, '--output', str(raw)]
        started = now()
        with (REPORTS / (name + '.stdout.log')).open('w') as out, (
                REPORTS / (name + '.stderr.log')).open('w') as err:
            result = subprocess.run(command, env=env, stdout=out, stderr=err)
        record = {'target': name, 'command': command, 'started_at': started,
                  'finished_at': now(), 'exit_code': result.returncode,
                  'report_generated': raw.exists()}
        if result.returncode == 0 and raw.exists():
            data = json.loads(raw.read_text())
            # No publicar valores hallados por el detector de secretos, ni en ejemplos.
            for item in data.get('Results', []):
                for secret in item.get('Secrets', []):
                    for key in ('Match', 'Code'):
                        if key in secret:
                            secret[key] = '[REDACTED: raw report retained privately]'
            (REPORTS / (name + '.json')).write_text(json.dumps(data, indent=2) + '\n')
            record['json_valid'] = True
        journal.append(record)
        (REPORTS / 'commands.json').write_text(json.dumps(journal, indent=2) + '\n')
        print(name + ': exit=' + str(result.returncode) + '; JSON=' + str(raw.exists()), flush=True)
    if any(x['exit_code'] != 0 for x in journal):
        raise SystemExit(1)


if __name__ == '__main__':
    main()

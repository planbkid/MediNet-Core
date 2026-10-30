import hashlib,json,tarfile,urllib.request
from pathlib import Path
p=Path('.local-containers/trivy-audit-2026-10-30')
j=json.loads((p/'release.json').read_text())
assert j['tag_name']=='v0.76.1'
names=['trivy_0.76.1_Linux-64bit.tar.gz','trivy_0.76.1_checksums.txt','trivy_0.76.1_Linux-64bit.tar.gz.sigstore.json']
record=[]
for name in names:
 a=next(a for a in j['assets'] if a['name']==name)
 data=urllib.request.urlopen(a['browser_download_url'],timeout=120).read()
 digest='sha256:'+hashlib.sha256(data).hexdigest()
 assert digest==a['digest'], 'GitHub asset digest mismatch'
 (p/name).write_bytes(data)
 record.append({'name':name,'url':a['browser_download_url'],'sha256':digest,'github_asset_digest_verified':True})
checks=(p/'trivy_0.76.1_checksums.txt').read_text().splitlines()
line=next(x for x in checks if x.split()[-1].lstrip('*')==names[0])
assert line.split()[0]==record[0]['sha256'].split(':')[1], 'Official checksum mismatch'
(p/'bin').mkdir(exist_ok=True)
with tarfile.open(p/names[0]) as tar:
 member=tar.getmember('trivy')
 assert member.isfile()
 (p/'bin/trivy').write_bytes(tar.extractfile(member).read())
(p/'bin/trivy').chmod(0o700)
result={'release':j['tag_name'],'release_url':j['html_url'],'published_at':j['published_at'],'downloads':record,'official_checksum_verified':True,'binary_sha256':hashlib.sha256((p/'bin/trivy').read_bytes()).hexdigest(),'sigstore_signature_verified':False,'note':'Sigstore bundle retained, cosign unavailable; verified official checksums and GitHub asset digests over HTTPS.'}
Path('docs/auditoria-trivy-2026-10-30/integridad.json').write_text(json.dumps(result,indent=2)+'\n')
print('Trivy 0.76.1: SHA256 oficial y digests GitHub verificados; binario aislado.')

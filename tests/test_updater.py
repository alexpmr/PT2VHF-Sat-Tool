from dataclasses import replace
from pathlib import Path
import hashlib
import zipfile
import pytest

from sat_tool.updater import (AvailableUpdate, select_release, version_tuple,
                              parse_checksum_manifest, safe_extract_portable, install_flavor)
from sat_tool.satellite_info import orbital_characteristics, operational_characteristics, characteristics_text


def sample_release(ver='0.1.3', variant='Win11-x64', kind='Portable', **changes):
    name=f'PT2VHF-Sat-Tool-v{ver}-{variant}-{kind}.exe'
    data={'schema':1,'source':'https://www.pt2vhf.com','product':'sat','status':'available',
          'version':ver,'notes':'Melhorias importantes','page':'https://www.pt2vhf.com/sat',
          'files':[{'name':name,'size':1234,'sha256':'a'*64,
                    'url':'https://www.pt2vhf.com/downloads/sat-tool/'+name}]}
    data.update(changes)
    return data


def test_version_semver_and_no_downgrade():
    assert version_tuple('v0.1.12')>(version_tuple('0.1.9'))
    assert version_tuple('v0.1.2-rc1') is None
    assert select_release(sample_release('0.1.1'), '0.1.2','Win11-x64','Portable') is None
    assert select_release(sample_release('0.1.2'), '0.1.2','Win11-x64','Portable') is None


def test_release_picks_exact_variant_and_asset():
    r=select_release(sample_release('0.1.3'),'0.1.2','Win11-x64','Portable')
    assert r.version=='0.1.3' and r.expected_sha256=='a'*64 and r.expected_size==1234
    assert r.url.startswith('https://www.pt2vhf.com/downloads/sat-tool/')
    assert select_release(sample_release(),'0.1.2','Win7-x86','Portable') is None
    assert select_release(sample_release(),'0.1.2','Win11-x64','Setup') is None


@pytest.mark.parametrize('url', [
    'http://www.pt2vhf.com/downloads/sat-tool/PT2VHF-Sat-Tool-v0.1.3-Win11-x64-Portable.exe',
    'https://github.com/alexpmr/PT2VHF-Sat-Tool/releases/download/v0.1.3/PT2VHF-Sat-Tool-v0.1.3-Win11-x64-Portable.exe',
    'https://evil.pt2vhf.com/downloads/sat-tool/PT2VHF-Sat-Tool-v0.1.3-Win11-x64-Portable.exe',
    'https://www.pt2vhf.com/downloads/aprs-client/PT2VHF-Sat-Tool-v0.1.3-Win11-x64-Portable.exe',
    'https://www.pt2vhf.com/downloads/sat-tool/PT2VHF-Sat-Tool-v0.1.3-Win11-x64-Portable.exe?x=1',
])
def test_release_rejects_assets_outside_site(url):
    bad=sample_release()
    bad['files'][0]['url']=url
    assert select_release(bad,'0.1.2','Win11-x64','Portable') is None


def test_release_requires_size_and_sha256():
    for field, value in (('sha256','abc'),('size',0),('size','1234')):
        bad=sample_release()
        bad['files'][0][field]=value
        assert select_release(bad,'0.1.2','Win11-x64','Portable') is None


def test_manifest_must_be_sat_product_from_site():
    with pytest.raises(ValueError):
        select_release(sample_release(product='aprs'),'0.1.2','Win11-x64','Portable')
    with pytest.raises(ValueError):
        select_release(sample_release(source='https://github.com'),'0.1.2','Win11-x64','Portable')
    assert select_release(sample_release(status='unpublished',version=None),'0.1.2','Win11-x64','Portable') is None


def test_updater_never_contacts_github():
    import sat_tool.updater as updater
    source=Path(updater.__file__).read_text(encoding='utf-8')
    assert 'github' not in source.casefold()
    assert updater.UPDATE_API=='https://www.pt2vhf.com/update.php?product=sat'


def test_download_rejects_hash_mismatch(monkeypatch):
    import sat_tool.updater as updater
    payload=b'MZ-not-the-published-file'
    upd=select_release(sample_release(),'0.1.2','Win11-x64','Portable')
    upd=replace(upd, expected_size=len(payload))
    class Resp:
        is_redirect=False; headers={'Content-Length':str(len(payload))}
        def __enter__(self): return self
        def __exit__(self,*a): return False
        def raise_for_status(self): pass
        def iter_content(self,chunk_size): yield payload
    monkeypatch.setattr(updater.requests,'get',lambda *a,**k: Resp())
    with pytest.raises(ValueError,match='SHA-256'):
        updater.download_update(upd)
    good=replace(upd, expected_sha256=hashlib.sha256(payload).hexdigest())
    assert updater.download_update(good).read_bytes()==payload


def test_checksum_manifest_exact_filename():
    d='0123456789abcdef'*4
    assert parse_checksum_manifest(f'{d}  Setup.exe', 'Setup.exe')==d
    assert parse_checksum_manifest(f'{d}  Old.exe', 'Setup.exe') is None


def test_safe_portable_archive_requires_flag_and_rejects_traversal(tmp_path):
    good=tmp_path/'good.zip'
    with zipfile.ZipFile(good,'w') as z:
        z.writestr('PT2VHF-Sat-Tool.exe',b'demo')
        z.writestr('portable.flag',b'')
        z.writestr('_internal/library.txt',b'lib')
    out=safe_extract_portable(good)
    assert (out/'PT2VHF-Sat-Tool.exe').read_bytes()==b'demo'
    bad=tmp_path/'bad.zip'
    with zipfile.ZipFile(bad,'w') as z:
        z.writestr('../evil.txt','unsafe')
        z.writestr('PT2VHF-Sat-Tool.exe','exe')
        z.writestr('portable.flag','')
    with pytest.raises(ValueError,match='inseguro'):
        safe_extract_portable(bad)
    data=tmp_path/'data.zip'
    with zipfile.ZipFile(data,'w') as z:
        z.writestr('data/settings.json','overwrite!')
    with pytest.raises(ValueError,match='inseguro'):
        safe_extract_portable(data)


def test_updater_disabled_outside_packaged_windows():
    assert install_flavor('PySide2',frozen=False) is None


def test_orbital_omm_characteristics():
    sample={'OBJECT_NAME':'TEST-SAT','NORAD_CAT_ID':99910,
            'INCLINATION':97.56,'MEAN_MOTION':14.4,'ECCENTRICITY':0.001}
    o=orbital_characteristics(sample)
    assert o['period_min']==100.0
    assert o['inclination_deg']==97.56
    assert 'TEST-SAT' in characteristics_text(sample,[])
    op=operational_characteristics([{'status':'active','downlink_low':435200000,'mode':'FM','alive':True},
                                   {'status':'inactive','downlink_low':435100000,'mode':'CW','alive':False}])
    assert op['modes']==['FM']
    assert op['downlinks_mhz']==[435.2]
    assert op['status']=='Canais publicados'


def test_tle_orbital_characteristics():
    tle='2 25544  51.6410  70.0000 0004000  20.0000 330.0000 15.50000000000001'
    o=orbital_characteristics({'NORAD_CAT_ID':25544, 'OBJECT_NAME':'TEST','TLE_LINE2':tle})
    assert o['period_min']==pytest.approx(1440/15.5)
    assert o['eccentricity']==pytest.approx(0.0004)

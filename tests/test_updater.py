from dataclasses import replace
from pathlib import Path
import hashlib
import zipfile
import pytest

from sat_tool.updater import (AvailableUpdate, select_release, version_tuple,
                              parse_checksum_manifest, safe_extract_portable, install_flavor)
from sat_tool.satellite_info import orbital_characteristics, operational_characteristics, characteristics_text


def sample_release(ver='0.1.3', prerelease=False):
    stem=f'PT2VHF-Sat-Tool-v{ver}-Win7-x86'
    return {'tag_name':f'v{ver}', 'draft':False, 'prerelease':prerelease,
            'body':'Melhorias importantes', 'html_url':f'https://github.com/alexpmr/PT2VHF-Sat-Tool/releases/tag/v{ver}',
            'assets':[{'name':stem+'-Portable.zip','state':'uploaded',
                       'browser_download_url':f'https://github.com/alexpmr/PT2VHF-Sat-Tool/releases/download/v{ver}/{stem}-Portable.zip',
                       'digest':'sha256:'+ 'a'*64},
                      {'name':stem+'-SHA256.txt','state':'uploaded',
                       'browser_download_url':f'https://github.com/alexpmr/PT2VHF-Sat-Tool/releases/download/v{ver}/{stem}-SHA256.txt'}]}


def test_version_semver_and_no_downgrade():
    assert version_tuple('v0.1.12')>(version_tuple('0.1.9'))
    assert version_tuple('v0.1.2-rc1') is None
    assert select_release([sample_release('0.1.1')], '0.1.2','Win7-x86','Portable') is None


def test_release_picks_exact_variant_and_asset():
    r=select_release([sample_release('0.1.3')],'0.1.2','Win7-x86','Portable')
    assert r.version=='0.1.3' and r.expected_sha256=='a'*64
    assert select_release([sample_release()],'0.1.2','Win11-x64','Portable') is None
    assert select_release([sample_release()],'0.1.2','Win7-x86','Setup') is None


def test_release_filters_prerelease_and_missing_url():
    assert select_release([sample_release(prerelease=True)],'0.1.2','Win7-x86','Portable',include_prereleases=False) is None
    bad=sample_release()
    bad['assets'][0]['browser_download_url']='http://evil.example/payload'
    assert select_release([bad],'0.1.2','Win7-x86','Portable') is None


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

from io import BytesIO
from pathlib import Path
import json,zipfile
import pytest
from server.storage import Store
from server.material_import import import_bundle

def bundle(files):
    data=BytesIO()
    with zipfile.ZipFile(data,'w') as archive:
        archive.writestr('workbench-import.json',json.dumps({'format':'workbench-project.v2','source_project_id':'a'*32}))
        for path,value in files.items():archive.writestr(path,value)
    return data.getvalue()

def test_code_only_source_import(tmp_path):
    store=Store(tmp_path);project=store.create('author','import fixture')
    result=import_bundle(store,'author',project['id'],bundle({'project/src/model.py':'print(7)','.workbench/figures/model.pickle':'never execute'}))
    assert result['files']==1 and result['omitted_runtime_files']==['.workbench/figures/model.pickle']
    assert (store.path('author',project['id'])/'project/src/model.py').read_text()=='print(7)'

def test_reject_traversal_before_write(tmp_path):
    store=Store(tmp_path);project=store.create('author','fixture')
    with pytest.raises(ValueError):import_bundle(store,'author',project['id'],bundle({'project/../escape':'bad'}))
    assert not (store.path('author',project['id'])/'escape').exists()

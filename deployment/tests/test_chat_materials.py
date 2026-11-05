from pathlib import Path
import json,sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,'D:/Development/research-workbench')
from fastapi import FastAPI
from fastapi.testclient import TestClient
from server.storage import Store
from server.chat_materials import install,save_material
from server.native import actor

class ChatMaterialTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=Store(self.temp.name);self.project=self.store.create('alice','Research')
        self.store.update('alice',self.project['id'],native_id='ws-alice')
        self.app=FastAPI();install(self.app,self.store,None)
        self.app.dependency_overrides[actor]=lambda:{'id':'alice'}
        self.client=TestClient(self.app);self.calls=[]
    async def native(self,request,method,path,**kwargs):
        self.calls.append((method,path,kwargs))
        if method=='POST' and path.startswith('/api/knowledge-bases?'):return {'id':'ws-alice::project-docs'}
        if '/upload?' in path:return {'task_id':'native-index-1'}
        return {'ok':True}
    def test_document_is_saved_searchable_bound_and_append_is_deduplicated(self):
        with patch('server.chat_materials.call',side_effect=self.native):
            response=self.client.post('/research/api/projects/'+self.project['id']+'/attachments',files=[('files',('model.py',b'chloride_flux = -diffusivity * gradient','text/plain'))])
            self.assertEqual(response.status_code,200,response.text);result=response.json()
            self.assertTrue(result['items'][0]['searchable']);self.assertEqual(result['knowledge_task'],'native-index-1')
            self.assertIn('ws-alice::project-docs',self.store.get('alice',self.project['id'])['config']['knowledge_bases'])
            self.assertTrue((self.store.path('alice',self.project['id'])/'project'/result['items'][0]['path']).is_file())
            again=self.client.post('/research/api/projects/'+self.project['id']+'/attachments',files=[('files',('model.py',b'chloride_flux = -diffusivity * gradient','text/plain'))]).json()
            self.assertTrue(again['items'][0]['duplicate'])
            self.assertEqual(sum('/upload?' in call[1] for call in self.calls),1)
    def test_index_failure_keeps_material_and_local_text(self):
        async def unavailable(*args,**kwargs):raise RuntimeError('embedding offline')
        with patch('server.chat_materials.call',side_effect=unavailable):
            response=self.client.post('/research/api/projects/'+self.project['id']+'/attachments',files={'files':('paper.md',b'Sulfate diffusion model','text/plain')})
        self.assertEqual(response.status_code,200);entry=response.json()['items'][0]
        self.assertEqual(entry['knowledge_status'],'failed');self.assertTrue(entry['searchable'])
        self.assertEqual((self.store.path('alice',self.project['id'])/entry['text_path']).read_text(),'Sulfate diffusion model')
    def test_pdf_is_in_literature_and_image_stays_an_image(self):
        import fitz
        pdf=fitz.open();page=pdf.new_page();page.insert_text((40,40),'Moisture transport research');data=pdf.tobytes();pdf.close()
        entry=save_material(self.store,'alice',self.project['id'],'study.pdf',data)
        index=json.loads((self.store.path('alice',self.project['id'])/'.workbench/literature-index.json').read_text())
        self.assertIn(entry['literature_asset'],index)
        image=save_material(self.store,'alice',self.project['id'],'image.png',b'not-executed-image-bytes')
        self.assertFalse(image['searchable']);self.assertEqual(image['knowledge_status'],'not-applicable')

    def test_literature_hides_second_kb_copy_of_chat_pdf(self):
        import fitz
        from server.literature import install as install_literature
        pdf=fitz.open();page=pdf.new_page();page.insert_text((40,40),'Sulfate transport study')
        entry=save_material(self.store,'alice',self.project['id'],'study.pdf',pdf.tobytes());pdf.close()
        self.store.update('alice',self.project['id'],config={'knowledge_bases':['project-kb']})
        install_literature(self.app,self.store,None)
        async def native(*args,**kwargs):
            return {'files':[{'name':entry['digest'][:12]+'-study.pdf','type':'file'},
                             {'name':'another-paper.pdf','type':'file'}]}
        with patch('server.literature.call',side_effect=native):
            response=self.client.get('/research/api/projects/'+self.project['id']+'/literature/items')
        self.assertEqual(response.status_code,200,response.text)
        names=[row['name'] for row in response.json()['files']]
        self.assertEqual(names,[entry['literature_asset'],'another-paper.pdf'])

    def test_existing_ready_index_does_not_complete_new_upload_while_run_is_active(self):
        with patch('server.chat_materials.call',side_effect=self.native):
            self.client.post('/research/api/projects/'+self.project['id']+'/attachments',files={'files':('new.md',b'new source text','text/markdown')})
        state={'value':'running','count':1}
        async def native(request,method,path,**kwargs):
            if '/indexing-run?' in path:return {'run':{'state':state['value']}}
            if '/indexing-readiness?' in path:return {'ready':True}
            return {'status':'ready','statistics':{'rag_initialized':True,'raw_documents':2},'metadata':{'last_indexed_count':state['count']}}
        with patch('server.chat_materials.call',side_effect=native):
            current=self.client.get('/research/api/projects/'+self.project['id']+'/attachments').json()
            self.assertEqual(current['index']['status'],'indexing')
            self.assertEqual(current['items'][0]['knowledge_status'],'indexing')
            state.update(value='completed',count=2)
            complete=self.client.get('/research/api/projects/'+self.project['id']+'/attachments').json()
            self.assertEqual(complete['index']['status'],'ready')
            self.assertEqual(complete['items'][0]['knowledge_status'],'ready')

if __name__=='__main__':unittest.main()

"""Check source integrity, bounded reading and owner/project-scoped records."""
import json,tempfile,unittest
from pathlib import Path
from server.storage import Store,atomic_json
from server.research_flow import save_record,graph,excerpts,synthesis_payload,stable,RunInput

class ResearchFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=Store(self.temp.name);self.owner='alice'
        self.project=self.store.create(self.owner,'workflow test');self.pid=self.project['id'];self.root=self.store.path(self.owner,self.pid)
    def tearDown(self):self.temp.cleanup()
    def pdf(self):
        import fitz
        folder=self.root/'literature/reading';folder.mkdir(parents=True)
        with fitz.open() as pdf:
            for i in range(12):pdf.new_page().insert_text((50,50),'Evidence page '+str(i+1))
            pdf.save(folder/'paper.pdf')
        atomic_json(self.root/'.workbench/literature-index.json',{'reading/paper.pdf':{'title':'Actual paper','doi':'10.1234/test'}})
        return 'reading/paper.pdf'
    def test_record_and_relations_are_durable_and_project_owned(self):
        paper=stable('paper','test');method=stable('method','test')
        result=save_record(self.store,self.owner,self.pid,{'id':'record-1','title':'Methods','content':'Public reasoning summary',
          'nodes':[{'id':paper,'kind':'paper','label':'Paper'},{'id':method,'kind':'method','label':'Method','status':'known','evidence_refs':[{'url':'https://doi.org/10.1234/test'}]}],
          'edges':[{'source':paper,'target':method,'relation':'uses'}]})
        self.assertTrue((self.root/'project'/result['path']).is_file());self.assertEqual(len(graph(self.store,self.owner,self.pid)['edges']),1)
        with self.assertRaises(KeyError):graph(self.store,'another-owner',self.pid)
        other=self.store.create(self.owner,'another project');self.assertEqual(graph(self.store,self.owner,other['id'])['nodes'],[])
    def test_empty_search_is_not_global_novelty(self):
        data={'nodes':[{'kind':'gap','label':'Missing method','status':'not_found_in_scope'}]}
        with self.assertRaises(ValueError):save_record(self.store,self.owner,self.pid,data)
        data['search_scope']={'queries':['limited query'],'providers':['crossref']};save_record(self.store,self.owner,self.pid,data)
        self.assertEqual(graph(self.store,self.owner,self.pid)['nodes'][0]['search_scope']['queries'],['limited query'])
    def test_known_finding_requires_a_source(self):
        with self.assertRaises(ValueError):save_record(self.store,self.owner,self.pid,{'nodes':[{'kind':'finding','label':'Finding','status':'known'}]})
    def test_reading_is_bounded_and_citations_are_packet_bound(self):
        asset=self.pdf();docs=excerpts(self.store,self.owner,self.pid,[asset],3)
        self.assertEqual([p['page'] for p in docs[0]['pages']],[1,2,3,4,5,6,11,12]);self.assertLessEqual(sum(len(p['text']) for p in docs[0]['pages']),14000)
        answer={'summary':'Result','nodes':[{'kind':'finding','label':'F','status':'known','evidence_refs':[{'asset':asset,'pages':[7]}]}]}
        with self.assertRaises(ValueError):synthesis_payload(json.dumps(answer),docs,'q',{},'r')
        answer['nodes'][0]['evidence_refs'][0]['pages']=[2];record=synthesis_payload(json.dumps(answer),docs,'q',{},'r');self.assertEqual(record['edges'][0]['relation'],'supports')
    def test_pdf_identity_and_page_bounds(self):
        asset=self.pdf()
        with self.assertRaises(ValueError):save_record(self.store,self.owner,self.pid,{'nodes':[{'kind':'finding','label':'F','status':'known','evidence_refs':[{'asset':asset,'pages':[99]}]}]})
        with self.assertRaises(ValueError):excerpts(self.store,self.owner,self.pid,['../../another.pdf'],3)
    def test_pagination_keeps_only_valid_endpoints(self):
        save_record(self.store,self.owner,self.pid,{'nodes':[{'id':str(i),'kind':'idea','label':str(i),'status':'proposed'} for i in range(10)],'edges':[{'source':'0','target':'8','relation':'motivates'}]})
        value=graph(self.store,self.owner,self.pid,3);self.assertEqual(value['total'],10);self.assertEqual(value['next_offset'],3);self.assertEqual(value['edges'],[])
    def test_structured_route_limits(self):
        with self.assertRaises(ValueError):RunInput(kind='invented')
        with self.assertRaises(ValueError):RunInput(max_sources=1000)
    def test_native_model_payload_keeps_long_protocol_inside_actual_contract(self):
        from server.models import native_edit_payload
        instruction='rule '*2500;text='source material'
        payload=native_edit_payload(text,instruction)
        self.assertLessEqual(len(payload['instruction']),10000);self.assertIn(instruction,payload['text']);self.assertIn(text,payload['text'])

if __name__=='__main__':unittest.main()

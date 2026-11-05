"""Journal-specific matches and provenance for installed native templates."""
from functools import lru_cache
from pathlib import Path
import json,re

ROOT=Path(__file__).resolve().parents[1]
RSC_SOURCE='https://www.rsc.org/publishing/publish-with-us/publish-a-journal-article/article-templates'
WILEY_SOURCE='https://authorservices-ppd.wiley.com/author-resources/Journal-Authors/Prepare/new-journal-design.html'
IEEE_SOURCE='https://journals.ieeeauthorcenter.ieee.org/create-your-ieee-journal-article/authoring-tools-and-templates/tools-for-ieee-authors/ieee-article-templates/'


def normalize(value):return re.sub(r'[^a-z0-9\u4e00-\u9fff]','',value.lower())


@lru_cache(maxsize=1)
def wiley_journals():return {normalize(j['name']):j for j in json.loads((ROOT/'templates/manuscripts/journals-wiley.json').read_text())['journals']}


def match_template(journal):
    name=journal['name'];key=normalize(name);publisher=journal.get('publisher','').lower();family='';template=None
    if key in (normalize('CIRP Annals'),normalize('CIRP Annals Manufacturing Technology')):
        template={'family':'word-native','word_template':'cirp','name':'CIRP Annals 2026 · 官方原生 Word','source':'https://cirp.net/mainmenu-publications/cirp-annals-col-200/authors-submit-a-paper.html','columns':[2,1],'match':'journal'}
    elif key==normalize('Faraday Discussions'):
        template={'family':'word-native','word_template':'rsc-faraday','name':'Faraday Discussions · 官方原生单栏 Word','source':RSC_SOURCE,'columns':[1],'match':'journal'}
    elif 'royal society of chemistry' in publisher:
        template={'family':'word-native','word_template':'rsc','name':'RSC Article · 官方原生双栏 Word','source':RSC_SOURCE,'columns':[2],'match':'publisher author template','article_types':['Article','Review','Edge']}
        if key==normalize('Chemical Communications'):template.update(supported=False,name='ChemComm 需要专用 Communication 模板')
    elif key in wiley_journals():
        profile=wiley_journals()[key]
        template={'family':'wiley','name':'Wiley NJD v5 · '+profile['name'],'source':WILEY_SOURCE,'columns':[profile['columns'],3-profile['columns']],'match':'journal spreadsheet','journal_profile':profile}
    elif 'ieee' in publisher or name.lower().startswith('ieee '):
        template={'family':'ieee','name':'IEEEtran 1.8b · 官方期刊类','source':IEEE_SOURCE,'columns':[2,1],'match':'publisher journal class'}
    elif 'elsevier' in publisher:
        template={'family':'elsevier','name':'Elsevier CAS 2.4 · cas-dc 双栏 / cas-sc 单栏','source':'https://www.elsevier.com/researcher/author/policies-and-guidelines/latex-instructions','columns':[2,1],'match':'publisher author class; user-supplied CAS 2.4'}
    elif ('springer' in publisher or 'bmc' in publisher) and not re.search(r'^Nature\b|npj ',name,re.I):
        template={'family':'springer','name':'Springer Nature sn-jnl · 官方作者类','source':'https://www.springernature.com/gp/authors/campaigns/latex-author-support','columns':[2,1],'match':'publisher author class'}
    if template:
        template.setdefault('supported',True);template['preview_kind']='原生作者模板预览';journal['template']=template
    else:journal['template']={'family':'','name':'需取得该刊官方模板','supported':False,'source':journal.get('homepage',''),'columns':[2,1],'match':'unresolved'}
    return journal


def local_journals():
    from .storage import now
    return [
      {'id':'local-nwpu-260909','name':'西北工业大学学报','publisher':'西北工业大学','issn':['1000-2758'],'homepage':'https://journals.nwpu.edu.cn/xbgydxxb/','source':'/research/api/manuscript-template-source/chinese','language':'zh-CN','template':{'family':'word-native','word_template':'chinese','name':'用户提供原生 Word · 论文模板260909.doc','source':'/research/api/manuscript-template-source/chinese','supported':True,'columns':[2,1],'match':'journal'},'impact_factor':None,'quartile':None,'metrics_checked':now()},
      {'id':'local-chinese-mechanics','name':'力学进展','publisher':'中国科学院力学研究所 / 中国力学学会','issn':['1000-0992'],'homepage':'https://lxxj.cstam.org.cn/','source':'https://lxxj.cstam.org.cn/','language':'zh-CN','template':{'family':'word-native','word_template':'chinese-mechanics','name':'2015 年写作范例 · 需检索当前官方模板','source':'https://lxxj.cstam.org.cn/','supported':False,'columns':[1,2],'match':'historical writing example; not a current journal production template'},'impact_factor':None,'quartile':None,'metrics_checked':now()},
      {'id':'local-chinese-engineering','name':'中国工程科学','publisher':'中国工程院','issn':['1009-1742'],'homepage':'https://www.engineering.org.cn/sscae/CN/templates','source':'https://www.engineering.org.cn/sscae/CN/templates','language':'zh-CN','template':{'family':'word-native','word_template':'chinese-engineering','name':'中国工程科学 · 官方原生 Word','source':'https://www.engineering.org.cn/sscae/CN/templates','supported':True,'columns':[2,1],'match':'journal'},'impact_factor':None,'quartile':None,'metrics_checked':now()}
    ]

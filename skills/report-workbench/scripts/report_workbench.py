"""Small local helpers for report inputs, dependencies and DOCX inspection.

Python standard library only. Never writes reports or alters input material.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import sys
from collections import Counter
from xml.etree import ElementTree as ET
from zipfile import ZipFile

NS={"w":"http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "wp":"http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"}
W="{"+NS['w']+"}"
GROUPS=('sources','facts','units','assets','sections')

def load(path):
    p=Path(path).resolve();return p,json.loads(p.read_text(encoding='utf-8-sig'))

def write_new(path,obj):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2)

def file_path(base,value):
    if not value or re.match(r'^https?://',value):return None
    p=Path(value);return (base/p).resolve() if not p.is_absolute() else p.resolve()

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def init_manifest(name,kind,periods):
    return {'schema_version':1,'project':{'name':name,'kind':kind,'periods':periods,
            'purpose':'','audience':'','profile':''},
            'template':{'path':'','sha256':'','role':'layout_reference'},
            'rules':{'expected_asset_kinds':[],'require_target_confirmation':False},
            **{g:[] for g in GROUPS}}

def check(path,data):
    errors=[];warnings=[]
    def add(out,code,entity,message):out.append(dict(code=code,entity=entity,message=message))
    if data.get('schema_version')!=1:add(errors,'schema','manifest','schema_version必须是1')
    project=data.get('project',{})
    if not project.get('name'):add(errors,'name','project','缺少项目名')
    if not project.get('purpose'):add(warnings,'purpose','project','报告用途未登记')
    periods=set(project.get('periods',[]));indexes={}
    for group in GROUPS:
        rows=data.get(group,[])
        if not isinstance(rows,list):add(errors,'type',group,'应为数组');rows=[]
        ids=[r.get('id') for r in rows if isinstance(r,dict)]
        for key,n in Counter(ids).items():
            if not key or n>1:add(errors,'id',group,f'空标识或重复标识：{key}')
        indexes[group]={r.get('id'):r for r in rows if isinstance(r,dict) and r.get('id')}
        for r in indexes[group].values():
            if r.get('period') and periods and r['period'] not in periods:
                add(errors,'period',r['id'],f'周期不在项目范围：{r["period"]}')
    template=data.get('template',{})
    for group in ('sources','assets'):
        for r in indexes[group].values():
            v=r.get('path','');p=file_path(path.parent,v)
            if p is not None and not p.is_file():add(errors,'missing_file',r['id'],str(p))
            if group=='assets' and not v:add(errors,'asset_path',r['id'],'素材缺少文件位置')
            state=r.get('review_status',r.get('status','pending'))
            if state!='confirmed':add(warnings,'review',r['id'],f'状态为{state}')
    tp=file_path(path.parent,template.get('path',''))
    if tp is not None:
        if not tp.is_file():add(errors,'template_path','template',str(tp))
        elif template.get('sha256') and sha(tp).lower()!=template['sha256'].lower():
            add(errors,'template_changed','template','模板指纹改变，重新检查替换映射')
    refs={'source_ids':'sources','asset_ids':'assets','unit_ids':'units','fact_ids':'facts'}
    for group in ('facts','units','sections'):
        rows=data.get(group,[])
        for r in (rows if isinstance(rows,list) else []):
            if not isinstance(r,dict):continue
            for field,target in refs.items():
                for key in r.get(field,[]):
                    if key not in indexes[target]:add(errors,'broken_reference',r.get('id',''),f'{field}引用不存在：{key}')
    for a in indexes['assets'].values():
        if a.get('unit_id') and a['unit_id'] not in indexes['units']:
            add(errors,'asset_owner',a['id'],'所属单元不存在')
    required=data.get('rules',{}).get('expected_asset_kinds',[])
    for u in indexes['units'].values():
        assigned=[indexes['assets'][i] for i in u.get('asset_ids',[]) if i in indexes['assets']]
        for a in assigned:
            if a.get('unit_id') and a['unit_id']!=u['id']:add(errors,'owner_conflict',u['id'],f'素材{a["id"]}登记给另一单元')
            if a.get('period') and u.get('period') and a['period']!=u['period']:
                add(errors,'asset_period',u['id'],f'素材{a["id"]}与单元周期不同')
        kinds={a.get('kind') for a in assigned}
        for kind in required:
            if kind not in kinds:add(errors,'missing_kind',u['id'],f'缺少{kind}素材')
        if u.get('evidence_status')!='verified':add(warnings,'evidence',u['id'],'证据尚未核验或不足')
        if data.get('rules',{}).get('require_target_confirmation') and not u.get('target_confirmed'):
            add(warnings,'target',u['id'],'具体目标位置待核对')
        if u.get('result') and not u.get('source_ids'):
            add(warnings,'result_source',u['id'],'结果缺少来源或用户决定记录')
    for f in indexes['facts'].values():
        if f.get('status')!='confirmed' or not f.get('source_ids'):
            add(warnings,'fact_source',f['id'],'事实状态或来源需核对')
    if not indexes['sources']:add(warnings,'sources','project','尚未登记资料来源')
    return {'scope':'仅检查已登记台账；不验证业务结论或实际排版','errors':errors,'warnings':warnings}

def snapshot(path,data):
    files={}
    for group in ('sources','assets'):
        for row in data.get(group,[]):
            p=file_path(path.parent,row.get('path',''))
            files[f'{group}:{row["id"]}']={'path':str(p) if p else row.get('path',''),
                'sha256':sha(p) if p and p.is_file() else None}
    tp=file_path(path.parent,data.get('template',{}).get('path',''))
    files['template']={'path':str(tp) if tp else '', 'sha256':sha(tp) if tp and tp.is_file() else None}
    return {'snapshot_version':1,'manifest':copy.deepcopy(data),'files':files}

def plan(before,after):
    old=before['manifest'];new=after['manifest'];changed={};removed={};added={}
    for g in GROUPS:
        a={r['id']:r for r in old.get(g,[])};b={r['id']:r for r in new.get(g,[])}
        added[g]=sorted(b.keys()-a.keys());removed[g]=sorted(a.keys()-b.keys())
        keys={k for k in a.keys()|b.keys() if a.get(k)!=b.get(k)}
        for key in a.keys()|b.keys():
            fkey=f'{g}:{key}'
            if before.get('files',{}).get(fkey)!=after.get('files',{}).get(fkey):keys.add(key)
        changed[g]=sorted(keys)
    assets=set(changed['assets']);sources=set(changed['sources']);facts=set(changed['facts']);units=set(changed['units'])
    for d in [old,new]:
        for f in d.get('facts',[]):
            if sources.intersection(f.get('source_ids',[])):facts.add(f['id'])
        for u in d.get('units',[]):
            if assets.intersection(u.get('asset_ids',[])) or sources.intersection(u.get('source_ids',[])):units.add(u['id'])
    template=old.get('template')!=new.get('template') or before.get('files',{}).get('template')!=after.get('files',{}).get('template')
    project_changed=old.get('project')!=new.get('project')
    rules_changed=old.get('rules')!=new.get('rules')
    affected_periods={}
    for group,ids in [('units',units),('facts',facts),('assets',assets)]:
        affected_periods[group]={r.get('period','') for d in [old,new] for r in d.get(group,[]) if r['id'] in ids}
    sections={};known={r['id']:r for r in old.get('sections',[])};known.update({r['id']:r for r in new.get('sections',[])})
    for k,s in known.items():
        reasons=[]
        for field,ids in [('unit_ids',units),('fact_ids',facts),('asset_ids',assets),('source_ids',sources)]:
            if ids.intersection(s.get(field,[])):reasons.append(field)
        for g,ids in [('units',units),('facts',facts),('assets',assets)]:
            if f'all_{g}' in s.get('depends_on',[]) and ids:
                if not s.get('period') or '' in affected_periods[g] or s['period'] in affected_periods[g]:reasons.append(f'all_{g}')
        if template:reasons.append('template_layout')
        if project_changed:reasons.append('project_scope')
        if rules_changed:reasons.append('review_rules')
        if k in changed['sections']:reasons.append('section_definition')
        if reasons:sections[k]={'title':s.get('title',''),'reasons':reasons}
    membership=bool(added['units'] or removed['units'])
    old_units={r['id']:r for r in old.get('units',[])}
    for u in new.get('units',[]):
        prev=old_units.get(u['id'])
        if prev and any(prev.get(k)!=u.get(k) for k in ['period','display_no','result']):membership=True
    return {'changed':changed,'added':added,'removed':removed,'affected_units':sorted(units),
        'affected_facts':sorted(facts),'affected_sections':sections,'template_changed':template,'project_changed':project_changed,'rules_changed':rules_changed,
        'recheck_counts_numbering_maps':membership,'recheck_case_evidence_and_text':bool(assets or units or sources),
        'requires_render_before_delivery':any(changed.values()) or template or project_changed or rules_changed,
        'scope':'依赖检查建议；需人工/AI复核语义、图件目标与最终排版'}

def inspect_docx(path):
    with ZipFile(path) as z:
        root=ET.fromstring(z.read('word/document.xml'));body=root.find('w:body',NS)
        sections=[]
        for s in root.findall('.//w:sectPr',NS):
            pg=s.find('w:pgSz',NS);mar=s.find('w:pgMar',NS);num=s.find('w:pgNumType',NS)
            sections.append({'page_twips':{k.split('}')[-1]:v for k,v in pg.attrib.items()} if pg is not None else {},
                'margins_twips':{k.split('}')[-1]:v for k,v in mar.attrib.items()} if mar is not None else {},
                'numbering':{k.split('}')[-1]:v for k,v in num.attrib.items()} if num is not None else {}})
        paragraphs=[];visible=[]
        styles=ET.fromstring(z.read('word/styles.xml')) if 'word/styles.xml' in z.namelist() else None
        stylemap={s.get(W+'styleId'):s for s in styles.findall('w:style',NS)} if styles is not None else {}
        def heading_style(key,seen=None):
            seen=set() if seen is None else seen
            if not key or key in seen:return False
            seen.add(key);s=stylemap.get(key)
            if s is None:return bool(re.search(r'heading|标题',key,re.I))
            name=s.find('w:name',NS);level=s.find('w:pPr/w:outlineLvl',NS);parent=s.find('w:basedOn',NS)
            if name is not None and re.search(r'heading|标题',name.get(W+'val',''),re.I):return True
            if level is not None and int(level.get(W+'val','9'))<9:return True
            return heading_style(parent.get(W+'val') if parent is not None else None,seen)
        for name in z.namelist():
            if name=='word/document.xml' or re.match(r'word/(header|footer)\d+\.xml$',name):
                tree=ET.fromstring(z.read(name))
                for p in tree.findall('.//w:p',NS):
                    t=''.join(x.text or '' for x in p.findall('.//w:t',NS))
                    if t:visible.append({'part':name,'text':t})
        for p in body.findall('w:p',NS):
            st=p.find('w:pPr/w:pStyle',NS)
            level=p.find('w:pPr/w:outlineLvl',NS)
            if (st is not None and heading_style(st.get(W+'val'))) or (level is not None and int(level.get(W+'val','9'))<9):
                paragraphs.append(''.join(x.text or '' for x in p.findall('.//w:t',NS)))
        ids=[x.get('id') for x in root.findall('.//wp:docPr',NS)]
        duplicates=[k for k,v in Counter(ids).items() if v>1]
        leaks=[r for r in visible if re.search(r'[A-Za-z]:[\\/]|file://|\\\\[^\\\s]+\\',r['text'])]
        unresolved=[r for r in visible if re.search(r'待填|待补|待核对|待圈注|XX月|【待|待[^。；\n]{0,24}核对|仍需[^。；\n]{0,16}核对',r['text'])]
        fields=[''.join(x.itertext()).strip() for x in root.findall('.//w:instrText',NS)]
        grid_widths=[sum(int(x.get(W+'w','0')) for x in t.findall('w:tblGrid/w:gridCol',NS)) for t in body.findall('w:tbl',NS)]
        return {'scope':'结构检查；实际页码、字体可读性、边框显示和图片内容需要渲染/目视复核',
            'sections':sections,'headings':paragraphs,'top_level_tables':len(grid_widths),'table_grid_width_twips':grid_widths,
            'inline_images':len(root.findall('.//wp:inline',NS)),'anchored_images':len(root.findall('.//wp:anchor',NS)),
            'duplicate_drawing_ids':duplicates,'local_paths_in_visible_text':leaks,'unresolved_text':unresolved,
            'body_field_instructions':fields}

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('init');a.add_argument('--out',required=True);a.add_argument('--name',required=True);a.add_argument('--kind',default='special');a.add_argument('--periods',nargs='*',default=[])
    for cmd in ['check','snapshot','plan']:
        a=sub.add_parser(cmd);a.add_argument('--manifest',required=True)
        if cmd=='snapshot':a.add_argument('--out',required=True)
        if cmd=='plan':a.add_argument('--baseline',required=True)
    a=sub.add_parser('inspect-docx');a.add_argument('--file',required=True)
    args=p.parse_args()
    try:
        if args.command=='init':
            write_new(args.out,init_manifest(args.name,args.kind,args.periods));print(str(Path(args.out).resolve()));return 0
        if args.command=='inspect-docx':result=inspect_docx(args.file)
        else:
            path,data=load(args.manifest)
            if args.command=='check':result=check(path,data)
            elif args.command=='snapshot':
                write_new(args.out,snapshot(path,data));print(str(Path(args.out).resolve()));return 0
            else:result=plan(load(args.baseline)[1],snapshot(path,data))
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 1 if result.get('errors') else 0
    except (OSError,ValueError,KeyError,TypeError) as e:
        print(f'{type(e).__name__}: {e}',file=sys.stderr);return 2

if __name__=='__main__':sys.exit(main())

"""Behavior checks using isolated synthetic inputs only."""
from pathlib import Path
import importlib.util,copy,json,tempfile,unittest

HERE=Path(__file__).resolve().parent
REPO=HERE.parent
spec=importlib.util.spec_from_file_location('rw',REPO/'skills'/'report-workbench'/'scripts'/'report_workbench.py')
rw=importlib.util.module_from_spec(spec);spec.loader.exec_module(rw)

class WorkbenchChecks(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='qa_',dir=HERE)
        self.root=Path(self.tmp.name).resolve();assert self.root.parent==HERE
        self.addCleanup(self.tmp.cleanup)
        self.path=self.root/'report-project.json'
        (self.root/'source.txt').write_text('synthetic source',encoding='utf-8')
        (self.root/'a.png').write_bytes(b'synthetic asset; no image semantic test')
        self.data=rw.init_manifest('通用测试项目','special',['2026-01','2026-02'])
        self.data['project']['purpose']='测试依赖关联，非真实业务结论'
        self.data['sources']=[{'id':'S1','path':'source.txt','status':'confirmed'}]
        self.data['units']=[{'id':'U1','period':'2026-01','display_no':'1','question':'Q','result':'synthetic',
            'source_ids':['S1'],'asset_ids':['A1'],'evidence_status':'pending','target_confirmed':False}]
        self.data['assets']=[{'id':'A1','path':'a.png','kind':'photo','period':'2026-01','unit_id':'U1','review_status':'pending'}]
        self.data['sections']=[{'id':'case','unit_ids':['U1']},{'id':'jan','period':'2026-01','depends_on':['all_units']},
            {'id':'feb','period':'2026-02','depends_on':['all_units']}]

    def test_pending_is_not_verified(self):
        self.data['rules']['require_target_confirmation']=True
        r=rw.check(self.path,self.data)
        self.assertFalse(r['errors']);self.assertTrue({'target','evidence','review'}<={x['code'] for x in r['warnings']})

    def test_missing_files_and_cross_period(self):
        self.data['assets'][0]['path']='missing.png';self.data['assets'][0]['period']='2026-02'
        r=rw.check(self.path,self.data)
        self.assertTrue({'missing_file','asset_period'}<={x['code'] for x in r['errors']})

    def test_duplicate_and_broken_reference(self):
        self.data['units'].append(copy.deepcopy(self.data['units'][0]));self.data['units'][0]['source_ids']=['missing']
        r=rw.check(self.path,self.data)
        self.assertTrue({'id','broken_reference'}<={x['code'] for x in r['errors']})

    def test_required_pair(self):
        self.data['rules']['expected_asset_kinds']=['photo','satellite']
        self.assertIn('missing_kind',{x['code'] for x in rw.check(self.path,self.data)['errors']})

    def test_same_name_replacement_invalidates_case_and_period(self):
        old=rw.snapshot(self.path,self.data);(self.root/'a.png').write_bytes(b'new bytes, same filename')
        r=rw.plan(old,rw.snapshot(self.path,self.data))
        self.assertEqual(r['changed']['assets'],['A1']);self.assertEqual(r['affected_units'],['U1'])
        self.assertEqual(set(r['affected_sections']),{'case','jan'});self.assertTrue(r['recheck_case_evidence_and_text'])

    def test_no_change_and_add_delete(self):
        old=rw.snapshot(self.path,self.data)
        self.assertFalse(rw.plan(old,rw.snapshot(self.path,self.data))['requires_render_before_delivery'])
        self.data['units']=[]
        r=rw.plan(old,rw.snapshot(self.path,self.data))
        self.assertTrue(r['recheck_counts_numbering_maps']);self.assertEqual(r['removed']['units'],['U1'])

    def test_source_or_result_change_propagates(self):
        old=rw.snapshot(self.path,self.data);(self.root/'source.txt').write_text('changed source',encoding='utf-8')
        r=rw.plan(old,rw.snapshot(self.path,self.data));self.assertEqual(r['affected_units'],['U1'])
        newer=rw.snapshot(self.path,self.data);self.data['units'][0]['result']='another class'
        self.assertTrue(rw.plan(newer,rw.snapshot(self.path,self.data))['recheck_counts_numbering_maps'])

    def test_template_and_project_change(self):
        (self.root/'t.docx').write_bytes(b'template');self.data['template']={'path':'t.docx','sha256':'incorrect'}
        self.assertIn('template_changed',{x['code'] for x in rw.check(self.path,self.data)['errors']})
        old=rw.snapshot(self.path,self.data);self.data['project']['name']='new title'
        r=rw.plan(old,rw.snapshot(self.path,self.data));self.assertTrue(r['project_changed']);self.assertEqual(len(r['affected_sections']),3)

    def test_refuse_overwrite(self):
        rw.write_new(self.path,self.data)
        with self.assertRaises(FileExistsError):rw.write_new(self.path,self.data)

    def test_synthetic_docx_structure(self):
        from zipfile import ZipFile
        path=self.root/'synthetic.docx'
        xml="""<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"><w:body>
        <w:p><w:pPr><w:pStyle w:val="CustomHeading"/></w:pPr><w:r><w:t>方法说明</w:t></w:r></w:p>
        <w:p><w:r><w:t>目标待核对</w:t></w:r></w:p>
        <w:p><w:pPr><w:sectPr><w:pgNumType w:fmt="upperRoman" w:start="1"/></w:sectPr></w:pPr></w:p>
        <w:tbl><w:tblGrid><w:gridCol w:w="4000"/><w:gridCol w:w="4000"/></w:tblGrid></w:tbl>
        <w:p><w:r><w:drawing><wp:inline><wp:docPr id="7"/></wp:inline></w:drawing></w:r></w:p>
        <w:p><w:r><w:drawing><wp:inline><wp:docPr id="7"/></wp:inline></w:drawing></w:r></w:p>
        <w:sectPr><w:pgNumType w:fmt="decimal" w:start="1"/></w:sectPr></w:body></w:document>"""
        styles="""<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:style w:styleId="CustomHeading"><w:pPr><w:outlineLvl w:val="0"/></w:pPr></w:style></w:styles>"""
        with ZipFile(path,'w') as z:
            z.writestr('word/document.xml',xml)
            z.writestr('word/styles.xml',styles)
        result=rw.inspect_docx(path)
        self.assertEqual(len(result['sections']),2)
        self.assertEqual(result['sections'][0]['numbering']['fmt'],'upperRoman')
        self.assertEqual(result['top_level_tables'],1)
        self.assertEqual(result['inline_images'],2)
        self.assertEqual(result['duplicate_drawing_ids'],['7'])
        self.assertEqual(result['headings'],['方法说明'])
        self.assertTrue(result['unresolved_text'])
        self.assertFalse(result['local_paths_in_visible_text'])

if __name__=='__main__':unittest.main(verbosity=2)

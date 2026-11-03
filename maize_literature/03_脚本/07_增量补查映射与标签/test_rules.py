"""小型规则回归检查；使用合成文本，不产生生物学事实。"""
import unittest
import run_continuation as m

class Rules(unittest.TestCase):
    def setUp(self):
        self.genes=[dict(gene_id='Zm00001eb000010',symbol='ZmTEST1',aliases='SHARED1;chloroplast'),dict(gene_id='Zm00001eb000020',symbol='ZmTEST2',aliases='SHARED1')]
        self.aliases=m.build_reference(self.genes);self.ids={g['gene_id'] for g in self.genes}
        self.lex,self.tr,self.terms=m.make_extractors(self.aliases,[])
    def scan(self,text,title='Test title'):
        p=dict(source_row='synthetic',pmid='synthetic',doi='',title=title,abstract=text,candidate_evidence_labels='X')
        return m.scan_paper(p,self.lex,self.tr,self.terms,{},self.aliases,self.ids,'synthetic_reference')[0]
    def test_multigene_not_cartesian(self):
        rs=self.scan('ZmTEST1 and ZmTEST2 knockout mutants reduced root length and plant height.')
        self.assertEqual(len(rs),1);self.assertEqual(rs[0]['supplemental_quality_group'],'待定')
        self.assertEqual(rs[0]['mapping_status'],'unresolved')
    def test_contrast_locality(self):
        rs=self.scan('ZmTEST1 knockout mutants reduced root length whereas ZmTEST2 overexpression increased plant height.')
        self.assertEqual(len(rs),2)
        self.assertEqual([(r['gene_mention'],r['trait_normalized']) for r in rs],[('ZmTEST1','根长'),('ZmTEST2','株高')])
    def test_expression_not_causal(self):
        r=self.scan('ZmTEST1 expression levels increased during salt stress.')[0]
        self.assertEqual(r['relation_evidence_type'],'C');self.assertEqual(r['effect_direction'],'unknown')
    def test_unknown_mapping_not_negative(self):
        a=m.map_gene('GRMZM2G999999',self.aliases,self.ids,'test')
        self.assertEqual(a['mapping_status'],'unresolved');self.assertEqual(a['resolved_gene_id'],'')
    def test_ambiguous_alias(self):
        a=m.map_gene('SHARED1',self.aliases,self.ids,'test')
        self.assertEqual(a['mapping_status'],'ambiguous');self.assertEqual(a['resolved_gene_id'],'')
    def test_generic_descriptor_not_gene(self):
        a=m.map_gene('chloroplast',self.aliases,self.ids,'test')
        self.assertFalse(a['mapping_reference_verified']);self.assertEqual(a['resolved_gene_id'],'')
    def test_title_not_abstract_evidence(self):
        self.assertEqual(self.scan('No gene evidence in this abstract.','ZmTEST1 knockout mutants reduced plant height.'),[])
    def test_verbatim_source_and_no_effect(self):
        text='In maize, ZmTEST1 knockout mutants had no significant effect on root length.'
        r=self.scan(text)[0]
        self.assertIn(r['supporting_text'],text);self.assertEqual(r['effect_direction'],'no_significant_effect')
    def test_reference_external_syntax(self):
        a=m.map_gene('Zm00001eb999999',self.aliases,self.ids,'test')
        self.assertFalse(a['mapping_reference_verified']);self.assertEqual(a['mapping_status'],'unresolved_reference_membership')
    def test_other_lowercase_gene_detected(self):
        r=self.scan('The maize rth5 and rth6 mutants exhibited increased cold tolerance.')[0]
        self.assertEqual(r['supplemental_quality_group'],'待定');self.assertIn('rth5',r['gene_mention'])

if __name__=='__main__':unittest.main()

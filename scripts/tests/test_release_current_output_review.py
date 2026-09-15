"""Complete output identity composition remains exact and non-semantic."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import generated_output_inventory as inventory
import release_current_output_review as gate


class OutputReviewTests(unittest.TestCase):
    SOURCE = 'a' * 64

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='current-output-review-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.formal = self.inventory(inventory.roots(), {})
        self.write(self.root / 'formal-after.json', self.formal)
        self.current = self.inventory(inventory.roots(['extra']), {
            'extra': {'kind':'directory','mode':0o755},
            'extra/a': {'kind':'file','mode':0o644,'size':1,'sha256':'1'*64},
            'extra/b': {'kind':'file','mode':0o644,'size':2,'sha256':'2'*64},
            'extra/c': {'kind':'file','mode':0o755,'size':3,'sha256':'3'*64}})
        self.additional = {name: value for name,value in self.current['entries'].items() if name.startswith('extra')}
        self.write(self.root / 'source.json', {})
        self.write(self.root / 'manifest.json', {})
        self.observation = self.make_observation()
        self.reviews = {}
        names = list(self.additional)
        self.make_review('registry', [names[0]], names[1:],
            'partial_additional_registry_review_checked_other_nodes_pending',
            'partial-additional-cargo-registry-review-v1', 'reviewed_nodes', 0)
        self.make_review('build', [names[1]], names[2:],
            'additional_build_and_directory_records_checked_other_files_pending',
            'partial-additional-build-and-directory-review-v1', 'new_reviewed_nodes', 1)
        self.make_review('record', names[2:], [],
            'all_additional_observed_nodes_record_reviewed_with_non_semantic_boundaries',
            'additional-record-and-cache-review-v1', 'new_reviewed_nodes', 2)
        self.confirmation = self.make_confirmation()
        self.component = {'observation': self.ref(self.observation),
            'registry_review': self.ref(self.reviews['registry']['report_path']),
            'build_review': self.ref(self.reviews['build']['report_path']),
            'record_review': self.ref(self.reviews['record']['report_path']),
            'confirmation': self.ref(self.confirmation)}

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + '\n')

    def ref(self, path):
        return {'path': path.relative_to(self.root).as_posix(), 'sha256': gate.common.sha(path)}

    def inventory(self, roots, extra):
        entries = {name: None for name in roots}
        entries.update(extra)
        result = {'schema_version':1, 'kind':inventory.KIND, 'roots':roots, 'entries':entries,
                  'symlinks_followed':False, 'whole_workspace_coverage_claimed':False}
        result['snapshot_sha256'] = inventory.digest(result)
        inventory.validate(result)
        return result

    def make_observation(self):
        out = self.root / 'observation'
        self.write(out / 'current/snapshot.json', self.current)
        self.write(out / 'current-formal-scope.json', self.formal)
        delta = inventory.compare(self.formal, self.formal)
        self.write(out / 'formal-to-current/delta.json', delta)
        additional = {'schema_version':1, 'scope':'fixture',
            'observed_snapshot_sha256':self.current['snapshot_sha256'], 'entries':self.additional,
            'historical_absence_claimed':False, 'generated_outputs_audited':False}
        self.write(out / 'additional-observed-nodes.json', additional)
        scope = {'schema_version':1, 'kind':'current-output-scope-observation-not-delivery-approval',
            'formal_report':self.ref(self.root/'formal-after.json'),
            'formal_after':self.ref(self.root/'formal-after.json'),
            'current_source_record':self.ref(self.root/'source.json'),
            'current_manifest':self.ref(self.root/'manifest.json'),
            'historical_roots':self.formal['roots'], 'observed_roots':self.current['roots'],
            'actual_native_root':'extra', 'new_evidence_children_since_formal':[],
            'unobserved_preexisting_evidence_children':[], 'artifacts_top_level_names_only':[],
            'recording_directory_excluded_from_its_own_inventory':'observation',
            'additional_roots_have_no_invented_historical_baseline':True,
            'whole_workspace_coverage_claimed':False, 'final_delivery_scope_approved':False}
        self.write(out/'scope.json', scope)
        files = {path.relative_to(out).as_posix():gate.common.sha(path) for path in out.rglob('*') if path.is_file()}
        report = {'schema_version':1, 'kind':'current-expanded-output-observation-v1',
            'status':'current_output_observation_and_complete_formal_delta_recorded_pending_review',
            'started_at':'2026-01-01T00:00:00+00:00', 'stages':[], 'errors':[],
            **dict.fromkeys(gate.OBSERVATION_FLAGS,False), 'source_snapshot_sha256':self.SOURCE,
            'observed_summary':inventory.summary(self.current), 'historical_scope_summary':inventory.summary(self.formal),
            'scope':self.ref(out/'scope.json'), 'current_inventory':self.ref(out/'current/snapshot.json'),
            'formal_delta':self.ref(out/'formal-to-current/delta.json'), 'changed_historical_nodes':0,
            'change_operations':{}, 'additional_observed_nodes':len(self.additional),
            'non_atomic_observation_only':True, 'finished_at':'2026-01-01T00:01:00+00:00',
            'record_files':files}
        path=out/'report.json';self.write(path,report);return path

    def make_review(self, name, selected, remaining, status, kind, field, prior):
        out=self.root/name
        rows={node:{'node_sha256':inventory.digest(self.additional[node]),'category':'fixture',
                    'evidence':{'fixture':True},'semantic_correctness_proven':False,'delivery_approved':False}
              for node in selected}
        review={'schema_version':1,'kind':kind,'scope':'fixture','source_snapshot_sha256':self.SOURCE,
            field:rows,'remaining_unreviewed_nodes':{node:inventory.digest(self.additional[node]) for node in remaining},
            'category_counts':{'fixture':len(rows)},**dict.fromkeys(gate.REVIEW_FALSE_FLAGS,False)}
        if name!='registry':review['prior_reviewed_nodes']=prior
        review_path=out/'review.json';self.write(review_path,review)
        report={'schema_version':1,'status':status,'errors':[],'source_snapshot_sha256':self.SOURCE,
            'review':self.ref(review_path),**dict.fromkeys(gate.REVIEW_FALSE_FLAGS,False),
            'record_files':{'review.json':gate.common.sha(review_path)}}
        report_path=out/'report.json';self.write(report_path,report)
        self.reviews[name]={'review':review,'review_path':review_path,'report':report,'report_path':report_path,'field':field}

    def reseal_review(self,name):
        item=self.reviews[name];self.write(item['review_path'],item['review'])
        item['report']['review']=self.ref(item['review_path'])
        item['report']['record_files']['review.json']=gate.common.sha(item['review_path'])
        self.write(item['report_path'],item['report'])
        self.component[name+'_review']=self.ref(item['report_path'])

    def make_confirmation(self):
        out=self.root/'confirmation';snap=out/'current/snapshot.json';self.write(snap,self.current)
        extras=[name for name in self.current['roots'] if name not in inventory.CANONICAL_ROOTS]
        argv=['/usr/bin/python3','-B','-O','scripts/generated_output_inventory.py','capture','--out',str(out/'current')]
        for name in extras:argv += ['--extra-root',name]
        initial={'name':'capture-current','argv':argv,'cwd':str(self.root),'started_at':'2026-01-01T01:00:01+00:00',
                 'timeout_seconds':3600,'exit_code':None,'status':'starting','log':'capture-current.log'}
        process={**initial,'pid':12}; log=out/'capture-current.log';log.write_text('captured\n')
        finished={**process,'exit_code':0,'status':'completed','finished_at':'2026-01-01T01:00:02+00:00',
                  'log_sha256':gate.common.sha(log)}
        for suffix,row in [('started',initial),('process',process),('finished',finished)]:self.write(out/f'capture-current-{suffix}.json',row)
        files={p.relative_to(out).as_posix():gate.common.sha(p) for p in out.rglob('*') if p.is_file()}
        report={'schema_version':1,'kind':'current-output-exact-rescan-confirmation-v1',
            'status':'current_24_root_snapshot_exactly_matches_reviewed_observation',
            'started_at':'2026-01-01T01:00:00+00:00','finished_at':'2026-01-01T01:00:03+00:00',
            'stages':[finished],'errors':[],'source_snapshot_sha256':self.SOURCE,
            'observation_report_sha256':gate.common.sha(self.observation),
            'observed_snapshot_sha256':self.current['snapshot_sha256'],'snapshot':self.ref(snap),
            'record_files':files,**dict.fromkeys(gate.CONFIRMATION_FLAGS,False)}
        path=out/'report.json';self.write(path,report);return path

    def check(self): return gate.check(self.component,self.SOURCE,self.root)
    def test_valid(self):
        result=self.check();self.assertEqual(result['reviewed_additional_nodes'],4)
        self.assertTrue(result['current_generated_output_identity_recorded'])
        self.assertFalse(result['generated_outputs_audited'])
    def test_component_field(self):
        self.component['skip']=self.component['observation']
        with self.assertRaises(RuntimeError):self.check()
    def test_wrong_source(self):
        with self.assertRaisesRegex(RuntimeError,'wrong source'):gate.check(self.component,'b'*64,self.root)
    def test_observation_assurance(self):
        row=json.loads(self.observation.read_text());row['generated_outputs_audited']=True;self.write(self.observation,row)
        self.component['observation']=self.ref(self.observation)
        with self.assertRaisesRegex(RuntimeError,'assurance'):self.check()
    def test_observation_member_drift(self):
        (self.observation.parent/'scope.json').write_text('{}')
        with self.assertRaises(RuntimeError):self.check()
    def test_review_row_digest(self):
        item=self.reviews['build'];next(iter(item['review'][item['field']].values()))['node_sha256']='b'*64;self.reseal_review('build')
        with self.assertRaisesRegex(RuntimeError,'another observed'):self.check()
    def test_review_overlap(self):
        registry_name=next(iter(self.reviews['registry']['review']['reviewed_nodes']))
        item=self.reviews['build'];item['review']['new_reviewed_nodes']={registry_name:{
            'node_sha256':inventory.digest(self.additional[registry_name]),'category':'fixture','evidence':{},
            'semantic_correctness_proven':False,'delivery_approved':False}}
        self.reseal_review('build')
        with self.assertRaisesRegex(RuntimeError,'partition'):self.check()
    def test_review_assurance(self):
        self.reviews['record']['review']['semantic_correctness_proven']=True;self.reseal_review('record')
        with self.assertRaisesRegex(RuntimeError,'assurance'):self.check()
    def test_confirmation_observation(self):
        row=json.loads(self.confirmation.read_text());row['observation_report_sha256']='b'*64;self.write(self.confirmation,row)
        self.component['confirmation']=self.ref(self.confirmation)
        with self.assertRaisesRegex(RuntimeError,'confirmation'):self.check()
    def test_confirmation_snapshot(self):
        (self.confirmation.parent/'current/snapshot.json').write_text('{}')
        with self.assertRaises(RuntimeError):self.check()
    def test_confirmation_stage_exit(self):
        row=json.loads(self.confirmation.read_text());row['stages'][0]['exit_code']=1;self.write(self.confirmation,row)
        self.component['confirmation']=self.ref(self.confirmation)
        with self.assertRaises(RuntimeError):self.check()
    def test_historical_delta(self):
        row=json.loads((self.observation.parent/'current-formal-scope.json').read_text())
        row['entries'][row['roots'][0]]={'kind':'directory','mode':0o755};row['snapshot_sha256']=inventory.digest({k:v for k,v in row.items() if k!='snapshot_sha256'})
        self.write(self.observation.parent/'current-formal-scope.json',row)
        report=json.loads(self.observation.read_text());report['record_files']['current-formal-scope.json']=gate.common.sha(self.observation.parent/'current-formal-scope.json');self.write(self.observation,report)
        self.component['observation']=self.ref(self.observation)
        with self.assertRaises(RuntimeError):self.check()


if __name__=='__main__':unittest.main()

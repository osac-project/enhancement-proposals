"""Behavioral regression tests for the required test-plan check."""

import json
import os
import subprocess
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import tp_check
import tp_gate
import tp_review
from tp_hooks import CONTEXT_FILES, TestPlanHooks

SHA = 'a' * 40
PR = {'number': 42, 'head': {'sha': SHA, 'repo': {'full_name': 'contributor/repo'}}}


def verdict(result='Ready'):
    return {
        'verdict': result, 'scores': dict.fromkeys(tp_gate.SCORE_KEYS, 2),
        'total': 10, 'criterionNotes': dict.fromkeys(tp_gate.SCORE_KEYS, 'Evidence cited'),
        'summary': 'All required boundaries accounted for',
        'feedback': 'No changes needed' if result == 'Ready' else 'Repair the stated evidence gap',
        'findings': {'critical': [], 'important': [], 'suggestions': []},
    }


@contextmanager
def scoring_fixture():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        skill = root / 'skills/test-plan-score/SKILL.md'
        skill.parent.mkdir(parents=True)
        skill.write_text('Authoritative test skill\nIntegration-boundary Rework veto\n')
        for name in CONTEXT_FILES:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('Authoritative scoring reference: ' + path.name)
        with patch.dict(os.environ, {'TP_OSAC_PATH': str(root)}), patch(
            'tp_hooks.grounding_context',
            return_value={'osac_sha': SHA, 'files': {'AGENTS.md': 'Touched area evidence'}},
        ):
            yield root


@contextmanager
def working_directory(path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


class VerdictTests(unittest.TestCase):
    def test_ready_and_high_score_nonready_vetoes_are_valid(self):
        for result in ('Ready', 'Revise', 'Rework'):
            with self.subTest(result=result):
                self.assertEqual(tp_gate.validate_verdict(verdict(result)), [])

    def test_unusable_and_inconsistent_outputs_are_rejected(self):
        mutations = [
            lambda v: v.update(total=9),
            lambda v: v.update(verdict='PASS'),
            lambda v: v['scores'].update(grounding=True),
            lambda v: v['scores'].update(grounding=3),
            lambda v: v['scores'].pop('grounding'),
            lambda v: v['scores'].update(extra=2),
            lambda v: v.update(criterionNotes={}),
            lambda v: v.update(feedback=''),
            lambda v: v['findings'].update(critical=['Wrong-tier required boundary']),
        ]
        for mutation in mutations:
            value = verdict()
            mutation(value)
            with self.subTest(value=value):
                self.assertTrue(tp_gate.validate_verdict(value))
        self.assertTrue(tp_gate.validate_verdict([]))
        self.assertTrue(tp_gate.validate_verdict(None))

    def test_zero_cannot_pass_even_with_eight_points(self):
        value = verdict()
        value['scores']['grounding'] = 0
        value['total'] = 8
        self.assertTrue(tp_gate.validate_verdict(value))
        value['verdict'] = 'Rework'
        self.assertEqual(tp_gate.validate_verdict(value), [])


class ScoringTests(unittest.TestCase):
    def setUp(self):
        self.files = [
            {'filename': 'enhancements/one/design.md', 'status': 'modified'},
            {'filename': 'enhancements/two/testplan.md', 'status': 'modified'},
        ]
        self.documents = {
            f'enhancements/{slug}/{name}': {'content': f'{slug} {name}', 'sha': 'blob'}
            for slug in ('one', 'two') for name in ('testplan.md', 'design.md', 'prd.md')
        }

    def run_score(self, outputs):
        def fetch(repo, sha, path, **kw):
            self.assertEqual(sha, SHA)
            return self.documents.get(path)
        with scoring_fixture() as skills, patch.object(
            tp_review, 'fetch_pr_file', side_effect=fetch,
        ), patch.object(tp_review, 'get_pull_request', return_value=PR), patch.object(
            tp_review, 'complete', side_effect=[(json.dumps(v), {}) for v in outputs],
        ) as model, tempfile.TemporaryDirectory() as directory, working_directory(directory):
            rows = tp_review.score_pr(
                PR, self.files, skills_path=str(skills), model='test-model', shadow=True,
            )
            self.assertIn('Authoritative test skill', model.call_args.args[0])
            self.assertIn('Touched area evidence', model.call_args.args[0])
            return rows, model.call_count

    def test_all_plans_scored_including_unchanged_plan_on_design_edit(self):
        rows, count = self.run_score([verdict(), verdict('Revise')])
        self.assertEqual(count, 2)
        self.assertEqual([r['verdict'] for r in rows], ['Ready', 'Revise'])
        self.assertEqual(rows[0]['path'], 'enhancements/one/testplan.md')

    def test_invalid_model_result_does_not_prevent_other_plan_evaluation(self):
        bad = verdict()
        bad['scores']['grounding'] = True
        rows, count = self.run_score([bad, verdict()])
        self.assertEqual(count, 2)
        self.assertEqual([r['verdict'] for r in rows], ['Error', 'Ready'])

    def test_retry_recomputes_even_when_a_score_comment_exists(self):
        with patch.object(TestPlanHooks, 'check_already_scored', return_value='Already scored') as cache:
            self.run_score([verdict(), verdict()])
            self.run_score([verdict(), verdict()])
        cache.assert_not_called()

    def test_missing_required_context_blocks_without_calling_model(self):
        del self.documents['enhancements/one/prd.md']
        rows, count = self.run_score([verdict()])
        self.assertEqual(count, 1)
        self.assertEqual(rows[0]['verdict'], 'Error')
        self.assertIn('prd_content', rows[0]['summary'])

    def test_missing_plan_blocks_design_but_prd_only_and_removed_feature_pass(self):
        with patch.object(tp_review, 'fetch_pr_file', side_effect=lambda repo, sha, path, **kw: self.documents.get(path)):
            del self.documents['enhancements/one/testplan.md']
            rows = tp_review.score_pr(PR, self.files[:1], skills_path='unused', model='unused', shadow=True)
            self.assertEqual(rows[0]['verdict'], 'Error')
            del self.documents['enhancements/one/design.md']
            self.files[0]['filename'] = 'enhancements/one/prd.md'
            rows = tp_review.score_pr(PR, self.files[:1], skills_path='unused', model='unused', shadow=True)
            self.assertEqual(rows[0]['verdict'], 'Not applicable')
            self.files[0]['filename'] = 'enhancements/one/testplan.md'
            rows = tp_review.score_pr(PR, self.files[:1], skills_path='unused', model='unused', shadow=True)
            self.assertEqual(rows[0]['verdict'], 'Error')
            self.documents = {}
            self.files[0]["status"] = "removed"
            with patch.object(tp_review, 'enhancement_exists', return_value=False):
                rows = tp_review.score_pr(PR, self.files[:1], skills_path='unused', model='unused', shadow=True)
            self.assertEqual(rows[0]['verdict'], 'Not applicable')

    def test_stale_head_after_model_call_does_not_publish_result(self):
        with scoring_fixture() as skills, tempfile.TemporaryDirectory() as directory:
            hooks = TestPlanHooks(repo='test/repo', skills_path=str(skills),
                                  pr_data=dict(testplan_content='plan', design_content='design', prd_content='prd'))
            with patch.object(tp_review, 'complete', return_value=(json.dumps(verdict()), {})), patch.object(
                tp_review, 'get_pull_request', return_value={'head': {'sha': 'b' * 40}},
            ), patch.object(hooks, 'apply_labels') as publish:
                with self.assertRaisesRegex(RuntimeError, 'head changed'):
                    tp_review.run_review(hooks, 'test-plan-score', 'TP-42',
                                         {'number': 42, 'headRefOid': SHA}, directory, model='test')
                publish.assert_not_called()

    def test_old_scoring_skill_is_not_used_as_a_gate(self):
        with scoring_fixture() as skills:
            (skills / 'skills/test-plan-score/SKILL.md').write_text('Old rubric')
            hooks = TestPlanHooks(repo='test/repo', skills_path=str(skills))
            with self.assertRaisesRegex(RuntimeError, 'OSAC-4840'):
                hooks._score_prompt()

    def test_missing_reference_and_source_guidance_block(self):
        with scoring_fixture() as skills, tempfile.TemporaryDirectory() as directory:
            (skills / CONTEXT_FILES[0]).unlink()
            hooks = TestPlanHooks(repo='test/repo', skills_path=str(skills),
                                  pr_data=dict(testplan_content='plan', design_content='design', prd_content='prd'))
            with self.assertRaisesRegex(RuntimeError, 'Missing scoring reference'):
                hooks._write_score_context('TP-42', {}, directory)

    def test_aggregate_failure_and_shadow_mode_cannot_bypass_nonready(self):
        for result in ('Ready', 'Revise', 'Rework', 'Error'):
            with self.subTest(result=result), tempfile.TemporaryDirectory() as directory, working_directory(directory):
                rows = [{'path': 'enhancements/one/testplan.md', **verdict(result)}]
                with patch.dict(os.environ, {'PR_NUMBER': '42', 'PR_HEAD_SHA': SHA, 'TP_SHADOW': 'true', 'TP_OSAC_PATH': '/unused'}), patch.object(
                    tp_review, 'get_pull_request', return_value=PR,
                ), patch.object(tp_review, 'get_changed_files', return_value=self.files), patch.object(
                    tp_review, 'score_pr', return_value=rows,
                ), patch.object(tp_review, 'git_sha', return_value=SHA):
                    rc = tp_review.score_main()
                self.assertEqual(rc, 0 if result == 'Ready' else 1)
                report = json.loads(tp_review.SCORE_REPORT.read_text())
                self.assertEqual(report['conclusion'], 'success' if result == 'Ready' else 'failure')

    def test_report_write_preparation_error_cannot_leave_success(self):
        with tempfile.TemporaryDirectory() as directory, working_directory(directory), patch.dict(
            os.environ, {'PR_NUMBER': '42', 'PR_HEAD_SHA': SHA},
        ), patch.object(tp_review, 'get_pull_request', return_value=PR), patch.object(
            tp_review, 'get_changed_files', return_value=[],
        ), patch.object(tp_review, 'score_pr', return_value=[]), patch.object(
            tp_check, 'report_summary', side_effect=RuntimeError('Cannot summarize'),
        ):
            self.assertEqual(tp_review.score_main(), 1)
            self.assertEqual(json.loads(tp_review.SCORE_REPORT.read_text())['conclusion'], 'failure')

    def test_duplicate_json_fields_are_not_accepted(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            tp_review.parse_verdict('{"verdict": "Rework", "verdict": "Ready"}')

    def test_response_revision_starts_a_new_score_check(self):
        original = {**PR, 'head': {**PR['head'], 'repo': {'full_name': tp_review.REPO}}}
        revised = {**original, 'head': {**original['head'], 'sha': 'b' * 40}}
        with patch.dict(os.environ, {'PR_NUMBER': '42', 'PR_HEAD_SHA': SHA, 'TP_SHADOW': 'false'}), patch.object(
            tp_review, 'get_pull_request', side_effect=[original, revised],
        ), patch.object(tp_review, 'get_changed_files', return_value=self.files), patch.object(
            tp_review, 'fetch_pr_documents', return_value={'head_repo': tp_review.REPO},
        ), patch.object(tp_review, 'run_review'), patch.object(tp_check, 'start') as start, patch.object(
            tp_review, 'score_main', return_value=1,
        ) as score:
            self.assertEqual(tp_review.respond_main(), 1)
            start.assert_called_once_with(tp_review.REPO, 'b' * 40)
            score.assert_called_once()
            self.assertEqual(os.environ['PR_HEAD_SHA'], 'b' * 40)

    def test_bad_json_and_model_failure_block(self):
        for output in (('not json', {}), RuntimeError('Model unavailable')):
            with self.subTest(output=output), scoring_fixture() as skills, tempfile.TemporaryDirectory() as directory:
                hooks = TestPlanHooks(repo='test/repo', skills_path=str(skills),
                                      pr_data=dict(testplan_content='plan', design_content='design', prd_content='prd'))
                with patch.object(tp_review, 'complete', side_effect=output if isinstance(output, Exception) else None,
                                  return_value=output if not isinstance(output, Exception) else None), patch.object(
                    tp_review, 'get_pull_request', return_value=PR,
                ):
                    with self.assertRaises((RuntimeError, json.JSONDecodeError)):
                        tp_review.run_review(hooks, 'test-plan-score', 'TP-42',
                                             {'number': 42, 'headRefOid': SHA}, directory, model='test')


class CheckLifecycleTests(unittest.TestCase):
    def test_finish_requires_current_head_success_and_matching_report(self):
        for live_sha, status, report_sha, conclusion, expected in (
            (SHA, 'success', SHA, 'success', 'success'),
            (SHA, 'failure', SHA, 'success', 'failure'),
            (SHA, 'success', SHA, 'failure', 'failure'),
            (SHA, 'success', 'b' * 40, 'success', 'failure'),
            ('b' * 40, 'success', SHA, 'success', 'cancelled'),
        ):
            with self.subTest(expected=expected, status=status, conclusion=conclusion), tempfile.TemporaryDirectory() as directory, working_directory(directory):
                tp_check.STATE_PATH.write_text(json.dumps({'id': 123, 'head_sha': SHA}))
                tp_check.REPORT_PATH.parent.mkdir()
                tp_check.REPORT_PATH.write_text(json.dumps({'head_sha': report_sha, 'conclusion': conclusion}))
                with patch.object(tp_check, 'api', side_effect=[{'head': {'sha': live_sha}}, {}]) as api:
                    rc = tp_check.finish('test/repo', '42', status)
                self.assertEqual(api.call_args.kwargs['payload']['conclusion'], expected)
                self.assertEqual(rc, 0 if expected == 'success' else 1)
                self.assertTrue(api.call_args.args[0].endswith('/check-runs/123'))

    def test_setup_failure_finalizes_without_a_report(self):
        with tempfile.TemporaryDirectory() as directory, working_directory(directory):
            tp_check.STATE_PATH.write_text(json.dumps({'id': 123, 'head_sha': SHA}))
            with patch.object(tp_check, 'api', side_effect=[PR, {}]) as api:
                self.assertEqual(tp_check.finish('test/repo', '42', 'failure'), 1)
            self.assertEqual(api.call_args.kwargs['payload']['conclusion'], 'failure')

    def test_invalid_report_is_finalized_as_failure(self):
        with tempfile.TemporaryDirectory() as directory, working_directory(directory):
            tp_check.STATE_PATH.write_text(json.dumps({'id': 123, 'head_sha': SHA}))
            tp_check.REPORT_PATH.parent.mkdir()
            tp_check.REPORT_PATH.write_text('broken json')
            with patch.object(tp_check, 'api', side_effect=[PR, {}]) as api:
                self.assertEqual(tp_check.finish('test/repo', '42', 'success'), 1)
            self.assertEqual(api.call_args.kwargs['payload']['conclusion'], 'failure')

    def test_start_attaches_check_to_full_pr_sha(self):
        with tempfile.TemporaryDirectory() as directory, working_directory(directory), patch.dict(os.environ, {'GITHUB_RUN_ID': '99'}):
            with patch.object(tp_check, 'api', return_value={'id': 123}) as api:
                tp_check.start('test/repo', SHA)
            payload = api.call_args.kwargs['payload']
            self.assertEqual(payload['head_sha'], SHA)
            self.assertEqual(payload['name'], 'Test Plan Score')
            self.assertEqual(json.loads(tp_check.STATE_PATH.read_text())['id'], 123)

    def test_applicability_needs_no_model_or_cloud_credentials(self):
        for filename, entries, needs_review, conclusion in (
            ('README.md', None, False, 'success'),
            ('enhancements/one/prd.md', ['prd.md'], False, 'success'),
            ('enhancements/one/design.md', ['design.md', 'prd.md'], False, 'failure'),
            ('enhancements/one/prd.md', ['design.md', 'prd.md', 'testplan.md'], True, 'failure'),
            ('enhancements/one/TestPlan.md', None, False, 'success'),
            ('enhancements/one/testplan.md', ['diagram.png'], False, 'failure'),
        ):
            with self.subTest(filename=filename, entries=entries), tempfile.TemporaryDirectory() as directory, working_directory(directory):
                output = Path('output.txt')
                responses = [{**PR, 'changed_files': 1}, [{'filename': filename, 'status': 'removed' if entries is None and filename.startswith('enhancements/') else 'modified'}]]
                if entries is not None or filename.startswith('enhancements/'):
                    responses.append(None if entries is None else [{'name': name} for name in entries])
                with patch.dict(os.environ, {'GITHUB_OUTPUT': str(output)}), patch.object(tp_check, 'api', side_effect=responses):
                    tp_check.prepare('test/repo', '42', SHA)
                self.assertEqual(output.read_text(), f'needs_review={str(needs_review).lower()}\n')
                self.assertEqual(json.loads(tp_check.REPORT_PATH.read_text())['conclusion'], conclusion)

    def test_absent_directory_cannot_hide_a_modified_document(self):
        with patch.object(tp_check, 'api', side_effect=[
            {**PR, 'changed_files': 1},
            [{'filename': 'enhancements/one/design.md', 'status': 'modified'}], None,
        ]):
            with self.assertRaisesRegex(RuntimeError, 'unavailable'):
                tp_check.prepare('test/repo', '42', SHA)

    def test_incomplete_api_listing_blocks(self):
        with patch.object(tp_check, 'api', side_effect=[{**PR, 'changed_files': 100}, []]):
            with self.assertRaisesRegex(RuntimeError, 'Incomplete'):
                tp_check.prepare('test/repo', '42', SHA)

    def test_only_absence_is_optional_not_permission_or_network_failure(self):
        for message, absent in (('gh: Not Found (HTTP 404)', True), ('gh: Forbidden (HTTP 403)', False), ('network unavailable', False)):
            with self.subTest(message=message), patch.object(subprocess, 'run') as run:
                run.return_value.returncode = 1
                run.return_value.stderr = message
                if absent:
                    self.assertIsNone(tp_check.api('test', optional=True))
                    self.assertIsNone(tp_review.fetch_pr_file('test/repo', SHA, 'test'))
                else:
                    with self.assertRaises(RuntimeError):
                        tp_check.api('test', optional=True)
                    with self.assertRaises(RuntimeError):
                        tp_review.fetch_pr_file('test/repo', SHA, 'test')

    def test_feedback_is_escaped(self):
        summary = tp_check.report_summary({'plans': [{'path': '<script>|@all', 'verdict': 'Error', 'summary': 'line\nnext'}]})
        self.assertNotIn('<script>', summary)
        self.assertNotIn('@all', summary)
        self.assertIn('line next', summary)


class GroundingTests(unittest.TestCase):
    def test_rename_selects_both_features_and_rejects_traversal(self):
        files = [{'filename': 'enhancements/two/TestPlan.md', 'previous_filename': 'enhancements/one/testplan.md'},
                 {'filename': 'enhancements/../testplan.md'}, {'filename': 'enhancements/one/nested/testplan.md'}]
        self.assertEqual(tp_gate.affected_enhancements(files), ['one', 'two'])

    def test_grounding_uses_tracked_sources_and_records_unavailable_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '-q', directory], check=True)
            for name in ('AGENTS.md', 'docs/INTEGRATION-TESTING.md', *(f'{c}/AGENTS.md' for c in tp_gate.COMPONENTS), 'osac-operator/Makefile', 'osac-operator/internal/test.go'):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('Guidance or test source')
            (root / 'osac-operator/untracked.go').write_text('Must not be loaded')
            subprocess.run(['git', '-C', directory, 'add', 'AGENTS.md', 'docs', *(f'{c}/AGENTS.md' for c in tp_gate.COMPONENTS), 'osac-operator/Makefile', 'osac-operator/internal'], check=True)
            with patch.object(tp_gate, 'git_sha', return_value=SHA):
                context = tp_gate.grounding_context(root, {'plan': 'osac-operator/internal/test.go osac-operator/untracked.go osac-operator/../../secret'})
            self.assertEqual(context['osac_sha'], SHA)
            self.assertIn('osac-operator/internal/test.go', context['files'])
            self.assertNotIn('osac-operator/untracked.go', context['files'])
            self.assertIn('osac-operator/untracked.go', context['unavailable_cited_paths'])


if __name__ == '__main__':
    unittest.main()

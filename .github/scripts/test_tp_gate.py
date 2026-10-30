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


def assessment(value=None):
    value = json.loads(json.dumps(value or verdict()))
    previous = value.pop('verdict')
    value.pop('total')
    caps = []
    if previous in ('Revise', 'Rework'):
        caps.append({'code': 'missing_required_case' if previous == 'Revise' else 'boundary_mismatch',
                     'caseIds': ['TC-FR1-01'], 'source': 'component map',
                     'detail': 'Required case missing' if previous == 'Revise' else 'Required real boundary uses a fake'})
    value['policy'] = {'integrationRequired': True, 'groundingUsable': True, 'caps': caps}
    return value


@contextmanager
def scoring_fixture():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        skill = root / 'skills/test-plan-score/SKILL.md'
        skill.parent.mkdir(parents=True)
        skill.write_text('Authoritative test skill\nIntegration-boundary Rework veto\nCI assessment mode\n')
        for name in CONTEXT_FILES:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('Authoritative scoring reference: ' + path.name
                            + (' undisclosed_dependencies' if path.name == 'ci-assessment.md' else ''))
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


class ApplicabilityPolicyTests(unittest.TestCase):
    def test_shared_policy_covers_aliases_missing_removed_and_prd_only(self):
        base = 'enhancements/feature'
        for names, exists, files, expected in [
            ({'TestPlan.md'}, True, [], 'Review'),
            ({'DESIGN.md'}, True, [], 'Error'),
            ({'prd.md'}, True, [], 'Not applicable'),
            (set(), False, [{'filename': base + '/testplan.md', 'status': 'removed'}], 'Not applicable'),
            ({'notes.md'}, True, [{'filename': base + '/testplan.md', 'status': 'removed'}], 'Error'),
            ({'notes.md'}, True, [{'filename': 'enhancements/other/testplan.md',
                                 'previous_filename': base + '/TestPlan.md', 'status': 'renamed'}], 'Error'),
        ]:
            with self.subTest(names=names, files=files):
                self.assertEqual(tp_gate.plan_applicability(base, names, exists, files), expected)

    def test_changed_missing_directory_is_not_treated_as_removed(self):
        with self.assertRaisesRegex(RuntimeError, 'unavailable'):
            tp_gate.plan_applicability('enhancements/feature', set(), False, [
                {'filename': 'enhancements/feature/design.md', 'status': 'modified'},
            ])


class ReviewBudgetTests(unittest.TestCase):
    def test_exact_plan_and_prompt_limits_are_allowed(self):
        tp_gate.enforce_review_budget(
            enhancement_count=tp_gate.MAX_AFFECTED_ENHANCEMENTS,
            plan_count=tp_gate.MAX_PLAN_FILES,
            prompt_sizes=[tp_gate.MAX_PROMPT_BYTES, tp_gate.MAX_PROMPT_BYTES],
        )

    def test_exceeding_any_fixed_limit_requires_splitting_the_pr(self):
        cases = (
            dict(enhancement_count=tp_gate.MAX_AFFECTED_ENHANCEMENTS + 1,
                 plan_count=1),
            dict(enhancement_count=1, plan_count=tp_gate.MAX_PLAN_FILES + 1),
            dict(enhancement_count=1, plan_count=1,
                 prompt_sizes=[tp_gate.MAX_PROMPT_BYTES + 1]),
            dict(enhancement_count=1, plan_count=3,
                 prompt_sizes=[tp_gate.MAX_PROMPT_BYTES] * 3),
        )
        for limits in cases:
            with self.subTest(limits=limits), self.assertRaisesRegex(
                RuntimeError, 'Split into smaller PRs',
            ):
                tp_gate.enforce_review_budget(**limits)

    def test_plan_count_includes_both_case_aliases(self):
        self.assertEqual(tp_gate.plan_file_count({'testplan.md'}), 1)
        self.assertEqual(tp_gate.plan_file_count({'TestPlan.md'}), 1)
        self.assertEqual(
            tp_gate.plan_file_count({'testplan.md', 'TestPlan.md'}), 2,
        )


class CaseDefinitionTests(unittest.TestCase):
    def test_audit_and_matrix_references_cannot_replace_case_definitions(self):
        plan = "| E-I | TC-FR4-01, TC-FR4-02 |\n#### TC-FR4-01: Isolation\n"
        self.assertEqual(tp_gate.validate_case_definitions(plan), [
            'Referenced test cases have no definition heading: TC-FR4-02',
        ])

    def test_defined_case_references_pass(self):
        self.assertEqual(tp_gate.validate_case_definitions(
            '| E-I | TC-FR4-01 |\n#### TC-FR4-01: Isolation\n'), [])

    def test_code_and_comments_are_not_definitions_or_references(self):
        for fence in ('```', '~~~~'):
            with self.subTest(fence=fence):
                plan = ('TC-FR4-01\n' + fence + '\n#### TC-FR4-01: example\n'
                        + fence + '\n<!-- #### TC-FR4-01: comment -->')
                self.assertIn('TC-FR4-01', tp_gate.validate_case_definitions(plan)[0])
                self.assertEqual(tp_gate.validate_case_definitions(
                    fence + '\nTC-FR4-02\n' + fence), [])

    def test_fence_with_info_string_does_not_close_open_fence(self):
        plan = (
            '| E-I | TC-FR4-01 |\n'
            '```\n'
            '```bash\n'
            '#### TC-FR4-01: Example in code\n'
            '```\n'
        )
        self.assertEqual(tp_gate.validate_case_definitions(plan), [
            'Referenced test cases have no definition heading: TC-FR4-01',
        ])

    def test_backtick_in_info_string_does_not_open_backtick_fence(self):
        plan = (
            '| E-I | TC-FR4-01 |\n'
            '```bash`code\n'
            '#### TC-FR4-01: Visible definition\n'
        )
        self.assertEqual(tp_gate.validate_case_definitions(plan), [])

    def test_duplicate_definitions_fail(self):
        self.assertEqual(tp_gate.validate_case_definitions(
            '#### TC-FR4-01: One\n#### TC-FR4-01: Two'), [
                'Duplicate test-case definition headings: TC-FR4-01',
            ])

    def test_legacy_text_without_case_ids_remains_model_reviewable(self):
        self.assertEqual(tp_gate.validate_case_definitions('A legacy plan'), [])


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
            tp_review, 'complete', side_effect=[(json.dumps(assessment(v)), {}) for v in outputs],
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

    def test_oversized_final_plan_blocks_every_model_call(self):
        self.documents['enhancements/two/testplan.md']['content'] = (
            '界' * (tp_gate.MAX_PROMPT_BYTES // 3 + 1)
        )
        with scoring_fixture() as skills, tempfile.TemporaryDirectory() as directory, working_directory(directory):
            def fetch(repo, sha, path, **kw):
                return self.documents.get(path)

            with patch.object(tp_review, 'fetch_pr_file', side_effect=fetch), patch.object(
                tp_review, 'complete', return_value=(json.dumps(assessment()), {}),
            ) as model:
                with self.assertRaisesRegex(RuntimeError, 'Split into smaller PRs'):
                    tp_review.score_pr(
                        PR, self.files, skills_path=str(skills),
                        model='test-model', shadow=True,
                    )
            model.assert_not_called()

    def test_aggregate_prompt_limit_blocks_before_first_model_call(self):
        self.files = [
            {'filename': f'enhancements/{slug}/testplan.md', 'status': 'modified'}
            for slug in ('one', 'two', 'three')
        ]
        self.documents['enhancements/three/testplan.md'] = {
            'content': 'x' * 900_000, 'sha': 'blob',
        }
        for name in ('design.md', 'prd.md'):
            self.documents[f'enhancements/three/{name}'] = {
                'content': 'Supporting document', 'sha': 'blob',
            }
        for slug in ('one', 'two', 'three'):
            self.documents[f'enhancements/{slug}/testplan.md'] = {
                'content': 'x' * 900_000, 'sha': 'blob',
            }
        with scoring_fixture() as skills, tempfile.TemporaryDirectory() as directory, working_directory(directory):
            def fetch(repo, sha, path, **kw):
                return self.documents.get(path)

            with patch.object(tp_review, 'fetch_pr_file', side_effect=fetch), patch.object(
                tp_review, 'complete', return_value=(json.dumps(assessment()), {}),
            ) as model:
                with self.assertRaisesRegex(RuntimeError, 'Split into smaller PRs'):
                    tp_review.score_pr(
                        PR, self.files, skills_path=str(skills),
                        model='test-model', shadow=True,
                    )
            model.assert_not_called()

    def test_invalid_model_result_does_not_prevent_other_plan_evaluation(self):
        bad = verdict()
        bad['scores']['grounding'] = True
        rows, count = self.run_score([bad, verdict()])
        self.assertEqual(count, 2)
        self.assertEqual([r['verdict'] for r in rows], ['Error', 'Ready'])

    def test_undefined_case_blocks_before_model_but_other_plan_still_scored(self):
        self.documents['enhancements/one/testplan.md']['content'] = (
            '| Required isolation | TC-FR4-01 |\n#### TC-FR1-01: Read volume\n'
        )
        rows, count = self.run_score([verdict()])
        self.assertEqual(count, 1)
        self.assertEqual([row['verdict'] for row in rows], ['Error', 'Ready'])
        self.assertIn('TC-FR4-01', rows[0]['summary'])

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

    def test_response_revision_waits_past_four_seconds_then_scores(self):
        original = {**PR, 'head': {**PR['head'], 'repo': {'full_name': tp_review.REPO}}}
        revised = {**original, 'head': {**original['head'], 'sha': 'b' * 40}}
        with patch.dict(os.environ, {'PR_NUMBER': '42', 'PR_HEAD_SHA': SHA, 'TP_SHADOW': 'false'}), patch.object(
            tp_review, 'get_pull_request', side_effect=[original] * 5 + [revised],
        ) as pull, patch.object(tp_review, 'get_changed_files', return_value=self.files), patch.object(
            tp_review, 'fetch_pr_file', return_value={'content': 'plan', 'sha': 'blob'},
        ), patch.object(
            tp_review, 'fetch_pr_documents', return_value={'head_repo': tp_review.REPO},
        ), patch.object(tp_review, 'run_review', return_value={'response_commit_sha': 'b' * 40}), patch.object(tp_review.time, 'sleep') as sleep, patch.object(tp_check, 'start') as start, patch.object(
            tp_review, 'score_main', return_value=1,
        ) as score:
            self.assertEqual(tp_review.respond_main(), 1)
            start.assert_called_once_with(tp_review.REPO, 'b' * 40)
            score.assert_called_once()
            self.assertEqual(os.environ['PR_HEAD_SHA'], 'b' * 40)
            sleep_durations = [entry.args[0] for entry in sleep.call_args_list]
            self.assertEqual(sleep_durations, [1, 2, 4, 8])
            self.assertGreater(sum(sleep_durations), 4)
            self.assertEqual(pull.call_count, 6)

    def test_response_head_move_or_staleness_finalizes_the_check_without_scoring(self):
        original = {**PR, 'head': {**PR['head'], 'repo': {'full_name': tp_review.REPO}}}
        moved = {**original, 'head': {**original['head'], 'sha': 'c' * 40}}
        cases = (
            ([original, moved], 'c' * 40, 'head moved', []),
            ([original] * 9, SHA, 'not yet visible', [1, 2, 4, 8, 10, 10, 10]),
        )
        for reads, current_sha, error, expected_sleeps in cases:
            with self.subTest(current_sha=current_sha), tempfile.TemporaryDirectory() as directory, working_directory(directory), patch.dict(os.environ, {
                'PR_NUMBER': '42', 'PR_HEAD_SHA': SHA, 'TP_SHADOW': 'false',
                'GITHUB_RUN_ID': '99',
            }), patch.object(tp_review, 'IN_CI', False), patch.object(
                tp_review, 'get_pull_request', side_effect=reads,
            ) as pull, patch.object(tp_review, 'get_changed_files', return_value=self.files), patch.object(
                tp_review, 'fetch_pr_file', return_value={'content': 'plan', 'sha': 'blob'},
            ), patch.object(
                tp_review, 'fetch_pr_documents', return_value={'head_repo': tp_review.REPO},
            ), patch.object(
                tp_review, 'run_review', return_value={'response_commit_sha': 'b' * 40},
            ), patch.object(tp_review.time, 'sleep') as sleep, patch.object(
                tp_check, 'api', side_effect=[
                    {'id': 123}, {'head': {'sha': current_sha}}, {},
                ],
            ) as check_api, patch.object(tp_review, 'score_main') as score:
                with self.assertRaisesRegex(RuntimeError, error):
                    tp_review.respond_main()
                score.assert_not_called()
                self.assertEqual(pull.call_count, len(reads))
                self.assertEqual(
                    [entry.args[0] for entry in sleep.call_args_list],
                    expected_sleeps,
                )
                self.assertEqual(tp_check.finish(tp_review.REPO, '42', 'failure'), 1)
                self.assertEqual(
                    check_api.call_args_list[-1].kwargs['payload']['conclusion'],
                    'cancelled',
                )

    def test_response_rejects_oversized_plan_batch_before_revision_request(self):
        pr = {**PR, 'head': {**PR['head'], 'repo': {'full_name': tp_review.REPO}}}
        files = [
            {'filename': f'enhancements/{slug}/testplan.md', 'status': 'modified'}
            for slug in ('one', 'two', 'three')
        ]
        with patch.dict(os.environ, {'PR_NUMBER': '42', 'PR_HEAD_SHA': SHA}), patch.object(
            tp_review, 'get_pull_request', return_value=pr,
        ), patch.object(tp_review, 'get_changed_files', return_value=files), patch.object(
            tp_review, 'fetch_pr_file', return_value={'content': 'plan', 'sha': 'blob'},
        ) as fetch, patch.object(
            tp_review, 'fetch_pr_documents', return_value={'head_repo': tp_review.REPO},
        ) as documents, patch.object(tp_review, 'run_review') as review:
            with self.assertRaisesRegex(RuntimeError, 'Split into smaller PRs'):
                tp_review.respond_main()
        self.assertEqual(fetch.call_count, 2 * len(files))
        documents.assert_not_called()
        review.assert_not_called()

    def test_bad_json_and_model_failure_block(self):
        for output in (('not json', {}), RuntimeError('Model unavailable')):
            with self.subTest(output=output), scoring_fixture() as skills, tempfile.TemporaryDirectory() as directory:
                hooks = TestPlanHooks(repo='test/repo', skills_path=str(skills),
                                      pr_data=dict(testplan_content='plan', design_content='design', prd_content='prd'))
                with patch.object(tp_review, 'complete', side_effect=output if isinstance(output, Exception) else None,
                                  return_value=output if not isinstance(output, Exception) else None) as model, patch.object(
                    tp_review, 'get_pull_request', return_value=PR,
                ):
                    with self.assertRaises((RuntimeError, json.JSONDecodeError)):
                        tp_review.run_review(hooks, 'test-plan-score', 'TP-42',
                                             {'number': 42, 'headRefOid': SHA}, directory, model='test')
                self.assertIn('exactly one serialized JSON object', model.call_args.args[1])
                if isinstance(output, Exception):
                    self.assertFalse((Path(directory) / 'model-usage.json').exists())
                else:
                    self.assertEqual(json.loads((Path(directory) / 'model-usage.json').read_text()), {})
                    self.assertFalse((Path(directory) / 'verdict.json').exists())
                self.assertFalse((Path(directory) / 'model-output.txt').exists())


class BoundedUsageTests(unittest.TestCase):
    def test_unknown_fields_and_unexpected_types_are_dropped(self):
        self.assertEqual(tp_review.bounded_usage({
            'input_tokens': 100, 'output_tokens': 50, 'stop_reason': 'end_turn',
            'cache_read_input_tokens': 9999, 'model': 'secret-or-junk',
            'nested': {'unexpected': 'provider data'}, 'input_tokens_str': '7',
            'stop_reason_extra': True,
        }), {'input_tokens': 100, 'output_tokens': 50,
             'stop_reason': 'end_turn'})
        self.assertEqual(tp_review.bounded_usage('not a dict'), {})
        self.assertEqual(tp_review.bounded_usage(None), {})
        self.assertEqual(tp_review.bounded_usage(
            {'input_tokens': True, 'stop_reason': 7, 'output_tokens': None}),
            {'stop_reason': tp_review.INVALID_STOP_REASON})

    def test_non_string_stop_reason_still_fails_closed_in_review(self):
        with scoring_fixture() as skills, tempfile.TemporaryDirectory() as directory:
            hooks = TestPlanHooks(repo='test/repo', skills_path=str(skills),
                                  pr_data=dict(testplan_content='plan', design_content='design', prd_content='prd'))
            with patch.object(tp_review, 'complete',
                              return_value=('{}', {'stop_reason': 7})), patch.object(
                tp_review, 'get_pull_request', return_value=PR,
            ):
                with self.assertRaisesRegex(RuntimeError, 'ended early'):
                    tp_review.run_review(hooks, 'test-plan-score', 'TP-42',
                                         {'number': 42, 'headRefOid': SHA}, directory, model='test')

    def test_long_string_values_are_truncated(self):
        usage = tp_review.bounded_usage({
            'input_tokens': 1, 'stop_reason': 'x' * 500,
        })
        self.assertEqual(usage, {'input_tokens': 1,
                                 'stop_reason': 'x' * tp_review.USAGE_VALUE_LIMIT})

    def test_oversized_payload_is_reduced_then_emptied(self):
        payload = {'input_tokens': 3, 'output_tokens': 4,
                   'stop_reason': 'end_turn'}
        with patch.object(tp_review, 'USAGE_PAYLOAD_LIMIT', 45):
            self.assertEqual(tp_review.bounded_usage(payload),
                             {'input_tokens': 3, 'output_tokens': 4})
        with patch.object(tp_review, 'USAGE_PAYLOAD_LIMIT', 8):
            self.assertEqual(tp_review.bounded_usage(payload), {})


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

    def test_prepare_caps_affected_enhancements_before_directory_fetches(self):
        files = [
            {'filename': f'enhancements/feature-{i}/design.md', 'status': 'modified'}
            for i in range(tp_gate.MAX_AFFECTED_ENHANCEMENTS + 1)
        ]
        with patch.object(tp_check, 'api', side_effect=[
            {**PR, 'changed_files': len(files)}, files,
        ]) as api:
            with self.assertRaisesRegex(RuntimeError, 'Split into smaller PRs'):
                tp_check.prepare('test/repo', '42', SHA)
        self.assertEqual(api.call_count, 2)

    def test_prepare_counts_unchanged_plan_aliases_across_affected_enhancements(self):
        files = [
            {'filename': 'enhancements/one/design.md', 'status': 'modified'},
            {'filename': 'enhancements/two/prd.md', 'status': 'modified'},
            {'filename': 'enhancements/three/design.md', 'status': 'modified'},
        ]
        listing = lambda *names: [{'name': name} for name in names]
        with patch.object(tp_check, 'api', side_effect=[
            {**PR, 'changed_files': len(files)}, files,
            listing('design.md', 'testplan.md'),
            listing('DESIGN.md', 'TestPlan.md', 'testplan.md'),
            listing('prd.md', 'TestPlan.md', 'testplan.md'),
        ]) as api:
            with self.assertRaisesRegex(
                RuntimeError, '5 plan files.*Split into smaller PRs',
            ):
                tp_check.prepare('test/repo', '42', SHA)
        self.assertEqual(api.call_count, 5)

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
                context = tp_gate.grounding_context(root, {
                    'plan': 'osac-operator/internal/test.go. '
                            'osac-operator/untracked.go:1-2. '
                            'osac-operator/../../secret',
                })
            self.assertEqual(context['osac_sha'], SHA)
            self.assertIn('osac-operator/internal/test.go', context['files'])
            self.assertNotIn('osac-operator/internal/test.go.',
                             context['unavailable_cited_paths'])
            self.assertNotIn('osac-operator/untracked.go', context['files'])
            self.assertIn('osac-operator/untracked.go', context['unavailable_cited_paths'])

    def test_explicit_source_ranges_preserve_identity_and_full_guidance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '-q', directory], check=True)
            source = 'osac-operator/internal/example.go'
            for name in ('AGENTS.md', 'docs/INTEGRATION-TESTING.md',
                         *(f'{c}/AGENTS.md' for c in tp_gate.COMPONENTS), source):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('one\ntwo\nthree\nfour\nfive\n')
            subprocess.run(['git', '-C', directory, 'add', '.'], check=True)
            with patch.object(tp_gate, 'git_sha', return_value=SHA):
                context = tp_gate.grounding_context(root, {
                    'plan': f'{source}:2-3 {source}:5-5 osac-operator/AGENTS.md:2-3',
                })
                self.assertEqual(context['osac_sha'], SHA)
                self.assertEqual(context['excerpted_paths'][source], {
                    'ranges': [(2, 3), (5, 5)], 'total_lines': 5,
                })
                excerpt = context['files'][source]
                self.assertIn('other lines omitted', excerpt)
                self.assertIn('two\nthree\n', excerpt)
                self.assertIn('five\n', excerpt)
                self.assertNotIn('one\n', excerpt)
                self.assertNotIn('four\n', excerpt)
                self.assertEqual(context['files']['osac-operator/AGENTS.md'],
                                 'one\ntwo\nthree\nfour\nfive\n')
                full = tp_gate.grounding_context(root, {
                    'plan': f'{source}:2-3 {source}',
                })
                self.assertNotIn(source, full['excerpted_paths'])
                self.assertEqual(full['files'][source],
                                 'one\ntwo\nthree\nfour\nfive\n')

    def test_invalid_source_ranges_fail_before_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '-q', directory], check=True)
            source = 'osac-operator/internal/example.go'
            for name in ('AGENTS.md', 'docs/INTEGRATION-TESTING.md',
                         *(f'{c}/AGENTS.md' for c in tp_gate.COMPONENTS), source):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('one\ntwo\nthree\n')
            subprocess.run(['git', '-C', directory, 'add', '.'], check=True)
            for reference in (f'{source}:0-1', f'{source}:3-2',
                              f'{source}:2-4', f'{source}:2-4.',
                              f'{source}:2-4 {source}',
                              'osac-operator/AGENTS.md:2-4'):
                with self.subTest(reference=reference), self.assertRaisesRegex(
                        RuntimeError, 'Invalid source line range'):
                    tp_gate.grounding_context(root, {'plan': reference})


class PlanningPromptTests(unittest.TestCase):
    def test_ci_response_requests_small_edits_without_changing_legacy_format(self):
        hooks = TestPlanHooks(repo='test/repo', skills_path='unused')
        self.assertIn('replacements array', hooks._respond_prompt(patches=True))
        self.assertNotIn('Return the complete revised', hooks._respond_prompt(patches=True))
        self.assertIn('Return the complete revised', hooks._respond_prompt())

    def test_verdict_uses_numeric_band_with_only_defined_caps(self):
        with scoring_fixture() as skills:
            hooks = TestPlanHooks(repo='test/repo', skills_path=str(skills))
            prompt = hooks._score_prompt()
        self.assertIn('8-10 total with no zero requires Ready', prompt)
        self.assertIn('Consistency 1 alone is not a Revise cap', prompt)
        self.assertIn('identify the cap, affected case', prompt)

    def test_scoring_distinguishes_planned_coverage_from_execution(self):
        with scoring_fixture() as skills:
            hooks = TestPlanHooks(repo='test/repo', skills_path=str(skills))
            prompt = hooks._score_prompt()
        self.assertIn('planning gate, not an execution gate', prompt)
        self.assertIn('quality gates govern implemented code/releases', prompt)
        self.assertIn('Do not treat explicitly proposed work', prompt)
        self.assertIn('can receive Grounding 2 before they', prompt)
        self.assertIn('missing required case still caps readiness', prompt)
        self.assertIn('wrong-tier/faked required boundary', prompt)
        self.assertIn('undisclosed required-integration dependencies still triggers Rework', prompt)


class ResponseReplacementTests(unittest.TestCase):
    def test_invalid_revision_never_publishes_a_partial_document(self):
        hooks = TestPlanHooks(repo='test/repo', skills_path='unused',
                              pr_data={'testplan_content': 'same same'})
        output = json.dumps({'replacements': [{'old': 'same', 'new': 'edited'}]})
        with tempfile.TemporaryDirectory() as directory, patch.object(
            hooks, '_gh', return_value=''
        ), patch.object(tp_review, 'complete', return_value=(output, {})), patch.object(
            tp_review, 'get_pull_request', return_value=PR
        ), patch.object(hooks, 'apply_labels') as publish:
            with self.assertRaisesRegex(ValueError, 'match exactly once'):
                tp_review.run_review(hooks, 'test-plan-review', 'TP-42',
                                     {'number': 42, 'headRefOid': SHA}, directory,
                                     model='test')
            publish.assert_not_called()
            self.assertFalse((Path(directory) / 'testplan-output.md').exists())
            self.assertTrue((Path(directory) / 'model-usage.json').exists())
            self.assertFalse((Path(directory) / 'model-output.txt').exists())

    def test_edits_preserve_frontmatter_and_unchanged_ledger(self):
        original = '---\nauthor: user\n---\nledger remains\n### FR4\nold result\n### FR5\n'
        revised = tp_review.apply_response_replacements(original, {
            'replacements': [{'old': 'old result', 'new': 'specific new result'},
                             {'old': '### FR5\n', 'new': 'additional case\n### FR5\n'}],
        })
        self.assertEqual(revised, '---\nauthor: user\n---\nledger remains\n### FR4\nspecific new result\nadditional case\n### FR5\n')

    def test_ambiguous_missing_overlapping_and_malformed_edits_are_rejected(self):
        original = 'same same unique target'
        for replacements in (
            [], [{'old': 'same', 'new': 'changed'}],
            [{'old': 'missing', 'new': 'changed'}],
            [{'old': 'unique target', 'new': 'changed'}, {'old': 'target', 'new': 'other'}],
            [{'old': '', 'new': 'changed'}],
            [{'old': 'unique', 'new': 'unique'}],
            [{'old': 'unique', 'new': 1}],
            [{'old': 'unique', 'new': 'changed', 'path': '/tmp/other'}],
        ):
            with self.subTest(replacements=replacements), self.assertRaises(ValueError):
                tp_review.apply_response_replacements(original, {'replacements': replacements})


class AssessmentClassificationTests(unittest.TestCase):
    def test_ci_run_saves_assessment_separately_and_publishes_classified_schema(self):
        value = assessment()
        value['scores']['consistency'] = 1
        with scoring_fixture() as skills, tempfile.TemporaryDirectory() as directory:
            hooks = TestPlanHooks(repo='test/repo', skills_path=str(skills),
                                  pr_data={'testplan_content': 'plan', 'design_content': 'design', 'prd_content': 'prd'})
            with patch.object(tp_review, 'complete', return_value=(json.dumps(value), {})) as model, patch.object(
                tp_review, 'get_pull_request', return_value=PR,
            ):
                result = tp_review.run_review(hooks, 'test-plan-score', 'TP-42',
                                             {'number': 42, 'headRefOid': SHA}, directory,
                                             model='test', publish=False)
            self.assertEqual(result['verdict'], 'Ready')
            self.assertEqual(json.loads((Path(directory) / 'assessment.json').read_text()), value)
            public = json.loads((Path(directory) / 'verdict.json').read_text())
            self.assertEqual((public['total'], public['verdict']), (9, 'Ready'))
            self.assertNotIn('policy', public)
            self.assertIn('Do not emit verdict or total', model.call_args.args[1])

    def test_old_skill_protocol_is_rejected_before_a_model_request(self):
        with scoring_fixture() as skills, tempfile.TemporaryDirectory() as directory:
            (skills / 'skills/test-plan-score/SKILL.md').write_text('Integration-boundary Rework veto\n')
            hooks = TestPlanHooks(repo='test/repo', skills_path=str(skills),
                                  pr_data={'testplan_content': 'plan', 'design_content': 'design', 'prd_content': 'prd'})
            with patch.object(tp_review, 'complete') as model, self.assertRaisesRegex(RuntimeError, '0.4.0'):
                tp_review.run_review(hooks, 'test-plan-score', 'TP-42',
                                     {'number': 42, 'headRefOid': SHA}, directory,
                                     model='test', publish=False)
            model.assert_not_called()

    def test_pre_disclosure_protocol_is_rejected_before_a_model_request(self):
        with scoring_fixture() as skills, tempfile.TemporaryDirectory() as directory:
            (skills / 'skills/test-plan-score/references/ci-assessment.md').write_text('Old protocol')
            hooks = TestPlanHooks(repo='test/repo', skills_path=str(skills),
                                  pr_data={'testplan_content': 'plan', 'design_content': 'design', 'prd_content': 'prd'})
            with patch.object(tp_review, 'complete') as model, self.assertRaisesRegex(RuntimeError, '0.5.0'):
                tp_review.run_review(hooks, 'test-plan-score', 'TP-42',
                                     {'number': 42, 'headRefOid': SHA}, directory,
                                     model='test', publish=False)
            model.assert_not_called()

    def test_minor_consistency_issue_at_nine_is_ready_with_complete_policy_facts(self):
        value = assessment()
        value['scores']['consistency'] = 1
        value['feedback'] = 'Optional formatting improvement; no rubric cap applies.'
        result = tp_gate.classify_assessment(value)
        self.assertEqual((result['total'], result['verdict']), (9, 'Ready'))
        self.assertEqual(set(result), set(verdict()))
        self.assertNotIn('policy', result)

    def test_each_zero_dimension_is_rework_even_at_a_high_total(self):
        for key in tp_gate.SCORE_KEYS:
            value = assessment()
            value['scores'][key] = 0
            with self.subTest(dimension=key):
                result = tp_gate.classify_assessment(value)
                self.assertEqual((result['total'], result['verdict']), (8, 'Rework'))

    def test_named_caps_preserve_high_total_revocation_and_boundary_veto(self):
        for code, expected in [('missing_required_case', 'Revise'),
                               ('unusable_grounding', 'Revise'),
                               ('boundary_mismatch', 'Rework'),
                               ('undisclosed_dependencies', 'Rework')]:
            value = assessment()
            value['policy']['caps'] = [{'code': code, 'caseIds': ['TC-FR4-01'],
                                       'source': 'component required-boundary map',
                                       'detail': 'Evidence identifying this required gap/mismatch'}]
            with self.subTest(code=code):
                result = tp_gate.classify_assessment(value)
                self.assertEqual((result['total'], result['verdict']), (10, expected))

    def test_grounding_one_caps_required_integration_but_not_usable_unit_only_work(self):
        value = assessment()
        value['scores']['grounding'] = 1
        self.assertEqual(tp_gate.classify_assessment(value)['verdict'], 'Revise')
        value['policy']['integrationRequired'] = False
        self.assertEqual(tp_gate.classify_assessment(value)['verdict'], 'Ready')

    def test_numeric_bands_below_eight_still_require_revision(self):
        for total in (5, 6, 7):
            value = assessment()
            keys = sorted(tp_gate.SCORE_KEYS)
            value['scores'] = dict.fromkeys(keys, 1)
            for key in keys[:total - 5]:
                value['scores'][key] = 2
            with self.subTest(total=total):
                result = tp_gate.classify_assessment(value)
                self.assertEqual((result['total'], result['verdict']), (total, 'Revise'))

    def test_old_model_verdict_cannot_be_promoted_without_assessing_policy(self):
        old = verdict('Revise')
        old['scores']['consistency'] = 1
        old['total'] = 9
        with self.assertRaisesRegex(ValueError, 'no model verdict'):
            tp_gate.classify_assessment(old)

    def test_unknown_or_unsupported_caps_and_missing_source_evidence_fail(self):
        for change in (
            lambda v: v['policy'].update(integrationRequired=1),
            lambda v: v['policy'].pop('groundingUsable'),
            lambda v: v['policy'].update(groundingUsable=False),
            lambda v: v['scores'].update(grounding=True),
            lambda v: v.update(verdict='Ready'),
            lambda v: v['policy']['caps'].append({'code': 'formatting', 'caseIds': ['TC-1'], 'source': 'guide', 'detail': 'style'}),
            lambda v: v['policy']['caps'].append({'code': 'boundary_mismatch', 'caseIds': [], 'source': 'guide', 'detail': 'fake'}),
            lambda v: v['policy']['caps'].append({'code': 'missing_required_case', 'caseIds': ['TC-1'], 'source': '', 'detail': 'missing'}),
            lambda v: v['findings']['critical'].append('Unresolved blocking issue with no corresponding cap'),
        ):
            value = assessment()
            change(value)
            with self.subTest(assessment=value), self.assertRaises(ValueError):
                tp_gate.classify_assessment(value)


if __name__ == '__main__':
    unittest.main()

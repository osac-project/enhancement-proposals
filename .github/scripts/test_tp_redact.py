"""Redaction keeps credential-shaped model output out of published text."""

import base64
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import tp_check
import tp_hooks
import tp_redact
import tp_review
from test_tp_gate import (PR, SHA, assessment, scoring_fixture,
                          working_directory)
from tp_hooks import TestPlanHooks


def fixture_shaped(kind, filler='x'):
    """Assemble a sample credential-shaped input at runtime.

    The pieces come from tp_redact's named shape constants, so no test
    source line spells or assembles a vendor prefix or key label.
    """
    if kind == 'github':
        return tp_redact.GITHUB_TOKEN_PREFIXES[0] + filler * 36
    if kind == 'jwt':
        return (tp_redact.JWT_SEGMENT_PREFIX + 'A' * 24 + '.'
                + tp_redact.JWT_SEGMENT_PREFIX + 'B' * 24 + '.'
                + 'C' * 16)
    if kind == 'pem':
        return (tp_redact.PEM_OPEN_MARK + 'RSA '
                + tp_redact.PEM_KEY_LABEL + '-----\n'
                + 'k' * 40 + '\n'
                + tp_redact.PEM_CLOSE_MARK + 'RSA '
                + tp_redact.PEM_KEY_LABEL + '-----')
    if kind == 'basic':
        return base64.b64encode(b'fakeuser:fakepass').decode('ascii')
    raise ValueError(kind)


FAKE_SSN = '12' + '3-45-' + '6789'
FAKE_CARD = '4111' + ' 1111' + ' 1111' + ' 1111'
FAKE_CARD_DASHES = '4111' + '-1111' + '-1111' + '-1111'


class RedactionPatternTests(unittest.TestCase):
    def test_private_key_blocks_are_redacted(self):
        redacted = tp_redact.redact('leaked key:\n' + fixture_shaped('pem')
                                 + '\nafter')
        self.assertNotIn('k' * 40, redacted)
        self.assertNotIn(tp_redact.PEM_OPEN_MARK, redacted)
        self.assertNotIn(tp_redact.PEM_KEY_LABEL, redacted)
        self.assertIn(tp_redact.REDACTED, redacted)
        self.assertIn('leaked key:', redacted)
        self.assertIn('after', redacted)

    def test_authorization_and_bearer_values_are_redacted(self):
        self.assertEqual(
            tp_redact.redact('Authorization: Basic ' + fixture_shaped('basic')),
            'Authorization: Basic ' + tp_redact.REDACTED,
        )
        self.assertEqual(
            tp_redact.redact('authorization: Bearer ' + 'A' * 24),
            'authorization: Bearer ' + tp_redact.REDACTED,
        )
        self.assertEqual(
            tp_redact.redact('Authorization: ' + 'K' * 40),
            'Authorization: ' + tp_redact.REDACTED,
        )
        self.assertEqual(
            tp_redact.redact('bearer ' + 'A' * 30 + ' accepted'),
            'bearer ' + tp_redact.REDACTED + ' accepted',
        )

    def test_authorization_prose_survives(self):
        for prose in (
            '**Authorization:** tenant admin only',
            'Authorization: requires Cloud Provider Admin role',
            '| Authorization: | 403 for non-owners |',
            'Authorization: Basic auth is not used here',
        ):
            with self.subTest(prose=prose):
                self.assertEqual(tp_redact.redact(prose), prose)

    def test_provider_credentials_are_redacted(self):
        for prefix in tp_redact.GITHUB_TOKEN_PREFIXES:
            with self.subTest(prefix=prefix):
                self.assertEqual(
                    tp_redact.redact(prefix + 'x' * 36),
                    tp_redact.REDACTED,
                )
        self.assertEqual(
            tp_redact.redact(tp_redact.GITHUB_PAT_PREFIX + 'x' * 30),
            tp_redact.REDACTED)
        for prefix in tp_redact.AWS_KEY_PREFIXES:
            with self.subTest(prefix=prefix):
                self.assertEqual(
                    tp_redact.redact(prefix + '0123456789ABCDEF'),
                    tp_redact.REDACTED,
                )
        self.assertEqual(
            tp_redact.redact(tp_redact.GOOGLE_KEY_PREFIX + 'x' * 35),
            tp_redact.REDACTED)
        for prefix in tp_redact.SLACK_TOKEN_PREFIXES:
            with self.subTest(prefix=prefix):
                self.assertEqual(
                    tp_redact.redact(prefix + '1234567890-ABCDEF'),
                    tp_redact.REDACTED,
                )

    def test_jwt_is_redacted(self):
        redacted = tp_redact.redact('session ' + fixture_shaped('jwt')
                                 + ' persisted')
        self.assertNotIn(tp_redact.JWT_SEGMENT_PREFIX, redacted)
        self.assertIn(tp_redact.REDACTED, redacted)

    def test_sensitive_assignments_redact_only_values(self):
        for source, expected in (
            (f'password=hunter2', 'password=' + tp_redact.REDACTED),
            (f'"secret": "s3cr3t-value"',
             '"secret": "' + tp_redact.REDACTED + '"'),
            (f'api_key: ABC123', 'api_key: ' + tp_redact.REDACTED),
            (f'client_secret: oauth-value',
             'client_secret: ' + tp_redact.REDACTED),
            (f'aws_secret_access_key: wJalrXUtnFEMI',
             'aws_secret_access_key: ' + tp_redact.REDACTED),
            (f'client-key-data: LS0tLS1CRUdJTi',
             'client-key-data: ' + tp_redact.REDACTED),
            (f'client-certificate-data: LS0tLS1CRUdJ',
             'client-certificate-data: ' + tp_redact.REDACTED),
            (f'certificate-authority-data: LS0tLS1CRUd',
             'certificate-authority-data: ' + tp_redact.REDACTED),
            ('token: ' + fixture_shaped('jwt'),
             'token: ' + tp_redact.REDACTED),
        ):
            with self.subTest(source=source):
                self.assertEqual(tp_redact.redact(source), expected)

    def test_identifier_prefixed_keys_are_redacted(self):
        for source, expected in (
            ('ACCESS_TOKEN=abc123', 'ACCESS_TOKEN=' + tp_redact.REDACTED),
            ('access_token: val-1', 'access_token: ' + tp_redact.REDACTED),
            ('refresh_token: r-tok-987', 'refresh_token: ' + tp_redact.REDACTED),
            ('FAKE_GH_TOKEN=' + fixture_shaped('github'),
             'FAKE_GH_TOKEN=' + tp_redact.REDACTED),
            ('db_password=hunter2', 'db_password=' + tp_redact.REDACTED),
            ('DB_PASSWORD=hunter2', 'DB_PASSWORD=' + tp_redact.REDACTED),
            ('aws_session_token=XYZabc',
             'aws_session_token=' + tp_redact.REDACTED),
            ('authToken: abc123xyz', 'authToken: ' + tp_redact.REDACTED),
            ('"access_token": "val-1"',
             '"access_token": "' + tp_redact.REDACTED + '"'),
        ):
            with self.subTest(source=source):
                self.assertEqual(tp_redact.redact(source), expected)
        self.assertEqual(tp_redact.redact('the access token is rotated'),
                         'the access token is rotated')

    def test_us_ssn_is_redacted(self):
        self.assertEqual(tp_redact.redact(f'ssn {FAKE_SSN} on file'),
                         'ssn ' + tp_redact.REDACTED + ' on file')
        # A phone number formatted exactly like an SSN is redacted too:
        # over-redacting that format is safer than leaking a real SSN.
        self.assertEqual(tp_redact.redact('call 555-12-3456'),
                         'call ' + tp_redact.REDACTED)
        for invalid in ('000-45-6789', '666-45-6789', '900-12-3456',
                        '123-00-6789', '123-45-0000'):
            with self.subTest(invalid=invalid):
                self.assertEqual(tp_redact.redact(f'seen {invalid}'),
                                 f'seen {invalid}')

    def test_payment_cards_are_redacted_only_when_luhn_valid(self):
        self.assertEqual(tp_redact.redact(f'card {FAKE_CARD} charged'),
                         'card ' + tp_redact.REDACTED + ' charged')
        self.assertEqual(tp_redact.redact(f'card {FAKE_CARD_DASHES} charged'),
                         'card ' + tp_redact.REDACTED + ' charged')
        invalid = '4111' + ' 1111' + ' 1111' + ' 1112'
        self.assertEqual(tp_redact.redact(f'id {invalid} kept'),
                         f'id {invalid} kept')

    def test_session_and_cookie_values_are_redacted(self):
        self.assertEqual(tp_redact.redact('session_id: abc123xyz'),
                         'session_id: ' + tp_redact.REDACTED)
        self.assertEqual(tp_redact.redact('sessionId: value1'),
                         'sessionId: ' + tp_redact.REDACTED)
        self.assertEqual(tp_redact.redact('sid: sess-123'),
                         'sid: ' + tp_redact.REDACTED)
        self.assertEqual(
            tp_redact.redact('X-Session-Token: ' + 'A' * 30),
            'X-Session-Token: ' + tp_redact.REDACTED)
        cookie_value = 'B' * 20
        self.assertEqual(
            tp_redact.redact(f'Cookie: sessionid={cookie_value}; theme=dark'),
            'Cookie: sessionid=' + tp_redact.REDACTED + '; theme=dark')
        self.assertEqual(
            tp_redact.redact(f'Set-Cookie: session={cookie_value}'),
            'Set-Cookie: session=' + tp_redact.REDACTED)
        self.assertEqual(tp_redact.redact('Cookie: not used in this release'),
                         'Cookie: not used in this release')

    def test_email_addresses_are_redacted(self):
        redacted = tp_redact.redact('contact user.name+tag@example.com now')
        self.assertNotIn('example.com', redacted)
        self.assertIn(tp_redact.REDACTED, redacted)
        self.assertIn('contact', redacted)


class InternalHostRedactionTests(unittest.TestCase):
    def test_internal_ip_addresses_are_redacted(self):
        for address in ('10.0.0.1', '172.16.0.5', '172.31.255.1',
                        '192.168.1.10', '127.0.0.1', '169.254.1.1',
                        'fd00::1', 'fe80::1'):
            with self.subTest(address=address):
                self.assertEqual(
                    tp_redact.redact(f'connect to {address} now'),
                    'connect to ' + tp_redact.HOST_REDACTED + ' now')
        # Decision: a private address with a hyphen tag is still redacted;
        # it is far more likely a host reference than a version string.
        self.assertEqual(tp_redact.redact('builds on 10.0.0.5-rc1 today'),
                         'builds on ' + tp_redact.HOST_REDACTED
                         + '-rc1 today')

    def test_internal_hostnames_are_redacted(self):
        for host in ('fulfillment-service.osac.svc',
                     'keycloak.keycloak.svc.cluster.local',
                     'db.internal', 'printer.lan', 'portal.corp',
                     'wiki.intranet', 'raspi.home.arpa', 'host.local',
                     'my_db.internal'):
            with self.subTest(host=host):
                self.assertEqual(
                    tp_redact.redact(f'calls {host} internally'),
                    'calls ' + tp_redact.HOST_REDACTED + ' internally')
        # Underscore labels are replaced in full, with no leftover prefix.
        self.assertEqual(tp_redact.redact('at svc_a.ns.svc:8443 ready'),
                         'at ' + tp_redact.HOST_REDACTED + ':8443 ready')
        self.assertEqual(
            tp_redact.redact('at fulfillment-service.osac.svc:8443 ready'),
            'at ' + tp_redact.HOST_REDACTED + ':8443 ready')
        # A sentence-final dot and a path separator still end a hostname.
        self.assertEqual(
            tp_redact.redact('Call fulfillment-service.osac.svc.'),
            'Call ' + tp_redact.HOST_REDACTED + '.')
        self.assertEqual(
            tp_redact.redact('http://api.ci.local/healthz'),
            'http://' + tp_redact.HOST_REDACTED + '/healthz')

    def test_suffix_like_file_and_module_names_survive(self):
        unchanged = (
            'Edit settings.local.json and config.local.yaml, run '
            'python -m pkg.internal.mod, inspect foo.svc.go, read '
            'docs/internal/x.md and '
            'osac-operator/internal/controller/foo.go. '
            'Import tp_redact.local_rules and my_pkg.internal.mod.'
        )
        self.assertEqual(tp_redact.redact(unchanged), unchanged)

    def test_public_hosts_and_bare_names_survive(self):
        unchanged = (
            'See https://github.com/osac-project/osac/pull/375, '
            'https://redhat.atlassian.net/browse/OSAC-4542, '
            'registry quay.io and docs at example.com. '
            'The bare service name fulfillment-service and the resolver '
            '8.8.8.8 stay readable, as does version 1.2.3.4-beta.'
        )
        self.assertEqual(tp_redact.redact(unchanged), unchanged)


class PlanTextSurvivesRedactionTests(unittest.TestCase):
    def test_normal_plan_evidence_is_unchanged(self):
        unchanged = (
            'Commit f6dbd636792f16489dde9f5504ccc4ade2146f9a pins the plan. '
            'TC-FR4-01 covers osac-operator/internal/controller/foo.go:100-160 '
            'and proto/private/v1/volumes.proto. '
            '**Tokens:** 100 in / 50 out. '
            'Dates 2026-10-20 and runs 2026-10-20 2026-10-21 stay readable. '
            'The bare service name fulfillment-service stays readable. '
            'The rubric tokenizes each clause; authorization is delegated to OPA; '
            'the bearer of tokens is the tenant. '
            'Short prefixes like ' + tp_redact.AWS_KEY_PREFIXES[0] + '123 and '
            + tp_redact.GOOGLE_KEY_PREFIX + '1 and '
            + tp_redact.SLACK_TOKEN_PREFIXES[1] + 'abc stay readable.'
        )
        self.assertEqual(tp_redact.redact(unchanged), unchanged)

    def test_redaction_is_idempotent(self):
        once = tp_redact.redact('password=hunter2 '
                              + fixture_shaped('github'))
        self.assertEqual(tp_redact.redact(once), once)

    def test_keyed_rule_stops_at_the_first_value_token(self):
        # Prose after a sensitive key loses at most its first word; the
        # rest of the sentence stays readable.
        self.assertEqual(
            tp_redact.redact('secret: must be stored in a Secret'),
            'secret: ' + tp_redact.REDACTED + ' be stored in a Secret',
        )
        self.assertEqual(
            tp_redact.redact('token: required'),
            'token: ' + tp_redact.REDACTED,
        )
        self.assertEqual(tp_redact.redact('password field is masked'),
                         'password field is masked')


class RedactJsonTests(unittest.TestCase):
    def test_strings_are_redacted_recursively(self):
        redacted = tp_redact.redact_json({
            'summary': 'uses ' + fixture_shaped('github'),
            'findings': {'suggestions': ['email admin@example.com', 'clean']},
            'scores': {'grounding': 2},
            'nested': [{'note': 'password=hunter2'}],
        })
        self.assertNotIn(fixture_shaped('github'), json.dumps(redacted))
        self.assertNotIn('example.com', json.dumps(redacted))
        self.assertNotIn('hunter2', json.dumps(redacted))
        self.assertEqual(redacted['scores'], {'grounding': 2})
        self.assertEqual(redacted['findings']['suggestions'][1], 'clean')
        self.assertIn('scores', redacted)


class RedactionEndToEndTests(unittest.TestCase):
    def test_report_summary_redacts_raw_values_before_escaping(self):
        report = {
            'head_sha': 'a' * 40,
            'plans': [{'path': 'enhancements/one/testplan.md', 'total': 8,
                       'verdict': 'Revise',
                       'feedback': ('leaked ' + fixture_shaped('github', 'y')
                                    + ' by admin@example.com')}],
            'error': 'mail user@example.com with '
                     + fixture_shaped('github', 'y'),
        }
        summary = tp_check.report_summary(report)
        self.assertNotIn(fixture_shaped('github', 'y'), summary)
        self.assertNotIn('example.com', summary)
        self.assertNotIn('&#64;', summary)
        self.assertNotIn('@', summary)
        self.assertIn('REDACTED', summary)

    def test_replacement_values_are_redacted_and_anchors_still_apply(self):
        original = 'front matter\n### FR4\nold result\n### FR5\n'
        revised = tp_review.apply_response_replacements(original, {
            'replacements': [
                {'old': 'old result',
                 'new': 'specific result citing '
                        + fixture_shaped('github', 'z')},
                {'old': '### FR5\n', 'new': 'additional case\n### FR5\n'},
            ],
        })
        self.assertNotIn(fixture_shaped('github', 'z'), revised)
        self.assertIn(tp_redact.REDACTED, revised)
        self.assertIn('specific result citing', revised)
        self.assertIn('additional case\n### FR5\n', revised)
        self.assertIn('front matter', revised)

    def test_respond_preserves_author_text_and_redacts_model_edits(self):
        output = json.dumps({'replacements': [
            {'old': 'old result',
             'new': 'new evidence citing ' + fixture_shaped('github', 'z')},
        ]})
        plan = ('owner@example.com\n' + 'planning context line\n' * 40
                + '### FR4\nold result\n')
        hooks = TestPlanHooks(repo='test/repo', skills_path='unused',
                              pr_data={'testplan_content': plan})
        with tempfile.TemporaryDirectory() as directory, patch.object(
            hooks, '_gh', return_value='',
        ), patch.object(
            tp_review, 'complete', return_value=(output, {}),
        ), patch.object(
            tp_review, 'get_pull_request', return_value=PR,
        ), patch.object(hooks, 'apply_labels') as publish:
            tp_review.run_review(hooks, 'test-plan-review', 'TP-42',
                                 {'number': 42, 'headRefOid': SHA}, directory,
                                 model='test')
            publish.assert_called_once()
            revision = (Path(directory) / 'testplan-output.md').read_text()
            artifact = (Path(directory)
                        / 'testplan-output.redacted.md').read_text()
        # The committed revision keeps the author's untouched text.
        self.assertIn('owner@example.com', revision)
        self.assertIn('new evidence citing', revision)
        self.assertNotIn(fixture_shaped('github', 'z'), revision)
        self.assertIn(tp_redact.REDACTED, revision)
        # The uploaded artifact is fully redacted.
        self.assertNotIn('owner@example.com', artifact)
        self.assertNotIn(fixture_shaped('github', 'z'), artifact)
        self.assertIn(tp_redact.REDACTED, artifact)
        self.assertIn('new evidence citing', artifact)

    def test_generate_pr_gets_a_redacted_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'testplan-output.md'
            output.write_text('# Test Plan\n\nEvidence uses '
                              + fixture_shaped('github', 'g') + '\n')
            hooks = TestPlanHooks(repo='test/repo', skills_path='unused',
                                  shadow=False)
            with patch.object(
                hooks, '_gh', return_value='',
            ), patch.object(
                tp_hooks.subprocess, 'run',
            ) as run, working_directory(directory):
                hooks.apply_labels('TP-42', {}, 'generate', directory,
                                   ticket={'_ep_slug': 'osac-1',
                                           'title': 'Test title'})
            self.assertTrue(run.called)
            dest = Path(directory) / 'enhancements/osac-1/TestPlan.md'
            content = dest.read_text()
            self.assertNotIn(fixture_shaped('github', 'g'), content)
            self.assertIn(tp_redact.REDACTED, content)
            self.assertIn('# Test Plan', content)

    def test_model_secrets_never_reach_artifacts_comments_or_check_summary(self):
        value = assessment()
        value['summary'] = ('Admin token ' + fixture_shaped('github')
                            + ' in evidence')
        value['feedback'] = 'password: hunter2 and ' + fixture_shaped('jwt')
        value['criterionNotes']['grounding'] = 'contact admin@example.com'
        value['findings']['suggestions'] = [
            'bearer ' + fixture_shaped('github')]
        leaked = ('hunter2', 'admin@example.com')
        with scoring_fixture() as skills, tempfile.TemporaryDirectory() as directory:
            hooks = TestPlanHooks(
                repo='test/repo', skills_path=str(skills),
                pr_data=dict(testplan_content='plan', design_content='design',
                             prd_content='prd'),
            )
            with patch.object(
                tp_review, 'complete', return_value=(json.dumps(value), {}),
            ), patch.object(
                tp_review, 'get_pull_request', return_value=PR,
            ), patch.object(
                hooks, '_gh', return_value='',
            ), patch.object(hooks, '_upsert_score_comment') as upsert:
                tp_review.run_review(hooks, 'test-plan-score', 'TP-42',
                                     {'number': 42, 'headRefOid': SHA},
                                     directory, model='test')
            for name in ('assessment.json', 'verdict.json'):
                artifact = (Path(directory) / name).read_text()
                self.assertIn(tp_redact.REDACTED, artifact)
                self.assertNotIn(fixture_shaped('github'), artifact)
                self.assertNotIn(fixture_shaped('jwt'), artifact)
                for secret in leaked:
                    self.assertNotIn(secret, artifact)
            body = upsert.call_args.args[1]
            self.assertIn('REDACTED', body)
            self.assertNotIn(fixture_shaped('github'), body)
            self.assertNotIn(fixture_shaped('jwt'), body)
            for secret in leaked:
                self.assertNotIn(secret, body)
            report = {'head_sha': SHA, 'plans': [json.loads(
                (Path(directory) / 'verdict.json').read_text())]}
            report['plans'][0]['path'] = 'enhancements/one/testplan.md'
            summary = tp_check.report_summary(report)
            self.assertIn('REDACTED', summary)
            self.assertNotIn(fixture_shaped('github'), summary)
            self.assertNotIn(fixture_shaped('jwt'), summary)
            for secret in leaked:
                self.assertNotIn(secret, summary)


class ErrorLoggingRedactionTests(unittest.TestCase):
    def capture_stderr(self):
        stream = io.StringIO()
        return stream, contextlib.redirect_stderr(stream)

    def test_review_exception_is_redacted_before_logging(self):
        # IN_CI is read from GITHUB_ACTIONS when the module is imported;
        # patch the constant so the CI exit contract is deterministic.
        error = RuntimeError('provider failed with '
                             + fixture_shaped('github'))
        files = [{'filename': 'enhancements/one/testplan.md',
                  'status': 'modified'}]
        with patch.dict(os.environ, {'PR_NUMBER': '42'}), patch.object(
            tp_review, 'IN_CI', True,
        ), patch.object(
            tp_review, 'get_pull_request', return_value=PR,
        ), patch.object(
            tp_review, 'get_changed_files', return_value=files,
        ), patch.object(
            tp_review, 'fetch_pr_file', return_value=None,
        ), patch.object(
            tp_review, 'fetch_pr_documents',
            return_value={'head_repo': tp_review.REPO},
        ), patch.object(
            tp_review, 'run_review', side_effect=error,
        ):
            stream, redirect = self.capture_stderr()
            with redirect:
                with self.assertRaises(SystemExit) as raised:
                    tp_review.respond_main()
        self.assertEqual(raised.exception.code, 1)
        self.assertNotIn(fixture_shaped('github'), stream.getvalue())
        self.assertIn(tp_redact.REDACTED, stream.getvalue())

    def test_score_exception_is_redacted_in_log_and_report(self):
        error = RuntimeError('scoring failed with '
                             + fixture_shaped('github'))
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {'PR_NUMBER': '42', 'PR_HEAD_SHA': SHA,
                         'GITHUB_STEP_SUMMARY': ''},
        ), patch.object(tp_review, 'get_pull_request', side_effect=error):
            stream, redirect = self.capture_stderr()
            with redirect, working_directory(directory):
                result = tp_review.score_main()
            report = json.loads(
                (Path(directory) / 'test-plan-score' / 'report.json').read_text())
        self.assertEqual(result, 1)
        self.assertNotIn(fixture_shaped('github'), stream.getvalue())
        self.assertIn(tp_redact.REDACTED, stream.getvalue())
        self.assertNotIn(fixture_shaped('github'), report['error'])
        self.assertIn(tp_redact.REDACTED, report['error'])

    def test_comment_failure_is_redacted_before_logging(self):
        rows = [{'path': 'enhancements/one/testplan.md', 'verdict': 'Ready',
                 'total': 10, 'feedback': 'complete'}]
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {'PR_NUMBER': '42', 'PR_HEAD_SHA': SHA,
                         'GITHUB_STEP_SUMMARY': '', 'TP_SHADOW': 'false',
                         'TP_OSAC_PATH': directory,
                         'TP_REVIEW_SKILLS_PATH': directory},
        ), patch.object(
            tp_review, 'get_pull_request', return_value=PR,
        ), patch.object(
            tp_review, 'get_changed_files', return_value=[],
        ), patch.object(
            tp_review, 'score_pr', return_value=rows,
        ), patch.object(
            tp_review, 'git_sha', return_value=SHA,
        ), patch.object(
            TestPlanHooks, '_upsert_score_comment',
            side_effect=RuntimeError('comment failed with '
                                     + fixture_shaped('github')),
        ):
            stream, redirect = self.capture_stderr()
            with redirect, working_directory(directory):
                result = tp_review.score_main()
        self.assertEqual(result, 0)
        self.assertNotIn(fixture_shaped('github'), stream.getvalue())
        self.assertIn(tp_redact.REDACTED, stream.getvalue())

    def test_gh_error_text_is_redacted_before_logging(self):
        failure = Mock(returncode=1,
                       stderr='request failed with '
                              + fixture_shaped('github'))
        hooks = TestPlanHooks(repo='test/repo', skills_path='unused')
        with patch.object(tp_hooks.subprocess, 'run', return_value=failure):
            stream, redirect = self.capture_stderr()
            with redirect:
                hooks._gh(['pr', 'view', '42'], check=False)
            with self.assertRaises(RuntimeError) as raised:
                hooks._gh(['pr', 'view', '42'], check=True)
        self.assertNotIn(fixture_shaped('github'), stream.getvalue())
        self.assertIn(tp_redact.REDACTED, stream.getvalue())
        self.assertNotIn(fixture_shaped('github'), str(raised.exception))
        self.assertIn(tp_redact.REDACTED, str(raised.exception))

    def test_truncation_happens_after_redaction(self):
        # A token straddling the truncation boundary must not survive as
        # a partial fragment: redact the complete stderr first.
        token_length = len(fixture_shaped('github', 'e'))
        fragments = [fixture_shaped('github', 'e')[i:i + 8]
                     for i in range(token_length - 7)]
        # The token is preceded by a space so the word boundary the
        # token patterns anchor on exists; glued to word characters a
        # token is deliberately not matched (that is what keeps paths
        # and identifiers readable).
        failure = Mock(returncode=1, stderr='a' * 291 + ' '
                                  + fixture_shaped('github', 'e'))
        with patch.object(tp_review.subprocess, 'run', return_value=failure):
            with self.assertRaises(RuntimeError) as raised:
                tp_review.gh(['pr', 'view', '42'])
        message = str(raised.exception)
        self.assertIn('a' * 291, message)
        for fragment in fragments:
            self.assertNotIn(fragment, message)

        failure = Mock(returncode=1, stderr='b' * 191 + ' '
                                  + fixture_shaped('github', 'e'))
        hooks = TestPlanHooks(repo='test/repo', skills_path='unused')
        with patch.object(tp_hooks.subprocess, 'run', return_value=failure):
            with self.assertRaises(RuntimeError) as raised:
                hooks._gh(['pr', 'view', '42'], check=True)
        message = str(raised.exception)
        self.assertIn('b' * 191, message)
        for fragment in fragments:
            self.assertNotIn(fragment, message)


if __name__ == '__main__':
    unittest.main()

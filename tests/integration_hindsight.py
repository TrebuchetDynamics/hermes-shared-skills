"""Hermes/Hindsight routing contract; captured SDK calls, no server/model traffic.

Run with Hermes' Python and source PYTHONPATH. Pass the installed Hindsight
plugin directory as the only argument. All configuration is temporary.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace


def main():
    plugin = Path(sys.argv[1]).resolve()
    assert (plugin / '__init__.py').is_file()
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='hindsight-isolation-test-') as directory:
        home = Path(directory)
        template = home / 'connection.json'
        template.write_text('{"mode":"local_external","api_url":"http://127.0.0.1:9"}')
        homes = [home, home / 'profiles/research']
        for profile in homes:
            (profile / 'plugins').mkdir(parents=True)
            (profile / 'plugins/hindsight').symlink_to(plugin)
            (profile / 'config.yaml').write_text('memory:\n  provider: ""\n')
        setup_env = dict(os.environ, HOME=str(home / 'no-legacy-home'))
        for key in ('HINDSIGHT_MODE', 'HINDSIGHT_BANK_ID', 'HINDSIGHT_API_URL'):
            setup_env.pop(key, None)
        subprocess.run([sys.executable, str(root / 'install-hindsight.py'),
                        '--hermes-home', str(home), '--profile', 'default',
                        '--profile', 'research', '--config', str(template), '--prepare'],
                       check=True, env=setup_env)
        os.environ['HERMES_HOME'] = str(home)
        from hermes_constants import set_hermes_home_override, reset_hermes_home_override
        from plugins.memory import load_memory_provider
        spec = importlib.util.spec_from_file_location('bundle_probe', root / 'bundle.py')
        bundle = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bundle)
        stores = {}
        banks = []

        class Client:
            def aretain_batch(self, *, bank_id, items, **kwargs):
                stores.setdefault(bank_id, []).extend(item['content'] for item in items)
                return SimpleNamespace()

            def arecall(self, *, bank_id, **kwargs):
                return SimpleNamespace(results=stores.get(bank_id, []))

        for index, profile in enumerate(homes):
            token = set_hermes_home_override(profile)
            try:
                (profile / 'config.yaml').write_text('memory:\n  provider: hindsight\n')
                provider = load_memory_provider('hindsight', register_skills=False)
                assert provider and provider.is_available()
                provider.initialize(session_id='same-session', agent_identity='same-identity')
                provider._run_hindsight_operation = lambda operation: operation(Client())
                provider._make_turn_retain_job([f'profile-{index}-fact'],
                    document_id='test', update_mode=None, label='test', track_ops=False)()
                recalled = provider._recall('test')
                assert len(recalled) == 1 and f'profile-{index}-fact' in recalled[0], recalled
                assert f'profile-{1-index}-fact' not in recalled[0], recalled
                expected = json.loads((profile / 'hindsight/config.json').read_text())['bank_id']
                banks.append(expected)
                assert provider._bank_id == expected
                report = bundle.inventory()
                assert 'hindsight' not in report['missing_plugins'], report['missing_plugins']
            finally:
                reset_hermes_home_override(token)
        assert len(set(banks)) == len(homes)
        assert set(stores) == set(banks)
        print('PASS: actual provider uses separate banks for captured retain/recall; category diagnostics agree')


if __name__ == '__main__':
    main()

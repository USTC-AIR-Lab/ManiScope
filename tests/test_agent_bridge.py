"""CPU-only bridge contract tests; no external inference or simulator calls."""
import io
import json
import pytest
from policy.GPT6 import budget
from policy.GPT6.local_bridge import Bridge, validate_move


def state():
    return {'left_endpose': [0, 0, 0.5, 1, 0, 0, 0], 'left_gripper': 0.4}


def action(**changes):
    return dict(arm='left', position=[0.1, 0, 0.5], quaternion_wxyz=[1, 0, 0, 0],
                gripper=1, phase='approach', **changes)


def test_motion_bounds_and_gripper_semantics():
    a = action()
    assert validate_move(a, state())['gripper'] == 0.4
    a['position'][0] = 0.13
    with pytest.raises(ValueError, match='envelope'):
        validate_move(a, state())
    a.update(phase='gripper', position=[0.1, 0, 0.5])
    result = validate_move(a, state())
    assert result['position'] == state()['left_endpose'][:3]
    assert result['gripper'] == 1
    for value in (float('nan'), True, '0.1'):
        a['position'][0] = value
        with pytest.raises(ValueError): validate_move(a, state())


def setup_budget(tmp_path, monkeypatch, cap=10):
    monkeypatch.setenv('AGENT_RUNTIME_DIR', str(tmp_path))
    (tmp_path/'budget_config.json').write_text(json.dumps({'models': {'test-model': {
        'context': 100, 'output': 20, 'input_rate': 0.01, 'output_rate': 0.02}}}))
    (tmp_path/'budget_ledger.json').write_text(json.dumps({
        'cap_usd': cap, 'prior_committed_upper_usd': 0, 'requests': {}}))


def test_budget_retains_unknown_cost_and_stops_at_cap(tmp_path, monkeypatch):
    setup_budget(tmp_path, monkeypatch, cap=2)
    ident = budget.reserve('test-model')
    budget.settle(ident, {})
    with pytest.raises(RuntimeError, match='cap'): budget.reserve('test-model')
    ledger = json.loads((tmp_path/'budget_ledger.json').read_text())
    assert ledger['requests'][ident]['held_usd'] == pytest.approx(1.4)
    assert (tmp_path/'BUDGET_STOP').exists()


def test_budget_accounts_gemini_thinking_and_rejects_excess(tmp_path, monkeypatch):
    setup_budget(tmp_path, monkeypatch)
    ident = budget.reserve('test-model')
    budget.settle(ident, {'usageMetadata': {'promptTokenCount': 10, 'candidatesTokenCount': 2, 'thoughtsTokenCount': 3}})
    ledger = json.loads((tmp_path/'budget_ledger.json').read_text())
    assert ledger['requests'][ident]['held_usd'] == pytest.approx(0.2)
    with pytest.raises(RuntimeError, match='bounds'):
        budget.settle(budget.reserve('test-model'), {'usage': {'input_tokens': 101, 'output_tokens': 0}})
    with pytest.raises(RuntimeError, match='stop marker'): budget.reserve('test-model')


def test_missing_ledger_fails_closed(tmp_path, monkeypatch):
    setup_budget(tmp_path, monkeypatch)
    (tmp_path/'budget_ledger.json').unlink()
    with pytest.raises(FileNotFoundError): budget.reserve('test-model')


def test_mock_inference_preserves_finish_and_filters_privileged_fields(tmp_path, monkeypatch):
    setup_budget(tmp_path, monkeypatch)
    bridge = Bridge({'base_url':'https://example.invalid/v1', 'model':'test-model'}, 'dummy-secret', tmp_path/'logs', 1)
    result = {'output': [{'type':'function_call','name':'finish','arguments':'{"note":"done"}','call_id':'1'}],
              'usage': {'input_tokens':10,'output_tokens':2}}
    captured = []
    class Fake:
        def open(self, request, timeout):
            captured.append(json.loads(request.data))
            return io.BytesIO(json.dumps(result).encode())
    bridge.opener = Fake()
    obs = {'instruction':'Lift the red block','eef_state':state(),'images':{},'object_poses':{'secret':1},'expert_trajectory':[1]}
    response = bridge.infer(obs)
    assert response['type'] == 'finish' and 'success' not in response
    assert 'object_poses' not in json.dumps(captured) and 'expert_trajectory' not in json.dumps(captured)
    assert bridge.infer(obs)['type'] == 'finish' and len(captured) == 1
    assert 'dummy-secret' not in (tmp_path/'logs/decisions.jsonl').read_text()


@pytest.mark.parametrize('base', ['http://example.invalid', 'https://user:pass@example.invalid', 'https://example.invalid?key=x'])
def test_invalid_provider_origins_rejected(tmp_path, base):
    with pytest.raises(ValueError): Bridge({'base_url':base},'dummy',tmp_path,1)

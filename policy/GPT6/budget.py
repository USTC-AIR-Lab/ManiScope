"""Private, fail-closed request reservations; no account state or prices in source."""
import contextlib
import fcntl
import json
import math
import os
from pathlib import Path
import time
import uuid


def runtime_dir():
    return Path(os.environ.get('AGENT_RUNTIME_DIR', 'configs/private/agent'))


def nonnegative(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


@contextlib.contextmanager
def ledger():
    root = runtime_dir()
    root.mkdir(parents=True, exist_ok=True)
    with (root / 'budget.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = root / 'budget_ledger.json'
        data = json.loads(path.read_text())  # Missing state is fatal; never reset spending.
        if not nonnegative(data['cap_usd']) or not nonnegative(data['prior_committed_upper_usd']):
            raise ValueError('Invalid budget cap or prior spending')
        for item in data['requests'].values():
            if not nonnegative(item['held_usd']):
                raise ValueError('Invalid retained reservation')
        yield data
        temp = path.with_suffix('.tmp')
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)


def reserve(model):
    root = runtime_dir()
    if (root / 'BUDGET_STOP').exists():
        raise RuntimeError('Budget stop marker exists; review the private ledger')
    bounds = json.loads((root / 'budget_config.json').read_text())['models'][model]
    for name in ('context', 'output', 'input_rate', 'output_rate'):
        if not nonnegative(bounds[name]) or bounds[name] == 0:
            raise ValueError('Request bounds and conservative rates must be positive')
    amount = bounds['context'] * bounds['input_rate'] + bounds['output'] * bounds['output_rate']
    with ledger() as data:
        total = data['prior_committed_upper_usd'] + sum(x['held_usd'] for x in data['requests'].values())
        if total + amount > data['cap_usd']:
            (root / 'BUDGET_STOP').write_text('Insufficient remaining request reservation')
            raise RuntimeError('Cumulative USD cap: insufficient request reservation')
        ident = uuid.uuid4().hex
        data['requests'][ident] = dict(model=model, started_at=time.time(), held_usd=amount,
                                      status='reserved_or_unknown', bounds=bounds)
    return ident


def settle(ident, result):
    with ledger() as data:
        item = data['requests'][ident]
        bounds = item['bounds']
        if 'usageMetadata' in result:
            usage = result.get('usageMetadata') or {}
            inp, out = usage.get('promptTokenCount'), usage.get('candidatesTokenCount')
            thought = usage.get('thoughtsTokenCount', 0)
            out = out + thought if type(out) is int and type(thought) is int else None
        else:
            usage = result.get('usage') or {}
            inp, out = usage.get('input_tokens'), usage.get('output_tokens')
        if type(inp) is not int or type(out) is not int:
            return  # Unknown usage retains the full reservation.
        if not 0 <= inp <= bounds['context'] or not 0 <= out <= bounds['output']:
            (runtime_dir() / 'BUDGET_STOP').write_text('Usage exceeded configured reservation bounds')
            raise RuntimeError('Usage exceeds configured reservation bounds')
        item.update(status='usage_accounted', held_usd=inp*bounds['input_rate']+out*bounds['output_rate'],
                    usage=usage, completed_at=time.time())

"""Load simulator dependencies only when the evaluator requests adapter entry points."""
__all__ = ['get_model', 'eval', 'reset_model']


def __getattr__(name):
    if name in __all__:
        from . import deploy_policy
        return getattr(deploy_policy, name)
    raise AttributeError(f'{__name__} has no attribute {name!r}')

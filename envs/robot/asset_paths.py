"""Resolve relocated embodiment paths in memory without editing shared assets."""
from copy import deepcopy
from pathlib import Path


def resolve_robot_config(config, config_file):
    result = deepcopy(config)
    directory = Path(config_file).resolve().parent
    kinematics = result["robot_cfg"]["kinematics"]
    for key in ("urdf_path", "collision_spheres", "asset_root_path"):
        value = kinematics.get(key)
        if not isinstance(value, str) or not value:
            continue
        path = Path(value)
        if path.is_absolute():
            marker = "/" + directory.name + "/"
            if marker not in value:
                if path.exists(): continue
                raise FileNotFoundError(f"{key}: cannot resolve external asset path {value}")
            relative = value.rsplit(marker, 1)[1]
        else:
            relative = value
        target = (directory / relative).resolve()
        # References inside the embodiment remain inside that directory.
        if not target.is_relative_to(directory):
            raise ValueError(f"{key}: path leaves embodiment directory")
        if not target.exists():
            raise FileNotFoundError(f"{key}: missing local asset {target}")
        kinematics[key] = str(target)
    return result

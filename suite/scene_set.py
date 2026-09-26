# -*- coding: utf-8 -*-
"""Shared scene entry point: handwritten table plus generated mixtures. Import this module rather than table directly so downstream tools include derived scenes."""
import gen_scenes          # Importing gen_scenes extends SCENES with generated mixtures.
from table import SCENES   # noqa: E402  SCENES now includes generated mixtures.

__all__ = ["SCENES"]

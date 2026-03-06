"""
Core functionality module for REST-at.

Includes:
---------
Classes for abstracting pretrained models and conversation sessions.\n
A function for formatting prompt strings.\n
A class for abstracting REST specifications.\n
A class for calculating and formatting statistical data.\n
A class for reading and parsing GPU metrics.

Copyright:
----------
(c) 2024 Anonymous software testing consultancy company

License:
--------
MIT (see LICENSE for more information)
"""

__all__ = [
    "model",
    "prompt",
    "rest",
    "stats",
    "gpu_profiler"
]


from . import model
from . import prompt
from . import rest
from . import stats
from . import gpu_profiler

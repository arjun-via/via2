#!/usr/bin/env python3
"""Debug script to analyze why patches fail."""

import json
import sys
import asyncio
sys.path.insert(0, '.')

from config import get_config, ModelMode
from parallel_generator import ParallelGenerator
from api_client import EnsembleAPIClient
from docker_executor import DockerExecutor

# Test issue from astropy__astropy-12907
issue = """
Modeling's `separability_matrix` does not compute separability correctly for nested CompoundModels

Consider the following model:

```python
from astropy.modeling import models as m
from astropy.modeling.separable import separability_matrix

cm = m.Linear1D(10) & m.Linear1D(5)
```

It's separability matrix as you might expect is a diagonal:

```python
>>> separability_matrix(cm)
array([[ True, False],
       [False,  True]])
```

If I make the model more complex:

```python
>>> separability_matrix(m.Pix2Sky_TAN() & cm)
array([[ True,  True, False, False],
       [ True,  True, False, False],
       [False, False,  True, False],
       [False, False, False,  True]])
```

However, this doesn't work properly for nested compound models:

```python
>>> separability_matrix(m.Pix2Sky_TAN() & m.Linear1D(10) & m.Linear1D(5))
array([[ True,  True, False, False],
       [ True,  True, False, False],
       [False, False,  True, False],
       [False, False, False,  True]])
```

This should return a full True matrix since all models are connected.
"""

code = """
### TEST FILE (must pass): astropy/modeling/tests/test_separable.py

```python
def test_nested_compound_separability():
    from astropy.modeling import models as m
    from astropy.modeling.separable import separability_matrix

    cm1 = m.Linear1D(10) & m.Linear1D(5)
    cm2 = m.Pix2Sky_TAN() & cm1

    # This should work correctly
    mat = separability_matrix(cm2)
    assert mat.shape == (4, 4)
```

### Source File: astropy/modeling/separable.py

```python
def separability_matrix(transform):
    if transform.n_inputs == 1 and transform.n_outputs > 1:
        return np.ones((transform.n_outputs, transform.n_inputs),
                       dtype=np.bool_)
    separable_matrix = _separable(transform)
    separable_matrix = np.where(separable_matrix != 0, True, False)
    return separable_matrix


def _separable(transform):
    if isinstance(transform, CompoundModel):
        sepleft = _separable(transform.left)
        sepright = _separable(transform.right)
        return _operators[transform.op](sepleft, sepright)
    elif isinstance(transform, Model):
        return _coord_matrix(transform, 'left', transform.n_outputs)
```
"""


async def main():
    print("=" * 60)
    print("PATCH GENERATION DEBUG")
    print("=" * 60)

    config = get_config(ModelMode.PRODUCTION)
    config.num_parallel_instances = 3  # Small number for testing

    generator = ParallelGenerator(ModelMode.PRODUCTION)

    print(f"\nGenerating {config.num_parallel_instances} patches...")

    patches = await generator.generate(
        issue=issue,
        code=code,
        test_code="",
        num_instances=config.num_parallel_instances
    )

    print(f"\nGenerated {len(patches)} patches")

    for i, p in enumerate(patches):
        print(f"\n{'='*60}")
        print(f"PATCH {i+1}")
        print(f"{'='*60}")
        print(f"Strategy: {p.strategy}")
        print(f"Code length: {len(p.code) if p.code else 0}")

        if p.code:
            # Check if it's in SEARCH/REPLACE format
            if "<<<<<<< SEARCH" in p.code:
                print("Format: SEARCH/REPLACE")
            elif "---" in p.code and "+++" in p.code:
                print("Format: Unified diff")
            else:
                print("Format: Unknown/raw code")

            print(f"\nPatch content:")
            print("-" * 40)
            print(p.code[:1500])
            if len(p.code) > 1500:
                print(f"... [{len(p.code) - 1500} more chars]")
        else:
            print("WARNING: Empty patch!")


if __name__ == "__main__":
    asyncio.run(main())

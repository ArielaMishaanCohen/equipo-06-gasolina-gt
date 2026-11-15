"""La fuente "databricks" (SQL warehouse) devuelve todo como texto; _normalizar lo tipa."""

import pandas as pd
import pytest

from gasolina.oro import _normalizar


@pytest.mark.parametrize("dtype", [object, "string"])
def test_probabilidad_texto_a_float(dtype):
    # pandas 3 usa el dtype "str"/"string" para texto en vez de object.
    df = pd.DataFrame({
        "semana_objetivo": ["2026-11-10"],
        "combustible": ["super"],
        "probabilidad": ["0.8139"],
        "version_modelo": ["0.2.0"],
    }).astype(dtype)
    n = _normalizar(df)
    assert n["probabilidad"].dtype == float
    assert n["probabilidad"].iloc[0] == pytest.approx(0.8139)
    assert n["version_modelo"].iloc[0] == "0.2.0"
    assert n["combustible"].iloc[0] == "super"

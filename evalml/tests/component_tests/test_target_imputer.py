import numpy as np
import pandas as pd
import pytest
import woodwork as ww
from pandas.testing import assert_series_equal
from woodwork.logical_types import (
    Boolean,
    Categorical,
    Double,
    Integer,
    NaturalLanguage
)

from evalml.pipelines.components import TargetImputer


def test_target_imputer_median():
    y = pd.Series([np.nan, 1, 10, 10, 6])
    imputer = TargetImputer(impute_strategy='median')
    y_expected = pd.Series([8, 1, 10, 10, 6])
    y_t = imputer.fit_transform(None, y)
    assert_series_equal(y_expected, y_t.to_series(), check_dtype=False)


def test_target_imputer_mean():
    y = pd.Series([np.nan, 2, 0])
    imputer = TargetImputer(impute_strategy='mean')
    y_expected = pd.Series([1, 2, 0])
    y_t = imputer.fit_transform(None, y)
    assert_series_equal(y_expected, y_t.to_series(), check_dtype=False)


@pytest.mark.parametrize("fill_value, y, y_expected", [(None, pd.Series([np.nan, 0, 5]), pd.Series([0, 0, 5])),
                                                       (None, pd.Series([np.nan, "a", "b"]), pd.Series(["missing_value", "a", "b"]).astype("category")),
                                                       (3, pd.Series([np.nan, 0, 5]), pd.Series([3, 0, 5])),
                                                       (3, pd.Series([np.nan, "a", "b"]), pd.Series([3, "a", "b"]).astype("category"))])
def test_target_imputer_constant(fill_value, y, y_expected):
    imputer = TargetImputer(impute_strategy='constant', fill_value=fill_value)
    y_t = imputer.fit_transform(None, y)
    assert_series_equal(y_expected, y_t.to_series(), check_dtype=False)


def test_target_imputer_most_frequent():
    y = pd.Series([np.nan, "a", "b"])
    imputer = TargetImputer(impute_strategy='most_frequent')
    y_expected = pd.Series(["a", "a", "b"]).astype("category")
    y_t = imputer.fit_transform(None, y)
    assert_series_equal(y_expected, y_t.to_series(), check_dtype=False)

    y = pd.Series([np.nan, 1, 1, 2])
    imputer = TargetImputer(impute_strategy='most_frequent')
    y_expected = pd.Series([1, 1, 1, 2])
    y_t = imputer.fit_transform(None, y)
    assert_series_equal(y_expected, y_t.to_series(), check_dtype=False)


def test_target_imputer_col_with_non_numeric_with_numeric_strategy():
    y = pd.Series([np.nan, "a", "b"])
    imputer = TargetImputer(impute_strategy='mean')
    with pytest.raises(ValueError, match="Cannot use mean strategy with non-numeric data"):
        imputer.fit_transform(None, y)
    with pytest.raises(ValueError, match="Cannot use mean strategy with non-numeric data"):
        imputer.fit(None, y)
    imputer = TargetImputer(impute_strategy='median')
    with pytest.raises(ValueError, match="Cannot use median strategy with non-numeric data"):
        imputer.fit_transform(None, y)
    with pytest.raises(ValueError, match="Cannot use median strategy with non-numeric data"):
        imputer.fit(None, y)


@pytest.mark.parametrize("data_type", ['pd', 'ww'])
def test_target_imputer_all_bool_return_original(data_type, make_data_type):
    y = pd.Series([True, True, False, True, True], dtype=bool)
    y = make_data_type(data_type, y)
    y_expected = pd.Series([True, True, False, True, True], dtype='boolean')
    imputer = TargetImputer()
    imputer.fit(None, y)
    y_t = imputer.transform(None, y)
    assert_series_equal(y_expected, y_t.to_series())


@pytest.mark.parametrize("data_type", ['pd', 'ww'])
def test_target_imputer_boolean_dtype(data_type, make_data_type):
    y = pd.Series([True, np.nan, False, np.nan, True], dtype='boolean')
    y_expected = pd.Series([True, True, False, True, True], dtype='boolean')
    y = make_data_type(data_type, y)
    imputer = TargetImputer()
    imputer.fit(None, y)
    y_t = imputer.transform(None, y)
    assert_series_equal(y_expected, y_t.to_series())


def test_target_imputer_fit_transform_all_nan_empty():
    y = pd.Series([np.nan, np.nan])
    imputer = TargetImputer()
    y_expected = pd.Series([])
    y_t = imputer.fit_transform(None, y)
    assert_series_equal(y_expected, y_t.to_series())


def test_target_imputer_numpy_input():
    y = np.array([np.nan, 0, 2])
    imputer = TargetImputer(impute_strategy='mean')
    y_expected = np.array([1, 0, 2])
    assert np.allclose(y_expected, imputer.fit_transform(None, y).to_series())
    np.testing.assert_almost_equal(y, np.array([np.nan, 0, 2]))


def test_target_imputer_does_not_reset_index():
    y = pd.Series(np.arange(10))
    y[5] = np.nan
    assert y.index.tolist() == list(range(10))

    y.drop(0, inplace=True)
    pd.testing.assert_series_equal(pd.Series([1.0, 2, 3, 4, np.nan, 6, 7, 8, 9], dtype=float, index=list(range(1, 10))), y)

    imputer = TargetImputer(impute_strategy="mean")
    imputer.fit(None, y=y)
    transformed = imputer.transform(None, y)
    pd.testing.assert_series_equal(pd.Series([1.0, 2, 3, 4, 5, 6, 7, 8, 9], dtype=float, index=list(range(1, 10))), transformed.to_series())


@pytest.mark.parametrize("y, y_expected", [(pd.Series([1, 0, 5, None]), pd.Series([1, 0, 5, 2])),
                                           (pd.Series([0.1, 0.0, 0.5, None]), pd.Series([0.1, 0.0, 0.5, 0.2])),
                                           (pd.Series([None, None, None, None]), pd.Series([]))])
def test_target_imputer_with_none(y, y_expected):
    imputer = TargetImputer(impute_strategy="mean")
    y_t = imputer.fit_transform(None, y)
    assert_series_equal(y_expected, y_t.to_series(), check_dtype=False)


@pytest.mark.parametrize("y, y_expected", [(pd.Series(["b", "a", "a", None], dtype='category'), pd.Series(["b", "a", "a", "a"], dtype='category')),
                                           (pd.Series([True, None, False, True], dtype='boolean'), pd.Series([True, True, False, True], dtype='boolean')),
                                           (pd.Series(["b", "a", "a", None]), pd.Series(["b", "a", "a", "a"], dtype='category'))])
def test_target_imputer_with_none_non_numeric(y, y_expected):
    imputer = TargetImputer()
    y_t = imputer.fit_transform(None, y)
    assert_series_equal(y_expected, y_t.to_series(), check_dtype=False)


@pytest.mark.parametrize("y", [pd.Series([1, 2, 3], dtype="Int64"),
                               pd.Series([1., 2., 3.], dtype="float"),
                               pd.Series(['a', 'b', 'a'], dtype="category"),
                               pd.Series([True, False, True], dtype="boolean"),
                               pd.Series(['this will be a natural language column because length', 'yay', 'hay'], dtype="string")])
@pytest.mark.parametrize("has_nan", [True, False])
@pytest.mark.parametrize("impute_strategy", ["mean", "median", "most_frequent"])
def test_target_imputer_woodwork_custom_overrides_returned_by_components(y, has_nan, impute_strategy):
    y = pd.Series([1, 2, 1])
    if has_nan:
        y[len(y) - 1] = np.nan
    override_types = [Integer, Double, Categorical, NaturalLanguage, Boolean]
    for logical_type in override_types:
        try:
            y = ww.DataColumn(y, logical_type=logical_type)
        except TypeError:
            continue

        impute_strategy_to_use = impute_strategy
        if logical_type in [NaturalLanguage, Categorical]:
            impute_strategy_to_use = "most_frequent"

        imputer = TargetImputer(impute_strategy=impute_strategy_to_use)
        imputer.fit(None, y)
        transformed = imputer.transform(None, y)
        assert isinstance(transformed, ww.DataColumn)
        if impute_strategy_to_use == "most_frequent" or not has_nan:
            assert transformed.logical_type == logical_type
        else:
            assert transformed.logical_type == Double
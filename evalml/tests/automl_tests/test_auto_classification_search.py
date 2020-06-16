import time
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
from sklearn.model_selection import StratifiedKFold, TimeSeriesSplit

from evalml import (
    AutoBinaryClassificationSearch,
    AutoMulticlassClassificationSearch
)
from evalml.automl.pipeline_search_plots import SearchIterationPlot
from evalml.exceptions import ObjectiveNotFoundError
from evalml.model_family import ModelFamily
from evalml.objectives import (
    FraudCost,
    Precision,
    PrecisionMicro,
    Recall,
    get_objective,
    get_objectives
)
from evalml.pipelines import (
    LogisticRegressionBinaryPipeline,
    ModeBaselineBinaryPipeline,
    PipelineBase,
    get_pipelines
)
from evalml.problem_types import ProblemTypes


def test_init(X_y):
    X, y = X_y

    automl = AutoBinaryClassificationSearch(max_pipelines=1, n_jobs=4)
    automl.search(X, y)

    assert automl.n_jobs == 4
    assert isinstance(automl.rankings, pd.DataFrame)
    assert isinstance(automl.best_pipeline, PipelineBase)
    assert isinstance(automl.best_pipeline.feature_importances, pd.DataFrame)
    # test with datafarmes
    automl.search(pd.DataFrame(X), pd.Series(y))

    assert isinstance(automl.rankings, pd.DataFrame)
    assert isinstance(automl.full_rankings, pd.DataFrame)

    assert isinstance(automl.best_pipeline, PipelineBase)
    assert isinstance(automl.get_pipeline(0), PipelineBase)
    with pytest.raises(RuntimeError, match="Pipeline not found"):
        automl.get_pipeline(1000)

    automl.describe_pipeline(0)

    scores = automl.best_pipeline.score(X, y, ['precision'])
    assert not any(np.isnan(val) for val in scores.values())
    assert not automl.best_pipeline.feature_importances.isnull().all().all()


def test_get_pipeline_none(X_y):
    X, y = X_y

    automl = AutoBinaryClassificationSearch()
    with pytest.raises(RuntimeError, match="Pipeline not found"):
        automl.describe_pipeline(0)


def test_cv(X_y):
    X, y = X_y
    cv_folds = 5
    automl = AutoBinaryClassificationSearch(cv=StratifiedKFold(cv_folds), max_pipelines=1)
    automl.search(X, y)

    assert isinstance(automl.rankings, pd.DataFrame)
    assert len(automl.results['pipeline_results'][0]["cv_data"]) == cv_folds

    automl = AutoBinaryClassificationSearch(cv=TimeSeriesSplit(cv_folds), max_pipelines=1)
    automl.search(X, y)

    assert isinstance(automl.rankings, pd.DataFrame)
    assert len(automl.results['pipeline_results'][0]["cv_data"]) == cv_folds


def test_max_pipelines(X_y):
    X, y = X_y
    max_pipelines = 5
    automl = AutoBinaryClassificationSearch(max_pipelines=max_pipelines)
    automl.search(X, y)
    assert len(automl.full_rankings) == max_pipelines


def test_specify_objective(X_y):
    X, y = X_y
    automl = AutoBinaryClassificationSearch(objective=Precision(), max_pipelines=1)
    automl.search(X, y)
    assert isinstance(automl.objective, Precision)
    assert automl.best_pipeline.threshold is not None


def test_recall_error(X_y):
    X, y = X_y
    error_msg = 'Could not find the specified objective.'
    with pytest.raises(ObjectiveNotFoundError, match=error_msg):
        AutoBinaryClassificationSearch(objective='recall', max_pipelines=1)


def test_recall_object(X_y):
    X, y = X_y
    automl = AutoBinaryClassificationSearch(objective=Recall(), max_pipelines=1)
    automl.search(X, y)


def test_binary_auto(X_y):
    X, y = X_y
    automl = AutoBinaryClassificationSearch(objective="log_loss_binary", max_pipelines=5)
    automl.search(X, y)
    y_pred = automl.best_pipeline.predict(X)

    assert len(np.unique(y_pred)) == 2


def test_multi_error(X_y_multi):
    X, y = X_y_multi
    error_automls = [AutoBinaryClassificationSearch(objective='precision'), AutoMulticlassClassificationSearch(objective='precision_micro', additional_objectives=['precision'])]
    error_msg = 'not compatible with a multiclass problem.'
    for automl in error_automls:
        with pytest.raises(ValueError, match=error_msg):
            automl.search(X, y)


def test_multi_auto(X_y_multi):
    X, y = X_y_multi
    automl = AutoMulticlassClassificationSearch(objective="f1_micro", max_pipelines=5)
    automl.search(X, y)
    y_pred = automl.best_pipeline.predict(X)
    assert len(np.unique(y_pred)) == 3

    objective = PrecisionMicro()
    automl = AutoMulticlassClassificationSearch(objective=objective, max_pipelines=5)
    automl.search(X, y)
    y_pred = automl.best_pipeline.predict(X)
    assert len(np.unique(y_pred)) == 3

    expected_additional_objectives = get_objectives('multiclass')
    objective_in_additional_objectives = next((obj for obj in expected_additional_objectives if obj.name == objective.name), None)
    expected_additional_objectives.remove(objective_in_additional_objectives)

    for expected, additional in zip(expected_additional_objectives, automl.additional_objectives):
        assert type(additional) is type(expected)


def test_multi_objective(X_y_multi):
    automl = AutoBinaryClassificationSearch(objective="log_loss_binary")
    assert automl.problem_type == ProblemTypes.BINARY

    automl = AutoMulticlassClassificationSearch(objective="log_loss_multi")
    assert automl.problem_type == ProblemTypes.MULTICLASS

    automl = AutoMulticlassClassificationSearch(objective='auc_micro')
    assert automl.problem_type == ProblemTypes.MULTICLASS

    automl = AutoBinaryClassificationSearch(objective='auc')
    assert automl.problem_type == ProblemTypes.BINARY

    automl = AutoMulticlassClassificationSearch()
    assert automl.problem_type == ProblemTypes.MULTICLASS

    automl = AutoBinaryClassificationSearch()
    assert automl.problem_type == ProblemTypes.BINARY


def test_categorical_classification(X_y_categorical_classification):
    X, y = X_y_categorical_classification
    automl = AutoBinaryClassificationSearch(objective="precision", max_pipelines=5)
    automl.search(X, y)
    assert not automl.rankings['score'].isnull().all()
    assert not automl.get_pipeline(0).feature_importances.isnull().all().all()


def test_random_state(X_y):
    X, y = X_y

    automl = AutoBinaryClassificationSearch(objective=Precision(), max_pipelines=5, random_state=0)
    automl.search(X, y)

    automl_1 = AutoBinaryClassificationSearch(objective=Precision(), max_pipelines=5, random_state=0)
    automl_1.search(X, y)
    assert automl.rankings.equals(automl_1.rankings)


def test_callback(X_y):
    X, y = X_y

    counts = {
        "start_iteration_callback": 0,
        "add_result_callback": 0,
    }

    def start_iteration_callback(pipeline_class, parameters, counts=counts):
        counts["start_iteration_callback"] += 1

    def add_result_callback(results, trained_pipeline, counts=counts):
        counts["add_result_callback"] += 1

    max_pipelines = 3
    automl = AutoBinaryClassificationSearch(objective=Precision(), max_pipelines=max_pipelines,
                                            start_iteration_callback=start_iteration_callback,
                                            add_result_callback=add_result_callback)
    automl.search(X, y)

    assert counts["start_iteration_callback"] == max_pipelines
    assert counts["add_result_callback"] == max_pipelines


def test_additional_objectives(X_y):
    X, y = X_y

    objective = FraudCost(retry_percentage=.5,
                          interchange_fee=.02,
                          fraud_payout_percentage=.75,
                          amount_col=10)
    automl = AutoBinaryClassificationSearch(objective='F1', max_pipelines=2, additional_objectives=[objective])
    automl.search(X, y)

    results = automl.describe_pipeline(0, return_dict=True)
    assert 'Fraud Cost' in list(results["cv_data"][0]["all_objective_scores"].keys())


@patch('evalml.objectives.BinaryClassificationObjective.optimize_threshold')
@patch('evalml.pipelines.BinaryClassificationPipeline.predict_proba')
@patch('evalml.pipelines.BinaryClassificationPipeline.score')
@patch('evalml.pipelines.PipelineBase.fit')
def test_optimizable_threshold_enabled(mock_fit, mock_score, mock_predict_proba, mock_optimize_threshold, X_y, caplog):
    mock_optimize_threshold.return_value = 0.8
    X, y = X_y
    automl = AutoBinaryClassificationSearch(objective='precision', max_pipelines=1, optimize_thresholds=True)
    mock_score.return_value = {automl.objective.name: 1.0}
    automl.search(X, y)
    mock_fit.assert_called()
    mock_score.assert_called()
    mock_predict_proba.assert_called()
    mock_optimize_threshold.assert_called()
    assert automl.best_pipeline.threshold == 0.8

    automl.describe_pipeline(0)
    out = caplog.text
    assert "Objective to optimize binary classification pipeline thresholds for" in out


@patch('evalml.objectives.BinaryClassificationObjective.optimize_threshold')
@patch('evalml.pipelines.BinaryClassificationPipeline.predict_proba')
@patch('evalml.pipelines.BinaryClassificationPipeline.score')
@patch('evalml.pipelines.PipelineBase.fit')
def test_optimizable_threshold_disabled(mock_fit, mock_score, mock_predict_proba, mock_optimize_threshold, X_y):
    mock_optimize_threshold.return_value = 0.8
    X, y = X_y
    automl = AutoBinaryClassificationSearch(objective='precision', max_pipelines=1, optimize_thresholds=False)
    mock_score.return_value = {automl.objective.name: 1.0}
    automl.search(X, y)
    mock_fit.assert_called()
    mock_score.assert_called()
    assert not mock_predict_proba.called
    assert not mock_optimize_threshold.called
    assert automl.best_pipeline.threshold == 0.5


@patch('evalml.pipelines.BinaryClassificationPipeline.score')
@patch('evalml.pipelines.PipelineBase.fit')
def test_non_optimizable_threshold(mock_fit, mock_score, X_y):
    mock_score.return_value = {"AUC": 1.0}
    X, y = X_y
    automl = AutoBinaryClassificationSearch(objective='AUC', max_pipelines=1)
    automl.search(X, y)
    mock_fit.assert_called()
    mock_score.assert_called()
    assert automl.best_pipeline.threshold == 0.5


def test_describe_pipeline_objective_ordered(X_y, caplog):
    X, y = X_y
    automl = AutoBinaryClassificationSearch(objective='AUC', max_pipelines=2)
    automl.search(X, y)

    automl.describe_pipeline(0)
    out = caplog.text
    out_stripped = " ".join(out.split())

    objectives = [get_objective(obj) for obj in automl.additional_objectives]
    objectives_names = [obj.name for obj in objectives]
    expected_objective_order = " ".join(objectives_names)

    assert expected_objective_order in out_stripped


def test_max_time_units():
    str_max_time = AutoBinaryClassificationSearch(objective='F1', max_time='60 seconds')
    assert str_max_time.max_time == 60

    hour_max_time = AutoBinaryClassificationSearch(objective='F1', max_time='1 hour')
    assert hour_max_time.max_time == 3600

    min_max_time = AutoBinaryClassificationSearch(objective='F1', max_time='30 mins')
    assert min_max_time.max_time == 1800

    min_max_time = AutoBinaryClassificationSearch(objective='F1', max_time='30 s')
    assert min_max_time.max_time == 30

    with pytest.raises(AssertionError, match="Invalid unit. Units must be hours, mins, or seconds. Received 'year'"):
        AutoBinaryClassificationSearch(objective='F1', max_time='30 years')

    with pytest.raises(TypeError, match="max_time must be a float, int, or string. Received a <class 'tuple'>."):
        AutoBinaryClassificationSearch(objective='F1', max_time=(30, 'minutes'))


def test_early_stopping(caplog):
    with pytest.raises(ValueError, match='patience value must be a positive integer.'):
        automl = AutoBinaryClassificationSearch(objective='AUC', max_pipelines=5, allowed_model_families=['linear_model'], patience=-1, random_state=0)

    with pytest.raises(ValueError, match='tolerance value must be'):
        automl = AutoBinaryClassificationSearch(objective='AUC', max_pipelines=5, allowed_model_families=['linear_model'], patience=1, tolerance=1.5, random_state=0)

    automl = AutoBinaryClassificationSearch(objective='AUC', max_pipelines=5, allowed_model_families=['linear_model'], patience=2, tolerance=0.05, random_state=0)
    mock_results = {
        'search_order': [0, 1, 2],
        'pipeline_results': {}
    }

    scores = [0.95, 0.84, 0.96]  # 0.96 is only 1% greater so it doesn't trigger patience due to tolerance
    for id in mock_results['search_order']:
        mock_results['pipeline_results'][id] = {}
        mock_results['pipeline_results'][id]['score'] = scores[id]
        mock_results['pipeline_results'][id]['pipeline_class'] = LogisticRegressionBinaryPipeline

    automl.results = mock_results
    automl._check_stopping_condition(time.time())
    out = caplog.text
    assert "2 iterations without improvement. Stopping search early." in out


def test_plot_disabled_missing_dependency(X_y, has_minimal_dependencies):
    X, y = X_y

    automl = AutoBinaryClassificationSearch(max_pipelines=3)
    if has_minimal_dependencies:
        with pytest.raises(AttributeError):
            automl.plot.search_iteration_plot
    else:
        automl.plot.search_iteration_plot


def test_plot_iterations_max_pipelines(X_y):
    go = pytest.importorskip('plotly.graph_objects', reason='Skipping plotting test because plotly not installed')
    X, y = X_y

    automl = AutoBinaryClassificationSearch(objective="f1", max_pipelines=3)
    automl.search(X, y)
    plot = automl.plot.search_iteration_plot()
    plot_data = plot.data[0]
    x = pd.Series(plot_data['x'])
    y = pd.Series(plot_data['y'])

    assert isinstance(plot, go.Figure)
    assert x.is_monotonic_increasing
    assert y.is_monotonic_increasing
    assert len(x) == 3
    assert len(y) == 3


def test_plot_iterations_max_time(X_y):
    go = pytest.importorskip('plotly.graph_objects', reason='Skipping plotting test because plotly not installed')
    X, y = X_y

    automl = AutoBinaryClassificationSearch(objective="f1", max_time=10)
    automl.search(X, y, show_iteration_plot=False)
    plot = automl.plot.search_iteration_plot()
    plot_data = plot.data[0]
    x = pd.Series(plot_data['x'])
    y = pd.Series(plot_data['y'])

    assert isinstance(plot, go.Figure)
    assert x.is_monotonic_increasing
    assert y.is_monotonic_increasing
    assert len(x) > 0
    assert len(y) > 0


@patch('IPython.display.display')
def test_plot_iterations_ipython_mock(mock_ipython_display, X_y):
    pytest.importorskip('IPython.display', reason='Skipping plotting test because ipywidgets not installed')
    pytest.importorskip('plotly.graph_objects', reason='Skipping plotting test because plotly not installed')
    X, y = X_y

    automl = AutoBinaryClassificationSearch(objective="f1", max_pipelines=3)
    automl.search(X, y)
    plot = automl.plot.search_iteration_plot(interactive_plot=True)
    assert isinstance(plot, SearchIterationPlot)
    assert isinstance(plot.data, AutoBinaryClassificationSearch)
    mock_ipython_display.assert_called_with(plot.best_score_by_iter_fig)


@patch('IPython.display.display')
def test_plot_iterations_ipython_mock_import_failure(mock_ipython_display, X_y):
    pytest.importorskip('IPython.display', reason='Skipping plotting test because ipywidgets not installed')
    go = pytest.importorskip('plotly.graph_objects', reason='Skipping plotting test because plotly not installed')
    X, y = X_y

    automl = AutoBinaryClassificationSearch(objective="f1", max_pipelines=3)
    automl.search(X, y)

    mock_ipython_display.side_effect = ImportError('KABOOOOOOMMMM')
    plot = automl.plot.search_iteration_plot(interactive_plot=True)
    mock_ipython_display.assert_called_once()

    assert isinstance(plot, go.Figure)
    assert isinstance(plot.data, tuple)
    plot_data = plot.data[0]
    x = pd.Series(plot_data['x'])
    y = pd.Series(plot_data['y'])
    assert x.is_monotonic_increasing
    assert y.is_monotonic_increasing
    assert len(x) == 3
    assert len(y) == 3


def test_max_time(X_y):
    X, y = X_y
    clf = AutoBinaryClassificationSearch(max_time=1e-16)
    clf.search(X, y)
    # search will always run at least one pipeline
    assert len(clf.results['pipeline_results']) == 1


def test_automl_allowed_pipelines_init(dummy_binary_pipeline_class):
    automl = AutoBinaryClassificationSearch(max_pipelines=2, allowed_pipelines=None, allowed_model_families=None)
    expected_pipelines = get_pipelines(problem_type=ProblemTypes.BINARY)
    assert automl.allowed_pipelines == expected_pipelines
    assert set(automl.allowed_model_families) == set([p.model_family for p in expected_pipelines])

    automl = AutoBinaryClassificationSearch(max_pipelines=2, allowed_pipelines=[dummy_binary_pipeline_class], allowed_model_families=None)
    expected_pipelines = [dummy_binary_pipeline_class]
    assert automl.allowed_pipelines == expected_pipelines
    assert set(automl.allowed_model_families) == set([ModelFamily.NONE])

    automl = AutoBinaryClassificationSearch(max_pipelines=2, allowed_pipelines=None, allowed_model_families=[ModelFamily.RANDOM_FOREST])
    expected_pipelines = get_pipelines(problem_type=ProblemTypes.BINARY, model_families=[ModelFamily.RANDOM_FOREST])
    assert automl.allowed_pipelines == expected_pipelines
    assert set(automl.allowed_model_families) == set([ModelFamily.RANDOM_FOREST])

    automl = AutoBinaryClassificationSearch(max_pipelines=2, allowed_pipelines=None, allowed_model_families=['random_forest'])
    expected_pipelines = get_pipelines(problem_type=ProblemTypes.BINARY, model_families=[ModelFamily.RANDOM_FOREST])
    assert automl.allowed_pipelines == expected_pipelines
    assert set(automl.allowed_model_families) == set([ModelFamily.RANDOM_FOREST])

    automl = AutoBinaryClassificationSearch(max_pipelines=2, allowed_pipelines=[dummy_binary_pipeline_class], allowed_model_families=[ModelFamily.RANDOM_FOREST])
    expected_pipelines = [dummy_binary_pipeline_class]
    assert automl.allowed_pipelines == expected_pipelines
    assert set(automl.allowed_model_families) == set([ModelFamily.RANDOM_FOREST])


@patch('evalml.pipelines.BinaryClassificationPipeline.score')
@patch('evalml.pipelines.BinaryClassificationPipeline.fit')
def test_automl_allowed_pipelines_search(mock_fit, mock_score, dummy_binary_pipeline_class, X_y):
    X, y = X_y
    mock_score.return_value = {'Log Loss Binary': 1.0}

    allowed_pipelines = [dummy_binary_pipeline_class]
    start_iteration_callback = MagicMock()
    automl = AutoBinaryClassificationSearch(max_pipelines=2, start_iteration_callback=start_iteration_callback,
                                            allowed_pipelines=allowed_pipelines)
    automl.search(X, y)

    assert start_iteration_callback.call_count == 2
    assert start_iteration_callback.call_args_list[0][0][0] == ModeBaselineBinaryPipeline
    assert start_iteration_callback.call_args_list[1][0][0] == dummy_binary_pipeline_class

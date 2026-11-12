"""User-visible workflows; no server, external data, or provider requests."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest
import sales_ai.ai as ai
from tests.fake_superstore import make_fake_superstore

APP = str(Path(__file__).resolve().parents[1] / "app.py")


@pytest.fixture
def app(monkeypatch):
    for provider in ai.PROVIDERS.values():
        monkeypatch.delenv(provider["env"], raising=False)
    def forbidden(*args, **kwargs):
        raise AssertionError("Offline demo must not contact a provider")
    monkeypatch.setattr(ai, "verify_api_key", forbidden)
    monkeypatch.setattr(ai, "_call_llm", forbidden)
    return AppTest.from_file(APP, default_timeout=40).run()


def test_local_demo_is_useful_and_tabs_are_lazy(app, monkeypatch):
    assert not app.exception
    assert len(app.metric) == 5
    assert any("Decisions to review" in m.value for m in app.markdown)
    assert not app.slider  # Forecast is not evaluated on the overview.
    app.session_state["dashboard_tabs"] = "AI Insights"
    app.run()
    assert not app.exception
    assert any("Headline" in m.value for m in app.markdown)
    assert not app.toggle[0].value


def test_every_local_tab_renders(app):
    for label in ["Products & Regions", "Forecast", "Anomalies", "AI Insights", "Data & EDA"]:
        app.session_state["dashboard_tabs"] = label
        app.run()
        assert not app.exception, label
    app.session_state["dashboard_tabs"] = "Forecast"
    app.run()
    assert any("Validation WAPE" in m.label for m in app.metric)
    assert len(app.dataframe) >= 2


def test_invalid_upload_does_not_show_generated_metrics(app):
    next(w for w in app.radio if w.label == "Data source").set_value("Upload my own CSV").run()
    assert not app.metric
    app.file_uploader[0].upload("broken.csv", b"date,revenue\n2026-01-01,100\n", "text/csv").run()
    assert not app.exception
    assert app.error
    assert not app.metric


def test_superstore_upload_and_audit(app):
    next(w for w in app.radio if w.label == "Data source").set_value("Upload my own CSV").run()
    contents = make_fake_superstore(100).to_csv(index=False).encode("utf-8")
    app.file_uploader[0].upload("superstore.csv", contents, "text/csv").run()
    assert not app.exception
    assert app.metric
    app.session_state["dashboard_tabs"] = "Data & EDA"
    app.run()
    assert not app.exception
    assert "Exact duplicate rows removed" in set(app.dataframe[0].value["Step"])


def test_empty_filters_are_safe(app):
    app.multiselect[0].set_value([]).run()
    assert not app.exception
    assert not app.metric
    assert app.warning


def test_missing_comparison_coverage_suppresses_growth(app):
    from datetime import date
    app.date_input[0].set_value((date(2023, 1, 1), date(2023, 1, 31))).run()
    assert not app.exception
    assert any("comparison period" in w.value for w in app.warning)
    assert app.metric[0].delta in (None, "")


def test_unfinished_date_range_is_safe(app):
    from datetime import date
    app.date_input[0].set_value((date(2026, 9, 1),)).run()
    assert not app.exception
    assert not app.metric
    assert any("both a start date" in i.value for i in app.info)


def test_custom_upload_has_own_cleaning_report(app):
    next(w for w in app.radio if w.label == "Data source").set_value("Upload my own CSV").run()
    csv = ("date,order_id,region,city,category,product,channel,customer_segment,units,discount,revenue,cost\n"
           "2026-01-01,A,,Delhi,Office,Desk,Website,Consumer,1,0,100,60\n")
    app.file_uploader[0].upload("sales.csv", csv.encode(), "text/csv").run()
    assert not app.exception
    app.session_state["dashboard_tabs"] = "Data & EDA"
    app.run()
    assert not app.exception
    assert "Missing dimension labels filled with Unknown" in set(app.dataframe[0].value["Step"])


def test_tab_settings_survive_navigation(app):
    app.session_state["dashboard_tabs"] = "Forecast"
    app.run()
    app.slider[0].set_value(12).run()
    app.session_state["dashboard_tabs"] = "Overview"
    app.run()
    app.session_state["dashboard_tabs"] = "Forecast"
    app.run()
    assert app.slider[0].value == 12
    app.session_state["dashboard_tabs"] = "Anomalies"
    app.run()
    app.select_slider[0].set_value("High").run()
    app.session_state["dashboard_tabs"] = "Overview"
    app.run()
    app.session_state["dashboard_tabs"] = "Anomalies"
    app.run()
    assert app.select_slider[0].value == "High"
    assert not app.exception

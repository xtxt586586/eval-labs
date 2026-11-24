from types import SimpleNamespace


def test_calibration_variance_measures_repeats_within_each_sample(client, monkeypatch, test_llm_payload):
    llm = client.post("/api/llm-configs", json=test_llm_payload).json()
    metric = client.post("/api/metrics", json={
        "name": "calibration_variance_metric",
        "display_name": "Calibration Variance Metric",
        "metric_type": "aspect_critic",
        "config": {"definition": "Score the sample"},
        "category": "custom",
    }).json()
    scores = iter([0.2, 0.4, 0.6, 0.5, 0.5, 0.5])

    class FakeMetric:
        async def ascore(self, _sample, _judge):
            return SimpleNamespace(value=next(scores), reason="fixture score")

    monkeypatch.setattr("app.api.calibration.build_metric", lambda *_args, **_kwargs: ("llm", FakeMetric()))
    monkeypatch.setattr("app.api.calibration.OpenAIJudgeClient", lambda _config: object())

    response = client.post("/api/calibration/judge", json={
        "llm_config_id": llm["id"],
        "metric_definition_id": metric["id"],
        "repeats": 3,
        "examples": [
            {"sample": {"case": "variable"}, "expected_score": 0.4},
            {"sample": {"case": "stable"}, "expected_score": 0.5},
        ],
    })

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["mean_absolute_error"] == 0.0
    assert payload["score_variance"] == 0.013333
    assert [item["repeat_score_variance"] for item in payload["samples"]] == [0.026667, 0.0]
    assert [item["attempted_requests"] for item in payload["samples"]] == [3, 3]

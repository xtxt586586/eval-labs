def test_llm_config_draft_smoke_test(client, monkeypatch):
    class FakeResponseMessage:
        content = "你好，我是测试模型。"

    class FakeChoice:
        message = FakeResponseMessage()

    class FakeResponse:
        choices = [FakeChoice()]

    class FakeCompletions:
        def create(self, **kwargs):
            return FakeResponse()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        chat = FakeChat()

    monkeypatch.setattr("openai.OpenAI", FakeOpenAI)

    resp = client.post(
        "/api/llm-configs/test-draft",
        json={
            "name": "Draft Test",
            "api_base_url": "https://example.com/v1",
            "api_key": "xxx",
            "model_name": "demo-model",
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["success"] is True
    assert "测试模型" in payload["sample_output"]


def test_llm_config_update_increments_version(client, test_llm_payload):
    created = client.post("/api/llm-configs", json=test_llm_payload).json()
    assert created["version"] == 1

    updated = client.put(
        f"/api/llm-configs/{created['id']}",
        json={"model_name": "test-model-v2"},
    )

    assert updated.status_code == 200
    assert updated.json()["model_name"] == "test-model-v2"
    assert updated.json()["version"] == 2

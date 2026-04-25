from backend.storage.supabase_storage import SupabaseStorageService


def test_supabase_client_prefers_service_role_key(monkeypatch):
    calls = []

    monkeypatch.setattr("backend.storage.supabase_storage.settings.SUPABASE_PROJECT_URL", "https://example.supabase.co")
    monkeypatch.setattr("backend.storage.supabase_storage.settings.SUPABASE_SECRET_KEY", "anon-key")
    monkeypatch.setattr("backend.storage.supabase_storage.settings.SUPABASE_SERVICE_ROLE_KEY", "service-role-key")

    def fake_create_client(url, key):
        calls.append((url, key))
        return object()

    monkeypatch.setattr("backend.storage.supabase_storage.create_client", fake_create_client)

    storage = SupabaseStorageService()
    _ = storage.client

    assert calls == [("https://example.supabase.co", "service-role-key")]

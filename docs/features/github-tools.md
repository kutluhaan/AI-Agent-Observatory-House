# GitHub Tool'ları (GitHub kategorisi)

**Küme:** loop it.9 · **Kategori:** `github` · **Kalıcılık:** `github_connections`
tablosu (migration `0028`).

Org-bazlı **GitHub PAT** (Personal Access Token, Fernet ile şifreli) ile GitHub REST
API'sine okuma-odaklı erişim. `backend/app/services/agent/tools/github.py`.

| Tool | Ne yapar | Endpoint |
|------|----------|----------|
| `github_search` | Repo / kod / issue arama (`kind`) | `/search/{kind}` |
| `github_repo_info` | Repo özeti: yıldız, dil, açıklama + README parçası | `/repos/{o}/{n}` (+ `/readme`) |
| `github_issues` | Issue/PR listele veya tek detay (`number`) | `/repos/{o}/{n}/issues[/{n}]` |
| `github_read_file` | Repo'dan dosya içeriği oku (`path`, `ref`) | `/repos/{o}/{n}/contents/{path}` |

- Token: org'da yapılandırılır (5000 istek/saat + private repo). PAT yoksa tool net uyarı döner.
- Tüm tool'lar exception fırlatmaz; hatayı string döner.
- README + dosya içerikleri base64'ten çözülür, karakter limitiyle kesilir.

## Güvenlik

- PAT **Fernet** ile şifreli (`encrypted_token`); API'de **ham dönmez** (`GithubConnResponse`'ta `token` yok).
- Yönetim **admin**; listeleme/test **member**. `/test` → `GET /user` ile token doğrular (login döner).
- repo parametresi `owner/name` biçiminde doğrulanır.

## Entegrasyon

| | Yer |
|---|---|
| Model | `app/models/github_connection.py` + migration `0028` |
| Tool'lar | `app/services/agent/tools/github.py` (`_gh`, 4 tool) |
| API | `app/api/v1/github_connections.py` (CRUD + `/test`) |
| Kategori | `tool_categories.py` (`github`) |
| UI | `frontend/src/app/(app)/github-connections/page.tsx` + nav (GitHub) + agent-form ikon (Github) |
| Test | `tests/integration/test_github_connections.py` (CRUD + mock /test) |

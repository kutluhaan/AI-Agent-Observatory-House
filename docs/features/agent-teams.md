# Agent Ekipleri (Çok-agent İşbirliği)

**Faz:** F8 · **Kalıcılık:** `teams` + `team_members` + `team_runs` +
`team_run_messages` (migration `0020`). Tüm işbirliği timeline'ı (delegasyon +
paylaşılan pano) DB'de kalıcı.

Rollü çok-agent ekipleri: her üye = mevcut bir **agent** + atanmış **rol** +
**rol promptu**. Herkes kendi ve diğerlerinin rolünü bilir (kadro promptta).

## Roller (varsayılan, düzenlenebilir)

| Rol | Görev |
|---|---|
| **Coordinator** | Orkestratör: görevi alır, üyelere `delegate` ile dağıtır, sonuçları birleştirir. **Yalnız o delege eder.** |
| **Planner** | Görevi adımlara böler |
| **Researcher** | Bilgi toplar |
| **Worker/Developer** | Asıl üretimi yapar |
| **Evaluator/Critic** | Çıktıyı değerlendirir (kabul/red + geri bildirim) |

Her üyenin efektif system prompt'u = `agent prompt + rol promptu + ekip kadrosu`.

## Koordinasyon + paylaşılan bağlam (ikisi birden)

- **Delegasyon:** Coordinator `delegate(role, task)` → o roldeki üye agent çalışır,
  sonucu döner. İzole, trace'lenir; her adım `team_run_messages`'a yazılır
  (kind=delegate/result). Yalnız Coordinator'da `delegate` tool'u vardır.
- **Paylaşılan pano (blackboard):** her üyede `team_share(title, content)` (yazar) +
  `team_board()` (okur) tool'ları. Pano notları kalıcıdır (kind=board); örn.
  Researcher bulgusunu yazar, Worker delegasyonsuz okur. Sıralı yürütme → yarış yok.

## Çalıştırma

```
GET    /teams/roles                  → rol kataloğu + varsayılan promptlar
POST   /teams {name, members:[{agent_id, role, role_prompt}]}   (admin; tam 1 coordinator)
GET    /teams · GET /teams/{id} · PATCH · DELETE
POST   /teams/{id}/run {input}       → 202; arka planda TeamRunner çalışır
GET    /teams/{id}/runs              → çalıştırma listesi
GET    /team-runs/{id}               → run + mesaj timeline'ı (delegasyon + pano + final)
```

`TeamRunner` Coordinator'ı görevle çalıştırır; o delege eder, panoyu kullanır,
final çıktıyı üretir → `team_runs.final_output` + `kind=final` mesajı.

## Güvenlik / sınırlar

- Yalnız Coordinator delege ettiği için çağrı derinliği ≤ 1 (sonsuz döngü yok).
- Ekip üyeleri MCP tool'larını + dosya sistemini de kullanabilir (agent config'i geçerli).

## Entegrasyon noktaları

| | Dosya |
|---|---|
| Modeller | `app/models/team.py` (migration `0020`) |
| Roller | `app/services/team/roles.py` |
| Yürütme | `app/services/team/executor.py` (`build_member_runner`), `runner.py` (`TeamRunner`) |
| Tool'lar | `app/services/agent/tools/team.py` (`delegate`/`team_share`/`team_board`) + `ToolContext` team alanları |
| API | `app/api/v1/teams.py` (CRUD + run + roles + run detail) |
| UI | `frontend/src/app/(app)/teams/*` + `team-runs/[id]` + nav |
| Test | `backend/tests/unit/test_team_roles.py`, `tests/integration/test_teams.py` |

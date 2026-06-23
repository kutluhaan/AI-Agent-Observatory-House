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
GET    /teams/{id}/stats             → ekip performansı (success_rate, avg_duration, trend) [C3]
GET    /team-runs/{id}               → run + mesaj timeline'ı (delegasyon + tool + pano + final)
```

`TeamRunner` Coordinator'ı görevle çalıştırır; o delege eder, panoyu kullanır,
final çıktıyı üretir → `team_runs.final_output` + `kind=final` mesajı.

## İzlenebilirlik (C kümesi)

Ekibin nasıl çalıştığını **canlı ve minimal** izlersin:
- **Üye tool çağrıları** timeline'a işlenir (`kind="tool"`): `AgentRunner.on_tool`
  hook'u her tool sonrası tetiklenir; `make_tool_recorder` bunu `team_run_messages`'a
  yazar (team tool'ları hariç). UI'da delegasyonun altına **girintili, katlanabilir**
  (rol ikonu + 🔧 tool adı + minimal çıktı).
- **Canlı (WebSocket):** yeni mesaj/durum oldukça `WS /ws/team-runs` org kanalına
  `{type:"team_run_updated", run_id}` ping'i yayınlar; istemci ilgili run'ı yeniden
  çeker (yedek: 4sn poll). `record_message(..., org_id=)` + TeamRunner durum yayını.
- **Final çıktı** markdown olarak güzelleştirilmiş.
- Akış: **kim→kim delege (neden=görev) → o üyenin tool çağrıları (minimal) → sonuç →
  … → final (markdown)**.

## Çok-turlu sohbet (B3 / #3)

Ekiple **tıpkı bir agent'la konuşur gibi** sohbet edilir: her mesaj bir tur (team
run); Coordinator **önceki turları hatırlar**; canlı işbirliği akışı + markdown yanıt.

- **Gruplama:** `team_runs.conversation_id` (migration `0023`). Aynı conversation'daki
  run'lar bir sohbet. `POST /teams/{id}/run` `conversation_id` opsiyonel — yoksa yeni
  sohbet başlar; varsa o sohbete eklenir.
- **Hafıza:** TeamRunner, aynı conversation'daki **önceki tamamlanmış run'ları**
  (input + final_output) `history` olarak Coordinator runner'ına verir.
- **Endpoint'ler:** `GET /teams/{id}/conversations` (sohbet listesi),
  `GET /teams/{id}/conversations/{conv}` (turlar).
- **UI:** `/teams/{id}/chat` — mesaj yaz → Enter; her tur: kullanıcı balonu +
  **katlanabilir canlı işbirliği** (delege→tool→sonuç, C'deki akış) + **markdown
  final yanıt**. Geçmiş sohbetler seçici ile yüklenir; "Yeni" ile sıfırdan başlar.
  Ekip detayında **Sohbet** butonu.

### Entegrasyon (C)
| | Dosya |
|---|---|
| Tool hook | `app/services/agent/runner.py` (`on_tool`), `team/executor.py` (`make_tool_recorder`, `record_message` org_id+broadcast) |
| WS | `app/ws/team_runs.py` (`/ws/team-runs`) + `frontend/src/lib/ws.ts` (`subscribeTeamRuns`) |
| Stats | `app/services/team/team_stats.py` + `GET /teams/{id}/stats` + dashboard ekip lider tablosu |
| UI | `team-runs/[id]` (tool mesajı + markdown final + WS), `teams/[id]` (stats şeridi), `dashboard` (agent+ekip lider) |

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

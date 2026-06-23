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

## Bütçeler, limitler ve ekip promptu (loop kontrolü)

Çok-agent çalıştırmaları sonsuz dönüp token tüketmesin diye **katmanlı koruma**
(sektör pratiği — [Anthropic multi-agent research](https://www.anthropic.com/engineering/multi-agent-research-system)
+ [agentic loop control](https://datasciencedojo.com/blog/agentic-loops-explained-from-react-to-loop-engineering-2026-guide/)):

| Katman | Nerede | Varsayılan | Ne yapar |
|--------|--------|-----------|----------|
| **Iterasyon limiti** | `agent.max_steps` (üye bazında) | 6–10 | ReAct döngüsü / tool-çağrı tavanı |
| **Üye süre limiti** | `agent.timeout_seconds` | 120 | Tek üyenin wall-clock tavanı |
| **Çalışma üst süresi** | `team.run_timeout_seconds` | 600 | Coordinator = TÜM orkestrasyonun tavanı |
| **İletişim bütçesi** | `team.max_delegations` | 12 | Coordinator bir run'da en fazla N delege; aşınca `delegate` "panodan sentezle, dur" döndürür |
| **Ekip promptu** | `team.shared_instructions` | — | Tüm üyelere eklenir: ortak kurallar (kısa çalış, az arama, dil, kaynak) |

- **Coordinator timeout override:** `build_member_runner`, coordinator için
  `timeout_seconds = team.run_timeout_seconds` kullanır (üyeler kendi `agent.timeout_seconds`).
- **Delegasyon bütçesi:** `delegate` tool'u, run'daki `kind="delegate"` mesaj sayısını
  `team.max_delegations` ile kıyaslar; aşılırsa delege etmeden "team_board ile sentezle, final ver" mesajı döner.
- **Bütçe-farkındalığı (önemli):** `build_member_runner`, her üyenin system prompt'una
  `--- ÇALIŞMA BÜTÇEN ---` bloğunu **dinamik** ekler (gerçek `max_delegations`/`max_steps`/süre
  değerleriyle). Coordinator açıkça "EN FAZLA N delege; N'den sonra delegate CEVAP DÖNDÜRMEZ;
  limite yaklaşınca team_board'dan sentezle" uyarısını görür. Sayı statik değil — ekip ayarı
  değişince prompt da otomatik güncellenir. Yani limit hem **prompt'ta bildirilir** (önleyici)
  hem de `delegate`'te **zorlanır** (kesin).
- **Roller netleştirilmeli:** `delegate(role, ...)` ROL ile çalışır — her uzman rol
  (researcher/worker/evaluator/planner) ayrı atanmalı; iki üyeye aynı rol verilirse
  Coordinator yalnız ilkine ulaşır (yaygın hata, timeout sebebi olabilir).
- **Prompt rehberi (Anthropic):** her role net **hedef + çıktı formatı + tool/kaynak
  rehberi + sınır + bütçe** ver; belirsiz/kısa talimat → tekrarlı arama, token israfı.

UI: ekip oluşturma + ekip detay sayfasında **"Ekip ayarları (prompt & bütçe)"** bölümü.

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
- **UI:** `/teams/{id}/chat` — **tek-agent sohbetiyle birebir aynı düzen**: solda
  **geçmiş sohbetler kenar çubuğu** (yeni sohbet + sil + relatif zaman), sağda
  **chat-bubble**'lı akış (kullanıcı sağda, ekip solda). Her tur: kullanıcı balonu +
  **katlanabilir canlı işbirliği** (delege→tool→sonuç; final gelince otomatik kapanır) +
  **markdown final yanıt** balonu. Çok-turlu (Coordinator önceki turları hatırlar).
  Silme: `DELETE /teams/{id}/conversations/{conv}`.
- **Markdown her yerde:** ekip çıktıları (final, paylaşılan pano, delege/sonuç içerikleri)
  hem sohbet hem `team-runs/{id}` sayfasında `Markdown` ile güzelleştirilir (tablo, başlık,
  liste). Ham tool I/O düz metin kalır.

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

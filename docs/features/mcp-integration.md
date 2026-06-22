# MCP Server Entegrasyonu

**Faz:** F7.2 · **Kalıcılık:** `mcp_servers` tablosu (org-bazlı) +
`agents.mcp_tools` (migration `0019`). İstemci: resmi **`mcp`** SDK, **Streamable
HTTP** transport. Strateji: **çağrı başına bağlan** (stateless).

Dış MCP (Model Context Protocol) sunucularındaki tool'ları agent'lara açar. Org bir
kez MCP sunucusu ekler; agent oluştururken o sunucunun tool'larından seçer; agent
çalışırken bu tool'lar uzak sunucuda yürütülür.

## Akış

```
POST   /mcp-servers              {name, url, api_key?}     → org'a sunucu ekle (admin)
GET    /mcp-servers                                        → listele (member)
PATCH  /mcp-servers/{id}                                   → güncelle (admin)
DELETE /mcp-servers/{id}                                   → sil (admin)
GET    /mcp-servers/{id}/tools                             → canlı tool keşfi (member)
                                                             bağlanılamazsa 502 MCP_CONNECT_FAILED
```

Agent, kullanacağı tool'ları `mcp_tools: [{server_id, tool_name, description, input_schema}]`
olarak saklar (şema config sırasında discovery'den alınır → çalışma anında ağ
çağrısı gerekmez, yalnız yürütmede bağlanılır).

## Çalışma zamanı

1. Runner kurulurken `resolve_agent_mcp_tools(db, agent)` → her tool'a sunucu URL +
   (şifre çözülmüş) key eklenir.
2. `AgentRunner` bunları **`mcp__{tool}`** önekiyle LLM'e tool olarak sunar
   (`_mcp_definitions`) — native tool'larla çakışmaz.
3. LLM `mcp__search` çağırınca `_execute_tool` bunu yakalar → `call_mcp_tool(url, key,
   "search", args)` ile uzak sunucuya **Streamable HTTP** üzerinden bağlanır,
   `tools/call` yapar, sonucu metne çevirir. Hata olursa zarif `[MCP tool error: …]`.
4. chat/run (`_build_runner`) + test (`case_runner`/sandbox) yollarının ikisi de destekler.

## Güvenlik / ağ

- Sunucu API key'i Fernet ile şifreli (`Authorization: Bearer`), yanıtta `has_api_key`.
- Docker backend MCP sunucusuna ulaşabilmeli (host.docker.internal / IP).

## Entegrasyon noktaları

| | Dosya |
|---|---|
| İstemci | `backend/app/services/mcp/client.py` (`list_mcp_tools`, `call_mcp_tool`) |
| Çözümleyici | `backend/app/services/mcp/resolver.py` (`resolve_agent_mcp_tools`) |
| Model | `app/models/mcp.py` (`McpServer`) + `agents.mcp_tools` (migration `0019`) |
| Runner | `app/services/agent/runner.py` (`_mcp_definitions`, `_execute_tool` routing) |
| API | `app/api/v1/mcp_servers.py` (CRUD + discovery) |
| UI — sunucular | `frontend/src/app/(app)/mcp-servers/page.tsx` + nav |
| UI — agent | `frontend/src/components/agent-form.tsx` (`McpServerTools`) |
| Bağımlılık | `mcp>=1.2.0` (pyproject) |
| Test | `backend/tests/unit/test_mcp.py`, `tests/integration/test_mcp_endpoints.py` |

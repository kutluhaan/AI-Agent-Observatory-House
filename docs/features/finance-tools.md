# Finans Tool'ları (Finans kategorisi)

**Küme:** D/#2 · **Kalıcılık:** kod (tool kaydı) — DB/migration gerektirmez.
Anahtarsız public kaynaklarla piyasa verisi + teknik analiz. **Trading ekibinin temeli.**
**Gerçek emir YOK** — yalnız veri/analiz (güvenli; kullanıcı "sadece analiz/öneri" seçti).

## Tool'lar (`backend/app/services/agent/tools/finance.py`)

| Tool | Ne yapar | Kaynak |
|------|----------|--------|
| `get_crypto_price` | Anlık USD fiyat + 24s değişim/aralık/hacim | CoinGecko `/coins/markets` (anahtarsız) |
| `get_crypto_ohlc` | Günlük fiyat geçmişi özeti (N gün) | CoinGecko `/market_chart` → günlük downsample |
| `get_stock_quote` | Anlık hisse fiyatı + önceki kapanış + değişim | Yahoo Finance `chart` (anahtarsız, JSON) |
| `get_stock_history` | Son N işlem günü kapanış özeti | Yahoo Finance `chart` |
| `get_technical_indicators` | RSI-14, SMA-20/50, EMA-12/26, MACD(12,26,9) | Fiyat geçmişinden **saf-Python hesap** (ek API yok) |
| `get_market_news` | Bir sembol/konu için güncel finans haberi | `_web_search` (Tavily, news-odaklı) |

- **Asset tipi:** `get_technical_indicators(symbol, asset_type)` — `asset_type` `crypto`|`stock`.
- Kripto sembol: `BTC`, `ETH` … · Hisse: `AAPL`, `MSFT` … (ABD varsayılır; Yahoo sembolü).
- Tüm tool'lar **exception fırlatmaz**, hatayı string döner (AgentRunner uyumlu).

## Tasarım notları (öğrenilenler)

- **Stooq elendi:** `stooq.com` CSV ucu sunucu/bot isteklerine JS-challenge HTML döndürüyor
  (CSV değil) → **Yahoo Finance chart API**'sine geçildi (anahtarsız, JSON, güvenilir).
- **CoinGecko `/ohlc` 4-günlük mum** veriyor (90g → ~23 nokta, indikatöre yetmez) →
  `/market_chart` (saatlik) çekilip **güne göre downsample** edilerek günlük kapanış üretiliyor.
- İndikatörler saf-Python; RSI Wilder yöntemiyle, MACD = EMA12−EMA26 + 9-EMA sinyal.

## Entegrasyon

| | Yer |
|---|---|
| Tool'lar | `backend/app/services/agent/tools/finance.py` (`register_finance_tools`) |
| Kayıt | `app/main.py` lifespan |
| Kategori | `app/services/agent/tool_categories.py` (`finance`, artık `coming_soon=False`) |
| UI | `frontend/src/components/agent-form.tsx` (ikon `TrendingUp`; kategori dinamik gelir) |
| Test | `backend/tests/unit/test_finance.py` (indikatör matematiği + kayıt) |

## Trading & Piyasa Analiz Ekibi (kuruldu)

Finans tool'larını kullanan örnek ekip — **mevcut team yapısına oturur, yeni mimari yok**.
5 ajan (hepsi Gemini 2.5 Pro), **gerçek emir YOK** (yalnız analiz + öneri), kripto + hisse.

| Rol (etiket) | Ajan | Tool'lar |
|---|---|---|
| `coordinator` | Portföy & Karar Ajanı | think, write_todos (+ delege/board) |
| `technical` | Teknik Analist | get_technical_indicators, kripto/hisse fiyat+geçmiş |
| `news` | Haber & Sentiment Analisti | get_market_news, web_search, read_url |
| `fundamental` | Temel Analist | web_search, read_url, fiyat |
| `evaluator` | Risk Yöneticisi | get_technical_indicators, fiyat |

- **Çok-analist çözümü (keşif):** `TeamMember.role` serbest metin olduğu için 3 analiste
  **benzersiz rol etiketi** (`technical`/`news`/`fundamental`) verildi → Coordinator
  `delegate('technical', …)` ile her birini ayrı çağırabiliyor (rol başına 1-ajan limiti aşıldı, kod değişmeden).
- **Bull/Bear münazara** ([TradingAgents](https://arxiv.org/abs/2412.20138)) ekstra ajan yerine
  **Coordinator promptuna gömülü** (boğa↔ayı tezlerini tarttırıp karara bağlar).
- **Final çıktı:** `Öneri: AL/SAT/TUT · gerekçe · Risk · Güven: %X` (markdown). Eğitim amaçlı, finansal tavsiye değil.

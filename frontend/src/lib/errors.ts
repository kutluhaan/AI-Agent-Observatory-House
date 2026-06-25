/**
 * Hata mesajlarını kullanıcı dostu Türkçe metne çevirir.
 *
 * Provider'dan gelen ham billing/kota/unavailable mesajlarını chat'te olduğu gibi
 * göstermek yerine anlamlı bir başlık + ipucu üretir; ham metni "teknik detay"
 * olarak ayrı tutar.
 */
export interface FriendlyError {
  title: string;
  hint?: string;
  detail?: string;
}

const CODE_MESSAGES: Record<string, { title: string; hint?: string }> = {
  PROVIDER_RATE_LIMITED: {
    title: "Model şu an çok yoğun ya da kotan dolmuş.",
    hint: "Birkaç dakika sonra tekrar dene veya daha az yoğun bir model seç.",
  },
  PROVIDER_AUTH_FAILED: {
    title: "Provider API anahtarı geçersiz.",
    hint: "Anahtarı kontrol et ve gerekiyorsa yeniden gir.",
  },
  PROVIDER_NOT_CONFIGURED: {
    title: "Bu provider için API anahtarı yapılandırılmamış.",
    hint: "Anahtarı .env'e ekle ya da workspace ayarlarından gir.",
  },
  PROVIDER_REQUEST_FAILED: {
    title: "Sağlayıcıdan beklenmeyen bir hata geldi.",
    hint: "Geçici bir sorun, kota ya da faturalandırma kaynaklı olabilir.",
  },
  AGENT_TIMEOUT: {
    title: "Agent zaman aşımına uğradı.",
    hint: "Daha kısa bir görev dene ya da agent'ın timeout süresini artır.",
  },
  AGENT_MAX_STEPS_EXCEEDED: {
    title: "Agent maksimum adım sayısına ulaştı.",
    hint: "Görev karmaşıksa adım limitini artırabilirsin.",
  },
  AGENT_TOOL_ERROR: { title: "Bir araç çalışırken hata oluştu." },
  HITL_REJECTED: { title: "İşlem reddedildi, agent durdu." },
  HITL_TIMEOUT: { title: "Onay/yanıt beklenirken süre doldu." },
  RUN_FAILED: { title: "Çalıştırma başlatılamadı." },
  AGENT_UNEXPECTED_ERROR: { title: "Beklenmeyen bir hata oluştu." },
};

export function friendlyError(
  code: string | undefined,
  message: string | undefined,
): FriendlyError {
  const raw = (message ?? "").trim();
  const lower = `${raw} ${code ?? ""}`.toLowerCase();

  if (/quota|resource_exhausted|insufficient|billing|payment|credit|exceeded your current/.test(lower)) {
    return {
      title: "Kota veya faturalandırma sorunu.",
      hint: "Provider hesabında kullanım limiti dolmuş ya da faturalandırma gerekiyor olabilir.",
      detail: raw || code,
    };
  }
  if (/unavailable|overloaded|high demand|try again later|\b503\b/.test(lower)) {
    return {
      title: "Model şu an aşırı yoğun.",
      hint: "Geçici bir durum — birkaç saniye sonra tekrar dene.",
      detail: raw || code,
    };
  }

  const mapped = code ? CODE_MESSAGES[code] : undefined;
  if (mapped) {
    return { ...mapped, detail: raw || code };
  }
  return {
    title: raw || "Bir hata oluştu.",
    detail: code && code !== "UNKNOWN_ERROR" ? code : undefined,
  };
}

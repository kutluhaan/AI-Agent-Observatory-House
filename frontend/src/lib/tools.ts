/**
 * Tool'lar için kullanıcı dostu etiketler — HITL onay ekranı ve tool kartlarında
 * JSON yerine normal metin göstermek için.
 */

const TOOL_LABELS: Record<string, string> = {
  web_search: "Web araması",
  read_url: "Web sayfası",
  summarize: "Metni özetle",
  save_note: "Not kaydet",
  get_notes: "Kaydedilen notları getir",
  echo: "Metni aynen döndür (test)",
  calculator: "Hesap yap",
  call_agent: "Başka bir agent'ı çağır",
  think: "Düşünüyor",
  write_todos: "Görev listesi",
  ask_user: "Kullanıcıya soru",
  write_file: "Dosya yaz",
  read_file: "Dosya oku",
  modify_file: "Dosya düzenle",
  delete_file: "Dosya sil",
  list_files: "Dosyaları listele",
  make_directory: "Klasör oluştur",
  search_files: "Dosyalarda ara",
  move_file: "Dosya taşı",
};

const ARG_LABELS: Record<string, string> = {
  query: "Arama sorgusu",
  url: "Adres (URL)",
  max_results: "Sonuç sayısı",
  max_chars: "Karakter limiti",
  topic: "Konu",
  time_range: "Zaman aralığı",
  text: "Metin",
  focus: "Odak",
  max_sentences: "Cümle sayısı",
  title: "Başlık",
  content: "İçerik",
  expression: "İfade",
  agent_id: "Agent",
  input: "Girdi",
  path: "Yol",
  old_string: "Eski metin",
  new_string: "Yeni metin",
  source: "Kaynak",
  destination: "Hedef",
};

/** Tool'un okunabilir adı. */
export function toolLabel(name: string): string {
  return TOOL_LABELS[name] ?? name.replace(/_/g, " ");
}

/** Bir argüman anahtarının okunabilir etiketi. */
export function argLabel(key: string): string {
  return ARG_LABELS[key] ?? key.replace(/_/g, " ");
}

/** Argümanları {label, value} satırlarına çevirir (gösterim için). */
export function formatArgs(
  args: Record<string, unknown> | null | undefined,
): { label: string; value: string }[] {
  if (!args) return [];
  return Object.entries(args).map(([k, v]) => ({
    label: argLabel(k),
    value:
      typeof v === "string"
        ? v
        : typeof v === "number" || typeof v === "boolean"
          ? String(v)
          : JSON.stringify(v),
  }));
}

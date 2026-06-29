// Current Google Workspace brand icons (2020+ redesign)

export type IconProps = { size?: number; className?: string };

export function GmailIcon({ size = 16, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" className={className}>
      {/* Left column — red */}
      <path fill="#EA4335" d="M6 40h6V22L0 16v20a4 4 0 004 4h2z" />
      {/* Right column — green */}
      <path fill="#34A853" d="M36 40h6a4 4 0 004-4V16l-10 6v18z" />
      {/* Top-right flap — blue */}
      <path fill="#4285F4" d="M36 8v14l10-6V10a4 4 0 00-6.4-3.2L36 8z" />
      {/* Center M — yellow */}
      <path fill="#FBBC05" d="M12 22v18l12-9 12 9V22L24 13 12 22z" />
      {/* Top-left flap — dark red */}
      <path fill="#C5221F" d="M0 10v6l12 6V8L5.6 3.8A4 4 0 000 8v2z" />
    </svg>
  );
}

export function GoogleCalendarIcon({ size = 16, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" className={className}>
      {/* Outer border */}
      <rect x="5" y="6" width="38" height="37" rx="3" fill="#fff" stroke="#DADCE0" strokeWidth="1" />
      {/* Top bar — blue */}
      <rect x="5" y="6" width="38" height="9" rx="3" fill="#1A73E8" />
      <rect x="5" y="12" width="38" height="3" fill="#1A73E8" />
      {/* Calendar lines */}
      <line x1="5" y1="22" x2="43" y2="22" stroke="#DADCE0" strokeWidth="0.8" />
      <line x1="5" y1="31" x2="43" y2="31" stroke="#DADCE0" strokeWidth="0.8" />
      {/* "15" — main date number */}
      <text x="24" y="37" textAnchor="middle" fill="#1A73E8" fontSize="17" fontWeight="700" fontFamily="Arial,sans-serif">15</text>
      {/* Calendar hanger pins */}
      <rect x="13" y="3" width="3" height="8" rx="1.5" fill="#1A73E8" />
      <rect x="32" y="3" width="3" height="8" rx="1.5" fill="#1A73E8" />
    </svg>
  );
}

export function GoogleDriveIcon({ size = 16, className }: IconProps) {
  // Official Google Drive icon paths (87.3 × 78 viewBox)
  return (
    <svg width={size} height={size} viewBox="0 0 87.3 78" className={className}>
      <path fill="#0066DA" d="M6.6 66.85l3.85 6.65c.8 1.4 1.95 2.5 3.3 3.3L27.5 53H0c0 1.55.4 3.1 1.2 4.5z" />
      <path fill="#00AC47" d="M43.65 25L29.9 1.2C28.55 2 27.4 3.1 26.6 4.5L1.2 48.5A9 9 0 000 53h27.5z" />
      <path fill="#FFBA00" d="M73.55 76.8c1.35-.8 2.5-1.9 3.3-3.3l1.6-2.75 7.65-13.25c.8-1.4 1.2-2.95 1.2-4.5H59.8l5.85 11.5z" />
      <path fill="#EA4335" d="M43.65 25L57.4 1.2A9.01 9.01 0 0053.3 0H34c-1.55 0-3.1.45-4.5 1.2z" />
      <path fill="#00832D" d="M59.8 53H27.5L13.75 76.8c1.4.8 2.95 1.2 4.5 1.2h50.8c1.55 0 3.1-.4 4.5-1.2z" />
      <path fill="#2684FC" d="M73.4 26.5L60.7 4.5c-.8-1.4-1.95-2.5-3.3-3.3L43.65 25l16.15 28H87.3c0-1.55-.4-3.1-1.2-4.5z" />
    </svg>
  );
}

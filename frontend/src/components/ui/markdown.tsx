"use client";

import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { memo } from "react";
import { cn } from "@/lib/utils";

/**
 * Agent çıktısı + dosya içeriği için zengin Markdown renderer.
 * Koyu tema için elle stillenmiş öğeler (typography eklentisi gerekmez).
 * Ham HTML render edilmez (rehype-raw yok) → XSS güvenli.
 */
const components: Components = {
  h1: ({ children }) => (
    <h1 className="mb-2 mt-4 text-lg font-semibold text-zinc-100 first:mt-0">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="mb-2 mt-4 text-base font-semibold text-zinc-100 first:mt-0">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="mb-1.5 mt-3 text-sm font-semibold text-zinc-200 first:mt-0">{children}</h3>
  ),
  h4: ({ children }) => (
    <h4 className="mb-1.5 mt-3 text-sm font-medium text-zinc-200 first:mt-0">{children}</h4>
  ),
  p: ({ children }) => <p className="my-2 leading-relaxed first:mt-0 last:mb-0">{children}</p>,
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-indigo-400 underline decoration-indigo-400/30 underline-offset-2 transition-colors hover:text-indigo-300"
    >
      {children}
    </a>
  ),
  ul: ({ children }) => <ul className="my-2 ml-1 list-disc space-y-1 pl-4 marker:text-zinc-600">{children}</ul>,
  ol: ({ children }) => <ol className="my-2 ml-1 list-decimal space-y-1 pl-4 marker:text-zinc-500">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  strong: ({ children }) => <strong className="font-semibold text-zinc-100">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  blockquote: ({ children }) => (
    <blockquote className="my-2 border-l-2 border-indigo-500/40 pl-3 text-zinc-400">{children}</blockquote>
  ),
  hr: () => <hr className="my-3 border-zinc-800" />,
  code: ({ className, children, ...props }) => {
    const text = String(children ?? "");
    const isBlock = /language-/.test(className ?? "") || text.includes("\n");
    if (isBlock) {
      return (
        <code className={cn("font-mono text-[0.8rem] leading-relaxed", className)} {...props}>
          {children}
        </code>
      );
    }
    return (
      <code className="rounded bg-zinc-800/80 px-1.5 py-0.5 font-mono text-[0.85em] text-indigo-200" {...props}>
        {children}
      </code>
    );
  },
  pre: ({ children }) => (
    <pre className="my-2.5 overflow-x-auto rounded-lg border border-zinc-800 bg-zinc-950 p-3 text-zinc-200">
      {children}
    </pre>
  ),
  table: ({ children }) => (
    <div className="my-2.5 overflow-x-auto">
      <table className="w-full border-collapse text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="border-b border-zinc-700">{children}</thead>,
  th: ({ children }) => (
    <th className="border border-zinc-800 px-3 py-1.5 text-left font-medium text-zinc-200">{children}</th>
  ),
  td: ({ children }) => <td className="border border-zinc-800 px-3 py-1.5 text-zinc-300">{children}</td>,
  img: ({ src, alt }) => (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={typeof src === "string" ? src : ""} alt={alt ?? ""} className="my-2 max-w-full rounded-lg" />
  ),
};

function MarkdownImpl({ children, className }: { children: string; className?: string }) {
  return (
    <div className={cn("text-sm text-zinc-200 [&>*:first-child]:mt-0 [&>*:last-child]:mb-0", className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {children}
      </ReactMarkdown>
    </div>
  );
}

export const Markdown = memo(MarkdownImpl);

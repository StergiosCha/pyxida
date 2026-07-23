import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/** Renders LLM Markdown (tables, headings, bold, lists) safely — no raw HTML.
 *  react-markdown escapes HTML by default; we do not enable rehype-raw, so any
 *  HTML in the model output is shown as text, not executed. */
export default function Markdown({ children }: { children: string }) {
  return (
    <div className="md">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
    </div>
  );
}

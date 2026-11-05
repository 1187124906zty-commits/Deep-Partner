/** Browser-only raw Markdown AST cache. Each processor gets a private clone:
 * source links and later remark/rehype transforms must never mutate the cache.
 */
type Parser = (content: string, file: unknown) => unknown;
const entries = new Map<string, { tree: unknown; bytes: number }>();
const MAX_BYTES = 32 * 1024 * 1024;
let bytes = 0;

export function clearMarkdownParseCache(): void {
  entries.clear();
  bytes = 0;
}

export function remarkCachedParse(this: { parser?: Parser }, mode: string): void {
  const parse = this.parser;
  if (!parse || typeof window === "undefined") return;
  this.parser = (content, file) => {
    if (content.length < 256) return parse(content, file);
    const key = `${mode}\0${content}`;
    const cached = entries.get(key);
    if (cached) {
      entries.delete(key);
      entries.set(key, cached);
      return structuredClone(cached.tree);
    }
    const tree = parse(content, file);
    // Conservative charge avoids serializing a large AST on every token.
    const charge = content.length * 24;
    if (charge <= MAX_BYTES) {
      entries.set(key, { tree: structuredClone(tree), bytes: charge });
      bytes += charge;
      while (entries.size > 128 || bytes > MAX_BYTES) {
        const oldest = entries.keys().next().value;
        if (oldest === undefined) break;
        bytes -= entries.get(oldest)!.bytes;
        entries.delete(oldest);
      }
    }
    return tree;
  };
}

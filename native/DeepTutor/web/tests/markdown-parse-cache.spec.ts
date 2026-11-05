import { beforeEach, expect, it, vi } from "vitest";
import { clearMarkdownParseCache, remarkCachedParse } from "@/components/common/markdown-parse-cache";

beforeEach(clearMarkdownParseCache);

it("reuses parsing across remounts while keeping later source transforms private", () => {
  const parse = vi.fn((_content: string, _file: unknown) => ({ type: "root", children: [{ type: "text", value: "original" }] }));
  const first = { parser: parse };
  remarkCachedParse.call(first, "gfm");
  const source = "Long scientific paragraph. ".repeat(100);
  const mutable = first.parser(source, null);
  mutable.children[0].value = "per-message source annotation";
  const second = { parser: parse };
  remarkCachedParse.call(second, "gfm");
  expect(second.parser(source, null).children[0].value).toBe("original");
  expect(parse).toHaveBeenCalledTimes(1);
});

it("separates math parse options and clears private content on account/workspace reset", () => {
  const parse = vi.fn((_content: string, _file: unknown) => ({ type: "root", children: [] }));
  const source = "$c(x,t)$ ".repeat(100);
  const plain = { parser: parse }; remarkCachedParse.call(plain, "gfm"); plain.parser(source, null);
  const math = { parser: parse }; remarkCachedParse.call(math, "gfm-math"); math.parser(source, null);
  expect(parse).toHaveBeenCalledTimes(2);
  clearMarkdownParseCache();
  math.parser(source, null);
  expect(parse).toHaveBeenCalledTimes(3);
});

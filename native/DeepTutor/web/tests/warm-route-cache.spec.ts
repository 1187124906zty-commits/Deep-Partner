import { describe, expect, it, vi } from "vitest";
import { keepRoutesWarm } from "@/lib/warm-route-cache";

describe("resident route shells", () => {
  it("refills an invalidated route without scheduling duplicate initial requests", () => {
    const router = { prefetch: vi.fn() };
    keepRoutesWarm(router, ["/settings/general", "/chat/a", "/chat/a"]);
    expect(router.prefetch).toHaveBeenCalledTimes(2);
    router.prefetch.mock.calls[0][1].onInvalidate();
    expect(router.prefetch).toHaveBeenCalledTimes(3);
    expect(router.prefetch.mock.calls[2][0]).toBe("/settings/general");
  });

  it("stops refilling after the owning page or workspace is disposed", () => {
    const router = { prefetch: vi.fn() };
    const stop = keepRoutesWarm(router, ["/chat/a"]);
    const invalidated = router.prefetch.mock.calls[0][1].onInvalidate;
    stop();
    invalidated();
    expect(router.prefetch).toHaveBeenCalledTimes(1);
  });
});

import { describe, expect, it } from "vitest";

import {
  ERP_TIME_ZONE,
  formatLocalDateTime,
  localDateString,
  localDateTimeString,
  localMonthString,
} from "../src/utils/time";

describe("ERP local time", () => {
  it("uses Asia/Shanghai even when the browser runtime is elsewhere", () => {
    const instant = new Date("2026-08-12T16:30:45Z");
    expect(ERP_TIME_ZONE).toBe("Asia/Shanghai");
    expect(localDateString(instant)).toBe("2026-08-13");
    expect(localMonthString(instant)).toBe("2026-08");
    expect(localDateTimeString(instant)).toBe("2026-08-13T00:30:45");
  });

  it("converts offset timestamps and preserves local wall-clock strings", () => {
    expect(formatLocalDateTime("2026-08-12T13:30:45Z")).toBe("2026-08-12 21:30:45");
    expect(formatLocalDateTime("2026-08-12T21:30:45")).toBe("2026-08-12 21:30:45");
  });
});

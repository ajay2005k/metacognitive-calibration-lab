import { describe, it, expect, vi, afterEach } from "vitest";
import {
  generateDots,
  shuffledOptions,
  remainingSeconds,
  startTimer,
} from "./logic";
afterEach(() => vi.useRealTimers());
describe("option mapping", () => {
  const item = { options: ["a", "b", "c", "d"] };
  it("retains original answer indexes after shuffling", () => {
    const shuffled = shuffledOptions(item, () => 0);
    expect(shuffled.map((o) => o.text)).not.toEqual(item.options);
    for (const option of shuffled)
      expect(item.options[option.originalIndex]).toBe(option.text);
    expect(new Set(shuffled.map((o) => o.originalIndex)).size).toBe(4);
  });
  it("never shuffles circle positions", () => {
    expect(
      shuffledOptions({ ...item, stimulus: { type: "circles" } }, () => 0).map(
        (o) => o.text,
      ),
    ).toEqual(item.options);
  });
});
describe("dot generation", () => {
  for (const count of [0, 12, 24, 38, 100])
    it(`generates exactly ${count} non-overlapping dots inside the box`, () => {
      for (const random of [Math.random, () => 0, () => 0.999999]) {
        const dots = generateDots(count, random);
        expect(dots).toHaveLength(count);
        for (let i = 0; i < dots.length; i++) {
          expect(dots[i].x).toBeGreaterThanOrEqual(5);
          expect(dots[i].x).toBeLessThanOrEqual(435);
          expect(dots[i].y).toBeGreaterThanOrEqual(5);
          expect(dots[i].y).toBeLessThanOrEqual(235);
          for (let j = 0; j < i; j++)
            expect(
              Math.hypot(dots[i].x - dots[j].x, dots[i].y - dots[j].y),
            ).toBeGreaterThanOrEqual(10);
        }
      }
    });
  it("rejects impossible counts", () => {
    expect(() => generateDots(101)).toThrow();
    expect(() => generateDots(-1)).toThrow();
  });
});
describe("deadline timer", () => {
  it("rounds up and never goes negative", () => {
    expect(remainingSeconds(20000, 0)).toBe(20);
    expect(remainingSeconds(20000, 19001)).toBe(1);
    expect(remainingSeconds(20000, 21000)).toBe(0);
  });
  it("expires once and cancellation prevents expiration", () => {
    vi.useFakeTimers();
    vi.setSystemTime(0);
    const expire = vi.fn(),
      tick = vi.fn();
    startTimer({
      deadline: 20000,
      now: Date.now,
      onTick: tick,
      onExpire: expire,
    });
    vi.advanceTimersByTime(19900);
    expect(expire).not.toHaveBeenCalled();
    vi.advanceTimersByTime(500);
    expect(expire).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(1000);
    expect(expire).toHaveBeenCalledTimes(1);
    const cancel = startTimer({
      deadline: Date.now() + 1000,
      now: Date.now,
      onTick: tick,
      onExpire: expire,
    });
    cancel();
    vi.advanceTimersByTime(2000);
    expect(expire).toHaveBeenCalledTimes(1);
  });
  it("handles already expired deadlines immediately", () => {
    vi.useFakeTimers();
    const expire = vi.fn();
    startTimer({
      deadline: 0,
      now: () => 1,
      onTick: () => {},
      onExpire: expire,
    });
    expect(expire).toHaveBeenCalledOnce();
  });
});

import { useState } from "react";
export default function FillerTask({ seconds }) {
  const [start] = useState(() => 80 + Math.floor(Math.random() * 20));
  return (
    <div className="mx-auto max-w-lg py-12 text-center">
      <p className="eyebrow">A SHORT DISTRACTION</p>
      <h2 className="mt-4">Count backwards by 3, starting at {start}.</h2>
      <p className="my-4 text-sm text-muted">
        Type the numbers below. This is not scored or recorded.
      </p>
      <label className="field">
        Your countdown
        <input
          autoFocus
          autoComplete="off"
          placeholder={`${start}, ${start - 3}, …`}
        />
      </label>
      <p className="mt-6 text-sm text-muted" role="timer">
        Question begins in {seconds} seconds
      </p>
    </div>
  );
}

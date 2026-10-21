export default function ConfidenceSlider({ value, onChange }) {
  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <label htmlFor="confidence" className="font-medium">
          How confident are you?
        </label>
        <span className="rounded-md bg-blue-50 px-3 py-1 font-mono text-xl font-semibold text-brand">
          {value ?? 50}%
        </span>
      </div>
      <input
        id="confidence"
        type="range"
        min="0"
        max="100"
        step="1"
        value={value ?? 50}
        onPointerDown={(e) => onChange(Number(e.currentTarget.value))}
        onKeyDown={(e) => {
          if (
            [
              "ArrowLeft",
              "ArrowRight",
              "ArrowUp",
              "ArrowDown",
              "Home",
              "End",
            ].includes(e.key)
          )
            onChange(Number(e.currentTarget.value));
        }}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-brand"
      />
      <div className="mt-2 flex justify-between text-xs text-muted">
        <span>0 · Guessing</span>
        <span>50 · Unsure</span>
        <span>100 · Certain</span>
      </div>
      <p className="mt-3 text-xs text-muted">
        Move or touch the slider to confirm your confidence.
      </p>
    </div>
  );
}

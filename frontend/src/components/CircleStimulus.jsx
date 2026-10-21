export default function CircleStimulus({ radii }) {
  return (
    <svg
      role="img"
      aria-label="Four circles; compare their sizes"
      viewBox="0 0 300 260"
      width="300"
      height="260"
      className="mx-auto max-w-full"
    >
      {radii.map((r, i) => (
        <circle
          key={i}
          cx={i % 2 ? 220 : 80}
          cy={i < 2 ? 65 : 195}
          r={r}
          fill="#245de0"
        />
      ))}
    </svg>
  );
}

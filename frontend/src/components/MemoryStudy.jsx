export default function MemoryStudy({ words, seconds }) {
  return (
    <div className="py-10 text-center">
      <p className="eyebrow">MEMORIZE THESE WORDS</p>
      <h2 className="mt-3">
        Study the list. You’ll be asked about it shortly.
      </h2>
      <div className="mx-auto my-10 grid max-w-lg grid-cols-2 gap-4">
        {words.map((word) => (
          <div
            key={word}
            className="rounded-lg border border-line bg-paper p-4 text-xl"
          >
            {word}
          </div>
        ))}
      </div>
      <p role="timer" className="text-sm text-muted">
        {seconds} seconds remaining
      </p>
    </div>
  );
}

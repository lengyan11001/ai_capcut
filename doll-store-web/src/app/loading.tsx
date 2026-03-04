export default function GlobalLoading() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <div className="h-8 w-48 animate-pulse rounded bg-gray-200" />
      <div className="mt-4 h-4 w-80 animate-pulse rounded bg-gray-100" />
      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, idx) => (
          <div key={idx} className="h-56 animate-pulse rounded-lg border border-gray-100 bg-gray-50" />
        ))}
      </div>
    </div>
  );
}

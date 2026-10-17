export default function Loading() {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <div className="h-8 w-56 animate-pulse rounded-xl bg-secondary/60" />
        <div className="h-4 w-80 animate-pulse rounded-lg bg-secondary/40" />
      </div>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="h-24 animate-pulse rounded-lg border border-border bg-secondary/30"
          />
        ))}
      </div>
      <div className="h-64 animate-pulse rounded-lg border border-border bg-secondary/20" />
    </div>
  );
}

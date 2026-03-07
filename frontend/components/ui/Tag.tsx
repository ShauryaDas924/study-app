export function Tag({ text }: { text: string }) {
  return (
    <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-700">
      {text}
    </span>
  );
}
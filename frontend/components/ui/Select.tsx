import { SelectHTMLAttributes } from "react";

export function Select({
  className = "",
  ...props
}: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className={[
        "w-full rounded-xl border border-slate-200 px-3 py-2 text-sm bg-white",
        "focus:outline-none focus:ring-2 focus:ring-green-200",
        className,
      ].join(" ")}
    />
  );
}
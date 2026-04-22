import { SelectHTMLAttributes } from "react";

export function Select({
  className = "",
  ...props
}: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className={[
        "w-full app-input px-3 py-2 text-sm bg-white/90",
        className,
      ].join(" ")}
    />
  );
}
import { InputHTMLAttributes } from "react";

export function Input({
  className = "",
  ...props
}: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={[
        "w-full rounded-xl border border-slate-200 px-3 py-2 text-sm",
        "focus:outline-none focus:ring-2 focus:ring-green-200",
        className,
      ].join(" ")}
    />
  );
}
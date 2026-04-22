import { InputHTMLAttributes } from "react";

export function Input({
  className = "",
  ...props
}: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={[
        "w-full app-input px-3 py-2 text-sm",
        className,
      ].join(" ")}
    />
  );
}
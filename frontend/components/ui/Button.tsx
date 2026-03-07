import { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";

const styles: Record<Variant, string> = {
  primary:
    "bg-green-500 text-white hover:bg-green-600 active:bg-green-700",
  secondary:
    "bg-blue-500 text-white hover:bg-blue-600 active:bg-blue-700",
  ghost:
    "bg-slate-100 text-slate-900 hover:bg-slate-200 active:bg-slate-300",
  danger:
    "bg-pink-500 text-white hover:bg-pink-600 active:bg-pink-700",
};

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      {...props}
      className={[
        "rounded-xl px-4 py-2 text-sm font-medium transition",
        "disabled:opacity-50 disabled:cursor-not-allowed",
        styles[variant],
        className,
      ].join(" ")}
    />
  );
}
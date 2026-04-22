import { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";

const styles: Record<Variant, string> = {
  primary:
    "app-button-primary",
  secondary:
    "app-button-secondary",
  ghost:
    "bg-white/70 text-[color:var(--text-main)] border border-[color:var(--border-soft)] hover:bg-white/90",
  danger:
    "border text-[color:#7a4551] hover:opacity-90",
};

export function Button({
  variant = "primary",
  className = "",
  style,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  const dangerStyle =
    variant === "danger"
      ? {
          background: "linear-gradient(135deg, #ffe6ec 0%, #fff1d4 100%)",
          borderColor: "var(--border-soft)",
          ...(style ?? {}),
        }
      : style;

  return (
    <button
      {...props}
      style={dangerStyle}
      className={[
        "rounded-xl px-4 py-2 text-sm font-medium transition",
        "disabled:opacity-50 disabled:cursor-not-allowed",
        styles[variant],
        className,
      ].join(" ")}
    />
  );
}
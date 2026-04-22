import { ReactNode } from "react";

export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={[
        "app-panel rounded-3xl p-6 transition",
        className,
      ].join(" ")}
    >
      {children}
    </div>
  );
}

export function CardHeader({
  title,
  subtitle,
  right,
}: {
  title: string;
  subtitle?: string;
  right?: ReactNode;
}) {
  return (
    <div className="mb-5 flex justify-between gap-4">
      <div>
        <h2 className="text-lg font-semibold" style={{ color: "var(--text-main)" }}>
          {title}
        </h2>
        {subtitle && (
          <p className="text-sm mt-1" style={{ color: "var(--text-soft)" }}>
            {subtitle}
          </p>
        )}
      </div>
      {right}
    </div>
  );
}
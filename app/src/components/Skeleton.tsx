"use client";

export type SkeletonVariant = "text" | "circle" | "rect";

interface SkeletonProps {
  variant?: SkeletonVariant;
  width?: string | number;
  height?: string | number;
  className?: string;
  style?: React.CSSProperties;
}

export function Skeleton({
  variant = "text",
  width,
  height,
  className = "",
  style = {},
}: SkeletonProps) {
  const variantClasses: Record<SkeletonVariant, string> = {
    text: "rounded-[var(--radius-sm)] h-4",
    circle: "rounded-full",
    rect: "rounded-[var(--radius-md)]",
  };

  const computedStyle: React.CSSProperties = {
    ...style,
    ...(width !== undefined && {
      width: typeof width === "number" ? `${width}px` : width,
    }),
    ...(height !== undefined && {
      height: typeof height === "number" ? `${height}px` : height,
    }),
  };

  return (
    <div
      className={`animate-skeleton bg-[var(--color-gray-200)] ${variantClasses[variant]} ${className}`.trim()}
      style={computedStyle}
      aria-hidden="true"
    />
  );
}

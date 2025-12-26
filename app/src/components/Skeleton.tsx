import "../styles/Skeleton.css";

export type SkeletonVariant = "text" | "circle" | "rect";

interface SkeletonProps {
  variant?: SkeletonVariant;
  width?: string | number;
  height?: string | number;
  className?: string;
  style?: React.CSSProperties;
}

/**
 * Reusable Skeleton component with pulse animation.
 * Use for loading states to show content placeholders.
 *
 * @param variant - "text" (default, rounded), "circle" (circular), "rect" (rectangular)
 * @param width - Width of the skeleton (CSS value or number for px)
 * @param height - Height of the skeleton (CSS value or number for px)
 * @param className - Additional CSS classes
 * @param style - Additional inline styles
 */
export function Skeleton({
  variant = "text",
  width,
  height,
  className = "",
  style = {},
}: SkeletonProps) {
  const variantClass = `skeleton-${variant}`;

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
      className={`skeleton ${variantClass} ${className}`.trim()}
      style={computedStyle}
      aria-hidden="true"
    />
  );
}

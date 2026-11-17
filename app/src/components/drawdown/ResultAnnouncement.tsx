/**
 * The headline as the API last answered it, for screen readers. The visible
 * headline follows every key typed into a figure; this changes only when an
 * answer lands, so a reader hears the settled figure once (WCAG 2.2 SC 4.1.3).
 */
export function ResultAnnouncement({ text }: { text: string }) {
  return (
    <p role="status" className="sr-only">
      {text}
    </p>
  );
}

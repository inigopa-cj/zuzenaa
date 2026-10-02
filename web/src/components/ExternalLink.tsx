import type { ReactNode } from 'react'

/** Anchor to an external site (opens in a new tab) with an outbound icon. */
export function ExternalLink({
  href,
  children,
  className,
  title,
}: {
  href: string
  children: ReactNode
  className?: string
  title?: string
}) {
  return (
    <a className={className} href={href} target="_blank" rel="noreferrer" title={title}>
      {children}
      <svg
        className="ext-icon"
        width="12"
        height="12"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="M14 4h6v6M20 4l-9 9M19 14v5a1 1 0 01-1 1H5a1 1 0 01-1-1V6a1 1 0 011-1h5" />
      </svg>
    </a>
  )
}

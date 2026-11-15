"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [["/", "Brief"], ["/portfolio", "Portfolio"], ["/alerts", "Alerts"]] as const;

export default function Tabs() {
  const path = usePathname();
  return (
    <nav className="fixed inset-x-0 bottom-0 z-10 border-t border-line bg-ink/95 backdrop-blur" aria-label="Main">
      <ul className="mx-auto grid max-w-xl grid-cols-3 pb-[env(safe-area-inset-bottom)]">
        {TABS.map(([href, label]) => {
          const on = href === "/" ? path === "/" : path.startsWith(href);
          return (
            <li key={href}>
              <Link href={href} aria-current={on ? "page" : undefined}
                className={`block py-3 text-center text-sm ${on ? "font-semibold text-text shadow-[inset_0_2px_0_var(--color-crit)]" : "text-dim"}`}>
                {label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

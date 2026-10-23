"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { ThemeToggle } from "./theme-toggle";

const primaryNavigation = [
  { href: "/recommendations", label: "Next Right Thing" },
  { href: "/dashboard", label: "Goals" },
  { href: "/content-sources", label: "Content Sources" },
  { href: "/content-items", label: "Content Items" },
];

type AuthenticatedNavigationProps = {
  onSignOut: () => void;
};

export function AuthenticatedNavigation({ onSignOut }: AuthenticatedNavigationProps) {
  const pathname = usePathname();

  return (
    <div className="authenticated-navigation">
      <nav aria-label="Primary navigation" className="primary-navigation">
        {primaryNavigation.map((item) => {
          const isActive = pathname === item.href;

          return (
            <Link
              aria-current={isActive ? "page" : undefined}
              className={`button navigation-link${isActive ? " primary" : ""}`}
              href={item.href}
              key={item.href}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
      <ThemeToggle />
      <button className="button sign-out-button" type="button" onClick={onSignOut}>
        Sign Out
      </button>
    </div>
  );
}

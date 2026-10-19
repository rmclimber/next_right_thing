"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getCurrentUser, signOut } from "aws-amplify/auth";

import { configureAmplify } from "@/lib/amplify-client";
import { ContentItem, listContentItems } from "@/lib/content-items-api";

type ContentItemsState =
  | { status: "loading" }
  | { status: "ready"; items: ContentItem[] }
  | { status: "error" };

type ContentItemFilter = "all" | "snoozed" | "completed" | "archived";

function formatTimestamp(timestamp: string): string {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(timestamp));
}

function summaryAsPlainText(summary: string | null): string | null {
  if (!summary) {
    return null;
  }

  const normalized = summary.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
  return normalized || null;
}

function isCurrentlySnoozed(item: ContentItem, now: Date): boolean {
  return item.status === "active" && item.snoozed_until !== null && new Date(item.snoozed_until) > now;
}

function filterItems(items: ContentItem[], filter: ContentItemFilter, now: Date): ContentItem[] {
  if (filter === "all") {
    return items;
  }

  return items.filter((item) => filter === "snoozed" ? isCurrentlySnoozed(item, now) : item.status === filter);
}

function emptyMessage(filter: ContentItemFilter): string {
  switch (filter) {
    case "snoozed": return "No snoozed items.";
    case "completed": return "No completed items yet.";
    case "archived": return "No archived items.";
    default: return "";
  }
}

export default function ContentItemsPage() {
  const router = useRouter();
  const [state, setState] = useState<ContentItemsState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [filter, setFilter] = useState<ContentItemFilter>("all");

  useEffect(() => {
    let active = true;

    async function loadContentItems() {
      try {
        configureAmplify();
        await getCurrentUser();
        const response = await listContentItems();

        if (active) {
          setState({ status: "ready", items: response.content_items });
        }
      } catch (caught) {
        if (!active) {
          return;
        }

        if (caught instanceof Error && caught.name === "UserUnAuthenticatedException") {
          router.replace("/");
          return;
        }

        setState({ status: "error" });
      }
    }

    loadContentItems();

    return () => {
      active = false;
    };
  }, [reloadKey, router]);

  async function handleSignOut() {
    configureAmplify();
    await signOut();
    router.replace("/");
  }

  function retryLoading() {
    setState({ status: "loading" });
    setReloadKey((current) => current + 1);
  }

  return (
    <main className="page-shell">
      <section className="panel dashboard-panel">
        <div className="header-row">
          <div>
            <p className="eyebrow">Next Right Thing</p>
            <h1>Content Items</h1>
          </div>
          <div className="header-actions">
            <Link className="button primary" href="/recommendations">
              Next Right Thing
            </Link>
            <Link className="button" href="/dashboard">
              Goals
            </Link>
            <Link className="button" href="/content-sources">
              Content Sources
            </Link>
            <button className="button" type="button" onClick={handleSignOut}>
              Sign Out
            </button>
          </div>
        </div>

        {state.status === "loading" ? <p>Loading Content Items...</p> : null}

        {state.status === "error" ? (
          <div className="error-state">
            <p className="error compact-error">Content Items could not be loaded. Please try again.</p>
            <button className="button" type="button" onClick={retryLoading}>
              Retry
            </button>
          </div>
        ) : null}

        {state.status === "ready" ? (() => {
          const visibleItems = filterItems(state.items, filter, new Date());

          return <section className="content-items-section" aria-label="Content Items list">
            <div className="section-heading">
              <h2>Recently discovered</h2>
              <p>{state.items.length} total</p>
            </div>

            <div className="content-item-filters" aria-label="Filter content items">
              {(["all", "snoozed", "completed", "archived"] as const).map((option) => (
                <button
                  aria-pressed={filter === option}
                  className={`filter-button${filter === option ? " selected" : ""}`}
                  key={option}
                  onClick={() => setFilter(option)}
                  type="button"
                >
                  {option.charAt(0).toUpperCase() + option.slice(1)}
                </button>
              ))}
            </div>

            {state.items.length === 0 ? (
              <div className="empty-state">
                <h3>No Content Items yet</h3>
                <p>Active content sources will appear here after NRT discovers new items.</p>
                <Link className="button empty-state-action" href="/content-sources">
                  View Content Sources
                </Link>
              </div>
            ) : visibleItems.length === 0 ? (
              <div className="empty-state">
                <p>{emptyMessage(filter)}</p>
              </div>
            ) : (
              <ul className="content-items-list">
                {visibleItems.map((item) => (
                  <ContentItemCard item={item} key={item.id} />
                ))}
              </ul>
            )}
          </section>;
        })() : null}
      </section>
    </main>
  );
}

function ContentItemCard({ item }: { item: ContentItem }) {
  const summary = summaryAsPlainText(item.summary);
  const stateLabel = isCurrentlySnoozed(item, new Date())
    ? `Snoozed until ${formatTimestamp(item.snoozed_until!)}`
    : item.status === "completed" && item.completed_at
      ? `Completed ${formatTimestamp(item.completed_at)}`
      : item.status === "completed"
        ? "Completed"
        : item.status === "archived"
          ? "Archived"
          : null;

  return (
    <li className="content-item">
      <h3>
        <a href={item.url} target="_blank" rel="noopener noreferrer">
          {item.title}
        </a>
      </h3>
      {summary ? <p className="content-item-summary">{summary}</p> : null}
      <div className="content-item-meta">
        {item.published_at ? <span>Published {formatTimestamp(item.published_at)}</span> : null}
        <span>Discovered {formatTimestamp(item.discovered_at)}</span>
        {stateLabel ? <span className={`content-item-state state-${item.status}`}>{stateLabel}</span> : null}
      </div>
      <a className="content-item-link" href={item.url} target="_blank" rel="noopener noreferrer">
        Open article
      </a>
    </li>
  );
}

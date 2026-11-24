"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getCurrentUser, signOut } from "aws-amplify/auth";

import { configureAmplify } from "@/lib/amplify-client";
import { AuthenticatedNavigation } from "@/components/authenticated-navigation";
import { ContentItem, ContentItemFilter, listContentItems } from "@/lib/content-items-api";

type ContentItemsState =
  | { status: "loading" }
  | { status: "ready"; items: ContentItem[]; nextCursor: string | null; page: number }
  | { status: "error"; message: string };

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

  const [cursors, setCursors] = useState<(string | null)[]>([null]);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(50);
  const requestCursor = cursors[page];

  useEffect(() => {
    let active = true;

    async function loadContentItems() {
      try {
        configureAmplify();
        await getCurrentUser();
        const response = await listContentItems({ filter, limit: pageSize, cursor: requestCursor });

        if (active) {
          setCursors((current) => {
            if (response.next_cursor === null) return current.slice(0, page + 1);
            if (current[page + 1] === response.next_cursor) return current;
            return [...current.slice(0, page + 1), response.next_cursor];
          });
          setState({ status: "ready", items: response.content_items, nextCursor: response.next_cursor, page });
        }
      } catch (caught) {
        if (!active) {
          return;
        }

        if (caught instanceof Error && caught.name === "UserUnAuthenticatedException") {
          router.replace("/");
          return;
        }

        setState({ status: "error", message: caught instanceof Error ? caught.message : "Please try again." });
      }
    }

    loadContentItems();

    return () => {
      active = false;
    };
  }, [reloadKey, router, filter, requestCursor, page, pageSize]);

  async function handleSignOut() {
    configureAmplify();
    await signOut();
    router.replace("/");
  }

  function retryLoading() {
    setState({ status: "loading" });
    setReloadKey((current) => current + 1);
  }

  function goToPage(target: number) {
    if (state.status !== "ready" || target === page || target < 0 || target >= cursors.length) return;
    setState({ status: "loading" });
    setPage(target);
  }

  function paginationControls(position: "top" | "bottom") {
    return (
      <nav className="content-items-pagination" aria-label={`Pagination ${position}`}>
        <label className="content-items-page-size">
          Items per page
          <select value={pageSize} onChange={(event) => {
            setState({ status: "loading" });
            setPageSize(Number(event.target.value));
            setCursors([null]);
            setPage(0);
          }}>
            {[10, 25, 50, 100].map((size) => <option key={size} value={size}>{size}</option>)}
          </select>
        </label>
        <button className="button pagination-icon-button" type="button" aria-label="Previous" title="Previous page"
          disabled={state.status !== "ready" || page === 0}
          onClick={() => goToPage(page - 1)}>
          <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="m15 6-6 6 6 6" /></svg>
        </button>
        <div className="pagination-pages" role="group" aria-label="Go to page">
          <span>Go to page</span>
          {cursors.map((_, index) => (
            <button key={index} type="button" className={`filter-button pagination-page${state.status === "ready" && state.page === index ? " selected" : ""}`}
              aria-label={`Go to page ${index + 1}`}
              aria-current={state.status === "ready" && state.page === index ? "page" : undefined}
              disabled={state.status !== "ready" || page === index}
              onClick={() => goToPage(index)}>{index + 1}</button>
          ))}
        </div>
        <button className="button pagination-icon-button" type="button" aria-label="Next" title="Next page"
          disabled={state.status !== "ready" || state.nextCursor === null}
          onClick={() => goToPage(page + 1)}>
          <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="m9 6 6 6-6 6" /></svg>
        </button>
      </nav>
    );
  }

  return (
    <main className="page-shell">
      <section className="panel dashboard-panel">
        <div className="header-row">
          <div>
            <p className="eyebrow">Next Right Thing</p>
            <h1>Content Items</h1>
            <p className="lede">Browse the professional content discovered from your active Content Sources.</p>
          </div>
          <AuthenticatedNavigation onSignOut={handleSignOut} />
        </div>

        {state.status === "loading" ? <p>Loading Content Items...</p> : null}

        {state.status === "error" ? (
          <div className="error-state">
            <p className="error compact-error">Content Items could not be loaded. {state.message}</p>
            <button className="button" type="button" onClick={retryLoading}>
              Retry
            </button>
          </div>
        ) : null}

        <div className="content-item-filters" aria-label="Filter content items">
          {(["all", "snoozed", "completed", "archived"] as const).map((option) => (
            <button aria-pressed={filter === option} className={`filter-button${filter === option ? " selected" : ""}`}
              key={option} type="button" onClick={() => {
                if (option === filter) return;
                setState({ status: "loading" });
                setFilter(option);
                setCursors([null]);
                setPage(0);
              }}>{option.charAt(0).toUpperCase() + option.slice(1)}</button>
          ))}
        </div>
        {paginationControls("top")}
        {state.status === "ready" ? (
          <section className="content-items-section" aria-label="Content Items list">
            <div className="section-heading">
              <h2>Recently discovered</h2>
              <p>Showing {state.items.length} items · Page {state.page + 1}</p>
            </div>
            {state.items.length === 0 && filter === "all" && page === 0 ? (
              <div className="empty-state">
                <h3>No Content Items yet</h3>
                <p>Active content sources will appear here after NRT discovers new items.</p>
                <Link className="button empty-state-action" href="/content-sources">
                  View Content Sources
                </Link>
              </div>
            ) : state.items.length === 0 ? (
              <div className="empty-state">
                <p>{page > 0 ? "No items on this page. Go back or reload to restart." : emptyMessage(filter)}</p>
              </div>
            ) : (
              <ul className="content-items-list">
                {state.items.map((item) => (
                  <ContentItemCard item={item} key={item.id} />
                ))}
              </ul>
            )}
          </section>
        ) : null}
        {paginationControls("bottom")}
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
      {item.content_source ? (
        <a className="content-item-source" href={item.content_source.url} target="_blank" rel="noopener noreferrer">
          {item.content_source.name}
        </a>
      ) : null}
      {summary ? <p className="content-item-summary">{summary}</p> : null}
      <div className="content-item-meta">
        {item.content_type === "podcast_episode" ? <span className="status-pill">Podcast episode</span> : null}
        {item.content_type === "podcast_episode" ? <span>{item.duration_minutes === null ? "Duration unknown" : `${item.duration_minutes} min`}</span> : null}
        {item.published_at ? <span>Published {formatTimestamp(item.published_at)}</span> : null}
        <span>Discovered {formatTimestamp(item.discovered_at)}</span>
        {stateLabel ? <span className={`status-pill content-item-state state-${item.status}`}>{stateLabel}</span> : null}
      </div>
      <a className="content-item-link" href={item.url} target="_blank" rel="noopener noreferrer">
        {item.content_type === "podcast_episode" ? "Listen externally" : "Open article"}
      </a>
    </li>
  );
}

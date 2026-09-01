"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { getCurrentUser, signOut } from "aws-amplify/auth";

import { ApiError } from "@/lib/authenticated-api";
import { configureAmplify } from "@/lib/amplify-client";
import {
  ContentSource,
  ContentSourceStatus,
  createContentSource,
  listContentSources,
  updateContentSource,
} from "@/lib/content-sources-api";

type ContentSourcesState =
  | { status: "loading" }
  | { status: "ready"; sources: ContentSource[] }
  | { status: "error"; message: string };

type ContentSourceFormValues = {
  name: string;
  url: string;
  status: ContentSourceStatus;
};

const contentSourceStatuses: ContentSourceStatus[] = ["active", "paused", "archived"];

const sourceTypeLabels: Record<ContentSource["source_type"], string> = {
  rss: "RSS",
};

const statusLabels: Record<ContentSourceStatus, string> = {
  active: "Active",
  paused: "Paused",
  archived: "Archived",
};

function valuesFromSource(source: ContentSource): ContentSourceFormValues {
  return {
    name: source.name,
    url: source.url,
    status: source.status,
  };
}

function toCreatePayload(values: ContentSourceFormValues) {
  return {
    name: values.name.trim(),
    url: values.url.trim(),
  };
}

function toUpdatePayload(values: ContentSourceFormValues) {
  return {
    ...toCreatePayload(values),
    status: values.status,
  };
}

function friendlyError(action: "load" | "create" | "update"): string {
  if (action === "load") {
    return "Content Sources could not be loaded. Please try again.";
  }

  if (action === "create") {
    return "Content Source could not be created. Please check the form and try again.";
  }

  return "Content Source could not be updated. Please check the form and try again.";
}

function errorFor(action: "create" | "update", caught: unknown): string {
  if (caught instanceof ApiError && caught.status === 409) {
    return "You already have a content source with this URL.";
  }

  return friendlyError(action);
}

export default function ContentSourcesPage() {
  const router = useRouter();
  const [state, setState] = useState<ContentSourcesState>({ status: "loading" });
  const [createValues, setCreateValues] = useState<ContentSourceFormValues>({
    name: "",
    url: "",
    status: "active",
  });
  const [createError, setCreateError] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [editingSourceId, setEditingSourceId] = useState<string | null>(null);
  const [editValues, setEditValues] = useState<ContentSourceFormValues | null>(null);
  const [updateError, setUpdateError] = useState<string | null>(null);
  const [savingSourceId, setSavingSourceId] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function loadContentSources() {
      try {
        configureAmplify();
        await getCurrentUser();
        const response = await listContentSources();

        if (active) {
          setState({ status: "ready", sources: response.content_sources });
        }
      } catch (caught) {
        if (!active) {
          return;
        }

        if (caught instanceof Error && caught.name === "UserUnAuthenticatedException") {
          router.replace("/");
          return;
        }

        setState({
          status: "error",
          message: friendlyError("load"),
        });
      }
    }

    loadContentSources();

    return () => {
      active = false;
    };
  }, [router]);

  async function handleSignOut() {
    configureAmplify();
    await signOut();
    router.replace("/");
  }

  async function handleCreateSource(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreateError(null);

    if (!createValues.name.trim()) {
      setCreateError("Name is required.");
      return;
    }

    if (!createValues.url.trim()) {
      setCreateError("URL is required.");
      return;
    }

    try {
      setIsCreating(true);
      const source = await createContentSource(toCreatePayload(createValues));

      setState((current) =>
        current.status === "ready"
          ? { status: "ready", sources: [source, ...current.sources] }
          : current,
      );
      setCreateValues({
        name: "",
        url: "",
        status: "active",
      });
    } catch (caught) {
      setCreateError(errorFor("create", caught));
    } finally {
      setIsCreating(false);
    }
  }

  function beginEditing(source: ContentSource) {
    setUpdateError(null);
    setEditingSourceId(source.id);
    setEditValues(valuesFromSource(source));
  }

  function cancelEditing() {
    setUpdateError(null);
    setEditingSourceId(null);
    setEditValues(null);
  }

  async function handleUpdateSource(
    sourceId: string,
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    setUpdateError(null);

    if (!editValues?.name.trim()) {
      setUpdateError("Name is required.");
      return;
    }

    if (!editValues.url.trim()) {
      setUpdateError("URL is required.");
      return;
    }

    try {
      setSavingSourceId(sourceId);
      const source = await updateContentSource(sourceId, toUpdatePayload(editValues));

      setState((current) =>
        current.status === "ready"
          ? {
              status: "ready",
              sources: current.sources.map((existing) =>
                existing.id === source.id ? source : existing,
              ),
            }
          : current,
      );
      cancelEditing();
    } catch (caught) {
      setUpdateError(errorFor("update", caught));
    } finally {
      setSavingSourceId(null);
    }
  }

  async function handleStatusChange(
    source: ContentSource,
    status: ContentSourceStatus,
  ) {
    setUpdateError(null);

    try {
      setSavingSourceId(source.id);
      const updated = await updateContentSource(source.id, { status });

      setState((current) =>
        current.status === "ready"
          ? {
              status: "ready",
              sources: current.sources.map((existing) =>
                existing.id === updated.id ? updated : existing,
              ),
            }
          : current,
      );
    } catch (caught) {
      setUpdateError(errorFor("update", caught));
    } finally {
      setSavingSourceId(null);
    }
  }

  return (
    <main className="page-shell">
      <section className="panel dashboard-panel">
        <div className="header-row">
          <div>
            <p className="eyebrow">Next Right Thing</p>
            <h1>Content Sources</h1>
          </div>
          <div className="header-actions">
            <Link className="button" href="/dashboard">
              Goals
            </Link>
            <button className="button" type="button" onClick={handleSignOut}>
              Sign Out
            </button>
          </div>
        </div>

        {state.status === "loading" ? <p>Loading Content Sources...</p> : null}

        {state.status === "error" ? <p className="error">{state.message}</p> : null}

        {state.status === "ready" ? (
          <div className="goals-workspace">
            <form className="goal-form create-goal-form" onSubmit={handleCreateSource}>
              <div>
                <h2>Add RSS Source</h2>
                <p className="form-note">Add a professional feed for future recommendations.</p>
              </div>

              <label>
                <span>Name</span>
                <input
                  value={createValues.name}
                  onChange={(event) =>
                    setCreateValues((values) => ({
                      ...values,
                      name: event.target.value,
                    }))
                  }
                  required
                />
              </label>

              <label>
                <span>URL</span>
                <input
                  type="url"
                  value={createValues.url}
                  onChange={(event) =>
                    setCreateValues((values) => ({
                      ...values,
                      url: event.target.value,
                    }))
                  }
                  required
                />
              </label>

              {createError ? <p className="error compact-error">{createError}</p> : null}

              <div className="form-actions">
                <button className="button primary" type="submit" disabled={isCreating}>
                  {isCreating ? "Adding..." : "Add Source"}
                </button>
              </div>
            </form>

            <section className="goals-section" aria-label="Content Sources list">
              <div className="section-heading">
                <h2>Your Content Sources</h2>
                <p>{state.sources.length} total</p>
              </div>

              {updateError ? <p className="error compact-error">{updateError}</p> : null}

              {state.sources.length === 0 ? (
                <div className="empty-state">
                  <h3>No Content Sources yet</h3>
                  <p>Add your first RSS source when you are ready to connect content.</p>
                </div>
              ) : (
                <ul className="goals-list">
                  {state.sources.map((source) => (
                    <li className="goal-item" key={source.id}>
                      {editingSourceId === source.id && editValues ? (
                        <form
                          className="goal-form edit-goal-form"
                          onSubmit={(event) => handleUpdateSource(source.id, event)}
                        >
                          <label>
                            <span>Name</span>
                            <input
                              value={editValues.name}
                              onChange={(event) =>
                                setEditValues((values) =>
                                  values
                                    ? {
                                        ...values,
                                        name: event.target.value,
                                      }
                                    : values,
                                )
                              }
                              required
                            />
                          </label>

                          <label>
                            <span>URL</span>
                            <input
                              type="url"
                              value={editValues.url}
                              onChange={(event) =>
                                setEditValues((values) =>
                                  values
                                    ? {
                                        ...values,
                                        url: event.target.value,
                                      }
                                    : values,
                                )
                              }
                              required
                            />
                          </label>

                          <label>
                            <span>Status</span>
                            <select
                              value={editValues.status}
                              onChange={(event) =>
                                setEditValues((values) =>
                                  values
                                    ? {
                                        ...values,
                                        status: event.target.value as ContentSourceStatus,
                                      }
                                    : values,
                                )
                              }
                            >
                              {contentSourceStatuses.map((status) => (
                                <option key={status} value={status}>
                                  {statusLabels[status]}
                                </option>
                              ))}
                            </select>
                          </label>

                          <div className="form-actions">
                            <button
                              className="button primary"
                              type="submit"
                              disabled={savingSourceId === source.id}
                            >
                              {savingSourceId === source.id ? "Saving..." : "Save"}
                            </button>
                            <button className="button" type="button" onClick={cancelEditing}>
                              Cancel
                            </button>
                          </div>
                        </form>
                      ) : (
                        <>
                          <div className="goal-content">
                            <div className="goal-title-row">
                              <h3>{source.name}</h3>
                              <span className={`status-pill status-${source.status}`}>
                                {statusLabels[source.status]}
                              </span>
                            </div>
                            <p className="source-url">{source.url}</p>
                            <p className="target-date">
                              {sourceTypeLabels[source.source_type]}
                            </p>
                          </div>

                          <div className="goal-actions">
                            <label className="status-control">
                              <span>Status</span>
                              <select
                                value={source.status}
                                onChange={(event) =>
                                  handleStatusChange(
                                    source,
                                    event.target.value as ContentSourceStatus,
                                  )
                                }
                                disabled={savingSourceId === source.id}
                              >
                                {contentSourceStatuses.map((status) => (
                                  <option key={status} value={status}>
                                    {statusLabels[status]}
                                  </option>
                                ))}
                              </select>
                            </label>
                            <button
                              className="button"
                              type="button"
                              onClick={() => beginEditing(source)}
                            >
                              Edit
                            </button>
                          </div>
                        </>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        ) : null}
      </section>
    </main>
  );
}

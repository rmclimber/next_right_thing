"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { getCurrentUser, signOut } from "aws-amplify/auth";

import { configureAmplify } from "@/lib/amplify-client";
import {
  createGoal,
  Goal,
  GoalStatus,
  listGoals,
  updateGoal,
} from "@/lib/goals-api";

type DashboardState =
  | { status: "loading" }
  | { status: "ready"; goals: Goal[] }
  | { status: "error"; message: string };

type GoalFormValues = {
  title: string;
  description: string;
  targetDate: string;
  status: GoalStatus;
};

const goalStatuses: GoalStatus[] = ["active", "paused", "completed", "archived"];

const statusLabels: Record<GoalStatus, string> = {
  active: "Active",
  paused: "Paused",
  completed: "Completed",
  archived: "Archived",
};

function toCreatePayload(values: GoalFormValues) {
  return {
    title: values.title.trim(),
    description: values.description.trim() || null,
    target_date: values.targetDate || null,
  };
}

function toUpdatePayload(values: GoalFormValues) {
  return {
    ...toCreatePayload(values),
    status: values.status,
  };
}

function valuesFromGoal(goal: Goal): GoalFormValues {
  return {
    title: goal.title,
    description: goal.description ?? "",
    targetDate: goal.target_date ?? "",
    status: goal.status,
  };
}

function formatTargetDate(targetDate: string | null): string {
  if (!targetDate) {
    return "No target date";
  }

  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${targetDate}T00:00:00Z`));
}

function friendlyError(action: "load" | "create" | "update"): string {
  if (action === "load") {
    return "Goals could not be loaded. Please try again.";
  }

  if (action === "create") {
    return "Goal could not be created. Please check the form and try again.";
  }

  return "Goal could not be updated. Please check the form and try again.";
}

export default function Dashboard() {
  const router = useRouter();
  const [state, setState] = useState<DashboardState>({ status: "loading" });
  const [createValues, setCreateValues] = useState<GoalFormValues>({
    title: "",
    description: "",
    targetDate: "",
    status: "active",
  });
  const [createError, setCreateError] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [editingGoalId, setEditingGoalId] = useState<string | null>(null);
  const [editValues, setEditValues] = useState<GoalFormValues | null>(null);
  const [updateError, setUpdateError] = useState<string | null>(null);
  const [savingGoalId, setSavingGoalId] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function loadDashboard() {
      try {
        configureAmplify();
        await getCurrentUser();
        const response = await listGoals();

        if (active) {
          setState({ status: "ready", goals: response.goals });
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

    loadDashboard();

    return () => {
      active = false;
    };
  }, [router]);

  async function handleSignOut() {
    configureAmplify();
    await signOut();
    router.replace("/");
  }

  async function handleCreateGoal(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreateError(null);

    if (!createValues.title.trim()) {
      setCreateError("Title is required.");
      return;
    }

    try {
      setIsCreating(true);
      const goal = await createGoal(toCreatePayload(createValues));

      setState((current) =>
        current.status === "ready"
          ? { status: "ready", goals: [goal, ...current.goals] }
          : current,
      );
      setCreateValues({
        title: "",
        description: "",
        targetDate: "",
        status: "active",
      });
    } catch {
      setCreateError(friendlyError("create"));
    } finally {
      setIsCreating(false);
    }
  }

  function beginEditing(goal: Goal) {
    setUpdateError(null);
    setEditingGoalId(goal.id);
    setEditValues(valuesFromGoal(goal));
  }

  function cancelEditing() {
    setUpdateError(null);
    setEditingGoalId(null);
    setEditValues(null);
  }

  async function handleUpdateGoal(goalId: string, event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setUpdateError(null);

    if (!editValues?.title.trim()) {
      setUpdateError("Title is required.");
      return;
    }

    try {
      setSavingGoalId(goalId);
      const goal = await updateGoal(goalId, toUpdatePayload(editValues));

      setState((current) =>
        current.status === "ready"
          ? {
              status: "ready",
              goals: current.goals.map((existing) =>
                existing.id === goal.id ? goal : existing,
              ),
            }
          : current,
      );
      cancelEditing();
    } catch {
      setUpdateError(friendlyError("update"));
    } finally {
      setSavingGoalId(null);
    }
  }

  async function handleStatusChange(goal: Goal, status: GoalStatus) {
    setUpdateError(null);

    try {
      setSavingGoalId(goal.id);
      const updated = await updateGoal(goal.id, { status });

      setState((current) =>
        current.status === "ready"
          ? {
              status: "ready",
              goals: current.goals.map((existing) =>
                existing.id === updated.id ? updated : existing,
              ),
            }
          : current,
      );
    } catch {
      setUpdateError(friendlyError("update"));
    } finally {
      setSavingGoalId(null);
    }
  }

  return (
    <main className="page-shell">
      <section className="panel dashboard-panel">
        <div className="header-row">
          <div>
            <p className="eyebrow">Next Right Thing</p>
            <h1>Goals</h1>
          </div>
          <button className="button" type="button" onClick={handleSignOut}>
            Sign Out
          </button>
        </div>

        {state.status === "loading" ? <p>Loading Goals...</p> : null}

        {state.status === "error" ? <p className="error">{state.message}</p> : null}

        {state.status === "ready" ? (
          <div className="goals-workspace">
            <form className="goal-form create-goal-form" onSubmit={handleCreateGoal}>
              <div>
                <h2>Create Goal</h2>
                <p className="form-note">Add a professional objective to guide recommendations.</p>
              </div>

              <label>
                <span>Title</span>
                <input
                  value={createValues.title}
                  onChange={(event) =>
                    setCreateValues((values) => ({
                      ...values,
                      title: event.target.value,
                    }))
                  }
                  required
                />
              </label>

              <label>
                <span>Description</span>
                <textarea
                  rows={3}
                  value={createValues.description}
                  onChange={(event) =>
                    setCreateValues((values) => ({
                      ...values,
                      description: event.target.value,
                    }))
                  }
                />
              </label>

              <label>
                <span>Target Date</span>
                <input
                  type="date"
                  value={createValues.targetDate}
                  onChange={(event) =>
                    setCreateValues((values) => ({
                      ...values,
                      targetDate: event.target.value,
                    }))
                  }
                />
              </label>

              {createError ? <p className="error compact-error">{createError}</p> : null}

              <div className="form-actions">
                <button className="button primary" type="submit" disabled={isCreating}>
                  {isCreating ? "Creating..." : "Create Goal"}
                </button>
              </div>
            </form>

            <section className="goals-section" aria-label="Goals list">
              <div className="section-heading">
                <h2>Your Goals</h2>
                <p>{state.goals.length} total</p>
              </div>

              {updateError ? <p className="error compact-error">{updateError}</p> : null}

              {state.goals.length === 0 ? (
                <div className="empty-state">
                  <h3>No Goals yet</h3>
                  <p>Create your first Goal to start shaping future recommendations.</p>
                </div>
              ) : (
                <ul className="goals-list">
                  {state.goals.map((goal) => (
                    <li className="goal-item" key={goal.id}>
                      {editingGoalId === goal.id && editValues ? (
                        <form
                          className="goal-form edit-goal-form"
                          onSubmit={(event) => handleUpdateGoal(goal.id, event)}
                        >
                          <label>
                            <span>Title</span>
                            <input
                              value={editValues.title}
                              onChange={(event) =>
                                setEditValues((values) =>
                                  values
                                    ? {
                                        ...values,
                                        title: event.target.value,
                                      }
                                    : values,
                                )
                              }
                              required
                            />
                          </label>

                          <label>
                            <span>Description</span>
                            <textarea
                              rows={3}
                              value={editValues.description}
                              onChange={(event) =>
                                setEditValues((values) =>
                                  values
                                    ? {
                                        ...values,
                                        description: event.target.value,
                                      }
                                    : values,
                                )
                              }
                            />
                          </label>

                          <div className="form-grid">
                            <label>
                              <span>Target Date</span>
                              <input
                                type="date"
                                value={editValues.targetDate}
                                onChange={(event) =>
                                  setEditValues((values) =>
                                    values
                                      ? {
                                          ...values,
                                          targetDate: event.target.value,
                                        }
                                      : values,
                                  )
                                }
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
                                          status: event.target.value as GoalStatus,
                                        }
                                      : values,
                                  )
                                }
                              >
                                {goalStatuses.map((status) => (
                                  <option key={status} value={status}>
                                    {statusLabels[status]}
                                  </option>
                                ))}
                              </select>
                            </label>
                          </div>

                          <div className="form-actions">
                            <button
                              className="button primary"
                              type="submit"
                              disabled={savingGoalId === goal.id}
                            >
                              {savingGoalId === goal.id ? "Saving..." : "Save"}
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
                              <h3>{goal.title}</h3>
                              <span className={`status-pill status-${goal.status}`}>
                                {statusLabels[goal.status]}
                              </span>
                            </div>
                            {goal.description ? <p>{goal.description}</p> : null}
                            <p className="target-date">{formatTargetDate(goal.target_date)}</p>
                          </div>

                          <div className="goal-actions">
                            <label className="status-control">
                              <span>Status</span>
                              <select
                                value={goal.status}
                                onChange={(event) =>
                                  handleStatusChange(goal, event.target.value as GoalStatus)
                                }
                                disabled={savingGoalId === goal.id}
                              >
                                {goalStatuses.map((status) => (
                                  <option key={status} value={status}>
                                    {statusLabels[status]}
                                  </option>
                                ))}
                              </select>
                            </label>
                            <button
                              className="button"
                              type="button"
                              onClick={() => beginEditing(goal)}
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

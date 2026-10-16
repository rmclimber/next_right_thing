"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { getCurrentUser, signOut } from "aws-amplify/auth";

import { configureAmplify } from "@/lib/amplify-client";
import { applyContentItemAction, ContentItemAction, getNextRecommendation, Recommendation } from "@/lib/recommendations-api";

const presetDurations = [5, 15, 30, 60];

function durationError(value: string): string | null {
  if (!/^\d+$/.test(value)) {
    return "Enter a whole number of minutes.";
  }

  const minutes = Number(value);

  if (minutes < 1 || minutes > 240) {
    return "Available time must be between 1 and 240 minutes.";
  }

  return null;
}

function summaryAsPlainText(summary: string | null): string | null {
  if (!summary) {
    return null;
  }

  const normalized = summary.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
  return normalized || null;
}

export default function RecommendationsPage() {
  const router = useRouter();
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [availableMinutes, setAvailableMinutes] = useState("15");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [recommendation, setRecommendation] = useState<Recommendation | null | undefined>(
    undefined,
  );
  const [requestError, setRequestError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [isRequesting, setIsRequesting] = useState(false);
  const [isApplyingAction, setIsApplyingAction] = useState(false);

  useEffect(() => {
    let active = true;

    async function checkAuthentication() {
      try {
        configureAmplify();
        await getCurrentUser();
        if (active) {
          setIsAuthenticated(true);
        }
      } catch (caught) {
        if (caught instanceof Error && caught.name === "UserUnAuthenticatedException") {
          router.replace("/");
        }
      }
    }

    checkAuthentication();

    return () => {
      active = false;
    };
  }, [router]);

  async function handleSignOut() {
    configureAmplify();
    await signOut();
    router.replace("/");
  }

  function choosePreset(minutes: number) {
    setAvailableMinutes(String(minutes));
    setValidationError(null);
  }

  async function loadRecommendation() {
    if (isRequesting) {
      return;
    }

    const error = durationError(availableMinutes);
    setValidationError(error);
    setRequestError(null);

    if (error) {
      return;
    }

    try {
      setIsRequesting(true);
      const response = await getNextRecommendation(Number(availableMinutes));
      setRecommendation(response.recommendation);
    } catch {
      setRequestError("A recommendation could not be loaded. Please try again.");
    } finally {
      setIsRequesting(false);
    }
  }

  function requestRecommendation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void loadRecommendation();
  }

  async function applyAction(action: ContentItemAction) {
    if (!recommendation || isApplyingAction) return;
    setActionError(null);
    try {
      setIsApplyingAction(true);
      await applyContentItemAction(recommendation.content_item.id, action, recommendation.recommendation_event_id);
      await loadRecommendation();
    } catch {
      setActionError("That action could not be saved. Please try again.");
    } finally {
      setIsApplyingAction(false);
    }
  }

  return (
    <main className="page-shell">
      <section className="panel dashboard-panel">
        <div className="header-row">
          <div>
            <p className="eyebrow">Next Right Thing</p>
            <h1>What should you do next?</h1>
          </div>
          <div className="header-actions">
            <Link className="button" href="/dashboard">Goals</Link>
            <Link className="button" href="/content-sources">Content Sources</Link>
            <Link className="button" href="/content-items">Content Items</Link>
            <button className="button" type="button" onClick={handleSignOut}>Sign Out</button>
          </div>
        </div>

        {isAuthenticated ? (
          <form className="recommendation-form" onSubmit={requestRecommendation}>
            <fieldset disabled={isRequesting}>
              <legend>How much time do you have?</legend>
              <div className="duration-presets">
                {presetDurations.map((minutes) => (
                  <button
                    className={`button ${availableMinutes === String(minutes) ? "primary" : ""}`}
                    key={minutes}
                    type="button"
                    onClick={() => choosePreset(minutes)}
                  >
                    {minutes} min
                  </button>
                ))}
              </div>
              <label className="custom-duration">
                <span>Custom minutes</span>
                <input
                  aria-describedby={validationError ? "duration-error" : undefined}
                  inputMode="numeric"
                  min="1"
                  max="240"
                  value={availableMinutes}
                  onChange={(event) => {
                    setAvailableMinutes(event.target.value);
                    setValidationError(null);
                  }}
                />
              </label>
            </fieldset>
            {validationError ? <p className="error compact-error" id="duration-error">{validationError}</p> : null}
            <div className="form-actions">
              <button className="button primary" type="submit" disabled={isRequesting}>
                {isRequesting ? "Finding your next thing..." : recommendation ? "Find another" : "Find my next thing"}
              </button>
            </div>
          </form>
        ) : <p>Checking your session...</p>}

        {requestError ? (
          <div className="error-state">
            <p className="error compact-error">{requestError}</p>
            <button className="button" type="button" onClick={() => void loadRecommendation()} disabled={isRequesting}>
              Retry
            </button>
          </div>
        ) : null}

        {recommendation === null ? (
          <div className="empty-state recommendation-result">
            <h2>No recommendation is available right now.</h2>
            <p>Add a Content Source or check your Content Items, then try again.</p>
            <Link className="button empty-state-action" href="/content-sources">View Content Sources</Link>
          </div>
        ) : null}

        {recommendation ? <RecommendationCard recommendation={recommendation} onAction={applyAction} isApplyingAction={isApplyingAction} actionError={actionError} /> : null}
      </section>
    </main>
  );
}

function RecommendationCard({ recommendation, onAction, isApplyingAction, actionError }: { recommendation: Recommendation; onAction: (action: ContentItemAction) => void; isApplyingAction: boolean; actionError: string | null }) {
  const summary = summaryAsPlainText(recommendation.content_item.summary);

  if (recommendation.action_type !== "read_content_item") {
    return <p className="error">This recommendation cannot be displayed yet.</p>;
  }

  return (
    <section className="recommendation-card recommendation-result" aria-label="Your recommendation">
      <p className="eyebrow">Your next thing</p>
      <h2>{recommendation.content_item.title}</h2>
      <p className="recommendation-duration">About {recommendation.estimated_duration_minutes} min</p>
      <p className="recommendation-reason">{recommendation.reason}</p>
      {summary ? <p className="content-item-summary">{summary}</p> : null}
      {actionError ? <p className="error compact-error">{actionError}</p> : null}
      <div className="form-actions">
        <a className="button primary" href={recommendation.content_item.url} target="_blank" rel="noopener noreferrer">Open</a>
        <button className="button" type="button" disabled={isApplyingAction} onClick={() => onAction("complete")}>{isApplyingAction ? "Saving..." : "Complete"}</button>
        <button className="button" type="button" disabled={isApplyingAction} onClick={() => onAction("snooze")}>Snooze</button>
        <button className="button" type="button" disabled={isApplyingAction} onClick={() => onAction("archive")}>Archive</button>
      </div>
    </section>
  );
}

"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getCurrentUser, signInWithRedirect, signOut } from "aws-amplify/auth";

import { configureAmplify } from "@/lib/amplify-client";

type AuthState = "checking" | "signed-in" | "signed-out";

export default function Home() {
  const [authState, setAuthState] = useState<AuthState>("checking");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    configureAmplify();

    getCurrentUser()
      .then(() => setAuthState("signed-in"))
      .catch(() => setAuthState("signed-out"));
  }, []);

  async function signIn() {
    setError(null);

    try {
      configureAmplify();
      await signInWithRedirect();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Sign in failed.");
    }
  }

  async function handleSignOut() {
    setError(null);

    try {
      configureAmplify();
      await signOut();
      setAuthState("signed-out");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Sign out failed.");
    }
  }

  return (
    <main className="page-shell">
      <section className="panel">
        <p className="eyebrow">Next Right Thing</p>
        <h1>Authentication check</h1>
        <p className="lede">
          Sign in with Cognito to verify the hosted UI, local session, protected
          dashboard, and authenticated API call.
        </p>

        <div className="actions">
          {authState === "signed-in" ? (
            <>
              <Link className="button primary" href="/dashboard">
                Dashboard
              </Link>
              <button className="button" type="button" onClick={handleSignOut}>
                Sign Out
              </button>
            </>
          ) : (
            <button
              className="button primary"
              type="button"
              onClick={signIn}
              disabled={authState === "checking"}
            >
              Sign In
            </button>
          )}
        </div>

        {error ? <p className="error">{error}</p> : null}
      </section>
    </main>
  );
}

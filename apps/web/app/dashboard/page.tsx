"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { fetchAuthSession, getCurrentUser, signOut } from "aws-amplify/auth";

import { configureAmplify } from "@/lib/amplify-client";
import { getPublicConfig } from "@/lib/config";

type MeResponse = {
  sub: string | null;
};

type DashboardState =
  | { status: "loading" }
  | { status: "ready"; me: MeResponse }
  | { status: "error"; message: string };

export default function Dashboard() {
  const router = useRouter();
  const [state, setState] = useState<DashboardState>({ status: "loading" });

  useEffect(() => {
    let active = true;

    async function loadIdentity() {
      try {
        configureAmplify();
        await getCurrentUser();

        const session = await fetchAuthSession();
        const accessToken = session.tokens?.accessToken?.toString();

        if (!accessToken) {
          throw new Error("No access token was found for the current session.");
        }

        const { apiBaseUrl } = getPublicConfig();
        const response = await fetch(`${apiBaseUrl}/me`, {
          headers: {
            Authorization: `Bearer ${accessToken}`,
          },
        });

        if (!response.ok) {
          throw new Error(`GET /me failed with status ${response.status}.`);
        }

        const me = (await response.json()) as MeResponse;

        if (active) {
          setState({ status: "ready", me });
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
          message: caught instanceof Error ? caught.message : "Dashboard failed to load.",
        });
      }
    }

    loadIdentity();

    return () => {
      active = false;
    };
  }, [router]);

  async function handleSignOut() {
    configureAmplify();
    await signOut();
    router.replace("/");
  }

  return (
    <main className="page-shell">
      <section className="panel">
        <div className="header-row">
          <div>
            <p className="eyebrow">Protected</p>
            <h1>Dashboard</h1>
          </div>
          <button className="button" type="button" onClick={handleSignOut}>
            Sign Out
          </button>
        </div>

        {state.status === "loading" ? <p>Loading authenticated identity...</p> : null}

        {state.status === "error" ? <p className="error">{state.message}</p> : null}

        {state.status === "ready" ? (
          <dl className="identity-list">
            <div>
              <dt>Sub</dt>
              <dd>{state.me.sub ?? "Not returned"}</dd>
            </div>
          </dl>
        ) : null}
      </section>
    </main>
  );
}

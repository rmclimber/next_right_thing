export type PublicConfig = {
  region: string;
  userPoolId: string;
  userPoolClientId: string;
  cognitoDomain: string;
  redirectSignIn: string;
  redirectSignOut: string;
  apiBaseUrl: string;
};

function requireEnv(name: string, value: string | undefined): string {

  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }

  return value;
}

function normalizeCognitoDomain(domain: string): string {
  return domain.replace(/^https?:\/\//, "").replace(/\/$/, "");
}

function normalizeApiBaseUrl(url: string): string {
  return url.replace(/\/$/, "");
}

export function getPublicConfig(): PublicConfig {
  return {
    region: requireEnv(
      "NEXT_PUBLIC_AWS_REGION",
      process.env.NEXT_PUBLIC_AWS_REGION,
    ),
    userPoolId: requireEnv(
      "NEXT_PUBLIC_COGNITO_USER_POOL_ID",
      process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID,
    ),
    userPoolClientId: requireEnv(
      "NEXT_PUBLIC_COGNITO_USER_POOL_CLIENT_ID",
      process.env.NEXT_PUBLIC_COGNITO_USER_POOL_CLIENT_ID,
    ),
    cognitoDomain: normalizeCognitoDomain(
      requireEnv(
        "NEXT_PUBLIC_COGNITO_DOMAIN",
        process.env.NEXT_PUBLIC_COGNITO_DOMAIN,
      ),
    ),
    redirectSignIn: requireEnv(
      "NEXT_PUBLIC_AUTH_REDIRECT_SIGN_IN",
      process.env.NEXT_PUBLIC_AUTH_REDIRECT_SIGN_IN,
    ),
    redirectSignOut: requireEnv(
      "NEXT_PUBLIC_AUTH_REDIRECT_SIGN_OUT",
      process.env.NEXT_PUBLIC_AUTH_REDIRECT_SIGN_OUT,
    ),
    apiBaseUrl: normalizeApiBaseUrl(
      requireEnv("NEXT_PUBLIC_API_BASE_URL", process.env.NEXT_PUBLIC_API_BASE_URL),
    ),
  };
}

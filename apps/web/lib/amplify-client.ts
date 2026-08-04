"use client";

import { Amplify } from "aws-amplify";
import "aws-amplify/auth/enable-oauth-listener";

import { getPublicConfig } from "./config";

let configured = false;

export function configureAmplify(): void {
  if (configured) {
    return;
  }

  const config = getPublicConfig();

  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId: config.userPoolId,
        userPoolClientId: config.userPoolClientId,
        loginWith: {
          oauth: {
            domain: config.cognitoDomain,
            scopes: [
              "openid",
              "email",
              "profile",
              "aws.cognito.signin.user.admin",
            ],
            redirectSignIn: [config.redirectSignIn],
            redirectSignOut: [config.redirectSignOut],
            responseType: "code",
          },
        },
      },
    },
  });

  configured = true;
}

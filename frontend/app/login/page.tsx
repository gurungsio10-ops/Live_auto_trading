import { Suspense } from "react";
import { LoginForm } from "./LoginForm";

export default function LoginPage() {
  const showDevCredentials =
    process.env.APP_ENV === "development" || process.env.NODE_ENV === "development";

  return (
    <div className="flex min-h-dvh min-h-screen items-center justify-center px-4 py-8">
      <Suspense
        fallback={
          <div className="w-full max-w-md rounded-card border border-border bg-surface p-8 text-center text-sm text-secondary">
            Loading sign-in…
          </div>
        }
      >
        <LoginForm showDevCredentials={showDevCredentials} />
      </Suspense>
    </div>
  );
}

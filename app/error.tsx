"use client";

import { useRouter } from "next/navigation";

export default function Error({ error, reset }: { error: Error; reset: () => void }) {
  // The only reporting left is the console. The effect that used to sit here
  // forwarded the error to two window globals injected by the visual builder
  // this site was originally generated in; they existed only inside its editor
  // preview, so on the deployed site both were always undefined and the call
  // shipped a module plus a global type augmentation to do nothing. Wire up a
  // real service here if this site ever needs client error tracking.
  console.error(error);
  const router = useRouter();

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-xl font-semibold tracking-tight text-foreground">
          This page didn&apos;t load
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Something went wrong on our end. You can try refreshing or head back home.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <button
            onClick={() => {
              router.refresh();
              reset();
            }}
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Try again
          </button>
          {/* A hard navigation, not <Link>: this boundary renders when the app
              is already broken, so a full document load is the reliable escape. */}
          {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
          <a
            href="/"
            className="inline-flex items-center justify-center rounded-md border border-input bg-background px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-accent"
          >
            Go home
          </a>
        </div>
      </div>
    </div>
  );
}

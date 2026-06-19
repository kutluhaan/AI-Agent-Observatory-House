import { redirect } from "next/navigation";

// Root / is handled by src/app/page.tsx which redirects here;
// dashboard content lives at (app)/dashboard/page.tsx
export default function AppRootPage() {
  redirect("/dashboard");
}

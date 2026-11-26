import { redirect } from "next/navigation";

// The app starts at the dashboard; the app shell sends logged-out visitors to /login.
export default function Home() {
  redirect("/dashboard");
}

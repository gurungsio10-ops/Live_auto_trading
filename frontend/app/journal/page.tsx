import { redirect } from "next/navigation";

/** Journal maps to the existing audit trail surface. */
export default function JournalPage() {
  redirect("/audit");
}

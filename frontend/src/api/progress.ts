import { apiUrl } from "./client";

export async function fetchMastery(userId: string): Promise<
  {
    concept_id: string;
    score: number;
    repetitions: number;
    easiness_factor: number;
    next_review_date: string | null;
  }[]
> {
  const r = await fetch(apiUrl(`/progress/mastery/${userId}`));
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function fetchDue(userId: string): Promise<
  { concept_id: string; name: string; next_review_date: string }[]
> {
  const r = await fetch(apiUrl(`/progress/due?user_id=${encodeURIComponent(userId)}`));
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

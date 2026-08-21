import { useEffect, useState } from "react"
import { getDashboard } from "../api/dashboard"
import type { Dashboard } from "../types/dashboard"



export default function DashboardPage() {
const [data, setData] = useState<Dashboard | null>(null);
const [error, setError] = useState<string | null>(null);
const [loading, setLoading] = useState<boolean>(true);

useEffect(() => {
  async function load() {
    try {
      const result = await getDashboard()
      setData(result)
      setError(null)
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong"
      setError(message)
    } 
    finally {
      setLoading(false)
    }
  }
  load()
}, []) // empty dependency array means run once on mount

if (loading) {
  return <div>Loading...</div>
}
if (error) {
  return <div>Error: {error}</div>
}
if (!data) {
  return <div>No dashboard data.</div>
}

return (
  <main>
    <h1>GitHub Dashboard</h1>
    <p>Commits: {data.commit_count}</p>
    <p>PRs opened: {data.pr_opened_count}</p>
    <p>PRs merged: {data.pr_merged_count}</p>
    <p>Active repos: {data.active_repo_count}</p>
  </main>
)
}

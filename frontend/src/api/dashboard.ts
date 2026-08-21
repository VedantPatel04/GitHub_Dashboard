import type { Dashboard } from "../types/dashboard";

export async function getDashboard(): Promise<Dashboard> {
    const url = `${import.meta.env.VITE_API_BASE_URL}/api/dashboard`;
    const response = await fetch(url);
    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }
    const data = (await response.json()) as Dashboard;
    return data;
}

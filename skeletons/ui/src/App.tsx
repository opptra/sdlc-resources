import { useEffect, useState } from "react";

export function App() {
  const [health, setHealth] = useState("checking");

  useEffect(() => {
    fetch("/api/health")
      .then((response) => {
        if (!response.ok) {
          throw new Error(String(response.status));
        }
        return response.json() as Promise<{ status: string }>;
      })
      .then((body) => setHealth(body.status))
      .catch(() => setHealth("unreachable"));
  }, []);

  return (
    <main>
      <h1>Example app</h1>
      <p>API health: {health}</p>
    </main>
  );
}

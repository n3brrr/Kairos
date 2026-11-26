import { useEffect, useState } from "react";
import { api } from "./api/client";
import { messages } from "./messages";

export function App() {
  const [version, setVersion] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    api.GET("/api/health").then(({ data }) => {
      if (active && data) setVersion(data.version);
    });
    return () => {
      active = false;
    };
  }, []);

  return (
    <main>
      <h1>{messages.appName}</h1>
      {version && <p>{messages.serverConnected(version)}</p>}
    </main>
  );
}

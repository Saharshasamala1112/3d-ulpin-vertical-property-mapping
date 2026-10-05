import { useEffect, useState } from "react";
import { healthService } from "../../services/health-service";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { LoadingSpinner } from "../../components/feedback/LoadingSpinner";
import { PageContainer } from "../../components/layout/PageContainer";

type ConnectionState = "loading" | "connected" | "disconnected";

export function HealthPage() {
  const [state, setState] = useState<ConnectionState>("loading");
  const [service, setService] = useState<string>("");

  const checkHealth = async () => {
    setState("loading");

    try {
      const response = await healthService.check();
      setService(response.service);
      setState(response.status === "ok" ? "connected" : "disconnected");
    } catch {
      setService("");
      setState("disconnected");
    }
  };

  useEffect(() => {
    void checkHealth();
  }, []);

  return (
    <PageContainer title="Backend Connectivity">
      <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
        <div>
          <h1>Backend Connectivity</h1>
          <p style={{ color: "var(--muted-foreground)" }}>
            Check the connection between the frontend and GEOSIX API.
          </p>
        </div>

        <Card>
          {state === "loading" && (
            <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
              <LoadingSpinner />
              <span>Checking backend connection...</span>
            </div>
          )}

          {state === "connected" && (
            <div
              style={{ display: "flex", flexDirection: "column", gap: "12px" }}
            >
              <div>
                <Badge>Connected</Badge>
              </div>
              <p>Frontend is successfully connected to the GEOSIX backend.</p>
              <p>Service: {service}</p>
            </div>
          )}

          {state === "disconnected" && (
            <div
              style={{ display: "flex", flexDirection: "column", gap: "12px" }}
            >
              <div>
                <Badge>Disconnected</Badge>
              </div>
              <p>
                Unable to connect to the GEOSIX backend. Please make sure the
                backend server is running on port 8000.
              </p>
              <Button onClick={() => void checkHealth()}>
                Retry Connection
              </Button>
            </div>
          )}
        </Card>
      </div>
    </PageContainer>
  );
}

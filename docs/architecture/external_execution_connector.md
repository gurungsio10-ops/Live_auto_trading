# External execution connector design

Atlas is the orchestration, intelligence, risk, monitoring, and UI layer.

External trading engines such as Hummingbot **must not** be merged into the Atlas
source tree. Integrate them as a separate worker/service that speaks to Atlas
through a clean boundary.

## Interface

`ExecutionConnector` lives in `app/execution/connectors/`:

- `start` / `stop` / `pause` / `resume`
- `health`
- `getStrategies` / `startStrategy` / `stopStrategy`
- `getOrders` / `getPositions`
- `emergencyStop`

The default implementation is `MockExecutionConnector` (safe, in-process).

## Recommended deployment shape

```
┌────────────┐   REST/WS/queue   ┌──────────────────┐
│ Atlas API  │ ◄───────────────► │ Hummingbot worker│
│ + dashboard│                   │ (separate repo)  │
└────────────┘                   └──────────────────┘
        │
        ▼
  RiskEngine / PaperSession / Kill switch
```

1. Run Hummingbot (or another engine) as its own process or container.
2. Implement a thin HTTP/WebSocket adapter that maps to `ExecutionConnector`.
3. Atlas remains the only place that authorises risk, kill-switch, and user UI.
4. Secrets for the remote engine stay in server-side env vars — never in the browser.

## Safety

- Live trading remains disabled unless env gates + live approval + kill-switch checks pass.
- `emergencyStop` on the connector must also flip Atlas kill-switch / pause as required.
- Paper mode continues to use `MockExchangeAdapter` / `PaperTradingEngine`.

## Overview

We maintain two suites of tests for our application:

### **Smoke Tests**
- *Isolation:* All network calls (including authentication) are fully **mocked out**.
- *Purpose:* Quickly verify that core UI components and routes render without hitting any backend.
- *Use Case:* Fast, lightweight sanity checks on every code change.

### **End‑to‑End (E2E) Tests**
- *Integration:* Execute complete user flows against a **live API** (or your local dev stack).
- *Coverage:* Real authentication, data fetches, and error‑handling paths.
- *Goal:* Ensure the entire system (frontend ↔ backend) works seamlessly together.

---
## Test Setup

In `cypress.e2e.config.ts` or `cypress.smoke.config.ts` the following environment variables need to be configured:
- `baseUrl` - set to either `http://localhost:3000/` or the URL of your dev stack (e.g. `https://<api gateway id>.execute-api.us-east-1.amazonaws.com/Prod/`).

#### Example setup for localhost:
```
e2e: {
    ...
    baseUrl: "<localhost or your API Gateway URL>",
  }
```

# Running the tests
If you are running the e2e tests, you will need to add the test account password to your env prior to executing the tests:
```
export TEST_ACCOUNT_PASSWORD=<password>

npm run cypress:e2e:run
```

You should get output like:
```
npm run cypress:e2e:run

> @awslabs/lisae2e@1.0.0 cypress:e2e:run
> cypress run --config-file cypress.e2e.config.ts


DevTools listening on ws://127.0.0.1:51352/devtools/browser/2f804c68-414e-4004-9e3f-0314417bf875

====================================================================================================

  (Run Starting)

  ┌────────────────────────────────────────────────────────────────────────────────────────────────┐
  │ Cypress:        14.3.0                                                                         │
  │ Browser:        Electron 130 (headless)                                                        │
  │ Node Version:   v18.20.4 (/.../.nvm/versions/node/v18.20.4/bin/node)                           │
  │ Specs:          1 found (administration.e2e.spec.ts)                                           │
  │ Searched:       src/e2e/specs/**/*.e2e.spec.ts                                                 │
  └────────────────────────────────────────────────────────────────────────────────────────────────┘


────────────────────────────────────────────────────────────────────────────────────────────────────

  Running:  administration.e2e.spec.ts                                                    (1 of 1)


  Administration features
    ✓ Logs in as admin and sees the Administration button (2656ms)
    ✓ Opens the Administration dropdown and shows menu items when clicked (1218ms)
    ✓ Logs in as non-admin and does not see the Administration button (1200ms)


  3 passing (5s)


  (Results)

  ┌────────────────────────────────────────────────────────────────────────────────────────────────┐
  │ Tests:        3                                                                                │
  │ Passing:      3                                                                                │
  │ Failing:      0                                                                                │
  │ Pending:      0                                                                                │
  │ Skipped:      0                                                                                │
  │ Screenshots:  0                                                                                │
  │ Video:        true                                                                             │
  │ Duration:     5 seconds                                                                        │
  │ Spec Ran:     administration.e2e.spec.ts                                                       │
  └────────────────────────────────────────────────────────────────────────────────────────────────┘


  (Video)

  -  Video output: /.../LISA/cypress/videos/e2e/administration.e2e.spec.ts.mp4


====================================================================================================

  (Run Finished)


       Spec                                              Tests  Passing  Failing  Pending  Skipped
  ┌────────────────────────────────────────────────────────────────────────────────────────────────┐
  │ ✔  administration.e2e.spec.ts               00:05        3        3        -        -        - │
  └────────────────────────────────────────────────────────────────────────────────────────────────┘
    ✔  All specs passed!                        00:05        3        3        -        -        -


```

## Run tests interactively
```
npm run cypress:e2e:open
```

# Linting

To ensure that code is meeting the enforced code standards you can run the following command within the `cypress` directory:
```
npm run lint:fix
```

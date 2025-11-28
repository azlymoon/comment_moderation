import http from "k6/http";
import { check, fail } from "k6";

// Stress profile: ramping arrival rate grows RPS, then ramps down.
export const options = {
  scenarios: {
    stress: {
      executor: "ramping-arrival-rate",
      startRate: 1,            // RPS at start
      timeUnit: "1s",
      preAllocatedVUs: 20,     // k6 will scale VUs up to handle the rate
      maxVUs: 120,
      stages: [
        { target: 10, duration: "1m" },
        { target: 20, duration: "1m" },
        { target: 30, duration: "1m" },
        { target: 40, duration: "1m" }, // peak tuned for CPU-heavy model
        { target: 0, duration: "30s" }, // ramp-down
      ],
      gracefulStop: "30s",
    },
  },
  thresholds: {
    "http_req_failed{phase:main}": ["rate<0.05"], // allow some errors under stress
  },
};

const BASE_URL = __ENV.BASE_URL || "http://127.0.0.1:8000";
const ADMIN_USER = __ENV.ADMIN_USER || "moderator";
const ADMIN_PASS = __ENV.ADMIN_PASS || "moderator";

const sampleTexts = [
  "I hate this movie",
  "This is a neutral statement about weather",
  "You are an idiot",
  "I am disappointed with this service",
  "Great job, team!",
];

export function setup() {
  const loginRes = http.post(
    `${BASE_URL}/auth/login`,
    JSON.stringify({ username: ADMIN_USER, password: ADMIN_PASS }),
    { headers: { "Content-Type": "application/json" } },
  );
  if (loginRes.status !== 200) {
    fail(`Login failed: ${loginRes.status} ${loginRes.body}`);
  }
  const token = loginRes.json("token");

  const svcRes = http.get(`${BASE_URL}/admin/services`, {
    headers: { "X-Admin-Token": token },
  });
  if (svcRes.status !== 200) {
    fail(`List services failed: ${svcRes.status} ${svcRes.body}`);
  }
  const services = svcRes.json();
  if (!services || services.length === 0) {
    fail("No services available to issue API key");
  }
  const serviceId = services[0].service_id || services[0].serviceId;

  const keyRes = http.post(`${BASE_URL}/admin/services/${serviceId}/api-keys`, null, {
    headers: { "X-Admin-Token": token },
  });
  if (keyRes.status !== 200 && keyRes.status !== 201) {
    fail(`Issue API key failed: ${keyRes.status} ${keyRes.body}`);
  }
  const apiKey = keyRes.json("api_key");

  // Warm-up the model once so peak stages measure steady-state.
  http.post(
    `${BASE_URL}/api/v1/moderation/text`,
    JSON.stringify({ service_id: serviceId, content_text: "Warmup request" }),
    {
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": apiKey,
      },
      tags: { phase: "warmup" },
    },
  );

  return { serviceId, apiKey };
}

export default function (data) {
  const text = sampleTexts[Math.floor(Math.random() * sampleTexts.length)];
  const res = http.post(
    `${BASE_URL}/api/v1/moderation/text`,
    JSON.stringify({ service_id: data.serviceId, content_text: text }),
    {
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": data.apiKey,
      },
      tags: { phase: "main" },
    },
  );

  const isOk = res.status === 200;
  let decision = null;
  if (isOk && res.body && res.body.length > 0) {
    try {
      decision = res.json("result.decision");
    } catch (e) {
      decision = null;
    }
  }

  check(res, {
    "status is 200": () => isOk,
    "decision present": () => decision !== null,
  });
}

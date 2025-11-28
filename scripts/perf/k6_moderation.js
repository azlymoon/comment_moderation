import http from "k6/http";
import { check, sleep, fail } from "k6";

export const options = {
  stages: [
    { duration: "30s", target: 5 }, // ramp-up
    { duration: "1m", target: 5 },  // steady
    { duration: "30s", target: 0 }, // ramp-down
  ],
  thresholds: {
    "http_req_failed{phase:main}": ["rate<0.01"],
    "http_req_duration{phase:main}": ["p(95)<800"],
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

  // Warm up model once; mark as warmup so thresholds ignore it.
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

  check(res, {
    "status is 200": (r) => r.status === 200,
    "decision present": (r) => !!r.json("result.decision"),
  });

  sleep(0.5);
}

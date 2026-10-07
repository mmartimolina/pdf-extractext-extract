import http from "k6/http";
import { check } from "k6";

const pdf = open("../../tests/sample.pdf", "b");

export const options = {
  stages: [
    { duration: "10s", target: 100 },
    { duration: "20s", target: 100 },
    { duration: "10s", target: 0 },
  ],
};

export default function () {
  const response = http.post(
    "http://localhost:8000/extract",
    pdf,
    {
      headers: {
        "Content-Type": "application/pdf",
      },
    },
  );

  check(response, {
    "status is 200": (r) => r.status === 200,
    "response contains content": (r) => r.json("content") !== undefined,
    "response contains page_count": (r) => r.json("page_count") !== undefined,
  });
}

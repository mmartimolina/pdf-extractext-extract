import http from "k6/http";
import { check } from "k6";

const pdfFiles = [
  open("../../tests/stress/pdfs/2020-Scrum-Guide-Spanish-Latin-South-American.pdf", "b"),
  open("../../tests/stress/pdfs/Essential-Kanban-Condensed-Spanish.pdf", "b"),
  open("../../tests/stress/pdfs/Filosofia Lean.pdf", "b"),
  open("../../tests/stress/pdfs/scrum_manager_historias_usuario.pdf", "b"),
];

export const options = {
  stages: [
    { duration: "10s", target: 100 },
    { duration: "20s", target: 100 },
    { duration: "10s", target: 0 },
  ],
};

export default function () {
  const pdf = pdfFiles[Math.floor(Math.random() * pdfFiles.length)];

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
  });
}
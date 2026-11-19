import React from "react";
import { renderToStaticMarkup } from "react-dom/server.node";
import { StandingsLists } from "./PublishedCompetitionStandings";

const run = {
  id: "row",
  rank: 11,
  start_number: "027",
  published_name: "Eva Nová",
  team: "Lhota",
  times: [{ attempt: 1, time: 18.4, status: "valid" }],
  final_time: 18.4,
  final_time_status: "valid",
};

const team = {
  id: "team",
  category_id: "category",
  category_name: "Dorostenky - družstvo",
  rank: 4,
  name: "Lhota",
  source_number: 1,
  total_time: 94.05,
  total_status: "valid",
  source_url: "https://mladez.dh.cz/vysledky.pdf",
  members: [run],
};

test("shows the organizer's team total separately from the member's time", () => {
  const html = renderToStaticMarkup(<StandingsLists teams={[team]} historical={[]} discipline="100m" />);
  expect(html).toContain("Týmový součet 94.05 s");
  expect(html).toContain("Časy členů družstva");
  expect(html).toContain("Eva Nová");
  expect(html).toContain("<td>11</td>");
  expect(html).toContain("<td>18.40 s</td>");
});

test("keeps historic age labels and their rankings in the 60 metre view", () => {
  const historical = [{ name: "Mladší žáci A – dívky", min_age: 6, max_age: 8, results: [run] }];
  const html = renderToStaticMarkup(<StandingsLists teams={[team]} historical={historical} discipline="60m" />);
  expect(html).toContain("Mladší žáci A – dívky · 6–8 let");
  expect(html).toContain("<td>11</td>");
  expect(html).not.toContain("Týmový součet");
});

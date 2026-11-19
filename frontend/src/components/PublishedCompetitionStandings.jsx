import { useQuery } from "@tanstack/react-query";
import api from "../api/axios";

function resultTime(time, status) {
  if (status === "missing") return "—";
  if (status === "invalid") return time == null ? "Neplatný" : `${time} s (neplatný)`;
  return time == null ? "—" : `${time.toFixed(2)} s`;
}

function PublishedRuns({ rows }) {
  return (
    <div className="results-table-wrapper">
      <table className="results-table">
        <thead>
          <tr>
            <th scope="col">Pořadí v listině</th>
            <th scope="col">Startovní číslo</th>
            <th scope="col">Závodník</th>
            <th scope="col">Družstvo</th>
            <th scope="col">První pokus</th>
            <th scope="col">Druhý pokus</th>
            <th scope="col">Výsledný čas</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>{row.rank ?? "—"}</td>
              <td>{row.start_number ?? "—"}</td>
              <td>{row.published_name || [row.first_name, row.last_name].filter(Boolean).join(" ") || "—"}</td>
              <td>{row.team ?? "—"}</td>
              {[1, 2].map((number) => {
                const attempt = row.times.find((item) => item.attempt === number);
                return <td key={number}>{resultTime(attempt?.time, attempt?.status)}</td>;
              })}
              <td>{row.final_time_unverified ? "Čas k ověření" : resultTime(row.final_time, row.final_time_status)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function PublishedCompetitionStandings({ competitionId, discipline }) {
  const { data, isError } = useQuery({
    queryKey: ["competition", competitionId, "published-standings"],
    enabled: Boolean(competitionId),
    queryFn: async () => {
      const response = await api.get(`/v1/competitions/${competitionId}/published-standings`);
      return response.data;
    },
  });

  if (isError) return <p>Doplňkové výsledkové listiny se nepodařilo načíst.</p>;
  return <StandingsLists teams={data?.teams ?? []} historical={data?.historical ?? []} discipline={discipline} />;
}

export function StandingsLists({ teams, historical, discipline }) {
  const categories = new Map();
  for (const team of teams) {
    if (!categories.has(team.category_id)) categories.set(team.category_id, []);
    categories.get(team.category_id).push(team);
  }

  return (
    <>
      {discipline !== "60m" && categories.size > 0 && (
        <section className="competition-published-standings" aria-labelledby="published-team-standings">
          <h2 id="published-team-standings">Družstva · 100 m</h2>
          {[...categories].map(([id, entries]) => (
            <details key={id}>
              <summary>{entries[0].category_name} · {entries.length} položek</summary>
              {entries.map((team) => (
                <details key={team.id}>
                  <summary>
                    {team.rank != null && `${team.rank}. `}
                    {team.name ?? `Družstvo č. ${team.source_number}`}
                    {" · Týmový součet "}{resultTime(team.total_time, team.total_status)}
                  </summary>
                  {team.members.length > 0 && (
                    <>
                      <h3>Časy členů družstva</h3>
                      <PublishedRuns rows={team.members} />
                    </>
                  )}
                  <p><a href={team.source_url}>Oficiální týmová listina</a></p>
                </details>
              ))}
            </details>
          ))}
        </section>
      )}
      {discipline !== "100m" && historical.length > 0 && (
        <section className="competition-published-standings" aria-labelledby="historical-standings">
          <h2 id="historical-standings">Historické výsledkové listiny · 60 m</h2>
          <p>Pořadí a věkové skupiny odpovídají původním výsledkovým listinám.</p>
          {historical.map((group) => (
            <details key={group.results[0].id}>
              <summary>
                {group.name} · {group.min_age}–{group.max_age} let
                {group.result_list_id && ` · ${group.result_list_id}`}
              </summary>
              <PublishedRuns rows={group.results} />
              {/^https:\/\//i.test(group.source_url ?? "") && (
                <p><a href={group.source_url}>Původní výsledková listina</a></p>
              )}
            </details>
          ))}
        </section>
      )}
    </>
  );
}

import groupResultLists from "./groupResultLists";

test("keeps official rank gaps and separates source standings that share a canonical category", () => {
  const combined = "Muži a starší dorostenci";
  const rows = [
    { _id: "1", rank: 2, source_category: { name: combined } },
    { _id: "2", rank: 3, source_category: { name: "Muži HZS" } },
    { _id: "3", rank: 6, source_category: { name: combined } },
    { _id: "4", rank: 6, source_category: { name: combined }, result_list_id: "B" },
  ];

  const lists = groupResultLists(rows, "Muži");
  expect(lists.map(({ name, block, results }) => [name, block, results.map((row) => row.rank)])).toEqual([
    [combined, null, [2, 6]],
    ["Muži HZS", null, [3]],
    [combined, "B", [6]],
  ]);
});

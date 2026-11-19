export default function groupResultLists(results, categoryName) {
  const lists = new Map();
  for (const result of results) {
    const name = result.source_category?.name ?? categoryName;
    const block = result.result_list_id ?? null;
    const id = JSON.stringify([block, name]);
    if (!lists.has(id)) lists.set(id, { id, name, block, results: [] });
    lists.get(id).results.push(result);
  }
  return [...lists.values()];
}

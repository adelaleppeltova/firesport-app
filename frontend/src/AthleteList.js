useEffect(() => {
  fetch(`${API_URL}/athletes`)
    .then((response) => response.json())
    .then((data) => setAthletes(data))
    .catch((error) => console.error(error));
}, []);

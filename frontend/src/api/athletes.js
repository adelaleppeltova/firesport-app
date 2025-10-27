import api from "./axios";

export const fetchAthletes = () => api.get("/athletes");
export const createAthlete = (data) => api.post("/athletes", data);

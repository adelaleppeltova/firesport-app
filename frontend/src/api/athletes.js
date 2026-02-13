import api from "./axios";

export const fetchAthletes = () => api.get("/v1/athletes");
export const createAthlete = (data) => api.post("/v1/athletes", data);
